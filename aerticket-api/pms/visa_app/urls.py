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
    path('visa/category', VisaCategoryView.as_view()),
    path('visa/type', VisaTypeMasterView.as_view()),

    path('visa/sku', VisaSKUDetailView.as_view()),

    #get prodcut exist from and to countries
    path('country/filter', SearchFromToCountryView.as_view()),

    path('visa/change/status', VisaChangeStatusView.as_view()),
    path('visa/default/values', VisaDefaultValues.as_view()),

    #get all visa unser particular country id
    path('visa/sku/favourite', visaSKUHolidayFavouriteGet.as_view()),

    path('visa/favourite', VisaFavoriteView.as_view()),
    path('visa/queue', VisaQueueGet.as_view()),
    path('visa/enquiry/status', VisaEnquiryStatusGet.as_view()),
    path('supplier/name/list', GetSupplierListForVisEnquiry.as_view()),
    path('single_visa_slug/<str:slug>', SingleVisaUsingSlug.as_view()),
    # path('eazylink_supplier_table', Upload_data_to_eazylink_supplier_table.as_view()),

    
    
]

