from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum, F
from .models import ProductStock

@receiver(post_save, sender=ProductStock)
def update_product_activity(sender, instance, **kwargs):
    """Deactivate product if total available quantity is zero or less."""
    product = instance.variant.product
    total_available = (
        ProductStock.objects
        .filter(variant__product=product)
        .aggregate(total=Sum(F('quantity') - F('reserved_quantity')))
        .get('total') or 0
    )
    if total_available <= 0 and product.is_active:
        product.is_active = False
        product.save(update_fields=['is_active'])