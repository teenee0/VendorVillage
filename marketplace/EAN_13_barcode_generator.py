import random
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from django.core.files.base import ContentFile

def generate_barcode(prefix: str = "200") -> (str, ContentFile):
    """
    Генерирует уникальный EAN-13 штрихкод и изображение для Django ImageField.

    Возвращает:
        ean_code (str): строка из 13 цифр
        image_file (ContentFile): PNG-файл с изображением
    """
    assert prefix.isdigit() and len(prefix) == 3, "Префикс должен быть из 3 цифр"

    from marketplace.models import ProductVariant  # импорт внутри, чтобы избежать циклов

    for _ in range(10):  # до 10 попыток уникальности
        base = prefix + ''.join(random.choices("0123456789", k=9))
        EAN = barcode.get_barcode_class('ean13')
        ean = EAN(base, writer=ImageWriter())
        full_code = ean.get_fullcode()  # включает контрольную цифру

        if not ProductVariant.objects.filter(barcode=full_code).exists():
            buffer = BytesIO()
            ean.write(buffer, options={
                "module_height": 15.0,
                "font_size": 8,
                "text_distance": 5.0,
                "quiet_zone": 4.0,
            })
            buffer.seek(0)
            image_file = ContentFile(buffer.read(), name=f"{full_code}.png")
            return full_code, image_file

    raise ValueError("Не удалось сгенерировать уникальный EAN-13 штрихкод")
