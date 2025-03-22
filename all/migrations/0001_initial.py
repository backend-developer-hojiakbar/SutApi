# Generated by Django 5.1.6 on 2025-03-22 12:16

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Birlik',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Kategoriya',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(max_length=150, unique=True)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('user_type', models.CharField(choices=[('admin', 'Admin'), ('dealer', 'Dealer'), ('shop', 'Shop'), ('omborchi', 'Omborchi'), ('yetkazib_beruvchi', 'Yetkazib_beruvchi')], max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('is_staff', models.BooleanField(default=False)),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now)),
                ('address', models.CharField(blank=True, max_length=255, null=True)),
                ('phone_number', models.CharField(blank=True, max_length=20, null=True)),
                ('last_sotuv_vaqti', models.DateTimeField(blank=True, null=True)),
                ('balance', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('image', models.ImageField(blank=True, null=True, upload_to='user_images/')),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=255)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('details', models.TextField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Mahsulot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('sku', models.CharField(max_length=255, unique=True)),
                ('narx', models.DecimalField(decimal_places=2, max_digits=10)),
                ('rasm', models.ImageField(blank=True, null=True, upload_to='mahsulotlar/')),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('birlik', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='all.birlik')),
                ('kategoriya', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='all.kategoriya')),
            ],
        ),
        migrations.CreateModel(
            name='Ombor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('address', models.TextField(blank=True, null=True)),
                ('current_stock', models.PositiveIntegerField()),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('total_products', models.IntegerField(default=0)),
                ('transaction_count', models.IntegerField(default=0)),
                ('responsible_person', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_warehouses', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sana', models.DateField()),
                ('summa', models.DecimalField(decimal_places=2, max_digits=10)),
                ('typeSotuv', models.CharField(choices=[('naqd', 'Naqd'), ('karta', 'Karta'), ('shot', 'Shot')], default='naqd', max_length=20)),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Purchase',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('sana', models.DateField()),
                ('total_sum', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('ombor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='all.ombor')),
                ('yetkazib_beruvchi', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='PurchaseItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('soni', models.PositiveIntegerField()),
                ('narx', models.DecimalField(decimal_places=2, max_digits=10)),
                ('yaroqlilik_muddati', models.DateField(blank=True, null=True)),
                ('mahsulot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='all.mahsulot')),
                ('purchase', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='all.purchase')),
            ],
        ),
        migrations.CreateModel(
            name='Sotuv',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('sana', models.DateField(auto_now_add=True)),
                ('total_sum', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('ombor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='all.ombor')),
                ('sotib_oluvchi', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='SotuvItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('soni', models.PositiveIntegerField()),
                ('narx', models.DecimalField(decimal_places=2, max_digits=10)),
                ('mahsulot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='all.mahsulot')),
                ('sotuv', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='all.sotuv')),
            ],
        ),
        migrations.CreateModel(
            name='SotuvQaytarish',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('sana', models.DateField(auto_now_add=True)),
                ('total_sum', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('condition', models.CharField(choices=[('healthy', 'Sog‘lom'), ('unhealthy', 'Nosog‘lom')], default='healthy', max_length=20)),
                ('time', models.DateTimeField(auto_now_add=True)),
                ('ombor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='all.ombor')),
                ('qaytaruvchi', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qaytarishlar', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='SotuvQaytarishItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('soni', models.PositiveIntegerField()),
                ('narx', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_defective', models.BooleanField(default=False)),
                ('mahsulot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='all.mahsulot')),
                ('sotuv_qaytarish', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='all.sotuvqaytarish')),
            ],
        ),
        migrations.CreateModel(
            name='OmborMahsulot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('soni', models.PositiveIntegerField(default=0)),
                ('mahsulot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='all.mahsulot')),
                ('ombor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='all.ombor')),
            ],
            options={
                'unique_together': {('ombor', 'mahsulot')},
            },
        ),
    ]
