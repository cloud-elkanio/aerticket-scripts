from datetime import datetime, timedelta
from django.shortcuts import render
from base64 import b64encode
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import *
import requests
import xmltodict
import json
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
import threading
from .models import GiataCountry,GiataDestination
import sys
import traceback
from django.utils import timezone
from integrations.suppliers.models import SupplierIntegration
from fuzzywuzzy import fuzz
import pandas as pd
import time
from requests.auth import HTTPBasicAuth


#TOKEN
def basic_auth(username,password):
    auth_string = f"{username}:{password}"
    token = b64encode(auth_string.encode('utf-8')).decode('ascii')
    return token

class FetchCountriesView(APIView):
    permission_classes =[]
    authentication_classes = []

    def post(self, request):
        supplier_obj = SupplierIntegration.objects.get(name = 'GIATA')
        username = supplier_obj.data['username']
        password = supplier_obj.data['password']
        updation_time_limit = supplier_obj.data['updation_time_limit']
        token = basic_auth(username,password)
        base_url = supplier_obj.data['base_url']
        # #===================================================================================
        thread = threading.Thread(target =self.CountryDestinationCity,
                                  kwargs={
                                        'token': token,
                                        'base_url': base_url,
                                        'updation_time_limit':updation_time_limit
                                          })      
        thread.start()  
        return Response({'message': 'Properties fetch started! Check logs for progress.'}, status=200)
        #===================================================================================

    def CountryDestinationCity(self,token,base_url,updation_time_limit):
        loc_time = datetime.now()

        data = {
                "error_message":"CountryDestinationCity start again ",
                "timestamp":loc_time.strftime("%Y-%m-%d %H:%M:%S"),
                "traceback": "",
                "giata_id":"",
                "url":loc_time.strftime("%Y-%m-%d %H:%M:%S")
            }
        self.SaveErrorLog(**data)
        current_date = datetime.now()
        date_before_limit = current_date - timedelta(days=updation_time_limit)
        epoch_time_limit = int(date_before_limit.timestamp())

        country_url = base_url+'geography'
        try:
            payload = {}
            headers = {
            'Authorization': 'Basic '+token
            }
            response = requests.request("POST", country_url, headers=headers, data=payload)
            res_dict = xmltodict.parse(response.text)
            json_Data = json.dumps(res_dict, indent=4)
            countries = res_dict.get('geography', {}).get('countries', {}).get('country', [])
            incoming_country = []
            if countries:
                for country in countries:
                    countries_name = country.get('@countryName', None)
                    countries_code = country.get('@countryCode', None)
                    country_obj = GiataCountry.objects.filter(country_name = countries_name).first()
                    incoming_country.append(countries_code)
                    if not country_obj or country_obj.lastupdated_epoch < epoch_time_limit:
                        lastupdated_epoch = int(time.time())
                        giata_country,_ = GiataCountry.objects.update_or_create(
                                                country_code=countries_code,
                                                defaults = {"country_name":countries_name,
                                                            "lastupdated_epoch" : lastupdated_epoch}
                                                )
                GiataCountry.objects.exclude(country_code__in =incoming_country).delete()
                self.DestinationCreation(countries,token,base_url,updation_time_limit)
        except Exception as e:
            exc_type , exc_value, exc_traceback = sys.exc_info()
            formatted_traceback = ','.join(traceback.format_exception(exc_type,exc_value,exc_traceback))
            data = {
                "error_message":str(e),
                "timestamp":timezone.now(),
                "traceback": formatted_traceback,
                "giata_id":base_url,
                "url":base_url
            }
            self.SaveErrorLog(**data)

    def DestinationCreation(self,countries,token,base_url,updation_time_limit):
        try:
            current_date = datetime.now()
            date_before_limit = current_date - timedelta(days=updation_time_limit)
            epoch_time_limit = int(date_before_limit.timestamp())

            if countries:
                for country in countries:
                    destinations = country.get('destinations', {}).get('destination', [])
                    country_name  = country['@countryName']
                    country_codee = country['@countryCode']
                    giata_country = GiataCountry.objects.get(country_code = country_codee)
                    if giata_country:
                        incoming_destination = []
                        if not isinstance(destinations,list):
                            destinations = [destinations]
                        if destinations:
                            for destination in destinations:
                                des_id = destination.get('@destinationId', None)
                                des_name = destination.get('@destinationName', None)
                                incoming_destination.append(des_id)
                                destination_obj = GiataDestination.objects.filter(destination_id = des_id).first()
                                if not destination_obj or destination_obj.lastupdated_epoch < epoch_time_limit:
                                    lastupdated_epoch =  int(time.time())
                                    giata_des, _ = GiataDestination.objects.update_or_create(
                                    country_id=giata_country, 
                                    destination_id=des_id,
                                    defaults={
                                        "destination_name": des_name,
                                        "lastupdated_epoch": lastupdated_epoch
                                        }
                                    )
                            if incoming_destination:
                                GiataDestination.objects.filter(country_id=giata_country).exclude(destination_id__in=incoming_destination).delete()
                self.CityCreation(countries,token,base_url,updation_time_limit)
        except Exception as e:
            exc_type , exc_value, exc_traceback = sys.exc_info()
            formatted_traceback = ','.join(traceback.format_exception(exc_type,exc_value,exc_traceback))
            data_field= {"country_name":country_name}
            data = {
                "error_message":str(e),
                "timestamp":timezone.now(),
                "traceback": formatted_traceback,
                "variables":data_field
            }
            self.SaveErrorLog(**data)
    def CityCreation(self,countries,token,base_url,updation_time_limit):
        try:
            current_date = datetime.now()
            date_before_limit = current_date - timedelta(days=updation_time_limit)
            epoch_time_limit = int(date_before_limit.timestamp()) 
            giata_country_obj_list = []
            for country in countries:
                destinations = country.get('destinations', {}).get('destination', [])
                if not isinstance(destinations,list):
                    destinations = [destinations]

                for destination in destinations:
                    incoming_city = []
                    des_id = destination.get('@destinationId')
                    des_name = destination.get('@destinationName', None)
                    if des_id:
                        giata_des_id = GiataDestination.objects.get(destination_id  = des_id)
                    cities = destination.get('cities', {}).get('city', [])
                    if not isinstance(cities,list):
                        cities = [cities]
                    if cities:  
                        for city in cities:
                            countries_city_id = city.get('@cityId', None)
                            countries_city_name = city.get('@cityName', None)
                            incoming_city.append(countries_city_id)
                            city_obj = GiataCity.objects.filter(city_id = countries_city_id,destination_id__destination_id =des_id).first()
                            if not city_obj or city_obj.lastupdated_epoch < epoch_time_limit:
                                giata_country_city, _ = GiataCity.objects.update_or_create(
                                city_id=countries_city_id,
                                defaults={
                                    "destination_id": giata_des_id,
                                    "city_name": countries_city_name
                                    }
                                )
                                giata_country_obj_list.append(giata_country_city)
                        GiataCity.objects.filter(destination_id=giata_des_id).exclude(city_id__in=incoming_city).delete()
            country_code_list = GiataCountry.objects.values_list('country_code', flat= True)
            self.GetGiataIds(giata_country_obj_list,token,base_url)

        except Exception as e:
            exc_type , exc_value, exc_traceback = sys.exc_info()
            formatted_traceback = ','.join(traceback.format_exception(exc_type,exc_value,exc_traceback))
            data_field = {"des_id":des_id,
                "des_name":des_name}
            data = {
                "error_message":str(e),
                "timestamp":timezone.now(),
                "traceback": formatted_traceback,
                "variables": data_field
            }
            self.SaveErrorLog(**data)
    
    
    def GetGiataIds(self,giata_country_obj_list,token,base_url):
        try:
            for city_obj in giata_country_obj_list:
                property_url = f"{base_url}properties/city/{city_obj.city_id}"
                headers = {
                'Authorization': 'Basic '+token
                }
                response = requests.get(property_url, headers=headers)
                res_dict = xmltodict.parse(response.text)
                json_Data = json.dumps(res_dict, indent=4)
                if res_dict['properties'] != None:
                    properties = res_dict['properties']['property']
                    if isinstance(properties,dict):
                        properties = [properties]
                    for giata in properties:
                        giata_id  = giata['@giataId']
                        self.GetProperties(giata_id,token,city_obj,base_url)
                    GiataCity.objects.filter(id=city_obj.id).update(lastupdated_epoch=int(time.time())) 
            data = {
                "error_message":"Giata loop completed"
            }
            self.SaveErrorLog(**data)
        except Exception as e:
            exc_type , exc_value, exc_traceback = sys.exc_info()
            formatted_traceback = ','.join(traceback.format_exception(exc_type,exc_value,exc_traceback))
            data = {
                "error_message":str(e),
                "timestamp":timezone.now(),
                "traceback": formatted_traceback,
                "giata_id":giata_id,
                "url":base_url
            }
            self.SaveErrorLog(**data)
    def GetProperties(self,giata_id,token,giata_country_city,base_url):
        try:
            loc_time = datetime.now()
            data = {
                    "error_message":"GetProperties start again ",
                    "timestamp":loc_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "traceback": "",
                    "giata_id":"",
                    "url":loc_time.strftime("%Y-%m-%d %H:%M:%S")
                }
            self.SaveErrorLog(**data)
            
            property_url = f"{base_url}properties/{giata_id}"
            # base_url = "https://multicodes.giatamedia.com/webservice/rest/1.0/properties/16089"
            headers = {
            'Authorization': 'Basic '+token
            }
            response = requests.get(property_url, headers=headers)
            res_dict = xmltodict.parse(response.text)
            property = res_dict['properties']['property']
            if property:
                json_Data = json.dumps(res_dict, indent=4)
                email_data = property.get('emails', {}).get('email', [])
                if not isinstance(email_data, list):
                    email_data = [email_data]
                phone_data = property.get('phones', {}).get('phone', [])
                if not isinstance(phone_data, list):
                    phone_data = [phone_data]
                address_data = property.get('addresses', {}).get('address', {}).get('addressLine', [])
                if not isinstance(address_data, list):
                    address_data = [address_data]

                property_obj, created = GiataProperties.objects.update_or_create(
                        giata_id=property.get('@giataId', None),
                        defaults = {
                            "city_id": giata_country_city,
                            "last_updated" : property.get('@lastUpdate', None),
                            "name" : property.get('name', ''),
                            "street" : property.get('addresses', {}).get('address', {}).get('street', ''),
                            "address" :address_data,
                            "postal_code" : property.get('addresses', {}).get('address', {}).get('postalCode', ''),
                            "po_box" : property.get('addresses', {}).get('address', {}).get('postalCode', ''),
                            "phone" : phone_data,
                            "email" : email_data,
                            "latitude" : property.get('geoCodes', {}).get('geoCode', {}).get('latitude', None),
                            "longitude" : property.get('geoCodes', {}).get('geoCode', {}).get('longitude', None)
                                    }
                        )
                self.GetImages(giata_id,token,property_obj)

                property_codes = property.get('propertyCodes')
                if property_codes is not None:
                    provider_data = property_codes.get('provider',[])
                    if provider_data:
                        if isinstance(provider_data,dict):
                            provider_data = [provider_data]
                        for single_provider in provider_data:
                            code_type = single_provider.get('code',[])
                            if isinstance(code_type,dict):
                                code_type = [code_type]                        
                            GiataProviderCode.objects.update_or_create(property_id=property_obj,
                                provider_name = single_provider.get('@providerCode',''),
                                provider_type = single_provider.get('@providerType',''),
                                provider_code = [code.get('value','') for code in code_type]
                                )
                property_chains = property.get('chains')
                if property_chains is not None:
                    provider_chain_data = property_chains.get('chain',[])
                    if provider_chain_data:
                        if isinstance(provider_chain_data,dict):
                            provider_chain_data = [provider_chain_data]
                        for single_chain_provider in provider_chain_data: 
                            GiataChain.objects.update_or_create(
                                property_id=property_obj,
                                chain_name = single_chain_provider.get('@chainName',''),
                                chain_id = single_chain_provider.get('@chainId',''),
                                chain_code = single_chain_provider.get('@chainCode','')
                                    )
            
                    
        except Exception as e:
            exc_type , exc_value, exc_traceback = sys.exc_info()
            formatted_traceback = ','.join(traceback.format_exception(exc_type,exc_value,exc_traceback))
            data = {
                "error_message":str(e),
                "timestamp":timezone.now(),
                "traceback": formatted_traceback,
                "giata_id":giata_id,
                "url":base_url
            }
            self.SaveErrorLog(**data)

    def GetImages(self,giata_id, token,property_obj):
        try:
            url = f"https://ghgml.giatamedia.com/webservice/rest/1.0/items/{giata_id}"
            headers = {
                'Authorization': 'Basic '+token
            }
            response = requests.get(url,headers=headers)
            res_dict = xmltodict.parse(response.content)
            images_list = res_dict.get('result',{}).get('item',{}).get('images',{}).get('image',[])
            text_obj = res_dict.get('result',{}).get('item',{}).get('texts',{}).get('text',{})
            if text_obj:
                text_url= text_obj['@xlink:href']
                if text_url:
                    self.GetTexts(text_url,token,property_obj)
                if isinstance(images_list,dict):
                    images_list = [images_list]
                for image in images_list:
                    type_data = image.get('@type','')
                    size_list =image.get('sizes',{}).get('size',[])
                    if size_list:
                        list_sizes = []
                        for size_dict in size_list:
                            img_list = {
                                    'maxwidth':size_dict.get('@maxwidth',''),'width': size_dict.get('@maxwidth','@width'),
                                        'height':size_dict.get('@height','') , 'filesize':size_dict.get('@filesize',''),
                                        'url':size_dict.get('@xlink:href','')  
                                        }
                            list_sizes.append(img_list)
                        GiataPropertyImage.objects.update_or_create(
                            propert_id = property_obj,
                            image_type = type_data,
                            image_list = list_sizes
                        )

        except Exception as e:
            exc_type , exc_value, exc_traceback = sys.exc_info()
            formatted_traceback = ','.join(traceback.format_exception(exc_type,exc_value,exc_traceback))
            data = {
                "error_message":str(e),
                "timestamp":timezone.now(),
                "traceback": formatted_traceback,
                "giata_id":giata_id,
                "url":url
            }
            self.SaveErrorLog(data)
    
    def GetTexts(self,text_url,token,property_obj):
        try:
            url = text_url
            headers ={
                'Authorization': 'Basic '+token
            }
            response = requests.get(url,headers=headers)
            res_dict = xmltodict.parse(response.content)
            if res_dict:
                section_data = res_dict.get('result',{}).get('item',{}).get('texts',{}).get('text',{}).get('sections',{}).get('section',[])

                if section_data:
                    if isinstance(section_data,dict):
                        section_data = [section_data]
                    for section in section_data:
                        if section:
                            GiataTexts.objects.update_or_create(
                                propert_id = property_obj,
                                type = section.get('@type',''),
                                title = section.get('title',''),
                                paragraph = section.get('para','')
                            )
        except Exception as e:
            exc_type , exc_value, exc_traceback = sys.exc_info()
            formatted_traceback = ','.join(traceback.format_exception(exc_type,exc_value,exc_traceback))
            data = {
                "error_message":str(e),
                "timestamp":timezone.now(),
                "traceback": formatted_traceback,
                "giata_id":url,
                "url":url
            }
            self.SaveErrorLog(**data)
         
    def SaveErrorLog(self,**kwargs):
        try:
            GiataErrorLog.objects.create(error_message=kwargs.get('error_message'), 
                                        time_date=kwargs.get('timestamp'),
                                        traceback = kwargs.get('traceback'),
                                        giata_id = kwargs.get('giata_id'),
                                        base_url = kwargs.get('url'),
                                        variables = kwargs.get('variables')
                                        )
        except Exception as e:
            print(f"Error occurred during saving error log: {str(e)}")


