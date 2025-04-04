from django import forms
from django.contrib.auth.forms import UserCreationForm
from core.models import User

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Обязательное поле. Введите корректный адрес электронной почты.")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
