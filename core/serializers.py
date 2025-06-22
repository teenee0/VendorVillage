from rest_framework import serializers
from .models import BusinessType
from marketplace.models import Product, ProductVariant, ProductImage

class BusinessTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessType
        fields = '__all__'  # Или укажите конкретные поля
class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'on_the_main', 'is_active']

class ProductVariantCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = [
            'sku', 'price', 'discount', 'show_this',
            'has_custom_name', 'custom_name', 'has_custom_description', 'custom_description'
        ]

class ProductImageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['image', 'is_main', 'alt_text', 'display_order']