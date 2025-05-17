from PIL import Image
from django.db import models
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel
from django.core.exceptions import ValidationError
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
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_filterable = models.BooleanField(
        default=False,
        verbose_name="Использовать в фильтрах",
        help_text="Если отмечено, атрибут будет доступен для фильтрации в каталоге"
    )

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
        Business,
        on_delete=models.CASCADE,
        related_name='products',
        null=False,
        default=None,
        verbose_name="Бизнес"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='products',
        verbose_name="Категория"
    )
    name = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    on_the_main = models.BooleanField(default=False, verbose_name="На главной странице")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['on_the_main']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.name
    
    @property
    def available_attributes(self):
        """Возвращает доступные атрибуты для вариаций, которые отмечены для отображения справа"""
        if not self.category:
            return {}
        
        result = {}
        print([i for i in self.variants.all()])
        # Получаем атрибуты категории, где show_attribute_at_right=True
        for cat_attr in self.category.category_attributes.all():
            attr_name = cat_attr.attribute.name
            
            # Собираем все значения из вариантов этого товара
            values = set()
            for pva in ProductVariantAttribute.objects.filter(
                variant__product=self,
                category_attribute=cat_attr
            ):
                if pva.predefined_value:
                    values.add(pva.predefined_value.value)
                elif pva.custom_value:
                    values.add(pva.custom_value)
            
            result[attr_name] = {
                'values': list(values),
                'required': cat_attr.required,
                'attribute_id': cat_attr.attribute.id
            }
            
        return result
    
    @property
    def default_variant(self):
        """Возвращает вариант товара по умолчанию (для отображения в списках)"""
        # Сначала ищем вариант с show_this=True
        variant = self.variants.filter(show_this=True, stock_quantity__gt=0).first()
        if not variant:
            # Если такого нет, берем первый в наличии
            variant = self.variants.filter(stock_quantity__gt=0).first()
            if not variant:
                # Если нет в наличии, берем любой
                variant = self.variants.first()
        return variant
    
    @property
    def price_range(self):
        """Возвращает минимальную и максимальную цену среди вариантов"""
        variants = self.variants.filter(stock_quantity__gt=0)
        if not variants.exists():
            return None, None
            
        prices = [variant.current_price for variant in variants if variant.current_price is not None]
        
        if not prices:
            return None, None
            
        return min(prices), max(prices)
    
    @property
    def main_image(self):
        """Возвращает главное изображение продукта"""
        main = self.images.filter(is_main=True).first()
        if not main:
            main = self.images.first()
        return main
    
    @property
    def all_images(self):
        """Возвращает все изображения продукта"""
        return self.images.all().order_by('-is_main', 'display_order')


