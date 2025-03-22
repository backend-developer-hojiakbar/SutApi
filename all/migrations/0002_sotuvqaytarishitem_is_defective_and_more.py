# Generated by Django 5.1.6 on 2025-03-22 10:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('all', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='sotuvqaytarishitem',
            name='is_defective',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='sotuvqaytarishitem',
            name='sotuv_qaytarish',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='all.sotuvqaytarish'),
        ),
    ]
