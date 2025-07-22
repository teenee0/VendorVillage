from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import ProductStock, ProductDefect, ProductSale


@receiver([post_save, post_delete], sender=ProductStock)
def update_product_is_active_on_stock_change(sender, instance, **kwargs):
    if instance.variant and instance.variant.product:
        instance.variant.product.update_is_active()


@receiver([post_save, post_delete], sender=ProductDefect)
def update_product_is_active_on_defect_change(sender, instance, **kwargs):
    """
    Обновляет is_active у продукта при изменении брака, так как он влияет на available_quantity.
    """
    stock = instance.stock
    if stock and stock.variant and stock.variant.product:
        stock.variant.product.update_is_active()


@receiver([post_save, post_delete], sender=ProductSale)
def update_product_is_active_on_sale_change(sender, instance, **kwargs):
    """Обновляет is_active при продаже или отмене продажи"""
    variant = instance.variant
    if variant and variant.product:
        variant.product.update_is_active()