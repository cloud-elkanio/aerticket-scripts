from .models import *
from rest_framework import serializers

class HotelDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelDetails
        fields = ('id','hotel_code', 'heading', 'address', 'latitude', 'longitude', 'description', 'amenities', 'image','base_price','currency_code')
class PaymentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentDetail
        fields = ('id','amount','status','payment_method','order_api_endpoint',
                  'order_api_payload','order_api_response','is_callback_recieved','callback_payload')
class SupplierIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierIntegration
        fields = ('id','country','name','data','icon_url','integration_type','is_active')
class HotelBookingSerializer(serializers.ModelSerializer):
    hotel = HotelDetailsSerializer(read_only = True)
    payment = PaymentDetailSerializer(read_only = True)
    created_by = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    supplier = SupplierIntegrationSerializer(read_only = True)
    no_of_rooms = serializers.SerializerMethodField()
    
    class Meta:
        model = HotelBooking
        fields = ('id','display_id','check_in','check_out','status','hotel','payment','created_by','supplier','no_of_rooms','created_at')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['customer'] = data.pop('customers',[{}])[0]
        data['hotel']['no_of_rooms'] = data['no_of_rooms']
        return data

    def get_created_by(self, obj):
        if obj.created_by:
            return obj.created_by.first_name + ' ' + obj.created_by.last_name
        return None

    def get_created_at(self, obj):
        return obj.created_at
    
    def get_no_of_rooms(self, obj):
        # Calculate the difference in days
        no_of_rooms = sum([ booking.no_of_rooms for booking in HotelBookedRoom.objects.filter(booking_id = obj.id)])
        return no_of_rooms


