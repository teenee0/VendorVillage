from contextlib import nullcontext

from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from django.core.exceptions import ValidationError
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
    ProductDefect
)
from core.models import Business, BusinessLocation
from .serializers import ProductCreateSerializer
from .product_edit_serializers import (
    ProductDetailSerializer,
    ProductCreateUpdateSerializer,
)
from .exceptions import ProductError
from .ProductCreateService import ProductService
from django.db.models import Count
from accounts.JWT_AUTH import CookieJWTAuthentication
import json

def parse_product_formdata(request):
    import json
    from django.core.exceptions import ValidationError

    parsed_data = {}

    # --- Попытка JSON парсинга (если есть "data")
    raw_json = request.data.get("data")
    if raw_json:
        try:
            parsed_data = json.loads(raw_json)
        except json.JSONDecodeError:
            raise ValidationError("Ошибка в JSON-структуре")

    else:
        # иначе — ручной парсинг формы (вариант 2)
        parsed_data = {
            "name": request.data.get("name"),
            "description": request.data.get("description"),
            "category": int(request.data.get("category")),
            "is_active": request.data.get("is_active") == "true",
            "is_visible_on_marketplace": request.data.get("is_visible_on_marketplace") == "true",
            "is_visible_on_own_site": request.data.get("is_visible_on_own_site") == "true",
            "images": [],
            "variants": [],
        }

    # --- Обработка variants (универсально)
    variants = []
    if "variants" in parsed_data:
        # JSON-способ
        for variant in parsed_data["variants"]:
            if "id" in variant:
                variant["id"] = int(variant["id"])
            for attr in variant["attributes"]:
                if "id" in attr and attr["id"] is not None:
                    attr["id"] = int(attr["id"])
                attr["category_attribute"] = int(attr["category_attribute"])
                if attr["predefined_value"] not in ("", None):
                    attr["predefined_value"] = int(attr["predefined_value"])
                else:
                    attr["predefined_value"] = None
            for stock in variant["stocks"]:
                if "id" in stock:
                    stock["id"] = int(stock["id"])
                if "location_id" in stock:
                    stock["location"] = int(stock.pop("location_id"))
                stock["quantity"] = int(stock["quantity"])
                stock["reserved_quantity"] = int(stock["reserved_quantity"])
                stock["is_available_for_sale"] = bool(stock["is_available_for_sale"])
        variants = parsed_data["variants"]

    else:
        # FORM способ
        vi = 0
        while f"variants[{vi}][price]" in request.data:
            variant = {
                "price": request.data.get(f"variants[{vi}][price]"),
                "discount": request.data.get(f"variants[{vi}][discount]"),
                "show_this": request.data.get(f"variants[{vi}][show_this]") == "true",
                "description": request.data.get(f"variants[{vi}][description]", ""),
                "attributes": [],
                "stocks": [],
            }
            if f"variants[{vi}][id]" in request.data:
                variant["id"] = int(request.data.get(f"variants[{vi}][id]"))

            # Атрибуты
            ai = 0
            while f"variants[{vi}][attributes][{ai}][category_attribute]" in request.data:
                attr = {
                    "category_attribute": int(request.data.get(f"variants[{vi}][attributes][{ai}][category_attribute]")),
                    "custom_value": request.data.get(f"variants[{vi}][attributes][{ai}][custom_value]", "")
                }
                pv = request.data.get(f"variants[{vi}][attributes][{ai}][predefined_value]", "")
                attr["predefined_value"] = int(pv) if pv.strip() else None
                if f"variants[{vi}][attributes][{ai}][id]" in request.data:
                    attr["id"] = int(request.data.get(f"variants[{vi}][attributes][{ai}][id]"))
                variant["attributes"].append(attr)
                ai += 1

            # Склады
            si = 0
            while f"variants[{vi}][stocks][{si}][location_id]" in request.data:
                stock = {
                    "location": int(request.data.get(f"variants[{vi}][stocks][{si}][location_id]")),
                    "quantity": int(request.data.get(f"variants[{vi}][stocks][{si}][quantity]")),
                    "reserved_quantity": int(request.data.get(f"variants[{vi}][stocks][{si}][reserved_quantity]", 0)),
                    "is_available_for_sale": request.data.get(f"variants[{vi}][stocks][{si}][is_available_for_sale]", "true") == "true"
                }
                if f"variants[{vi}][stocks][{si}][id]" in request.data:
                    stock["id"] = int(request.data.get(f"variants[{vi}][stocks][{si}][id]"))
                variant["stocks"].append(stock)
                si += 1

            variants.append(variant)
            vi += 1

    parsed_data["variants"] = variants

    # --- Обработка изображений (новых и существующих)
    images = []

    # existing_images
    ei = 0
    while f"existing_images[{ei}][id]" in request.data:
        images.append({
            "id": int(request.data.get(f"existing_images[{ei}][id]")),
            "is_main": request.data.get(f"existing_images[{ei}][is_main]", "false") == "true",
            "display_order": int(request.data.get(f"existing_images[{ei}][display_order]", "0"))
        })
        ei += 1

    # new images
    for key in request.FILES:
        if key.startswith("images[") and key.endswith("][image]"):
            idx = key.split("[")[1].split("]")[0]
            images.append({
                "image": request.FILES[key],
                "is_main": request.data.get(f"images[{idx}][is_main]", "false") == "true",
                "display_order": int(request.data.get(f"images[{idx}][display_order]", "0"))
            })

    parsed_data["images"] = images
    return parsed_data






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

    serializer = ProductCreateUpdateSerializer(
        data=parsed_data, context={"request": request}
    )
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
            .order_by("category__level", "display_order")
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


