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
from django.urls import path
from .views import *

urlpatterns = [
    path('holiday_product', HolidaySKUView.as_view()),
    path('lookup_country_get', GetWholeCountry.as_view()),
    path('holiday_theme', HolidayThemeView.as_view()),
    path('holiday_approval_status', HolidayApprovalAPI.as_view()),

    path('holiday_favourite', HolidayFavoriteView.as_view()),
    #get all sku holiday for favourite
    path('holiday_sku_favourite', SKUHolidayFavouriteGet.as_view()),

    path('holiday_default_values', HolidayDefaultValues.as_view()),
    path('holiday_queue', HolidayQueuesView.as_view(), name='holiday-queues-list'),
    path('holiday_queue/status', HolidayQueueStatusList.as_view()),
    path('update-queue-status', UpdateHolidayQueueStatusView.as_view(), ),
    path('holiday_suppliers', HolidaySupplierListView.as_view()),
    path('holiday-test-script', HolidayTestScript.as_view()),
    path('holiday-test-script2', HolidayTestScript2.as_view()),
    



]
