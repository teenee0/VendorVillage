from django.core.paginator import Paginator
from django.http import Http404, HttpResponseForbidden

from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Category
from .serializers import *

from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib.auth.decorators import login_required
from core.models import Business
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q, F, Case, When, DecimalField, Min, Max
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Subquery, OuterRef
from .models import Category, Product, ProductVariant, AttributeValue
from .serializers import (
    ProductListSerializer,
    CategorySerializer,
    AttributeValueSerializer,
)
from django.db.models import Q, Exists, OuterRef
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import Q, Case, When, F, DecimalField, Min, Max
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from django.db.models import Exists, OuterRef


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


# def get_descendant_ids(category):
#     ids = [category.id]
#     for child in category.children.all():
#         ids += get_descendant_ids(child)
#     return ids


def filter_products_by_variants(products):
    # Подзапрос для проверки наличия варианта с stock_quantity > 0 и show_this=True
    variant_subquery = ProductVariant.objects.filter(
        product=OuterRef("pk"), stock_quantity__gt=0, show_this=True
    )

    # Аннотируем продукты, у которых есть хотя бы один подходящий вариант
    filtered_products = products.annotate(
        has_valid_variant=Exists(variant_subquery)
    ).filter(has_valid_variant=True)

    return filtered_products


def get_products(request, pk):
    category = get_object_or_404(Category, pk=pk, is_active=True)
    ids = get_descendant_ids(category)

    # Базовый запрос: активные товары в указанной категории (и подкатегориях)
    products = Product.objects.filter(category_id__in=ids, is_active=True)

    products_qs = filter_products_by_variants(products)

    # Фильтр по наличию на складе
    in_stock_only = request.GET.get("in_stock") == "1"
    if in_stock_only:
        products_qs = products_qs.filter(variants__stock_quantity__gt=0).distinct()

    # Фильтр "только на главной"
    main_only = request.GET.get("main_only") == "1"
    if main_only:
        products_qs = products_qs.filter(on_the_main=True)

    # Поиск по названию и описанию
    search_query = request.GET.get("search", "")
    if search_query:
        products_qs = products_qs.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(variants__custom_name__icontains=search_query)
        ).distinct()

    # Фильтрация по цене
    price_min = request.GET.get("price_min")
    if price_min:
        try:
            # Учитываем скидки при фильтрации по минимальной цене
            products_qs = products_qs.annotate(
                min_price=Min(
                    Case(
                        When(
                            variants__discount__isnull=False,
                            then=F("variants__price") - F("variants__discount"),
                        ),
                        default=F("variants__price"),
                        output_field=DecimalField(),
                    )
                )
            ).filter(min_price__gte=float(price_min))
        except ValueError:
            pass

    price_max = request.GET.get("price_max")
    if price_max:
        try:
            # Учитываем скидки при фильтрации по максимальной цене
            products_qs = products_qs.annotate(
                max_price=Max(
                    Case(
                        When(
                            variants__discount__isnull=False,
                            then=F("variants__price") - F("variants__discount"),
                        ),
                        default=F("variants__price"),
                        output_field=DecimalField(),
                    )
                )
            ).filter(max_price__lte=float(price_max))
        except ValueError:
            pass

    # Фильтрация по атрибутам
    for key, value in request.GET.items():
        if key.startswith("attr_") and value:
            try:
                attr_id = int(key.replace("attr_", ""))
                attr_values = request.GET.getlist(
                    key
                )  # Получаем все значения для этого атрибута

                # Создаем Q-объекты для фильтрации
                q_objects = Q()

                for val in attr_values:
                    if val.startswith("val_"):
                        # Обработка текстовых значений (с префиксом val_)
                        text_value = val.replace("val_", "")
                        q_objects |= Q(
                            variants__attributes__category_attribute__attribute_id=attr_id,
                            variants__attributes__custom_value=text_value,
                        )
                    else:
                        # Обработка числовых ID (без префикса)
                        q_objects |= Q(
                            variants__attributes__category_attribute__attribute_id=attr_id,
                            variants__attributes__predefined_value__id=val,
                        )

                if q_objects:
                    products_qs = products_qs.filter(q_objects).distinct()

            except (ValueError, TypeError) as e:
                print(f"Error processing attribute filter: {e}")
                continue

    # Сортировка
    sort_option = request.GET.get("sort", "-created_at")
    if sort_option == "price":
        # Сортировка по минимальной цене с учетом скидок
        products_qs = products_qs.annotate(
            sort_price=Min(
                Case(
                    When(
                        variants__discount__isnull=False,
                        then=F("variants__price") - F("variants__discount"),
                    ),
                    default=F("variants__price"),
                    output_field=DecimalField(),
                )
            )
        ).order_by("sort_price")
    elif sort_option == "-price":
        # Сортировка по максимальной цене с учетом скидок
        products_qs = products_qs.annotate(
            sort_price=Max(
                Case(
                    When(
                        variants__discount__isnull=False,
                        then=F("variants__price") - F("variants__discount"),
                    ),
                    default=F("variants__price"),
                    output_field=DecimalField(),
                )
            )
        ).order_by("-sort_price")
    elif sort_option in ["name", "-name", "created_at", "-created_at"]:
        products_qs = products_qs.order_by(sort_option)
    return (
        products_qs,
        category,
        search_query,
        price_min,
        price_max,
        in_stock_only,
        main_only,
        sort_option,
    )


