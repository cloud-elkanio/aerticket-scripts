from .views import *
from django.urls import path

urlpatterns = [
    path("rail/create_request",CreateRequest.as_view(), name='create_request'),
    path('rail/list-agencies/', RailOrganizationDetailsList.as_view(), name='rail-list'),
    path('rail/update-agency/<str:pk>/', UpdateAgentIrctcAPIView.as_view(), name='update-agency'),
]