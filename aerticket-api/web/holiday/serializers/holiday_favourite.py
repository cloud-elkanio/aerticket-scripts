from rest_framework import serializers
from pms.holiday_app.models import HolidayFavourite,HolidaySKUImage
from api.settings import MEDIA_URL as aws_url

class HolidayFavouriteSerializer(serializers.ModelSerializer):
    holiday_name = serializers.CharField(source='sku_id.name', read_only=True)
    holiday_description = serializers.CharField(source='sku_id.overview', read_only=True)
    holiday_images = serializers.SerializerMethodField()
    holiday_slug = serializers.CharField(source='sku_id.slug', read_only=True)  
    class Meta:
        model = HolidayFavourite
        fields = '__all__'

    
    def get_holiday_images(self, obj):
        image_instances = HolidaySKUImage.objects.filter(sku_id=obj.sku_id)
        image_data = [{
            'image_url': f"{aws_url}{str(image_instance.gallery_id.url)}"
        } for image_instance in image_instances]
        
        return image_data 