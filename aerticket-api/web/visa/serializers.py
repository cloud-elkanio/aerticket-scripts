from rest_framework import serializers
from pms.visa_app.models import *
from .models import *

# class VisaCategorySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = VisaCategoryMaster
#         fields = '__all__'

class VisaCategorySerializerGet(serializers.ModelSerializer):
    icon_id = serializers.UUIDField(source='icon_url.id',  read_only=True)
    icon_url = serializers.ImageField(source='icon_url.url', read_only=True)

    class Meta:
        model = VisaCategoryMaster
        exclude = ('is_deleted','deleted_at','created_at','modified_at')


# class VisaTypeMasterSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = VisaTypeMaster
#         fields = '__all__'

# class VisaTypeMasterSerializerGet(serializers.ModelSerializer):
#     icon_id = serializers.UUIDField(source='icon_url.id',  read_only=True)
#     icon_url = serializers.ImageField(source='icon_url.url', read_only=True)

#     class Meta:
#         model = VisaTypeMaster
#         exclude = ('is_deleted','deleted_at','created_at','modified_at')  





class VisaSKUSerializer(serializers.ModelSerializer):
    from_country= serializers.SerializerMethodField()
    to_country   =serializers.SerializerMethodField()
    category_name   =serializers.SerializerMethodField()
    entry_type   =serializers.SerializerMethodField()

    class Meta:
        model = VisaSKU
        exclude = ('is_deleted','deleted_at','created_at','modified_at')

    def get_from_country (self,obj):
        return obj.from_country.country_name
    def get_to_country (self,obj):
        return obj.to_country.country_name
    def get_category_name (self,obj):
        return obj.category.name
    def get_entry_type (self,obj):
        return obj.type.name


class VisaSKUPriceSerializer(serializers.ModelSerializer):
    # country_name = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()
    class Meta:
        model = VisaSKUPrice
        exclude = ('is_deleted','deleted_at')

    def get_currency_symbol (self,obj):
        return obj.country_id.currency_symbol

    # def get_country_name (self,obj):
    #     return obj.country_id.lookup.country_name

# class VisaSKUimageSerializer(serializers.ModelSerializer):
#     image_id= serializers.SerializerMethodField()
#     image_url= serializers.SerializerMethodField()

#     class Meta:
#         model = VisaSKUImage
#         exclude = ('is_deleted','deleted_at')
#     def get_image_id (self,obj):
#         return obj.gallery_id.id
#     def get_image_url (self,obj):
#         return obj.gallery_id.url


class SingleVisaDetailSerializer(serializers.ModelSerializer):
    from_country= serializers.SerializerMethodField()
    to_country   =serializers.SerializerMethodField()

    class Meta:
        model = VisaSKU
        exclude = ('is_deleted','deleted_at')

    def get_from_country (self,obj):
        return obj.from_country.country_name
    def get_to_country (self,obj):
        return obj.to_country.country_name

class VisaEnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = VisaEnquiry
        exclude = ('is_deleted','deleted_at')

class VisaFavoriteSerializerGet(serializers.ModelSerializer):
    country_name = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    visa_type = serializers.SerializerMethodField()
    processing_time = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    slug = serializers.SerializerMethodField()


    class Meta:
        model = VisaFavourite
        exclude = ('is_deleted','deleted_at','created_at','modified_at')

    def get_country_name(self, obj):
        return obj.country_id.lookup.country_name
    
    def get_name(self, obj):
        return obj.sku_id.name
    def get_visa_type(self, obj):
        return obj.sku_id.type.name
    def get_processing_time(self, obj):
        return obj.sku_id.processing_time
    def get_price(self, obj):
        visa_price = VisaSKUPrice.objects.filter(sku_id=obj.sku_id, country_id=obj.country_id).first()
        if visa_price:
            return visa_price.price
        return None
    
    def get_currency(self, obj):
        return obj.country_id.currency_symbol
    
    def get_images(self, obj):
        image_instances = VisaSKUImage.objects.filter(sku_id=obj.sku_id)
        return [
            {
                'id': str(image_instance.gallery_id.id),
                'url': image_instance.gallery_id.url.url
            }
            for image_instance in image_instances
        ]
    
    def get_slug(self, obj):
        return obj.sku_id.slug
