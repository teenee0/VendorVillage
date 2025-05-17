from itertools import product

from django.core.paginator import Paginator
from django.http import Http404, HttpResponseForbidden

from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Category
from .serializers import *

from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib.auth.decorators import login_required
# from .models import Product, ProductImage
from core.models import Business
from rest_framework import status

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

# @api_view(["GET"])
# def category_products_api(request, pk):
#     category = get_object_or_404(Category, pk=pk)
#     print(category)
#     ids = get_descendant_ids(category)

#     products_qs = Product.objects.filter(
#         category_id__in=ids, on_the_main=True, stock_quantity__gt=0
#     )

#     # Фильтрация по названию
#     # TODO улучшить поиск
#     search_query = request.GET.get("search", "")
#     if search_query:
#         products_qs = products_qs.filter(name__icontains=search_query)

#     # Фильтрация по цене
#     price_min = request.GET.get("price_min")
#     if price_min:
#         try:
#             products_qs = products_qs.filter(price__gte=float(price_min))
#         except ValueError:
#             pass

#     price_max = request.GET.get("price_max")
#     if price_max:
#         try:
#             products_qs = products_qs.filter(price__lte=float(price_max))
#         except ValueError:
#             pass

#     # Сортировка
#     sort_option = request.GET.get("sort", "-id")
#     if sort_option in ["price", "-price", "name", "-name", "-created_at", "-id"]:
#         products_qs = products_qs.order_by(sort_option)

#     # Пагинация
#     paginator = Paginator(products_qs, 12)
#     page_number = request.GET.get("page", 1)
#     try:
#         page_obj = paginator.page(page_number)
#     except PageNotAnInteger:
#         page_obj = paginator.page(1)
#     except EmptyPage:
#         page_obj = paginator.page(paginator.num_pages)

#     serializer = ProductSerializer(page_obj, many=True)
#     ancestors = category.get_ancestors(include_self=True)

#     # Формируем breadcrumbs
#     breadcrumbs = [
#         {
#             "id": ancestor.id,
#             "name": ancestor.name,
#             "url": f"/marketplace/categories/{ancestor.id}"
#         }
#         for ancestor in ancestors
#     ]

#     return Response(
#         {
#             "category": CategorySerializer(category).data,
#             "breadcrumbs": breadcrumbs,
#             "subcategories": CategorySerializer(
#                 category.children.all().order_by("name"), many=True
#             ).data,
#             "products": serializer.data,
#             "pagination": {
#                 "current_page": page_obj.number,
#                 "total_pages": paginator.num_pages,
#                 "total_items": paginator.count,
#                 "has_next": page_obj.has_next(),
#                 "has_previous": page_obj.has_previous(),
#             },
#             "search_query": search_query,
#             "price_min": price_min,
#             "price_max": price_max,
#             "sort": sort_option,
#         }
#     )

from django.shortcuts import get_object_or_404
from django.db.models import Q, F, Case, When, DecimalField, Min, Max
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Subquery, OuterRef
from .models import Category, Product, ProductVariant, AttributeValue
from .serializers import ProductListSerializer, CategorySerializer, AttributeValueSerializer
from django.db.models import Q, Exists, OuterRef
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.cache import cache

