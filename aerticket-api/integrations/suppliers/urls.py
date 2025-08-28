from django.urls import path

from .views import *

urlpatterns = [
    path('supplier/integration/type',GetSupplierIntegrationType.as_view()),
    path('supplier/list',SupplierList.as_view()),
    path('lookup/supplier/integration/details',LookupSupplierIntegrationView.as_view()),
    path('supplier/integration/details',SupplierIntegrationView.as_view(), name = 'admin1space1panel_api1space1management'),
    path('control-panel/agency-master/api-integration/available-suppliers/<uuid:agency_id>', AgencyIntegeration.as_view()),
    path('control-panel/agency-master/api-integration/available-suppliers/status-update', UpdateSupplierStatus.as_view())

]

#