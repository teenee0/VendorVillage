from django.shortcuts import get_object_or_404
from rest_framework import permissions
from core.models import Business


class IsBusinessOwner(permissions.BasePermission):
    def has_permission(self, request, view):
        business_slug = view.kwargs.get('business_slug')
        business = get_object_or_404(Business, slug=business_slug)
        return business.owner == request.user
