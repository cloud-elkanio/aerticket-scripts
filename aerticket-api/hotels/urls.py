
from django.contrib import admin
from django.urls import path, include
from .views import *   


urlpatterns = [
    path('hotel/booking-queues',HotelQueuesView.as_view()),
    path('grn-sync',GrnSyncView.as_view())

    

]