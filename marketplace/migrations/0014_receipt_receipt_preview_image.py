# Generated by Django 5.1.2 on 2025-07-22 00:13

import marketplace.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0013_rename_pdf_file_receipt_receipt_pdf_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='receipt',
            name='receipt_preview_image',
            field=models.ImageField(blank=True, null=True, upload_to=marketplace.models.receipt_preview_path, verbose_name='Превью чека (jpg/png)'),
        ),
    ]
