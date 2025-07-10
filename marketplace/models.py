from PIL import Image
from django.db import models
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel
from django.core.exceptions import ValidationError
from core.models import Business, User
from django.http import Http404
from core.models import BusinessLocation
from .EAN_13_barcode_generator import generate_barcode
from django.db.models import Sum


# Create your models here.
class Category(MPTTModel):
    """
    Иерархическая категория товаров (для маркетплейса).
    """

    name = models.CharField(max_length=100)
    parent = TreeForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    description = models.TextField(blank=True, null=True)
    page_identificator = models.CharField(
        max_length=100, blank=True, null=True, default=None
    )
    big_image = models.ImageField(
        upload_to="category_images/big_images/", blank=True, null=True, default=None
    )
    small_image = models.ImageField(
        upload_to="category_images/small_images/", blank=True, null=True, default=None
    )
    ordering = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_filterable = models.BooleanField(
        default=False,
        verbose_name="Использовать в фильтрах",
        help_text="Если отмечено, атрибут будет доступен для фильтрации в каталоге",
    )

    class Meta:
        verbose_name = "Категория товара"
        verbose_name_plural = "Категории товаров"

    class MPTTMeta:
        order_insertion_by = ["name"]

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
        related_name="products",
        null=False,
        default=None,
        verbose_name="Бизнес",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="products",
        verbose_name="Категория",
    )
    name = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    is_visible_on_marketplace = models.BooleanField(
        default=False,
        verbose_name="Показывать на маркетплейсе",
    )
    is_visible_on_own_site = models.BooleanField(
        default=False,
        verbose_name="Показывать на личном сайте",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["is_visible_on_marketplace"]),
            models.Index(fields=["is_visible_on_own_site"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.name

    @property
    def available_attributes(self):
        """Возвращает атрибуты для отображения справа, собранные по всем вариантам"""
        attributes_data = {}

        # Проходим по всем вариантам товара
        for variant in self.variants.all():
            # Получаем атрибуты варианта, которые нужно показывать справа
            for attr in variant.get_right_attributes():
                attr_name = attr.category_attribute.attribute.name

                # Инициализируем запись для атрибута, если её ещё нет
                if attr_name not in attributes_data:
                    attributes_data[attr_name] = {
                        "values": set(),
                        "required": attr.category_attribute.required,
                        "attribute_id": attr.category_attribute.attribute.id,
                        "has_predefined_values": attr.category_attribute.attribute.has_predefined_values,
                    }

                # Добавляем значение атрибута
                if attr.predefined_value:
                    attributes_data[attr_name]["values"].add(
                        attr.predefined_value.value
                    )
                elif attr.custom_value:
                    attributes_data[attr_name]["values"].add(attr.custom_value)

        # Преобразуем множества в отсортированные списки
        for attr_name, data in attributes_data.items():
            data["values"] = sorted(data["values"])

        return attributes_data

    def update_is_active(self):
        """
        Обновляет поле is_active в зависимости от наличия доступных вариантов.
        Активен, если хотя бы один вариант с show_this=True и available_quantity > 0.
        Также выводит лог с названием товара, варианта и доступным количеством.
        """
        for variant in self.variants.filter(show_this=True):
            qty = variant.available_quantity
            print(f"[Проверка] Товар: {self.name} | Вариант: {variant} | Доступно: {qty}")

            if qty > 0:
                if not self.is_active:
                    self.is_active = True
                    self.save(update_fields=["is_active"])
                    print(f"[АКТИВАЦИЯ] '{self.name}' включён, есть доступный вариант: {variant}")
                return

        # Ни один подходящий вариант не найден
        if self.is_active:
            self.is_active = False
            self.save(update_fields=["is_active"])
            print(f"[ДЕАКТИВАЦИЯ] '{self.name}' выключен, нет доступных вариантов.")

    @property
    def default_variant(self):
        for variant in self.variants.filter(show_this=True):
            if variant.available_quantity > 0:
                return variant
        return None

    def get_default_variant(self, strict=True):
        """
        strict=True — только доступный.
        strict=False — любой видимый или просто первый.
        """
        if strict:
            return self.default_variant
        return self.variants.filter(show_this=True).first() or self.variants.first()


    @property
    def price_range(self):
        """Возвращает минимальную и максимальную цену среди вариантов с учетом наличия на складах"""
        variants = [
            v
            for v in self.variants.filter(show_this=True)
            if v.available_quantity > 0
        ]

        if not variants:
            return None, None

        # Получаем все актуальные цены
        prices = [v.current_price for v in variants if v.current_price is not None]

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
        return self.images.all().order_by("-is_main", "display_order")


class Attribute(models.Model):
    """
    Справочник атрибутов.
    Пример: 'Цвет', 'Материал', 'Размер', 'Бренд'
    """

    name = models.CharField(max_length=100, unique=True, verbose_name="Название")
    has_predefined_values = models.BooleanField(
        default=False, verbose_name="Имеет предустановленные значения"
    )
    is_filterable = models.BooleanField(
        default=False,
        verbose_name="Использовать в фильтрах",
        help_text="Если отмечено, атрибут будет доступен для фильтрации в каталоге",
    )
    display_order = models.PositiveSmallIntegerField(
        default=0, verbose_name="Порядок отображения"
    )

    class Meta:
        verbose_name = "Атрибут"
        verbose_name_plural = "Атрибуты"
        ordering = ["display_order", "name"]

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
        related_name="values",
        verbose_name="Атрибут",
    )
    value = models.CharField(max_length=100, verbose_name="Значение")
    display_order = models.PositiveSmallIntegerField(
        default=0, verbose_name="Порядок отображения"
    )
    color_code = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        verbose_name="Код цвета",
        help_text="HEX-код цвета (например, #FF0000 для красного). Используется для атрибутов цвета.",
    )
    # TODO ДОБАВИТЬ СЛАГ В КАТЕГОРИИ АТРИБУТЫ И ЗНАЧЕНИЯ АТРИБУТОВ, А ЕЩЕ ЛУЧШЕ И В ПРОДУКТЫ

    class Meta:
        unique_together = ("attribute", "value")
        verbose_name = "Значение атрибута"
        verbose_name_plural = "Значения атрибутов"
        ordering = ["display_order", "value"]

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class CategoryAttribute(models.Model):
    """Связь между категорией и атрибутами, которые применимы к ней"""

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="category_attributes",
        verbose_name="Категория",
    )
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        related_name="category_attributes",
        verbose_name="Атрибут",
    )
    required = models.BooleanField(
        default=False,
        help_text="Если отмечено, для товаров в этой категории этот атрибут обязателен.",
        verbose_name="Обязательный",
    )
    display_order = models.PositiveSmallIntegerField(
        default=0, verbose_name="Порядок отображения"
    )
    show_attribute_at_right = models.BooleanField(
        default=False,
        help_text="Показывать атрибут в правой части страницы товара для выбора",
    )

    class Meta:
        unique_together = ("category", "attribute")
        verbose_name = "Атрибут категории"
        verbose_name_plural = "Атрибуты категорий"
        ordering = ["display_order"]

    def __str__(self):
        return f"{self.category.name} - {self.attribute.name} ({'обязательно' if self.required else 'не обязательно'})"

