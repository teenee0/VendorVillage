import os
from django.conf import settings
from weasyprint import HTML, CSS
from django.template import Template, Context
from django.utils import timezone
from django.core.files.base import ContentFile
import io
from pdf2image import convert_from_bytes  # используем from_bytes чтобы не писать файл на диск
from VendorVillage.settings import POPPLER_PATH
from jinja2 import Environment

def truncate(s, length=255, killwords=False):
    return s[:length] + ('...' if len(s) > length and not killwords else '')

env = Environment()
env.filters['truncate'] = truncate

def generate_receipt_pdf(receipt_id, save=True):
    """
    Генерирует PDF для чека и сохраняет в FileField (Receipt.receipt_pdf_file).
    Также генерирует превью (receipt_preview_image) для этого чека.
    :param receipt_id: id чека
    :param save: если True — сохранить файл в pdf_file и превью, иначе вернуть bytes
    :return: путь к PDF файлу или bytes
    """
    from marketplace.models import Receipt  # твой импорт модели

    try:
        receipt = Receipt.objects.select_related(
            'payment_method', 'customer'
        ).prefetch_related(
            'sales__variant__product__business',  # подтягиваем бизнес через variant->product
            'sales__location'
        ).get(pk=receipt_id)
    except Receipt.DoesNotExist:
        raise ValueError("Чек не найден")

    # Получаем бизнес через первую продажу (если чек пустой — ошибка)
    first_sale = receipt.sales.select_related('variant__product__business').first()
    if not first_sale:
        raise ValueError("В чеке нет продаж!")
    business = first_sale.variant.product.business

    # Используем кастомные или дефолтные шаблоны
    html_tpl = business.receipt_html_template or DEFAULT_RECEIPT_HTML
    css_tpl = business.receipt_css_template or DEFAULT_RECEIPT_CSS

    context = {
        'receipt': receipt,
        'business': business,
        'sales': list(receipt.sales.select_related('variant', 'location')),
        'now': timezone.now(),
        'customer': receipt.customer,
    }

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
    pdf_bytes = HTML(string=full_html, base_url=settings.MEDIA_ROOT).write_pdf(stylesheets=[CSS(string=css_tpl)])

    if save:
        # Сохраняем PDF-файл
        filename = f"{receipt.number}.pdf"
        receipt.receipt_pdf_file.save(filename, ContentFile(pdf_bytes), save=False)  # save=False чтобы не обновлять updated_at

        # Генерируем превью (jpg/png) с первой страницы PDF
        try:
            # convert_from_bytes возвращает список PIL.Image
            images = convert_from_bytes(
                pdf_bytes,
                first_page=1,
                last_page=1,
                dpi=170,
                poppler_path=POPPLER_PATH
            )
            if images:
                img_io = io.BytesIO()
                images[0].save(img_io, 'PNG', quality=85)
                img_io.seek(0)
                preview_filename = f"{receipt.number}_preview.png"
                receipt.receipt_preview_image.save(preview_filename, ContentFile(img_io.read()), save=False)
        except Exception as e:
            print(os.path.exists(r'C:\poppler-24.08.0\Library\bin\pdftoppm.exe'))
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
      size: 80mm 297mm;
      margin: 2mm 0;
    }
    body {
      font-family: 'Courier New', monospace;
      font-size: 9pt;
      width: 76mm;
      margin: 0 auto;
      padding: 0;
      line-height: 1.1;
    }
    .header, .footer {
      text-align: center;
      font-weight: bold;
    }
    .divider {
      border-top: 1px dashed #000;
      margin: 3px 0;
    }
    .items {
      width: 100%;
    }
    .item-row {
      display: flex;
      justify-content: space-between;
    }
    .item-name {
      flex: 3;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .item-qty {
      flex: 1;
      text-align: right;
      padding-right: 5px;
    }
    .item-price {
      flex: 2;
      text-align: right;
    }
    .total {
      font-weight: bold;
      margin-top: 5px;
    }
  </style>
</head>
<body>
  <div class="header">{{ business.name|upper }}</div>
  <div style="text-align: center; font-size: 8pt;">{{ business.address }}</div>
  <div class="divider"></div>
  
  <div>
    ЧЕК №: {{ receipt.number }}<br>
    ДАТА: {{ receipt.created_at.strftime('%d.%m.%Y %H:%M') }}<br>
    КАССИР: загушка <br>
  </div>
  
  <div class="divider"></div>
  
  <div class="items">
    {% for sale in sales %}
    <div class="item-row">
      <span class="item-name">{{ sale.variant.name|truncate(24, true) }}</span>
      <span class="item-qty">{{ sale.quantity }}x</span>
      <span class="item-price">{{ "%.2f"|format(sale.price_per_unit) }}₸</span>
    </div>
    <div class="item-row" style="justify-content: flex-end;">
      <span style="flex: 3; text-align: right;">{{ "%.2f"|format(sale.total_price) }}₸</span>
    </div>
    {% endfor %}
  </div>
  
  <div class="divider"></div>
  
  <div class="total">
    ИТОГО: {{ "%.2f"|format(receipt.total_amount) }}₸
  </div>
  
  {% if receipt.discount_percent or receipt.discount_amount %}
  <div>
    СКИДКА: 
    {% if receipt.discount_percent %}{{ receipt.discount_percent }}%{% endif %}
    {% if receipt.discount_amount %}{% if receipt.discount_percent %} - {% endif %}{{ receipt.discount_amount }}₸{% endif %}
  </div>
  {% endif %}
  
  <div class="divider"></div>
  
  <div class="footer">СПАСИБО ЗА ПОКУПКУ!</div>
  <div style="text-align: center; font-size: 7pt;">{{ now.strftime('%d.%m.%Y %H:%M:%S') }}</div>
</body>
</html>
"""

DEFAULT_RECEIPT_CSS = """

"""
