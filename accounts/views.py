

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from django.http import Http404
from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout

from accounts.forms import RegistrationForm
@login_required
def account(request):
    user = request.user
    business_status = request.user.groups.filter(name='Business').exists()
    context = {'user': user,
               'business_status': business_status}
    return render(request, 'accounts/account.html', context)
@login_required
def my_business(request):
    if request.user.groups.filter(name='Business').exists():
        user_businesses = request.user.businesses.all()
        context = {'user_businesses': user_businesses}
        return render(request, 'accounts/businesses.html', context)
    else:
        raise Http404

def logout_view(request):
    logout(request)
    return redirect('/')

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('accounts:account')
    else:
        form = RegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})
