import time
import xml.etree.ElementTree as ET
import threading
import uuid
from itertools import chain
import traceback 
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from vendors.transfers import mongo_handler
from .api import authentication, fetch_country_list, fetch_city_data, fetch_transfer_data, fetch_transfer_results_data, book, get_booking_details
from users.models import SupplierIntegration,OrganizationSupplierIntegeration, UserDetails
from common.models_transfers import TransferBookingSearchDetail, TransferBookingPaymentDetail, TransferBooking, \
                                    TransferBookingContactDetail, TransferBookingFareDetail, TransferBookingLocationDetail
from common.models import DailyCounter
import json
from vendors.transfers.utils import get_fare_markup
from vendors.transfers.finance.manager import FinanceManager

class TransferManager:
    """
    This manager class handles the application logic for 'transfers'.
    It delegates external API calls to api.py.
    """
    def __init__(self, user:UserDetails):
        self.user = user
        self.mongo_client = mongo_handler.Mongo()
        self.creds = self.get_supplier_data()
        self.auth_success = True if self.creds !=None else False

    def create_uuid(self,suffix=""):
        if suffix == "":
            return str(uuid.uuid4())
        else:
            return suffix+"-"+str(uuid.uuid4())

    def get_supplier_data(self):
        associated_suppliers_list = OrganizationSupplierIntegeration.objects.filter(organization=self.user.organization,is_enabled=True).values_list('supplier_integeration', flat=True)
        supplier_integrations = SupplierIntegration.objects.filter(id__in=associated_suppliers_list,integration_type ='Transfers',is_active=True)
        data = None
        for x in supplier_integrations:
            if x.name == "TBO":
                if  x.expired_at>int(time.time()) and x.token!=None:
                    data = x.data | {"token_id":x.token,"supplier_name":x.name,"supplier_id":str(x.id)}
                else:
                    token = authentication(x.data)
                    if token == None:
                        return None
                    x.update_token(token)
                    data = x.data | {"token_id":token,"supplier_name":x.name,"supplier_id":str(x.id)}
        return data
    
    
    def get_country_list(self):
        try:
            CountryList = self.mongo_client.fetch_static_data({"type":"CountryList"})
            if len(CountryList) > 0:
                if CountryList[0].get("createdAt") + timedelta(hours=int(self.creds.get("static_data_ttl",24))) > datetime.now():
                    if len(CountryList[0].get("data",[])) >0:
                        return CountryList[0].get("data",[])
            # Call the function from api.py
            response = fetch_country_list(
                token_id=self.creds['token_id'],
                client_id=self.creds['client_id'],
                end_user_ip=self.creds['end_user_ip'],
                base_url=self.creds['auth_url']
            )
            # If the API call failed or returned an unexpected response, it can return None
            if response is None:
                return None
            CountryList = response.get('CountryList',[])
            country_list = []
            if len(CountryList) >0:
                root = ET.fromstring(CountryList)

                # Extract country data into a list of dictionaries
                for country in root.findall('Country'):
                    code = country.find('Code').text
                    name = country.find('Name').text
                    country_list.append({'Code': code, 'Name': name})
                self.mongo_client.insert_static_data({"type":"CountryList","data":country_list},{"type":"CountryList"})
            return country_list
        except:
            return []
    
    def get_city_data(self,kwargs):
        try:
            data = {
            "search_type" : kwargs.get("search_type"),
            "country_code" : kwargs.get("country_code"),
            }
            Citydata = self.mongo_client.fetch_static_data({"type":"Citydata",
                                                                 "search_type":data['search_type'],
                                                                 "country_code":data["country_code"]})
            if len(Citydata) > 0:
                if Citydata[0].get("createdAt") + timedelta(hours=int(self.creds.get("static_data_ttl",24))) > datetime.now():
                    if len(Citydata[0].get("data",[])) >0:
                        return Citydata[0].get("data",[])
            # Call the function from api.py
            response = fetch_city_data(
                token_id=self.creds['token_id'],
                end_user_ip=self.creds['end_user_ip'],
                base_url=self.creds['static_data_url'],
                data=data
            )

            # If the API call failed or returned an unexpected response, it can return None
            if response is None:
                return None
            city_list = response.get('Destinations',[])
            self.mongo_client.insert_static_data({"type":"Citydata","data":city_list,
                                                "search_type":data['search_type'],"country_code":data["country_code"]},
                                                {"type":"Citydata","search_type":data['search_type'],"country_code":data["country_code"]})
            return city_list
        except:
            return []

    def pre_fetch_transfer_data(self,kwargs):
        try:
            city_code =  kwargs.get("city_code")
            static_data_ttl = datetime.now() - timedelta(hours=int(self.creds.get("static_data_ttl",24)))
            # Aggregation: get the maximum (latest) createdAt for each search_type that matches type and city_code.
            pipeline = [
                            # 1. Filter for documents of type "TransferData" and matching city_code.
                            {"$match": {"type": "TransferData", "city_code": city_code}},
                            # 2. Sort descending by createdAt so the latest document per search_type comes first.
                            {"$sort": {"createdAt": -1}},
                            # 3. Group by search_type and pick the first (latest) document.
                            {"$group": {
                                "_id": "$search_type",
                                "latestDoc": {"$first": "$$ROOT"}
                            }},
                            # 4. Check for each search_type that:
                            #    - The latest document's createdAt is >= static_data_ttl, and
                            #    - The 'data' field is not empty (if it's null or an empty array, this fails).
                            {"$project": {
                                "search_type": "$_id",
                                "passes": {
                                    "$and": [
                                        {"$gte": ["$latestDoc.createdAt", static_data_ttl]},
                                        {"$gt": [
                                            {"$size": {"$ifNull": ["$latestDoc.data", []]}}, 0
                                        ]}
                                    ]
                                }
                            }},
                            # 5. Collect the search types that passed the conditions into an array.
                            {"$group": {
                                "_id": None,
                                "passing": {"$push": {"$cond": ["$passes", "$search_type", "$$REMOVE"]}}
                            }},
                            # 6. Define the expected search types and compute the failing ones.
                            {"$addFields": {"expected": ["1", "2", "3", "4"]}},
                            {"$project": {"failing": {"$setDifference": ["$expected", "$passing"]}}}
                        ]
            results = list(self.mongo_client.staticData.aggregate(pipeline))
            if results:
                failing_search_types = results[0].get("failing", [])
            else:
                failing_search_types = [1, 2, 3, 4]
            for i in failing_search_types:
                data = {
                        "search_type" : str(i),
                        "city_code" : city_code,
                        }
                thread = threading.Thread(target=self.get_transfer_data, args=(data,))
                thread.start()
            return True
        except:
            return False


    def get_transfer_data(self,data):
        try:
            # Call the function from api.py
            response = fetch_transfer_data(
                token_id=self.creds['token_id'],
                client_id=self.creds['client_id'],
                end_user_ip=self.creds['end_user_ip'],
                base_url=self.creds['static_data_url'],
                data=data
            )
            # If the API call failed or returned an unexpected response, it can return None
            if response != None:
                TransferData = response.get('TransferStaticData',[])
                transfer_list = []
                if len(TransferData) >0:
                    root = ET.fromstring(TransferData)
                    if root.tag == "ArrayOfBasicAirportPropertyInfo":
                        if root.findall('BasicAirportPropertyInfo'):
                            for airport in root.findall('BasicAirportPropertyInfo'):
                                airport_info = {
                                    "Type": "Airport",
                                    "Code": airport.get("AirportCode"),
                                    "Name": airport.get("AirportName"),
                                    "CityCode": airport.get("CityCode"),
                                    "CityName": airport.get("cityName"),
                                    "CountryCode": airport.get("CountryCode")
                                }
                                transfer_list.append(airport_info)
                    elif root.tag == "ArrayOfBasicPortPropertyInfo":
                        if root.findall('BasicPortPropertyInfo'):
                            for port in root.findall('BasicPortPropertyInfo'):
                                port_info = {
                                    "Type": "Port",
                                    "Code": port.get("PortId"),
                                    "Name": port.get("PortName"),
                                    "CityCode": port.get("Destination"),
                                    "CityName": port.get("Destination"),
                                    "CountryCode": port.get("CountryCode").strip()
                                }
                                transfer_list.append(port_info)
                    elif root.tag == "ArrayOfBasicStationPropertyInfo":
                        if root.findall('BasicStationPropertyInfo'):
                            for station in root.findall('BasicStationPropertyInfo'):
                                station_info = {
                                    "Type": "Station",
                                    "Code": station.get("StationId"),
                                    "Name": station.get("StationName"),
                                    "CityCode": station.get("CityCode"),
                                    "CityName": station.get("CityName"),
                                    "CountryCode": station.get("CountryCode").strip()
                                }
                                transfer_list.append(station_info)
                    elif root.tag == "ArrayOfTransferAccomodationInfo":
                        if root.findall('TransferAccomodationInfo'):
                            for hotel in root.findall('TransferAccomodationInfo'):
                                hotel_info = {
                                    "Type": "Accomodation",
                                    "Code": hotel.attrib.get("HotelId"),
                                    "GiataId": hotel.attrib.get("GiataId"),
                                    "Name": hotel.attrib.get("HotelName"),
                                    "CityName": hotel.attrib.get("CityName"),
                                    "CountryCode": hotel.attrib.get("CountryCode").strip(),
                                    "AddressLine1": hotel.attrib.get("AddressLine1"),
                                    "AddressLine2": hotel.attrib.get("AddressLine2"),
                                    "Latitude": float(hotel.attrib.get("Latitude")),
                                    "Longitude": float(hotel.attrib.get("Longitude")),
                                    "PostalCode": hotel.attrib.get("PostalCode"),
                                    "IsTransferActive": hotel.attrib.get("IsTransferActive") == "True"
                                }
                                transfer_list.append(hotel_info)
                self.mongo_client.insert_static_data({"type":"TransferData","data":transfer_list,
                                                    "search_type":data['search_type'],"city_code":data["city_code"]},
                                                    {"type":"TransferData","search_type":data['search_type'],"city_code":data["city_code"]})
        except:
            pass

    def search_location(self,data):
        try:
            city_code =  data.get("city_code","")
            search_query = data.get("query")
            pipeline = [
                            # 1. Filter documents by type and city_code.
                            {"$match": {"type": "TransferData", "city_code": city_code}},
                            
                            # 2. Project a new field "matchingData" that filters the "data" array
                            {"$project": {
                                "matchingData": {
                                    "$filter": {
                                        "input": "$data",
                                        "as": "item",
                                        "cond": {
                                            "$or": [
                                                {"$regexMatch": {
                                                    "input": "$$item.Code",
                                                    "regex": ".*" + search_query + ".*",
                                                    "options": "i"
                                                }},
                                                {"$regexMatch": {
                                                    "input": "$$item.Name",
                                                    "regex": ".*" + search_query + ".*",
                                                    "options": "i"
                                                }}
                                            ]
                                        }
                                    }
                                }
                            }},
                            
                            # 3. Only pass documents where matchingData is not empty.
                            {"$match": {"matchingData": {"$ne": []}}},
                            
                            # 4. Unwind the matchingData array so each element becomes its own document.
                            {"$unwind": "$matchingData"},
                            
                            # 5. Replace the root with the matchingData element so that only the dict remains.
                            {"$replaceRoot": {"newRoot": "$matchingData"}}
                        ]

            results = list(self.mongo_client.staticData.aggregate(pipeline))
            return results
        except:
            return None


    def initiate_search(self,data):
        try:
            session_id = self.create_uuid()
            thread = threading.Thread(target=self.search_transfers, args=(session_id,data))
            thread.start()
            return [{"session_id":session_id}]
        except:
            return []
    
    # def search_dummy_result(self,session_id,data):
    #     session_id = "5b5a86c0-9fbf-404a-9cfb-a7eef566a7b6"
    #     session_data = self.mongo_client.fetch_all_with_sessionid(session_id)
    #     master_doc = [x for x in session_data if x.get("type")=='raw'][0]
    #     unified_result = []
    #     data = master_doc['data']
    #     vendor_data = {"name":self.creds.get("supplier_name"),"id":self.creds.get("supplier_id"),"status":"Success"}
    #     start = time.time()
    #     city_code = "126632"
    #     pickup_code = "1"
    #     dropoff_code = "1"
    #     pickup_static_data = self.mongo_client.fetch_static_data({"type":"TransferData",
    #                                                              "search_type":pickup_code,
    #                                                              "city_code":city_code})
    #     dropoff_static_data = self.mongo_client.fetch_static_data({"type":"TransferData",
    #                                                              "search_type":dropoff_code,
    #                                                              "city_code":city_code})
    #     for res in data:
    #         for r in res.get("Vehicles",[]):
    #             unified_result.append({
    #                 "category": r.get("Vehicle"),
    #                 "max_bags": r.get("VehicleMaximumLuggage"),
    #                 "max_passengers": r.get("VehicleMaximumPassengers"),
    #                 "transfer_time": res.get("ApproximateTransferTime"),
    #                 "pickup": {"type":res.get("PickUp",{}).get("PickUpName",""),
    #                         "name":res.get("PickUp",{}).get("PickUpDetailName",""),
    #                         "date":res.get("PickUp",{}).get("PickUpDate","").replace("/","-"),
    #                         "time":res.get("PickUp",{}).get("PickUpTime",""),
    #                         "pickup_code":res.get("PickUp",{}).get("PickUpCode",""),
    #                         "pickup_point_code":res.get("PickUp",{}).get("PickUpDetailCode","")
    #                         },
    #                 "drop_off": {"type":res.get("DropOff",{}).get("DropOffName",""),
    #                         "name":res.get("DropOff",{}).get("DropOffDetailName",""),
    #                         "dropoff_code":res.get("DropOff",{}).get("DropOffCode",""),
    #                         "dropoff_point_code":res.get("DropOff",{}).get("DropOffDetailCode","")
    #                         },
    #                 "amount": {"pub_fare":r.get("TransferPrice",{}).get("PublishedPriceRoundedOff",""),
    #                         "off_fare":r.get("TransferPrice",{}).get("OfferedPriceRoundedOff",""),
    #                         "currency":r.get("TransferPrice",{}).get("CurrencyCode","")
    #                         },
    #                 "info": res.get("Condition"),
    #                 "seg_id": r.get("segment_id"),
    #                 "is_pan":r.get("IsPANMandatory",False),
    #                 "last_cancellation_date":r.get("LastCancellationDate",""),
    #                 "cancellation_policy":[{
    #                     "value":c.get("Charge"),
    #                     "type":"percentage",
    #                     "currency":c.get("Currency"),
    #                     "from":c.get("FromDate"),
    #                     "to":c.get("ToDate"),
    #                 } if c.get("ChargeType") ==2 else {
    #                     "value":c.get("Charge"),
    #                     "type":"flat",
    #                     "currency":c.get("Currency"),
    #                     "from":c.get("FromDate"),
    #                     "to":c.get("ToDate"),
    #                 } 
    #                 for c in r.get("TransferCancellationPolicy",[]) ]
    #             })
    #     unique_pickup_codes = [x['pickup']['pickup_point_code'] for x in unified_result]
    #     unique_dropoff_codes = list(set([x['drop_off']['dropoff_point_code'] for x in unified_result]))
    #     pickup_data = [x|{"type":pickup_code} for x in pickup_static_data[0]['data'] if x['Code']in unique_pickup_codes]
    #     dropoff_data = [x|{"type":dropoff_code} for x in dropoff_static_data[0]['data'] if x['Code']in unique_dropoff_codes]
    #     final_loc = pickup_data+dropoff_data
    #     unique_loc_list = []
    #     seen = set()

    #     for d in final_loc:
    #         # Convert dictionary to a frozenset of key-value pairs for hashing
    #         identifier = frozenset(d.items())
    #         if identifier not in seen:
    #             seen.add(identifier)
    #             unique_loc_list.append(d)
    #     final_result = {"results":unified_result,"location_data":unique_loc_list}
    #     end = time.time()
    #     vendor_data['duration'] = end-start
    #     self.mongo_client.store_unified_data( session_id, vendor_data, final_result)
    
    
    def fare_calculation(self,fare_detatils,supplier_published_fare,supplier_offered_fare):
        fare_adjustment = fare_detatils['fare']
        tax_condition = fare_detatils['tax']
        new_published_fare = supplier_published_fare + ((float(fare_adjustment["markup"]))+(float(fare_adjustment["distributor_markup"]))-\
                                float(fare_adjustment["cashback"]) - float(fare_adjustment["distributor_cashback"]))
        new_offered_fare = supplier_published_fare + (float(fare_adjustment["markup"]) + float(fare_adjustment["distributor_markup"]) -\
            float(fare_adjustment["cashback"])-float(fare_adjustment["distributor_cashback"])) -\
            (supplier_published_fare-supplier_offered_fare)*(float(fare_adjustment["parting_percentage"])/100)*(float(fare_adjustment["distributor_parting_percentage"])/100)*(1-float(tax_condition["tax"])/100)
        discount = new_published_fare - new_offered_fare
        return {"offered_fare":round(new_offered_fare,2),"discount":round(discount,2),
                "published_fare":round(new_published_fare,2),"supplier_published_fare":supplier_published_fare,
                "supplier_offered_fare":supplier_offered_fare}



    def search_transfers(self,session_id,data):
        try:
            search_start0 = time.time()
            agg_data = {
            "transfer_time" : data.get("transfer_time"),
            "transfer_date" : data.get("transfer_date"),
            "adult_count" : str(data.get("pax_count")),
            "preferred_language" : data.get("preferred_language"),
            "alternate_language" : data.get("alternate_language"),
            "pickup_type" : data.get("pickup_type"),
            "pickup_point_code" : data.get("pickup_point_code"),
            "city_id" : str(data.get("city_id")),
            "dropoff_type" : data.get("dropoff_type"),
            "dropoff_point_code" : data.get("dropoff_point_code"),
            "country_code" : data.get("country_code"),
            "preferred_currency":data.get("preferred_currency")
            }
            code_map = {"Airport":1,"Port":3,"Station":2,"Accomodation":0}
            agg_data['pickup_code'] = code_map[agg_data['pickup_type']]
            agg_data['dropoff_code'] = code_map[agg_data['dropoff_type']]
            day, month, year = data['transfer_date'].split("-")
            agg_data['transfer_date'] = f"{year}-{month}-{day}"
            agg_data['transfer_time'] = int("".join(data['transfer_time'].split(":")))
            session_created = self.mongo_client.create_session(agg_data,self.user,self.creds.get("supplier_id"),session_id)
            if session_created:
            # Call the function from api.py
                start = time.time()
                response = fetch_transfer_results_data(
                    token_id=self.creds['token_id'],
                    end_user_ip=self.creds['end_user_ip'],
                    base_url=self.creds['base_url'],
                    session_id = session_id,
                    data=agg_data
                )
                end = time.time()
                # If the API call failed or returned an unexpected response, it can return None
                if response is None:
                    self.mongo_client.update_vendor_search_status(session_id,self.creds.get("supplier_id"),"API Failed")
                    self.mongo_client.update_session_status(session_id,"failed")
                elif response.get("TransferSearchResult", {}).get("ResponseStatus") != 1:
                    self.mongo_client.update_vendor_search_status(session_id,self.creds.get("supplier_id"),"API Failed")
                    self.mongo_client.update_session_status(session_id,"failed")
                else:
                    vendor_data = {"name":self.creds.get("supplier_name"),"id":self.creds.get("supplier_id"),"duration":end-start,"status":"Success"}
                    transfers_result = response.get("TransferSearchResult",{}).get("TransferSearchResults", [])
                    TraceId = response.get("TransferSearchResult", {}).get("TraceId")
                    def add_uuid_to_data(result):
                        # Flatten the list of data dictionaries and add UUIDs
                        all_data_entries = chain.from_iterable(item['Vehicles'] for item in result)
                        for entry in all_data_entries:
                            entry['segment_id'] = str(uuid.uuid4())
                        return result
                    transfers_result = add_uuid_to_data(transfers_result)
                    self.mongo_client.store_raw_data( session_id, vendor_data, transfers_result, TraceId)
                    self.mongo_client.update_vendor_search_status(session_id,self.creds.get("supplier_id"),"API Success")
                    city_code = agg_data['city_id']
                    codes_list = [agg_data['pickup_point_code'],agg_data['dropoff_point_code']]
                    pipeline = [
                                    # 1. Filter documents by type and optionally city_code.
                                    {"$match": {"type": "TransferData", "city_code": city_code}},
                                    
                                    # 2. Project a new field "matchingData" that filters the "data" array
                                    {"$project": {
                                        "matchingData": {
                                            "$filter": {
                                                "input": "$data",
                                                "as": "item",
                                                "cond": {"$in": ["$$item.Code", codes_list]}
                                            }
                                        }
                                    }},
                                    
                                    # 3. Exclude documents where the filtered array is empty.
                                    {"$match": {"matchingData": {"$ne": []}}},
                                    
                                    # 4. Unwind the matchingData array so that each element becomes its own document.
                                    {"$unwind": "$matchingData"},
                                    
                                    # 5. Replace the document root with the matchingData element.
                                    {"$replaceRoot": {"newRoot": "$matchingData"}}
                                ]
                    point_data = list(self.mongo_client.staticData.aggregate(pipeline))
                    pickup_data = [x for x in point_data if x['Code'] == agg_data['pickup_point_code']][0]
                    dropoff_data = [x for x in point_data if x['Code'] == agg_data['dropoff_point_code']][0]
                    start = time.time()
                    unified_result = []
                    fare_detatils = get_fare_markup(self.user)
                    image_urls = {"Business MPV":"https://b2bta-production.s3.ap-south-1.amazonaws.com/media/transfers/Business-MPV.png",
                                  "Business Sedan":"https://b2bta-production.s3.ap-south-1.amazonaws.com/media/transfers/Business-Sedan.png",
                                  "Economy MPV":"https://b2bta-production.s3.ap-south-1.amazonaws.com/media/transfers/Economy-MPV.png",
                                  "Economy Sedan":"https://b2bta-production.s3.ap-south-1.amazonaws.com/media/transfers/Economy-Sedan.png",
                                  "Economy VAN":"https://b2bta-production.s3.ap-south-1.amazonaws.com/media/transfers/Economy-VAN.png",
                                  "First Class Sedan":"https://b2bta-production.s3.ap-south-1.amazonaws.com/media/transfers/First-Class-Sedan.png",
                                  "Minibus":"https://b2bta-production.s3.ap-south-1.amazonaws.com/media/transfers/Minibus.png",
                                  "Business Van":"https://b2bta-production.s3.ap-south-1.amazonaws.com/media/transfers/Business-Van.png"}
                    for res in transfers_result:
                        for r in res.get("Vehicles",[]):
                            calculated_fares = self.fare_calculation(fare_detatils,r.get("TransferPrice",{}).get("PublishedPriceRoundedOff",""),r.get("TransferPrice",{}).get("OfferedPriceRoundedOff",""))
                            if r.get("Vehicle").strip() in image_urls.keys():
                                url = image_urls[r.get("Vehicle").strip()]
                            else:
                                url = "https://b2bta-production.s3.ap-south-1.amazonaws.com/media/transfers/cab-default-img.png"
                            unified_result.append({
                                "category": r.get("Vehicle"),
                                "max_bags": r.get("VehicleMaximumLuggage"),
                                "max_passengers": r.get("VehicleMaximumPassengers"),
                                "transfer_time": res.get("ApproximateTransferTime"),
                                "url":url,
                                "pickup": {
                                        "date":res.get("PickUp",{}).get("PickUpDate","").replace("/","-"),
                                        "time":res.get("PickUp",{}).get("PickUpTime",""),
                                        "info":pickup_data
                                        },
                                "drop_off": {
                                        "info":dropoff_data
                                        },
                                "amount": {"pub_fare":calculated_fares["published_fare"],
                                        "off_fare":calculated_fares["offered_fare"],
                                        "discount":calculated_fares["discount"],
                                        "currency":r.get("TransferPrice",{}).get("CurrencyCode",""),
                                        "base_fare":r.get("TransferPrice",{}).get("BasePrice",""),
                                        "tax":r.get("TransferPrice",{}).get("Tax",""),
                                        },
                                "supplier_published_fare": calculated_fares["supplier_published_fare"],
                                "supplier_offered_fare": calculated_fares["supplier_offered_fare"],
                                "info": res.get("Condition"),
                                "seg_id": r.get("segment_id"),
                                "is_pan":r.get("IsPANMandatory",False),
                                "last_cancellation_date":r.get("LastCancellationDate",""),
                                "cancellation_policy":[{
                                    "value":c.get("Charge"),
                                    "type":"percentage",
                                    "currency":c.get("Currency"),
                                    "from":c.get("FromDate"),
                                    "to":c.get("ToDate"),
                                } if c.get("ChargeType") ==2 else {
                                    "value":c.get("Charge"),
                                    "type":"flat",
                                    "currency":c.get("Currency"),
                                    "from":c.get("FromDate"),
                                    "to":c.get("ToDate"),
                                } 
                                for c in r.get("TransferCancellationPolicy",[]) ]
                            })
                    end = time.time()
                    vendor_data['duration'] = end-start
                    self.mongo_client.store_unified_data( session_id, vendor_data, unified_result)
                    self.mongo_client.update_vendor_search_status(session_id,self.creds.get("supplier_id"),"Unified")
                    self.mongo_client.update_session_status(session_id,"completed")
        except:
            self.mongo_client.update_vendor_search_status(session_id,self.creds.get("supplier_id"),"API Failed")
            self.mongo_client.update_session_status(session_id,"failed")
            pass

    def get_transfers_search_data(self,session_id):
        try:
            session_data = self.mongo_client.fetch_all_with_sessionid(session_id)
            if len(session_data) >0:
                for item in session_data:
                    item.pop("_id", None)
                master_doc = [x for x in session_data if x.get("type")=='master'][0]
                if (datetime.now()-master_doc.get("createdAt")).seconds > 900:
                    return  {
                                "session_break":True
                            }
                else:
                    if master_doc.get("status") == "completed":
                        unified  = [x for x in session_data if x.get("type")=='unified'][0]
                        return {
                                "transfer_list":unified.get("data"),
                                "status":True,
                                "is_completed":True,
                                "is_new_data": True,
                                "session_break":False,
                                "search_data": master_doc.get("search_data")
                            }
                    elif master_doc.get("status") == "in_progress":
                        return {
                                "status":True,
                                "is_completed":False,
                                "is_new_data": False,
                                "session_break":False,
                                "search_data": master_doc.get("search_data")
                            }
                    elif  master_doc.get("status") == "failed":
                        return {
                                "status":False,
                                "is_completed":True,
                                "is_new_data": False,
                                "session_break":False,
                                "search_data": master_doc.get("search_data")
                            }

            else:
                return {
                            "status":False,
                            "is_completed":True,
                            "is_new_data": False,
                            "session_break":False
                        }
        except:
            return {
                        "status":False,
                        "is_completed":True,
                        "is_new_data": False,
                        "session_break":False
                    }
    def generate_booking_display_id(self):
        now = timezone.now()
        today = now.date()
        with transaction.atomic():
            counter, created = DailyCounter.objects.select_for_update().get_or_create(date=today,module ='transfers')
            counter.count += 1
            counter.save()
            booking_number = counter.count
        formatted_booking_number = f"{booking_number:04d}"
        day_month = now.strftime("%d%m")  # DDMM format
        year_suffix = now.strftime("%y")  # Last two digits of the year
        return f"XFR{year_suffix}-{day_month}-{formatted_booking_number}"
    
    def create_booking(self,data):
        try:
            mongo_doc = self.mongo_client.fetch_all_with_sessionid(data.get("session_id"))
            if len(mongo_doc) >0:
                for item in mongo_doc:
                    item.pop("_id", None)
            master_doc = [x for x in mongo_doc if x.get("type")=='master']
            if len(master_doc)>0:
                master_doc =  master_doc[0]
                if (datetime.now()-master_doc.get("createdAt")).seconds > 900:
                    return  {
                                "session_break":True
                            }
                search_data = master_doc.get("search_data")
                date_obj = datetime.strptime(search_data['transfer_date'], "%Y-%m-%d")
                new_date_str = date_obj.strftime("%d-%m-%Y")
                transfer_booking_search = TransferBookingSearchDetail.objects.create(
                                                                                     transfer_time = search_data['transfer_time'],
                                                                                     transfer_date = new_date_str,
                                                                                     pax_count = search_data['adult_count'],
                                                                                     preferred_language = search_data['preferred_language'],
                                                                                     alternate_language = search_data['alternate_language'],
                                                                                     pickup_type = search_data['pickup_type'],
                                                                                     pickup_point_code = search_data['pickup_point_code'],
                                                                                     city_id = search_data['city_id'],
                                                                                     dropoff_type = search_data['dropoff_type'],
                                                                                     dropoff_point_code = search_data['dropoff_point_code'],
                                                                                     country_code = search_data['country_code'],
                                                                                     preferred_currency = search_data['preferred_currency'],
                                                                                     )
                unified_doc = [x for x in mongo_doc if x.get("type")=='unified'][0]
                unified_doc= unified_doc['data']
                seg_data = [x for x in unified_doc if x['seg_id'] == data.get("seg_id")][0]

                transfer_booking_payment_details = TransferBookingPaymentDetail.objects.create(
                    supplier_published_fare = seg_data.get('supplier_published_fare'),
                    supplier_offered_fare = seg_data.get('supplier_offered_fare'),
                    created_at = int(time.time()),
                    new_published_fare = seg_data.get('amount',{}).get('pub_fare'),
                    new_offered_fare = seg_data.get('amount',{}).get('off_fare')
                )
                display_id = self.generate_booking_display_id()
                transfer_booking = TransferBooking.objects.create(
                    display_id = display_id,
                    session_id = data.get("session_id"),
                    segment_id = data.get("seg_id"),
                    user = self.user,
                    search_detail = transfer_booking_search,
                    payment_detail = transfer_booking_payment_details,
                    pax_count = int(data.get("pax_info",{}).get("adult_count",0)) + int(data.get("pax_info",{}).get("child_count",0)),
                    status = 'Enquiry',
                    modified_by = self.user,
                    pax_data = json.dumps({"AdultCount":int(data.get("pax_info",{}).get("adult_count",0)),
                                'ChildCount':int(data.get("pax_info",{}).get("child_count",0))}),
                    max_passengers = seg_data['max_passengers'],
                    max_bags = seg_data['max_bags'],
                    category = seg_data['category'],
                    url = seg_data['url'],
                )
                transfer_booking_contact_detail = TransferBookingContactDetail.objects.create(
                    booking = transfer_booking,
                    title = data.get("pax_info",{}).get("title",''),
                    first_name = data.get("pax_info",{}).get("first_name",''),
                    last_name = data.get("pax_info",{}).get("last_name",''),
                    pan = data.get("pax_info",{}).get("pan",''),
                    contact_number = data.get("pax_info",{}).get("number",''),
                    age = data.get("pax_info",{}).get("age",''),
                    email= data.get("pax_info",{}).get("email",''),
                    country_code = data.get("pax_info",{}).get("country_code",''),
                )
                transfer_booking_location_detail_pickup = TransferBookingLocationDetail.objects.create(
                    booking = transfer_booking,
                    type = data.get("pickup",{}).get("type",''),
                    name = data.get("pickup",{}).get("name",''),
                    date = data.get("pickup",{}).get("date",''),
                    time = data.get("pickup",{}).get("time",''),
                    code = data.get("pickup",{}).get("code",''),
                    city_name = data.get("pickup",{}).get("city_name",''),
                    country = data.get("pickup",{}).get("country",''),
                    AddressLine1 = data.get("pickup",{}).get("AddressLine1",''),
                    AddressLine2 = data.get("pickup",{}).get("AddressLine2",''),
                    details = data.get("pickup",{}).get("details",''),
                    ZipCode = data.get("pickup",{}).get("ZipCode",''),
                    transfer_type = 'pickup',
                )
                transfer_booking_location_detail_drop = TransferBookingLocationDetail.objects.create(
                    booking = transfer_booking,
                    type = data.get("drop_off",{}).get("type",''),
                    name = data.get("drop_off",{}).get("name",''),
                    date = data.get("drop_off",{}).get("date",''),
                    time = data.get("drop_off",{}).get("time",''),
                    code = data.get("drop_off",{}).get("code",''),
                    city_name = data.get("drop_off",{}).get("city_name",''),
                    country = data.get("drop_off",{}).get("country",''),
                    AddressLine1 = data.get("drop_off",{}).get("AddressLine1",''),
                    AddressLine2 = data.get("drop_off",{}).get("AddressLine2",''),
                    details = data.get("drop_off",{}).get("details",''),
                    ZipCode = data.get("drop_off",{}).get("ZipCode",''),
                    transfer_type = 'drop',
                )
                seg_id = data.get("seg_id")
                raw_doc_main = [x for x in mongo_doc if x.get("type")=='raw'][0]
                raw_doc = raw_doc_main.get("data",[])
                raw_seg_data = [segs for segs in raw_doc for seg in segs.get('Vehicles',[]) if seg['segment_id'] == seg_id ][0]
                vehicle_data = [vehicle for vehicle in raw_seg_data['Vehicles'] if vehicle['segment_id'] == seg_id][0]
                transfer_booking_fare_detail = TransferBookingFareDetail.objects.create(
                    booking = transfer_booking,
                    published_fare = seg_data.get('amount',{}).get('pub_fare'),
                    offered_fare = seg_data.get('amount',{}).get('off_fare'),
                    organization_discount = 0,
                    dist_agent_markup = 0,
                    dist_agent_cashback = 0,
                    fare_breakdown = vehicle_data['TransferPrice'],
                    tax = seg_data.get('amount',{}).get('tax'),
                    cancellation_details = json.dumps(seg_data.get('cancellation_policy'))
                )
                return {"session_id":data.get("session_id"),"display_id":display_id,"booking_id": transfer_booking.id}
            else:
                return None
        except Exception as e:
            print(str(e))
            return None
    
    def purchase_start(self,kwargs):
        session_data = self.mongo_client.fetch_master_doc(kwargs.get("session_id"))
        if len(session_data) >0:
            for item in session_data:
                item.pop("_id", None)
            master_doc = [x for x in session_data if x.get("type")=='master'][0]
            if (datetime.now()-master_doc.get("createdAt")).seconds > 900:
                return  {
                            "session_break":True
                        }
            else:
                if kwargs.get("payment_mode","wallet").strip().lower() == "wallet":
                    wallet_thread = threading.Thread(target = self.purchase, kwargs={'data': kwargs,"wallet":True})
                    wallet_thread.start()
                    return {"status":True}
                else:
                    response = self.purchase(data = kwargs,wallet = False)
                    return {"status":True,"razorpay_url":response.get("payment_url")} 

    def purchase(self,**kwargs):
        try:
            booking_amount = float(kwargs["data"].get("amount",0)) 
            from_razorpay = kwargs["data"].get("from_razorpay",False)
            booking = TransferBooking.objects.filter(id = kwargs["data"]["booking_id"]).first()
            if booking and not from_razorpay:
                payment_instance = booking.payment_detail
                payment_instance.payment_type = kwargs["data"].get("payment_mode","wallet")
                payment_instance.save(update_fields = ["payment_type"])
                booking.status = 'In-Progress'
                booking.save(update_fields = ["status"])
            if not kwargs.get("wallet") and not from_razorpay:
                from common.razor_pay import razorpay_payment # imported here to solve circular import error
                razor_response = razorpay_payment(user = booking.user,amount = booking_amount,module = "transfers",
                                                booking_id = kwargs["data"]["booking_id"], 
                                                session_id = kwargs["data"]["session_id"])
                payment_status = True if razor_response.get("status") else False
                booking.save(update_fields = ["status"])
                return {"payment_status":payment_status,"payment_url":razor_response.get("short_url"),
                        "error":razor_response.get("error")}
            else:
                raw_doc_main = self.mongo_client.fetch_raw_with_sessionid(kwargs["data"].get("session_id"))[0]
                seg_id = booking.segment_id
                raw_doc = raw_doc_main.get("data",[])
                seg_data = [segs for segs in raw_doc for seg in segs.get('Vehicles',[]) if seg['segment_id'] == seg_id ][0]
                vehicle_data = [vehicle for vehicle in seg_data['Vehicles'] if vehicle['segment_id'] == seg_id][0]
                NumOfPax = booking.pax_count
                contact_details = TransferBookingContactDetail.objects.filter(booking_id = kwargs["data"]["booking_id"]).first()
                PaxInfo = [{
                            "PaxId": 0,
                            "Title": contact_details.title,
                            "FirstName": contact_details.first_name,
                            "LastName": contact_details.last_name,
                            "PaxType": 0,
                            "Age": contact_details.age,
                            "ContactNumber": contact_details.country_code + ' ' + contact_details.contact_number,
                            "PAN": contact_details.pan,
                            }]
                qs = TransferBookingLocationDetail.objects.filter(booking_id=kwargs["data"]["booking_id"])
                pickup_detail = qs.filter(transfer_type='pickup').first()
                drop_detail = qs.filter(transfer_type='drop').first()
                date_obj = datetime.strptime(pickup_detail.date, "%d-%m-%Y")
                new_date_str = date_obj.strftime("%m/%d/%Y")
                PickUp = {
                            "PickUpDetailName": pickup_detail.name,
                            "PickUpDetailCode": pickup_detail.code,
                            "Description": pickup_detail.details,
                            "Remarks": "",
                            "Time": pickup_detail.time,
                            "PickUpDate": new_date_str,
                            "AddressLine1": pickup_detail.AddressLine1,
                            "AddressLine2": pickup_detail.AddressLine2,
                            "City": pickup_detail.city_name,
                            "Country": pickup_detail.country,
                            "ZipCode": pickup_detail.ZipCode,
                        }
                try:
                    date_obj = datetime.strptime(drop_detail.date, "%d-%m-%Y")
                    new_date_str = date_obj.strftime("%m/%d/%Y")
                except:
                    new_date_str = drop_detail.date
                DropOff = {
                            "DropOffDetailName": drop_detail.name,
                            "DropOffDetailCode": drop_detail.code,
                            "Description": drop_detail.details,
                            "Remarks": "",
                            "Time": drop_detail.time,
                            "PickUpDate": new_date_str,
                            "AddressLine1": drop_detail.AddressLine1,
                            "AddressLine2": drop_detail.AddressLine2,
                            "City": drop_detail.city_name,
                            "Country": drop_detail.country,
                            "ZipCode": drop_detail.ZipCode,
                        }
                transfer_price_without_gst = vehicle_data['TransferPrice'].copy()
                transfer_price_without_gst.pop("GST", None)
                Vehicles = [
                            {
                                "VehicleIndex": vehicle_data['VehicleIndex'],
                                "Vehicle": vehicle_data['Vehicle'],
                                "VehicleCode": vehicle_data['VehicleCode'],
                                "VehicleMaximumPassengers": vehicle_data['VehicleMaximumPassengers'],
                                "VehicleMaximumLuggage": vehicle_data['VehicleMaximumLuggage'],
                                "Language": vehicle_data['Language'],
                                "LanguageCode": vehicle_data['LanguageCode'],
                                "TransferPrice": transfer_price_without_gst,
                            }
                        ]
                ResultIndex = seg_data['ResultIndex']
                TransferCode = seg_data['TransferCode']
                VehicleIndex = vehicle_data['VehicleIndex']
                OccupiedPax = [json.loads(booking.pax_data)]
                TraceId = raw_doc_main['TraceId']
                agg_data = {
                            "NumOfPax":NumOfPax,
                            "PaxInfo":PaxInfo,
                            "PickUp":PickUp,
                            "DropOff":DropOff,
                            "Vehicles":Vehicles,
                            "ResultIndex":ResultIndex,
                            "TransferCode":TransferCode,
                            "VehicleIndex":VehicleIndex,
                            "OccupiedPax":OccupiedPax,
                            "TraceId":TraceId
                            }
                is_thread_start = False
                response = book(
                        token_id=self.creds['token_id'],
                        end_user_ip=self.creds['end_user_ip'],
                        base_url=self.creds['base_url'],
                        session_id = kwargs["data"]["session_id"],
                        data=agg_data
                    )
                response_data = response.get('BookResult',None)
                if response_data != None:
                    if response_data.get("Error",{}).get("ErrorCode") == 0:
                        if response_data.get("BookingStatus") == 1:
                            status = 'Confirmed'
                        elif response_data.get("BookingStatus") in [0,4,5]:
                            status = 'Failed'
                            is_thread_start = True
                        elif response_data.get("BookingStatus") == 3:
                            status = 'Pending'
                            is_thread_start = True
                        else:
                            status = 'Cancelled'
                            is_thread_start = True
                        BookingRefNo = response_data.get("BookingRefNo",'')
                        ConfirmationNo = response_data.get("ConfirmationNo",'')
                        BookingId = response_data.get("BookingId",'')
                        TransferId = response_data.get("TransferId",'')
                        booking.booking_ref_no = BookingRefNo
                        booking.confirmation_number = ConfirmationNo
                        booking.booking_id = BookingId
                        booking.transfer_id = TransferId
                        booking.status = status
                        booking.error = response_data.get("Error",{}).get("ErrorMessage")
                        booking.booking_remarks = response_data.get("BookingRemarks",'')
                        booking.save(update_fields = ["status",'booking_ref_no','confirmation_number','booking_id','transfer_id','error','booking_remarks'])
                        if status == 'Confirmed':
                            finance_manager = FinanceManager(booking)
                            finance_manager.process_billing(self.creds)
                    else:
                        is_thread_start = True
                        booking.status = 'Failed'
                        booking.error = response_data.get("Error",{}).get("ErrorMessage")
                        booking.save(update_fields = ["status",'error'])
                else:
                    is_thread_start = True
                    booking.status = 'Failed'
                    booking.error = response_data.get("Error",{}).get("ErrorMessage")
                    booking.save(update_fields = ["status",'error'])
                
                if is_thread_start ==True:
                    time.sleep(20)
                    self.get_booking_details({"booking_id":booking.id,'TraceId':TraceId})

                
        except Exception as e:
            booking = TransferBooking.objects.filter(id = kwargs["data"]["booking_id"]).first()
            booking.status = 'Failed'
            booking.error = str(e)
            booking.save(update_fields = ["status",'error'])

    def process_failed(self,data):
        try:
            status = data.get("status")
            if status == 'Rejected':
                booking = TransferBooking.objects.filter(id = data["booking_id"]).first()
                booking.status = 'Rejected'
                booking.save(update_fields = ["status"])
                return "Booking Rejected Successfully"
            elif status == 'Confirmed':
                booking = TransferBooking.objects.filter(id = data["booking_id"]).first()
                booking.status = 'Confirmed'
                booking.booking_ref_no = data.get("booking_ref_no",'')
                booking.confirmation_number = data.get("confirmation_number",'')
                booking.booking_id = data.get("booking_id",'')
                booking.transfer_id = data.get("transfer_id",'')
                booking.save(update_fields = ["status","booking_ref_no","confirmation_number","booking_id","transfer_id"])
                finance_manager = FinanceManager(booking)
                finance_manager.process_billing(self.creds)
                return "Booking Confirmed Successfully"
        except:
            return None
    
    def get_booking_details(self,data):
        try:
            booking = TransferBooking.objects.filter(id = data["booking_id"]).first()
            booking_id = booking.booking_id
            confirmation_number = booking.confirmation_number
            contact = TransferBookingContactDetail.objects.filter(booking_id = data["booking_id"]).first()
            f_name = contact.first_name
            l_name = contact.last_name
            # Call the function from api.py
            response = get_booking_details(
                token_id=self.creds['token_id'],
                end_user_ip=self.creds['end_user_ip'],
                base_url=self.creds['base_url'],
                session_id='',
                data={"booking_id":booking_id,"confirmation_number":confirmation_number,"f_name":f_name,"l_name":l_name,'TraceId':data.get('TraceId',None)}
            )
            # If the API call failed or returned an unexpected response, it can return None
            if response != None:
                TransferData = response.get('GetBookingDetailResult',None)
                if TransferData.get("Error",{}).get("ErrorCode") == 0:
                    TransferBookingDetail = TransferData.get('TransferBookingDetail')
                    if TransferBookingDetail.get("BookingStatus") == 1:
                        status = 'Confirmed'
                    elif TransferBookingDetail.get("BookingStatus") in [0,4,5]:
                        status = 'Failed'
                    elif TransferBookingDetail.get("BookingStatus") == 3:
                        status = 'Pending'
                    else:
                        status = 'Cancelled'
                    BookingRefNo = TransferBookingDetail.get("BookingRefNo",'')
                    ConfirmationNo = TransferBookingDetail.get("ConfirmationNo",'')
                    BookingId = TransferBookingDetail.get("BookingId",'')
                    TransferId = TransferBookingDetail.get("TransferCode",'')
                    booking.booking_ref_no = BookingRefNo
                    booking.confirmation_number = ConfirmationNo
                    booking.booking_id = BookingId
                    booking.transfer_id = TransferId
                    booking.status = status
                    booking.error = TransferData.get("Error",{}).get("ErrorMessage")
                    # booking.booking_remarks = TransferData.get("BookingRemarks",'')
                    booking.save(update_fields = ["status",'booking_ref_no','confirmation_number','booking_id','transfer_id','error'])
                    if status == 'Confirmed':
                        finance_manager = FinanceManager(booking)
                        finance_manager.process_billing(self.creds)
                    return True
            return False
        except Exception as e:
            return None
    def check_easy_link(self,data):
        print(997)
        booking = TransferBooking.objects.filter(id = data["booking_id"]).first()
        finance_manager = FinanceManager(booking)
        finance_manager.process_billing(self.creds)