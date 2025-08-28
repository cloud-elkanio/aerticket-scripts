from rest_framework.generics import (
    ListAPIView
)
from pms.holiday_app.models import HolidayFavourite
from ..serializers.holiday_favourite import HolidayFavouriteSerializer
from rest_framework import generics, status
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from uuid import UUID
class HolidayFavouriteListView(ListAPIView):
    authentication_classes=[]
    permission_classes=[]
    serializer_class = HolidayFavouriteSerializer
    
    def get_queryset(self):
        country_id = self.request.query_params.get('country_id', None)
        if country_id is not None:
            return HolidayFavourite.objects.filter(country_id=country_id)
