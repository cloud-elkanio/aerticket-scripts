# urls.py

from django.urls import path
from .views import *
urlpatterns = [
    path('web/visa/category', WebVisaCategoryView.as_view()),
    path('web/visa/sku', WebVisaSKUDetailView.as_view()),

    path("single/visa/<str:from_country>/<str:to_country>/<str:category>/<str:entry_type>/<uuid:country_id>",SingleVisaDetailView.as_view()),
    path("single/visa/slug/<str:slug>",SingleVisaDetailViewUsingSlug.as_view()),
    path('visa/enquiry', VisaEnquiryView.as_view()),
    path('web/visa/favourite', WebVisaFavoriteView.as_view()),
    path('visa/mydashboard', MyDashboardContent.as_view()),
    path('visa/category/country', CategoryBasedOnCountry.as_view()),

]
