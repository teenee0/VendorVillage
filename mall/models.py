from django.db import models

# Create your models here.
from django.db import models

from core.models import Business


class Mall(models.Model):
    """
    Расширенная модель для торговых центров (Mall),
    связанная 1:1 с `Business`.
    """
    business = models.OneToOneField(
        Business,
        on_delete=models.CASCADE,
        related_name='mall'
    )
    total_floors = models.PositiveIntegerField(default=1,
        help_text="Сколько этажей в ТЦ")
    opening_hours = models.CharField(max_length=255, blank=True, null=True,
        help_text="Часы работы, например '10:00 - 22:00'")
    parking_spots = models.PositiveIntegerField(blank=True, null=True,
        help_text="Количество парковочных мест, если актуально")

    # Можно добавить и другие поля:
    # - website = models.URLField(blank=True, null=True)
    # - phone_info_center = models.CharField(...)  # телефон инфо-центра
    # - etc.

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Mall: {self.business.name}"

    def save(self, *args, **kwargs):
        """
        Проверка на то, что business имеет тип "Mall" в BusinessType,
        чтобы не связать магазин или ресторан с моделью Mall.
        """
        if self.business.business_type.name != 'Mall':
            raise ValueError("Связанный Business должен иметь тип 'Mall'.")
        super().save(*args, **kwargs)

class MallFloor(models.Model):
    """
    Этаж ТЦ, связан с Mall по ForeignKey (один ТЦ может иметь много этажей).
    """
    mall = models.ForeignKey(
        Mall,
        on_delete=models.CASCADE,
        related_name='floors'
    )
    floor_number = models.CharField(max_length=50,
        help_text="Условное обозначение этажа, например '1', '2', '3', '-1' (паркинг)")
    description = models.TextField(blank=True, null=True)

    # При желании: планировка, фото схемы, количество магазинов, ...
    # floor_plan = models.ImageField(upload_to='malls/floors/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Floor {self.floor_number} of {self.mall.business.name}"


class MallShop(models.Model):
    """
    Магазин внутри ТЦ, который также является отдельным Business в системе.
    """
    floor = models.ForeignKey(
        'MallFloor',
        on_delete=models.CASCADE,
        related_name='shops'
    )
    business = models.OneToOneField(
        'core.Business',
        on_delete=models.CASCADE,
        related_name='mall_shop',
        null=False,
        blank=True,
        default=None,
    )
    # Можно оставить дополнительные поля, специфичные для расположения в ТЦ:
    is_open = models.BooleanField(default=True,
        help_text="Открыт ли магазин сейчас?")
    description = models.TextField(blank=True, null=True,
        help_text="Доп. описание расположения, ассортимента и т. д.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        # business.name – это название магазина (как бизнес)
        return f"MallShop: {self.business.name} on floor {self.floor.floor_number}"