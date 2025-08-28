"""
URL configuration for api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,TokenVerifyView,TokenBlacklistView
    
)



from django.urls import re_path
from rest_framework import permissions
# from drf_yasg.views import get_schema_view
# from drf_yasg import openapi



# schema_view = get_schema_view(
#     openapi.Info(
#         title="Snippets API",
#         default_version='v1',
#         description="Test description",
#         terms_of_service="https://www.google.com/policies/terms/",
#         contact=openapi.Contact(email="contact@snippets.local"),
#         license=openapi.License(name="BSD License"),
#     ),
#     public=True,
#     permission_classes=(permissions.AllowAny,),
# )

from django.contrib.auth import views as auth_views
urlpatterns = [
    # path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    # path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    # path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('admin/auth/', admin.site.urls),
    path('baton/', include('baton.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('', include('users.urls')),
    path('integeration/', include('integrations.notification.urls')),
    path('', include('integrations.general.urls')),
    path('', include('integrations.suppliers.urls')),
    path('', include('integrations.template.urls')),

    # cms
    path("", include("cms.flight.urls")),
    path("", include("cms.hotel.urls")),
    path("", include("cms.holiday.urls")),
    
    
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),


    # pms
    path("", include("pms.holiday_app.urls")),
    path("", include("pms.visa_app.urls")),


    # web
    path("", include("web.holiday.urls")),
    path("", include("web.hotel.urls")),
    path("", include("web.flight.urls")),

    # common
    path("", include("common.urls")),
    path("", include("web.visa.urls")),

    #accounting
    path("", include("accounting.flight.urls")),
    path("", include("accounting.hotel.urls")),
    path("", include("accounting.holiday.urls")),
    path("", include("accounting.shared.urls")),
    path("", include("accounting.reports.urls")),

    #booking
    path("", include("bookings.flight.urls")),

    path("", include("giata.urls")),



]

