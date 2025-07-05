from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0005_productvariant_barcode_productvariant_barcode_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_visible_on_marketplace',
            field=models.BooleanField(default=False, verbose_name='Показывать на маркетплейсе'),
        ),
        migrations.AddField(
            model_name='product',
            name='is_visible_on_own_site',
            field=models.BooleanField(default=False, verbose_name='Показывать на личном сайте'),
        ),
        migrations.RemoveField(
            model_name='product',
            name='on_the_main',
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['is_visible_on_marketplace'], name='marketplace_is_visib_market_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['is_visible_on_own_site'], name='marketplace_is_visib_own_idx'),
        ),
        migrations.RemoveIndex(
            model_name='product',
            name='marketplace_on_the__1be3cb_idx',
        ),
    ]
