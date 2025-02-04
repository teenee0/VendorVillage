from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import User, Role, BusinessType, Business

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'email', 'phone')
    search_fields = ('username', 'email', 'phone')

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    filter_horizontal = ('users',)  # Если M2M, удобно иметь фильтр

@admin.register(BusinessType)
class BusinessTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'owner', 'business_type', 'phone')
    list_filter = ('business_type', 'owner')
    search_fields = ('name', 'address', 'phone')
