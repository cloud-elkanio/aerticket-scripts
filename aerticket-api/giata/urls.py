from django.urls import path
from .views import *

urlpatterns = [

    path('create/country/destination/city', FetchCountriesView.as_view(),  name='fetch_countries'),
    # path('property/get', FetchPropertiesView.as_view()),
    path('property/rating', UpdatePropertyRating.as_view()),


    

]
