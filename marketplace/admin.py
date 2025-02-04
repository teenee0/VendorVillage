from django.contrib import admin
from mptt.admin import MPTTModelAdmin

from .models import (
    Category,
    Product,
    ProductImage,
    Attribute,
    CategoryAttribute,
    ProductAttribute
)

@admin.register(Category)
class CategoryAdmin(MPTTModelAdmin):  # Наследуемся от MPTTModelAdmin
    list_display = ('id', 'name', 'parent', 'level', 'page_identificator')
    search_fields = ('name',)
    list_filter = ('parent',)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1



class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'business', 'price', 'stock_quantity')
    list_filter = ('business', 'category')
    search_fields = ('name', 'description')
    inlines = [ProductImageInline, ProductAttributeInline]

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'image', 'created_at')


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(CategoryAttribute)
class CategoryAttributeAdmin(admin.ModelAdmin):
    list_display = ('category', 'attribute', 'required')
    list_filter = ('category', 'required')
    search_fields = ('category__name', 'attribute__name')
