from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import *
from .token_view import (
    CustomTokenRefreshView
)

app_name = 'accounts'

urlpatterns = [
    path('', views.account, name='account'),
    path('register/', views.register, name='register'),
    # path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('my_business/', views.my_business, name='my_business'),
]

# API
urlpatterns.extend([
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/login/', LoginView.as_view(), name='login'),
    path('api/auth/logout/', views.logout_api, name='logout'),
    path('api/account/', views.account_info, name='account-info'),
    path('api/auth/me/', views.me, name='check_auth'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    # path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
])
