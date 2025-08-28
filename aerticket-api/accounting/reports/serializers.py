from users.models import UserDetails
from bookings.flight.models import Booking
from rest_framework import serializers
from datetime import datetime

class UserDetailsReportSerilaizer(serializers.ModelSerializer):
    class Meta:
        model = UserDetails
        fields = ('first_name','id','is_active','date_joined','email','phone_number','base_country','organization')
        # fields = "__all__"

    def to_representation(self, instance):

        data = super().to_representation(instance)
        data['company_name'] = data.pop('first_name')
        data['agency_id'] = data.pop('id')
        data['created_at'] = data.pop('date_joined')
        data['state'] = instance.organization.state
        data['status'] = data.pop('is_active')
        data['country'] = instance.base_country.lookup.country_name
         
        return data
    

class SalesReportSerilaizer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        # fields = ('first_name','id','is_active','date_joined','email','phone_number','base_country','organization')
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # data['itinerarydetails_status'] = instance.flightbookingitinerarydetails
        return data