import random
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from django.core.files.base import ContentFile

def calculate_ean13_checksum(code12: str) -> str:
    digits = list(map(int, code12))
    even_sum = sum(digits[-1::-2])    # четные с конца
    odd_sum = sum(digits[-2::-2])     # нечетные с конца
    checksum = (10 - ((odd_sum * 3 + even_sum) % 10)) % 10
    return str(checksum)

def generate_ean13_code(prefix: str = "200") -> str:
    """
    prefix: первые 3 цифры, например '200' — внутренняя продукция (не международная).
    """
    assert prefix.isdigit() and len(prefix) == 3
    for _ in range(5):  # попытки с уникальностью
        base = prefix + ''.join(random.choices("0123456789", k=9))
        checksum = calculate_ean13_checksum(base)
        code = base + checksum
        from marketplace.models import ProductVariant
        if not ProductVariant.objects.filter(barcode=code).exists():
            return code
    raise ValueError("Не удалось сгенерировать уникальный EAN-13 код")

def generate_barcode_image(ean_code: str, file_name: str = None) -> ContentFile:
    """
    Возвращает PNG-изображение штрихкода как Django `ContentFile`
    """
    EAN = barcode.get_barcode_class('ean13')
    ean = EAN(ean_code, writer=ImageWriter())

    buffer = BytesIO()
    ean.write(buffer, options={
        "module_height": 15.0,
        "font_size": 8,
        "text_distance": 5.0,
        "quiet_zone": 4.0,
    })
    buffer.seek(0)

    return ContentFile(buffer.read(), name=(file_name or f"{ean_code}.png"))