from rest_framework import serializers
from .models import (
    Category,
    Product,
    ProductVariant,
    ProductImage,  # Новая модель вместо ProductVariantImage
    ProductVariantAttribute,
    AttributeValue,
    ProductStock,
    Attribute,
    CategoryAttribute,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "description",
            "big_image",
            "small_image",
            "page_identificator",
            "ordering",
            "is_active",
        ]


class CategoryBreadcrumbsSerializer(serializers.ModelSerializer):
    ancestors = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "ancestors"]

    def get_ancestors(self, obj):
        ancestors = obj.get_ancestors(include_self=False)
        return CategorySerializer(ancestors, many=True, fields=["id", "name"]).data


class AttributeValueSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source="attribute.name", read_only=True)

    class Meta:
        model = AttributeValue
        fields = ["id", "value", "attribute_name", "color_code"]


class ProductVariantAttributeSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(
        source="category_attribute.attribute.name", read_only=True
    )
    display_value = serializers.CharField(read_only=True)
    attribute_id = serializers.IntegerField(
        source="category_attribute.attribute.id", read_only=True
    )

    class Meta:
        model = ProductVariantAttribute
        fields = ["id", "attribute_name", "display_value", "attribute_id"]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_main", "alt_text", "created_at"]


class ProductStockSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    available_quantity = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProductStock
        fields = ["location_name", "available_quantity"]


class ProductVariantSerializer(serializers.ModelSerializer):
    attributes = ProductVariantAttributeSerializer(many=True, read_only=True)
    stocks = ProductStockSerializer(many=True, read_only=True)
    current_price = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()  # Исправлено название
    is_in_stock = serializers.BooleanField(read_only=True)
    display_name = serializers.SerializerMethodField()
    display_description = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "price",
            "discount",
            "discount_amount",
            "stock_quantity",
            "attributes",
            "current_price",
            "is_in_stock",
            "show_this",
            "has_custom_name",
            "custom_name",
            "display_name",
            "has_custom_description",
            "custom_description",
            "display_description",
            "stocks",
        ]

    def get_display_name(self, obj):
        return obj.name

    def get_display_description(self, obj):
        return obj.description

    def get_current_price(self, obj):
        """Возвращает цену с учетом скидки"""
        if obj.discount and obj.price > 0:
            # return float(obj.price) - float(obj.discount)  # Для абсолютной скидки
            # Или для процентной скидки:
            return float(obj.price) * (1 - float(obj.discount) / 100)
        return float(obj.price)

    def get_discount_amount(self, obj):
        """Возвращает сумму скидки в рублях"""
        if obj.discount and obj.price > 0:
            # return float(obj.discount)  # Для абсолютной скидки
            # Или для процентной скидки:
            return float(obj.price) * float(obj.discount) / 100
        return 0


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    business_name = serializers.CharField(source="business.name", read_only=True)
    default_variant = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()
    max_price = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "category",
            "category_name",
            "business",
            "business_name",
            "default_variant",
            "min_price",
            "max_price",
            "created_at",
            "main_image",
        ]

    def get_default_variant(self, obj):
        variant = obj.default_variant

        return ProductVariantSerializer(variant).data

    def get_min_price(self, obj):
        min_price, _ = obj.price_range
        return min_price

    def get_max_price(self, obj):
        _, max_price = obj.price_range
        return max_price

    def get_main_image(self, obj):
        main_image = obj.main_image
        if main_image:
            return ProductImageSerializer(main_image).data
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    business_name = serializers.CharField(source="business.name", read_only=True)
    variants = serializers.SerializerMethodField()
    available_attributes = serializers.SerializerMethodField()
    default_variant = serializers.SerializerMethodField()
    price_range = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "is_visible_on_marketplace",
            "is_visible_on_own_site",
            "is_active",
            "category",
            "category_name",
            "business",
            "business_name",
            "variants",
            "available_attributes",
            "default_variant",
            "price_range",
            "created_at",
            "updated_at",
            "images",
        ]

    def get_available_attributes(self, obj):
        return obj.available_attributes

    def get_default_variant(self, obj):
        variant = obj.get_default_variant(strict=True)
        if variant:
            return ProductVariantSerializer(variant).data
        return None

    def get_variants(self, obj):
        valid_variants = [
            v
            for v in obj.variants.filter(show_this=True)
            if v.available_quantity > 0
        ]
        return ProductVariantSerializer(valid_variants, many=True).data

    def get_price_range(self, obj):
        min_price, max_price = obj.price_range
        if min_price is None:
            return None
        return {
            "min_price": min_price,
            "max_price": max_price,
            "is_range": min_price != max_price,
        }
