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
    ProductDetailSerializer,
    ProductListSerializer,
    ProductVariantSerializer,
    ProductImageSerializer,
)
from core.models import Business
from accounts.JWT_AUTH import CookieJWTAuthentication
from .serializers import EnhancedProductListSerializer
from marketplace.ProductsSet import ProductSet
from .ProductCreateService import ProductService
from .product_detail_serializer import ProductDetailSerializer


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def business_products_api(request, business_slug):
    """API для управления товарами бизнеса"""
    business = get_object_or_404(Business, slug=business_slug)

    # Получение списка товаров бизнеса
    products = Product.objects.filter(business=business).order_by("-created_at")
    filtered_products, applied_filters = ProductSet.filter_products(products, request)
    page_obj, pagination = ProductSet.pagination_for_products(
        filtered_products, request
    )
    filters = ProductSet.get_filters_by_products(filtered_products)
    categories = Category.objects.filter(products__business=business).distinct()

    serializied_products = EnhancedProductListSerializer(
        page_obj, many=True, context={"request": request}
    )
    serializied_categories = CategorySerializer(categories, many=True)
    all_data = {
        "categories": serializied_categories.data,
        "products": serializied_products.data,
        "applied_filters": applied_filters,
        "filters": filters,
        "pagination": pagination,
    }
    return Response(all_data)


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def get_info_product(request, business_slug, product_id):
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
