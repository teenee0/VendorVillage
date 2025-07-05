from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Category
from .serializers import *

from django.shortcuts import get_object_or_404
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Category, Product
from .serializers import (
    ProductListSerializer,
    CategorySerializer,
    ProductDetailSerializer,
)
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .ProductsSet import ProductSet


@api_view(["GET"])
def test_api(request):
    """API для товаров"""
    products = ProductSet.get_products_by_category(33, visibility="marketplace")
    category = get_object_or_404(Category, pk=33, is_active=True)
    breadcrumbs = ProductSet.get_breadcrumbs_by_category(category)
    filtered_products, applied_filters = ProductSet.filter_products(products, request)
    page_obj, pagination = ProductSet.pagination_for_products(
        filtered_products, request
    )
    filters = ProductSet.get_filters_by_products(filtered_products)
    category_serialized = CategorySerializer(category)

    products_page = ProductListSerializer(
        page_obj, many=True, context={"request": request}
    )

    # Возвращаем сериализованные данные в ответе
    return Response(
        {
            "category": category_serialized.data,
            "breadcrumbs": breadcrumbs,
            "subcategories": CategorySerializer(
                category.children.filter(is_active=True).order_by("ordering", "name"),
                many=True,
            ).data,
            "products": products_page.data,
            "pagination": pagination,
            "applied_filters": applied_filters,
            "filters": filters,
        }
    )


@api_view(["GET"])
def marketplace_categories_api(request):
    """API для категорий маркетплейса"""
    parent_categories = Category.objects.filter(parent__isnull=True).order_by("name")
    serializer = CategorySerializer(parent_categories, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def child_category_api(request, pk):
    category = get_object_or_404(Category, pk=pk)
    serializer = CategorySerializer(category)

    if category.get_level() < 2 and category.get_children().count() >= 2:
        children = category.get_children().order_by("ordering")
        children_serializer = CategorySerializer(children, many=True)
        return Response(
            {"category": serializer.data, "children": children_serializer.data}
        )
    else:
        return Response(
            {
                "should_redirect": True,
                "redirect_to": f"/marketplace/categories/{pk}/products",
            }
        )


@api_view(["GET"])
def category_products_api(request, pk):
    """API для получения товаров в указанной категории."""
    products = ProductSet.get_products_by_category(pk, visibility="marketplace")
    category = get_object_or_404(Category, pk=pk, is_active=True)
    breadcrumbs = ProductSet.get_breadcrumbs_by_category(category)
    filtered_products, applied_filters = ProductSet.filter_products(products, request)
    page_obj, pagination = ProductSet.pagination_for_products(
        filtered_products, request
    )
    filters = ProductSet.get_filters_by_products(filtered_products)

    category_serialized = CategorySerializer(category)

    products_page = ProductListSerializer(
        page_obj, many=True, context={"request": request}
    )

    # Возвращаем сериализованные данные в ответе
    return Response(
        {
            "oldData": {
                "category": category_serialized.data,
                "breadcrumbs": breadcrumbs,
                "subcategories": CategorySerializer(
                    category.children.filter(is_active=True).order_by(
                        "ordering", "name"
                    ),
                    many=True,
                ).data,
                "products": products_page.data,
                "pagination": pagination,
                "applied_filters": applied_filters,
            },
            "filters": filters,
        }
    )


@api_view(["GET"])
def product_detail_api(request, pk):
    try:
        # Получаем продукт с предзагрузкой всех связанных данных
        product = ProductSet.get_product_detail(pk)

        # Формируем breadcrumbs
        breadcrumbs = ProductSet.get_breadcrumbs_by_category(product.category)

        # Получаем похожие товары (из той же категории)
        same_products = ProductSet.get_same_products(product)

        serializer = ProductDetailSerializer(product, context={"request": request})
        same_products_serializer = ProductListSerializer(
            same_products, many=True, context={"request": request}
        )

        return Response(
            {
                "breadcrumbs": breadcrumbs,
                "product": serializer.data,
                "same_products": same_products_serializer.data,
            }
        )

    except Product.DoesNotExist:
        return Response(
            {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
        )
