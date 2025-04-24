from django.core.paginator import Paginator
from django.http import Http404, HttpResponseForbidden

from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Category
from .serializers import *

from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib.auth.decorators import login_required
from marketplace.forms import ProductForm, ProductImageForm
from .models import Product, ProductImage
from core.models import Business

# Create your views here.
def home(request):
    return redirect('marketplace:parent_category_list')

# marketplace/views.py

def parent_category_list(request):
    """
    Показывает список только тех категорий, у которых parent is NULL
    (то есть «родительских»).
    """
    parent_cats = Category.objects.filter(parent__isnull=True).order_by('name')
    context = {
        'parent_cats': parent_cats
    }
    return render(request, 'marketplace/parent_category_list.html', context)



@api_view(['GET'])
def marketplace_categories_api(request):
    """API для категорий маркетплейса"""
    parent_categories = Category.objects.filter(parent__isnull=True).order_by('name')
    serializer = CategorySerializer(parent_categories, many=True)
    return Response(serializer.data)


def get_descendant_ids(category):
    ids = [category.id]
    for child in category.children.all():
        ids += get_descendant_ids(child)
    return ids
def child_category_list(request, pk):
    """
    Если категория depth=1 -> показываем список детей.
    Если depth >= 2 -> показываем товары (этой и всех вложенных),
    а подкатегории - как "фильтр".
    """
    category = get_object_or_404(Category, pk=pk)

    if category.get_level() < 2 and category.get_children().count() >= 2:
        # Просто список детей
        children = category.children.all().order_by('ordering')
        return render(request, 'marketplace/child_category_list.html', {
            'category': category,
            'children': children
        })
    else:

        return redirect('marketplace:category_products', pk=pk)

@api_view(['GET'])
def child_category_api(request, pk):
    category = get_object_or_404(Category, pk=pk)
    serializer = CategorySerializer(category)
    
    if category.get_level() < 2 and category.get_children().count() >= 2:
        children = category.get_children().order_by('ordering')
        children_serializer = CategorySerializer(children, many=True)
        return Response({
            'category': serializer.data,
            'children': children_serializer.data
        })
    else:
        return Response({
            'should_redirect': True,
            'redirect_to': f'/marketplace/categories/{pk}/products'
        })
    
def category_products(request, pk):
    """
    Показывает товары текущей категории (pk) и всех её вложенных (через get_descendant_ids).
    Также делает фильтрацию и пагинацию.
    """
    category = get_object_or_404(Category, pk=pk)
    ids = get_descendant_ids(category)

    # 1) Берём все товары, относящиеся к этой и вложенным категориям.
    products_qs = Product.objects.filter(category_id__in=ids, on_the_main=True).order_by('-id')

    subcategories = category.children.all().order_by('name')

    # 2) Фильтр по GET-параметрам (пример: по названию товара).
    search_query = request.GET.get('search', '')
    if search_query:
        # Допустим, ищем в поле "name"
        products_qs = products_qs.filter(name__icontains=search_query)

    # Можно добавить другие фильтры. Например, price_min, price_max:
    # price_min = request.GET.get('price_min')
    # if price_min:
    #     products_qs = products_qs.filter(price__gte=price_min)
    #
    # price_max = request.GET.get('price_max')
    # if price_max:
    #     products_qs = products_qs.filter(price__lte=price_max)

    # 3) Пагинация
    page_number = request.GET.get('page', 1)
    paginator = Paginator(products_qs, 12)  # 12 товаров на страницу
    page_obj = paginator.get_page(page_number)

    return render(request, 'marketplace/category_products.html', {
        'category': category,
        'subcategories': subcategories,  # для отображения фильтра
        'page_obj': page_obj,  # передаём страницу вместо products
        'search_query': search_query  # чтобы отобразить в форме поиска
    })


@api_view(['GET'])
def category_products_api(request, pk):
    category = get_object_or_404(Category, pk=pk)
    ids = get_descendant_ids(category)
    
    products_qs = Product.objects.filter(category_id__in=ids, on_the_main=True)
    
    # Фильтрация по названию
    # TODO улучшить поиск
    search_query = request.GET.get('search', '')
    if search_query:
        products_qs = products_qs.filter(name__icontains=search_query)
    
    # Фильтрация по цене
    price_min = request.GET.get('price_min')
    if price_min:
        try:
            products_qs = products_qs.filter(price__gte=float(price_min))
        except ValueError:
            pass
    
    price_max = request.GET.get('price_max')
    if price_max:
        try:
            products_qs = products_qs.filter(price__lte=float(price_max))
        except ValueError:
            pass
    
    # Сортировка
    sort_option = request.GET.get('sort', '-id')
    if sort_option in ['price', '-price', 'name', '-name', '-created_at', '-id']:
        products_qs = products_qs.order_by(sort_option)
    
    # Пагинация
    paginator = Paginator(products_qs, 12)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    serializer = ProductSerializer(page_obj, many=True)
    
    return Response({
        'category': CategorySerializer(category).data,
        'subcategories': CategorySerializer(category.children.all().order_by('name'), many=True).data,
        'products': serializer.data,
        'pagination': {
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        },
        'search_query': search_query,
        'price_min': price_min,
        'price_max': price_max,
        'sort': sort_option
    })

