from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsBusinessOwner
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from marketplace.models import Product, ProductVariant, ProductImage, Category
from marketplace.serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductVariantSerializer,
    ProductImageSerializer,
)
from core.models import Business
from accounts.JWT_AUTH import CookieJWTAuthentication


@api_view(["GET", "POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def business_products_api(request, business_slug):
    """API для управления товарами бизнеса"""
    business = get_object_or_404(Business, slug=business_slug)

    if request.method == "GET":
        # Получение списка товаров бизнеса
        products = Product.objects.filter(business=business).order_by("-created_at")
        serializer = ProductListSerializer(
            products, many=True, context={"request": request}
        )
        return Response(serializer.data)

    elif request.method == "POST":
        # Создание нового товара
        serializer = ProductSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(business=business)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "DELETE"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def business_product_detail_api(request, business_slug, product_id):
    """API для работы с конкретным товаром"""
    business = get_object_or_404(Business, slug=business_slug, owner=request.user)
    product = get_object_or_404(Product, id=product_id, business=business)

    if request.method == "GET":
        serializer = ProductDetailSerializer(product, context={"request": request})
        return Response(serializer.data)

    elif request.method == "PUT":
        serializer = ProductSerializer(
            product, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def product_variants_api(request, business_slug, product_id):
    """API для работы с вариантами товара"""
    business = get_object_or_404(Business, slug=business_slug, owner=request.user)
    product = get_object_or_404(Product, id=product_id, business=business)

    if request.method == "GET":
        variants = ProductVariant.objects.filter(product=product)
        serializer = ProductVariantSerializer(variants, many=True)
        return Response(serializer.data)

    elif request.method == "POST":
        serializer = ProductVariantSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save(product=product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "DELETE"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def product_variant_detail_api(request, business_slug, product_id, variant_id):
    """API для работы с конкретным вариантом товара"""
    business = get_object_or_404(Business, slug=business_slug, owner=request.user)
    product = get_object_or_404(Product, id=product_id, business=business)
    variant = get_object_or_404(ProductVariant, id=variant_id, product=product)

    if request.method == "GET":
        serializer = ProductVariantSerializer(variant)
        return Response(serializer.data)

    elif request.method == "PUT":
        serializer = ProductVariantSerializer(variant, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        variant.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def product_images_api(request, business_slug, product_id):
    """API для работы с изображениями товара"""
    business = get_object_or_404(Business, slug=business_slug, owner=request.user)
    product = get_object_or_404(Product, id=product_id, business=business)

    if request.method == "GET":
        images = ProductImage.objects.filter(product=product).order_by(
            "-is_main", "display_order"
        )
        serializer = ProductImageSerializer(images, many=True)
        return Response(serializer.data)

    elif request.method == "POST":
        serializer = ProductImageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(product=product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def product_image_detail_api(request, business_slug, product_id, image_id):
    """API для удаления изображения товара"""
    business = get_object_or_404(Business, slug=business_slug, owner=request.user)
    product = get_object_or_404(Product, id=product_id, business=business)
    image = get_object_or_404(ProductImage, id=image_id, product=product)

    image.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def product_categories_api(request):
    """API для получения категорий товаров"""
    categories = Category.objects.filter(is_active=True)
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)


from marketplace.models import Product, CategoryAttribute, Attribute


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def get_product_attributes(request, business_slug, product_id):
    try:
        product = get_object_or_404(
            Product, id=product_id, business__slug=business_slug
        )

        if not product.category:
            return Response({"attributes": [], "existing_variants": []})

        # 1. Получаем все возможные атрибуты для этой категории
        category_attrs = (
            CategoryAttribute.objects.filter(category=product.category)
            .select_related("attribute")
            .prefetch_related("attribute__values")
        )

        attributes = []
        for cat_attr in category_attrs:
            attr_data = {
                "id": cat_attr.id,
                "attribute_id": cat_attr.attribute.id,
                "name": cat_attr.attribute.name,
                "required": cat_attr.required,
                "has_predefined_values": cat_attr.attribute.has_predefined_values,
                "show_attribute_at_right": cat_attr.show_attribute_at_right,
                "values": (
                    [
                        {"id": val.id, "value": val.value, "color_code": val.color_code}
                        for val in cat_attr.attribute.values.all()
                    ]
                    if cat_attr.attribute.has_predefined_values
                    else []
                ),
            }
            attributes.append(attr_data)

        # 2. Получаем существующие варианты товара с их атрибутами
        existing_variants = []
        for variant in product.variants.all().prefetch_related(
            "attributes__category_attribute__attribute", "attributes__predefined_value"
        ):
            variant_data = {
                "id": variant.id,
                "sku": variant.sku,
                "price": str(variant.price),
                "discount": str(variant.discount) if variant.discount else None,
                "stock_quantity": variant.stock_quantity,
                "show_this": variant.show_this,
                "has_custom_name": variant.has_custom_name,
                "custom_name": variant.custom_name,
                "has_custom_description": variant.has_custom_description,
                "custom_description": variant.custom_description,
                "attributes": [],
            }

            for attr in variant.attributes.all():
                attr_data = {
                    "category_attribute_id": attr.category_attribute.id,
                    "attribute_id": attr.category_attribute.attribute.id,
                    "attribute_name": attr.category_attribute.attribute.name,
                    "predefined_value_id": (
                        attr.predefined_value.id if attr.predefined_value else None
                    ),
                    "predefined_value": (
                        attr.predefined_value.value if attr.predefined_value else None
                    ),
                    "custom_value": attr.custom_value,
                    "has_predefined_values": attr.category_attribute.attribute.has_predefined_values,
                }
                variant_data["attributes"].append(attr_data)

            existing_variants.append(variant_data)

        return Response(
            {
                "attributes": attributes,  # Все возможные атрибуты для товара
                "existing_variants": existing_variants,  # Существующие варианты с их атрибутами
            }
        )

    except Exception as e:
        return Response({"error": str(e)}, status=400)
