from rest_framework import serializers
from .models import BusinessType
from marketplace.models import (
    Product,
    ProductVariant,
    ProductImage,
    ProductStock,
    ProductVariantAttribute,
    Category,
)

# Serializers
class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'is_main', 'alt_text', 'display_order']

class ProductStockSerializer(serializers.ModelSerializer):
    location = serializers.SerializerMethodField()

    def get_location(self, obj):
        return {
            "id": obj.location.id,
            "name": obj.location.name
        }

    class Meta:
        model = ProductStock
        fields = ['id', 'location', 'quantity', 'reserved_quantity', 'is_available_for_sale']


class ProductVariantAttributeSerializer(serializers.ModelSerializer):
    category_attribute_name = serializers.SerializerMethodField()
    predefined_value_name = serializers.SerializerMethodField()

    def get_category_attribute_name(self, obj):
        return obj.category_attribute.attribute.name if obj.category_attribute and obj.category_attribute.attribute else None

    def get_predefined_value_name(self, obj):
        return obj.predefined_value.value if obj.predefined_value else None

    class Meta:
        model = ProductVariantAttribute
        fields = [
            "id",
            "category_attribute",
            "category_attribute_name",
            "predefined_value",
            "predefined_value_name",
            "custom_value",
        ]

class ProductVariantSerializer(serializers.ModelSerializer):
    attributes = ProductVariantAttributeSerializer(many=True)
    stocks = ProductStockSerializer(many=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "price",
            "discount",
            "current_price",
            "show_this",
            "has_custom_name",
            "custom_name",
            "has_custom_description",
            "custom_description",
            "attributes",
            "stocks",
            "barcode",
            "barcode_image"
        ]

class ProductDetailSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True)
    variants = ProductVariantSerializer(many=True)
    category_name = serializers.CharField(source='category.name')

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'category', 'category_name',
            'on_the_main', 'is_active', 'images', 'variants'
        ]