class UpdatePropertyRating(APIView):
    print("enter class")
    permission_classes =[]
    authentication_classes = []
    def post(self, request):
        supplier_obj = SupplierIntegration.objects.get(name = 'GIATA')
        username = supplier_obj.data['username']
        password = supplier_obj.data['password']
        token = basic_auth(username,password)
        base_url = "https://multicodes.giatamedia.com/webservice/rest/1.latest/properties/"
        # #===================================================================================
        thread = threading.Thread(target =self.ListRating,
                                  kwargs={
                                        'token': token,
                                        'base_url': base_url
                                          })      
        thread.start()  
        return Response({'message': 'Properties Rating fetch started! Check logs for progress.'}, status=200)
        #===================================================================================

    def ListRating(self,token,base_url):
        try:
            giata_ids = GiataProperties.objects.all().values_list('giata_id',flat=True)
            for giata_id in giata_ids:
                rating_url = f'{base_url}{giata_id}'
                headers = {
                'Authorization': 'Basic '+token
                }
                response = requests.get(rating_url,headers=headers)
                res_dict = xmltodict.parse(response.text)
                json_Data = json.dumps(res_dict, indent=4)
                self.SaveRating(res_dict,giata_id)
        except Exception as e:
            exc_type , exc_value, exc_traceback = sys.exc_info()
            formatted_traceback = ','.join(traceback.format_exception(exc_type,exc_value,exc_traceback))
            data = {
                "error_message":str(e),
                "timestamp":timezone.now(),
                "traceback": formatted_traceback,
                "giata_id":base_url,
                "url":base_url
            }
            SaveErrorLog(**data)
    def SaveRating(self, res_dict,giata_id):
        try:
            ratings = res_dict.get('properties', {}).get('property', {}).get('ratings', {}).get('rating', None)
            if ratings:
                if isinstance(ratings,list):
                    rating_list = [int(rating.get('@value')) for rating in ratings if '@value' in rating]
                    rating_value = sum(rating_list) / len(rating_list)
                else:
                    rating_value = ratings.get('@value')
                properties = GiataProperties.objects.filter(giata_id = giata_id).update(rating = rating_value)

        except Exception as e:
            exc_type , exc_value, exc_traceback = sys.exc_info()
            formatted_traceback = ','.join(traceback.format_exception(exc_type,exc_value,exc_traceback))
            data = {
                "error_message":str(e),
                "timestamp":timezone.now(),
                "traceback": formatted_traceback,
            }
            SaveErrorLog(**data)

def SaveErrorLog(**kwargs):
    try:
        GiataErrorLog.objects.create(error_message=kwargs.get('error_message'), 
                                    timestamp=kwargs.get('timestamp'),
                                    traceback = kwargs.get('traceback'),
                                    giata_id = kwargs.get('giata_id'),
                                    base_url = kwargs.get('url'),
                                    variables = kwargs.get('variables')
                                    )
    except Exception as e:
        print(f"Error occurred during saving error log: {str(e)}")

