import os
from django.conf import settings
from weasyprint import HTML, CSS
from django.template import Template, Context
from django.utils import timezone
from django.core.files.base import ContentFile
import io
from pdf2image import (
    convert_from_bytes,
)  # используем from_bytes чтобы не писать файл на диск
from VendorVillage.settings import POPPLER_PATH
from jinja2 import Environment
from decimal import Decimal

def truncate(s, length=255, killwords=False):
    return s[:length] + ("..." if len(s) > length and not killwords else "")


env = Environment()
env.filters["truncate"] = truncate


def generate_receipt_pdf(receipt_id, save=True, test_mode=False):
    """
    Генерирует PDF для чека и сохраняет в FileField (Receipt.receipt_pdf_file).
    Также генерирует превью (receipt_preview_image) для этого чека.
    :param receipt_id: id чека
    :param save: если True — сохранить файл в pdf_file и превью, иначе вернуть bytes
    :return: путь к PDF файлу или bytes
    """
    from marketplace.models import Receipt  # твой импорт модели

    try:
        receipt = (
            Receipt.objects.select_related("payment_method", "customer")
            .prefetch_related(
                "sales__variant__product__business",  # подтягиваем бизнес через variant->product
                "sales__location",
                "sales__variant",
            )
            .get(pk=receipt_id)
        )
    except Receipt.DoesNotExist:
        raise ValueError("Чек не найден")

    # Получаем бизнес через первую продажу (если чек пустой — ошибка)
    first_sale = receipt.sales.select_related("variant__product__business").first()
    if not first_sale:
        raise ValueError("В чеке нет продаж!")
    business = first_sale.variant.product.business

    # Используем кастомные или дефолтные шаблоны
    html_tpl = business.receipt_html_template or DEFAULT_RECEIPT_HTML
    css_tpl = business.receipt_css_template or DEFAULT_RECEIPT_CSS

    original_total = Decimal("0")      # сумма всех товаров по оригинальной цене
    final_total = Decimal("0")         # сумма после всех скидок, кроме скидки на чек

    for s in receipt.sales.select_related("variant"):
        variant_base_price = Decimal(str(s.variant.price or 0))  # начальная цена
        qty = s.quantity

        # ---- Оригинальная цена ----
        original_total += variant_base_price * qty

        # ---- Считаем скидки на единицу ----
        orig_discount_unit = Decimal("0")
        if s.variant.discount:
            orig_discount_unit += variant_base_price * Decimal(str(s.variant.discount)) / 100
        if getattr(s, "orig_discount_amount", 0):
            orig_discount_unit += Decimal(str(s.orig_discount_amount))

        # Цена после оригинальной скидки
        after_orig = variant_base_price - orig_discount_unit

        # Скидка по товару (item-level)
        item_discount_unit = after_orig * Decimal(str(s.discount_percent)) / 100
        item_discount_unit += Decimal(str(s.discount_amount))

        # Конечная цена за единицу
        final_unit_price = after_orig - item_discount_unit

        # ---- Добавляем к финальной сумме ----
        final_total += final_unit_price * qty

    # Разница = общая скидка (без учёта скидки на чек)
    total_discount = original_total - final_total

    receipt_percent_discount = final_total * Decimal(str(receipt.discount_percent)) / 100
    receipt_fixed_discount = Decimal(str(receipt.discount_amount))
    receipt_discount_total = receipt_percent_discount + receipt_fixed_discount

    context = {
        "receipt": receipt,
        "business": business,
        "sales": list(receipt.sales.select_related("variant", "location").prefetch_related("variant__attributes__category_attribute__attribute", "variant__attributes__predefined_value")),
        "now": timezone.now(),
        "customer": receipt.customer,
        "total_discount": Decimal(total_discount),
        "price_without_any_discounts": Decimal(original_total),
        "receipt_discount": receipt_discount_total,
    }

    if test_mode:
        return context, html_tpl

    # Рендерим HTML шаблон через Jinja2
    from jinja2 import Template as JinjaTemplate

    html_rendered = JinjaTemplate(html_tpl).render(**context)

    full_html = f"""
    <html>
    <head>
      <meta charset="utf-8">
      <style>{css_tpl}</style>
    </head>
    <body>
      {html_rendered}
    </body>
    </html>
    """

    # Генерируем PDF в bytes
    pdf_bytes = HTML(string=full_html, base_url=settings.MEDIA_ROOT).write_pdf(
        stylesheets=[CSS(string=css_tpl)]
    )

    if save:
        # Сохраняем PDF-файл
        filename = f"{receipt.number}.pdf"
        receipt.receipt_pdf_file.save(
            filename, ContentFile(pdf_bytes), save=False
        )  # save=False чтобы не обновлять updated_at

        # Генерируем превью (jpg/png) с первой страницы PDF
        try:
            # convert_from_bytes возвращает список PIL.Image
            images = convert_from_bytes(
                pdf_bytes, first_page=1, last_page=1, dpi=170, poppler_path=POPPLER_PATH
            )
            if images:
                img_io = io.BytesIO()
                images[0].save(img_io, "PNG", quality=85)
                img_io.seek(0)
                preview_filename = f"{receipt.number}_preview.png"
                receipt.receipt_preview_image.save(
                    preview_filename, ContentFile(img_io.read()), save=False
                )
        except Exception as e:
            print(os.path.exists(r"C:\poppler-24.08.0\Library\bin\pdftoppm.exe"))
            print("Ошибка генерации превью:", e)

        receipt.save(update_fields=["receipt_pdf_file", "receipt_preview_image"])
        return receipt.receipt_pdf_file.path
    else:
        return pdf_bytes


