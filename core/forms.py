from django import forms
from core.models import Business

class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ['name', 'description', 'address', 'phone']
        # Поля подберите в соответствии с вашей моделью.
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
