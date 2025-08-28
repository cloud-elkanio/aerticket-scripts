import ast
import json
import os
from rest_framework import serializers
from rest_framework.response import Response
import yaml
from datetime import datetime


from common.models import PaymentDetail
from vendors.hotels.utils import add_icon_types
from .models import HotelBookedRoomPax, HotelBooking, HotelDetails, HotelRoom, HotelBookedRoom, HotelBookingCustomer

class HotelDetailsSerializer(serializers.ModelSerializer):
    amenities = serializers.SerializerMethodField()
    
    class Meta:
        model = HotelDetails
        fields = '__all__'
    
    def get_amenities(self, obj):
        return add_icon_types(obj.amenities)

class HotelRoomSerializer(serializers.ModelSerializer):
    features = serializers.SerializerMethodField()
    
    class Meta:
        model = HotelRoom
        fields = '__all__'
    
    def get_features(self, obj):
        parsed_features = []
        for feature in obj.features:
            if isinstance(feature, str):
                try:
                    parsed_features.append(ast.literal_eval(feature))  # Safely convert string to dict
                except (ValueError, SyntaxError):
                    pass
                    # parsed_features.append(feature)  # Keep original if parsing fails
            else:
                parsed_features.append(feature)
        return parsed_features

class HotelBookedRoomSerializer(serializers.ModelSerializer):
    room = HotelRoomSerializer()
    
    class Meta:
        model = HotelBookedRoom
        fields = '__all__'

class HotelBookingCustomerSerializer(serializers.ModelSerializer):
    no_of_guests = serializers.SerializerMethodField()
    class Meta:
        model = HotelBookingCustomer
        fields = '__all__'

    def get_no_of_guests(self, obj):
        no_of_guests = HotelBookedRoomPax.objects.filter(room__booking_id = obj.id).count()
        return no_of_guests
    

class HotelPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentDetail
        fields = '__all__'

class HotelBookingSerializer(serializers.ModelSerializer):
    hotel = HotelDetailsSerializer()
    payment = HotelPaymentSerializer()
    booked_rooms = HotelBookedRoomSerializer(many=True, source='hotelbookedroom_set')
    customers = HotelBookingCustomerSerializer(many=True, source='hotelbookingcustomer_set')
    no_of_nights = serializers.SerializerMethodField()
    no_of_rooms = serializers.SerializerMethodField()
    organization_details = serializers.SerializerMethodField()
    
    class Meta:
        model = HotelBooking
        fields = '__all__'
    
    def get_no_of_nights(self, obj):
        # Calculate the difference in days
        no_of_nights = (obj.check_out - obj.check_in).days
        return no_of_nights
    
    def get_no_of_rooms(self, obj):
        # Calculate the difference in days
        no_of_rooms = sum([ booking.no_of_rooms for booking in HotelBookedRoom.objects.filter(booking_id = obj.id)])
        return no_of_rooms
    
    def get_organization_details(self, obj):
        aws_bucket = os.getenv('AWS_STORAGE_BUCKET_NAME',"")
        profile_pic = "https://{}.s3.amazonaws.com/media/{}".format(aws_bucket,str(obj.created_by.organization.profile_picture))
        organization_details = {"support_email":obj.created_by.organization.support_email,"support_phone":obj.created_by.organization.support_phone,
                                "profile_img_url":profile_pic,"profile_address":obj.created_by.organization.address,
                                "profile_name":obj.created_by.organization.organization_name}
        return organization_details
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['customer'] = data.pop('customers',[{}])[0]
        return data