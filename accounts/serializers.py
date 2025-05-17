from rest_framework import serializers
from core.models import User, Business
from django.utils import timezone

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id', 'name', 'slug', 'business_type', 'description', 
                 'address', 'phone', 'business_logo', 'created_at']

class UserSerializer(serializers.ModelSerializer):
    businesses = BusinessSerializer(many=True, read_only=True)
    date_joined = serializers.SerializerMethodField()
    is_business = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone',
                 'is_active', 'is_business', 'date_joined', 'roles',
                 'businesses', 'first_name', 'last_name']
    
    def get_date_joined(self, obj):
        return obj.date_joined.strftime("%d.%m.%Y")
    
    def get_is_business(self, obj):
        return obj.roles.filter(name='business_owner').exists()
    
    def get_roles(self, obj):
        roles = []
        if obj.is_superuser:
            roles.append('Администратор')
        if obj.is_staff:
            roles.append('Персонал')
        if obj.roles.filter(name='business_owner').exists():
            roles.append('Владелец бизнеса')
        if not roles:
            roles.append('Пользователь')
        return roles