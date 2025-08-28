from django.urls import path
from . import views

urlpatterns = [
    path('create-city-list/',views.CreateCities.as_view(), name='create-city-list'),
    path('get-city-list/',views.CityListView.as_view(), name='city-list'),
    path('search-bus/',views.SearchBus.as_view(), name='search'),
    path('search-bus-data/',views.SearchBusData.as_view(), name='search-data'),
    path('get-seatmap/',views.SeatMap.as_view(), name='get-seatmap'),
    path('get-pickup-drop/',views.PickupDrop.as_view(), name='get-pickup-drop'),
    
    path('create-booking/', views.CreateBooking.as_view(), name='bus_$_POST'),
    path('booking-details/', views.BookingDetailsView.as_view(), name='bus_$_POST'),
    path('purchase/', views.Purchase.as_view(), name='purchase'),

    path('purchase-status/', views.PurchaseStatusView.as_view(), name='purchase'),

    path('cancellation-charges/', views.CancellationCharges.as_view(), name='cancellation_charges'),
    path('cancel-ticket/', views.CancelTicket.as_view(), name='cancel_ticket'),
    path('process-failed-booking/', views.ProcessFailedView.as_view(), name='process_failed'),

]
 