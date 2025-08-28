
from django.contrib import admin
from django.urls import path, include
from .views import *   


urlpatterns = [
    path('bus/booking-queues',BusQueuesView.as_view())
]