# Generated by Django 5.1.2 on 2025-02-03 13:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_business_product_card_template_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='business_logo',
            field=models.ImageField(blank=True, null=True, upload_to='business_logo/'),
        ),
    ]
