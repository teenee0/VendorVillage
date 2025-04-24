from django.shortcuts import render, redirect, get_object_or_404, reverse
from .models import Category

category = get_object_or_404(Category, pk=25)
print(category)