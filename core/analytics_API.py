# analytics_api.py
from datetime import datetime, timedelta, date, timezone as UTC
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import Sum, Count, F
from django.shortcuts import get_object_or_404
from django.utils import timezone, dateparse
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from marketplace.models import Business, Receipt, ProductSale
from accounts.JWT_AUTH import CookieJWTAuthentication
from accounts.permissions import IsBusinessOwner
from django.db.models import Prefetch
from .analytics_serializators import ReceiptDetailSerializer
from rest_framework import status


def _tz_from_request(request) -> ZoneInfo:
    """?tz=Asia/Qyzylorda  → ZoneInfo  (fallback = TIME_ZONE проекта)"""
    tz_name = request.GET.get("tz")
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            pass
    return timezone.get_current_timezone()


def _period(request, user_tz: ZoneInfo) -> tuple[datetime, datetime]:
    """
    Возвращает UTC-границы (start≤t<end).
    Если дат нет — текущий месяц в пользовательском поясе.
    """
    raw_start = request.GET.get("start")
    raw_end = request.GET.get("end")

    if raw_start and raw_end:
        s = dateparse.parse_datetime(raw_start)
        e = dateparse.parse_datetime(raw_end)
        if not (s and e and s.tzinfo and e.tzinfo):
            raise ValueError("start/end must be ISO with TZ, e.g. 2025-07-25T18:59:59Z")
        return s.astimezone(UTC.utc), (e + timedelta(seconds=1)).astimezone(UTC.utc)

    # — дефолт: целый текущий месяц
    now_loc = timezone.localtime(timezone.now(), user_tz)
    first_day = date(now_loc.year, now_loc.month, 1)
    start_loc = datetime.combine(first_day, datetime.min.time(), user_tz)
    end_loc = now_loc + timedelta(seconds=1)
    return start_loc.astimezone(UTC.utc), end_loc.astimezone(UTC.utc)


# analytics_api.py  ─ фрагмент

# … импортов ничего менять не нужно …


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def business_dashboard(request, business_slug):
    business = get_object_or_404(Business, slug=business_slug)
    user_tz = _tz_from_request(request)
    start_utc, end_utc = _period(request, user_tz)

    # ---------------------------- чек-кандидаты
    receipts_qs = (
        Receipt.objects.filter(
            sales__variant__product__business=business,
            created_at__gte=start_utc,
            created_at__lt=end_utc,
            is_deleted=False,
            is_paid=True,
        )
        .distinct()
        .only("number", "total_amount", "created_at", "payment_method")
    )

    # ---------------------------- продажи (для qty)
    sales_qs = ProductSale.objects.filter(
        variant__product__business=business,
        sale_date__gte=start_utc,
        sale_date__lt=end_utc,
        receipt__is_deleted=False,
        is_paid=True,
    ).values("quantity", "sale_date")

    # ---------------------------- totals
    totals = {
        "revenue": receipts_qs.aggregate(s=Sum("total_amount"))["s"] or 0,
        "sales_count": sales_qs.aggregate(c=Sum("quantity"))["c"] or 0,
        "orders": receipts_qs.count(),
    }

    # ---------------------------- заполняем «бакеты» по дням
    buckets: dict[date, dict[str, float | int]] = {}

    # 1. суммы чеков и кол-во чеков
    for r in receipts_qs.values("total_amount", "created_at"):
        day = r["created_at"].astimezone(user_tz).date()
        b = buckets.setdefault(day, {"amount": 0.0, "orders": 0, "variants": 0})
        b["amount"] += float(r["total_amount"])
        b["orders"] += 1

    # 2. количество проданных вариантов
    for s in sales_qs:
        day = s["sale_date"].astimezone(user_tz).date()
        b = buckets.setdefault(day, {"amount": 0.0, "orders": 0, "variants": 0})
        b["variants"] += s["quantity"]

    # ---------------------------- строим непрерывный список для фронта
    chart = []
    d = start_utc.astimezone(user_tz).date()
    last_day = (end_utc - timedelta(seconds=1)).astimezone(user_tz).date()

    while d <= last_day:
        b = buckets.get(d, {"amount": 0.0, "orders": 0, "variants": 0})
        chart.append(
            {
                "date": d.isoformat(),
                "amount": round(b["amount"], 2),
                "orders": b["orders"],
                "variants": b["variants"],
            }
        )
        d += timedelta(days=1)

    # ---------------------------- последние 5 чеков
    transactions = [
        {
            "id": r.id,
            "number": r.number,
            "amount": float(r.total_amount),
            "is_refund": r.total_amount < 0,
            "created_at": r.created_at.astimezone(user_tz).isoformat(),
            "payment_method": r.payment_method.name if r.payment_method else None,
        }
        for r in receipts_qs.order_by("-created_at")[:5]
    ]

    return Response(
        {
            "totals": totals,
            "chart": chart,
            "transactions": transactions,
        }
    )


@api_view(["GET"])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated, IsBusinessOwner])
def receipt_detail(request, business_slug: str, number: str):
    """
    GET /api/business/<slug>/receipts/<number>/

    Возвращает «шапку» чека + все продажи + расширенные данные вариантов
    (см. VariantInReceiptSerializer).
    """

    # --- 1. валидируем бизнес и чек --------------------------------------
    business = get_object_or_404(Business, slug=business_slug)

    receipt = (
        Receipt.objects
        .filter(
            number=number,
            sales__variant__product__business=business,
            is_deleted=False,
        )
        .distinct()                         # ← УБИРАЕТ дубли
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
        .get()                              # теперь одна строка
    )
    # --- 2. строим «map» variant_id → ProductSale ------------------------
    sales_map = {sale.variant_id: sale for sale in receipt.sales.all()}

    # --- 3. сериализуем --------------------------------------------------
    data = ReceiptDetailSerializer(
        receipt,
        context={
            "sales_map": sales_map,  # для VariantInReceiptSerializer
            "receipt": receipt,  # fallback-объект
        },
    ).data

    return Response(data, status=status.HTTP_200_OK)
