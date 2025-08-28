from .models import *
from rest_framework import serializers
from tools.time_helper import time_converter
    
class LookupSupplierIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupSupplierIntegration
        exclude = ('deleted_at','is_deleted','created_at','modified_at')

class SupplierIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierIntegration
        exclude = ('deleted_at','is_deleted','created_at','modified_at')

  
class SupplierListSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierIntegration
        fields=("id", "name")


class SupplierIntegrationGetSerializer(serializers.ModelSerializer):
    data = serializers.SerializerMethodField()
    country_detail = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    modified_at = serializers.SerializerMethodField()

    class Meta:
        model = SupplierIntegration
        fields = ['id', 'name','country', 'icon_url', 'data', 'integration_type','lookup_supplier','is_active','created_at', 'modified_at', 'country_detail','is_init']

    def get_data(self , obj):
        supplier_integration_data = obj.data
        lookup_supplier_data_obj  = obj.lookup_supplier
        if lookup_supplier_data_obj:
            integration_keys = lookup_supplier_data_obj.keys
            for key in integration_keys:
                if key not in supplier_integration_data:
                    supplier_integration_data[key] = None
        return supplier_integration_data
    

    def get_country_detail( self , obj):
        return {"country_name":str(obj.country.lookup.country_name), "country_code":str(obj.country.lookup.country_code)} if obj.country else None
    def get_created_at(self, obj):
        return time_converter.to_date_time(obj.created_at, stringify=True)
    def get_modified_at(self, obj):
        return time_converter.to_date_time(obj.modified_at, stringify=True)
    
    



class SupplierIntegratingSerializer(serializers.ModelSerializer):
    supplier_id = serializers.UUIDField(source='id')
    supplier_name = serializers.CharField(source='name')
    class Meta:
        model = SupplierIntegration
        fields = ['supplier_id', 'supplier_name', 'icon_url','integration_type']
class OrganizationSupplierIntegerationSerializer(serializers.ModelSerializer):

    class Meta:
        model = OrganizationSupplierIntegeration
        fields = []
        
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add the supplier integeration data directly without nesting
        supplier_data = SupplierIntegratingSerializer(instance.supplier_integeration).data
        supplier_data['status'] = instance.is_enabled
        return supplier_data
    
    



        
        
    


    