@api_view(["PATCH"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def toggle_status_product(request, business_slug, product_id):
    """
    Активация или деактивация товара.
    Ожидает JSON: { "is_active": true/false }
    """
    business = ProductService.get_business(request.user, business_slug)
    product = get_object_or_404(Product, id=product_id, business=business)

    is_active = request.data.get("is_active")
    if is_active is None:
        return Response(
            {"error": "Поле 'is_active' обязательно"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Проверка при активации: есть ли доступные варианты
    if is_active:
        has_available_variant = any(
            variant.available_quantity > 0 and variant.show_this
            for variant in product.variants.all()
        )
        if not has_available_variant:
            return Response(
                {"error": "Нельзя активировать товар без доступных вариантов."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    product.is_active = bool(is_active)
    product.save()

    return Response(
        {"id": product.id, "name": product.name, "is_active": product.is_active}
    )



@api_view(["POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def create_stock_defect(request, business_slug, stock_id):
    """Добавление брака по складу"""

    try:
        quantity = int(request.data.get("quantity", 0))
    except (TypeError, ValueError):
        quantity = 0

    reason = request.data.get("reason", "")

    if quantity <= 0:
        return Response(
            {"detail": "Количество должно быть больше нуля"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    business = ProductService.get_business(request.user, business_slug)
    stock = get_object_or_404(
        ProductStock,
        id=stock_id,
        variant__product__business=business,
    )

    ProductDefect.objects.create(stock=stock, quantity=quantity, reason=reason)

    return Response({"message": "Брак добавлен"}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def reserve_stock(request, business_slug, stock_id):
    """Резервирование товара по складу"""

    try:
        quantity = int(request.data.get("quantity", 0))
    except (TypeError, ValueError):
        quantity = 0

    if quantity <= 0:
        return Response(
            {"detail": "Неверное количество"}, status=status.HTTP_400_BAD_REQUEST
        )

    business = ProductService.get_business(request.user, business_slug)
    stock = get_object_or_404(
        ProductStock,
        id=stock_id,
        variant__product__business=business,
    )

    if quantity > stock.available_quantity:
        return Response(
            {"detail": "Недостаточно товара"}, status=status.HTTP_400_BAD_REQUEST
        )

    stock.reserved_quantity += quantity
    stock.save()

    return Response(
        {"message": "Товар зарезервирован", "reserved_quantity": stock.reserved_quantity},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def remove_stock_defect(request, business_slug, defect_id):
    """Удаление записи о браке по её ID"""

    business = ProductService.get_business(request.user, business_slug)

    defect = get_object_or_404(
        ProductDefect,
        id=defect_id,
        stock__variant__product__business=business,
    )

    defect.delete()

    return Response({"message": "Брак удалён"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def remove_stock_reserve(request, business_slug, stock_id):
    """Снятие резервирования с товара"""

    try:
        quantity_to_remove = int(request.data.get("quantity", 0))
    except (TypeError, ValueError):
        quantity_to_remove = 0

    if quantity_to_remove <= 0:
        return Response(
            {"detail": "Неверное количество"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    business = ProductService.get_business(request.user, business_slug)
    stock = get_object_or_404(
        ProductStock,
        id=stock_id,
        variant__product__business=business,
    )

    if quantity_to_remove > stock.reserved_quantity:
        return Response(
            {"detail": "Нельзя снять больше, чем зарезервировано"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    stock.reserved_quantity -= quantity_to_remove
    stock.save()

    return Response(
        {
            "message": f"Снято с резерва: {quantity_to_remove}",
            "reserved_quantity": stock.reserved_quantity,
        },
        status=status.HTTP_200_OK,
    )
