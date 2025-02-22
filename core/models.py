from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """
    Кастомная модель пользователя, наследуемся от AbstractUser,
    чтобы добавить поле phone и при необходимости переопределить логику.
    """
    phone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

class Role(models.Model):
    """
    Простая модель ролей.
    """
    name = models.CharField(max_length=50, unique=True)
    users = models.ManyToManyField(
        'core.User',       # ссылаемся на нашу кастомную модель
        related_name='roles',
        blank=True
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Роль'
        verbose_name_plural = 'Роли'

class BusinessType(models.Model):
    """
    Хранит список возможных типов бизнеса (Marketplace, Rental, Restaurant, Mall и т.д.)
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    url = models.CharField(max_length=100, blank=True, null=True, default='no_url')

    def __str__(self):
        return self.name

def business_logo_path(instance, filename):
    # Сохраняем логотип в "slug/logos/filename"
    return f"{instance.slug}/logos/{filename}"

def business_bg_path(instance, filename):
    # Сохраняем фон в "slug/background/filename"
    return f"{instance.slug}/background/{filename}"
def html_template_path(instance, filename):
    # Сохраняем фон в "slug/background/filename"
    return f"{instance.slug}/own_site_files/{filename}"


class Business(models.Model):
    """
    Основная модель для хранения бизнесов.
    """
    owner = models.ForeignKey(
        'core.User',
        on_delete=models.CASCADE,
        related_name='businesses'
    )
    business_type = models.ForeignKey(
        'core.BusinessType',
        on_delete=models.CASCADE,
        related_name='businesses'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    business_logo = models.ImageField(upload_to=business_logo_path, blank=True, null=True)
    html_template = models.FileField(upload_to=html_template_pathpip, blank=True, null=True)
    product_card_template = models.FileField(upload_to='business/', blank=True, null=True)
    product_detail_template = models.FileField(upload_to='business/', blank=True, null=True)
    background_image = models.ImageField(upload_to=business_bg_path, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True)

    def __str__(self):
        return self.name
