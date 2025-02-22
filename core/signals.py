import os
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Business

@receiver(post_save, sender=Business)
def create_business_folders(sender, instance, created, **kwargs):
    """
    При создании нового бизнеса автоматически создаёт папку с именем slug внутри MEDIA_ROOT,
    а также вложенные папки (например, "products", "images", "logos" и т.д.).
    """
    if created and instance.slug:
        base_path = os.path.join(settings.MEDIA_ROOT, instance.slug)
        # создаём папку бизнеса
        os.makedirs(base_path, exist_ok=True)

        # при желании создаём вложенные папки
        os.makedirs(os.path.join(base_path, 'products'), exist_ok=True)
        os.makedirs(os.path.join(base_path, 'background'), exist_ok=True)
        os.makedirs(os.path.join(base_path, 'logos'), exist_ok=True)
        os.makedirs(os.path.join(base_path, 'own_site_files'), exist_ok=True)
        # ... любые другие нужные подпапки ...
