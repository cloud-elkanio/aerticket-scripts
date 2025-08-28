from .views import *
from django.urls import path
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register(r'accounting/flight/deal-management', DealManagement)
router.register(r'accounting/flight/supplier-deal-management', SupplierDealManagementView)

urlpatterns = [
    path('accounting/flight/all-airlines/',AllAirLines.as_view(),name='all_airline'),
    path('accounting/flight/all-suppliers/',AllSupplierIntegrations.as_view(),name='all_airline'),
    path('accounting/flight/all-country/', AllCountryViewSet.as_view(), name='all-country'),
    path('accounting/flight/supplier/availability', FlightSupplierFiltersView.as_view())
]
urlpatterns+=router.urls