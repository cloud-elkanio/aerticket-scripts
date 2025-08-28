from .models import *
from rest_framework import serializers
from datetime import datetime, timezone  
from rest_framework.pagination import PageNumberPagination
from integrations.suppliers.models import SupplierIntegration
from django.db.models import Q
from users.models import Country,LookupAirline
from users.models import LookupAirports
from users.models import LookupCountry
class LookUpAirlineSerializersList(serializers.ModelSerializer):
    class Meta:
        model = LookupAirline
        exclude = ['is_deleted','deleted_at','created_at','modified_at']
        


class SupplierIntegrationSerializers(serializers.ModelSerializer):
    supplier_country_name = serializers.SerializerMethodField()

    class Meta:
        model = SupplierIntegration
        fields = ['name','id','supplier_country_name']
        
    def get_supplier_country_name(self, obj):
        return f"{obj.name}-{obj.country.lookup.country_name}"

class AirlineDealsSerializers(serializers.ModelSerializer):
    # source = serializers.SerializerMethodField()
    # destination = serializers.SerializerMethodField()
    
    class Meta:
        model = AirlineDeals
        fields = "__all__"
        
    def get_airport_name_from_code(self, code:str):
        try:
            airport_name = LookupAirports.objects.get(code=code).name
        except LookupAirports.DoesNotExist:
            return code
        return airport_name
        
    def get_country_code_from_code(self, code:str):
        try:
            airport_name = LookupCountry.objects.get(country_code=code).country_name
        except LookupCountry.DoesNotExist:
            return code
        return airport_name
    
    def validate(self, data):
        """
        checking if the data is already present in the table
        """
        request = self.context.get('request')
        if request.method  == "PUT":
            return data
        supplier = data.get('supplier')
        cabin= data.get('cabin')
        deal_type = data.get('deal_type')
        airline = data.get('airline')
        if AirlineDeals.objects.filter(airline_id=airline,supplier_id=supplier,cabin=cabin,deal_type=deal_type,status=True):
            raise serializers.ValidationError(f'the airline deal is already added  please check this value supplier = {supplier}'\
                f'  cabin = {cabin}, deal_type= {deal_type},  airline={airline}')
        return data
        
    def to_representation(self, instance):
        data =  super().to_representation(instance)
        data['airline_name'] = instance.airline.name
        data['supplier_name'] = instance.supplier.name
        data['source'] = self.restructure(instance.source) if instance.source else None
        data['destination'] = self.restructure(instance.destination) if instance.destination else None
        data['source_country_code'] = self.country_restructure(instance.source_country_code) if instance.source_country_code else None
        data['destination_country_code'] = self.country_restructure(instance.destination_country_code) if instance.destination_country_code else None
        
        def format_timestamp(timestamp):
            if timestamp:
                timestamp /= 1000  
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)  
                return dt.strftime('%Y-%m-%d %H:%M:%S')  
            return None
        if data.get('valid_till'):
            data['valid_till'] = format_timestamp(data['valid_till'])

        return data
    
    def restructure(self, obj_list):
        source_list = []
        for source  in  obj_list:
            source_list.append(
                {
                    "code":source,
                    "name":self.get_airport_name_from_code(source)
                }
            )
        return source_list
    
    def country_restructure(self, obj_list):
        source_list = []
        for source  in  obj_list:
            source_list.append(
                {
                    "code":source,
                    "name":self.get_country_code_from_code(source)
                }
            )
        return source_list
    
class SupplierDealManagementSerializers(serializers.ModelSerializer):
    class Meta:
        model = SupplierDealManagement
        fields = "__all__"
    
    def get_airport_name_from_code(self, code:str):
        try:
            airport_name = LookupAirports.objects.get(code=code).name
        except LookupAirports.DoesNotExist:
            return code
        return airport_name
        
    def get_country_code_from_code(self, code:str):
        try:
            airport_name = LookupCountry.objects.get(country_code=code).country_name
        except LookupCountry.DoesNotExist:
            return code
        return airport_name
 
    def validate(self, data):
        """
        checking if the data is already present in the table
        """
        request = self.context.get('request')
        if request.method  == "PUT":
            return data
        supplier = data.get('supplier')
        cabin= data.get('cabin')
        deal_type = data.get('deal_type')
        airline = data.get('airline')
        if SupplierDealManagement.objects.filter(airline_id=airline,supplier_id=supplier,cabin=cabin,deal_type=deal_type,status=True):
            raise serializers.ValidationError(f'the airline deal is already added  please check this value supplier = {supplier}'\
                f'  cabin = {cabin}, deal_type= {deal_type},  airline={airline}')
        return data
        
    def to_representation(self, instance):
        data =  super().to_representation(instance)
        data['airline_name'] = instance.airline.name
        data['supplier_name'] = instance.supplier.name
        data['source'] = self.restructure(instance.source) if instance.source else None
        data['destination'] = self.restructure(instance.destination) if instance.destination else None
        data['source_country_code'] = self.country_restructure(instance.source_country_code) if instance.source_country_code else None
        data['destination_country_code'] = self.country_restructure(instance.destination_country_code) if instance.destination_country_code else None
        
        def format_timestamp(timestamp):
            if timestamp:
                timestamp /= 1000  
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)  
                return dt.strftime('%Y-%m-%d %H:%M:%S')  
            return None
        if data.get('valid_till'):
            data['valid_till'] = format_timestamp(data['valid_till'])

        return data
    
    def restructure(self, obj_list):
        source_list = []
        for source  in  obj_list:
            source_list.append(
                {
                    "code":source,
                    "name":self.get_airport_name_from_code(source)
                }
            )
        return source_list
    
    def country_restructure(self, obj_list):
        source_list = []
        for source  in  obj_list:
            source_list.append(
                {
                    "code":source,
                    "name":self.get_country_code_from_code(source)
                }
            )
        return source_list
    
class CountrySerializers(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id']
        
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['name'] = instance.lookup.country_name
        return data
    
class FlightSupplierFiltersSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightSupplierFilters
        fields = '__all__'

class FlightSupplierFiltersSerializerGet(serializers.ModelSerializer):
    supplier_name = serializers.SerializerMethodField()
    class Meta:
        model = FlightSupplierFilters
        exclude = ('is_deleted','deleted_at')
    def get_supplier_name(self, obj):
        return obj.supplier.name
