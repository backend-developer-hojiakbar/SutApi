from django.contrib import admin
from .models import User, Ombor, Kategoriya, Birlik, Mahsulot, Purchase, PurchaseItem, Sotuv, SotuvItem, Payment, SotuvQaytarish, SotuvQaytarishItem, OmborMahsulot
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'user_type', 'balance', 'is_staff', 'created_by')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('email', 'phone_number', 'balance')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('User Type', {'fields': ('user_type','created_by')}),
    )
    readonly_fields = ('balance',)

@admin.register(Ombor)
class OmborAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'responsible_person', 'mahsulotlar_soni', 'mahsulotlar_royxati')
    readonly_fields = ('mahsulotlar_royxati',)

    def mahsulotlar_soni(self, obj):
        return obj.ombormahsulot_set.count()
    mahsulotlar_soni.short_description = "Mahsulot turlari soni"

    def mahsulotlar_royxati(self, obj):
        mahsulotlar = obj.ombormahsulot_set.all()
        if not mahsulotlar:
            return "Mahsulotlar mavjud emas"
        html = "<ul>"
        for item in mahsulotlar:
            html += f"<li>{item.mahsulot.name} - {item.soni} dona</li>"
        html += "</ul>"
        return format_html(html)
    mahsulotlar_royxati.short_description = "Mahsulotlar ro'yxati"

@admin.register(Kategoriya)
class KategoriyaAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Birlik)
class BirlikAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Mahsulot)
class MahsulotAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'birlik', 'kategoriya', 'narx')

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1

class PurchaseAdmin(admin.ModelAdmin):
    inlines = [PurchaseItemInline]

    def save_model(self, request, obj, form, change):
        obj.save()

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            instance.purchase = form.instance
            instance.save()
        formset.save_m2m()
        form.instance.save()  # Total_sum ni yangilash uchun

admin.site.register(Purchase, PurchaseAdmin)

class SotuvItemInline(admin.TabularInline):
    model = SotuvItem
    extra = 1

@admin.register(Sotuv)
class SotuvAdmin(admin.ModelAdmin):
    list_display = ('sana', 'sotib_oluvchi', 'total_sum', 'ombor')
    inlines = [SotuvItemInline]
    fields = ('sotib_oluvchi', 'ombor')  # total_sum ni olib tashladim
    readonly_fields = ('total_sum',)  # total_sum faqat o'qish uchun

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            instance.sotuv = form.instance
            instance.save()
        formset.save_m2m()
        form.instance.save()

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'sana', 'summa')


# Mavjud kodlar

class SotuvQaytarishItemInline(admin.TabularInline):
    model = SotuvQaytarishItem
    extra = 1
    fields = ('mahsulot', 'soni', 'narx')
    readonly_fields = ()

@admin.register(SotuvQaytarish)
class SotuvQaytarishAdmin(admin.ModelAdmin):
    list_display = ('sana', 'qaytaruvchi', 'total_sum', 'ombor')
    inlines = [SotuvQaytarishItemInline]
    fields = ('qaytaruvchi', 'ombor')
    readonly_fields = ('total_sum', 'sana')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        qaytaruvchi = form.instance.qaytaruvchi
        qaytarish_ombor = form.instance.ombor

        # Qaytaruvchiga bog‘langan omborni topish
        try:
            qaytaruvchi_ombor = Ombor.objects.get(responsible_person=qaytaruvchi)
        except Ombor.DoesNotExist:
            self.message_user(request, "Qaytaruvchiga bog‘langan ombor topilmadi.", level='error')
            return

        # Omborda yetarli mahsulot borligini tekshirish
        instances = formset.save(commit=False)
        for instance in instances:
            try:
                ombor_mahsulot = OmborMahsulot.objects.get(ombor=qaytaruvchi_ombor, mahsulot=instance.mahsulot)
                if ombor_mahsulot.soni < instance.soni:
                    self.message_user(request, f"{instance.mahsulot.name} uchun omborda yetarli mahsulot yo‘q.", level='error')
                    return
            except OmborMahsulot.DoesNotExist:
                self.message_user(request, f"{instance.mahsulot.name} mahsuloti qaytaruvchi omborda mavjud emas.", level='error')
                return

        # Ombordan mahsulotlarni ayirish
        total_sum = 0
        for instance in instances:
            ombor_mahsulot = OmborMahsulot.objects.get(ombor=qaytaruvchi_ombor, mahsulot=instance.mahsulot)
            ombor_mahsulot.soni -= instance.soni
            ombor_mahsulot.save()

            instance.sotuv_qaytarish = form.instance
            instance.save()
            total_sum += instance.soni * instance.narx

            # Qaytarish omboriga mahsulotni qo‘shish
            ombor_mahsulot, created = OmborMahsulot.objects.get_or_create(
                ombor=qaytarish_ombor,
                mahsulot=instance.mahsulot,
                defaults={'soni': 0}
            )
            ombor_mahsulot.soni += instance.soni
            ombor_mahsulot.save()

        formset.save_m2m()
        form.instance.total_sum = total_sum
        form.instance.save()

        # Qaytaruvchining balansini yangilash
        qaytaruvchi.balance = float(qaytaruvchi.balance) + float(total_sum)
        qaytaruvchi.save()

    def delete_model(self, request, obj):
        qaytaruvchi = obj.qaytaruvchi
        qaytarish_ombor = obj.ombor

        try:
            qaytaruvchi_ombor = Ombor.objects.get(responsible_person=qaytaruvchi)
        except Ombor.DoesNotExist:
            self.message_user(request, "Qaytaruvchiga bog‘langan ombor topilmadi.", level='error')
            return

        # Omborga qayta tiklash
        for item in obj.items.all():
            # Qaytaruvchi omboriga mahsulotlarni qaytarish
            ombor_mahsulot, created = OmborMahsulot.objects.get_or_create(
                ombor=qaytaruvchi_ombor,
                mahsulot=item.mahsulot,
                defaults={'soni': 0}
            )
            ombor_mahsulot.soni += item.soni
            ombor_mahsulot.save()

            # Qaytarish omboridan mahsulotlarni ayirish
            try:
                qaytarish_ombor_mahsulot = OmborMahsulot.objects.get(
                    ombor=qaytarish_ombor,
                    mahsulot=item.mahsulot
                )
                qaytarish_ombor_mahsulot.soni -= item.soni
                if qaytarish_ombor_mahsulot.soni < 0:
                    self.message_user(request, f"{item.mahsulot.name} uchun qaytarish omborda yetarli mahsulot yo‘q.", level='error')
                    return
                qaytarish_ombor_mahsulot.save()
            except OmborMahsulot.DoesNotExist:
                self.message_user(request, f"{item.mahsulot.name} qaytarish omborda topilmadi.", level='error')
                return

        # Balansni qayta tiklash
        qaytaruvchi.balance = float(qaytaruvchi.balance) - float(obj.total_sum)
        qaytaruvchi.save()

        super().delete_model(request, obj)