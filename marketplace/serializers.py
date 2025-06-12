from rest_framework import serializers
from .models import (
    Category,
    Product,
    ProductVariant,
    ProductImage,  # Новая модель вместо ProductVariantImage
    ProductVariantAttribute,
    AttributeValue,
    Attribute,
    CategoryAttribute
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'big_image', 
            'small_image', 'page_identificator', 'ordering',
            'is_active'
        ]


class CategoryBreadcrumbsSerializer(serializers.ModelSerializer):
    ancestors = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'ancestors']

    def get_ancestors(self, obj):
        ancestors = obj.get_ancestors(include_self=False)
        return CategorySerializer(ancestors, many=True, fields=['id', 'name']).data


class AttributeValueSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    
    class Meta:
        model = AttributeValue
        fields = ['id', 'value', 'attribute_name', 'color_code']


class ProductVariantAttributeSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source='category_attribute.attribute.name', read_only=True)
    display_value = serializers.CharField(read_only=True)
    attribute_id = serializers.IntegerField(source='category_attribute.attribute.id', read_only=True)
    
    class Meta:
        model = ProductVariantAttribute
        fields = ['id', 'attribute_name', 'display_value', 'attribute_id']


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'is_main', 'alt_text', 'created_at']


class ProductVariantSerializer(serializers.ModelSerializer):
    attributes = ProductVariantAttributeSerializer(many=True, read_only=True)
    current_price = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()  # Исправлено название
    is_in_stock = serializers.BooleanField(read_only=True)
    display_name = serializers.SerializerMethodField()
    display_description = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'sku', 'price', 'discount', 'discount_amount', 'stock_quantity',
            'attributes', 'current_price', 
            'is_in_stock', 'show_this', 'has_custom_name', 
            'custom_name', 'display_name', 'has_custom_description', 
            'custom_description', 'display_description'
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
            return float(obj.price) * (1 - float(obj.discount)/100)
        return float(obj.price)

    def get_discount_amount(self, obj):
        """Возвращает сумму скидки в рублях"""
        if obj.discount and obj.price > 0:
            # return float(obj.discount)  # Для абсолютной скидки
            # Или для процентной скидки:
            return float(obj.price) * float(obj.discount)/100
        return 0

class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    business_name = serializers.CharField(source='business.name', read_only=True)
    default_variant = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()
    max_price = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', "is_active",
            'category', 'category_name', 'business', 'business_name',
            'default_variant', 'min_price', 'max_price', 'created_at',
            'main_image'
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
    category_name = serializers.CharField(source='category.name', read_only=True)
    business_name = serializers.CharField(source='business.name', read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    available_attributes = serializers.SerializerMethodField()
    default_variant = serializers.SerializerMethodField()
    price_range = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'on_the_main', 'is_active',
            'category', 'category_name', 'business', 'business_name',
            'variants', 'available_attributes', 'default_variant',
            'price_range', 'created_at', 'updated_at', 'images'
        ]
    
    def get_available_attributes(self, obj):
        return obj.available_attributes
    
    def get_default_variant(self, obj):
        variant = obj.default_variant
        if variant:
            return ProductVariantSerializer(variant).data
        return None
    
    def get_price_range(self, obj):
        min_price, max_price = obj.price_range
        if min_price is None:
            return None
        return {
            'min_price': min_price,
            'max_price': max_price,
            'is_range': min_price != max_price
        }

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'category', 
            'on_the_main', 'is_active', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'created_at': {'read_only': True},
            'updated_at': {'read_only': True},
        } 

    def validate_category(self, value):
        """Проверка, что категория активна"""
        if value and not value.is_active:
            raise serializers.ValidationError("Нельзя выбрать неактивную категорию")
        return value

    def create(self, validated_data):
        """Создание товара с привязкой к бизнесу"""
        # Бизнес берется из контекста (передается в представлении)
        business = self.context.get('business')
        if not business:
            raise serializers.ValidationError("Бизнес не указан")
        
        validated_data['business'] = business
        return super().create(validated_data)

    def to_representation(self, instance):
        """Преобразование в представление с дополнительными полями"""
        representation = super().to_representation(instance)
        
        # Добавляем дополнительные поля для чтения
        representation['category_name'] = instance.category.name if instance.category else None
        representation['business_name'] = instance.business.name if instance.business else None
        
        # Добавляем информацию о главном изображении
        main_image = instance.main_image
        if main_image:
            representation['main_image'] = ProductImageSerializer(main_image).data
        else:
            representation['main_image'] = None
            
        return representation