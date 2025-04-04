from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import models, transaction


class CustomUserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, user_type=None, address=None, phone_number=None,
                    **extra_fields):
        if not username:
            raise ValueError('The Username field must be set')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, user_type=user_type, address=address,
                          phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'admin')
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('dealer', 'Dealer'),
        ('shop', 'Shop'),
        ('omborchi', 'Omborchi'),
        ('yetkazib_beruvchi', 'Yetkazib_beruvchi'),
    )

    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(blank=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    address = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    last_sotuv_vaqti = models.DateTimeField(blank=True, null=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    image = models.ImageField(upload_to='user_images/', blank=True, null=True)
    time = models.DateTimeField(null=False, default=timezone.now)  # NULL emas, default qiymat bilan

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['user_type']

    def __str__(self):
        return self.username


class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"


class Ombor(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    responsible_person = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_warehouses')
    current_stock = models.PositiveIntegerField()
    time = models.DateTimeField(auto_now_add=True)
    total_products = models.IntegerField(default=0)
    transaction_count = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class Kategoriya(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Birlik(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Mahsulot(models.Model):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=255, unique=True)
    birlik = models.ForeignKey(Birlik, on_delete=models.SET_NULL, null=True)
    kategoriya = models.ForeignKey(Kategoriya, on_delete=models.SET_NULL, null=True)
    narx = models.DecimalField(max_digits=10, decimal_places=2)
    rasm = models.ImageField(upload_to='mahsulotlar/', blank=True, null=True)
    time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class OmborMahsulot(models.Model):
    ombor = models.ForeignKey(Ombor, on_delete=models.CASCADE)
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE)
    soni = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('ombor', 'mahsulot')

    def __str__(self):
        return f"{self.ombor.name} - {self.mahsulot.name} - {self.soni}"


class Purchase(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    ombor = models.ForeignKey('Ombor', on_delete=models.CASCADE)
    sana = models.DateField()
    yetkazib_beruvchi = models.ForeignKey('User', on_delete=models.CASCADE)
    total_sum = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Purchase #{self.pk} - {self.ombor.name} - {self.sana}"

    def calculate_total_sum(self):
        return sum(item.soni * item.narx for item in self.items.all())

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            total_sum = self.calculate_total_sum()
            if self.total_sum != total_sum:
                self.total_sum = total_sum
                super().save(update_fields=['total_sum'])
            if self.yetkazib_beruvchi and self.total_sum > 0:
                if not hasattr(self, '_balance_updated') or not getattr(self, '_balance_updated', False):
                    self.yetkazib_beruvchi.balance += self.total_sum
                    self.yetkazib_beruvchi.save()
                    ActivityLog.objects.create(
                        user=self.yetkazib_beruvchi,
                        action="Purchase Created",
                        details=f"Purchase #{self.pk} created with total sum {self.total_sum}"
                    )
                    setattr(self, '_balance_updated', True)

    def delete(self, *args, **kwargs):
        if self.total_sum > 0 and self.yetkazib_beruvchi:
            self.yetkazib_beruvchi.balance -= self.total_sum
            self.yetkazib_beruvchi.save()
            ActivityLog.objects.create(
                user=self.yetkazib_beruvchi,
                action="Purchase Deleted",
                details=f"Purchase #{self.pk} deleted with total sum {self.total_sum}"
            )
        for item in self.items.all():
            ombor_mahsulot = OmborMahsulot.objects.filter(
                ombor=self.ombor,
                mahsulot=item.mahsulot
            ).first()
            if ombor_mahsulot and ombor_mahsulot.soni >= item.soni:
                ombor_mahsulot.soni -= item.soni
                ombor_mahsulot.save()
        super().delete(*args, **kwargs)


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    mahsulot = models.ForeignKey('Mahsulot', on_delete=models.CASCADE)
    soni = models.PositiveIntegerField()
    narx = models.DecimalField(max_digits=10, decimal_places=2)
    yaroqlilik_muddati = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.mahsulot.name} - {self.soni}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        ombor_mahsulot, created = OmborMahsulot.objects.get_or_create(
            ombor=self.purchase.ombor,
            mahsulot=self.mahsulot,
            defaults={'soni': 0}
        )
        ombor_mahsulot.soni += self.soni
        ombor_mahsulot.save()
        self.purchase.save()

    def delete(self, *args, **kwargs):
        ombor_mahsulot = OmborMahsulot.objects.filter(
            ombor=self.purchase.ombor,
            mahsulot=self.mahsulot
        ).first()
        if ombor_mahsulot and ombor_mahsulot.soni >= self.soni:
            ombor_mahsulot.soni -= self.soni
            ombor_mahsulot.save()
        self.purchase.total_sum = self.purchase.calculate_total_sum()
        self.purchase.save(update_fields=['total_sum'])
        if self.purchase.total_sum > 0 and self.purchase.yetkazib_beruvchi:
            self.purchase.yetkazib_beruvchi.balance -= self.narx * self.soni
            self.purchase.yetkazib_beruvchi.save()
        super().delete(*args, **kwargs)


class Sotuv(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    sana = models.DateField(auto_now_add=True)
    sotib_oluvchi = models.ForeignKey('User', on_delete=models.CASCADE)
    total_sum = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ombor = models.ForeignKey('Ombor', on_delete=models.CASCADE, null=True, blank=True)
    time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sotuv #{self.pk} - {self.sotib_oluvchi.username} - {self.sana}"

    def calculate_total_sum(self):
        return sum(item.soni * item.narx for item in self.items.all())

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        total_sum = self.calculate_total_sum()
        self.total_sum = total_sum
        if self.total_sum > 0:
            self.sotib_oluvchi.balance -= self.total_sum
            self.sotib_oluvchi.save()
            ActivityLog.objects.create(
                user=self.sotib_oluvchi,
                action="Sale Created",
                details=f"Sale #{self.pk} created with total sum {self.total_sum}"
            )
        super().save(update_fields=['total_sum'])

    def delete(self, *args, **kwargs):
        if self.total_sum > 0 and self.sotib_oluvchi:
            self.sotib_oluvchi.balance += self.total_sum
            self.sotib_oluvchi.save()
            ActivityLog.objects.create(
                user=self.sotib_oluvchi,
                action="Sale Deleted",
                details=f"Sale #{self.pk} deleted with total sum {self.total_sum}"
            )
        for item in self.items.all():
            ombor_mahsulot = OmborMahsulot.objects.filter(
                ombor=self.ombor,
                mahsulot=item.mahsulot
            ).first()
            if ombor_mahsulot:
                ombor_mahsulot.soni += item.soni
                ombor_mahsulot.save()
        if self.sotib_oluvchi.user_type in ['dealer', 'shop']:
            sotib_oluvchi_ombor = Ombor.objects.filter(responsible_person=self.sotib_oluvchi).first()
            if sotib_oluvchi_ombor:
                for item in self.items.all():
                    ombor_mahsulot_sotib_oluvchi = OmborMahsulot.objects.filter(
                        ombor=sotib_oluvchi_ombor,
                        mahsulot=item.mahsulot
                    ).first()
                    if ombor_mahsulot_sotib_oluvchi:
                        ombor_mahsulot_sotib_oluvchi.soni -= item.soni
                        ombor_mahsulot_sotib_oluvchi.save()
        super().delete(*args, **kwargs)


class SotuvItem(models.Model):
    sotuv = models.ForeignKey(Sotuv, on_delete=models.CASCADE, related_name='items')
    mahsulot = models.ForeignKey('Mahsulot', on_delete=models.CASCADE)
    soni = models.PositiveIntegerField()
    narx = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.mahsulot.name} - {self.soni}"

    def save(self, *args, **kwargs):
        if not self.sotuv.ombor:
            raise ValidationError("Sotuv uchun ombor belgilanmagan!")
        ombor_mahsulot = OmborMahsulot.objects.filter(
            ombor=self.sotuv.ombor,
            mahsulot=self.mahsulot
        ).first()
        if not ombor_mahsulot or ombor_mahsulot.soni < self.soni:
            raise ValidationError(
                f"Omborda {self.mahsulot.name} yetarli emas! Mavjud: {ombor_mahsulot.soni if ombor_mahsulot else 0}"
            )
        ombor_mahsulot.soni -= self.soni
        ombor_mahsulot.save()
        sotib_oluvchi = self.sotuv.sotib_oluvchi
        if sotib_oluvchi.user_type in ['dealer', 'shop']:
            sotib_oluvchi_ombor = Ombor.objects.filter(responsible_person=sotib_oluvchi).first()
            if sotib_oluvchi_ombor:
                ombor_mahsulot_sotib_oluvchi, created = OmborMahsulot.objects.get_or_create(
                    ombor=sotib_oluvchi_ombor,
                    mahsulot=self.mahsulot,
                    defaults={'soni': 0}
                )
                ombor_mahsulot_sotib_oluvchi.soni += self.soni
                ombor_mahsulot_sotib_oluvchi.save()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        ombor_mahsulot = OmborMahsulot.objects.filter(
            ombor=self.sotuv.ombor,
            mahsulot=self.mahsulot
        ).first()
        if ombor_mahsulot:
            ombor_mahsulot.soni += self.soni
            ombor_mahsulot.save()
        sotib_oluvchi = self.sotuv.sotib_oluvchi
        if sotib_oluvchi.user_type in ['dealer', 'shop']:
            sotib_oluvchi_ombor = Ombor.objects.filter(responsible_person=sotib_oluvchi).first()
            if sotib_oluvchi_ombor:
                ombor_mahsulot_sotib_oluvchi = OmborMahsulot.objects.filter(
                    ombor=sotib_oluvchi_ombor,
                    mahsulot=self.mahsulot
                ).first()
                if ombor_mahsulot_sotib_oluvchi:
                    ombor_mahsulot_sotib_oluvchi.soni -= self.soni
                    ombor_mahsulot_sotib_oluvchi.save()
        self.sotuv.total_sum = self.sotuv.calculate_total_sum()
        self.sotuv.save(update_fields=['total_sum'])
        if self.sotuv.total_sum > 0 and self.sotuv.sotib_oluvchi:
            self.sotuv.sotib_oluvchi.balance += self.narx * self.soni
            self.sotuv.sotib_oluvchi.save()
        super().delete(*args, **kwargs)


class Payment(models.Model):
    TYPE_PAYMENTS = (
        ('naqd', 'Naqd'),
        ('karta', 'Karta'),
        ('shot', 'Shot')
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    sana = models.DateField()
    summa = models.DecimalField(max_digits=10, decimal_places=2)
    typeSotuv = models.CharField(max_length=20, choices=TYPE_PAYMENTS, default='naqd')
    time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment #{self.pk} - {self.user.username} - {self.summa}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.user.balance += self.summa
        self.user.save()
        ActivityLog.objects.create(
            user=self.user,
            action="Payment Created",
            details=f"Payment #{self.pk} created with sum {self.summa}"
        )


from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Ombor, OmborMahsulot, Mahsulot, ActivityLog


class SotuvQaytarish(models.Model):
    CONDITION_CHOICES = (
        ('healthy', 'Sog‘lom'),
        ('unhealthy', 'Nosog‘lom'),
    )
    id = models.BigAutoField(primary_key=True, editable=False)
    sana = models.DateField(auto_now_add=True)
    qaytaruvchi = models.ForeignKey('User', on_delete=models.CASCADE, related_name='qaytarishlar')
    total_sum = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ombor = models.ForeignKey('Ombor', on_delete=models.CASCADE)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='healthy')
    time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.qaytaruvchi.username} - {self.sana}"

    def calculate_total_sum(self):
        return sum(item.soni * item.narx for item in self.items.all())

    def update_user_balance(self, total_sum):
        """Qaytaruvchi balansini yangilash."""
        # Balansga total_sum qo'shiladi (healthy yoki unhealthy bo'lishidan qat'i nazar)
        self.qaytaruvchi.balance += total_sum
        self.qaytaruvchi.save()

    def update_warehouse_stock(self):
        """Ombordagi mahsulot sonini yangilash."""
        qaytaruvchi_ombor = Ombor.objects.filter(responsible_person=self.qaytaruvchi).first()
        if not qaytaruvchi_ombor:
            raise ValidationError("Qaytaruvchiga biriktirilgan ombor topilmadi.")

        for item in self.items.all():
            # Qaytaruvchi omboridan mahsulotni ayirish
            ombor_mahsulot_qaytaruvchi, created = OmborMahsulot.objects.get_or_create(
                ombor=qaytaruvchi_ombor,
                mahsulot=item.mahsulot,
                defaults={'soni': 0}
            )
            if ombor_mahsulot_qaytaruvchi.soni < item.soni:
                raise ValidationError(f"{item.mahsulot.name} uchun omborda yetarli mahsulot yo'q")
            ombor_mahsulot_qaytaruvchi.soni -= item.soni
            ombor_mahsulot_qaytaruvchi.save()

            # Agar condition 'healthy' bo'lsa, tanlangan omborga mahsulot qo'shiladi
            if self.condition == 'healthy':
                ombor_mahsulot_qabul_qiluvchi, created = OmborMahsulot.objects.get_or_create(
                    ombor=self.ombor,
                    mahsulot=item.mahsulot,
                    defaults={'soni': 0}
                )
                ombor_mahsulot_qabul_qiluvchi.soni += item.soni
                ombor_mahsulot_qabul_qiluvchi.save()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            total_sum = self.calculate_total_sum()
            self.total_sum = total_sum
            super().save(update_fields=['total_sum'])

            if self.total_sum > 0 and self.qaytaruvchi:
                self.update_user_balance(self.total_sum)  # Balansni yangilash
                try:
                    self.update_warehouse_stock()  # Ombordagi mahsulot sonini yangilash
                except ValidationError as e:
                    raise ValidationError(str(e))

                ActivityLog.objects.create(
                    user=self.qaytaruvchi,
                    action="Return Created",
                    details=f"Return #{self.pk} created with total sum {self.total_sum}, condition: {self.condition}"
                )

    # `delete` metodida ham mos o'zgarishlarni kiritish
    def delete(self, *args, **kwargs):
        with transaction.atomic():
            total_sum = self.total_sum
            if total_sum > 0 and self.qaytaruvchi:
                self.qaytaruvchi.balance -= total_sum  # Balansni qaytarish
                self.qaytaruvchi.save()

            qaytaruvchi_ombor = Ombor.objects.filter(responsible_person=self.qaytaruvchi).first()
            if qaytaruvchi_ombor:
                for item in self.items.all():
                    ombor_mahsulot_qaytaruvchi, created = OmborMahsulot.objects.get_or_create(
                        ombor=qaytaruvchi_ombor,
                        mahsulot=item.mahsulot,
                        defaults={'soni': 0}
                    )
                    ombor_mahsulot_qaytaruvchi.soni += item.soni
                    ombor_mahsulot_qaytaruvchi.save()

            if self.condition == 'healthy':
                ombor_mahsulot = OmborMahsulot.objects.filter(
                    ombor=self.ombor,
                    mahsulot__in=self.items.all().values_list('mahsulot', flat=True)
                )
                for item in self.items.all():
                    ombor_mahsulot_qabul = ombor_mahsulot.filter(mahsulot=item.mahsulot).first()
                    if ombor_mahsulot_qabul and ombor_mahsulot_qabul.soni >= item.soni:
                        ombor_mahsulot_qabul.soni -= item.soni
                        ombor_mahsulot_qabul.save()

            ActivityLog.objects.create(
                user=self.qaytaruvchi,
                action="Return Deleted",
                details=f"Return #{self.pk} deleted with total sum {self.total_sum}"
            )
            super().delete(*args, **kwargs)


class SotuvQaytarishItem(models.Model):
    sotuv_qaytarish = models.ForeignKey(SotuvQaytarish, on_delete=models.CASCADE)
    mahsulot = models.ForeignKey(Mahsulot, on_delete=models.CASCADE)
    soni = models.PositiveIntegerField()
    narx = models.DecimalField(max_digits=10, decimal_places=2)
    is_defective = models.BooleanField(default=False)  # Yangi maydon

    def __str__(self):
        return f"{self.mahsulot.name} - {self.soni} dona"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        qaytaruvchi_ombor = Ombor.objects.filter(responsible_person=self.sotuv_qaytarish.qaytaruvchi).first()
        if qaytaruvchi_ombor:
            ombor_mahsulot = OmborMahsulot.objects.filter(
                ombor=qaytaruvchi_ombor,
                mahsulot=self.mahsulot
            ).first()
            if ombor_mahsulot:
                ombor_mahsulot.soni += self.soni
                ombor_mahsulot.save()
        qaytarish_ombor_mahsulot = OmborMahsulot.objects.filter(
            ombor=self.sotuv_qaytarish.ombor,
            mahsulot=self.mahsulot
        ).first()
        if qaytarish_ombor_mahsulot:
            qaytarish_ombor_mahsulot.soni -= self.soni
            qaytarish_ombor_mahsulot.save()
        super().delete(*args, **kwargs)


class DealerRequest(models.Model):
    CONDITION_CHOICES = (
        ('healthy', 'Sog‘lom'),
        ('unhealthy', 'Nosog‘lom'),
    )
    STATUS_CHOICES = (
        ('pending', 'Kutilmoqda'),
        ('approved', 'Tasdiqlangan'),
        ('rejected', 'Rad etilgan'),
    )

    id = models.BigAutoField(primary_key=True, editable=False)
    dealer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dealer_requests')
    shop = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shop_requests')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='healthy')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_sum = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        dealer_name = self.dealer.username if self.dealer else "Admin"
        return f"{dealer_name} -> {self.shop.username} - {self.created_at}"

    def calculate_total_sum(self):
        return sum(item.quantity * item.price for item in self.items.all())

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            total_sum = self.calculate_total_sum()
            if self.total_sum != total_sum:
                self.total_sum = total_sum
                super().save(update_fields=['total_sum'])

            if self.status == 'approved' and self.is_active:
                self.handle_approval()

    def handle_approval(self):
        shop = self.shop
        shop_ombor = Ombor.objects.filter(responsible_person=shop).first()
        dealer = self.dealer
        dealer_ombor = Ombor.objects.filter(responsible_person=dealer).first()

        if not shop_ombor:
            raise ValidationError("Do‘kon ombori topilmadi.")

        if not dealer_ombor:
            raise ValidationError("Diler ombori topilmadi.")

        for item in self.items.all():
            shop_ombor_mahsulot = OmborMahsulot.objects.filter(ombor=shop_ombor, mahsulot=item.product).first()
            dealer_ombor_mahsulot, created = OmborMahsulot.objects.get_or_create(
                ombor=dealer_ombor,
                mahsulot=item.product,
                defaults={'soni': 0}
            )
            if not shop_ombor_mahsulot or shop_ombor_mahsulot.soni < item.quantity:
                raise ValidationError(f"{item.product.name} uchun do‘kon omborida yetarli mahsulot yo‘q.")

            shop_ombor_mahsulot.soni -= item.quantity
            shop_ombor_mahsulot.save()
            dealer_ombor_mahsulot.soni += item.quantity
            dealer_ombor_mahsulot.save()

        shop.balance += self.total_sum
        shop.save()

        ActivityLog.objects.create(
            user=self.dealer if self.dealer else self.shop,
            action="Dealer Request Approved",
            details=f"Request #{self.pk} approved for {self.shop.username} with total sum {self.total_sum}, condition: {self.condition}"
        )

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            if self.status == 'approved' and self.is_active:
                shop = self.shop
                shop_ombor = Ombor.objects.filter(responsible_person=shop).first()
                dealer = self.dealer
                dealer_ombor = Ombor.objects.filter(responsible_person=dealer).first()

                for item in self.items.all():
                    shop_ombor_mahsulot = OmborMahsulot.objects.get(ombor=shop_ombor, mahsulot=item.product)
                    dealer_ombor_mahsulot = OmborMahsulot.objects.get(ombor=dealer_ombor, mahsulot=item.product)

                    shop_ombor_mahsulot.soni += item.quantity
                    shop_ombor_mahsulot.save()
                    dealer_ombor_mahsulot.soni -= item.quantity
                    dealer_ombor_mahsulot.save()

                shop.balance -= self.total_sum
                shop.save()

            super().delete(*args, **kwargs)


class DealerRequestItem(models.Model):
    dealer_request = models.ForeignKey(DealerRequest, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Mahsulot, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} dona"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.dealer_request.save()  # Total sum yangilanishi uchun