def product_detail(request, pk):
    """
    Отображает подробности товара:
      - Основная информация (название, описание, цена, остаток)
      - Галерея изображений (слайдер)
      - Список атрибутов (например, цвет, материал)
      - Ссылки на категорию и магазин
      - Кнопку "Добавить в корзину"
    """
    product = get_object_or_404(Product, pk=pk)
    images = product.images.all()         # связанные изображения
    attributes = product.attributes.all()   # связанные атрибуты (связь через ProductAttribute)
    same_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:8]



    context = {
        'product': product,
        'images': images,
        'attributes': attributes,
        'same_products': same_products
    }
    return render(request, 'marketplace/product_detail.html', context)



@api_view(['GET'])
def product_detail_api(request, pk):
    product = get_object_or_404(
        Product.objects.prefetch_related('images', 'attributes'),
        pk=pk
    )
    
    # Получаем 4 случайных товара из той же категории
    same_products = Product.objects.filter(
        category=product.category
    ).exclude(id=product.id).order_by('?')[:10]
    
    serializer = ProductSerializer(product, context={'request': request})
    same_products_serializer = ProductSerializer(
        same_products, 
        many=True,
        context={'request': request}
    )
    
    return Response({
        'product': serializer.data,
        'same_products': same_products_serializer.data
    })

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

@login_required()
def business_product_list(request, pk):
    """
    Показывает список товаров, принадлежащих бизнесу с указанным pk.
    """
    if request.user.groups.filter(name='Business').exists():
        business = get_object_or_404(Business, pk=pk, owner=request.user)
        products = business.products.all().order_by('-created_at')
        # 3) Пагинация
        page_number = request.GET.get('page', 1)
        paginator = Paginator(products, 11)  # 12 товаров на страницу
        page_obj = paginator.get_page(page_number)
        context = {
            'edit': True,
            'business': business,
            'products': products,
            'page_obj': page_obj,
        }
        return render(request, 'marketplace/business_product_list.html', context)
    else:
        raise Http404



@login_required
def product_add(request, pk):
    # Предполагаем, что у пользователя есть бизнес (поле owner в Business и related_name='businesses' в User)
    business = get_object_or_404(Business, pk=pk)
    if business.owner != request.user:
        raise Http404

    if request.method == 'POST':
        product_form = ProductForm(request.POST)
        image_form = ProductImageForm(request.POST, request.FILES)
        if product_form.is_valid() and image_form.is_valid():
            product = product_form.save(commit=False)
            product.business = business
            product.save()
            # Если изображение было загружено, сохраняем его
            if image_form.cleaned_data.get('image'):
                new_image = image_form.save(commit=False)
                new_image.product = product
                new_image.save()
            return redirect('marketplace:product_edit', pk=product.id)
    else:
        product_form = ProductForm()
        image_form = ProductImageForm()

    context = {
        'product_form': product_form,
        'image_form': image_form,
        'action': 'Добавление товара',
        'business': business,  # для кнопки "Назад"
    }
    return render(request, 'marketplace/includes/product_add.html', context)

@login_required()
def product_edit(request, pk):
    product = get_object_or_404(Product, id=pk)
    if product.business.owner != request.user:
        raise Http404
    if request.method == "POST":
        # Если нажата кнопка сохранения данных товара
        if 'save_product' in request.POST:
            product_form = ProductForm(request.POST, instance=product)
            image_form = ProductImageForm()  # пустая форма для изображения
            if product_form.is_valid():
                product_form.save()
                return redirect('marketplace:product_edit', pk=product.id)
        # Если нажата кнопка загрузки изображения
        elif 'upload_image' in request.POST:
            product_form = ProductForm(instance=product)  # форма товара для заполнения страницы
            image_form = ProductImageForm(request.POST, request.FILES)
            if image_form.is_valid():
                new_image = image_form.save(commit=False)
                new_image.product = product  # связываем изображение с товаром
                new_image.save()
                return redirect('marketplace:product_edit', pk=product.id)
    else:
        product_form = ProductForm(instance=product)
        image_form = ProductImageForm()

    images = product.images.all()  # получаем изображения, используя related_name 'images'

    context = {
        'product': product,
        'product_form': product_form,
        'image_form': image_form,
        'images': images,
    }
    return render(request, 'marketplace/includes/product_edit.html', context)


@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    # Проверяем, что текущий пользователь является владельцем бизнеса товара
    if product.business.owner != request.user:
        raise Http404("Товар не найден")

    # Можно предусмотреть подтверждение удаления через POST,
    # но для простоты примера удалим товар при GET-запросе.
    product.delete()
    # Перенаправляем пользователя на список товаров бизнеса
    return redirect('marketplace:business_product_list', pk=product.business.id)

@login_required
def product_image_delete(request, image_id):
    image = get_object_or_404(ProductImage, pk=image_id)
    # Проверяем, что владелец товара совпадает с текущим пользователем
    if image.product.business.owner != request.user:
        return HttpResponseForbidden("Доступ запрещен")
    product_id = image.product.id
    image.delete()
    return redirect('marketplace:product_edit', pk=product_id)





