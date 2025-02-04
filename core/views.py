from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
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

