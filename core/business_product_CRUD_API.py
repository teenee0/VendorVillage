from contextlib import nullcontext

from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from accounts.permissions import IsBusinessOwner
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
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
from .exceptions import ProductError
from .ProductCreateService import ProductService

from accounts.JWT_AUTH import CookieJWTAuthentication


@api_view(["POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def create_product(request, business_slug):
    print("RAW DATA:", request.data)

    # === Ручной парсер ===
    data = {}
    data['name'] = request.data.get('name')
    data['description'] = request.data.get('description')
    data['category'] = int(request.data.get('category'))
    data['is_active'] = request.data.get('is_active') == 'true'
    data['on_the_main'] = request.data.get('on_the_main') == 'true'

    # Images
    images = []
    i = 0
    while f'images[{i}][image]' in request.FILES:
        images.append({
            'image': request.FILES[f'images[{i}][image]'],
            'is_main': request.data.get(f'images[{i}][is_main]') == 'true',
            'display_order': int(request.data.get(f'images[{i}][display_order]', '0')),
        })
        i += 1
    data['images'] = images

    # Variants
    variants = []
    vi = 0
    while f'variants[{vi}][sku]' in request.data:
        variant = {
            'sku': request.data.get(f'variants[{vi}][sku]'),
            'price': request.data.get(f'variants[{vi}][price]'),
            'discount': request.data.get(f'variants[{vi}][discount]'),
            'show_this': request.data.get(f'variants[{vi}][show_this]') == 'true',
            'description': request.data.get(f'variants[{vi}][description]', ''),
            'attributes': [],
            'stocks': [],
        }

        # Attributes
        ai = 0
        while f'variants[{vi}][attributes][{ai}][category_attribute]' in request.data:
            predefined_value_raw = request.data.get(f'variants[{vi}][attributes][{ai}][predefined_value]', '')
            if predefined_value_raw.strip() != '':
                predefined_value = int(predefined_value_raw)
            else:
                predefined_value = None

            attr = {
                'category_attribute': int(request.data.get(f'variants[{vi}][attributes][{ai}][category_attribute]')),
                'predefined_value': predefined_value,
                'custom_value': request.data.get(f'variants[{vi}][attributes][{ai}][custom_value]', ''),
            }
            variant['attributes'].append(attr)
            ai += 1

        # Stocks
        si = 0
        while f'variants[{vi}][stocks][{si}][location_id]' in request.data:
            stock = {
                'location': int(request.data.get(f'variants[{vi}][stocks][{si}][location_id]')),
                'quantity': int(request.data.get(f'variants[{vi}][stocks][{si}][quantity]')),
                'reserved_quantity': int(request.data.get(f'variants[{vi}][stocks][{si}][reserved_quantity]', '0')),
                'is_available_for_sale': request.data.get(f'variants[{vi}][stocks][{si}][is_available_for_sale]', 'true') == 'true',
            }
            variant['stocks'].append(stock)
            si += 1

        variants.append(variant)
        vi += 1

    data['variants'] = variants

    print("PARSED DATA:", data)

    # === Теперь сериализатор ===
    serializer = ProductCreateSerializer(data=data, context={"request": request})
    serializer.is_valid(raise_exception=True)

    try:
        product = ProductService.create_product(
            request.user,
            business_slug,
            serializer.validated_data
        )
        return Response({
            "message": "Товар успешно создан",
            "product_id": product.id
        }, status=status.HTTP_201_CREATED)
    except ProductError as e:
        return Response({
            "detail": str(e),
            "errors": e.errors
        }, status=status.HTTP_400_BAD_REQUEST)



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
