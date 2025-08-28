
from django.contrib import admin
from django.urls import path,include
from users import views
from .views import PaymentView, RazorCallbackApi, SearchAirport, CreditBalanceView, SearchAirline
from .analytics import UserJourneyView,UserJourneyDetailsView

urlpatterns = [
    path('payment', PaymentView.as_view(), name='payment'),
    path('razor-callback/status', RazorCallbackApi.as_view(), name='razor-callback-status'),
    path('search_airport',SearchAirport.as_view(), name = 'flight'),
    path('get_credit_balance', CreditBalanceView.as_view(), name='Get Credit Balance'),
    path('search_airline', SearchAirline.as_view(), name='flight'),
    path('user_journey', UserJourneyView.as_view(), name='flight'),
    path('user_journey_details', UserJourneyDetailsView.as_view(), name='flight'),
    
]
