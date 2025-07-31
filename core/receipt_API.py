from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from rest_framework.response import Response
from marketplace.models import Receipt, ProductSale
from accounts.JWT_AUTH import CookieJWTAuthentication
from accounts.permissions import IsBusinessOwner
from core.models import Business
from django.shortcuts import get_object_or_404
from rest_framework.decorators import (api_view, authentication_classes,
                                       permission_classes)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .analytics_serializators import ReceiptDetailSerializer, ReceiptListSerializer
from django.db.models import Prefetch
from rest_framework import status
from datetime import datetime
from django.utils.dateparse import parse_datetime


def paginate_receipts(request, queryset=None, quantity=12):
    """
    Возвращает чеков по страницам (например, для бесконечной прокрутки).
    """
    if queryset is None:
        queryset = Receipt.objects.all()

    per_page = int(request.GET.get("per_page", quantity))
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    serialized = ReceiptListSerializer(page_obj, many=True)

    pagination = {
        "current_page": page_obj.number,
        "total_pages": paginator.num_pages,
        "total_items": paginator.count,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
        "per_page": per_page,
    }

    return serialized.data, pagination


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def receipt_list(request, business_slug):
    """
    GET /api/business/<slug>/receipts/?start=<ISO8601>&end=<ISO8601>
    Список чеков с фильтрацией по диапазону даты и времени и пагинацией
    """
    business = get_object_or_404(Business, slug=business_slug)

    receipts = (
        Receipt.objects
        .filter(sales__variant__product__business=business)
        .filter(is_deleted=False)
        .select_related("payment_method")
        .distinct()
    )

    # Фильтрация по диапазону времени
    start_param = request.GET.get("start")
    end_param = request.GET.get("end")

    try:
        if start_param:
            start_datetime = parse_datetime(start_param)
            if start_datetime:
                receipts = receipts.filter(created_at__gte=start_datetime)

        if end_param:
            end_datetime = parse_datetime(end_param)
            if end_datetime:
                receipts = receipts.filter(created_at__lte=end_datetime)
    except Exception as e:
        return Response({"error": "Некорректные параметры времени"}, status=400)

    receipts = receipts.order_by("-created_at")

    data, pagination = paginate_receipts(request, receipts, quantity=12)

    return Response({
        "results": data,
        "pagination": pagination,
    })



@api_view(["GET", "DELETE"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def receipt_detail(request, business_slug: str, receipt_id: int):
    """
    GET /api/business/<slug>/receipts/<id>/
    DELETE /api/business/<slug>/receipts/<id>/

    Просмотр или удаление чека (если принадлежит бизнесу пользователя)
    """
    business = get_object_or_404(Business, slug=business_slug)

    if business.owner != request.user:
        return Response({"detail": "У вас нет доступа к этому бизнесу."}, status=status.HTTP_403_FORBIDDEN)

    receipt = (
        Receipt.objects
        .filter(id=receipt_id, sales__variant__product__business=business)
        .distinct()
        .select_related("payment_method")
        .prefetch_related(
            Prefetch(
                "sales",
                queryset=ProductSale.objects
                    .select_related("variant__product")
                    .prefetch_related(
                        "variant__product__images",
                        "variant__attributes__category_attribute__attribute",
                        "variant__stocks",
                    ),
            )
        )
        .first()
    )

    if not receipt:
        return Response({"detail": "Чек не найден."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        from simple_history.utils import update_change_reason

        # 1. Указываем пользователя, от имени которого фиксируем изменение
        receipt._history_user = request.user

        # 2. Указываем причину изменения
        update_change_reason(receipt, "Удаление чека через API")

        # 3. Сохраняем, чтобы зафиксировать в истории
        receipt.save()

        # 4. Теперь удаляем сам объект
        receipt.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    sales_map = {sale.variant_id: sale for sale in receipt.sales.all()}

    data = ReceiptDetailSerializer(
        receipt,
        context={
            "sales_map": sales_map,
            "receipt": receipt,
        },
    ).data

    return Response(data)


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def grouped_receipt_history(request, business_slug):
    business = get_object_or_404(Business, slug=business_slug)

    receipt_ids = (
        ProductSale.objects
        .filter(variant__product__business=business, receipt__isnull=False)
        .values_list("receipt_id", flat=True)
        .distinct()
    )

    # Получаем активные (не удалённые) и soft-deleted чеки
    receipts = Receipt.objects.filter(id__in=receipt_ids)
    receipt_map = {
        receipt.id: ReceiptListSerializer(receipt).data
        for receipt in receipts
    }

    history_qs = (
        Receipt.history
        .filter(id__in=receipt_ids)
        .order_by("history_date")
    )

    # Группировка и диффы
    history_grouped = {}
    prev_state = {}

    for entry in history_qs:
        rid = entry.id
        changes = {}

        if rid in prev_state:
            prev = prev_state[rid]
            for field in ["total_amount", "discount_amount", "discount_percent", "is_deleted"]:
                old = getattr(prev, field, None)
                new = getattr(entry, field, None)
                if old != new:
                    changes[field] = {
                        "from": str(old),
                        "to": str(new)
                    }

        prev_state[rid] = entry

        if rid not in history_grouped:
            history_grouped[rid] = []

        history_grouped[rid].append({
            "type": entry.history_type,
            "date": entry.history_date,
            "user": str(entry.history_user) if entry.history_user else None,
            "is_deleted": entry.is_deleted,
            "total_amount": str(entry.total_amount),
            "discount_percent": float(entry.discount_percent),
            "discount_amount": float(entry.discount_amount),
            "changes": changes
        })

    # Объединяем данные: чек + история
    grouped_data = []
    for rid, history in history_grouped.items():
        receipt_data = receipt_map.get(rid, {"receipt_id": rid, "deleted": True})
        grouped_data.append({
            "receipt": receipt_data,
            "history": history
        })

    # Пагинация
    per_page = int(request.GET.get("per_page", 10))
    page_number = request.GET.get("page", 1)
    paginator = Paginator(grouped_data, per_page)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    pagination = {
        "current_page": page_obj.number,
        "total_pages": paginator.num_pages,
        "total_items": paginator.count,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
        "per_page": per_page,
    }

    return Response({
        "results": page_obj.object_list,
        "pagination": pagination,
    })
