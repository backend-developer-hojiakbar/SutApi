# Generated by Django 5.0.6 on 2025-03-04 12:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('all', '0005_user_created_by'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='user_type',
            field=models.CharField(choices=[('admin', 'Admin'), ('dealer', 'Dealer'), ('shop', 'Shop'), ('omborchi', 'Omborchi'), ('yetkazib_beruvchi', 'Yetkazib_beruvchi')], max_length=20),
        ),
    ]
