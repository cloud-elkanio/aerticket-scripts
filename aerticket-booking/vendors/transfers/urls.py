
from django.urls import path
from .views import CountryListView, CityDataView, SelectDestination, SearchLocation, \
                     TransferSearchInitView, TransferSearchDataView, CreateBookingView, PurchaseView, \
                     PurchaseStatusView, PurchaseDetailsView, ProcessFailedView, GetCancellationChargesView, MarkCancelledView, \
                     GetBookingDetailsView, CheckEasyLink

urlpatterns = [
    path('get_country_list/', CountryListView.as_view(), name='country-list'),
    path('get_city_data/', CityDataView.as_view(), name='city-hotel-data'),
    path('select_destination/', SelectDestination.as_view(), name='select-destination'),
    path('search_location/', SearchLocation.as_view(), name='search-location'),
    path('search_transfers_init/', TransferSearchInitView.as_view(), name='search-transfers-init'),
    path('get_transfers_search_data/', TransferSearchDataView.as_view(), name='search-transfers-data'),
    path('create_booking/', CreateBookingView.as_view(), name='create-transfers-booking'),
    path('purchase/', PurchaseView.as_view(), name='purchase'),
    path('purchase-status/', PurchaseStatusView.as_view(), name='purchase-status'),
    path('purchase-details/', PurchaseDetailsView.as_view(), name='purchase-details'),
    path('process-failed-booking/', ProcessFailedView.as_view(), name='process-failed-booking'),
    path('get-cancellation-charges/', GetCancellationChargesView.as_view(), name='get-cancellation-charges'),
    path('mark_cancelled/', MarkCancelledView.as_view(), name='mark-cancelled'),
    path('get_booking_details/', GetBookingDetailsView.as_view(), name='get-booking-details'),
    path('check_easy_link/', CheckEasyLink.as_view(), name='get-booking-details'),
]