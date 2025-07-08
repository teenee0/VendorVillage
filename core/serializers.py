from rest_framework import serializers
from .models import BusinessType
from marketplace.models import (
    Product,
    ProductVariant,
    ProductImage,
    ProductStock,
    ProductVariantAttribute,
)
from marketplace.serializers import ProductVariantSerializer, ProductImageSerializer


# ✅ Для ProductImage
class ProductImageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["image", "is_main", "alt_text", "display_order"]


# ✅ Для Stock
class ProductStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductStock
        fields = [
            "location",
            "quantity",
            "reserved_quantity",
            "is_available_for_sale",
        ]


# ✅ Для Variant Attributes
class ProductVariantAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariantAttribute
        fields = ["category_attribute", "predefined_value", "custom_value"]


# ✅ Для Variant
class ProductVariantCreateSerializer(serializers.ModelSerializer):
    attributes = ProductVariantAttributeSerializer(many=True, required=True)
    stocks = ProductStockSerializer(many=True, required=False)

    class Meta:
        model = ProductVariant
        fields = [
            "sku",
            "price",
            "discount",
            "show_this",
            "has_custom_name",
            "custom_name",
            "has_custom_description",
            "custom_description",
            "attributes",
            "stocks",
        ]


# ✅ Для Product
class ProductCreateSerializer(serializers.ModelSerializer):
    images = ProductImageCreateSerializer(many=True, required=False)
    variants = ProductVariantCreateSerializer(many=True, required=True)

    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "category",
            "is_visible_on_marketplace",
            "is_visible_on_own_site",
            "is_active",
            "images",
            "variants",
        ]

    def validate_variants(self, variants):
        if not variants:
            raise serializers.ValidationError(
                "Товар должен содержать хотя бы один вариант."
            )
        return variants


class ProductDetailSerializer(ProductCreateSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta(ProductCreateSerializer.Meta):
        fields = ProductCreateSerializer.Meta.fields + ["category_name"]


class ProductListStockSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    available_quantity = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProductStock
        fields = [
            "location_name",
            "quantity",
            "reserved_quantity",
            "available_quantity",
        ]


class ExtendedBusinessProductVariantSerializer(ProductVariantSerializer):
    stocks = ProductListStockSerializer(many=True, read_only=True)

    class Meta(ProductVariantSerializer.Meta):
        fields = ProductVariantSerializer.Meta.fields + ["stocks"]


class BusinessTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessType
        fields = "__all__"  # Или укажите конкретные поля


class EnhancedProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    business_name = serializers.CharField(source="business.name", read_only=True)
    default_variant = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()
    max_price = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()
    stock_info = serializers.SerializerMethodField()
    variants_count = serializers.SerializerMethodField()
    variants = ExtendedBusinessProductVariantSerializer(many=True, read_only=True)

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
            "variants",
            "default_variant",
            "min_price",
            "max_price",
            "created_at",
            "main_image",
            "stock_info",
            "variants_count",
        ]

    def get_default_variant(self, obj):
        variant = obj.get_default_variant(strict=False)
        return ProductVariantSerializer(variant).data if variant else None

    def get_min_price(self, obj):
        min_price, _ = obj.price_range
        return min_price

    def get_max_price(self, obj):
        _, max_price = obj.price_range
        return max_price

    def get_main_image(self, obj):
        main_image = obj.main_image
        return ProductImageSerializer(main_image).data if main_image else None

    def get_stock_info(self, obj):
        stocks = ProductStock.objects.filter(
            variant__product=obj, location__location_type__is_warehouse=True
        ).select_related("location")

        total_quantity = sum(stock.quantity for stock in stocks)
        total_reserved = sum(stock.reserved_quantity for stock in stocks)
        total_available = total_quantity - total_reserved

        locations = [
            {
                "location_id": stock.location.id,
                "location_name": stock.location.name,
                "quantity": stock.quantity,
                "reserved": stock.reserved_quantity,
                "available": stock.available_quantity,
            }
            for stock in stocks
        ]

        return {
            "total_quantity": total_quantity,
            "total_reserved": total_reserved,
            "total_available": total_available,
            "locations": locations,
        }

    def get_variants_count(self, obj):
        return obj.variants.count()
