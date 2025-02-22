from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

from marketplace import views

app_name = 'marketplace'

urlpatterns = [
    path('', views.home, name='main'),
    # Страница со всеми «родительскими» (корневыми) категориями
    path('categories/', views.parent_category_list, name='parent_category_list'),
    # Страница для конкретной категории — вывод её «детей»
    path('categories/<int:pk>/', views.child_category_list, name='child_category_list'),
    path('categories/<int:pk>/products/', views.category_products, name='category_products'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    # path('dashboard/', views.dashboard, name='dashboard'),
    path('business_product_list/<int:pk>/', views.business_product_list, name='business_product_list'),
    path('product/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('product-image/<int:image_id>/delete/', views.product_image_delete, name='product_image_delete'),
    path('product_/<int:pk>/add/', views.product_add, name='product_add'),
    path('product/<int:pk>/delete/', views.product_delete, name='product_delete'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