@api_view(['GET'])
def get_category_filters(request, pk):
    """
    Получение доступных фильтров для категории и её подкатегорий.
    Возвращает все атрибуты категории и реально используемые значения (как predefined, так и custom).
    """
    cache_key = f'category_filters_{pk}'
    cached_data = cache.get(cache_key)
    if cached_data:
        return Response(cached_data)
    
    category = get_object_or_404(Category, pk=pk)
    categories_in_hierarchy = category.get_ancestors(include_self=True)
    
    available_filters = {}
    
    # Получаем все фильтруемые атрибуты категории и её предков
    category_attrs = CategoryAttribute.objects.filter(
        category__in=categories_in_hierarchy,
        attribute__is_filterable=True
    ).select_related('attribute').distinct()
    
    for cat_attr in category_attrs:
        attr = cat_attr.attribute
        
        if attr.id in available_filters:
            continue
        
        # 1. Собираем предопределенные значения, которые используются в товарах
        predefined_values = AttributeValue.objects.filter(
            attribute=attr,
            productvariantattribute__variant__product__category__in=categories_in_hierarchy
        ).distinct()
        
        # 2. Собираем произвольные значения из custom_value
        custom_values = ProductVariantAttribute.objects.filter(
            category_attribute=cat_attr,
            variant__product__category__in=categories_in_hierarchy,
            custom_value__isnull=False
        ).exclude(custom_value='').values_list('custom_value', flat=True).distinct()
        
        # Сериализуем предопределенные значения
        predefined_data = AttributeValueSerializer(predefined_values, many=True).data
        
        # Добавляем произвольные значения как объекты с value и без id
        custom_data = [{'value': val, 'custom': True} for val in custom_values]
        
        # Объединяем оба типа значений
        all_values = predefined_data + custom_data
        
        # Если нет значений в товарах, берем все возможные предопределенные значения
        if not all_values and attr.has_predefined_values:
            all_values = AttributeValueSerializer(
                AttributeValue.objects.filter(attribute=attr),
                many=True
            ).data
        
        if all_values:
            available_filters[attr.id] = {
                'id': attr.id,
                'name': attr.name,
                'type': 'choice',
                'has_predefined_values': attr.has_predefined_values,
                'required': cat_attr.required,
                'values': all_values
            }
    
    # Сортируем фильтры по имени
    sorted_filters = sorted(available_filters.values(), key=lambda x: x['name'])
    
    response_data = {
        'category': {
            'id': category.id,
            'name': category.name
        },
        'filters': sorted_filters
    }
    
    # cache.set(cache_key, response_data, timeout=60*60*24)
    return Response(response_data)

from django.db.models import Q, Case, When, F, DecimalField, Min, Max
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

def get_descendant_ids(category):
    """Получить список ID всех подкатегорий, включая id переданной категории"""
    descendants = category.get_descendants(include_self=True)
    return [desc.id for desc in descendants]

