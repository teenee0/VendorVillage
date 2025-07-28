from accounts.JWT_AUTH import CookieJWTAuthentication
from accounts.permissions import IsBusinessOwner
from core.models import Business, BusinessLocation, BusinessLocationType
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import (api_view, authentication_classes,
                                       permission_classes)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .settings_serializers import (BusinessLocationSerializer,
                                   BusinessUpdateSerializer)


@api_view(["GET", "PATCH", "PUT"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def business_detail_or_update(request, business_slug):
    try:
        business = Business.objects.get(slug=business_slug, owner=request.user)
    except Business.DoesNotExist:
        return Response({"detail": "Бизнес не найден."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        serializer = BusinessUpdateSerializer(business)
        return Response(serializer.data)

    elif request.method in ["PATCH", "PUT"]:
        serializer = BusinessUpdateSerializer(business, data=request.data, partial=(request.method == "PATCH"))
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def location_type_list(request):
    """
    Возвращает список всех доступных типов локаций.
    """
    types = BusinessLocationType.objects.all().values("id", "code", "name", "is_warehouse", "is_sales_point")
    return Response(types)


@api_view(["GET", "POST"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def business_locations(request, business_slug):
    print(1)
    """
    Получение списка локаций или добавление новой локации для бизнеса.
    """
    try:
        business = Business.objects.get(slug=business_slug, owner=request.user)
    except Business.DoesNotExist:
        return Response({"detail": "Бизнес не найден."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        locations = BusinessLocation.objects.filter(business=business)
        serializer = BusinessLocationSerializer(locations, many=True)
        return Response(serializer.data)

    if request.method == "POST":
        serializer = BusinessLocationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(business=business)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PATCH", "DELETE"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def business_location_detail(request, business_slug, pk):
    """
    Получение, редактирование или удаление одной локации.
    """
    location = get_object_or_404(BusinessLocation, pk=pk, business__owner=request.user)

    if request.method == "GET":
        serializer = BusinessLocationSerializer(location)
        return Response(serializer.data)

    elif request.method == "PATCH":
        serializer = BusinessLocationSerializer(location, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        if location.is_primary:
            return Response({"detail": "Нельзя удалить основную локацию."}, status=status.HTTP_400_BAD_REQUEST)
        location.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
