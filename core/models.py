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

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


class Role(models.Model):
    """
    Простая модель ролей.
    """

    name = models.CharField(max_length=50, unique=True)
    users = models.ManyToManyField(
        "core.User",  # ссылаемся на нашу кастомную модель
        related_name="roles",
        blank=True,
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Роль"
        verbose_name_plural = "Роли"


class BusinessType(models.Model):
    """
    Хранит список возможных типов бизнеса (Marketplace, Rental, Restaurant, Mall и т.д.)
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    url = models.CharField(max_length=100, blank=True, null=True, default="no_url")
    slug = models.SlugField(max_length=100, blank=True, null=True, default="no_slug")

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
        "core.User", on_delete=models.CASCADE, related_name="businesses"
    )
    business_type = models.ForeignKey(
        "core.BusinessType", on_delete=models.CASCADE, related_name="businesses"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    business_logo = models.ImageField(
        upload_to=business_logo_path, blank=True, null=True
    )
    html_template = models.FileField(
        upload_to=html_template_path, blank=True, null=True
    )
    product_card_template = models.FileField(
        upload_to="business/", blank=True, null=True
    )
    product_detail_template = models.FileField(
        upload_to="business/", blank=True, null=True
    )
    background_image = models.ImageField(
        upload_to=business_bg_path, blank=True, null=True
    )
    receipt_html_template = models.TextField(
        blank=True, null=True, verbose_name="HTML шаблон чека",
        help_text="HTML шаблон для генерации PDF чека"
    )
    receipt_css_template = models.TextField(
        blank=True, null=True, verbose_name="CSS стили чека",
        help_text="CSS стили для генерации PDF чека"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True)

    def __str__(self):
        return self.name


class BusinessLocationType(models.Model):
    """Модель для хранения типов локаций бизнеса"""

    code = models.CharField(max_length=20, unique=True, verbose_name="Код типа")
    name = models.CharField(max_length=100, verbose_name="Название типа")
    description = models.TextField(blank=True, null=True, verbose_name="Описание типа")
    is_warehouse = models.BooleanField(default=False, verbose_name="Является складом")
    is_sales_point = models.BooleanField(
        default=False, verbose_name="Является точкой продаж"
    )
    icon = models.CharField(max_length=50, blank=True, null=True, verbose_name="Иконка")

    class Meta:
        verbose_name = "Тип локации бизнеса"
        verbose_name_plural = "Типы локаций бизнеса"

    def __str__(self):
        return self.name


class BusinessLocation(models.Model):
    """
    Универсальная модель для складов и точек продаж бизнеса.
    На начальном этапе может выполнять обе роли.
    """

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="locations",
        verbose_name="Бизнес",
    )
    name = models.CharField(max_length=255, verbose_name="Название")
    location_type = models.ForeignKey(
        BusinessLocationType,
        on_delete=models.PROTECT,
        verbose_name="Тип локации",
        related_name="locations"
    )
    address = models.CharField(max_length=500, verbose_name="Адрес")
    contact_phone = models.CharField(max_length=20, verbose_name="Контактный телефон")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    is_primary = models.BooleanField(default=False, verbose_name="Основная локация")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    opening_hours = models.JSONField(
        blank=True,
        null=True,
        verbose_name="Часы работы",
        help_text="Формат: {'monday': {'open': '09:00', 'close': '21:00'}, ...}",
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True, verbose_name="Широта"
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True, verbose_name="Долгота"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Локация бизнеса"
        verbose_name_plural = "Локации бизнеса"
        ordering = ["-is_primary", "name"]

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        # Если это основная локация, снимаем флаг с других локаций этого бизнеса
        if self.is_primary:
            BusinessLocation.objects.filter(business=self.business).exclude(
                id=self.id
            ).update(is_primary=False)
        super().save(*args, **kwargs)

    @property
    def is_warehouse(self):
        """Является ли локация складом"""
        return self.location_type.is_warehouse

    @property
    def is_sales_point(self):
        """Является ли локация точкой продаж"""
        return self.location_type.is_sales_point
