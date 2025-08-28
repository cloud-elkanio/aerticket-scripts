from django.contrib import admin
from django.urls import path
from vendors.flights.views import (
    CreateSessionView,GetFlightsView,GetFareDetails,
    AirPricing,FlightsSSR,CreateBooking,
    CheckHold,HoldBooking,Purchase,TicketStatus,PurchaseStatus,
    ConvertHoldtoTicket,ReleaseHold,Repricing,CancellationCharges,
      CancelTicket,BookingStatus,OfficeCodes,OfflineImportPNR,CreditCards,
        AgencyList,SupplierList,CreateOfflineBilling,TicketingImportPNR,
       TicketingCreate,TicketingRepricing,CreateTicketingBilling,UpdateFailedBooking,FallToFail,CheckCancellationStatus,
       UpdateTicketStatus,GetFareRule
)
urlpatterns = [
    path('flight-search', CreateSessionView.as_view(), name='flight_search_$_GET'),
    path('flight-search-data', GetFlightsView.as_view(), name='flight_search_$_GET'),
    path('fare-details', GetFareDetails.as_view(), name='flight_search_$_GET'),
    path('air-pricing', AirPricing.as_view(), name='flight_search_$_GET'),
    path('flight-ssr', FlightsSSR.as_view(), name='flight_$_GET'),
    path('get-fare-rule', GetFareRule.as_view(), name='flight_$_GET'),
    path('create-booking', CreateBooking.as_view(), name='flight_$_POST'),
    path('check-hold', CheckHold.as_view(), name='flight_$_POST'),
    path('hold-booking', HoldBooking.as_view(), name='flight_$_POST'),
    path('convert-hold-to-ticket', ConvertHoldtoTicket.as_view(), name='flight_$_POST'),
    path('purchase', Purchase.as_view(), name='flight_$_POST'),
    path('purchase-status', PurchaseStatus.as_view(), name='flight_$_POST'),
    path('payment-success', TicketStatus.as_view(), name='flight_$_POST'),
    path('booking-details', TicketStatus.as_view(), name='flight_$_POST'),
    path('booking-status', BookingStatus.as_view(), name='flight_$_POST'),
    path('pickup', TicketStatus.as_view(), name='flight_$_POST'),
    path('repricing', Repricing.as_view(), name='flight_$_PUT'),
    path('cancellation-charges', CancellationCharges.as_view(), name='flight_$_PUT'),
    path('cancel-ticket', CancelTicket.as_view(), name='flight_$_PUT'),
    path('release-hold', ReleaseHold.as_view(), name='flight_$_PUT'),
    path('offline-billing-import-pnr',OfflineImportPNR.as_view(), name='offline_import_pnr'),
    path('credit-cards',CreditCards.as_view(), name='credit_cards'),
    path('agency-list',AgencyList.as_view(), name='agency_list'),
    path('office-codes',OfficeCodes.as_view(), name='office_codes'),
    path('supplier-list',SupplierList.as_view(), name='supplier_list'),
    path('offline-billing-create-bill',CreateOfflineBilling.as_view(), name='offline_billing_create_bill'),
    path('ticketing-import-pnr',TicketingImportPNR.as_view(), name='ticketing_import_pnr'),
    path('ticketing-repricing',TicketingRepricing.as_view(), name='ticketing_repricing'),
    path('ticketing-create',TicketingCreate.as_view(), name='ticketing_create'),
    path('ticketing-create-bill',CreateTicketingBilling.as_view(), name='ticketing_create_bill'),
    path('update-failed-booking',UpdateFailedBooking.as_view(), name='flight_$_PUT'),
    path('fall-to-fail',FallToFail.as_view(), name='update_failed_booking'),
    path('check-cancellation-status',CheckCancellationStatus.as_view(), name='check_cancellation_status'),
    path('update-ticket-status',UpdateTicketStatus.as_view(), name='update-ticket-status')
]

