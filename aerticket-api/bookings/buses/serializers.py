from rest_framework import serializers
from .models import *
import json
from datetime import datetime
from users.models import Country
import pytz

class BusBookingQueueSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source = 'user.first_name', read_only = True)
    last_name = serializers.CharField(source = 'user.last_name', read_only = True)
    phone_no = serializers.CharField(source = 'user.phone_number' , read_only = True)

    pickup_id = serializers.CharField(source = 'search_detail.pickup_id' , read_only = True)
    pickup_name = serializers.CharField(source = 'search_detail.pickup_name' , read_only = True)
    pickup_time = serializers.CharField(source = 'search_detail.pickup_time' , read_only = True)
    pickup_address = serializers.CharField(source = 'search_detail.pickup_address' , read_only = True)

    dropoff_id= serializers.CharField(source = 'search_detail.dropoff_id' , read_only = True)
    dropoff_name= serializers.CharField(source = 'search_detail.dropoff_name' , read_only = True)
    dropoff_time= serializers.CharField(source = 'search_detail.dropoff_time' , read_only = True)
    dropoff_address= serializers.CharField(source = 'search_detail.dropoff_address' , read_only = True)

    origin_city_id = serializers.CharField(source = 'search_detail.origin.city_id' , read_only = True)
    origin_city_name = serializers.CharField(source = 'search_detail.origin.city_name' , read_only = True)
    destination_city_id = serializers.CharField(source = 'search_detail.destination.city_id' , read_only = True)
    destination_city_name = serializers.CharField(source = 'search_detail.destination.city_name' , read_only = True)

    created_date =  serializers.SerializerMethodField()
    # pax_data =  serializers.SerializerMethodField()
    fare_price = serializers.SerializerMethodField()
    class Meta:
        model = BusBooking
        fields = ('id','session_id','display_id','segment_id','gst_details','pax_count','status',
                  'error','contact','misc','booked_at','cancelled_at','modified_at','departure_time',
                  'arrival_time','bus_type','operator','provider',
                  'first_name','last_name','phone_no',
                  'pickup_id','pickup_name','pickup_time','pickup_address',
                  'dropoff_id','dropoff_name','dropoff_time','dropoff_address',
                    'origin_city_id','origin_city_name',
                    'destination_city_id','destination_city_name','created_date','fare_price')
        
    def get_created_date(self,obj):
        booking_date = obj.created_at
        # Convert epoch timestamp to UTC datetime
        utc_dt = datetime.fromtimestamp(booking_date, pytz.utc)
        # Convert UTC datetime to IST
        ist_dt = utc_dt.astimezone(pytz.timezone('Asia/Kolkata'))
        return ist_dt
    # def get_pax_data(self, obj):
    #     try:
    #         return json.loads(obj.pax_data) if obj.pax_data else {}
    #     except json.JSONDecodeError:
    #         return {}
    def get_fare_price(self, obj):
        pub_fare = obj.bus_payment_details.new_published_fare
        off_fare = obj.bus_payment_details.new_offered_fare
        currency = obj.user.base_country.currency_symbol
        return {
               "published_fare" : pub_fare,
               "offered_fare" : off_fare,
               "currency":currency
                }
    def to_representation(self, instance):
        data = super().to_representation(instance)
        fields = ['booked_at', 'cancelled_at', 'modified_at']
        convert = lambda ts: datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else None
        for field in fields:
            timestamp = getattr(instance, field, None)
            data[field] = convert(timestamp)
        return data




