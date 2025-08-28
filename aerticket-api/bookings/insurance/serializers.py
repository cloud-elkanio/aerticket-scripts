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

    commensing_date = serializers.CharField(source = 'search_detail.commensing_date' , read_only = True)
    end_date = serializers.CharField(source = 'search_detail.end_date' , read_only = True)
    duration = serializers.CharField(source = 'search_detail.duration' , read_only = True)

    created_date =  serializers.SerializerMethodField()

    fare_price = serializers.SerializerMethodField()

    cancelled_by = serializers.CharField(source = 'cancelled_by.first_name', read_only = True)
    modified_by = serializers.CharField(source = 'modified_by.first_name', read_only = True)

    class Meta:
        model = InsuranceBooking
        fields = ('id','session_id','display_id','status','error','misc',
                  'first_name','last_name','phone_no',
                  'commensing_date','end_date','duration','created_date',
                  'fare_price', 'booked_at', 'cancelled_at',
                  'cancelled_by','modified_by')
        
    def get_created_date(self,obj):
        booking_date = obj.created_at
        utc_dt = datetime.fromtimestamp(booking_date, pytz.utc)
        ist_dt = utc_dt.astimezone(pytz.timezone('Asia/Kolkata'))
        return ist_dt

    def get_fare_price(self, obj):
        pub_fare = obj.insurance_payment_details.new_published_fare
        off_fare = obj.insurance_payment_details.new_offered_fare
        currency = obj.user.base_country.currency_symbol
        return {
               "published_fare" : pub_fare,
               "offered_fare" : off_fare,
               "currency":currency
                }
    def to_representation(self, instance):
        data = super().to_representation(instance)
        fields = ['booked_at', 'cancelled_at']
        convert = lambda ts: datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else None
        for field in fields:
            timestamp = getattr(instance, field, None)
            data[field] = convert(timestamp)
        return data




