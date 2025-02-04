from django.conf import settings
from django.conf.urls.static import static

from django.urls import path
from . import views

app_name = 'core'
urlpatterns = [
    path('', views.home, name='main'),
    path('bussiness_categories', views.bussiness_categories_list, name='bussiness_categories_list'),
    path('business/edit/<int:pk>/', views.edit_business, name='edit_business'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)