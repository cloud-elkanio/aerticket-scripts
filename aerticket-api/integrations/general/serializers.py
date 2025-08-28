from .models import *
from rest_framework import serializers   

class IntegrationGetSerializer(serializers.ModelSerializer): 
    data = serializers.SerializerMethodField()
    class Meta:
        model = Integration
        fields = ['id', 'name', 'icon_url', 'data', 'lookup_integration','is_active']
    
    def get_data(self , obj):
        integration_data = obj.data
        lookup_data_obj  = obj.lookup_integration

        if isinstance(lookup_data_obj, list):
            for key in lookup_data_obj:
                if key not in integration_data:
                    integration_data[key] = None
        return integration_data
    
class LookupIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupIntegration
        exclude = ('deleted_at','is_deleted','created_at','modified_at')

class IntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Integration
        exclude = ('deleted_at','is_deleted','created_at','modified_at')