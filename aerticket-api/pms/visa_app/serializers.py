from rest_framework import serializers
from .models import *
from users.models import CountryDefault

class VisaCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VisaCategoryMaster
        fields = '__all__'

class VisaCategorySerializerGet(serializers.ModelSerializer):
    icon_id = serializers.UUIDField(source='icon_url.id',  read_only=True)
    icon_url = serializers.ImageField(source='icon_url.url', read_only=True)

    class Meta:
        model = VisaCategoryMaster
        exclude = ('is_deleted','deleted_at','created_at','modified_at')


class VisaTypeMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisaTypeMaster
        fields = '__all__'

class VisaTypeMasterSerializerGet(serializers.ModelSerializer):
    icon_id = serializers.UUIDField(source='icon_url.id',  read_only=True)
    icon_url = serializers.ImageField(source='icon_url.url', read_only=True)

    class Meta:
        model = VisaTypeMaster
        exclude = ('is_deleted','deleted_at','created_at','modified_at')  





class VisaSKUSerializer(serializers.ModelSerializer):
    from_country= serializers.SerializerMethodField()
    to_country   =serializers.SerializerMethodField()
    # category   =serializers.SerializerMethodField()
    # type   =serializers.SerializerMethodField()

    class Meta:
        model = VisaSKU
        exclude = ('is_deleted','deleted_at','created_at','modified_at')

    def get_from_country (self,obj):
        return obj.from_country.country_name
    def get_to_country (self,obj):
        return obj.to_country.country_name
    # def get_category (self,obj):
    #     return obj.category.name
    # def get_type (self,obj):
    #     return obj.type.name


class VisaSKUPriceSerializer(serializers.ModelSerializer):
    # country_name = serializers.SerializerMethodField()
    class Meta:
        model = VisaSKUPrice
        exclude = ('is_deleted','deleted_at')

    # def get_country_name (self,obj):
    #     return obj.country_id.lookup.country_name

class VisaSKUimageSerializer(serializers.ModelSerializer):
    image_id= serializers.SerializerMethodField()
    image_url= serializers.SerializerMethodField()

    class Meta:
        model = VisaSKUImage
        exclude = ('is_deleted','deleted_at')
    def get_image_id (self,obj):
        return obj.gallery_id.id
    def get_image_url (self,obj):
        return obj.gallery_id.url
    
class VisaDefaultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CountryDefault
        exclude = ('is_deleted','deleted_at','created_at','modified_at')

class VisaFavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisaFavourite
        fields = '__all__'

class VisaFavoriteSerializerGet(serializers.ModelSerializer):
    country_name = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        model = VisaFavourite
        exclude = ('is_deleted','deleted_at','created_at','modified_at')

    def get_country_name(self, obj):
        return obj.country_id.lookup.country_name
    
    def get_name(self, obj):
        return obj.sku_id.name
    
class VisaEnquirySerializerGet(serializers.ModelSerializer):
    visa_name = serializers.SerializerMethodField()
    country_name = serializers.SerializerMethodField()
    status_name = serializers.SerializerMethodField()
    # dob = serializers.DateField(format="%d-%m-%Y", input_formats=['%Y-%m-%d', '%d-%m-%Y'])
    history = serializers.SerializerMethodField()

    class Meta:
        model = VisaEnquiry
        exclude = ('is_deleted','deleted_at')
    def get_visa_name(self,obj):
        return obj.visa_id.name
    def get_country_name(self, obj):
        return obj.country.country_name
    def get_status_name(self, obj):
        # Retrieve the last status associated with the enquiry
        history_obj = VisaEnquiryHistory.objects.filter(visa_enquiry=obj).last()
        return history_obj.status_id.name if history_obj else None
    def get_history(self, obj):
        history = VisaEnquiryHistory.objects.filter(visa_enquiry=obj).order_by('-modified_at')
        return VisaEnquiryHistorySerializer(history, many=True).data
    
             
class VisaEnquiryStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupVisaEnquiryStatus
        fields = ['id', 'name']

class VisaEnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = VisaEnquiry
        fields = "__all__"

class VisaEnquiryHistorySerializer(serializers.ModelSerializer):
    status_name = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()
    visa_link = serializers.SerializerMethodField()
    class Meta:
        model = VisaEnquiryHistory
        exclude = ['is_deleted','deleted_at','created_at','modified_at']

    def get_status_name(self, obj):
        return obj.status_id.name
    def get_updated_by(self, obj):
        return obj.updated_by.first_name if obj.updated_by else None
    def get_visa_link(self, obj):
        return obj.visa_enquiry.visa_id.slug
    
class VisaSKUSlugSerializer(serializers.ModelSerializer):
    from_country= serializers.SerializerMethodField()
    to_country   =serializers.SerializerMethodField()
    price   =serializers.SerializerMethodField()
    category_name   =serializers.SerializerMethodField()
    type_name   =serializers.SerializerMethodField()

    class Meta:
        model = VisaSKU
        exclude = ('is_deleted','deleted_at','created_at','modified_at')

    def get_from_country (self,obj):
        return obj.from_country.country_name
    def get_to_country (self,obj):
        return obj.to_country.country_name
    
    def get_price(self,obj):
        visa_price_instance = VisaSKUPrice.objects.get(sku_id = obj)
        return visa_price_instance.price if visa_price_instance else None
    
    def get_category_name (self,obj):
        return obj.category.name
    def get_type_name (self,obj):
        return obj.type.name