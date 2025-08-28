from rest_framework import serializers
from .models import *
import json
from datetime import datetime
from users.models import Country
import pytz

class TransferBookingLocationDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferBookingLocationDetail
        fields = ['type','name','date','time','code','city_name','country','AddressLine1','AddressLine2',
                  'details','ZipCode','transfer_type']

class TransferBookingContactDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferBookingContactDetail
        fields = ['first_name','last_name','contact_number']

class TransfersBookingQueueSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    contact_number = serializers.SerializerMethodField()
    pickup_type = serializers.CharField(source = 'search_details.pickup_type' , read_only = True)
    pickup_point_code = serializers.CharField(source = 'search_details.pickup_point_code' , read_only = True)
    dropoff_type = serializers.CharField(source = 'search_details.dropoff_type' , read_only = True)
    dropoff_point_code = serializers.CharField(source = 'search_details.dropoff_point_code' , read_only = True)
    city_id = serializers.CharField(source = 'search_details.city_id' , read_only = True)
    pickup_data = serializers.SerializerMethodField()
    drop_data = serializers.SerializerMethodField()
    created_date =  serializers.SerializerMethodField()
    pax_data =  serializers.SerializerMethodField()
    fare_price = serializers.SerializerMethodField()
    class Meta:
        model = TransferBooking
        fields = ('id','display_id','session_id','segment_id','pax_count','pax_data','confirmation_number',
                  'booking_ref_no','booking_id','transfer_id','status','error','first_name','last_name',
                  'contact_number','pickup_type','pickup_point_code','dropoff_type','dropoff_point_code','city_id',
                  'pickup_data', 'drop_data','created_date', 'fare_price')
        
    def get_pickup_data(self, obj):
        pickup_details = TransferBookingLocationDetail.objects.filter(
            transfer_type='pickup', booking=obj  # or booking_id=obj.id if that's your field
        ).first()
        return TransferBookingLocationDetailSerializer(pickup_details).data if pickup_details else {}

    def get_drop_data(self, obj):
        drop_details = TransferBookingLocationDetail.objects.filter(
            transfer_type='drop', booking=obj  # or booking_id=obj.id
        ).first()
        return TransferBookingLocationDetailSerializer(drop_details).data if drop_details else {}

    
    def get_created_date(self,obj):
        booking_date = obj.modified_at
        # Convert epoch timestamp to UTC datetime
        utc_dt = datetime.fromtimestamp(booking_date, pytz.utc)
        # Convert UTC datetime to IST
        ist_dt = utc_dt.astimezone(pytz.timezone('Asia/Kolkata'))
        return ist_dt
    
    def get_pax_data(self, obj):
        try:
            return json.loads(obj.pax_data) if obj.pax_data else {}
        except json.JSONDecodeError:
            return {}
    def get_fare_price(self, obj):
        pub_fare = obj.payment_detail.new_published_fare
        off_fare = obj.payment_detail.new_offered_fare
        currency = obj.user.base_country.currency_symbol
        return {
               "published_fare" : pub_fare,
               "offered_fare" : off_fare,
               "currency":currency
                }
    def get_first_name(self, obj):
        contact_detail = TransferBookingContactDetail.objects.filter(booking_id = obj).first()
        return contact_detail.first_name if contact_detail else None
    def get_last_name(self, obj):
        contact_detail = TransferBookingContactDetail.objects.filter(booking_id = obj).first()
        return contact_detail.last_name if contact_detail else None
    def get_contact_number(self, obj):
        contact_detail = TransferBookingContactDetail.objects.filter(booking_id = obj).first()
        return contact_detail.contact_number if contact_detail else None


