from PIL import Image
from django.db import models
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel

from core.models import Business


# Create your models here.
class Category(MPTTModel):
    """
    Иерархическая категория товаров (для маркетплейса).
    """
    name = models.CharField(max_length=100)
    parent = TreeForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE, related_name='children'
    )
    description = models.TextField(blank=True, null=True)
    page_identificator = models.CharField(max_length=100, blank=True, null=True, default=None)
    big_image = models.ImageField(upload_to='category_images/big_images/', blank=True, null=True, default=None)
    small_image = models.ImageField(upload_to='category_images/small_images/', blank=True, null=True, default=None)
    ordering = models.PositiveSmallIntegerField(default=0)


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Категория товара'
        verbose_name_plural = 'Категории товаров'

    class MPTTMeta:
        order_insertion_by = ['name']

    def __str__(self):
        ancestors = self.get_ancestors(include_self=False)
        return " - ".join([ancestor.name for ancestor in ancestors] + [self.name])





class Product(models.Model):
    """
    Товар на маркетплейсе.
    """
    business = models.ForeignKey(
        Business,  # или 'app_name.Business'
        on_delete=models.CASCADE,
        related_name='products',
        null=False,
        default=None,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='products'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    on_the_main = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

    def __str__(self):
        return self.name


class Attribute(models.Model):
    """
    Справочник атрибутов.
    Пример: 'Цвет', 'Материал', 'Размер', 'Бренд'
    """
    name = models.CharField(max_length=100, unique=True)  # Например: "Размер", "Цвет"
    has_predefined_values = models.BooleanField(default=False)  # Есть ли фиксированные значения?

    def __str__(self):
        return self.name

class AttributeValue(models.Model):
    """
    Здесь у нас будут параметры для некторых атрибутов, например если у нас есть размер
    то здесь будет храниться XXS XS S M L XL XXL и так далее
    """
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=100)  # Например: "XL", "Красный"

    class Meta:
        unique_together = ('attribute', 'value')  # Исключаем дубликаты

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"

class CategoryAttribute(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='category_attributes'
    )
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        related_name='category_attributes'
    )
    required = models.BooleanField(
        default=False,
        help_text="Если отмечено, для товаров в этой категории этот атрибут обязателен."
    )

    class Meta:
        unique_together = ('category', 'attribute')
        verbose_name = "Атрибут категории"
        verbose_name_plural = "Атрибуты категорий"

    def __str__(self):
        return f"{self.category.name} - {self.attribute.name} ({'обязательно' if self.required else 'не обязательно'})"


class ProductAttribute(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attributes')
    category_attribute = models.ForeignKey(CategoryAttribute, on_delete=models.CASCADE)
    
    # Если у атрибута есть predefined_values — выбираем из них, иначе — произвольное значение
    predefined_value = models.ForeignKey(AttributeValue, on_delete=models.PROTECT, null=True, blank=True)
    custom_value = models.CharField(max_length=255, blank=True)  # Для атрибутов без фиксированных значений

    class Meta:
        unique_together = ('product', 'category_attribute')  # У товара может быть только один размер/цвет

    def clean(self):
        # Валидация: запрещаем произвольные значения для атрибутов с predefined_values
        if self.category_attribute.attribute.has_predefined_values and not self.predefined_value:
            raise ValidationError(f"Для атрибута '{self.category_attribute.attribute.name}' нужно выбрать значение из списка")
        
        # Запрещаем predefined_value для атрибутов без фиксированных значений
        if not self.category_attribute.attribute.has_predefined_values and self.predefined_value:
            raise ValidationError(f"Атрибут '{self.category_attribute.attribute.name}' не поддерживает предустановленные значения")

    @property
    def display_value(self):
        return self.predefined_value.value if self.predefined_value else self.custom_value

def product_image_path(instance, filename):
    # instance.product.business.slug -> получаем slug бизнеса
    slug = instance.product.business.slug
    return f"{slug}/products/{filename}"

class ProductImage(models.Model):
    """
    Изображение к товару.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to=product_image_path)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # Сначала сохраняем изображение

        img = Image.open(self.image.path)  # Открываем изображение
        output_size = (300, 500)  # Указываем нужный размер
        img.thumbnail(output_size)  # Масштабируем изображение
        img.save(self.image.path)

    class Meta:
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'

    def __str__(self):
        return f"Image for {self.product.name}"
