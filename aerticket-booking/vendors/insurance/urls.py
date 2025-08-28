from django.urls import path
from . import views

urlpatterns = [
    path('sync-data/',views.SyncData.as_view(), name='sync-data'),

    path('travel-category/',views.TravelCategories.as_view(), name='travel-category'),
    path('travel-plans/',views.TravelPlans.as_view(), name='travel-plans'),
    path('plan-addons/',views.PlanAddons.as_view(), name='plan-addons'),

    path('create-booking/',views.CreateBooking.as_view(), name='create-booking'),
    path('booking-details/', views.BookingDetailsView.as_view(), name='insurance_$_POST'),
    path('purchase/', views.Purchase.as_view(), name='purchase'),

    path('purchase-status/', views.PurchaseStatusView.as_view(), name='purchase'),

    # path('cancellation-charges/', views.CancellationCharges.as_view(), name='cancellation_charges'),
    path('endorse-ticket/', views.EndorseTicket.as_view(), name='endorse_ticket'),
    path('cancel-ticket/', views.CancelTicket.as_view(), name='cancel_ticket'),
    # path('process-failed-booking/', views.ProcessFailedView.as_view(), name='process_failed'),

]