def variants_barcode_path(instance, filename):
    # instance.product.business.slug -> получаем slug бизнеса
    slug = instance.product.business.slug
    return f"{slug}/barcodes/{filename}"

class ProductVariant(models.Model):
    """Вариант товара с разными атрибутами (размер, цвет и т.д.)"""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants", verbose_name="Товар"
    )

    locations = models.ManyToManyField(
        BusinessLocation,
        through="ProductStock",
        related_name="product_variants",
        verbose_name="Локации",
    )

    barcode = models.CharField(max_length=32, unique=True, blank=True, null=True)
    barcode_image = models.ImageField(upload_to=variants_barcode_path, blank=True, null=True)

    sku = models.CharField(
        max_length=100, unique=True, blank=True, null=True, verbose_name="Артикул"
    )
    # Новые поля для названия и описания
    has_custom_name = models.BooleanField(
        default=False,
        verbose_name="Использовать своё название",
        help_text="Если отмечено, для этого варианта будет использоваться собственное название",
    )
    custom_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Своё название",
        help_text="Название этого варианта (если отличается от основного товара)",
    )
    has_custom_description = models.BooleanField(
        default=False,
        verbose_name="Использовать своё описание",
        help_text="Если отмечено, для этого варианта будет использоваться собственное описание",
    )
    custom_description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Своё описание",
        help_text="Описание этого варианта (если отличается от основного товара)",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Процент скидки",
    )
    show_this = models.BooleanField(
        default=False,
        verbose_name="Показывать в поиске",
        help_text="Если отмечено, этот вариант будет показан в результатах поиска и списках товаров",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Вариант товара"
        verbose_name_plural = "Варианты товаров"
        ordering = ["price"]
        indexes = [
            models.Index(fields=["price"]),
            models.Index(fields=["show_this"]),
            models.Index(fields=["has_custom_name"]),
            models.Index(fields=["has_custom_description"]),
        ]

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if not self.barcode or not self.barcode_image:

            ean_code, image = generate_barcode()
            self.barcode = ean_code
            self.barcode_image.save(image.name, image, save=False)

        super().save(*args, **kwargs)

        if is_new and not self.sku:
            self.sku = f"{self.product.business.slug}-{self.pk}"
            ProductVariant.objects.filter(pk=self.pk).update(sku=self.sku)

    def __str__(self):
        if self.has_custom_name and self.custom_name:
            return self.custom_name

        attrs = self.attributes.all()
        attrs_str = ", ".join([attr.display_value for attr in attrs])
        return (
            f"{self.product.name} — {attrs_str}"
            if attrs_str
            else f"{self.product.name}"
        )

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
            return float(self.price) * (1 - float(self.discount) / 100)
        return float(self.price)

    @property
    def discount_amount(self):
        """Возвращает сумму скидки в рублях"""
        if self.discount:
            return float(self.price) * float(self.discount) / 100
        return 0

    @property
    def stock_quantity(self):
        """Общее количество на всех складах"""
        total = 0
        for stock in self.stocks.filter(
            location__location_type__is_warehouse=True
        ).select_related('location'):
            total += stock.quantity - stock.defect_quantity
        return total

    @property
    def available_quantity(self):
        """Доступное количество на всех складах"""
        total = 0
        for stock in self.stocks.filter(
            location__location_type__is_warehouse=True
        ).select_related('location'):
            total += stock.available_quantity
        return total

    @property
    def is_in_stock(self):
        """Проверяет наличие товара на любом из складов"""
        return self.available_quantity > 0

    def get_right_attributes(self):
        """Возвращает атрибуты варианта, которые нужно показывать справа"""
        return self.attributes.filter(
            category_attribute__show_attribute_at_right=True
        ).select_related(
            "category_attribute", "category_attribute__attribute", "predefined_value"
        )


class ProductStock(models.Model):
    """
    Остатки товаров в локациях бизнеса.
    Для упрощения объединяем складские остатки и остатки в точках продаж.
    """

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="stocks",
        verbose_name="Вариант товара",
    )
    location = models.ForeignKey(
        BusinessLocation,
        on_delete=models.CASCADE,
        related_name="product_stocks",
        verbose_name="Локация",
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество")
    reserved_quantity = models.PositiveIntegerField(
        default=0, verbose_name="Зарезервированное количество"
    )
    is_available_for_sale = models.BooleanField(
        default=True,
        verbose_name="Доступен для продажи",
        help_text="Если отмечено, товар можно продавать в этой локации",
    )
    last_updated = models.DateTimeField(
        auto_now=True, verbose_name="Последнее обновление"
    )

    class Meta:
        verbose_name = "Остаток товара"
        verbose_name_plural = "Остатки товаров"
        unique_together = ("variant", "location")
        indexes = [
            models.Index(fields=["variant", "location"]),
            models.Index(fields=["is_available_for_sale"]),
        ]

    def __str__(self):
        return f"{self.variant} в {self.location}: {self.available_quantity}"

    @property
    def defect_quantity(self):
        """Общее количество брака для этой записи"""

        return (
            self.defects.aggregate(total=Sum("quantity"))
            .get("total")
            or 0
        )

    @property
    def available_quantity(self):
        """Доступное количество (с учётом брака и резерва)"""
        return self.quantity - self.reserved_quantity - self.defect_quantity


class ProductDefect(models.Model):
    """Информация о бракованном товаре"""

    stock = models.ForeignKey(
        ProductStock,
        on_delete=models.CASCADE,
        related_name="defects",
        verbose_name="Остаток",
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество")
    reason = models.TextField(blank=True, verbose_name="Причина")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Брак товара"
        verbose_name_plural = "Брак товара"

    def __str__(self):
        return f"Брак {self.quantity} шт. для {self.stock}"
    
    def clean(self):
        if self.quantity < 0:
            raise ValidationError("Количество брака не может быть отрицательным.")

        current_defect = (
            self.stock.defects.exclude(pk=self.pk).aggregate(total=Sum("quantity"))["total"] or 0
        )
        total_defect_after_save = current_defect + self.quantity
        available_after_defect = self.stock.quantity - self.stock.reserved_quantity - total_defect_after_save

        if available_after_defect < 0:
            raise ValidationError("Недостаточно доступного количества для такого объёма брака.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class ProductVariantAttribute(models.Model):
    """Связь между вариантом товара и значением атрибута"""

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="attributes",
        verbose_name="Вариант товара",
    )
    category_attribute = models.ForeignKey(
        CategoryAttribute, on_delete=models.CASCADE, verbose_name="Атрибут категории"
    )
    predefined_value = models.ForeignKey(
        AttributeValue,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Предустановленное значение",
    )
    custom_value = models.CharField(
        max_length=255, blank=True, verbose_name="Произвольное значение"
    )

    class Meta:
        unique_together = ("variant", "category_attribute")
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
        return (
            self.predefined_value.value if self.predefined_value else self.custom_value
        )

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
        Product, on_delete=models.CASCADE, related_name="images", verbose_name="Продукт"
    )
    image = models.ImageField(upload_to=product_image_path, verbose_name="Изображение")
    is_main = models.BooleanField(
        default=False,
        help_text="Главное изображение для продукта",
        verbose_name="Главное",
    )
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Альтернативный текст",
        help_text="Текст, который показывается, если изображение не загрузилось",
    )
    display_order = models.PositiveSmallIntegerField(
        default=0, verbose_name="Порядок отображения"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Изображение продукта"
        verbose_name_plural = "Изображения продуктов"
        ordering = ["-is_main", "display_order"]

    def __str__(self):
        return f"Изображение для {self.product}"

    def save(self, *args, **kwargs):
        # Если это главное изображение, сбрасываем флаг у других изображений этого продукта
        if self.is_main:
            ProductImage.objects.filter(product=self.product, is_main=True).exclude(
                id=self.id
            ).update(is_main=False)
        super().save(*args, **kwargs)


class PaymentMethod(models.Model):
    code = models.CharField(
        max_length=32,
        unique=True,
        verbose_name="Код",
        help_text="Уникальный идентификатор, например 'cash', 'card', 'kaspi_qr'"
    )
    name = models.CharField(
        max_length=64,
        verbose_name="Название",
        help_text="Отображаемое название способа оплаты"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Способ оплаты"
        verbose_name_plural = "Способы оплаты"
        ordering = ["name"]

    def __str__(self):
        return self.name

class Receipt(models.Model):
    """
    Чек, объединяющий одну или несколько продаж (например, покупка нескольких товаров).
    """
    number = models.CharField(max_length=100, unique=True, verbose_name="Номер чека")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Итоговая сумма")
    payment_method = models.ForeignKey(
        "PaymentMethod",
        on_delete=models.PROTECT,
        verbose_name="Способ оплаты"
    )
    is_paid = models.BooleanField(default=False, verbose_name="Оплачено")
    customer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Покупатель"
    )
    customer_name = models.CharField(max_length=255, blank=True, verbose_name="Имя клиента (если нет аккаунта)")
    customer_phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон клиента")

    is_online = models.BooleanField(
        default=False,
        verbose_name="Онлайн покупка",
        help_text="True если заказ сделан через интернет"
    )

    class Meta:
        verbose_name = "Чек"
        verbose_name_plural = "Чеки"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Чек #{self.number} от {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ProductSale(models.Model):
    """
    Запись о продаже конкретного варианта товара.
    """
    variant = models.ForeignKey(
        "ProductVariant",
        on_delete=models.PROTECT,
        related_name="sales",
        verbose_name="Вариант товара"
    )
    location = models.ForeignKey(
        "core.BusinessLocation",
        on_delete=models.PROTECT,
        related_name="sales",
        verbose_name="Локация продажи"
    )
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    price_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Цена за единицу"
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Сумма продажи"
    )
    sale_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата продажи")
    is_paid = models.BooleanField(default=False)
    receipt = models.ForeignKey(
        "Receipt",
        on_delete=models.PROTECT,
        related_name="sales",
        verbose_name="Чек",
        null=True,
        blank=True
    )


    class Meta:
        verbose_name = "Продажа"
        verbose_name_plural = "Продажи"
        ordering = ["-sale_date"]

    def save(self, *args, **kwargs):
        if not self.total_price:
            self.total_price = self.quantity * float(self.price_per_unit)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.variant} — {self.quantity} шт."
