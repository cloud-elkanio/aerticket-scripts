from .views import TotalConfirmedBookingApiView, TotalAmountBookingConfirmedApiView,TotalBookingApiView, \
                    TotalBookingChartApiView, StaffConfirmedBookingPieChartApiView, StaffBookingLineChartAPIView,\
                    AirlineConfirmedBookingPieChartApiView,\
                    CommisionAPIView, OrganizationCountAPIView, RegistrationCountAPIView, TotalBookingsBarAndLineAmountApiView,\
                    VendorConfirmedBookingAmountPieChartApiView, VendorAirlineConfirmedBookingBarChartApiView, SalesPerformanceApiView, SalesPerformanceActiveOrganizationApiView,\
                    SalesPerformanceInactiveOrganizationApiView, TotalFailedToRejectedBookingApiView, TotalFailedToConfirmedBookingApiView,TotalFailedtoRejectedBookingChartApiView,\
                    TotalFailedtoConfirmedBookingChartApiView, ConfirmedBookingsBarAndLineAmountApiView, FailedAndRejectedBookingsBarAndLineAmountApiView
from .finance_team_performance import BillingStaffPerformanceApi,AirlineVsSupplierPerformanceApi,SupplierVsAirlinePerformanceApi,PaymentGatewayStackedChart
from django.urls import path
from rest_framework.routers import DefaultRouter


router = DefaultRouter()

urlpatterns = [
    path('accounting/reports/total-confirmed', TotalConfirmedBookingApiView.as_view(), name='total-flight-confirmed'),
    path('accounting/reports/total-amount-confirmed', TotalAmountBookingConfirmedApiView.as_view(), name='total-flight-booking'),
    path('accounting/reports/total-booking', TotalBookingApiView.as_view(), name='total-flight-booking'),
    path('accounting/reports/total-commision', CommisionAPIView.as_view(), name='total-commision'),
    path('accounting/reports/total-booking-chart', TotalBookingChartApiView.as_view(), name='total-flight-booking-chart'),
    path('accounting/reports/staff-booking-pie-chart', StaffConfirmedBookingPieChartApiView.as_view(), name='staff-flight-booking-pie-chart'),
    path('accounting/reports/airline-confirmed-booking-pie-chart', AirlineConfirmedBookingPieChartApiView.as_view(), name='airline-confirmed-booking-pie-chart'),
    path('accounting/reports/staff-booking-line-chart', StaffBookingLineChartAPIView.as_view(), name='staff-flight-booking-line-chart'),
    path('accounting/reports/organization-count', OrganizationCountAPIView.as_view(), name='organization-count'),
    path('accounting/reports/registration-count', RegistrationCountAPIView.as_view(), name='registration-count'),
    path('accounting/reports/booking-bar-line-amount-chart', TotalBookingsBarAndLineAmountApiView.as_view(), name='booking-bar-line-amount-chart'),
    path('accounting/reports/vendor-confirmed-booking-pie-chart', VendorConfirmedBookingAmountPieChartApiView.as_view(), name='vendor-confirmed-booking-pie-chart'),
    path('accounting/reports/vendor-airline-confirmed-booking-bar-chart', VendorAirlineConfirmedBookingBarChartApiView.as_view(), name='vendor-airline-confirmed-booking-bar-chart'),
    path('accounting/reports/sales-performance-table', SalesPerformanceApiView.as_view(), name='sales-performance-table'),
    path('accounting/reports/sales-performance-active-organization', SalesPerformanceActiveOrganizationApiView.as_view(), name='sales-performance-organization'),
    path('accounting/reports/sales-performance-inactive-organization', SalesPerformanceInactiveOrganizationApiView.as_view(), name='sales-performance-organization'),
    path('accounting/reports/total-failed-rejected-booking', TotalFailedToRejectedBookingApiView.as_view(), name='total-failed-rejected-booking'),
    path('accounting/reports/total-failed-confirmed-booking', TotalFailedToConfirmedBookingApiView.as_view(), name='total-failed-confirmed-booking'),
    path('accounting/reports/total-failed-rejected-chart', TotalFailedtoRejectedBookingChartApiView.as_view(), name='total-failed-rejected-chart'),
    path('accounting/reports/total-failed-confirmed-chart', TotalFailedtoConfirmedBookingChartApiView.as_view(), name='total-failed-confirmed-chart'),
    path('accounting/reports/confrimed-booking-barline-chart', ConfirmedBookingsBarAndLineAmountApiView.as_view(), name='confrimed-booking-barline-chart'),
    path('accounting/reports/failed-rejeceted-barline-chart', FailedAndRejectedBookingsBarAndLineAmountApiView.as_view(), name='failed-rejeceted-barline-chart'),

    #finance_report
    path('billing-staff-performance', BillingStaffPerformanceApi.as_view(), name='billing-staff-performance'),
    path('airline-vs-supplier-performance', AirlineVsSupplierPerformanceApi.as_view(), name='airline-supplier-performance'),
    path('supplier-vs-airline-performance', SupplierVsAirlinePerformanceApi.as_view(), name='supplier-airline-performance'),
    path('payments-chart', PaymentGatewayStackedChart.as_view(), name='payments-chart'),




     
]

# urlpatterns += router.urls