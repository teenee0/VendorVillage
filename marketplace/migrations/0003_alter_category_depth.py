# Generated by Django 5.1.2 on 2025-02-03 01:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0002_category_depth'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='depth',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
