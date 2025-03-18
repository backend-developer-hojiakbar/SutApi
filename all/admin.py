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
from django.db import transaction

class SotuvQaytarishItemInline(admin.TabularInline):
    model = SotuvQaytarishItem
    extra = 1  # Qo‘shimcha qatorlar soni

@admin.register(SotuvQaytarish)
class SotuvQaytarishAdmin(admin.ModelAdmin):
    inlines = [SotuvQaytarishItemInline]
    list_display = ('id', 'sana', 'qaytaruvchi', 'total_sum', 'ombor')
    search_fields = ('qaytaruvchi__username', 'sana')

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            # Total_sum ni hisoblash va yangilash
            obj.total_sum = obj.calculate_total_sum()
            obj.save(update_fields=['total_sum'])

            if obj.total_sum > 0 and obj.qaytaruvchi:
                obj.qaytaruvchi.balance += obj.total_sum
                obj.qaytaruvchi.save()