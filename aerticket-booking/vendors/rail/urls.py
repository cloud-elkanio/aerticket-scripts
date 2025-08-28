from django.urls import path
from .views import CheckRailOrganizationStatusView, CheckPaymentPermissionView, NotificationView

urlpatterns = [
    path('check-rail-organization-status/', CheckRailOrganizationStatusView.as_view(), name='check_rail_organization_status'),
    path('check-payment-permission/', CheckPaymentPermissionView.as_view(), name='check_rail_organization_status'),
    path('notification/', NotificationView.as_view(), name='check_rail_organization_status')
    ]