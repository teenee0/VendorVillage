from django.conf import settings
from django.conf.urls.static import static

from django.urls import path
from . import views
from . import business_API
from . import business_product_CRUD_API

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
    path('api/business/<slug:business_slug>/products/', business_API.business_products_api, name='business_products_api'),
    path('api/business/<slug:business_slug>/categories/', business_product_CRUD_API.get_business_categories, name='business-categories'),
    path('api/categories/<int:category_id>/attributes/', business_product_CRUD_API.get_category_attributes, name='category-attributes'),
    path('api/business/<slug:business_slug>/locations/', business_product_CRUD_API.get_business_locations, name='business-locations'),
    path('api/business/<slug:business_slug>/products/create/', business_product_CRUD_API.create_product, name='create-product'),
    # path('api/business/<slug:business_slug>/products/<int:product_id>/variants/', business_API.product_variants_api, name='product_variants_api'),
    # path('api/business/<slug:business_slug>/products/<int:product_id>/variants/<int:variant_id>/', business_API.product_variant_detail_api, name='product_variant_detail_api'),
    # path('api/business/<slug:business_slug>/products/<int:product_id>/images/', business_API.product_images_api, name='product_images_api'),
    # path('api/business/<slug:business_slug>/products/<int:product_id>/images/<int:image_id>/', business_API.product_image_detail_api, name='product_image_detail_api'),
    # path('api/products/categories/', business_API.product_categories_api, name='product_categories_api'),
    # path(
    #     'api/business/<slug:business_slug>/products/<int:product_id>/attributes/',
    #     business_API.get_product_attributes,
    #     name='product-attributes'
    # ),
])
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)