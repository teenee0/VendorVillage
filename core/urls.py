from django.conf import settings
from django.conf.urls.static import static

from django.urls import path
from . import views
from . import business_views

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
    # PRODUCT_CRUD
    path('api/business/<slug:business_slug>/products/', business_views.business_products_api, name='business_products_api'),
    path('api/business/<slug:business_slug>/products/<int:product_id>/', business_views.business_product_detail_api, name='business_product_detail_api'),
    path('api/business/<slug:business_slug>/products/<int:product_id>/variants/', business_views.product_variants_api, name='product_variants_api'),
    path('api/business/<slug:business_slug>/products/<int:product_id>/variants/<int:variant_id>/', business_views.product_variant_detail_api, name='product_variant_detail_api'),
    path('api/business/<slug:business_slug>/products/<int:product_id>/images/', business_views.product_images_api, name='product_images_api'),
    path('api/business/<slug:business_slug>/products/<int:product_id>/images/<int:image_id>/', business_views.product_image_detail_api, name='product_image_detail_api'),
    path('api/products/categories/', business_views.product_categories_api, name='product_categories_api'),
    path(
        'api/business/<slug:business_slug>/products/<int:product_id>/attributes/',
        business_views.get_product_attributes,
        name='product-attributes'
    ),
])
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)