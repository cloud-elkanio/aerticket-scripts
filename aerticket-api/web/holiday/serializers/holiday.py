from rest_framework import serializers
from pms.holiday_app.models import (
    HolidaySKU,
    HolidaySKUPrice,
    HolidaySKUTheme,
    LookUpHolidayEnquiryStatus,
    HolidayEnquiryHistory,
    HolidayEnquiry
)

class HolidaySKUSerializer(serializers.ModelSerializer):
    country = serializers.CharField(source='country.country_name', read_only=True)

    class Meta:
        model = HolidaySKU
        fields = ['id','name','location','country','slug','place']


class HolidaySkuGetSerializer(serializers.ModelSerializer):
    organization_id=serializers.SerializerMethodField()
    class Meta:
        model = HolidaySKU
        exclude = ('is_deleted','deleted_at','country','created_by','updated_by',)
    def get_organization_id(self, obj):
    # Replace with logic to get the organization ID from the obj
        return str(obj.organization_id.id) if obj.organization_id else None
    
    def to_representation(self, instance):
        data =  super().to_representation(instance)
        data['country'] = [str(country.id) for country in instance.country.all()]  
        data['created_by'] = str(instance.created_by.id)
        data['updated_by'] = str(instance.updated_by.id)
        return data


class HolidaySKUPriceSerializer(serializers.ModelSerializer):
    country_id = serializers.SerializerMethodField()
    class Meta:
        model = HolidaySKUPrice
        exclude = ('is_deleted','deleted_at')

    def get_country_id(self, obj):
        return str(obj.country_id.lookup.country_name) if obj.country_id else None

class HolidayThemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = HolidaySKUTheme
        fields="__all__"

class HolidayEnquirySerializerCreate(serializers.ModelSerializer):
    class Meta:
        model = HolidayEnquiry
        exclude = ('created_at', 'deleted_at', 'is_deleted')
