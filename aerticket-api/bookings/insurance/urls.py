
from django.contrib import admin
from django.urls import path, include
from .views import *   


urlpatterns = [
    path('insurance/booking-queues',InsuranceQueuesView.as_view())
]