from django.db import models
from django.utils import timezone

from core.models import BusinessType


# Create your models here.
from django.db import models

# Предположим, что Business лежит в core.models
# from core.models import Business

class Restaurant(models.Model):
    """
    Расширенная модель для ресторана, связанная 1:1 с Business.
    """
    business = models.OneToOneField(
        BusinessType,
        on_delete=models.CASCADE,
        related_name='restaurant',
        null=False,
        default=None
    )
    cuisine_type = models.CharField(max_length=100, blank=True, null=True,
        help_text="Тип кухни, например 'Итальянская', 'Японская' и т.п.")
    opening_hours = models.CharField(max_length=255, blank=True, null=True,
        help_text="Часы работы, например '10:00 - 22:00'")
    capacity = models.PositiveIntegerField(blank=True, null=True,
        help_text="Максимальное число гостей, если есть ограничение")
    liquor_license = models.BooleanField(default=False,
        help_text="Есть ли лицензия на алкоголь?")
    # можно добавить другие поля: доставка, Wi-Fi, парковка, и т.д.

    created_at = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Restaurant for {self.business.name}"

    def save(self, *args, **kwargs):
        # Проверка: если business_type не "Restaurant", можно выбросить ошибку
        # Или оставить это на уровне валидации формы.
        if self.business.business_type.name != 'Restaurant':
            raise ValueError("Связанный Business не является типом 'Restaurant'.")
        super().save(*args, **kwargs)

class MenuCategory(models.Model):
    """
    Категория меню внутри ресторана: «Закуски», «Основные блюда», «Напитки» и т.п.
    """
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='menu_categories'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Restaurant: {self.restaurant.business.name})"


class MenuItem(models.Model):
    """
    Конкретное блюдо или позиция меню.
    """
    category = models.ForeignKey(
        MenuCategory,
        on_delete=models.CASCADE,
        related_name='items'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='restaurant/menu_items/', blank=True, null=True)
    is_available = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Category: {self.category.name})"

from django.conf import settings  # для USER_MODEL, если надо

class RestaurantOrder(models.Model):
    """
    Заказ в ресторане (онлайн или за столиком).
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='restaurant_orders'
    )
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='orders'
    )

    table_number = models.CharField(max_length=50, blank=True, null=True,
        help_text="Столик, если заказ внутри ресторана")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_total(self):
        total = sum(item.subtotal for item in self.items.all())
        self.total_amount = total
        self.save()
        return total

    def __str__(self):
        return f"Order #{self.id} in {self.restaurant.business.name}"


class RestaurantOrderItem(models.Model):
    """
    Позиция заказа: конкретное блюдо и количество.
    """
    order = models.ForeignKey(
        RestaurantOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(default=1)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.price_per_unit
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.name} (Order #{self.order.id})"

class TableReservation(models.Model):
    """
    Бронирование столика в ресторане.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('canceled', 'Canceled'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='table_reservations'
    )
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='table_reservations'
    )
    reservation_date = models.DateTimeField()
    table_number = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Reservation #{self.id} at {self.restaurant.business.name}"

