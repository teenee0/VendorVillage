from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from marketplace.models import Product
from .forms import BusinessForm
from core.models import Business
from core.models import BusinessType


# Create your views here.
def home(request):
    return render(request, 'home.html')

def bussiness_categories_list(request):
    business_types = BusinessType.objects.all()
    context = {
        'business_types': business_types
    }
    return render(request, 'core/bussiness_list.html', context)

def business_site(request, slug):
    business = get_object_or_404(Business, slug=slug)
    products = business.products.all()
    print(business.html_template)
    if business.html_template:
        print(business.html_template)
        page_number = request.GET.get('page', 1)
        paginator = Paginator(products, 12)  # 12 товаров на страницу
        page_obj = paginator.get_page(page_number)
        template = business.html_template
        return render(request, str(template),
                      {'business': business,
                       'page_obj': page_obj,})
    return render(request, 'business_defaults/business_default_page.html', {'business': business, 'products': products})





@login_required
def edit_business(request, pk):
    if request.user.groups.filter(name='Business').exists():
        business = get_object_or_404(Business, pk=pk, owner=request.user)

        if request.method == 'POST':
            form = BusinessForm(request.POST, request.FILES, instance=business)
            if form.is_valid():
                form.save()
                return redirect('accounts:my_business')
        else:
            form = BusinessForm(instance=business)
        context = {'form': form, 'business': business}
        return render(request, 'core/edit_business.html', context)
    else:
        raise Http404


def sites(request):
    businesses = Business.objects.all()
    context = {'businesses': businesses}
    return render(request,'core/businesses.html', context)