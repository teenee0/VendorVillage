# services.py

from django.shortcuts import get_object_or_404
from django.db import transaction
from marketplace.models import Product, ProductVariant, ProductStock, ProductImage, CategoryAttribute, AttributeValue, Business
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
                    errors=[{"variant_index": i, "message": str(e)}]
                )

        for image_data in data.get("images", []):
            ProductService.create_image(product, image_data)

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
            ProductStock.objects.create(
                variant=variant,
                location=stock_data["location"],
                quantity=stock_data.get("quantity", 0),
                reserved_quantity=stock_data.get("reserved_quantity", 0),
                is_available_for_sale=stock_data.get("is_available_for_sale", True),
            )

    @staticmethod
    def create_variant_attribute(variant, attr_data):
        # attr_data уже содержит объекты, полученные сериализатором
        category_attribute = attr_data["category_attribute"]  # объект CategoryAttribute

        if (
            category_attribute.required and
            not attr_data.get("predefined_value") and
            not attr_data.get("custom_value")
        ):
            raise ProductError(f"Атрибут '{category_attribute.attribute.name}' обязателен")

        if category_attribute.attribute.has_predefined_values:
            predefined_value = attr_data.get("predefined_value")  # объект AttributeValue или None
            if not predefined_value:
                raise ProductError(f"Для '{category_attribute.attribute.name}' выберите значение")
            variant.attributes.create(
                category_attribute=category_attribute,
                predefined_value=predefined_value
            )
        else:
            custom_value = attr_data.get("custom_value")
            if not custom_value:
                raise ProductError(f"Для '{category_attribute.attribute.name}' задайте значение")
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
            display_order=image_data.get("display_order", 0)
        )
