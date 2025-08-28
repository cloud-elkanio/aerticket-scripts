import os
from dotenv import load_dotenv
from django.urls import include, path, re_path
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from .custom_schema_generator import CustomOpenAPISchemaGenerator
from django.conf import settings
from . import authentication_views
from django.conf.urls.static import static

load_dotenv()


include_patterns = [
    path('auth/',include('documentation.authentication_urls')),
    path('flights/',include('documentation.flight_urls')),
]

redoc_include_patterns = [
    path('/api/auth/token/refresh',authentication_views.RefreshTokenView.as_view(), name='Refresh Access Token'),
    path('/api/flights/',include('documentation.flight_urls')),
]

logo_url = settings.COMPANY_LOGO_URL

schema_view = get_schema_view(
    openapi.Info(
        title= os.getenv('COMPANY_NAME','') + " Consolidated API Documentation",
        default_version='v1',
        description="API Documentation - Private Access",
        contact=openapi.Contact(email= os.getenv('CONTACT_EMAIL','amjad@elkanio.com')),
        x_logo={
            "url": logo_url,
            "backgroundColor": "#FFFFFF",
            "altText": "Company Logo"
        },
    ),
    public=False,  # Set to False to restrict access
    authentication_classes=[SessionAuthentication],
    permission_classes=[IsAuthenticated],
    generator_class=CustomOpenAPISchemaGenerator,
    patterns=redoc_include_patterns,  # Only these patterns are included
    url = os.getenv('BOOKING_URL')
)
urlpatterns = [
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0),
         name='schema-redoc'),
] + include_patterns 