# --------- Пример дефолтных шаблонов ---------
DEFAULT_RECEIPT_HTML = """

<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
  @page {
    size: 58mm 210mm;
    margin: 0;
    padding: 0;
  }

  body {
    width: 57mm;
    margin: 0 auto;
    font-family: "Arial", sans-serif;
    font-size: 12pt;
    line-height: 1.5;
    color: #000;
  }

  .header {
    text-align: center;
    margin-bottom: 3mm;
  }

  .receipt-number {
    font-weight: bold;
    font-size: 14pt;
  }

  .receipt-date {
    font-size: 11pt;
    margin-bottom: 3mm;
  }

  .item-section {
    margin-bottom: 4mm;
  }

  .item-name {
    font-weight: bold;
    font-size: 12pt;
    margin-bottom: 1.5mm;
  }

  .item-attribute {
    margin-left: 2mm;
    font-size: 11pt;
  }

  .item-row {
    display: flex;
    justify-content: space-between;
    margin: 1.5mm 0;
    font-size: 12pt;
  }

  .discount-row {
    display: flex;
    justify-content: space-between;
    margin-left: 5mm;
    font-size: 11pt;
    color: #000;
  }

  .item-total {
    font-weight: bold;
    text-align: right;
    margin: 2mm 0 2.5mm;
    border-top: 1px dashed #000;
    padding-top: 1mm;
    font-size: 12pt;
  }

  .divider {
    border-top: 1px dashed #000;
    margin: 3mm 0;
  }

  .summary-section {
    margin-top: 4mm;
  }

  .summary-row {
    display: flex;
    justify-content: space-between;
    margin: 1.5mm 0;
    font-size: 12pt;
  }

  .final-total {
    font-weight: bold;
    font-size: 14pt;
    margin-top: 3mm;
    border-top: 1px solid #000;
    padding-top: 2mm;
  }

  .thank-you {
    text-align: center;
    margin-top: 4mm;
    font-style: italic;
    font-size: 12pt;
  }
</style>

</head>
<body>
  <div class="header">
    <div class="receipt-number">Чек #{{ receipt.number }}</div>
    <div class="receipt-date">{{ now.strftime("%d.%m.%Y, %H:%M:%S") }}</div>
  </div>

  {% for sale in sales %}
    <div class="item-section">
      <div class="item-name">{{ sale.variant.name }}</div>
      
      <!-- Изменено: используем variant.price вместо sale.price_per_unit -->
      <div class="item-row">
        <span>{{ sale.quantity }} × {{ "%.0f"|format(sale.variant.price|float) }} ₸</span>
        <span>{{ "%.0f"|format((sale.variant.price * sale.quantity)|float) }} ₸</span>
      </div>
      
      {% if sale.discount_percent or sale.discount_amount or sale.variant.discount %}
        <div class="discount-row">
          <span>
            {% if sale.variant.discount %}Скидка {{ sale.variant.discount }}%{% endif %}
            {% if sale.discount_percent %}
              {% if sale.variant.discount %}+{% else %}Скидка{% endif %}
              {{ sale.discount_percent }}%
            {% endif %}
            {% if sale.discount_amount %}
              {% if sale.variant.discount or sale.discount_percent %}+{% else %}Скидка{% endif %}
              {{ "%.0f"|format(sale.discount_amount|float) }} ₸
            {% endif %}
          </span>
          <span>
            -{{ "%.0f"|format(
              (sale.variant.price * sale.quantity * sale.variant.discount / 100 if sale.variant.discount else 0) +
              (sale.variant.price * sale.quantity * sale.discount_percent / 100 if sale.discount_percent else 0) +
              (sale.discount_amount if sale.discount_amount else 0)
            ) }}&nbsp;₸
          </span>
        </div>
      {% endif %}
      
      <div class="item-total">Итого за товар: {{ "%.0f"|format(sale.total_price|float) }} ₸</div>
      
      {% if not loop.last %}
        <div class="divider"></div>
      {% endif %}
    </div>
  {% endfor %}

  <div class="divider"></div>
  
  <div class="summary-section">
    <div class="summary-row">
      <span>Товары:</span>
      <span>{{ "%.0f"|format(price_without_any_discounts|float) }} ₸</span>
    </div>
    
    <div class="summary-row">
      <span>Скидка на товары:</span>
      <span>-{{ "%.0f"|format(total_discount|float) }} ₸</span>
    </div>

    {% if receipt.discount_percent %}
        <div class="summary-row">
            <span>Скидка на чек:</span>
            <span>
            -{{ "%.0f"|format(receipt.discount_percent|float) }}%
            ({{ "%.0f"|format(receipt_discount|float) }} ₸)
            </span>
        </div>
        {% elif receipt.discount_amount %}
        <div class="summary-row">
            <span>Скидка на чек:</span>
            <span>-{{ "%.0f"|format(receipt_discount|float) }} ₸</span>
        </div>
    {% endif %}

    
    <div class="final-total">
      <span>Итого к оплате:</span>
      <span>{{ "%.0f"|format(receipt.total_amount|float) }}&nbsp;₸</span>
    </div>
  </div>
  <div class="summary-row">
    <span>Способ оплаты:</span>
    <span>{{ receipt.payment_method.name }}</span>
 </div>
  
  <div class="thank-you">Спасибо за покупку!</div>
</body>
</html>

"""

DEFAULT_RECEIPT_CSS = """

"""
