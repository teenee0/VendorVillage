from rest_framework import serializers
from core.models import Business, BusinessLocation, BusinessLocationType


class BusinessUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = [
            'name',
            'description',
            'phone',
            'address',
            'business_logo',
            # 'background_image',
            'html_template',
            'product_card_template',
            'product_detail_template',
            'receipt_html_template',
            'receipt_css_template',
        ]


class BusinessLocationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessLocationType
        fields = ["id", "code", "name", "is_warehouse", "is_sales_point"]


class BusinessLocationSerializer(serializers.ModelSerializer):
    location_type = serializers.PrimaryKeyRelatedField(
        queryset=BusinessLocationType.objects.all()
    )
    location_type_detail = BusinessLocationTypeSerializer(source="location_type", read_only=True)

    class Meta:
        model = BusinessLocation
        fields = [
            "id",
            "business",
            "name",
            "location_type",         # ← используется при POST / PATCH
            "location_type_detail",  # ← вложенный объект при GET
            "address",
            "contact_phone",
            "is_active",
            "is_primary",
            "description",
            "opening_hours",
            "latitude",
            "longitude",
        ]
        read_only_fields = ["id", "business"]