@api_view(["GET"])
def category_products_api(request, pk):
    """API для получения товаров в указанной категории."""
    category = get_object_or_404(Category, pk=pk, is_active=True)
    ids = get_descendant_ids(category)

    # Базовый запрос: активные товары в указанной категории (и подкатегориях)
    products_qs = Product.objects.filter(
        category_id__in=ids, 
        is_active=True
    ).prefetch_related('variants', 'images')
    
    # Фильтр по наличию на складе
    in_stock_only = request.GET.get('in_stock') == '1'
    if in_stock_only:
        products_qs = products_qs.filter(variants__stock_quantity__gt=0).distinct()
    
    # Фильтр "только на главной"
    main_only = request.GET.get('main_only') == '1'
    if main_only:
        products_qs = products_qs.filter(on_the_main=True)

    # Поиск по названию и описанию
    search_query = request.GET.get("search", "")
    if search_query:
        products_qs = products_qs.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query) |
            Q(variants__custom_name__icontains=search_query)
        ).distinct()

    # Фильтрация по цене
    price_min = request.GET.get("price_min")
    if price_min:
        try:
            # Учитываем скидки при фильтрации по минимальной цене
            products_qs = products_qs.annotate(
                min_price=Min(
                    Case(
                        When(variants__discount__isnull=False, 
                             then=F('variants__price') - F('variants__discount')),
                        default=F('variants__price'),
                        output_field=DecimalField()
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
                        When(variants__discount__isnull=False, 
                             then=F('variants__price') - F('variants__discount')),
                        default=F('variants__price'),
                        output_field=DecimalField()
                    )
                )
            ).filter(max_price__lte=float(price_max))
        except ValueError:
            pass
    
    # Фильтрация по атрибутам
    for key, value in request.GET.items():
        if key.startswith('attr_') and value:
            try:
                attr_id = int(key.replace('attr_', ''))
                attr_values = request.GET.getlist(key)  # Получаем все значения для этого атрибута
                
                # Создаем Q-объекты для фильтрации
                q_objects = Q()
                
                for val in attr_values:
                    if val.startswith('val_'):
                        # Обработка текстовых значений (с префиксом val_)
                        text_value = val.replace('val_', '')
                        q_objects |= Q(
                            variants__attributes__category_attribute__attribute_id=attr_id,
                            variants__attributes__custom_value=text_value
                        )
                    else:
                        # Обработка числовых ID (без префикса)
                        q_objects |= Q(
                            variants__attributes__category_attribute__attribute_id=attr_id,
                            variants__attributes__predefined_value__id=val
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
                    When(variants__discount__isnull=False, 
                         then=F('variants__price') - F('variants__discount')),
                    default=F('variants__price'),
                    output_field=DecimalField()
                )
            )
        ).order_by('sort_price')
    elif sort_option == "-price":
        # Сортировка по максимальной цене с учетом скидок
        products_qs = products_qs.annotate(
            sort_price=Max(
                Case(
                    When(variants__discount__isnull=False, 
                         then=F('variants__price') - F('variants__discount')),
                    default=F('variants__price'),
                    output_field=DecimalField()
                )
            )
        ).order_by('-sort_price')
    elif sort_option in ["name", "-name", "created_at", "-created_at"]:
        products_qs = products_qs.order_by(sort_option)

    # Пагинация
    per_page = int(request.GET.get('per_page', 12))
    paginator = Paginator(products_qs, per_page)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    serializer = ProductListSerializer(page_obj, many=True, context={'request': request})
    ancestors = category.get_ancestors(include_self=True)

    # Формируем breadcrumbs
    breadcrumbs = [
        {
            "id": ancestor.id,
            "name": ancestor.name,
            "url": f"/marketplace/categories/{ancestor.id}"
        }
        for ancestor in ancestors
    ]

    return Response(
        {
            "category": CategorySerializer(category).data,
            "breadcrumbs": breadcrumbs,
            "subcategories": CategorySerializer(
                category.children.filter(is_active=True).order_by("ordering", "name"), 
                many=True
            ).data,
            "products": serializer.data,
            "pagination": {
                "current_page": page_obj.number,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
                "per_page": per_page
            },
            "applied_filters": {
                "search_query": search_query,
                "price_min": price_min,
                "price_max": price_max,
                "in_stock_only": in_stock_only,
                "main_only": main_only,
                "sort": sort_option
            }
        }
    )


