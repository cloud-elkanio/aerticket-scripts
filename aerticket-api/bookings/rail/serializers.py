from rest_framework import serializers
from .models import RailOrganizationDetails

class RailOrganizationDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = RailOrganizationDetails
        fields = [
            'id', 
            'agency_name', 
            'email', 
            'pan', 
            'dob', 
            'address', 
            'country', 
            'state', 
            'city', 
            'pincode', 
            'status',
            'is_active',
            'agent_id',
            'irctc_id'
        ]

class UpdateAgentIrctcSerializer(serializers.ModelSerializer):
    class Meta:
        model = RailOrganizationDetails
        fields = ['agent_id', 'irctc_id']
