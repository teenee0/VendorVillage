from django.conf import settings
from django.conf.urls.static import static

from django.urls import path
from . import views

app_name = 'core'
urlpatterns = [
    path('', views.home, name='main'),

    path('bussiness_categories', views.bussiness_categories_list, name='bussiness_categories_list'),
    path('business/edit/<int:pk>/', views.edit_business, name='edit_business'),
    path('sites/', views.sites, name='sites'),
    path('site/<slug:slug>/', views.business_site, name='site'),
]
# API
urlpatterns.extend([
    path('api/business-categories/', views.business_categories_api, name='business_categories_api'),
])
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)