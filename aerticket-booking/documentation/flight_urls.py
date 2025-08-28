
from django.urls import path
from . import flight_views

urlpatterns = [

    path('search_airport', flight_views.OutAPISearchAirport.as_view(), name='Search Airport'),
    path('search_airline', flight_views.OutAPISearchAirline.as_view(), name='Search Airline'),
    path('credit-balance', flight_views.OutAPICreditBalanceView.as_view(), name='Get Credit Balance'),
    path('health/', flight_views.OutAPIHealthCheckView.as_view(), name='Health Check'),
    path('flight-search', flight_views.OutAPICreateSessionView.as_view(), name='flight_search'),
    path('flight-search-data', flight_views.OutAPIGetFlightsView.as_view(), name='flight_search_data'),
    path('fare-details', flight_views.OutAPIGetFareDetails.as_view(), name='fare_details_data'),
    path('air-pricing', flight_views.OutAPIAirPricing.as_view(), name='air_pricing'),
    path('flight-ssr', flight_views.OutAPIFlightsSSR.as_view(), name='flight_ssr'),
    path('create-booking', flight_views.OutAPICreateBooking.as_view(), name='create_booking'),
    path('check-hold', flight_views.OutAPICheckHold.as_view(), name='check_hold'),
    path('hold-booking', flight_views.OutAPIHoldBooking.as_view(), name='hold_booking'),
    path('purchase-status', flight_views.OutAPIPurchaseStatus.as_view(), name='purchase_status'),
    path('purchase', flight_views.OutAPIPurchase.as_view(), name='purchase'),
    path('repricing', flight_views.OutAPIRepricing.as_view(), name='repricing'),
    path('convert-hold-to-ticket', flight_views.OutAPIConvertHoldtoTicket.as_view(), name='convert_hold_to_ticket'),
    path('release-hold', flight_views.OutAPIReleaseHold.as_view(), name='release_hold'),
    path('ticket-status', flight_views.OutAPITicketStatus.as_view(), name='ticket_status'),
    path('cancellation-charges', flight_views.OutAPICancellationCharges.as_view(), name='cancellation_charges'),
    path('cancel-ticket', flight_views.OutAPICancelTicket.as_view(), name='cancel_ticket'),
    path('get-fare-rule', flight_views.OutAPIGetFareRule.as_view(), name='get_fare_rule'),
]