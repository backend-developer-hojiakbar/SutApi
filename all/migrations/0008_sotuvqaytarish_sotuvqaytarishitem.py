# Generated by Django 5.1.6 on 2025-03-17 07:52

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('all', '0007_ombor_total_products_ombor_transaction_count'),
    ]

    operations = [
        migrations.CreateModel(
            name='SotuvQaytarish',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sana', models.DateTimeField(auto_now_add=True)),
                ('total_sum', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
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
                ('mahsulot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='all.mahsulot')),
                ('sotuv_qaytarish', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='all.sotuvqaytarish')),
            ],
        ),
    ]
