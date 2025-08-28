from rest_framework import serializers
from .models import *
import json
class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = '__all__'  


class ItenarySerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightBookingItineraryDetails
        fields = '__all__' 
        

class FlightBookingPaxDetailsSerializer(serializers.ModelSerializer):
    passport_issue_country_code = serializers.SerializerMethodField()
    
    class Meta:
        model = FlightBookingPaxDetails
        exclude = ('is_deleted','deleted_at','created_at','modified_at','booking')
        
    
    def get_passport_issue_country_code(self,data):
        if data.passport_issue_country_code:
            if data.passport_issue_country_code.country_code:
                return data.passport_issue_country_code.country_code
            else:
                return None
        
        
import ast       
class FlightBookingFareDetailsSerializer(serializers.ModelSerializer):
    fare_breakdown =serializers.SerializerMethodField()
    class Meta:
        model = FlightBookingFareDetails
        exclude = ('is_deleted','deleted_at','created_at','modified_at')
        
        
    def get_fare_breakdown(self,obj):
            if obj.fare_breakdown:
                fare_breakdown = ast.literal_eval(obj.fare_breakdown)
                return fare_breakdown
        
class FlightBookingSearchDetailsSerializer(serializers.ModelSerializer):
    passenger_details = serializers.SerializerMethodField()
    class Meta:
        model = FlightBookingSearchDetails
        exclude = ('is_deleted','deleted_at','created_at','modified_at')
        
        
    def get_passenger_details(self, obj):
        if obj.passenger_details:
            try:
                # Convert the string to a dictionary safely
                return ast.literal_eval(obj.passenger_details)
            except (ValueError, SyntaxError):
                # Handle parsing error
                return None  
        
    
    # def to_representation(self, instance):
    #     data =  super().to_representation(instance)
    #     ssr_obj = FlightBookingSSRDetails.objects.filter(pax_id=instance.id)
    #     print("-----")
    #     if ssr_obj:
    #         print("ssr")
    #         ssr_obj = ssr_obj.first()
    #         data["is_baggage"] = ssr_obj.is_baggage
    #         data["is_meals"] = ssr_obj.is_meals
    #         data["is_seats"] = ssr_obj.is_seats
    #         data["baggage_ssr"] = json.loads(ssr_obj.baggage_ssr) if ssr_obj.baggage_ssr else None
    #         data["meals_ssr"] = json.loads(ssr_obj.meals_ssr) if ssr_obj.meals_ssr else None
    #         data["seats_ssr"] = json.loads(ssr_obj.seats_ssr) if ssr_obj.seats_ssr else None
    #         data["ssr_id"] = ssr_obj.ssr_id
    #         data["supplier_pax_id"] = ssr_obj.supplier_pax_id
    #         data["supplier_ticket_id"] = ssr_obj.supplier_ticket_id
    #         data["supplier_ticket_number"] = ssr_obj.supplier_ticket_number
    #         data["supplier_ticket_number"] = ssr_obj.supplier_ticket_number
    #     return data
    
    

class PassengerCalendarSerializer(serializers.Serializer):
    display_id = serializers.CharField()
    booking_id = serializers.UUIDField(source='id') 
    airline = serializers.SerializerMethodField()
    airline_pnr = serializers.SerializerMethodField()
    gds_pnr = serializers.SerializerMethodField()
    source = serializers.SerializerMethodField()
    destination = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    pax_details = serializers.SerializerMethodField()
    booked_by = serializers.SerializerMethodField()
    contact = serializers.SerializerMethodField() 
    sector=serializers.SerializerMethodField() 
    def get_airline(self, obj):
        try:
            first_segment = obj.flightbookingjourneydetails_set.first().flightbookingsegmentdetails_set.first()
            return f"{first_segment.airline_code}-{first_segment.flight_number}" 
        except AttributeError:
            return ""
    


    def get_source(self, obj):
        try:
            return obj.flightbookingjourneydetails_set.first().source
        except:
            return ""

    def get_destination(self, obj):
        try:
            return obj.flightbookingjourneydetails_set.first().destination
        except:
            return ""

    def get_date(self, obj):
        try:
            return obj.flightbookingjourneydetails_set.first().date
        except:
            return ""

    def get_pax_details(self, obj):
        pax_data = []
        for pax in obj.flightbookingpaxdetails_set.all():
            pax_data.append({
                "name": f"{pax.title or ''} {pax.first_name} {pax.last_name}",
                "type": pax.pax_type.lower() 
            })
        return pax_data

    def get_booked_by(self, obj):
        return {
            "name": f"{obj.user.first_name} {obj.user.last_name}",
            "email": obj.user.email,
            "phone": obj.user.phone_number,
            "code": obj.user.base_country.lookup.calling_code,
            "organization_name":  f"{obj.user.organization.organization_name}({obj.user.organization.easy_link_billing_code})" if obj.user.organization and obj.user.organization.easy_link_billing_code else ""
        }
    def get_contact(self, obj):
        try:
            contact_data = json.loads(obj.contact)
            return {
                "email": contact_data.get("email", ""),
                "phone": contact_data.get("phone", ""),
                "phone_code": contact_data.get("phoneCode", "")
            }
        except (json.JSONDecodeError, AttributeError):
            return {
                "email": "",
                "phone": "",
                "phone_code": ""
            }
        
    def get_sector(self, obj):
        search_details = FlightBookingSearchDetails.objects.filter(id=obj.search_details_id).first()
        if search_details:
            return search_details.flight_type
        return " "
    def get_airline_pnr(self, obj):
        try:
            itinerary = obj.flightbookingitinerarydetails_set.first()
            return itinerary.airline_pnr if itinerary else ""
        except AttributeError:
            return ""

    def get_gds_pnr(self, obj):
        try:
            return obj.flightbookingitinerarydetails_set.first().gds_pnr
        except:
            return ""
        
class FetchPaxDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightBookingPaxDetails
        exclude = ('is_deleted','deleted_at','created_at','modified_at')