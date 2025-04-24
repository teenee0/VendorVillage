from rest_framework import serializers
from .models import Category
from .models import Product, ProductImage
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'  # Добавьте нужные поля

class CategoryBreadcrumbsSerializer(serializers.ModelSerializer):
    ancestors = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'ancestors']

    def get_ancestors(self, obj):
        ancestors = obj.get_ancestors(include_self=False)
        return CategoryBreadcrumbsSerializer(ancestors, many=True).data

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image']  # можно добавить 'created_at', если нужно

class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'discount',
            'stock_quantity', 'on_the_main', 'images'
        ]
