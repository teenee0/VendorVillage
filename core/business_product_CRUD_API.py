from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from accounts.permissions import IsBusinessOwner
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.shortcuts import get_object_or_404
from marketplace.models import (
    Product,
    ProductVariant,
    ProductVariantAttribute,
    ProductStock,
    ProductImage,
    Category,
    AttributeValue,
    CategoryAttribute,
)
from core.models import Business, BusinessLocation
from .serializers import ProductCreateSerializer  # Используем тот же сериализатор

from accounts.JWT_AUTH import CookieJWTAuthentication


@api_view(["POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
@transaction.atomic
def create_product(request, business_slug):
    """
    Создание нового товара с вариантами, атрибутами, остатками и изображениями
    """
    try:
        # Проверяем, что бизнес существует и пользователь имеет к нему доступ
        business = get_object_or_404(Business, slug=business_slug)
        if not request.user.businesses.filter(id=business.id).exists():
            return Response(
                {"detail": "У вас нет прав для добавления товаров в этот бизнес"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Валидация данных
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Создаем продукт
        product = Product.objects.create(
            business=business,
            category=data["category"],
            name=data["name"],
            description=data.get("description", ""),
            on_the_main=data.get("on_the_main", False),
            is_active=data.get("is_active", True),
        )

        # Обрабатываем варианты товара
        for variant_data in data["variants"]:
            variant = create_product_variant(product, variant_data)

        # Обрабатываем изображения (если есть)
        for image_data in data.get("images", []):
            ProductImage.objects.create(
                product=product,
                image=image_data["image"],
                is_main=image_data.get("is_main", False),
                alt_text=image_data.get("alt_text"),
                display_order=image_data.get("display_order", 0),
            )

        return Response(
            {"id": product.id, "name": product.name, "message": "Товар успешно создан"},
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


def create_product_variant(product, variant_data):
    """Создание варианта товара с атрибутами и остатками"""
    variant = ProductVariant.objects.create(
        product=product,
        sku=variant_data.get("sku"),
        has_custom_name=variant_data.get("has_custom_name", False),
        custom_name=variant_data.get("custom_name"),
        has_custom_description=variant_data.get("has_custom_description", False),
        custom_description=variant_data.get("custom_description"),
        price=variant_data["price"],
        discount=variant_data.get("discount"),
        show_this=variant_data.get("show_this", False),
    )

    # Добавляем атрибуты
    for attr_data in variant_data["attributes"]:
        create_variant_attribute(variant, attr_data, product.category)

    # Добавляем остатки
    for stock_data in variant_data.get("stocks", []):
        ProductStock.objects.create(
            variant=variant,
            location=stock_data["location"],
            quantity=stock_data.get("quantity", 0),
            reserved_quantity=stock_data.get("reserved_quantity", 0),
            is_available_for_sale=stock_data.get("is_available_for_sale", True),
        )

    return variant


def create_variant_attribute(variant, attr_data, category):
    """Создание атрибута для варианта товара"""
    attribute_id = attr_data["category_attribute"]["attribute"]["id"]
    value = attr_data["value"]

    # Находим CategoryAttribute для категории товара
    category_attribute = category.category_attributes.filter(
        attribute_id=attribute_id
    ).first()

    if not category_attribute:
        raise ValueError(f"Атрибут с ID {attribute_id} не найден для категории")

    # Для атрибутов с предопределенными значениями
    if category_attribute.attribute.has_predefined_values:
        predefined_value = AttributeValue.objects.filter(
            attribute_id=attribute_id, value=value
        ).first()
        if not predefined_value:
            raise ValueError(
                f"Значение '{value}' не найдено для атрибута '{category_attribute.attribute.name}'"
            )

        ProductVariantAttribute.objects.create(
            variant=variant,
            category_attribute=category_attribute,
            predefined_value=predefined_value,
        )
    else:
        # Для атрибутов с произвольными значениями
        ProductVariantAttribute.objects.create(
            variant=variant, category_attribute=category_attribute, custom_value=value
        )


from django.db.models import Count


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def get_business_categories(request, business_slug):
    """
    Получение конечных категорий (без детей) с полными путями
    Формат: "Родитель - Родитель - Категория"
    """
    # Получаем только категории без детей
    categories = (
        Category.objects.annotate(children_count=Count("children"))
        .filter(is_active=True, children_count=0)
        .order_by("name")
    )

    data = []
    for category in categories:
        # Получаем полный путь категории
        ancestors = category.get_ancestors(include_self=True)
        path = " - ".join([ancestor.name for ancestor in ancestors])

        data.append(
            {
                "id": category.id,
                "name": category.name,
                "full_path": path,
                "parent_id": category.parent_id,
            }
        )

    return Response(data)


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def get_category_attributes(request, category_id):
    """
    Получение атрибутов для категории и всех её родительских категорий
    """
    try:
        # Получаем текущую категорию и всех её предков
        category = Category.objects.get(id=category_id)
        ancestor_categories = category.get_ancestors(include_self=True)

        # Получаем все атрибуты для этих категорий
        attributes = (
            CategoryAttribute.objects.filter(category__in=ancestor_categories)
            .select_related("attribute")
            .order_by(
                "category__level", "display_order"
            )  # Сортируем по уровню категории и порядку отображения
        )

        data = []
        seen_attributes = set()  # Для отслеживания уже добавленных атрибутов

        for attr in attributes:
            # Пропускаем дубликаты (на случай если distinct не сработал)
            if attr.attribute.id in seen_attributes:
                continue

            seen_attributes.add(attr.attribute.id)

            attr_data = {
                "id": attr.attribute.id,
                "name": attr.attribute.name,
                "required": attr.required,
                "has_predefined_values": attr.attribute.has_predefined_values,
                "values": [],
                "inherited_from": (
                    None if attr.category_id == category_id else attr.category.name
                ),
            }

            if attr.attribute.has_predefined_values:
                attr_data["values"] = list(
                    attr.attribute.values.values("id", "value", "color_code")
                )

            data.append(attr_data)

        return Response(data)

    except Category.DoesNotExist:
        return Response(
            {"detail": "Категория не найдена"}, status=status.HTTP_404_NOT_FOUND
        )


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def get_business_locations(request, business_slug):
    """
    Получение всех складов/локаций бизнеса
    """
    business = get_object_or_404(Business, slug=business_slug)
    locations = BusinessLocation.objects.filter(business=business).order_by("name")

    data = [
        {
            "id": loc.id,
            "name": loc.name,
            "address": loc.address,
            "location_type": loc.location_type.name,
        }
        for loc in locations
    ]

    return Response(data)
