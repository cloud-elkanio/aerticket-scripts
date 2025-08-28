

"""
URL configuration for api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('suggestions/', views.SuggestionView.as_view()),
    path('create-session/', views.CreateSessionView.as_view()),
    path('hotel-search-data/', views.HotelSearchDataView.as_view()),
    path('hotel-details/', views.HotelDetailsView.as_view()),
    path('hotel-booking-details/', views.HotelBookingDetailsView.as_view()),
    path('hotel-booking-enquiry/', views.HotelBookingEnquiry.as_view()),
    path('hotel-booking/<str:booking_id>/', views.HotelBookingDetailsView.as_view()),
    path('hotel-payment/<str:payment_id>/', views.HotelPaymentDetailsView.as_view()),
    path('booking-cancellation/<str:booking_id>/', views.BookingCanellationView.as_view()),
    path('failed-booking-confirmation/<str:booking_id>/', views.FaledBookingConfirmationView.as_view()),
    path('failed-booking-reject/<str:booking_id>/', views.FaledBookingRejectView.as_view())

    # path('update-display-ids/', views.DisplayId.as_view()),
]
