from django.contrib import admin
from django.urls import path, include
from .views import *

urlpatterns = [
    path("transfers/booking-queue",TransfersBookingQueue.as_view(), name='flight_booking_view'),

]
