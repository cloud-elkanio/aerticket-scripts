from django.contrib import admin
from django.urls import path, include
from .views import *
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'bookings', BookingViewSet)
urlpatterns = [
  path("bookings/flight/flight-booking-queue",FlightBookingQueue.as_view(), name='flight_booking_view'),
  path('bookings/flight/flight-booking-queue/pick-up', FlightPickUp.as_view(),name='flightpickup'),
  path('bookings/flight/passenger-calender', PassengerCalender.as_view(),name='passenger-calender'),

  # =====================================invoke apis====================================================
  path('bookings/flight/flight-cancellation-request',FlightCancellationView.as_view()),
  path('bookings/flight/flight-booking-failed',FlightBookingFailed.as_view()),
  path('bookings/flight/flight-booking-modification',FlightBookingModification.as_view()),
  path('bookings/flight/flight-booking-confirmation',FlightBookingConfirmation.as_view()),
  path('passenger/details/list',FetchPaxDetails.as_view()),

  # =====================================invoke apis end====================================================

]

urlpatterns+=router.urls

