from django.contrib import admin
from .models import Booking,FlightBookingSearchDetails,FlightBookingPaymentDetails,FlightBookingJourneyDetails, FlightBookingItineraryDetails,FlightBookingSegmentDetails,FlightBookingPaxDetails
# Register your models here.
# admin.site.register(Booking)
admin.site.register(FlightBookingSearchDetails)
admin.site.register(FlightBookingPaymentDetails)
admin.site.register(FlightBookingJourneyDetails)
# admin.site.register(FlightBookingItineraryDetails)
# admin.site.register(FlightBookingSegmentDetails)




class BookingAdmin(admin.ModelAdmin):
    list_filter = ["display_id"]
    ordering = ['-created_at']
    search_fields = ('contact','id','gst_details','source')
    list_display = ['display_id','gst_details','status','booked_at','source']

admin.site.register(Booking,BookingAdmin)


class FlightBookingSegmentDetailsAdmin(admin.ModelAdmin):
    # list_filter = ["id"]
    ordering = ['-created_at']
    search_fields = ('id','journey__itinerary__booking__display_id')

    def booking_id(self, obj):
        return obj.journey.itinerary.booking.display_id if obj.journey and obj.journey.itinerary else None

    booking_id.short_description = 'Booking ID'  
    list_display = ['id','booking_id','airline_number','airline_name','airline_code'] 

admin.site.register(FlightBookingSegmentDetails, FlightBookingSegmentDetailsAdmin)

class FlightBookingItineraryDetailsAdmin(admin.ModelAdmin):
    list_filter = ["booking"]
    ordering = ['-created_at']
    search_fields = ('booking__display_id', 'id', 'itinerary_key')
    list_display = ['id', 'status', 'gds_pnr', 'invoice_amount', 'booking_display_id']

    def booking_display_id(self, obj):
        return obj.booking.display_id  # Fetch the related booking's display_id
    booking_display_id.short_description = 'Booking Display ID'  # Optional: Rename column header

admin.site.register(FlightBookingItineraryDetails, FlightBookingItineraryDetailsAdmin)

admin.site.register(FlightBookingPaxDetails)