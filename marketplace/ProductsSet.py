from django.db.models import (
    Q,
    F,
    Case,
    When,
    DecimalField,
    Min,
    Max,
    Sum,
    Exists,
    OuterRef,
)
from django.shortcuts import get_object_or_404
from .models import (
    Category,
    Product,
    ProductVariant,
    AttributeValue,
    Attribute,
    CategoryAttribute,
    ProductVariantAttribute,
)
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import QueryDict


class ProductSet:
    @staticmethod
    def get_products_by_category(category_pk):
        # Получаем категорию по первичному ключу
        category = get_object_or_404(Category, pk=category_pk, is_active=True)

        # Получаем список ID всех подкатегорий, включая текущую категорию
        descendant_ids = ProductSet.get_descendant_ids(category)

        # Получаем товары, которые принадлежат категории или её подкатегориям и активны
        products = Product.objects.filter(
            category_id__in=descendant_ids, is_active=True
        )

        # Фильтруем товары по наличию доступных вариантов
        filtered_products = ProductSet.filter_products_by_variants(products)

        return filtered_products

    @staticmethod
    def get_descendant_ids(category):
        # Получаем всех потомков категории, включая саму категорию
        descendants = category.get_descendants(include_self=True)
        return [desc.id for desc in descendants]

    @staticmethod
    def filter_products_by_variants(products):
        # Создаем подзапрос для проверки наличия варианта с доступным количеством > 0 и show_this=True
        variant_subquery = (
            ProductVariant.objects.filter(product=OuterRef("pk"), show_this=True)
            .annotate(
                total_available=Sum("stocks__quantity")
                - Sum("stocks__reserved_quantity")
            )
            .filter(total_available__gt=0)
        )

        # Аннотируем и фильтруем продукты, у которых есть хотя бы один подходящий вариант
        filtered_products = products.annotate(
            has_valid_variant=Exists(variant_subquery)
        ).filter(has_valid_variant=True)

        return filtered_products

    @staticmethod
    def get_breadcrumbs_by_category(category):
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
        return breadcrumbs

    @staticmethod
    def pagination_for_products(products, request):

        per_page = int(request.GET.get("per_page", 12))
        paginator = Paginator(products, per_page)
        page_number = request.GET.get("page", 1)
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        pagination = {
            "current_page": page_obj.number,
            "total_pages": paginator.num_pages,
            "total_items": paginator.count,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "per_page": per_page,
        }

        return page_obj, pagination
    
    @staticmethod
    def get_product_detail(pk):
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
        return product
    
    @staticmethod
    def get_same_products(product):
        same_products = (
            Product.objects.filter(category=product.category, is_active=True)
            .exclude(id=product.id)
            .order_by("?")[:8]
        )
        return same_products

    @staticmethod
    def get_filters_by_products(products_qs, category=None):
        if category:
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
                    cat_attr = CategoryAttribute.objects.get(
                        attribute=attr, category=category
                    )
                    required = cat_attr.required
                except CategoryAttribute.DoesNotExist:
                    required = False

                # Предопределенные значения
                predefined_values = AttributeValue.objects.filter(
                    attribute=attr,
                    productvariantattribute__variant__product_id__in=product_ids,
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

            response = {
                "category": {"id": category.id, "name": category.name},
                "filters": sorted(filters, key=lambda x: x["name"]),
            }

            return response
        else:
            product_ids = products_qs.values_list("id", flat=True)

            # Находим все уникальные атрибуты для этих товаров
            attributes = Attribute.objects.filter(
                category_attributes__productvariantattribute__variant__product_id__in=product_ids,
                is_filterable=True,
            ).distinct()

            filters = []

            for attr in attributes:
                # Получаем все значения атрибута для этих товаров
                predefined_values = AttributeValue.objects.filter(
                    attribute=attr,
                    productvariantattribute__variant__product_id__in=product_ids,
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
                            "required": False,  # Без категории не можем определить обязательность
                            "values": sorted(values, key=lambda x: x["value"]),
                        }
                    )

            return {
                "filters": sorted(filters, key=lambda x: x["name"]),
            }

    @staticmethod
    def filter_products(products_qs, request):
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
                | Q(variants__barcode__icontains=search_query)
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

        # Формируем объект applied_filters
        applied_filters = {
            "search_query": search_query,
            "price_min": price_min,
            "price_max": price_max,
            "in_stock_only": in_stock_only,
            "main_only": main_only,
            "sort": sort_option,
        }

        return products_qs, applied_filters
