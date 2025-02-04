from django import forms
from django.forms import inlineformset_factory
from .models import Product, ProductImage

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        # Выбирайте поля, которые хотите редактировать (например, не редактировать business, created_at и т.д.)
        fields = ['category', 'name', 'description', 'price', 'stock_quantity']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['image']

# Создаем inline formset для ProductImage, чтобы добавить/удалить изображения
ProductImageInlineFormSet = inlineformset_factory(
    Product, ProductImage, form=ProductImageForm,
    extra=1,  # сколько пустых форм по умолчанию
    can_delete=True
)