class Attribute(models.Model):
    """
    Справочник атрибутов.
    Пример: 'Цвет', 'Материал', 'Размер', 'Бренд'
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Название")
    has_predefined_values = models.BooleanField(
        default=False, 
        verbose_name="Имеет предустановленные значения"
    )
    is_filterable = models.BooleanField(
        default=False,
        verbose_name="Использовать в фильтрах",
        help_text="Если отмечено, атрибут будет доступен для фильтрации в каталоге"
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Порядок отображения"
    )

    class Meta:
        verbose_name = 'Атрибут'
        verbose_name_plural = 'Атрибуты'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class AttributeValue(models.Model):
    """
    Значения атрибутов.
    Например: XS, S, M, L, XL для размера или Красный, Синий для цвета.
    """
    attribute = models.ForeignKey(
        Attribute, 
        on_delete=models.CASCADE, 
        related_name='values',
        verbose_name="Атрибут"
    )
    value = models.CharField(max_length=100, verbose_name="Значение")
    display_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Порядок отображения"
    )
    color_code = models.CharField(
        max_length=7, 
        blank=True, 
        null=True,
        verbose_name="Код цвета",
        help_text="HEX-код цвета (например, #FF0000 для красного). Используется для атрибутов цвета."
    )
    #TODO ДОБАВИТЬ СЛАГ В КАТЕГОРИИ АТРИБУТЫ И ЗНАЧЕНИЯ АТРИБУТОВ, А ЕЩЕ ЛУЧШЕ И В ПРОДУКТЫ

    class Meta:
        unique_together = ('attribute', 'value')
        verbose_name = 'Значение атрибута'
        verbose_name_plural = 'Значения атрибутов'
        ordering = ['display_order', 'value']

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class CategoryAttribute(models.Model):
    """Связь между категорией и атрибутами, которые применимы к ней"""
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='category_attributes',
        verbose_name="Категория"
    )
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        related_name='category_attributes',
        verbose_name="Атрибут"
    )
    required = models.BooleanField(
        default=False,
        help_text="Если отмечено, для товаров в этой категории этот атрибут обязателен.",
        verbose_name="Обязательный"
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Порядок отображения"
    )
    show_attribute_at_right = models.BooleanField(
        default=False,
        help_text='Показывать атрибут в правой части страницы товара для выбора'
    )

    class Meta:
        unique_together = ('category', 'attribute')
        verbose_name = "Атрибут категории"
        verbose_name_plural = "Атрибуты категорий"
        ordering = ['display_order']

    def __str__(self):
        return f"{self.category.name} - {self.attribute.name} ({'обязательно' if self.required else 'не обязательно'})"


class ProductVariant(models.Model):
    """Вариант товара с разными атрибутами (размер, цвет и т.д.)"""
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='variants',
        verbose_name="Товар"
    )
    sku = models.CharField(
        max_length=100, 
        unique=True, 
        blank=True, 
        null=True,
        verbose_name="Артикул"
    )
    # Новые поля для названия и описания
    has_custom_name = models.BooleanField(
        default=False,
        verbose_name="Использовать своё название",
        help_text="Если отмечено, для этого варианта будет использоваться собственное название"
    )
    custom_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        verbose_name="Своё название",
        help_text="Название этого варианта (если отличается от основного товара)"
    )
    has_custom_description = models.BooleanField(
        default=False,
        verbose_name="Использовать своё описание",
        help_text="Если отмечено, для этого варианта будет использоваться собственное описание"
    )
    custom_description = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Своё описание",
        help_text="Описание этого варианта (если отличается от основного товара)"
    )
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Цена"
    )
    discount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="Процент скидки"
    )
    stock_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Количество на складе"
    )
    show_this = models.BooleanField(
        default=False, 
        verbose_name="Показывать в поиске",
        help_text="Если отмечено, этот вариант будет показан в результатах поиска и списках товаров"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = 'Вариант товара'
        verbose_name_plural = 'Варианты товаров'
        ordering = ['price', '-stock_quantity']
        indexes = [
            models.Index(fields=['price']),
            models.Index(fields=['stock_quantity']),
            models.Index(fields=['show_this']),
            models.Index(fields=['has_custom_name']),
            models.Index(fields=['has_custom_description']),
        ]

    def __str__(self):
        if self.has_custom_name and self.custom_name:
            return self.custom_name
            
        attrs = self.attributes.all()
        attrs_str = ', '.join([attr.display_value for attr in attrs])
        return f"{self.product.name} — {attrs_str}" if attrs_str else f"{self.product.name}"
    
    @property
    def name(self):
        """Возвращает название варианта (своё или от основного товара)"""
        if self.has_custom_name and self.custom_name:
            return self.custom_name
        return self.product.name
    
    @property
    def description(self):
        """Возвращает описание варианта (своё или от основного товара)"""
        if self.has_custom_description and self.custom_description:
            return self.custom_description
        return self.product.description
    
    @property
    def current_price(self):
        """Возвращает цену с учетом скидки в процентах"""
        if self.discount:
            return float(self.price) * (1 - float(self.discount)/100)
        return float(self.price)

    @property
    def discount_amount(self):
        """Возвращает сумму скидки в рублях"""
        if self.discount:
            return float(self.price) * float(self.discount)/100
        return 0
    
    @property
    def is_in_stock(self):
        """Проверяет наличие на складе"""
        return self.stock_quantity > 0


class ProductVariantAttribute(models.Model):
    """Связь между вариантом товара и значением атрибута"""
    variant = models.ForeignKey(
        ProductVariant, 
        on_delete=models.CASCADE, 
        related_name='attributes',
        verbose_name="Вариант товара"
    )
    category_attribute = models.ForeignKey(
        CategoryAttribute, 
        on_delete=models.CASCADE,
        verbose_name="Атрибут категории"
    )
    predefined_value = models.ForeignKey(
        AttributeValue, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        verbose_name="Предустановленное значение"
    )
    custom_value = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name="Произвольное значение"
    )

    class Meta:
        unique_together = ('variant', 'category_attribute')
        verbose_name = "Атрибут варианта товара"
        verbose_name_plural = "Атрибуты вариантов товаров"

    def clean(self):
        super().clean()
        attr = self.category_attribute.attribute
        
        # Проверка для атрибутов с предопределенными значениями
        if attr.has_predefined_values:
            if not self.predefined_value:
                raise ValidationError(
                    f"Для атрибута '{attr.name}' нужно выбрать значение из списка"
                )
            
            # Проверяем, что выбранное значение принадлежит этому атрибуту
            if self.predefined_value.attribute != attr:
                raise ValidationError(
                    f"Значение '{self.predefined_value.value}' не принадлежит атрибуту '{attr.name}'"
                )
        
        # Проверка для атрибутов с произвольными значениями
        else:
            if self.predefined_value:
                raise ValidationError(
                    f"Атрибут '{attr.name}' не поддерживает предустановленные значения"
                )
            if not self.custom_value:
                raise ValidationError(
                    f"Для атрибута '{attr.name}' необходимо указать значение"
                )

    def save(self, *args, **kwargs):
        self.full_clean()  # Вызов валидации при сохранении
        super().save(*args, **kwargs)

    @property
    def display_value(self):
        return self.predefined_value.value if self.predefined_value else self.custom_value
    
    @property
    def attribute_name(self):
        return self.category_attribute.attribute.name

    def __str__(self):
        return f"{self.variant} - {self.attribute_name}: {self.display_value}"


def product_image_path(instance, filename):
    # instance.product.business.slug -> получаем slug бизнеса
    slug = instance.product.business.slug
    return f"{slug}/products/{filename}"

class ProductImage(models.Model):
    """Изображения для продуктов (основные)"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name="Продукт"
    )
    image = models.ImageField(
        upload_to=product_image_path,
        verbose_name="Изображение"
    )
    is_main = models.BooleanField(
        default=False, 
        help_text="Главное изображение для продукта",
        verbose_name="Главное"
    )
    alt_text = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        verbose_name="Альтернативный текст",
        help_text="Текст, который показывается, если изображение не загрузилось"
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Порядок отображения"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = 'Изображение продукта'
        verbose_name_plural = 'Изображения продуктов'
        ordering = ['-is_main', 'display_order']

    def __str__(self):
        return f"Изображение для {self.product}"

    def save(self, *args, **kwargs):
        # Если это главное изображение, сбрасываем флаг у других изображений этого продукта
        if self.is_main:
            ProductImage.objects.filter(
                product=self.product, 
                is_main=True
            ).exclude(id=self.id).update(is_main=False)
        super().save(*args, **kwargs)
