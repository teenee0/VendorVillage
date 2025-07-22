from rest_framework import serializers
from marketplace.models import (
    ProductStock,
    ProductSale,
    Receipt,
    ProductVariant,
    BusinessLocation,
    ProductVariantAttribute,
    Product,
    ProductImage,
    ProductDefect,
    PaymentMethod,
)
from .models import User


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ['id', 'code', 'name', 'is_active']

class ProductSaleSerializer(serializers.Serializer):
    variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all())
    location = serializers.PrimaryKeyRelatedField(queryset=BusinessLocation.objects.all())
    quantity = serializers.IntegerField(min_value=1)
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, default=0)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)

    def validate(self, attrs):
        variant = attrs['variant']
        location = attrs['location']
        quantity = attrs['quantity']

        stock = variant.stocks.filter(location=location).first()
        if not stock:
            raise serializers.ValidationError(f"Нет остатков для товара {variant} в указанной локации.")
        if stock.available_quantity < quantity:
            raise serializers.ValidationError(f"Недостаточно товара '{variant}' в '{location}'. Доступно: {stock.available_quantity}.")
        return attrs


class ReceiptCreateSerializer(serializers.Serializer):
    payment_method = serializers.SlugRelatedField(slug_field='code', queryset=PaymentMethod.objects.filter(is_active=True))
    customer = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    customer_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    customer_phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    is_online = serializers.BooleanField(default=False)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, default=0)
    items = ProductSaleSerializer(many=True)




class ReceiptDetailSerializer(serializers.ModelSerializer):
    sales = serializers.SerializerMethodField()
    payment_method = serializers.CharField(source='payment_method.name')

    class Meta:
        model = Receipt
        fields = [
            'id', 'number', 'created_at', 'total_amount', 'payment_method',
            'customer_name', 'customer_phone', 'is_online', 'sales', 'receipt_pdf_file', 'receipt_preview_image'
        ]

    def get_sales(self, obj):
        return [
            {
                "variant": sale.variant.name,
                "location": sale.location.name,
                "quantity": sale.quantity,
                "price_per_unit": sale.price_per_unit,
                "total_price": sale.total_price,
            } for sale in obj.sales.all()
        ]

#Вывод продуктов
class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_main", "alt_text", "created_at"]


class ProductDefectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductDefect
        fields = ['id', 'quantity', 'reason', 'created_at']


class ProductStockSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    defects = ProductDefectSerializer(many=True, read_only=True)
    available_quantity = serializers.SerializerMethodField()

    class Meta:
        model = ProductStock
        fields = [
            "location",
            "location_name",
            "quantity",
            "reserved_quantity",
            "defects",
            "available_quantity",
        ]

    def get_available_quantity(self, obj):
        return obj.available_quantity


# 2. Атрибуты варианта (цвет, размер и т.д.)
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


# 3. Вариант товара (SKU, цена, атрибуты, остатки)
class ProductVariantSerializer(serializers.ModelSerializer):
    attributes = ProductVariantAttributeSerializer(many=True, read_only=True)
    stocks = ProductStockSerializer(many=True, read_only=True)

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

# 5. Сериализатор списка товаров (расширенный)
class EnhancedProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    business_name = serializers.CharField(source="business.name", read_only=True)
    images = ProductImageSerializer(many=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "category",
            "category_name",
            "business_name",
            "images",
            "variants",
            "created_at",
        ]
