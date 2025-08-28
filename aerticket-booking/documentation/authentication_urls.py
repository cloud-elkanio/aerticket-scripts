
from django.urls import path
from . import authentication_views

urlpatterns = [
    path('token',authentication_views.OutApiTokenObtainView.as_view(),name = 'Retrieve Refresh Token'),
    path('token/refresh', authentication_views.RefreshTokenView.as_view(), name='Refresh Access Token')
]