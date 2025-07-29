import uuid
from datetime import datetime
from decimal import Decimal

from accounts.JWT_AUTH import CookieJWTAuthentication
from accounts.permissions import IsBusinessOwner
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from marketplace.models import (
    PaymentMethod,
    Product,
    ProductSale,
    ProductStock,
    ProductVariant,
    Receipt,
)
from marketplace.ProductsSet import ProductSet
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Business
from .product_sale_serializer import (
    EnhancedProductListSerializer,
    PaymentMethodSerializer,
    ProductVariantSerializer,
    ReceiptCreateSerializer,
    ReceiptDetailSerializer,
)
from .ProductCreateService import ProductService
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


import uuid
from decimal import Decimal

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

# … остальные импорты опущены …


@api_view(["POST"])
@transaction.atomic
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def create_receipt(request, business_slug):
    business = ProductService.get_business(request.user, business_slug)

    ser = ReceiptCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    v = ser.validated_data

    sales_data = v.pop("items")
    rcpt_disc_amount = Decimal(v.pop("discount_amount", 0))
    rcpt_disc_percent = Decimal(v.pop("discount_percent", 0))

    # ---------- создаём сам чек ----------
    receipt = Receipt.objects.create(
        number=f"CHK-{uuid.uuid4().hex[:8].upper()}",
        payment_method=v["payment_method"],
        customer=v.get("customer"),
        customer_name=v.get("customer_name", ""),
        customer_phone=v.get("customer_phone", ""),
        is_online=False,
        is_paid=True,
        total_amount=0,  # обновим ниже
        discount_amount=rcpt_disc_amount,
        discount_percent=rcpt_disc_percent,
    )

    total_amount = Decimal("0")
    product_sales = []
    affected_products = set()  # ← будем хранить Product-ы

    # ---------- валидация + подготовка ----------
    for item in sales_data:
        var: ProductVariant = item["variant"]
        loc: BusinessLocation = item["location"]
        qty = item["quantity"]
        disc_amount = Decimal(str(item.get("discount_amount", 0)))
        disc_percent = Decimal(str(item.get("discount_percent", 0)))

        # проверки принадлежности и наличия
        if loc.business != business:
            raise ValidationError(f"Локация '{loc}' не принадлежит бизнесу.")

        if var.product.business != business:
            raise ValidationError(f"Вариант '{var}' не принадлежит бизнесу.")

        stock = ProductStock.objects.select_for_update().get(variant=var, location=loc)
        if stock.available_quantity < qty:
            raise ValidationError(
                f"Недостаточно '{var}' на '{loc}'. Доступно: {stock.available_quantity}"
            )

        price = Decimal(str(var.current_price))
        unit_disc = price * disc_percent / 100 + disc_amount
        final_price = max(price - unit_disc, 0)
        line_total = final_price * qty

        product_sales.append(
            ProductSale(
                receipt=receipt,
                variant=var,
                location=loc,
                quantity=qty,
                price_per_unit=price,
                discount_percent=disc_percent,
                discount_amount=disc_amount,
                total_price=line_total,
                is_paid=True,
            )
        )
        total_amount += line_total
        affected_products.add(var.product)  # запоминаем товар

    # ---------- массовое создание продаж ----------
    ProductSale.objects.bulk_create(product_sales)

    # ---------- перерасчёт итогов чека ----------
    if rcpt_disc_percent:
        total_amount -= total_amount * rcpt_disc_percent / 100
    total_amount -= rcpt_disc_amount
    receipt.total_amount = max(total_amount, 0)
    receipt._history_user = request.user
    receipt.save(update_fields=["total_amount"])
    generate_receipt_pdf(receipt.id, save=True)
    receipt.refresh_from_db()

    # ---------- ручной update_is_active ----------
    for product in affected_products:
        product.update_is_active()

    return Response(
        ReceiptDetailSerializer(receipt).data, status=status.HTTP_201_CREATED
    )
