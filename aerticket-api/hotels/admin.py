from django.contrib import admin
from .models import *

admin.site.register(HotelDetails)
admin.site.register(HotelRoom)
admin.site.register(HotelBooking)
admin.site.register(HotelBookingCustomer)
admin.site.register(HotelBookedRoom)
admin.site.register(HotelBookedRoomPax)
