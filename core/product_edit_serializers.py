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


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_main", "alt_text", "display_order"]


class ProductStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductStock
        fields = [
            "id",
            "location",
            "quantity",
            "reserved_quantity",
            "is_available_for_sale",
        ]


class ProductVariantAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariantAttribute
        fields = [
            "id",
            "category_attribute",
            "predefined_value",
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
            "show_this",
            "has_custom_name",
            "custom_name",
            "has_custom_description",
            "custom_description",
            "attributes",
            "stocks",
        ]


class ProductDetailSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True)
    variants = ProductVariantSerializer(many=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "category",
            "category_name",
            "is_visible_on_marketplace",
            "is_visible_on_own_site",
            "is_active",
            "images",
            "variants",
        ]


class ProductImageInputSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    image = serializers.ImageField(required=False)
    is_main = serializers.BooleanField()
    display_order = serializers.IntegerField()
    alt_text = serializers.CharField(allow_blank=True, required=False)


class ProductStockInputSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    location = serializers.IntegerField()
    quantity = serializers.IntegerField()
    reserved_quantity = serializers.IntegerField(required=False, default=0)
    is_available_for_sale = serializers.BooleanField()


class ProductVariantAttributeInputSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    category_attribute = serializers.IntegerField()
    predefined_value = serializers.IntegerField(allow_null=True, required=False)
    custom_value = serializers.CharField(allow_blank=True, required=False)


class ProductVariantInputSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    sku = serializers.CharField(allow_blank=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    show_this = serializers.BooleanField()
    has_custom_name = serializers.BooleanField(required=False, default=False)
    custom_name = serializers.CharField(allow_blank=True, required=False)
    has_custom_description = serializers.BooleanField(required=False, default=False)
    custom_description = serializers.CharField(allow_blank=True, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    attributes = ProductVariantAttributeInputSerializer(many=True)
    stocks = ProductStockInputSerializer(many=True)


class ProductCreateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True, required=False)
    category = serializers.IntegerField()
    is_visible_on_marketplace = serializers.BooleanField()
    is_visible_on_own_site = serializers.BooleanField()
    is_active = serializers.BooleanField()
    images = ProductImageInputSerializer(many=True)
    variants = ProductVariantInputSerializer(many=True)

    def validate_category(self, value):
        if not Category.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Категория не найдена")
        return Category.objects.get(id=value)

    def validate(self, data):
        if not data.get("variants"):
            raise serializers.ValidationError("Необходимо указать хотя бы один вариант")
        return data
