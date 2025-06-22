from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import User, Role, BusinessType, Business, BusinessLocation


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "phone")
    search_fields = ("username", "email", "phone")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    filter_horizontal = ("users",)  # Если M2M, удобно иметь фильтр


@admin.register(BusinessType)
class BusinessTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name")


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "business_type", "phone")
    list_filter = ("business_type", "owner")
    search_fields = ("name", "address", "phone")


from django.contrib import admin
from django.utils.html import format_html
from .models import BusinessLocation


@admin.register(BusinessLocation)
class BusinessLocationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "business",
        "location_type_display",
        "address_short",
        "contact_phone",
        "is_active",
        "is_primary",
        "map_link",
    )
    list_filter = ("is_active", "is_primary", "location_type", "business")
    search_fields = ("name", "address", "contact_phone", "business__name")
    list_editable = ("is_active", "is_primary")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "business",
                    "name",
                    "location_type",
                    "is_active",
                    "is_primary",
                )
            },
        ),
        ("Контактные данные", {"fields": ("address", "contact_phone", "description")}),
        (
            "Геоданные и время работы",
            {"fields": ("latitude", "longitude", "opening_hours")},
        ),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    actions = ["activate_locations", "deactivate_locations"]

    def location_type_display(self, obj):
        return obj.get_location_type_display()

    location_type_display.short_description = "Тип локации"

    def address_short(self, obj):
        return obj.address[:50] + "..." if len(obj.address) > 50 else obj.address

    address_short.short_description = "Адрес"

    def map_link(self, obj):
        if obj.latitude and obj.longitude:
            url = f"https://www.google.com/maps?q={obj.latitude},{obj.longitude}"
            return format_html('<a href="{}" target="_blank">🌍 Карта</a>', url)
        return "-"

    map_link.short_description = "Карта"

    @admin.action(description="Активировать выбранные локации")
    def activate_locations(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Деактивировать выбранные локации")
    def deactivate_locations(self, request, queryset):
        queryset.update(is_active=False)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("business")
