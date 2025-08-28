# urls.py

from django.urls import path
from .views import *
urlpatterns = [
    path('web/holiday/search/', HolidaySKUPredictView.as_view(), name='holiday_sku_predict'),
    path('web/holiday/search-result/', SearchHolidayView.as_view(), name='search-holidays'),
    path('web/single/product/slug/<str:slug>/', SingleHolidaySKUView.as_view(), name='single_holiday_sku'),
    path('web/holiday/enquiry/', HolidayEnquiryView.as_view(), name='holiday-enquiry'),
    path('web/holiday/favourites/', HolidayFavouriteListView.as_view(), name='holiday-favourite-list'),


]
