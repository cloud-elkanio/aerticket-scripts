from rest_framework import serializers
from common.models import LookupAirports, LookupAirline

class AirportSerializer(serializers.ModelSerializer):
    # Replace the foreign key (country) with the country name
    country = serializers.CharField(source='country.country_name', read_only=True)

    class Meta:
        model = LookupAirports
        fields = (
            "name",
            "code",
            "city",
            "country",   # Now displaying the country name
            "common",
            "latitude",
            "longitude",
        )

class LookupAirlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupAirline
        fields = ("name", "code")