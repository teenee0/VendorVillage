from rest_framework import serializers
from .product_sale_serializer import ProductVariantSerializer, ProductImageSerializer
from marketplace.models import ProductSale, Receipt


class TotalsSerializer(serializers.Serializer):
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    sales_count = serializers.IntegerField()
    orders = serializers.IntegerField()


class ChartPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    sales_qty = serializers.IntegerField()


class TransactionSerializer(serializers.Serializer):
    number = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    created_at = serializers.DateTimeField()
    is_refund = serializers.BooleanField()


class VariantInReceiptSerializer(ProductVariantSerializer):
    """
    Данные варианта в составе чека + информация о самой продаже.
    """

    # ---------- «базовые» поля из связанного продукта -----------------
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_images = ProductImageSerializer(
        source="product.images", many=True, read_only=True
    )

    # ---------- агрегаты по продаже ----------------------------------
    sold_quantity = serializers.SerializerMethodField()
    sold_total_price = serializers.SerializerMethodField()
    sale_discount_percent = serializers.SerializerMethodField()
    sale_discount_amount = serializers.SerializerMethodField()

    class Meta(ProductVariantSerializer.Meta):
        fields = ProductVariantSerializer.Meta.fields + [
            "product_id",
            "product_name",
            "product_images",
            "sold_quantity",
            "sold_total_price",
            "sale_discount_percent",
            "sale_discount_amount",
        ]

    # -----------------------------------------------------------------
    # вспомогательный метод – достаём ProductSale без N + 1
    def _get_sale_obj(self, obj):
        sales_map = self.context.get("sales_map")  # {variant_id: ProductSale}
        if sales_map:
            return sales_map.get(obj.id)

        receipt = self.context.get("receipt")
        if receipt is None:
            return None
        return (
            ProductSale.objects.filter(receipt=receipt, variant=obj)
            .only(
                "quantity",
                "total_price",
                "discount_percent",
                "discount_amount",
            )
            .first()
        )

    # ---------------- SerializerMethodField-ы ------------------------
    def get_sold_quantity(self, obj):
        sale = self._get_sale_obj(obj)
        return sale.quantity if sale else 0

    def get_sold_total_price(self, obj):
        sale = self._get_sale_obj(obj)
        return float(sale.total_price) if sale else 0.0

    def get_sale_discount_percent(self, obj):
        sale = self._get_sale_obj(obj)
        return float(sale.discount_percent) if sale else 0.0

    def get_sale_discount_amount(self, obj):
        sale = self._get_sale_obj(obj)
        return float(sale.discount_amount) if sale else 0.0


class SaleLineSerializer(serializers.ModelSerializer):
    """
    Одна позиция продажи из таблицы ProductSale
    + вложенный вариант с картинками/скидками.
    """
    variant = VariantInReceiptSerializer(read_only=True)

    class Meta:
        model  = ProductSale
        fields = [
            "id",
            "variant",           # ← всё, что мы собрали выше
            "location_id",
            "quantity",
            "price_per_unit",
            "total_price",
            "discount_percent",
            "discount_amount",
        ]
        read_only_fields = fields


class ReceiptDetailSerializer(serializers.ModelSerializer):
    """
    Полная информация о чеке: шапка + позиции.
    """
    sales           = SaleLineSerializer(many=True, read_only=True)
    payment_method  = serializers.CharField(source="payment_method.name", read_only=True)
    customer_name   = serializers.CharField(read_only=True)
    customer_phone  = serializers.CharField(read_only=True)

    class Meta:
        model  = Receipt
        fields = [
            "id",
            "number",
            "created_at",
            "total_amount",
            "payment_method",
            "is_paid",
            "customer_name",
            "customer_phone",
            "discount_percent",
            "discount_amount",
            "receipt_preview_image",
            "receipt_pdf_file",
            "sales",                # список позиций чека
        ]
        read_only_fields = fields


# --- (опционально) компактный список чеков ---------------------------
class ReceiptListSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Receipt
        fields = [
            "id",
            "number",
            "created_at",
            "total_amount",
            "is_paid",
            "payment_method_id",
        ]
        read_only_fields = fields
