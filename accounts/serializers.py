# Обновленный сериализатор
from rest_framework import serializers
from core.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

class UserSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True)  # Пароль
    password2 = serializers.CharField(write_only=True)  # Подтверждение пароля

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password1', 'password2')
        extra_kwargs = {'password1': {'write_only': True}}

    def validate(self, data):
        # Проверка на совпадение паролей
        if data['password1'] != data['password2']:
            raise serializers.ValidationError("Пароли не совпадают")
        
        # Проверка длины пароля
        if len(data['password1']) < 8:
            raise serializers.ValidationError("Пароль должен быть не менее 8 символов")
        
        # Проверка уникальности email
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError("Этот email уже используется")

        # Проверка пароля с использованием встроенных валидаторов
        try:
            validate_password(data['password1'])
        except ValidationError as e:
            #TODO сделать более правильную обработку вывода оишбок прирегистрации
            raise serializers.ValidationError(f"Пароль не соответствует требованиям: {e.messages[0]}") 

        return data

    def create(self, validated_data):
        # Создание пользователя
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password1']
        )
        return user

