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
    created_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)# Balans qoldig'i

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['user_type']

    def __str__(self):
        return self.username


class Ombor(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    responsible_person = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_warehouses')
    current_stock = models.PositiveIntegerField()

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
    birlik = models.ForeignKey(Birlik, on_delete=models.SET_NULL, null=True)  # null=True saqlanadi
    kategoriya = models.ForeignKey(Kategoriya, on_delete=models.SET_NULL, null=True)  # null=True saqlanadi
    narx = models.DecimalField(max_digits=10, decimal_places=2)
    rasm = models.ImageField(upload_to='mahsulotlar/', blank=True, null=True)

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


# models.py
class Purchase(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)  # ID faqat o'qish uchun
    ombor = models.ForeignKey('Ombor', on_delete=models.CASCADE)
    sana = models.DateField()
    yetkazib_beruvchi = models.ForeignKey('all.User', on_delete=models.CASCADE)
    total_sum = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Purchase #{self.pk} - {self.ombor.name} - {self.sana}"

    def calculate_total_sum(self):
        return sum(item.soni * item.narx for item in self.items.all())

    def save(self, *args, **kwargs):
        with transaction.atomic():
            # Avval obyektni saqlash
            super().save(*args, **kwargs)

            # Total sum ni hisoblash va yangilash
            total_sum = self.calculate_total_sum()
            if self.total_sum != total_sum:
                self.total_sum = total_sum
                super().save(update_fields=['total_sum'])

            # Yetkazib beruvchining balansini yangilash (faqat total_sum > 0 bo‘lganda)
            if self.yetkazib_beruvchi and self.total_sum > 0:
                # Balansni qayta-qayta yangilashni oldini olish uchun flag
                if not hasattr(self, '_balance_updated') or not getattr(self, '_balance_updated', False):
                    print(
                        f"Yetkazib beruvchi balansiga {self.total_sum} qo'shilmoqda, oldingi balans={self.yetkazib_beruvchi.balance}")
                    self.yetkazib_beruvchi.balance += self.total_sum
                    self.yetkazib_beruvchi.save()
                    setattr(self, '_balance_updated', True)
                    print(f"Yangi balans={self.yetkazib_beruvchi.balance}")

    def delete(self, *args, **kwargs):
        # Yetkazib beruvchining balansini tiklash
        if self.total_sum > 0 and self.yetkazib_beruvchi:
            self.yetkazib_beruvchi.balance -= self.total_sum
            self.yetkazib_beruvchi.save()

        # Mahsulotlar sonini ombordan o‘chirish
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
        # Mahsulot sonini ombordan o‘chirish
        ombor_mahsulot = OmborMahsulot.objects.filter(
            ombor=self.purchase.ombor,
            mahsulot=self.mahsulot
        ).first()
        if ombor_mahsulot and ombor_mahsulot.soni >= self.soni:
            ombor_mahsulot.soni -= self.soni
            ombor_mahsulot.save()

        # Purchase ning total_sum ni yangilash
        self.purchase.total_sum = self.purchase.calculate_total_sum()
        self.purchase.save(update_fields=['total_sum'])

        # Yetkazib beruvchining balansini yangilash (agar zarur bo‘lsa)
        if self.purchase.total_sum > 0 and self.purchase.yetkazib_beruvchi:
            self.purchase.yetkazib_beruvchi.balance -= self.narx * self.soni
            self.purchase.yetkazib_beruvchi.save()

        super().delete(*args, **kwargs)


class Sotuv(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)  # ID faqat o'qish uchun
    sana = models.DateField(auto_now_add=True)
    sotib_oluvchi = models.ForeignKey('all.User', on_delete=models.CASCADE)
    total_sum = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ombor = models.ForeignKey('Ombor', on_delete=models.CASCADE, null=True, blank=True)

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
        super().save(update_fields=['total_sum'])

    def delete(self, *args, **kwargs):
        # Sotuv o‘chirilganda sotib oluvchining balansini tiklash
        if self.total_sum > 0 and self.sotib_oluvchi:
            self.sotib_oluvchi.balance += self.total_sum
            self.sotib_oluvchi.save()

        # Mahsulotlar sonini omborda qaytarish
        for item in self.items.all():
            ombor_mahsulot = OmborMahsulot.objects.filter(
                ombor=self.ombor,
                mahsulot=item.mahsulot
            ).first()
            if ombor_mahsulot:
                ombor_mahsulot.soni += item.soni
                ombor_mahsulot.save()

        # Sotib oluvchining omboriga qo‘shilgan mahsulotlarni ayirish
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

        # Sotuvchi ombordan mahsulotni ayirish
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

        # Sotib oluvchiga bog'langan omborga mahsulot qo'shish
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
        # Mahsulot sonini sotuvchi omboriga qaytarish
        ombor_mahsulot = OmborMahsulot.objects.filter(
            ombor=self.sotuv.ombor,
            mahsulot=self.mahsulot
        ).first()
        if ombor_mahsulot:
            ombor_mahsulot.soni += self.soni
            ombor_mahsulot.save()

        # Sotib oluvchining omboridan mahsulotni ayirish
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

        # Sotuvning umumiy summasini yangilash (agar zarur bo‘lsa)
        self.sotuv.total_sum = self.sotuv.calculate_total_sum()
        self.sotuv.save(update_fields=['total_sum'])

        # Sotib oluvchining balansini tiklash (agar zarur bo‘lsa)
        if self.sotuv.total_sum > 0 and self.sotuv.sotib_oluvchi:
            self.sotuv.sotib_oluvchi.balance += self.narx * self.soni
            self.sotuv.sotib_oluvchi.save()

        super().delete(*args, **kwargs)


class Payment(models.Model):
    TYPE_PAYMENTS = (
        ('naqd', 'naqd'),
        ('karta', 'Karta'),
        ('shot', 'Shot')
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    sana = models.DateField()
    summa = models.DecimalField(max_digits=10, decimal_places=2)
    typeSotuv = models.CharField(max_length=20, choices=TYPE_PAYMENTS, default='naqd')

    def __str__(self):
        return f"Payment #{self.pk} - {self.user.username} - {self.summa}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.user.balance += self.summa
        self.user.save()


class SotuvQaytarish(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)  # Sotuvga o‘xshatildi
    sana = models.DateTimeField(auto_now_add=True)
    qaytaruvchi = models.ForeignKey('all.User', on_delete=models.CASCADE, related_name='qaytarishlar')
    total_sum = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ombor = models.ForeignKey('Ombor', on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.qaytaruvchi.username} - {self.sana}"

    def calculate_total_sum(self):
        return sum(item.soni * item.narx for item in self.items.all())

    def save(self, *args, **kwargs):
        with transaction.atomic():
            total_sum = self.calculate_total_sum()
            self.total_sum = total_sum
            if self.total_sum > 0 and self.qaytaruvchi:
                self.qaytaruvchi.balance += self.total_sum  # Qaytarishda balansga qo‘shiladi
                self.qaytaruvchi.save()
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            if self.total_sum > 0 and self.qaytaruvchi:
                self.qaytaruvchi.balance -= self.total_sum  # O‘chirilganda balansdan ayirish
                self.qaytaruvchi.save()

            # Qaytarish omboridan mahsulotlarni o‘chirish
            for item in self.items.all():
                ombor_mahsulot = OmborMahsulot.objects.filter(
                    ombor=self.ombor,
                    mahsulot=item.mahsulot
                ).first()
                if ombor_mahsulot:
                    ombor_mahsulot.soni -= item.soni
                    if ombor_mahsulot.soni < 0:
                        raise ValidationError(f"{item.mahsulot.name} uchun omborda yetarli mahsulot yo‘q")
                    ombor_mahsulot.save()

            # Qaytaruvchi omboriga mahsulotlarni qaytarish
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

            super().delete(*args, **kwargs)


class SotuvQaytarishItem(models.Model):
    sotuv_qaytarish = models.ForeignKey(SotuvQaytarish, on_delete=models.CASCADE, related_name='items')
    mahsulot = models.ForeignKey('Mahsulot', on_delete=models.CASCADE)
    soni = models.PositiveIntegerField()
    narx = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.mahsulot.name} - {self.soni} dona"

    def save(self, *args, **kwargs):
        if not self.sotuv_qaytarish.ombor:
            raise ValidationError("Qaytarish uchun ombor belgilanmagan!")

        qaytaruvchi_ombor = Ombor.objects.filter(responsible_person=self.sotuv_qaytarish.qaytaruvchi).first()
        if not qaytaruvchi_ombor:
            raise ValidationError("Qaytaruvchiga bog‘langan ombor topilmadi.")

        ombor_mahsulot = OmborMahsulot.objects.filter(
            ombor=qaytaruvchi_ombor,
            mahsulot=self.mahsulot
        ).first()
        if not ombor_mahsulot or ombor_mahsulot.soni < self.soni:
            raise ValidationError(
                f"{self.mahsulot.name} uchun qaytaruvchi omborda yetarli mahsulot yo‘q. Mavjud: {ombor_mahsulot.soni if ombor_mahsulot else 0}"
            )
        ombor_mahsulot.soni -= self.soni
        ombor_mahsulot.save()

        qaytarish_ombor_mahsulot, created = OmborMahsulot.objects.get_or_create(
            ombor=self.sotuv_qaytarish.ombor,
            mahsulot=self.mahsulot,
            defaults={'soni': 0}
        )
        qaytarish_ombor_mahsulot.soni += self.soni
        qaytarish_ombor_mahsulot.save()

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