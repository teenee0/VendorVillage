from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from django.utils.html import format_html

from .models import (
    Category,
    Product,
    ProductVariant,
    Attribute,
    AttributeValue,
    CategoryAttribute,
    ProductVariantAttribute,
    ProductImage,  # Новая модель
    ProductStock,
    ProductDefect
)


@admin.register(Category)
class CategoryAdmin(MPTTModelAdmin):
    list_display = ("name", "parent", "ordering")
    search_fields = ("name",)
    ordering = ("tree_id", "lft")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "is_main", "alt_text", "display_order")


class ProductVariantAttributeInline(admin.TabularInline):
    model = ProductVariantAttribute
    extra = 1


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("product", "sku", "price", "discount")
    inlines = [ProductVariantAttributeInline]
    search_fields = ("sku", "product__name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "business",
        "category",
        "is_visible_on_marketplace",
        "is_visible_on_own_site",
        "image_count",
    )
    search_fields = ("name",)
    list_filter = ("business", "category", "is_visible_on_marketplace", "is_visible_on_own_site")
    inlines = [ProductImageInline]

    def image_count(self, obj):
        return obj.images.count()

    image_count.short_description = "Кол-во изображений"


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ("name", "has_predefined_values")
    search_fields = ("name",)


@admin.register(AttributeValue)
class AttributeValueAdmin(admin.ModelAdmin):
    list_display = ("attribute", "value")
    search_fields = ("value",)
    list_filter = ("attribute",)


@admin.register(CategoryAttribute)
class CategoryAttributeAdmin(admin.ModelAdmin):
    list_display = ("category", "attribute", "required", "show_attribute_at_right")
    list_filter = ("category", "attribute", "required", "show_attribute_at_right")


@admin.register(ProductVariantAttribute)
class ProductVariantAttributeAdmin(admin.ModelAdmin):
    list_display = ("variant", "category_attribute", "predefined_value", "custom_value")
    list_filter = ("category_attribute__attribute",)


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "image_preview", "is_main", "display_order")
    list_filter = ("is_main", "product__category")
    search_fields = ("product__name",)
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        return (
            format_html('<img src="{}" height="50" />', obj.image.url)
            if obj.image
            else "-"
        )

    image_preview.short_description = "Превью"


@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    list_display = (
        "variant",
        "location",
        "quantity",
        "reserved_quantity",
        "defect_quantity",
        "available_quantity",
        "is_available_for_sale",
        "last_updated",
    )
    list_filter = ("is_available_for_sale", "location")
    search_fields = ("variant__name", "variant__sku", "location__name")
    list_editable = ("is_available_for_sale",)
    readonly_fields = ("available_quantity", "last_updated", "defect_quantity")
    fieldsets = (
        (None, {"fields": ("variant", "location")}),
        ("Количества", {"fields": ("quantity", "reserved_quantity", "available_quantity", "defect_quantity")}),
        ("Настройки", {"fields": ("is_available_for_sale", "last_updated")}),
    )

    def available_quantity(self, obj):
        return obj.available_quantity

    available_quantity.short_description = "Доступное количество"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("variant", "location")


@admin.register(ProductDefect)
class ProductDefectAdmin(admin.ModelAdmin):
    list_display = ("stock", "quantity", "reason", "created_at")

