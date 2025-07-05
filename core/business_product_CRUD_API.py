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
from .serializers import ProductCreateSerializer
from .product_edit_serializers import ProductDetailSerializer, ProductCreateUpdateSerializer
from .exceptions import ProductError
from .ProductCreateService import ProductService
from django.db.models import Count
from accounts.JWT_AUTH import CookieJWTAuthentication


def parse_product_formdata(request):
    """
    Универсальный парсер JSON данных + файлов для формы продукта:
    - поддерживает existing_images и новые images
    - поддерживает variants с id
    """
    data = {
        "name": request.data.get("name"),
        "description": request.data.get("description"),
        "category": int(request.data.get("category")),
        "is_active": request.data.get("is_active") == "true",
        "is_visible_on_marketplace": request.data.get("is_visible_on_marketplace") == "true",
        "is_visible_on_own_site": request.data.get("is_visible_on_own_site") == "true",
        "images": [],
        "variants": [],
    }

    # === Existing Images ===
    existing_images = []
    ei = 0
    while f"existing_images[{ei}][id]" in request.data:
        existing_images.append(
            {
                "id": int(request.data.get(f"existing_images[{ei}][id]")),
                "is_main": request.data.get(f"existing_images[{ei}][is_main]")
                == "true",
                "display_order": int(
                    request.data.get(f"existing_images[{ei}][display_order]", "0")
                ),
            }
        )
        ei += 1

    # === New Images ===
    new_images = []
    for key in request.FILES:
        if key.startswith("images[") and key.endswith("][image]"):
            idx = key.split("[")[1].split("]")[0]
            new_images.append(
                {
                    "image": request.FILES[key],
                    "is_main": request.data.get(f"images[{idx}][is_main]", "false")
                    == "true",
                    "display_order": int(
                        request.data.get(f"images[{idx}][display_order]", "0")
                    ),
                }
            )

    # Объединяем все фото
    data["images"] = existing_images + new_images

    # === Variants ===
    vi = 0
    while f"variants[{vi}][sku]" in request.data:
        variant = {
            "sku": request.data.get(f"variants[{vi}][sku]"),
            "price": request.data.get(f"variants[{vi}][price]"),
            "discount": request.data.get(f"variants[{vi}][discount]"),
            "show_this": request.data.get(f"variants[{vi}][show_this]") == "true",
            "description": request.data.get(f"variants[{vi}][description]", ""),
            "attributes": [],
            "stocks": [],
        }
        # ID варианта если есть
        if f"variants[{vi}][id]" in request.data:
            variant["id"] = int(request.data.get(f"variants[{vi}][id]"))

        # Attributes
        ai = 0
        while f"variants[{vi}][attributes][{ai}][category_attribute]" in request.data:
            attr = {
                "category_attribute": int(
                    request.data.get(
                        f"variants[{vi}][attributes][{ai}][category_attribute]"
                    )
                ),
                "predefined_value": (
                    int(
                        request.data.get(
                            f"variants[{vi}][attributes][{ai}][predefined_value]"
                        )
                    )
                    if request.data.get(
                        f"variants[{vi}][attributes][{ai}][predefined_value]", ""
                    ).strip()
                    != ""
                    else None
                ),
                "custom_value": request.data.get(
                    f"variants[{vi}][attributes][{ai}][custom_value]", ""
                ),
            }
            if f"variants[{vi}][attributes][{ai}][id]" in request.data:
                attr["id"] = int(
                    request.data.get(f"variants[{vi}][attributes][{ai}][id]")
                )
            variant["attributes"].append(attr)
            ai += 1

        # Stocks
        si = 0
        while f"variants[{vi}][stocks][{si}][location_id]" in request.data:
            stock = {
                "location": int(
                    request.data.get(f"variants[{vi}][stocks][{si}][location_id]")
                ),
                "quantity": int(
                    request.data.get(f"variants[{vi}][stocks][{si}][quantity]")
                ),
                "reserved_quantity": int(
                    request.data.get(
                        f"variants[{vi}][stocks][{si}][reserved_quantity]", "0"
                    )
                ),
                "is_available_for_sale": request.data.get(
                    f"variants[{vi}][stocks][{si}][is_available_for_sale]", "true"
                )
                == "true",
            }
            if f"variants[{vi}][stocks][{si}][id]" in request.data:
                stock["id"] = int(request.data.get(f"variants[{vi}][stocks][{si}][id]"))
            variant["stocks"].append(stock)
            si += 1

        data["variants"].append(variant)
        vi += 1

    return data


@api_view(["POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def create_product(request, business_slug):
    print("RAW:", request.data)
    data = parse_product_formdata(request)
    print("PARSED:", data)

    serializer = ProductCreateSerializer(data=data, context={"request": request})
    serializer.is_valid(raise_exception=True)

    try:
        product = ProductService.create_product(
            request.user, business_slug, serializer.validated_data
        )
        return Response(
            {"message": "Товар успешно создан", "product_id": product.id},
            status=status.HTTP_201_CREATED,
        )
    except ProductError as e:
        return Response(
            {"detail": str(e), "errors": e.errors}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def edit_product(request, business_slug, product_id):
    print("RAW:", request.data)
    parsed_data = parse_product_formdata(request)
    print("PARSED:", parsed_data)

    serializer = ProductCreateUpdateSerializer(data=parsed_data, context={"request": request})
    serializer.is_valid(raise_exception=True)

    try:
        product = ProductService.update_product(
            request.user, business_slug, product_id, serializer.validated_data
        )
        return Response(
            {"message": "Товар успешно изменён", "product_id": product.id},
            status=status.HTTP_200_OK,
        )
    except ProductError as e:
        return Response(
            {"detail": str(e), "errors": e.errors}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["DELETE"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def delete_product(request, business_slug, product_id):
    try:
        ProductService.delete_product(request.user, business_slug, product_id)
        return Response({"message": "Товар успешно удалён"}, status=status.HTTP_200_OK)
    except Product.DoesNotExist:
        return Response({"detail": "Товар не найден"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


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
            )
        )

        data = []
        seen_attributes = set()

        for attr in attributes:
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


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def get_product(request, business_slug, product_id):
    business = ProductService.get_business(request.user, business_slug)

    try:
        product = (
            Product.objects.prefetch_related(
                "variants__attributes", "variants__stocks", "images"
            )
            .select_related("category")
            .get(id=product_id, business=business)
        )
    except Product.DoesNotExist:
        return Response({"detail": "Товар не найден"}, status=status.HTTP_404_NOT_FOUND)

    serializer = ProductDetailSerializer(product, context={"request": request})

    return Response(serializer.data, status=status.HTTP_200_OK)
