from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import (
    Restaurant, MenuCategory, MenuItem,
    RestaurantOrder, RestaurantOrderItem, TableReservation
)

@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'cuisine_type', 'opening_hours', 'capacity', 'liquor_license')
    search_fields = ('business__name', 'cuisine_type')

@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'restaurant')
    list_filter = ('restaurant',)
    search_fields = ('name', 'description')

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category', 'price', 'is_available')
    list_filter = ('category', 'is_available')
    search_fields = ('name', 'description')

class RestaurantOrderItemInline(admin.TabularInline):
    model = RestaurantOrderItem
    extra = 0

@admin.register(RestaurantOrder)
class RestaurantOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'restaurant', 'status', 'total_amount', 'created_at')
    list_filter = ('restaurant', 'status')
    search_fields = ('user__username',)
    inlines = [RestaurantOrderItemInline]

@admin.register(RestaurantOrderItem)
class RestaurantOrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'menu_item', 'quantity', 'price_per_unit', 'subtotal')

@admin.register(TableReservation)
class TableReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'restaurant', 'reservation_date', 'status')
    list_filter = ('restaurant', 'status')
    search_fields = ('user__username', 'table_number')
