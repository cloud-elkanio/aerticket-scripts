import time
import xml.etree.ElementTree as ET
import threading
import uuid
from itertools import chain
import traceback
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from users.models import SupplierIntegration
from vendors.buses.flyshop.api import get_city_list
from common.models import LookupCountry



class Manager():
    def __init__(self, **kwargs):
        self.creds = kwargs['credentials']
        self.vendor_id = "VEN_"+str(kwargs['uuid'])
        self.vendor_uuid = kwargs['uuid']

        self.mongo_client = kwargs['mongo_client']

    def cities_by_name(self, **kwargs):
        city_list_doc = kwargs['CityName']
        filtered_cities = [
            {"CityID": city["CityID"], "CityName": city["CityName"]}
            for city in city_list_doc.get("data", [])
            if city["CityName"].startswith("Ban")
        ]

        # Print results
    def name(self):
        return "FlyShop"
    
    def create_city_list(self):
        try:
            response = get_city_list(
                **{'username': self.creds['username'],
                 'password': self.creds['password'],
                 'request_id': uuid.uuid4(),
                 'ip_address': self.creds['ip_address'],
                 'IMEI_number': self.creds['IMEI_number'],
                 'base_url': self.creds['base_url']}
            )
            X = LookupCountry.objects.filter(country_code = 'IN').first()
            CityDetails =response.get("CityDetails",[])
            converted = [{"city_id":x.get('CityID'),"city_name":x.get('CityName'),'country':X} for x in CityDetails]
            return converted
        except:
            return []



