from django.conf import settings
from django.conf.urls.static import static

from django.urls import path
from . import views
from . import business_API
from . import business_product_CRUD_API
from . import sale_product_API
from . import analytics_API
from . import settings_API
from . import receipt_API

app_name = "core"
urlpatterns = [
    path("", views.home, name="main"),
    path(
        "bussiness_categories",
        views.bussiness_categories_list,
        name="bussiness_categories_list",
    ),
    path("business/edit/<int:pk>/", views.edit_business, name="edit_business"),
    path("sites/", views.sites, name="sites"),
    path("site/<slug:slug>/", views.business_site, name="site"),
]
# API
urlpatterns.extend(
    [
        path(
            "api/business-categories/",
            views.business_categories_api,
            name="business_categories_api",
        ),
        # PRODUCT_CRUD
        path(
            "api/business/<slug:business_slug>/products/",
            business_API.business_products_api,
            name="business_products_api",
        ),
        path(
            "api/business/<slug:business_slug>/categories/",
            business_product_CRUD_API.get_business_categories,
            name="business-categories",
        ),
        path(
            "api/categories/<int:category_id>/attributes/",
            business_product_CRUD_API.get_category_attributes,
            name="category-attributes",
        ),
        # path(
        #     "api/business/<slug:business_slug>/locations/",
        #     business_product_CRUD_API.get_business_locations,
        #     name="business-locations",
        # ),
        path(
            "api/business/<slug:business_slug>/products/create/",
            business_product_CRUD_API.create_product,
            name="create-product",
        ),
        path(
            "api/business/<slug:business_slug>/products/<int:product_id>/",
            business_product_CRUD_API.get_product,
            name="detail-product",
        ),
        path(
            "api/business/<slug:business_slug>/products/<int:product_id>/info",
            business_API.get_info_product,
            name="info-product",
        ),
        path(
            "api/business/<slug:business_slug>/products/<int:product_id>/edit",
            business_product_CRUD_API.edit_product,
            name="edit-product",
        ),
        path(
            "api/business/<slug:business_slug>/products/<int:product_id>/delete",
            business_product_CRUD_API.delete_product,
            name="delete-product",
        ),
        path(
            "api/business/<slug:business_slug>/products/<int:product_id>/toggle-status/",
            business_product_CRUD_API.toggle_status_product,
            name="toggle-status-product",
        ),
        # Брак
        path(
            "api/business/<slug:business_slug>/stocks/<int:stock_id>/defects/create/",
            business_product_CRUD_API.create_stock_defect,
            name="create-stock-defect",
        ),
        path(
            "api/business/<slug:business_slug>/stocks/<int:defect_id>/defects/remove/",
            business_product_CRUD_API.remove_stock_defect,
            name="remove-stock-defect",
        ),
        # Резерв
        path(
            "api/business/<slug:business_slug>/stocks/<int:stock_id>/reserve/",
            business_product_CRUD_API.reserve_stock,
            name="reserve-stock",
        ),
        path(
            "api/business/<slug:business_slug>/stocks/<int:stock_id>/reserve/remove/",
            business_product_CRUD_API.remove_stock_reserve,
            name="remove-stock-reserve",
        ),
        # Продажа
        path(
            "api/business/<slug:business_slug>/sales-products/",
            sale_product_API.sales_products_api,
            name="sales_products_api",
        ),
        path(
            "api/business/<slug:business_slug>/create-receipt/",
            sale_product_API.create_receipt,
            name="create-receipt",
        ),
        path(
            "api/business/payment-methods/",
            sale_product_API.get_active_payment_methods,
            name="payment-methods",
        ),
        path(
            "api/business/<slug:business_slug>/dashboard/",
            analytics_API.business_dashboard,
            name="business-dashboard",
        ),
        # path(
        #     "api/business/<slug:business_slug>/receipts-in-analitycs/<str:number>/", # надо переделать в одно апи для чеков
        #     analytics_API.receipt_detail,
        #     name="receipt-detail",
        # ),
        path(
            "api/business/<slug:business_slug>/settings/",
            settings_API.business_detail_or_update,
            name="business-detail-or-update",
        ),
        path(
            "api/business/<slug:business_slug>/locations/",
            settings_API.business_locations,
            name="business-location-list-create",
        ),
        path(
            "api/business/<slug:business_slug>/locations/<int:pk>/",
            settings_API.business_location_detail,
            name="business-location-detail",
        ),
        path(
            "api/location-types/",
            settings_API.location_type_list,
            name="location-type-list",
        ),
        path(
            "api/business/<slug:business_slug>/receipts/",
            receipt_API.receipt_list,
            name="receipt-list",
        ),
        path(
            "api/business/<slug:business_slug>/receipts/<int:receipt_id>/",
            receipt_API.receipt_detail,
            name="receipt-detail",
        ),
        path(
            "api/business/<slug:business_slug>/receipts/history/",
            receipt_API.grouped_receipt_history,
            name="receipt-history",
        ),
        # path('api/business/<slug:business_slug>/products/<int:product_id>/variants/<int:variant_id>/', business_API.product_variant_detail_api, name='product_variant_detail_api'),
        # path('api/business/<slug:business_slug>/products/<int:product_id>/images/', business_API.product_images_api, name='product_images_api'),
        # path('api/business/<slug:business_slug>/products/<int:product_id>/images/<int:image_id>/', business_API.product_image_detail_api, name='product_image_detail_api'),
        # path('api/products/categories/', business_API.product_categories_api, name='product_categories_api'),
        # path(
        #     'api/business/<slug:business_slug>/products/<int:product_id>/attributes/',
        #     business_API.get_product_attributes,
        #     name='product-attributes'
        # ),
        path(
            "debug/receipt/<int:receipt_id>/html/",
            views.business_check,
            name="receipt-preview",
        ),
    ]
)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
