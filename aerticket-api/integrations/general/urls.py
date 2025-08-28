from django.urls import path

from .views import *

urlpatterns = [
    path('lookup/integration/details',LookUpIntegrationDetails.as_view()),
    path('integration/detail',IntegrationView.as_view()),
]