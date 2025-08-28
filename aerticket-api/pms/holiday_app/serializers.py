from rest_framework import serializers
from .models import *
from users.models import CountryDefault


class HolidaySKUSerializer(serializers.ModelSerializer):
    class Meta:
        model = HolidaySKU
        exclude = ["is_deleted", "deleted_at", "created_at"]


class LookupCountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupCountry
        exclude = ["is_deleted", "deleted_at", "created_at", "modified_at", "is_active"]


from datetime import datetime


class HolidaySKUSerializerGet(serializers.ModelSerializer):
    image_url = serializers.ImageField(source="image_url.image_url", read_only=True)
    image_id = serializers.UUIDField(source="image_url.id", read_only=True)
    created_by = serializers.CharField(source="created_by.first_name")
    updated_by = serializers.CharField(source="updated_by.first_name")
    modified_at = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()
    country_name=serializers.SerializerMethodField()
    themes = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    prices = serializers.SerializerMethodField()
    sku_inclusions = serializers.SerializerMethodField()  # Add inclusions field

    class Meta:
        model = HolidaySKU
        exclude = ("is_deleted", "deleted_at", "created_at")

    def get_created_by(self, obj):
        return obj.created_by.first_name

    def get_updated_by(self, obj):
        return obj.updated_by.first_name

    def get_modified_at(self, obj):
        # Convert epoch to datetime
        if obj.modified_at:
            return datetime.fromtimestamp(obj.modified_at).strftime("%Y-%m-%d %H:%M:%S")
        return None

    def get_country(self, obj):
        return [
            {"id": country.id, "name": country.country_name,"country_name":country.country_name}
            for country in obj.country.all()
        ]

    def get_country_name(self, obj):
        return [country.country_name for country in obj.country.all()]
    
    def get_themes(self, obj):
        themes = obj.holidayskutheme.all()
        return [
            {"id": theme.theme_id.id, "name": theme.theme_id.name} for theme in themes
        ]

    def get_images(self, obj):
        images = obj.holidayskuimage.all()
        return [
            {"id": image.gallery_id.id, "image_url": image.gallery_id.url.url}
            for image in images
        ]

    def get_prices(self, obj):
        # Retrieve the prices associated with the HolidaySKU object
        prices = obj.holidayskuprice.all()  # Use the correct related name
        return [
            {
                "country_id": price.country_id.id,
                # "country_name": price.country_id.currency_name,  # Assuming the currency_name is from the related Country model
                "price": str(
                    price.price
                ),  
            }
            for price in prices
        ]

    def get_sku_inclusions(self, obj):
        # Retrieve inclusions for the specific HolidaySKU object
        inclusion = HolidaySKUInclusion.objects.filter(sku_id=obj).first()
        if inclusion:
            return [
                {
                    "flight": inclusion.flight,
                    "hotel": inclusion.hotel,
                    "transfer": inclusion.transfer,
                    "meals": inclusion.meals,
                    "visa": inclusion.visa,
                    "sight_seeing": inclusion.sight_seeing,
                }
            ]
        return None


class HolidaySKUPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = HolidaySKUPrice
        exclude = ("is_deleted", "deleted_at")
    

class HolidaySKUThemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = HolidaySKUTheme
        fields = "__all__"


class HolidayThemeMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = HolidayThemeMaster
        fields = "__all__"


class HolidayThemeMasterSerializerGet(serializers.ModelSerializer):
    icon_url = serializers.ImageField(source="icon_url.url", read_only=True)
    image_id = serializers.UUIDField(source="icon_url.id", read_only=True)

    class Meta:
        model = HolidayThemeMaster
        exclude = ("is_deleted", "deleted_at", "created_at")


class GallerySerializer(serializers.ModelSerializer):
    class Meta:
        model = Gallery
        fields = ["id", "name", "url", "module"]


class HolidayFavoriteSerializer(serializers.ModelSerializer):

    class Meta:
        model = HolidayFavourite
        fields = "__all__"


class HolidayFavoriteSerializerGet(serializers.ModelSerializer):
    country_name = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        model = HolidayFavourite
        exclude = ("is_deleted", "deleted_at", "created_at", "modified_at")

    def get_country_name(self, obj):
        return obj.country_id.lookup.country_name

    def get_name(self, obj):
        return obj.sku_id.name


class CountryDefaultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CountryDefault
        exclude = ("is_deleted", "deleted_at", "created_at", "modified_at")


class HolidayEnquiryHistorySerializer(serializers.ModelSerializer):
    status_name = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()

    class Meta:
        model = HolidayEnquiryHistory
        fields = ("id", "status_name", "updated_at", "updated_by", "holiday_enquiry_id")
    

    def get_status_name(self, obj):
        return obj.status.name if obj.status else None

    def get_updated_by(self, obj):
        return (
            f"{obj.updated_by.first_name} {obj.updated_by.last_name}"
            if obj.updated_by
            else None
        )


class HolidayEnquirySerializer(serializers.ModelSerializer):
    holiday_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()

    class Meta:
        model = HolidayEnquiry
        fields = (
            "id",
            "name",
            "email",
            "phone",
            "city",
            "date_of_travel",
            "pax_count",
            "holiday_name",
            "holiday_id",
            "enquiry_ref_id",
            "status",
            "is_deleted",
            "created_at",
            "history",
        )

    def get_holiday_name(self, obj):
        return obj.holiday_id.name if obj.holiday_id else None

    def get_status(self, obj):
     latest_status = (
        HolidayEnquiryHistory.objects.filter(holiday_enquiry_id=obj.id)
        .order_by("-updated_at")
        .first()
    )
        # Check if latest_status exists and has a non-None status
     if latest_status and latest_status.status:
            return latest_status.status.name
     return None

    def get_history(self, obj):
        history_queryset = HolidayEnquiryHistory.objects.filter(
            holiday_enquiry_id=obj.id
        ).order_by("-updated_at")
        return HolidayEnquiryHistorySerializer(history_queryset, many=True).data


class HolidayQueueStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookUpHolidayEnquiryStatus
        fields = ["id", "name"]


class UpdateHolidayEnquiryStatusSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status_id = serializers.UUIDField()


class HolidaySupplierListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("id", "organization_name")
