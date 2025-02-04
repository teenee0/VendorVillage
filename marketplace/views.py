from django.core.paginator import Paginator
from django.http import Http404

from marketplace.models import Category
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from marketplace.forms import ProductForm, ProductImageInlineFormSet
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

    if category.get_level() < 2:
        # Просто список детей
        children = category.children.all().order_by('ordering')
        return render(request, 'marketplace/child_category_list.html', {
            'category': category,
            'children': children
        })
    else:
        print(1)
        return redirect('marketplace:category_products', pk=pk)


def category_products(request, pk):
    """
    Показывает товары текущей категории (pk) и всех её вложенных (через get_descendant_ids).
    Также делает фильтрацию и пагинацию.
    """
    category = get_object_or_404(Category, pk=pk)
    ids = get_descendant_ids(category)

    # 1) Берём все товары, относящиеся к этой и вложенным категориям.
    products_qs = Product.objects.filter(category_id__in=ids).order_by('-id')

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
        products = business.products.all()
        # 3) Пагинация
        page_number = request.GET.get('page', 1)
        paginator = Paginator(products, 12)  # 12 товаров на страницу
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
def product_create(request, pk):
    # Получаем бизнес текущего пользователя (предполагаем, что у пользователя есть бизнес)
    business = get_object_or_404(Business, pk=pk, owner=request.user)
    if not business:
        # Если бизнеса нет, можно перенаправить на страницу создания бизнеса
        return render('account:login')
    context = {'business': business}
    if request.method == 'POST':
        form = ProductForm(request.POST)
        formset = ProductImageInlineFormSet(request.POST, request.FILES)
        if form.is_valid() and formset.is_valid():
            product = form.save(commit=False)
            product.business = business
            product.save()
            formset.instance = product
            formset.save()
            return redirect('marketplace:product_detail', pk=product.id)
    else:
        form = ProductForm()
        formset = ProductImageInlineFormSet(queryset=ProductImage.objects.none())
    context.update({'form': form, 'formset': formset, 'action': 'Добавление товара'})
    return render(request, 'marketplace/includes/product_form.html', context)


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    # Проверяем, что текущий пользователь является владельцем бизнеса данного товара
    if product.business.owner != request.user:
        return redirect('marketplace:product_detail', pk=product.id)  # или вернуть ошибку 403

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        formset = ProductImageInlineFormSet(request.POST, request.FILES, instance=product)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('marketplace:product_detail', pk=product.id)
    else:
        form = ProductForm(instance=product)
        formset = ProductImageInlineFormSet(instance=product)
    return render(request, 'marketplace/includes/product_form.html',
                  {'form': form, 'formset': formset, 'action': 'Редактирование товара'})