@api_view(["GET"])
def product_detail_api(request, pk):
    try:
        # Получаем продукт с предзагрузкой всех связанных данных
        product = Product.objects.filter(is_active=True).select_related(
            'category', 'business'
        ).prefetch_related(
            'images',
            'variants',
            'variants__attributes',
            'variants__attributes__predefined_value',
            'variants__attributes__category_attribute__attribute'
        ).get(pk=pk)

        # Формируем breadcrumbs
        
        ancestors = product.category.get_ancestors(include_self=True)
        breadcrumbs = [
        {
            "id": ancestor.id,
            "name": ancestor.name,
            "url": f"/marketplace/categories/{ancestor.id}"
        }
        for ancestor in ancestors
    ]

        # Получаем похожие товары (из той же категории)
        same_products = Product.objects.filter(
            category=product.category, is_active=True
        ).exclude(id=product.id).order_by('?')[:8]

        serializer = ProductDetailSerializer(product, context={'request': request})
        same_products_serializer = ProductListSerializer(
            same_products, 
            many=True, 
            context={'request': request}
        )

        return Response({
            "breadcrumbs": breadcrumbs,
            "product": serializer.data,
            "same_products": same_products_serializer.data
        })

    except Product.DoesNotExist:
        return Response(
            {"error": "Product not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )


# @login_required
# def dashboard(request):
#     """
#        Страница панели управления бизнесом для владельца.
#        Если у пользователя есть бизнес, выводим информацию и ссылки на управление.
#        Если бизнеса нет – перенаправляем или показываем сообщение.
#        """
#
#     business = Business.objects.filter(owner=request.user).first()
#     if not business:
#         return redirect('core:create_business')
#     context = {
#         'business': business,
#     }
#     return render(request, 'marketplace/business_dashboard.html', context)


# @login_required()
# def business_product_list(request, pk):
#     """
#     Показывает список товаров, принадлежащих бизнесу с указанным pk.
#     """
#     if request.user.groups.filter(name="Business").exists():
#         business = get_object_or_404(Business, pk=pk, owner=request.user)
#         products = business.products.all().order_by("-created_at")
#         # 3) Пагинация
#         page_number = request.GET.get("page", 1)
#         paginator = Paginator(products, 11)  # 12 товаров на страницу
#         page_obj = paginator.get_page(page_number)
#         context = {
#             "edit": True,
#             "business": business,
#             "products": products,
#             "page_obj": page_obj,
#         }
#         return render(request, "marketplace/business_product_list.html", context)
#     else:
#         raise Http404


# @login_required
# def product_add(request, pk):
#     # Предполагаем, что у пользователя есть бизнес (поле owner в Business и related_name='businesses' в User)
#     business = get_object_or_404(Business, pk=pk)
#     if business.owner != request.user:
#         raise Http404

#     if request.method == "POST":
#         product_form = ProductForm(request.POST)
#         image_form = ProductImageForm(request.POST, request.FILES)
#         if product_form.is_valid() and image_form.is_valid():
#             product = product_form.save(commit=False)
#             product.business = business
#             product.save()
#             # Если изображение было загружено, сохраняем его
#             if image_form.cleaned_data.get("image"):
#                 new_image = image_form.save(commit=False)
#                 new_image.product = product
#                 new_image.save()
#             return redirect("marketplace:product_edit", pk=product.id)
#     else:
#         product_form = ProductForm()
#         image_form = ProductImageForm()

#     context = {
#         "product_form": product_form,
#         "image_form": image_form,
#         "action": "Добавление товара",
#         "business": business,  # для кнопки "Назад"
#     }
#     return render(request, "marketplace/includes/product_add.html", context)


# @login_required()
# def product_edit(request, pk):
#     product = get_object_or_404(Product, id=pk)
#     if product.business.owner != request.user:
#         raise Http404
#     if request.method == "POST":
#         # Если нажата кнопка сохранения данных товара
#         if "save_product" in request.POST:
#             product_form = ProductForm(request.POST, instance=product)
#             image_form = ProductImageForm()  # пустая форма для изображения
#             if product_form.is_valid():
#                 product_form.save()
#                 return redirect("marketplace:product_edit", pk=product.id)
#         # Если нажата кнопка загрузки изображения
#         elif "upload_image" in request.POST:
#             product_form = ProductForm(
#                 instance=product
#             )  # форма товара для заполнения страницы
#             image_form = ProductImageForm(request.POST, request.FILES)
#             if image_form.is_valid():
#                 new_image = image_form.save(commit=False)
#                 new_image.product = product  # связываем изображение с товаром
#                 new_image.save()
#                 return redirect("marketplace:product_edit", pk=product.id)
#     else:
#         product_form = ProductForm(instance=product)
#         image_form = ProductImageForm()

#     images = (
#         product.images.all()
#     )  # получаем изображения, используя related_name 'images'

#     context = {
#         "product": product,
#         "product_form": product_form,
#         "image_form": image_form,
#         "images": images,
#     }
#     return render(request, "marketplace/includes/product_edit.html", context)


# @login_required
# def product_delete(request, pk):
#     product = get_object_or_404(Product, pk=pk)
#     # Проверяем, что текущий пользователь является владельцем бизнеса товара
#     if product.business.owner != request.user:
#         raise Http404("Товар не найден")

#     # Можно предусмотреть подтверждение удаления через POST,
#     # но для простоты примера удалим товар при GET-запросе.
#     product.delete()
#     # Перенаправляем пользователя на список товаров бизнеса
#     return redirect("marketplace:business_product_list", pk=product.business.id)


# @login_required
# def product_image_delete(request, image_id):
#     image = get_object_or_404(ProductImage, pk=image_id)
#     # Проверяем, что владелец товара совпадает с текущим пользователем
#     if image.product.business.owner != request.user:
#         return HttpResponseForbidden("Доступ запрещен")
#     product_id = image.product.id
#     image.delete()
#     return redirect("marketplace:product_edit", pk=product_id)
