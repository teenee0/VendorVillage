# services.py

from django.shortcuts import get_object_or_404
from django.db import transaction
from marketplace.models import (
    Product,
    ProductVariant,
    ProductStock,
    ProductImage,
    ProductVariantAttribute,
    Business,
    AttributeValue,
    CategoryAttribute,
)
from .exceptions import ProductError


class ProductService:
    @staticmethod
    def get_business(user, slug):
        business = get_object_or_404(Business, slug=slug)
        if not user.businesses.filter(id=business.id).exists():
            raise ProductError("У вас нет прав для этого бизнеса")
        return business

    @staticmethod
    @transaction.atomic
    def create_product(user, business_slug, data):
        business = ProductService.get_business(user, business_slug)
        category = data["category"]  # Ожидается объект Category из сериализатора

        product = Product.objects.create(
            business=business,
            category=category,
            name=data["name"],
            description=data.get("description", ""),
            on_the_main=data.get("on_the_main", False),
            is_active=data.get("is_active", True),
        )

        variants = data.get("variants")
        if not variants:
            raise ProductError("Товар должен содержать хотя бы один вариант.")

        for i, variant_data in enumerate(variants):
            try:
                ProductService.create_variant(product, variant_data)
            except ProductError as e:
                raise ProductError(
                    "Ошибка создания варианта",
                    errors=[{"variant_index": i, "message": str(e)}],
                )

        for image_data in data.get("images", []):
            ProductService.create_image(product, image_data)

        return product

    @staticmethod
    @transaction.atomic
    def update_product(user, business_slug, product_id, data):
        business = ProductService.get_business(user, business_slug)
        product = get_object_or_404(Product, id=product_id, business=business)

        # Обновление полей продукта
        product.name = data["name"]
        product.description = data.get("description", "")
        product.category_id = data["category"]
        product.on_the_main = data.get("on_the_main", False)
        product.is_active = data.get("is_active", True)
        product.save()

        # === Обновление изображений ===
        existing_image_ids = {img["id"] for img in data["images"] if "id" in img}
        ProductImage.objects.filter(product=product).exclude(
            id__in=existing_image_ids
        ).delete()

        for img_data in data["images"]:
            if "id" in img_data:
                img = ProductImage.objects.get(id=img_data["id"], product=product)
                img.is_main = img_data.get("is_main", False)
                img.display_order = img_data.get("display_order", 0)
                img.save()
            else:
                ProductService.create_image(product, img_data)

        # === Обновление вариантов ===
        incoming_variant_ids = {v["id"] for v in data["variants"] if "id" in v}
        ProductVariant.objects.filter(product=product).exclude(
            id__in=incoming_variant_ids
        ).delete()

        for v_data in data["variants"]:
            if "id" in v_data:
                ProductService.update_variant(product, v_data)
            else:
                ProductService.create_variant(product, v_data)

        return product

    @staticmethod
    def create_variant(product, variant_data):
        # variant_data — объект или OrderedDict с валидированными полями из сериализатора
        variant = ProductVariant.objects.create(
            product=product,
            sku=variant_data.get("sku"),
            has_custom_name=variant_data.get("has_custom_name", False),
            custom_name=variant_data.get("custom_name"),
            has_custom_description=variant_data.get("has_custom_description", False),
            custom_description=variant_data.get("custom_description"),
            price=variant_data["price"],
            discount=variant_data.get("discount"),
            show_this=variant_data.get("show_this", True),
        )

        attributes = variant_data.get("attributes")
        if not attributes:
            raise ProductError("Вариант должен содержать хотя бы один атрибут.")

        for attr_data in attributes:
            ProductService.create_variant_attribute(variant, attr_data)

        for stock_data in variant_data.get("stocks", []):
            loc = stock_data.get("location")
            if isinstance(loc, int):
                # передано ID локации
                ProductStock.objects.create(
                    variant=variant,
                    location_id=loc,
                    quantity=stock_data.get("quantity", 0),
                    reserved_quantity=stock_data.get("reserved_quantity", 0),
                    is_available_for_sale=stock_data.get("is_available_for_sale", True),
                )
            else:
                # передан объект локации
                ProductStock.objects.create(
                    variant=variant,
                    location=loc,
                    quantity=stock_data.get("quantity", 0),
                    reserved_quantity=stock_data.get("reserved_quantity", 0),
                    is_available_for_sale=stock_data.get("is_available_for_sale", True),
                )

    @staticmethod
    def update_variant(product, v_data):
        variant = get_object_or_404(ProductVariant, id=v_data["id"], product=product)
        variant.sku = v_data.get("sku")
        variant.price = v_data["price"]
        variant.discount = v_data.get("discount")
        variant.show_this = v_data.get("show_this", True)
        variant.has_custom_name = v_data.get("has_custom_name", False)
        variant.custom_name = v_data.get("custom_name")
        variant.has_custom_description = v_data.get("has_custom_description", False)
        variant.custom_description = v_data.get("custom_description")
        variant.save()

        # === Атрибуты ===
        incoming_attr_ids = {a.get("id") for a in v_data["attributes"] if a.get("id")}
        variant.attributes.exclude(id__in=incoming_attr_ids).delete()

        for attr_data in v_data["attributes"]:
            if attr_data.get("id"):
                attr = ProductVariantAttribute.objects.get(
                    id=attr_data["id"], variant=variant
                )

                predefined_value_id = attr_data.get("predefined_value")
                attr.predefined_value = (
                    AttributeValue.objects.get(id=predefined_value_id)
                    if predefined_value_id
                    else None
                )

                attr.custom_value = attr_data.get("custom_value", "")
                attr.save()
            else:
                # Обработка category_attribute: если передан id — преобразуем в объект
                if isinstance(attr_data["category_attribute"], int):
                    attr_data["category_attribute"] = CategoryAttribute.objects.get(
                        id=attr_data["category_attribute"]
                    )
                ProductService.create_variant_attribute(variant, attr_data)

        # === Остатки ===
        incoming_stock_ids = {s.get("id") for s in v_data["stocks"] if s.get("id")}
        variant.stocks.exclude(id__in=incoming_stock_ids).delete()

        for stock_data in v_data["stocks"]:
            if stock_data.get("id"):
                stock = ProductStock.objects.get(id=stock_data["id"], variant=variant)
                stock.location_id = stock_data["location"]
                stock.quantity = stock_data["quantity"]
                stock.reserved_quantity = stock_data["reserved_quantity"]
                stock.is_available_for_sale = stock_data["is_available_for_sale"]
                stock.save()
            else:
                ProductStock.objects.create(
                    variant=variant,
                    location_id=stock_data["location"],
                    quantity=stock_data["quantity"],
                    reserved_quantity=stock_data["reserved_quantity"],
                    is_available_for_sale=stock_data["is_available_for_sale"],
                )

    @staticmethod
    def create_variant_attribute(variant, attr_data):
        # Обработка category_attribute: ID или объект
        category_attribute = attr_data["category_attribute"]
        if isinstance(category_attribute, int):
            category_attribute = CategoryAttribute.objects.get(id=category_attribute)

        # Проверка обязательности
        if (
            category_attribute.required
            and not attr_data.get("predefined_value")
            and not attr_data.get("custom_value")
        ):
            raise ProductError(
                f"Атрибут '{category_attribute.attribute.name}' обязателен"
            )

        # Если у атрибута есть предопределённые значения
        if category_attribute.attribute.has_predefined_values:
            predefined_value = attr_data.get("predefined_value")

            if isinstance(predefined_value, AttributeValue):
                pass  # уже объект — ок
            elif isinstance(predefined_value, int):
                predefined_value = AttributeValue.objects.get(id=predefined_value)
            elif predefined_value is None:
                raise ProductError(
                    f"Для '{category_attribute.attribute.name}' выберите значение"
                )
            else:
                raise ProductError(
                    f"Неверный тип значения для '{category_attribute.attribute.name}'"
                )

            variant.attributes.create(
                category_attribute=category_attribute,
                predefined_value=predefined_value
            )

        else:
            # Пользовательское значение
            custom_value = attr_data.get("custom_value")
            if not custom_value:
                raise ProductError(
                    f"Для '{category_attribute.attribute.name}' задайте значение"
                )
            variant.attributes.create(
                category_attribute=category_attribute,
                custom_value=custom_value
            )


    @staticmethod
    def create_image(product, image_data):
        ProductImage.objects.create(
            product=product,
            image=image_data["image"],
            is_main=image_data.get("is_main", False),
            alt_text=image_data.get("alt_text", ""),
            display_order=image_data.get("display_order", 0),
        )

    @staticmethod
    def delete_product(user, business_slug, product_id):
        business = ProductService.get_business(user, business_slug)
        product = get_object_or_404(Product, id=product_id, business=business)
        product.delete()