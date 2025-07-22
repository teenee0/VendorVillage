from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework import status

from .product_sale_serializer import ReceiptCreateSerializer, ReceiptDetailSerializer, PaymentMethodSerializer
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from datetime import datetime
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsBusinessOwner
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from marketplace.models import (
    Product,
    ProductVariant,
    Receipt,
    PaymentMethod,
    ProductSale,
    ProductStock
)
from .models import Business
from accounts.JWT_AUTH import CookieJWTAuthentication
from .product_sale_serializer import (
    EnhancedProductListSerializer,
    ProductVariantSerializer,
)
from marketplace.ProductsSet import ProductSet
import uuid
from .ProductCreateService import ProductService
from django.core.exceptions import ValidationError
from decimal import Decimal
from .utils.generate_receipt_pdf import generate_receipt_pdf


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def get_active_payment_methods(request):
    """Возвращает список всех активных методов оплаты"""
    methods = PaymentMethod.objects.filter(is_active=True)
    serializer = PaymentMethodSerializer(methods, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def sales_products_api(request, business_slug):
    """Возвращает список товаров для страницы продаж. Поддерживает фильтрацию по штрихкоду."""
    business = get_object_or_404(Business, slug=business_slug)

    category_pk = request.GET.get("category")
    if category_pk:
        products = ProductSet.get_products_by_category(category_pk)
        products = products.filter(business=business)
    else:
        products = Product.objects.filter(business=business).order_by("-created_at")

    # Фильтрация товаров
    filtered_products, applied_filters = ProductSet.filter_products(
        products,
        request,
        search=True,
        price=True,
        barcode=True,
    )

    # Проверка на наличие штрихкода
    barcode = request.GET.get("search")
    matched_variant = None
    if barcode and barcode.isdigit():  # или используй re.match(r'^\d{8,14}$', barcode)
        matched_variant = (
            ProductVariant.objects.select_related("product")
            .filter(barcode=barcode, product__in=filtered_products)
            .first()
        )

    # Пагинация
    page_obj, pagination = ProductSet.pagination_for_products(
        filtered_products, request
    )

    # Сериализация
    serialized_products = EnhancedProductListSerializer(
        page_obj, many=True, context={"request": request}
    ).data

    # Если найден вариант — подменим variants
    if matched_variant:
        for product_data in serialized_products:
            if product_data["id"] == matched_variant.product.id:
                filtered_variant_data = ProductVariantSerializer(
                    matched_variant, context={"request": request}
                ).data
                product_data["variants"] = [filtered_variant_data]

    return Response(
        {
            "products": serialized_products,
            "pagination": pagination,
            "applied_filters": applied_filters,
        }
    )



@api_view(["POST"])
@transaction.atomic
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def create_receipt(request, business_slug):
    print(request.data)
    business = ProductService.get_business(request.user, business_slug)

    serializer = ReceiptCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    validated_data = serializer.validated_data
    sales_data = validated_data.pop('items')
    receipt_discount_amount = validated_data.pop("discount_amount", 0)
    receipt_discount_percent = validated_data.pop("discount_percent", 0)

    total_amount = 0
    product_sales = []

    # Генерация номера чека
    number = f"CHK-{uuid.uuid4().hex[:8].upper()}"

    customer = validated_data.get('customer', None)

    receipt = Receipt.objects.create(
        number=number,
        payment_method=validated_data['payment_method'],
        customer=customer,
        customer_name=validated_data.get('customer_name', ''),
        customer_phone=validated_data.get('customer_phone', ''),
        is_online=False,
        is_paid=True,
        total_amount=0  # временно 0, позже обновим
    )

    for item in sales_data:
        variant = item['variant']
        location = item['location']
        quantity = item['quantity']
        discount_amount = item.get("discount_amount", 0)
        discount_percent = item.get("discount_percent", 0)

        price = Decimal(str(variant.current_price))
        discount_percent = Decimal(str(discount_percent))
        discount_amount = Decimal(str(discount_amount))

        unit_discount = price * discount_percent / Decimal('100') + discount_amount
        unit_price_final = max(price - unit_discount, Decimal('0'))
        total_price = unit_price_final * quantity

        # 🔒 Проверка: принадлежит ли локация бизнесу
        if location.business != business:
            raise ValidationError(f"Локация '{location}' не принадлежит бизнесу '{business.name}'.")

        # 🔒 Проверка: принадлежит ли вариант бизнесу
        if variant.product.business != business:
            raise ValidationError(f"Вариант товара '{variant}' не принадлежит бизнесу '{business.name}'.")

        # 🔒 Проверка: есть ли вариант на нужной локации
        try:
            stock = ProductStock.objects.select_for_update().get(variant=variant, location=location)
        except ProductStock.DoesNotExist:
            raise ValidationError(f"Вариант '{variant}' не найден на складе '{location.name}'.")

        # 🔒 Проверка доступности по количеству
        if stock.available_quantity < quantity:
            raise ValidationError(
                f"Недостаточно товара '{variant}' в '{location.name}'. Доступно: {stock.available_quantity}"
            )

        product_sale = ProductSale(
            receipt=receipt,
            variant=variant,
            location=location,
            quantity=quantity,
            price_per_unit=price,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            total_price=total_price,
            is_paid=True
        )
        product_sales.append(product_sale)
        total_amount += total_price

    ProductSale.objects.bulk_create(product_sales)

    if receipt_discount_percent:
        total_amount -= total_amount * receipt_discount_percent / 100
    total_amount -= receipt_discount_amount
    receipt.total_amount = max(total_amount, 0)
    receipt.save(update_fields=["total_amount"])

    generate_receipt_pdf(receipt.id, save=True)

    receipt.refresh_from_db()

    return Response(ReceiptDetailSerializer(receipt).data, status=status.HTTP_201_CREATED)