from django.db.models import Count
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def get_category_filters(request, pk):
    # Получаем отфильтрованные товары
    products_qs, category, _, _, _, _, _, _ = get_products(request, pk)
    product_ids = products_qs.values_list("id", flat=True)

    # Находим все уникальные атрибуты для этих товаров
    attributes = Attribute.objects.filter(
        category_attributes__productvariantattribute__variant__product_id__in=product_ids,
        is_filterable=True,
    ).distinct()

    filters = []

    for attr in attributes:
        # Получаем CategoryAttribute для этого атрибута в текущей категории
        try:
            cat_attr = CategoryAttribute.objects.get(attribute=attr, category=category)
            required = cat_attr.required
        except CategoryAttribute.DoesNotExist:
            required = False

        # Предопределенные значения
        predefined_values = AttributeValue.objects.filter(
            attribute=attr, productvariantattribute__variant__product_id__in=product_ids
        ).distinct()

        # Кастомные значения
        custom_values = (
            ProductVariantAttribute.objects.filter(
                category_attribute__attribute=attr,
                variant__product_id__in=product_ids,
                custom_value__isnull=False,
            )
            .exclude(custom_value="")
            .values_list("custom_value", flat=True)
            .distinct()
        )

        # Формируем список значений
        values = []
        for val in predefined_values:
            values.append(
                {
                    "id": val.id,
                    "value": val.value,
                    "attribute_name": attr.name,
                    "color_code": val.color_code,
                }
            )

        for custom_val in custom_values:
            values.append(
                {
                    "id": None,
                    "value": custom_val,
                    "attribute_name": attr.name,
                    "color_code": None,
                }
            )

        if values:
            filters.append(
                {
                    "id": attr.id,
                    "name": attr.name,
                    "type": "choice",
                    "has_predefined_values": attr.has_predefined_values,
                    "required": required,
                    "values": values,
                }
            )

    return Response(
        {
            "category": {"id": category.id, "name": category.name},
            "filters": sorted(filters, key=lambda x: x["name"]),
        }
    )


def get_descendant_ids(category):
    """Получить список ID всех подкатегорий, включая id переданной категории"""
    descendants = category.get_descendants(include_self=True)
    return [desc.id for desc in descendants]


@api_view(["GET"])
def get_category_filters_test(request, pk):
    category = get_object_or_404(Category, pk=pk, is_active=True)
    ids = get_descendant_ids(category)
    products = Product.objects.filter(
        category_id__in=ids,
        is_active=True,
    )
    # фильтр отсеивающий продукты без вариантов которые можно показать
    filtered_products = filter_products_by_variants(products)

    serializer = ProductListSerializer(
        filtered_products, many=True, context={"request": request}
    )
    return Response({"name": 12, "products": serializer.data})


@api_view(["GET"])
def category_products_api(request, pk):
    """API для получения товаров в указанной категории."""
    (
        products_qs,
        category,
        search_query,
        price_min,
        price_max,
        in_stock_only,
        main_only,
        sort_option,
    ) = get_products(request, pk)
    # Пагинация
    per_page = int(request.GET.get("per_page", 12))
    paginator = Paginator(products_qs, per_page)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    serializer = ProductListSerializer(
        page_obj, many=True, context={"request": request}
    )
    ancestors = category.get_ancestors(include_self=True)

    # Формируем breadcrumbs
    breadcrumbs = [
        {
            "id": ancestor.id,
            "name": ancestor.name,
            "url": f"/marketplace/categories/{ancestor.id}",
        }
        for ancestor in ancestors
    ]

    return Response(
        {
            "category": CategorySerializer(category).data,
            "breadcrumbs": breadcrumbs,
            "subcategories": CategorySerializer(
                category.children.filter(is_active=True).order_by("ordering", "name"),
                many=True,
            ).data,
            "products": serializer.data,
            "pagination": {
                "current_page": page_obj.number,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
                "per_page": per_page,
            },
            "applied_filters": {
                "search_query": search_query,
                "price_min": price_min,
                "price_max": price_max,
                "in_stock_only": in_stock_only,
                "main_only": main_only,
                "sort": sort_option,
            },
        }
    )


@api_view(["GET"])
def product_detail_api(request, pk):
    try:
        # Получаем продукт с предзагрузкой всех связанных данных
        product = (
            Product.objects.filter(is_active=True)
            .select_related("category", "business")
            .prefetch_related(
                "images",
                "variants",
                "variants__attributes",
                "variants__attributes__predefined_value",
                "variants__attributes__category_attribute__attribute",
            )
            .get(pk=pk)
        )

        # Формируем breadcrumbs

        ancestors = product.category.get_ancestors(include_self=True)
        breadcrumbs = [
            {
                "id": ancestor.id,
                "name": ancestor.name,
                "url": f"/marketplace/categories/{ancestor.id}",
            }
            for ancestor in ancestors
        ]

        # Получаем похожие товары (из той же категории)
        same_products = (
            Product.objects.filter(category=product.category, is_active=True)
            .exclude(id=product.id)
            .order_by("?")[:8]
        )

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
