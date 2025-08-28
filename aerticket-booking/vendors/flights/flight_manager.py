import threading
import time
import traceback
import json
import concurrent.futures
from datetime import datetime, timezone
from django.db import transaction
from django.utils import timezone
from vendors.flights import mongo_handler
from vendors.flights import utils
from vendors.flights.finance_manager import FinanceManager
from vendors.flights.tbo.manager import Manager as TBO  
from vendors.flights.brightsun.manager import Manager as Brightsun
from vendors.flights.tripjack.manager import Manager as TRIPJACK
from vendors.flights.stt_etravel.manager import Manager as STT_Etravel
from vendors.flights.stt_travelshop.manager import Manager as STT_Travelshop
from vendors.flights.stt_travelopedia.manager import Manager as STT_Travelopedia
from vendors.flights.amadeus.manager import Manager as Amadues
from vendors.flights.galileo.manager import Manager as Galileo
from vendors.flights.stt_etravel.manager import Manager as Etravel
from users.models import Organization,LookupAirports,LookupCreditCard,\
    UserDetails,SupplierIntegration,OrganizationSupplierIntegeration,\
        DistributorAgentFareAdjustment
from common.models import (FlightBookingSegmentDetails,FlightBookingFareDetails,
        FlightBookingItineraryDetails,FlightBookingJourneyDetails,FlightBookingPaxDetails,
        FlightBookingPaymentDetails,FlightBookingSearchDetails,FlightBookingSSRDetails,
            Booking,FlightBookingPaymentDetails,FlightBookingUnifiedDetails,DailyCounter)
from .utils import get_flight_type

class FlightManager:
    def __init__(self, user:UserDetails):
        self.user = user
        self.mongo_client = mongo_handler.Mongo()
        self.master_doc =None

    def get_vendors(self,**kwargs):
        vendors = []
        associated_suppliers_list = OrganizationSupplierIntegeration.objects.filter(organization=self.user.organization,is_enabled=True).values_list('supplier_integeration', flat=True)
        supplier_integrations = SupplierIntegration.objects.filter(id__in=associated_suppliers_list,integration_type="Flights",is_active = True)
        is_amadeus = False
        for x in supplier_integrations:
            if x.name == "TBO":
                data = x.data
                if  x.expired_at>int(time.time()) and x.token!=None:
                    data = x.data | {"token":x.token,"expired_at":x.expired_at}
                    manager = TBO(data,x.id,self.mongo_client,False)
                else:
                    manager = TBO(data,x.id,self.mongo_client,True)
                    x.update_token(manager.token)
                
                vendors.append(manager)
            if x.name == "Tripjack":
                manager = TRIPJACK(x.data,x.id,self.mongo_client)
                vendors.append(manager)
            if x.name == "STT-Etravel":
                 manager = STT_Etravel(x.data,x.id,self.mongo_client)
                 is_journey = manager.get_vendor_journey_types(kwargs)
                 if is_journey:
                    vendors.append(manager)
            if x.name == "STT-Travelopedia":
                 manager = STT_Travelopedia(x.data,x.id,self.mongo_client)
                 is_journey = manager.get_vendor_journey_types(kwargs)
                 if is_journey:
                    vendors.append(manager)
            if x.name == "STT-Travelshop":
                 manager = STT_Travelshop(x.data,x.id,self.mongo_client)
                 is_journey = manager.get_vendor_journey_types(kwargs)
                 if is_journey:
                    vendors.append(manager)
            if "Amadeus".lower() in x.name.lower() and is_amadeus==False:
                 is_amadeus = True
                 manager = Amadues(x.data,x.id,self.mongo_client)
                 vendors.append(manager)
        return vendors

    def create_session(self,data):
        flight_type = get_flight_type(data,self.user)
        self.vendors = self.get_vendors(journey_type = data.get("journey_type"),flight_type = flight_type)
        if len(self.vendors)>0:
            status = {"status":"success"}
        else:
            status = {"status":"failure","info":"Sorry, we couldn't find any flight data for your search. Please contact support for further assistance.",
                      "vendors":self.vendors}
        session_id = utils.create_uuid()
        thread = threading.Thread(target = self.get_flights, args=(session_id,data))
        thread.start()
        return {"session_id":session_id}|status
    
    def get_flights(self, session_id,data):
        session_id,flight_type = self.mongo_client.create_session(data,self.user,self.vendors,session_id)
        data = data | {"flight_type":flight_type,"session_id":session_id}
        threads = []
        raw_results = []
        unified_results = []
        def fetch_from_vendor(vendor):
            start = time.time()
            result = vendor.search_flights(data)
            end = time.time()
            vendor_data = {"name":vendor.name(),"id":vendor.get_vendor_id(),"duration":end-start,"status":result.get("status")}
            raw_results.append(self.store_raw_data(session_id,vendor_data, result.get("data")))
            self.mongo_client.update_vendor_search_status(session_id,vendor.get_vendor_id(),"Raw")
            if result.get("status") == "success":
                start = time.time()
                fare_detatils = utils.get_fare_markup(self.user)
                unified_response = vendor.converter(result.get("data"),data,fare_detatils)
                end = time.time()
                if unified_response.get("status") == "success":
                    vendor_data = {"name":vendor.name(),"id":vendor.get_vendor_id(),"duration":end-start,"status":unified_response.get("status")}
                    unified_results.append(self.store_unified_data(session_id, vendor_data, unified_response.get("data")))
                    self.mongo_client.update_vendor_search_status(session_id,vendor.get_vendor_id(),"Unified")
                else:
                    self.mongo_client.update_vendor_search_status(session_id,vendor.get_vendor_id(),"Unified_Failed")
            else:
                self.mongo_client.update_vendor_search_status(session_id,vendor.get_vendor_id(),"Raw_Failed")
        for vendor in self.vendors:
            thread = threading.Thread(target=fetch_from_vendor, args=(vendor,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Once all threads are done, update the master session status
        self.update_session_status(session_id, "completed")

    def store_raw_data(self, session_id, vendor, data):        
        raw_doc = self.mongo_client.store_raw_data( session_id, vendor, data)
        return raw_doc
    def store_unified_data(self, session_id, vendor, data):        
        unified = self.mongo_client.store_unified_data( session_id, vendor, data)
        return unified

    def update_session_status(self, session_id, status):
        self.mongo_client.update_session_status(session_id, status)


    def process_result(self, result):
        # Logic to process each vendor's response into a unified format
        return result  # Placeholder for the actual processing logic

    def check_session_validity(self, session_id,fast_mode =False):
        current_epoch = int(time.time())
        self.master_doc = self.get_master_doc(session_id,fast_mode)
        status = self.mongo_client.check_session_validity(self.master_doc)
        return status
    
    def get_master_doc(self,session_id,fast_mode=False):
        if self.master_doc:
            return self.master_doc
        self.session_id = session_id
        filter_data = {"session_id": session_id}
        if fast_mode:
            filter_data = filter_data|{'timestamp': {'$gte': time.time() - 1500}}
        self.master_doc = self.mongo_client.fetch_all_with_sessionid(session_id = session_id, type =  "master")
        self.master_doc = self.master_doc[0] if self.master_doc else {}
        return self.master_doc
    
    def get_unified_doc(self,unified_ids):
        filter_data = {
                "unified_id": {"$in": unified_ids},
                "type" : "unified",
                "service_type":"flight"
            }
        session_id = self.master_doc["session_id"]
        if session_id:
           filter_data = filter_data|{"session_id":session_id} 

        result = self.mongo_client.searches.find(filter_data)  
        unified_docs = list(result)
        if not unified_docs:
            result = self.mongo_client.searches.find({
                "unified_id": {"$in": unified_ids},
                "type": "unified"
            })    
            unified_docs = list(result)

        # Return the list of documents
        return unified_docs
    
    def update_is_showed_unified_docs(self,session_id,unified_ids):
        filter_query = {
                "unified_id": {"$in": unified_ids},
                "type" : "unified",
                "service_type":"flight",
                "session_id" :session_id
            }
        self.mongo_client.searches.update_many(filter_query, {"$set": {"is_shown": True}})

    def get_fare_doc(self,segment_id):
        all_fare_doc = self.mongo_client.fetch_all_with_sessionid(session_id = self.session_id, type =  "fare")
        result = []
        for fare in all_fare_doc:
            if fare.get("segment_id") ==segment_id:
                result.append(fare)
        return result
     
    def get_raw_doc(self,raw_ids):
        filter_data = {
            "raw_id": {"$in": raw_ids},
            "type": "raw",
            "service_type":"flight"
        }
        session_id = self.master_doc["session_id"]
        if session_id:
           filter_data = filter_data|{"session_id":session_id} 
        result = self.mongo_client.searches.find(filter_data)  
        raw_docs = list(result)
        if not raw_docs:
            result = self.mongo_client.searches.find({
                "raw_id": {"$in": raw_ids},
                "type": "raw"
            })        
            raw_docs = list(result)

        return raw_docs   
    
    def get_manager_from_id(self,id):
        supplier_integration = SupplierIntegration.objects.filter(id=id).first()
        if supplier_integration.name == "TBO":
            manager = TBO(supplier_integration.data,supplier_integration.id,self.mongo_client,False)
        if supplier_integration.name == "Brightson":
            manager = Brightsun(supplier_integration.data,supplier_integration.id,self.mongo_client)
        if supplier_integration.name == "Tripjack":
            manager = TRIPJACK(supplier_integration.data,supplier_integration.id,self.mongo_client)
        if "Amadeus".lower() in supplier_integration.name.lower() :
            manager = Amadues(supplier_integration.data,supplier_integration.id,self.mongo_client)
        if supplier_integration.name == "STT-Etravel":
            manager = STT_Etravel(supplier_integration.data,supplier_integration.id,self.mongo_client)
        if supplier_integration.name == "STT-Travelopedia":
            manager = STT_Travelopedia(supplier_integration.data,supplier_integration.id,self.mongo_client)
        if supplier_integration.name == "STT-Travelshop":
            manager = STT_Travelshop(supplier_integration.data,supplier_integration.id,self.mongo_client)
        return manager

    def store_fare_data(self, session_id, vendor, data):
        raw_doc = self.mongo_client.store_raw_data( session_id, vendor, data)
        return raw_doc
    
    def check_cancellation_status(self):
        itineraries = FlightBookingItineraryDetails.objects.filter(
                flightbookingssrdetails_set__cancellation_status__isnull=False,status = 'Confirmed'
            ).distinct()
        for itinerary in itineraries:
            manager = self.get_manager_from_id(itinerary.vendor_id)
            manager.check_cancellation_status(itinerary)

    def get_fare_details(self,session_id,segment_id):
        master_doc = self.get_master_doc(session_id)
        raw_ids = list(master_doc["raw"].keys())
        raw_docs = self.get_raw_doc(raw_ids)
        raw_docs_dict = {x["raw_id"]: x for x in raw_docs}
        vendor_uuiid = segment_id.split("_$_")[0].split("VEN-")[1]
        manager = self.get_manager_from_id(vendor_uuiid)
        misc = {}
        if manager.name() not in ["Amadeus"]:
            raw_ids = list(master_doc["raw"].keys())
            raw_docs = self.get_raw_doc(raw_ids)
            raw_docs_dict = {x["raw_id"]: x for x in raw_docs}
            target_vendor_id = segment_id.split("_$_")[0]
            master_raw_data = master_doc.get('raw', {})
            for key, value in master_raw_data.items():
                vendor_id = value.get('id')
                if vendor_id == target_vendor_id:
                    raw_doc = raw_docs_dict[key]
                    raw_data = manager.find_segment_by_id(raw_doc,segment_id,master_doc)
                    fare_details = utils.get_fare_markup(self.user)
                    fare_data,status = manager.get_fare_details(master_doc = master_doc,raw_data = raw_data,
                                                                fare_details = fare_details,raw_doc = raw_doc,
                                                                segment_id = segment_id, session_id=session_id)
        else:
            unified_ids = list(master_doc["unified"].keys())
            unified_docs = self.get_unified_doc(unified_ids)
            unified_docs_dict = {x["unified_id"]: x for x in unified_docs}
            target_vendor_id = segment_id.split("_$_")[0]
            master_unified_data = master_doc.get('unified', {})
            for key, value in master_unified_data.items():
                vendor_id = value.get('id')
                if vendor_id == target_vendor_id:
                    unified_doc = unified_docs_dict[key]
                    unified_data = self.get_unified_data(unified_doc,segment_id)
                    itinerary_key = unified_data.get("itinerary")
                    fare_details = utils.get_fare_markup(self.user)
                    fare_data,status = manager.get_fare_details(master_doc = master_doc,raw_data = unified_data,
                                                                fare_details = fare_details,raw_doc = unified_doc,
                                                     segment_id = segment_id,itinerary_key = itinerary_key,session_id=session_id)
        for fare in fare_data:
            if "misc" in fare:
                misc_pop = fare.pop("misc")
                misc = {**misc,**misc_pop}
        fare_doc = {
                    "segment_id": segment_id,
                    "fareDetails": fare_data,
                    "misc":misc,
                    "type":"fare",
                    "session_id":self.session_id,
                    "createdAt":datetime.now()
                    }
        self.mongo_client.searches.insert_one(fare_doc)
        return fare_doc,status
    
    def get_fare_rule(self,**kwargs):
        session_id = kwargs["session_id"]
        segment_id = kwargs["segment_id"]
        fare_id = kwargs["fare_id"]
        master_doc = self.get_master_doc(session_id)
        vendor_id = kwargs["segment_id"].split("_$_")[0]
        row_docs  = self.mongo_client.fetch_all_with_sessionid(session_id = session_id, type = "raw")
        raw_doc = [row for row in row_docs if row["vendor"] == vendor_id][0]           
        manager = self.get_manager_from_id(vendor_id.split("VEN-")[1])
        fares = self.mongo_client.fetch_all_with_sessionid(session_id = session_id, type = "fare")
        if manager.name().upper() not in ["AMADEUS"]:
            raw_data = manager.find_segment_by_id(raw_doc,segment_id,master_doc)
            fare_rule,minifare_rules = manager.get_fare_rule(master_doc = master_doc,raw_data = raw_data,fares = fares,
                                              session_id = session_id,segment_id = segment_id,fare_id = fare_id)
        return fare_rule,minifare_rules

    def get_updated_fare_quote(self,segments):
        timings = []
        start = time.time()
        session_id = self.session_id
        master_doc  = self.master_doc
        raw_ids = list(master_doc["raw"].keys())
        fare_details = utils.get_fare_markup(self.user)
        segment_keys = utils.create_segment_keys(master_doc)
        updated_dict = {}
        fare_details_dict = {}
        fare_quote = {}
        status = False
        master_raw_data = master_doc.get('raw', {})
        master_unified_data = master_doc.get('unified', {})
        before_mongo = time.time()-start
        timings.append({"before_mongo":before_mongo})
        frequent_flyer_number = False
        is_fare_change = []
        isGST_list = []
        start = time.time()
        raw_docs = self.get_raw_doc(raw_ids)
        end = time.time()
        timings.append({"raw_docs":end-start})
        raw_docs_dict = {x["raw_id"]: x for x in raw_docs}
        is_adultDOB = []
        is_childDOB = []
        is_infantDOB = []
        for index,segment in enumerate(segments):
            segment_id = segment['segment_id']
            fare_id = segment['fare_id']
            target_vendor_id = segment_id.split("_$_")[0]
            start = time.time()
            fare_doc = self.get_fare_doc(segment_id)
            end = time.time()
            timings.append({"fare_mongo":end-start})
            start =time.time()
            for fare_detail in fare_doc:
                fareDetails = fare_detail["fareDetails"]
                for x in fareDetails:
                    if x.get("fare_id") == fare_id:
                        currentfare = x
                        break    
            end  =time.time()
            timings.append({"fare_found":end-start})             
            fare_details_dict.update({segment_keys[index]:currentfare})

            # Iterate through the raw keys and values and compare against the target vendor ID
            vendor_uuiid = segment_id.split("_$_")[0].split("VEN-")[1]
            manager = self.get_manager_from_id(vendor_uuiid)
            if manager.name() not in ["Amadeus"]:
                for key, value in master_raw_data.items():
                    vendor_id = value.get('id')
                    if vendor_id == target_vendor_id:
                        raw_doc = raw_docs_dict[key]
                        vendor_uuiid = segment_id.split("_$_")[0].split("VEN-")[1]
                        manager = self.get_manager_from_id(vendor_uuiid)
                        start  =time.time()
                        raw_data = manager.find_segment_by_id(raw_doc,segment_id,master_doc)
                        end  =time.time()
                        timings.append({"raw_found":end-start})
                        start  =time.time()
                        updated = manager.get_updated_fare_details(index,segment_data =segment,search_details=master_doc,
                                                                raw_data=raw_data,raw_doc=raw_doc,currentfare=currentfare,
                                                                fare_details=fare_details,session_id=session_id)
                        end  =time.time()
                        timings.append({"api_found":end-start})
                        status = status or updated.get("status") != "success"
                        frequent_flyer_number = updated.get("frequent_flyer_number",False)
                        is_fare_change.append(updated.get("IsPriceChanged",False))
                        isGST_list.append(updated.get("is_gst_mandatory",False))
                        if "pax_DOB" in updated:
                            is_adultDOB.append(updated["pax_DOB"].get("is_adultDOB"))
                            is_childDOB.append(updated["pax_DOB"].get("is_childDOB"))
                            is_infantDOB.append(updated["pax_DOB"].get("is_infantDOB"))
                        if updated.get('updated') == True:
                            data_unified = updated.get('data')
                            fare_details_dict.update(data_unified.get('fareDetails'))
                            data_unified.pop('fareDetails')
                            data_unified[segment_keys[index]]["default_baggage"] = currentfare.get("baggage",{})
                            fare_quote.update({segment_keys[index]:updated.get('raw')})
                            updated_dict.update(data_unified)
                        else:
                            for key, value in master_unified_data.items():
                                vendor_id = value.get('id')
                                if vendor_id == target_vendor_id:
                                    unified_doc = self.get_unified_doc([key])[0]
                                    data_unified =  self.get_unified_data(unified_doc,segment_id)
                                    updated_dict.update(data_unified)
                                    break
            else:
                unified_ids = list(master_doc["unified"].keys())
                unified_docs = self.get_unified_doc(unified_ids)
                unified_docs_dict = {x["unified_id"]: x for x in unified_docs}
                target_vendor_id = segment_id.split("_$_")[0]
                master_unified_data = master_doc.get('unified', {})
                for key, value in master_unified_data.items():
                    vendor_id = value.get('id')
                    if vendor_id == target_vendor_id:
                        unified_doc = unified_docs_dict[key]
                        unified_data = self.get_unified_data(unified_doc,segment_id)
                        itinerary_key = unified_data.get("itinerary")
                        fare_details = utils.get_fare_markup(self.user)
                        updated = manager.get_updated_fare_details(index,segment_data =segment,search_details = master_doc,
                                                                    raw_data = unified_data,raw_doc = unified_doc,currentfare=currentfare,
                                                                    fare_details = fare_details,itinerary_key=itinerary_key,session_id=session_id)
                        
                        status = status or updated.get("status") != "success"
                        frequent_flyer_number = updated.get("frequent_flyer_number")
                        is_fare_change.append(updated.get("IsPriceChanged",False))
                        if updated.get('updated') == True:
                            data_unified = updated.get('data')
                            fare_details_dict.update({segment_keys[index]:currentfare})
                            data_unified.pop('fareDetails')
                            fare_quote.update({segment_keys[index]:updated.get('raw')})
                            updated_dict.update(data_unified)
                            
                        else:   
                            fare_quote.update({segment_keys[index]:updated.get('raw')})
                            updated_dict.update(unified_data)

            updated_dict["itineraries"] = segment_keys
            filter_query = {"session_id": session_id,"type":"air_pricing"}

            air_doc = {"$set":{
                            "fareDetails": fare_details_dict,
                            'fareQuote':fare_quote,
                            'unified':updated_dict,
                            "isGST_list" : isGST_list,
                            "createdAt":datetime.now()
                        }
                        }
            self.mongo_client.searches.update_one(filter_query, air_doc, upsert = True)
            for key in fare_details_dict:
                fare_details_dict[key].pop("misc","") 
            start  =time.time()
            end  = time.time()
            timings.append({"mongo_insert":end-start})
        start = time.time()
        flight_type = master_doc.get("flight_type")
        isPassport = False
        isGST = any(isGST_list)
        if flight_type =="INT":
            isPassport = True
        if is_adultDOB == [] and is_childDOB == [] and is_infantDOB == []:
            if flight_type =="INT":
                dob_dict =  {"is_adultDOB":True,"is_childDOB":True,"is_infantDOB":True}
            else:
                dob_dict =  {"is_adultDOB":False,"is_childDOB":True,"is_infantDOB":True}
        else:
            dob_dict =  {"is_adultDOB":any(is_adultDOB),"is_childDOB":any(is_childDOB),"is_infantDOB":any(is_infantDOB)}
        colllect_data = {**{"isGST":isGST,"isPassport":isPassport},**dob_dict}
        end = time.time()
        timings.append({"misc":end-start})
        start = time.time()
        gst_details = { "name":self.user.organization.organization_name,
                       "number":self.user.organization.organization_gst_number,
                        "email":self.user.email,\
                        "phone_code":self.user.phone_code,
                       "phone_number":self.user.phone_number,
                       "address":self.user.organization.address,
                       "support_email":self.user.organization.support_email,
                       "support_phone":self.user.organization.support_phone,
        }
        end = time.time()
        timings.append({"gst":end-start})
        search_details = {
             "flight_type":flight_type,
             "journey_type":master_doc.get("journey_type"),
             "journey_details":master_doc.get("journey_details"),
             "passenger_details":master_doc.get("passenger_details"),
             "fare_type":master_doc.get("fare_type"),
             "cabin_class":master_doc.get("cabin_class"),
                           }
        IsPriceChanged = all(is_fare_change) if is_fare_change else False
        return_data = {'session_id': session_id,"timings":timings,"fareDetails":fare_details_dict,"search_details":search_details,
                       "gst_details":gst_details,"IsPriceChanged":IsPriceChanged,"frequent_flyer_number":frequent_flyer_number}| colllect_data |updated_dict|{"status":status}
        return return_data
    
    def create_booking(self,session_id,data):
        try:
            master_doc = self.get_master_doc(session_id)
            booking = utils.check_duplicate_booking(journey = master_doc.get("journey_details",[]),
                                                            pax = data.get("pax_details",[]),user = self.user,
                                                            flight_type = master_doc.get("flight_type"),
                                                            journey_type = master_doc.get("journey_type"),session_id = session_id)
            if not booking:
                itinerary_list = []
                search_details = FlightBookingSearchDetails.objects.create(
                    flight_type = master_doc.get("flight_type"),
                    journey_type = master_doc.get("journey_type"),
                    passenger_details = master_doc.get("passenger_details"),
                    cabin_class = master_doc.get("cabin_class"),
                    fare_type = master_doc.get("fare_type")
                )
                booking = Booking.objects.create(
                    display_id = generate_booking_display_id(),
                    session_id=session_id,
                    user=self.user,
                    search_details=search_details,
                    gst_details=json.dumps(data.get("gstDetails")),
                    contact=json.dumps(data.get("contact")),
                    status='Enquiry',
                    booked_at=time.time(),  
                    cancelled_at=None, 
                    cancelled_by=None,
                    modified_at=time.time(), 
                    modified_by=self.user
                )
                segment_keys = utils.create_segment_keys(master_doc)
                air_doc = self.mongo_client.fetch_all_with_sessionid(session_id = session_id, type = "air_pricing")[0]
                ssr_doc = self.mongo_client.fetch_all_with_sessionid(session_id = session_id, type = "ssr")[0]
                misc_doc = self.mongo_client.fetch_all_with_sessionid(session_id = session_id, type = "misc")
                if booking:
                    new_published_fare = 0
                    new_offered_fare = 0
                    supplier_published_fare = 0
                    supplier_offered_fare = 0
                    for segment_key_pay in segment_keys:
                        new_published_fare += air_doc.get("fareDetails",{}).get(segment_key_pay,{}).get("publishedFare",0)
                        new_offered_fare += air_doc.get("fareDetails",{}).get(segment_key_pay,{}).get("offeredFare",0)
                        supplier_published_fare += air_doc.get("fareDetails",{}).get(segment_key_pay,{}).get("supplier_publishFare",0)
                        supplier_offered_fare += air_doc.get("fareDetails",{}).get(segment_key_pay,{}).get("supplier_offerFare",0)
                    new_payment = FlightBookingPaymentDetails.objects.create(
                    new_published_fare = new_published_fare,
                    new_offered_fare = new_offered_fare,
                    supplier_published_fare = supplier_published_fare,
                    supplier_offered_fare = supplier_offered_fare,
                    created_at = int(time.time()))
                    booking.payment_details = new_payment  
                    booking.save()
                if self.user.role.name == "distributor_agent":
                    dafa_obj = DistributorAgentFareAdjustment.objects.filter(user = self.user).first()
                    dafa = {"distributor_markup":dafa_obj.markup if dafa_obj else 0 ,
                        "distributor_cashback":dafa_obj.cashback if dafa_obj else 0}
                else:
                    dafa = {"distributor_markup":0,
                        "distributor_cashback":0}
                data_unified_dict = {}
                unified_ids = list(master_doc["unified"].keys())
                unified_docs = self.get_unified_doc(unified_ids)
                unified_docs_dict = {x["unified_id"]: x for x in unified_docs}
                for index,seg in enumerate(data.get("segments")):
                    air_doc_fare_details = air_doc.get("fareDetails",{}).get(segment_keys[index],{})
                    air_doc_fare_quote_details = air_doc.get("fareQuote",{}).get(segment_keys[index],{})
                    ssr_raw_details = ssr_doc.get("raw",{}).get(segment_keys[index],{})
                    segment_id = seg.get('segment_id')
                    target_vendor_id = segment_id.split("_$_")[0]
                    unified_data = master_doc.get('unified', {})
                    for key1, value1 in unified_data.items():
                        unified_vendor_id = value1.get('id')
                        if unified_vendor_id == target_vendor_id:
                            unified_doc = unified_docs_dict[key1]
                            data_unified =  self.get_unified_data(unified_doc,segment_id)
                            data_unified_dict.update(data_unified)
                            break

                    vendor_uuiid = target_vendor_id.split("VEN-")[1]
                    itinerary = FlightBookingItineraryDetails.objects.create(
                        booking=booking,
                        itinerary_key=segment_keys[index],
                        segment_id=segment_id,
                        vendor=SupplierIntegration.objects.filter(id=vendor_uuiid).first(),
                        status='Enquiry',
                        airline_pnr='',
                        gds_pnr='',
                        supplier_booking_id='',
                        itinerary_index =index,
                        old_itinerary=None,
                        default_baggage=air_doc["unified"][segment_keys[index]].get("default_baggage"),
                        )
                    misc_data = [misc.get("data",{}) for misc in misc_doc if misc["segment_id"] == segment_id] if misc_doc else {}
                    FlightBookingUnifiedDetails.objects.create(
                        itinerary = itinerary,
                        booking = booking,
                        fare_details = {segment_keys[index]:air_doc_fare_details},
                        fare_quote = {segment_keys[index]:air_doc_fare_quote_details},
                        ssr_raw = {segment_keys[index]:ssr_raw_details},
                        itinerary_data_unified = {segment_keys[index]:data_unified_dict.get(segment_keys[index])},
                        misc = misc_data[0] if misc_data else {},
                        created_at = int(time.time())
                        )
                    fare_details_dict = air_doc.get("fareDetails")
                    FlightBookingFareDetails.objects.create(
                        itinerary=itinerary,
                        published_fare=fare_details_dict.get(segment_keys[index]).get("publishedFare"),
                        offered_fare=fare_details_dict.get(segment_keys[index]).get("offeredFare"),
                        organization_discount=fare_details_dict.get(segment_keys[index]).get("Discount"),
                        dist_agent_markup=dafa.get("distributor_markup"),
                        dist_agent_cashback=dafa.get("distributor_cashback"),
                        fare_breakdown = fare_details_dict.get(segment_keys[index]).get("fareBreakdown")
                    )
                    itinerary_list.append(itinerary)

                for index,journey in enumerate(master_doc.get("journey_details")):
                    source_city = journey.get("source_city")
                    destination_city = journey.get("destination_city")
                    travel_date = journey.get("travel_date")
                    travel_date_obj = datetime.strptime(travel_date, "%d-%m-%Y")
                    formatted_date = travel_date_obj.strftime("%d%m")
                    segment_key = f"{source_city}_{destination_city}_{formatted_date}"
                    current_itinerary = itinerary_list[0] if len(itinerary_list)==1 else itinerary_list[index]
                    journey_details = FlightBookingJourneyDetails.objects.create(
                        itinerary=current_itinerary,
                        source=source_city,
                        destination=destination_city,
                        date=travel_date,
                        booking=booking,
                        journey_key=segment_key
                    )
                    for _segment in segment_keys:
                        _segment_data = data_unified_dict[_segment]['flightSegments']
                        for _key in _segment_data:
                            index = -1
                            for _journey in _segment_data[_key]:
                                json_data = _journey
                                index+=1
                                if segment_key == _key:

                                    departure_datetime_str = json_data.get("departure").get("departureDatetime")
                                    arrival_datetime_str = json_data.get("arrival").get("arrivalDatetime")
                                    departure_datetime = datetime.fromisoformat(departure_datetime_str)
                                    arrival_datetime = datetime.fromisoformat(arrival_datetime_str)
                                    departure_epoch_time = int(departure_datetime.timestamp())
                                    arrival_epoch_time = int(arrival_datetime.timestamp())
                                    FlightBookingSegmentDetails.objects.create(
                                    journey=journey_details,
                                    airline_number=json_data.get("flightNumber"),
                                    airline_name=json_data.get("airlineName"),
                                    airline_code=json_data.get("airlineCode"),
                                    flight_number=json_data.get("flightNumber"),
                                    equipment_type=json_data.get("equipmentType"),
                                    duration=json_data.get("durationInMinutes"),
                                    origin=json_data.get("departure").get("airportCode"),
                                    origin_terminal=json_data.get("departure").get("terminal"),
                                    departure_datetime=departure_epoch_time,
                                    destination=json_data.get("arrival").get("airportCode"),
                                    destination_terminal=json_data.get("arrival").get("terminal"),
                                    arrival_datetime=arrival_epoch_time,
                                    index=index)

                for index,pax in enumerate(data.get('pax_details')):
                    pax_details = FlightBookingPaxDetails.objects.create(
                        booking=booking,
                        pax_type=pax.get('type'),
                        title=pax.get('title'),
                        first_name=pax.get('firstName',"").strip(),
                        last_name=pax.get('lastName',"").strip(),
                        gender=pax.get('gender'),
                        dob=pax.get('dob'),
                        passport=pax.get('passport'),
                        passport_expiry = pax.get('passport_expiry'),
                        passport_issue_date =  pax.get('passport_issue_date'),
                        passport_issue_country_code=pax.get('passport_issue_country_code',"IN"),
                        address_1=pax.get('address_1'),
                        address_2=pax.get('address_2'),
                        is_lead_pax=True if index == 0 else False,
                        frequent_flyer_number = pax.get("ffn") if pax.get("ffn") else {}
                    )
                    for itinerary in itinerary_list:
                        ssr_doc = self.mongo_client.fetch_all_with_sessionid(session_id = session_id, type = "ssr")[0]
                        if itinerary.itinerary_key in pax:
                            baggage_ssr_list = {}
                            meals_ssr_list = {}
                            seats_ssr_list = {}
                            for _journey in pax.get(itinerary.itinerary_key):
                                _journey_dict = pax.get(itinerary.itinerary_key)[_journey]
                                baggage_ssr_list[_journey] = _journey_dict.get('baggage_ssr',{})
                                meals_ssr_list[_journey] = _journey_dict.get('meals_ssr',{})
                                seats_ssr_list[_journey] = _journey_dict.get('seats_ssr',{})
                            is_baggage = any(baggage_ssr_list[_journey] for _journey in pax.get(itinerary.itinerary_key))
                            is_meals =  any(meals_ssr_list[_journey] for _journey in pax.get(itinerary.itinerary_key))
                            is_seats =  any(seats_ssr_list[_journey] for _journey in pax.get(itinerary.itinerary_key))
                            FlightBookingSSRDetails.objects.create(
                                itinerary=itinerary,
                                pax=pax_details,
                                is_baggage=is_baggage,
                                is_meals=is_meals,
                                is_seats=is_seats,
                                baggage_ssr=json.dumps(baggage_ssr_list),
                                meals_ssr=json.dumps(meals_ssr_list),
                                seats_ssr=json.dumps(seats_ssr_list),
                                ssr_id=ssr_doc.get("ssr_id"))
                        else:
                            FlightBookingSSRDetails.objects.create(
                                itinerary = itinerary,
                                pax = pax_details,
                                is_baggage = False,
                                is_meals = False,
                                is_seats = False,
                                baggage_ssr = json.dumps({}),
                                meals_ssr = json.dumps({}),
                                seats_ssr = json.dumps({}),
                                ssr_id = ssr_doc.get("ssr_id"))
                self.mongo_client.flight_supplier.insert_one({"session_id":session_id,"booking_id":str(booking.id),
                                                    "booking_display_id":booking.display_id,"type":"create_booking","createdAt":  datetime.now(),})
                return {"status" :True, "booking":booking}
            elif booking.session_id == session_id:
                return {"status" :True, "booking":booking}
            else:
                return {"status" :False, "booking":booking,"info":"""Booking already exists ({}). 
                        Please try again after some time!""".format(booking.display_id)}
        except:
            error = traceback.format_exc()
            self.mongo_client.flight_supplier.insert_one({"session_id":session_id,"error":error,
                                                            "type":"create_booking","createdAt": datetime.now()})
            return {"status" :False, "info":"Duplicate Booking!",
                    "error":error}  
                
    def check_hold(self,session_id,booking_id):
        master_doc = self.get_master_doc(session_id)    
        booking = Booking.objects.filter(id = booking_id).first()
        air_doc = self.mongo_client.fetch_all_with_sessionid(session_id = session_id, type = "air_pricing")[0]
        itineraries = FlightBookingItineraryDetails.objects.filter(booking = booking)
        segments = itineraries.values_list('segment_id', flat=True)
        raw_list = master_doc.get('raw', {})
        segment_keys = utils.create_segment_keys(master_doc)
        hold_response = {}
        for index,seg in enumerate(segments):
            segment_id = seg
            target_vendor_id = segment_id.split("_$_")[0]
            for _, value in raw_list.items():
                vendor_id = value.get('id')
                if vendor_id == target_vendor_id:
                    vendor_uuiid = segment_id.split("_$_")[0].split("VEN-")[1]
                    manager = self.get_manager_from_id(vendor_uuiid)
                    fare_quote = air_doc["fareQuote"][segment_keys[index]]
                    itinerary = itineraries.filter(itinerary_key = segment_keys[index]).first()
                    response = manager.check_hold(fare_quote,itinerary)
                    hold_response[segment_keys[index]] = response
        is_hold = True
        is_hold_ssr =  True
        hold_info = ""    
        for hold_key in hold_response:
            hold_dict = hold_response[hold_key]
            is_hold =  is_hold and hold_dict.get("is_hold")
            is_hold_ssr =  is_hold_ssr and hold_dict.get("is_hold_ssr")
            hold_info = hold_dict.get("info","")
        return_data = {"is_hold":is_hold,"is_hold_ssr":is_hold_ssr,"info":hold_info}
        return return_data

    def hold_booking(self,**kwargs):
        booking = Booking.objects.filter(id = kwargs['data']["booking_id"]).first()
        booking.is_direct_booking = False
        booking.save(update_fields = ["is_direct_booking"])
        self.mongo_client.flight_supplier.insert_one({"session_id":kwargs['data']["session_id"],"booking_id":kwargs['data']["booking_id"],
                                                        "type":"hold_initiated","payment_mode":"N/A","createdAt":  datetime.now()})
        itinerary_details = FlightBookingItineraryDetails.objects.filter(booking = booking)
        pax_details  = FlightBookingPaxDetails.objects.filter(booking=booking)  
        itinerary_ids = itinerary_details.values_list('id', flat=True)
        pax_ids = pax_details.values_list('id', flat=True)
        ssr_details = FlightBookingSSRDetails.objects.filter(
            itinerary_id__in=itinerary_ids, 
            pax_id__in=pax_ids
        )        
        master_doc = self.get_master_doc(kwargs['data']["session_id"])
        if not booking.payment_details.ssr_price and kwargs['data'].get("ssr_amount"):
            booking.payment_details.ssr_price = float(kwargs['data'].get("ssr_amount",0))
            booking.save()
        unified_list = master_doc.get('unified', {})

        segment_keys = utils.create_segment_keys(master_doc)
        raw_list = master_doc.get('raw', {})
        air_doc = self.mongo_client.fetch_all_with_sessionid( session_id = kwargs['data']["session_id"], type = "air_pricing")[0]

        ssr_response_list = list(
            self.mongo_client.fetch_all_with_sessionid(session_id = kwargs['data']["session_id"], type = "ssr")
        )
        hold_break = False     
        raw_ids = list(master_doc["raw"].keys())
        raw_docs = self.get_raw_doc(raw_ids)
        raw_docs_dict = {x["raw_id"]: x for x in raw_docs}  
        unified_ids = list(master_doc["unified"].keys())
        unified_docs = self.get_unified_doc(unified_ids)
        unified_docs_dict = {x["unified_id"]: x for x in unified_docs}       
        for itinerary in itinerary_details:
            if itinerary.status == "Enquiry":
                vendor = SupplierIntegration.objects.filter(id=itinerary.vendor.id).first()
                manager = self.get_manager_from_id(vendor.id)
                if manager.name() not in ["Amadeus"]:
                    for key, value in raw_list.items():
                        if not hold_break:
                            vendor_id = value.get('id').split("VEN-")[1]
                            if vendor_id == str(vendor.id):
                                raw_doc = raw_docs_dict[key]
                                manager = self.get_manager_from_id(vendor.id)
                                raw_data = manager.find_segment_by_id(raw_doc, itinerary.segment_id, master_doc)
                                response = manager.hold_booking(
                                    raw_data = raw_data, fare_details=air_doc,ssr_response_list= ssr_response_list,booking= booking,
                                    itinerary = itinerary,pax_details= pax_details,ssr_details= ssr_details.filter(itinerary=itinerary)
                                )
                                if response.get("status") == False:
                                    hold_break = True
                else:
                    for key, value in unified_list.items():
                        if not hold_break:
                            vendor_id = vendor.id
                            if True:
                                unified_doc = unified_docs_dict[key]
                                unified_data =  self.get_unified_data(unified_doc,itinerary.segment_id)
                                itinerary_key = unified_data.get("itinerary")

                                fare_details = utils.get_fare_markup(self.user)
                                response = manager.hold_booking(
                                    raw_data = unified_data, fare_details=air_doc,ssr_response_list= ssr_response_list,booking= booking,
                                    itinerary = itinerary,pax_details= pax_details,ssr_details= ssr_details.filter(itinerary=itinerary),itinerary_key=itinerary_key
                                )
                                if response.get("status") == False:
                                    hold_break = True

    def purchase(self,**kwargs):
        booking_amount = float(kwargs["data"].get("amount",0)) + float(kwargs["data"].get("ssr_amount",0))
        from_razorpay = kwargs["data"].get("from_razorpay",False)
        booking = Booking.objects.filter(id = kwargs["data"]["booking_id"]).first()
        if booking and not from_razorpay:
            payment_instance = booking.payment_details
            payment_instance.ssr_price = kwargs["data"].get("ssr_amount",0)
            payment_instance.payment_type = kwargs["data"].get("payment_mode","wallet")
            payment_instance.save(update_fields = ["ssr_price","payment_type"])
        if not kwargs.get("wallet") and not from_razorpay:
            from common.razor_pay import razorpay_payment # imported here to solve circular import error
            razor_response = razorpay_payment(user = booking.user,amount = booking_amount,module = "flight",
                                              booking_id = kwargs["data"]["booking_id"], 
                                              session_id = kwargs["data"]["session_id"])
            payment_status = True if razor_response.get("status") else False
            booking.save(update_fields = ["status"])
            return {"payment_status":payment_status,"payment_url":razor_response.get("short_url"),
                    "error":razor_response.get("error")}
        else:
            pax_details  = FlightBookingPaxDetails.objects.filter(booking = booking)  
            itinerary_details = FlightBookingItineraryDetails.objects.filter(booking = booking).order_by("itinerary_index")
            itinerary_ids = itinerary_details.values_list('id', flat=True)
            pax_ids = pax_details.values_list('id', flat=True)
            session_id = booking.session_id
            master_doc = self.get_master_doc(session_id)
            raw_list = master_doc.get('raw', {})
            unified_list = master_doc.get('unified', {})
            unified_ids = list(master_doc["unified"].keys())
            unified_docs = self.get_unified_doc(unified_ids)
            unified_docs_dict = {x["unified_id"]: x for x in unified_docs}  
            air_doc = self.mongo_client.fetch_all_with_sessionid(session_id = session_id, type =  "air_pricing")[0]
            ssr_details = FlightBookingSSRDetails.objects.filter(
                    itinerary_id__in = itinerary_ids, 
                    pax_id__in = pax_ids)  
            ssr_response_list = list(
                    self.mongo_client.fetch_all_with_sessionid(session_id = session_id, type = "ssr")
                )
            break_booking = False
            for itinerary in itinerary_details:
                if itinerary.status == "Enquiry":
                    vendor = SupplierIntegration.objects.filter(id=itinerary.vendor.id).first()
                    manager = self.get_manager_from_id(vendor.id)
                    if manager.name() not in ["Amadeus"]:
                        for key, value in raw_list.items():
                            if not break_booking:
                                vendor_id = value.get('id').split("VEN-")[1]
                                if vendor_id == str(vendor.id):
                                    raw_doc = self.get_raw_doc([key])[0]
                                    manager = self.get_manager_from_id(vendor.id)
                                    raw_data = manager.find_segment_by_id(raw_doc, itinerary.segment_id, master_doc)
                                    response = manager.purchase(
                                            raw_data = raw_data, fare_details=air_doc,ssr_response_list= ssr_response_list,booking= booking,
                                            itinerary = itinerary,pax_details= pax_details,ssr_details= ssr_details.filter(itinerary=itinerary),
                                            first_time = itinerary.status not in ("On-Hold","Hold-Unavailable"),raw_doc = raw_doc
                                    ) 
                                    if response.get("status") == False:
                                        break_booking = True
                    else:
                        for key, value in unified_list.items():
                            if not break_booking:
                                vendor_id = vendor.id
                                unified_doc = unified_docs_dict[key]
                                unified_data =  self.get_unified_data(unified_doc,itinerary.segment_id)
                                itinerary_key = unified_data.get("itinerary")
                                response = manager.purchase(
                                    raw_data = unified_data, fare_details=air_doc,ssr_response_list= ssr_response_list,booking= booking,
                                    itinerary = itinerary,pax_details= pax_details,ssr_details= ssr_details.filter(itinerary=itinerary),itinerary_key=itinerary_key)
                                
                                if response.get("status") == False:
                                    break_booking = True
                 
    def purchase_response(self,**kwargs):
        booking = Booking.objects.filter(id = kwargs.get("booking_id")).first()
        itinerary_details = FlightBookingItineraryDetails.objects.filter(booking = booking).order_by("created_at")
        booking_statuses = itinerary_details.values_list('status', flat = True)
        display = {"display_id":booking.display_id}
        itinerary_statuses = {}
        for itinerary in itinerary_details:
            itinerary_statuses[itinerary.itinerary_key] = {"status":itinerary.status,"is_soft_fail":itinerary.soft_fail}
        if all(status in ["Confirmed","On-Hold"] for status in booking_statuses):
            return {"status":"success","info":"Ticket Booked Successfully!","is_soft_fail":False}|display|itinerary_statuses
        elif any(status in ["Ticketing-Failed","Hold-Failed"] for status in booking_statuses):
            soft_fail_status = any(soft_fail for soft_fail in itinerary_details.values_list('soft_fail', flat = True))
            return display|{"status":"failure","info":"Ticketing Failed!","is_soft_fail":soft_fail_status}|itinerary_statuses
        else:
            return {"status":"In-Progress","is_soft_fail":False}|display|itinerary_statuses

    def convert_hold_to_ticket(self, booking_id):
        booking = Booking.objects.filter(id=booking_id).first()
        session_id =booking.session_id 
        pax_details  = FlightBookingPaxDetails.objects.filter(booking=booking)  
        itinerary_details = FlightBookingItineraryDetails.objects.filter(booking=booking)
        itinerary_ids = itinerary_details.values_list('id', flat=True)
        pax_ids = pax_details.values_list('id', flat=True)
        ssr_details = FlightBookingSSRDetails.objects.filter(
            itinerary_id__in=itinerary_ids, 
            pax_id__in=pax_ids
        )        
        convert_hold_book_break = False
        for itinerary in itinerary_details:
            if itinerary.status == "On-Hold":
                vendor = SupplierIntegration.objects.filter(id=itinerary.vendor.id).first()
                manager = self.get_manager_from_id(vendor.id)
                if not convert_hold_book_break:
                    response = manager.convert_hold_to_ticket(
                    booking = booking,
                    itinerary = itinerary,pax_details = pax_details,ssr_details = ssr_details.filter(itinerary=itinerary),
                                first_time = itinerary.status not in ("On-Hold","Hold-Unavailable")
                    ) 
                    if response.get("status") == False:
                        convert_hold_book_break = True

    def cancellation_charges(self,itinerary,pax_data,pax_ids,journey_details,additional_charge):
        vendor_uuiid = itinerary.segment_id.split("_$_")[0].split("VEN-")[1]
        manager = self.get_manager_from_id(vendor_uuiid)
        fare_details = utils.get_fare_markup(self.user)
        cancellation_charges_data = manager.cancellation_charges(itinerary = itinerary,fare_details = fare_details,
                                                                 pax_data = pax_data, pax_ids = pax_ids, journey_details = journey_details,
                                                                 additional_charge = additional_charge)    
        return cancellation_charges_data
    
    def booking_status(self,booking_id):
        itinerary_list = FlightBookingItineraryDetails.objects.filter(booking_id = booking_id).order_by("created_at")
        status_dict = {}
        itinerary_key_list = []
        for itinerary in itinerary_list:
            if itinerary.soft_fail:
                info = "Your booking is being processed. Please wait for the PNR/Ticket number ({})".format(itinerary.booking.display_id)
            elif itinerary.status in ["Hold-Failed","Ticketing-Failed"]:
                info = "Your booking is being processed, and our support team will contact you shortly for assistance!"
            elif itinerary.status == "Confirmed":
                info = "Ticket Booked Successfully!"
            else:
                info = "The booking is not initiated as other bookings are in progress."
            status = {itinerary.itinerary_key:{"status":itinerary.status,"error":info}}
            status_dict.update(status)
            itinerary_key_list.append(itinerary.itinerary_key)

        return_data = {"itineraries":itinerary_key_list}|status_dict
        return {"flight_booking_status_response":return_data,"booking_id":booking_id}
    
    def cancel_ticket(self,**kwargs):
        vendor_uuiid = kwargs["itinerary"].segment_id.split("_$_")[0].split("VEN-")[1]
        manager = self.get_manager_from_id(vendor_uuiid)
        cancel_ticket_data = manager.cancel_ticket(kwargs)
        return cancel_ticket_data

    def repricing(self,itinerary):
        vendor_uuiid = itinerary.segment_id.split("_$_")[0].split("VEN-")[1]
        manager = self.get_manager_from_id(vendor_uuiid)
        repricing_data = manager.get_repricing(itinerary =itinerary)
        return repricing_data
    
    def offline_import_pnr(self,data): 
        pnr = data["pnr"].upper().strip()
        provider = data["provider"]
        supplier_id = data["supplier_id"]
        if "amadeus" in provider.lower():
            vendors = SupplierIntegration.objects.all()
            for vendor in vendors:
                city_code =  vendor.data.get("city_code","")
                if city_code.lower() == supplier_id.lower():
                    manager = Amadues(vendor.data,vendor.id,self.mongo_client)
                    break
        elif "galileo" in provider.lower():
            vendors = SupplierIntegration.objects.all()
            for vendor in vendors:
                city_code =  vendor.data.get("city_code","")
                if city_code.lower() == supplier_id.lower():
                    manager = Galileo(vendor.data,vendor.id)
                    break
        pnr_doc = self.mongo_client.searches.find_one({"pnr" : pnr, "type": "offline"})
        if data.get("override",True)==True:
            pass
        else:
            return pnr_doc["response"]

        if manager:
            response  = manager.retrieve_imported_pnr(pnr)
            if response.get("status") !=False :
                booking_id = self.save_offline_billing(response,manager)
                response["booking_id"] = str(booking_id)
                response["status"] = True
                pnr_doc = {
                                "booking_id": str(booking_id),
                                "pnr":pnr,
                                "data": response,
                                "vendor":manager.get_vendor_id(),
                                "type":"offline",
                                "createdAt":  datetime.now(),
                            }
                
                self.mongo_client.searches.insert_one(pnr_doc)
                response["error_status"] = False
                return response
            else:
                return {"status":False,"info":response.get("info","Could not import PNR. Please try again!")} 
        else:
            return {"status":False,"Info":"Supplier Not Found"}

    def save_offline_billing(self,response,manager):
        adult_count = [pax for pax in response.get('pax_details',[]) if pax.get("pax_type") == "adults"]
        child_count = [pax for pax in response.get('pax_details',[]) if pax.get("pax_type") == "children"]
        infant_count = [pax for pax in response.get('pax_details',[]) if pax.get("pax_type") == "infants"]
        published_fare = 0
        for fare_per_pax in response.get("fareDetails",{}).get("fareBreakdown",[]):
            if fare_per_pax.get("passengerType") == "adults":
                if adult_count:
                    published_fare += len(adult_count)*fare_per_pax.get("totalFare",0)
            if fare_per_pax.get("passengerType") == "children":
                if child_count:
                    published_fare += len(child_count)*fare_per_pax.get("totalFare",0)
            if fare_per_pax.get("passengerType") == "infants":
                if infant_count:
                    published_fare += len(infant_count)*fare_per_pax.get("totalFare",0)
        offered_fare = published_fare
        # published_fare = offered_fare = sum(passenger["totalFare"] for passenger in response.get("fareDetails").get("fareBreakdown"))
        dt_object = datetime.strptime(response.get("ticketing_date"), "%Y-%m-%dT%H:%M:%S")
        user_country = self.user.organization.organization_country.lookup
        flight_type = all(
            LookupAirports.objects.filter(code=journey.get("departure").get("airportCode")).first().country == user_country and
            LookupAirports.objects.filter(code=journey.get("arrival").get("airportCode")).first().country == user_country
            for journey in response.get("flightSegments", [])
        )
        flight_type = "DOM" if flight_type else "INT"
        journey_type = "One Way" if len(response.get("flightSegments")) == 1 else "Multi City"
        search_details = FlightBookingSearchDetails.objects.create(
            flight_type=flight_type,
            journey_type=journey_type,
            passenger_details=json.dumps(response.get("passenger_details",{})),
            cabin_class=response.get("cabin_class",""),
            fare_type=response.get("fare_type","")
        )
        
        booking = Booking.objects.create(
            display_id = generate_booking_display_id(),
            session_id = utils.create_uuid(),
            user = self.user,
            search_details = search_details,
            gst_details = json.dumps(None),
            contact = json.dumps({}),
            status = 'Enquiry',
            booked_at=int(time.time()),
            modified_at = int(time.time()), 
            cancelled_at = None,  
            cancelled_by = None,
            modified_by = self.user,
            source = "Offline"
        )
        new_payment = FlightBookingPaymentDetails.objects.create(
            new_published_fare = published_fare,
            new_offered_fare = published_fare,
            supplier_published_fare = published_fare,
            supplier_offered_fare = published_fare,
            payment_type = "N/A",
            created_at = int(time.time()))
        booking.payment_details = new_payment  
        booking.save()
        itinerary_list = []
        if self.user.role.name == "distributor_agent":
            dafa_obj = DistributorAgentFareAdjustment.objects.filter(user = self.user).first()
            dafa = {"distributor_markup":dafa_obj.markup if dafa_obj else 0 ,
                "distributor_cashback":dafa_obj.cashback if dafa_obj else 0}
        else:
            dafa = {"distributor_markup":0,
                "distributor_cashback":0}
        vendor_uuiid = manager.get_vendor_id().split("VEN-")[1]

        for flight_index,flight in enumerate(response.get("flightSegments")):
            start_time = flight.get("departure").get("departureDatetime")
            start_code = flight.get("departure").get("airportCode")
            end_code = flight.get("arrival").get("airportCode")
            dt_object = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")
            hhmm_format = dt_object.strftime("%H%M")
            formatted_date = dt_object.strftime("%d-%m-%Y")
            itinerary_key = start_code+"_"+end_code+"_"+hhmm_format
            itinerary = FlightBookingItineraryDetails.objects.create(
                    booking=booking,
                    itinerary_key=itinerary_key,
                    segment_id="",
                    vendor = SupplierIntegration.objects.filter(id=vendor_uuiid).first(),
                    status ='Confirmed',
                    airline_pnr = response.get("airline_pnr"),
                    gds_pnr = response.get("gds_pnr"),
                    supplier_booking_id ='',
                    itinerary_index = flight_index,
                    old_itinerary = None,
                    created_at = int(time.time()),
                    modified_at = int(time.time()),
                    default_baggage = response.get("fareDetails",{}).get("baggage",{}).get("default_baggage",{}).get(start_code+"_"+end_code,{})
                    )
            if flight_index == 0:
                unified_fare = {itinerary_key:{"currency":"INR","isRefundable": True}}
                fareBreakdown_unified = []
                fare_data = response.get("fareDetails",{}).get("fareBreakdown")
                for pax_fare in fare_data:
                    fareBreakdown_unified.append({"tax": pax_fare.get("tax",0),
                                                    "baseFare": pax_fare.get("baseFare",0),
                                                    "passengerType": pax_fare.get("passengerType")
                                                })                         
                unified_fare[itinerary_key]["fareBreakdown"] = fareBreakdown_unified
                                            
            else:
                unified_fare = {itinerary_key:{"currency":"INR","isRefundable": True}}
                unified_fare[itinerary_key]["fareBreakdown"] = [{"passengerType":"adults","baseFare":0,"tax":0},
                                                                {"passengerType":"children","baseFare":0,"tax":0},
                                                                {"passengerType":"infants","baseFare":0,"tax":0}]
            itinerary_data_unified = {itinerary_key:{"currency":"INR","offerFare":published_fare,"publishFare":"published_fare",
                                    "Discount":0,"supplier_offerFare":published_fare,"supplier_publishFare":published_fare,
                                    "flightSegments":{itinerary_key:[flight]}}}
            FlightBookingUnifiedDetails.objects.create(
                itinerary = itinerary,
                booking = booking,
                fare_details = unified_fare,
                itinerary_data_unified = itinerary_data_unified,
                created_at = int(time.time())
                )
            
            FlightBookingFareDetails.objects.create(
                itinerary=itinerary,
                published_fare=published_fare,
                offered_fare=offered_fare,
                organization_discount=0,
                dist_agent_markup=dafa.get("distributor_markup"),
                dist_agent_cashback = dafa.get("distributor_cashback"),
                fare_breakdown =  response.get("fareDetails").get("fareBreakdown") if flight_index == 0 \
                    else response.get("fareDetails").get("fareBreakdown")
            )
            itinerary_list.append(itinerary)
        for index,journey in enumerate(response.get("flightSegments")):
            source_city = journey.get("departure").get("airportCode")
            destination_city = journey.get("arrival").get("airportCode")
            travel_date = journey.get("departure").get("departureDatetime")
            dt_object = datetime.strptime(travel_date, "%Y-%m-%dT%H:%M:%S")
            formatted_date = dt_object.strftime("%d-%m-%Y")
            segment_key = f"{source_city}_{destination_city}_"
            current_itinerary = itinerary_list[index]
            journey_details = FlightBookingJourneyDetails.objects.create(
                itinerary = current_itinerary,
                source = source_city,
                destination = destination_city,
                date = formatted_date,
                booking = booking,
                journey_key= segment_key + formatted_date.replace("-","")[:4]
            )
            json_data = journey
            departure_datetime_str = json_data.get("departure").get("departureDatetime")
            arrival_datetime_str = json_data.get("arrival").get("arrivalDatetime")
            departure_datetime =  datetime.strptime(departure_datetime_str, "%Y-%m-%dT%H:%M:%S")
            arrival_datetime =datetime.strptime(arrival_datetime_str, "%Y-%m-%dT%H:%M:%S")
            departure_epoch_time = int(departure_datetime.timestamp())
            arrival_epoch_time = int(arrival_datetime.timestamp())
            FlightBookingSegmentDetails.objects.create(
                journey=journey_details,
                airline_number=json_data.get("flightNumber"),
                airline_name=json_data.get("airlineName"),
                airline_code=json_data.get("airlineCode"),
                flight_number=json_data.get("flightNumber"),  # Assuming flight number is the same as airline number
                equipment_type=json_data.get("equipmentType"),
                duration=json_data.get("durationInMinutes"),
                origin=json_data.get("departure").get("airportCode"),
                origin_terminal=json_data.get("departure").get("terminal"),
                departure_datetime=departure_epoch_time,
                destination=json_data.get("arrival").get("airportCode"),
                destination_terminal=json_data.get("arrival").get("terminal"),
                arrival_datetime=arrival_epoch_time,
                index=index)
        for index,pax in enumerate(response.get('pax_details')):
            pax_details = FlightBookingPaxDetails.objects.create(
                booking = booking,
                pax_type = pax.get('pax_type'),
                title = pax.get('title',""),
                first_name = pax.get('firstName'),
                last_name = pax.get('lastName'),
                gender = pax.get('gender',""),
                dob = pax.get('dob'),
                passport = pax.get('passport'),
                passport_expiry = pax.get('passport_expiry'),
                passport_issue_date =  pax.get('passport_issue_date'),
                passport_issue_country_code=pax.get('passport_issue_country_code',"IN"),
                address_1 = pax.get('address_1'),
                address_2 = pax.get('address_2'),
                is_lead_pax =True if index == 0 else False
            )
            for itinerary in itinerary_list:
                if itinerary.itinerary_key in pax:
                    baggage_ssr_list = {}
                    meals_ssr_list = {}
                    seats_ssr_list = {}
                    for _journey in pax.get(itinerary.itinerary_key):
                        _journey_dict = pax.get(itinerary.itinerary_key)[_journey]
                        baggage_ssr_list[_journey] = _journey_dict.get('baggage_ssr',{})
                        meals_ssr_list[_journey] = _journey_dict.get('meals_ssr',{})
                        seats_ssr_list[_journey] = _journey_dict.get('seats_ssr',{})
                    is_baggage = any(baggage_ssr_list[_journey] for _journey in pax.get(itinerary.itinerary_key))
                    is_meals =  any(meals_ssr_list[_journey] for _journey in pax.get(itinerary.itinerary_key))
                    is_seats =  any(seats_ssr_list[_journey] for _journey in pax.get(itinerary.itinerary_key))
                    FlightBookingSSRDetails.objects.create(
                        itinerary=itinerary,
                        pax=pax_details,
                        is_baggage=is_baggage,
                        supplier_ticket_number = pax.get("ticketNumber"),
                        is_meals=is_meals,
                        is_seats=is_seats,
                        baggage_ssr=json.dumps(baggage_ssr_list),
                        meals_ssr=json.dumps(meals_ssr_list),
                        seats_ssr=json.dumps(seats_ssr_list))
                else:
                    FlightBookingSSRDetails.objects.create(
                        itinerary=itinerary,
                        pax=pax_details,
                        is_baggage=False,
                        is_meals=False,
                        is_seats=False,
                        supplier_ticket_number = pax.get("ticketNumber"),
                        baggage_ssr=json.dumps({}),
                        meals_ssr=json.dumps({}),
                        seats_ssr=json.dumps({}))
        return booking.id

    def create_offline_billing(self,data,agent): 
        booking_id = data.get("booking_id")
        pnr_doc = self.mongo_client.searches.find_one({"booking_id" : booking_id, "type": "offline"})
        Org = Organization.objects.filter(id = data.get("supplier_end").get("agency_id")).first()
        user = UserDetails.objects.filter(organization = Org,role__name__in=("agency_owner","distributor_owner","super_admin")).first()
        booking_doc = Booking.objects.filter(id = booking_id).first()
        if data.get("fop",{}).get("type","").lower() == "card":
            card_number = LookupCreditCard.objects.get(id = data.get("fop",{}).get("card")).card_number
            payment_type = "Credit Card - " + card_number[-4:]
        else:
            payment_type = "Cash"
        booking_doc.user = user
        booking_doc.modified_by = agent
        created_at = data.get("ticketing_date")
        date_obj = datetime.fromisoformat(created_at).date()
        current_time = datetime.fromtimestamp(time.time()).time()
        combined_datetime = datetime.combine(date_obj, current_time)
        created_at_epoch_value = combined_datetime.timestamp()
        booking_doc.booked_at = created_at_epoch_value
        booking_doc.modified_at = int(time.time())
        booking_doc.status = 'Confirmed'
        payment_details = booking_doc.payment_details
        payment_details.payment_type = payment_type
        payment_details.save(update_fields=["payment_type"])
        booking_doc.save(update_fields=["user","status","booked_at","modified_at"])
        finance = FinanceManager(self.user)
        response  = finance.create_offline_billing(data,pnr_doc.get("data"))
        return response
    
    def ticketing_import_pnr(self,data):        
        provider = data["provider"]
        pnr = data["pnr"]
        supplier_id = data["supplier_id"]
        if "amadeus" in provider.lower():
            vendors = SupplierIntegration.objects.all()
            for vendor in vendors:
                city_code =  vendor.data.get("city_code","")
                if city_code.lower() == supplier_id.lower():
                    manager = Amadues(vendor.data,vendor.id,self.mongo_client)
                    break
        self.mongo_client.searches.delete_one({"pnr" : pnr, "type": "ticketing"})

        if manager:
            response  = manager.ticketing_import_pnr(pnr)
            unified = response.get("unified")
            raw = response.get("raw")
            info = response.get("info")
            status = response.get("status")
            if status == "success":
                pnr_doc = {
                                "booking_id": unified.get("booking_id"),
                                "pnr":pnr,
                                "unified":{"PNRRET_1": unified},
                                "raw":{"PNRRET_1": raw},
                                "supplier_id":city_code,
                                "vendor":manager.get_vendor_id(),
                                "type":"ticketing",
                                "createdAt":  datetime.now(),
                            }
                
                self.mongo_client.searches.insert_one(pnr_doc)
                unified.pop("fareDetails")
                unified["raw"] =raw
                return unified
            else:
                return response
        else:
            return {"Info":"Supplier Not Found"}

    def ticketing_repricing(self,data):        
        booking_id = data.get("booking_id")
        pnr_doc = self.mongo_client.searches.find_one({"booking_id" : booking_id, "type": "ticketing"})
        unified = pnr_doc["unified"]["PNRRET_1"]
        raw = pnr_doc["raw"]["PNRRET_1"]
        vendor = pnr_doc.get("vendor")
        vendor_uuid = vendor.split("VEN-")[1]
        manager = self.get_manager_from_id(vendor_uuid)
        currency_code = self.user.organization.organization_country.currency_code
        if manager:
            response  = manager.ticketing_repricing(unified,raw,currency_code)
            unified = response.get("unified")
            raw = response.get("raw")
            info = response.get("info")
            status = response.get("status")
            if status == "success":
                self.mongo_client.searches.update_one(
                        {"booking_id": booking_id, "type": "ticketing"},
                        {"$set": {"raw.TPCBRQ": raw,"unified.TPCBRQ":unified}}
                    )

                unified["raw"] = raw
                unified["booking_id"] = booking_id
                return unified
            else:
                return response
        else:
            return {"Info":"Supplier Not Found"}

    def ticketing_create(self,data):        
        booking_id = data.get("booking_id")
        pnr_doc = self.mongo_client.searches.find_one({"booking_id" : booking_id, "type": "ticketing"})
        unified = pnr_doc["unified"]["TPCBRQ"]
        raw = pnr_doc["raw"]["TPCBRQ"]
        vendor = pnr_doc.get("vendor")
        vendor_uuid = vendor.split("VEN-")[1]
        manager = self.get_manager_from_id(vendor_uuid)
        currency_code = self.user.organization.organization_country.currency_code
        if manager:
            response  = manager.ticketing_create(unified,raw)
            raw = response.get("raw")
            info = response.get("info")
            status = response.get("status")
            if status == "success":
                self.mongo_client.searches.update_one(
                        {"booking_id": booking_id, "type": "ticketing"},
                        {"$set": {"raw.TAUTCQ": raw}}
                    )
                unified["raw"] = raw
                pass
            else:
                return response
            
            response  = manager.ticketing_close_PNR(raw)
            raw = response.get("raw")
            info = response.get("info")
            status = response.get("status")
            if status == "success":
                self.mongo_client.searches.update_one(
                        {"booking_id": booking_id, "type": "ticketing"},
                        {"$set": {"raw.PNRADD": raw}}
                    )
                unified["raw"] = raw
                pass
            else:
                return response
            response  = manager.ticketing_issue_ticket(raw)
            raw = response.get("raw")
            info = response.get("info")
            status = response.get("status")
            if status == "success":
                self.mongo_client.searches.update_one(
                        {"booking_id": booking_id, "type": "ticketing"},
                        {"$set": {"raw.TTSTRQ": raw}}
                    )
                unified["raw"] = raw
                pass
            else:
                return response
            raw["pnr"] = pnr_doc.get("pnr")
            response  = manager.ticketing_import_pnr(raw,first_time=False)
            raw = response.get("raw")
            unified = response.get("unified")
            info = response.get("info")
            status = response.get("status")
            if status == "success":
                self.mongo_client.searches.update_one(
                        {"booking_id": booking_id, "type": "ticketing"},
                        {"$set": {"raw.PNRRET_2": raw,"unified.PNRRET_2": unified}}
                    )
                unified["raw"] = raw
                pass
            else:
                return response
            
            response  = manager.unify_pnr_response(raw)
            if response:
                db_booking_id = self.save_offline_billing(response,manager)
                self.mongo_client.searches.update_one(
                        {"booking_id": booking_id, "type": "ticketing"},
                        {"$set": {"db_booking_id": str(db_booking_id)}}
                    )
            security_response  = manager.security_signout(raw)
            raw = security_response.get("raw")
            info = security_response.get("info")
            status = security_response.get("status")
            return unified
        else:
            return {"Info":"Supplier Not Found"}

    def create_ticketing_billing(self,data):        
        booking_id = data.get("booking_id")
        pnr_doc = self.mongo_client.searches.find_one({"booking_id" : booking_id, "type": "ticketing"})
        db_booking_id = pnr_doc.get("db_booking_id")
        pnr_doc = pnr_doc.get("unified").get("PNRRET_2")
        Org = Organization.objects.filter(id = data.get("supplier_end").get("agency_id")).first()
        user = UserDetails.objects.filter(organization = Org,role__name__in=("agency_owner","distributor_owner","super_admin")).first()
        booking_doc = Booking.objects.filter(id = db_booking_id).first()
        booking_doc.user = user
        booking_doc.save(update_fields=["user"])
        finance = FinanceManager(self.user)
        response  = finance.create_offline_billing(data,pnr_doc)
        return response
    
    def update_ticket_status(self):
        soft_deleted_itineraries = FlightBookingItineraryDetails.objects.prefetch_related("flightbookingunifieddetailsitinerary_set",
                                                            "flightbookingssrdetails_set").filter(soft_fail=True,status__in = ["Ticketing-Failed","Hold-Failed"])
        for soft_deleted_itinerary in soft_deleted_itineraries:
            vendor_id = soft_deleted_itinerary.vendor_id
            manager = self.get_manager_from_id(vendor_id)
            manager.current_ticket_status(soft_deleted_itinerary = soft_deleted_itinerary)
    
    def release_hold(self, booking_id,first_time=True):
        itinerary_dict ={}
        booking = Booking.objects.filter(id=booking_id).first()
        session_id = booking.session_id
        itinerary_details = FlightBookingItineraryDetails.objects.filter(booking=booking)
        hold_statuses = list(itinerary_details.values_list('status', flat=True))
        segment_keys = list(itinerary_details.values_list('itinerary_key', flat=True))
        for itinerary in itinerary_details:
            itinerary_dict[itinerary.itinerary_key] = {"status":itinerary.status}
        if not any((status == "Release-Hold-Initiated" or status ==" Release-Hold-Failed" or status=="Hold-Released"or status =="On-Hold" or status =="Hold-Unavailable") for status in hold_statuses):
            return {"session_id":session_id,"status":"success","flight_hold_release_response":{"status":"Failure","info":"Release Hold Not Possible","itineraries":segment_keys}|itinerary_dict}
        already_start = False
        if any( (status =="Release-Hold-Failed") for status in hold_statuses):
            progress_status = "Failure"
            already_start = True
            info = "Release Hold Not Possible"
        if all( (status =="Hold-Released") for status in hold_statuses):
            progress_status = "Success"
            already_start = True
            info = "Release Hold successfull"
        if any( (status =="Release-Hold-Initiated") for status in hold_statuses):
            progress_status = "In-Progress"
            already_start = True
            info = "Release PNR under process"
        if already_start:
            return {"session_id":session_id,"status":"success","flight_hold_release_response":{"status":progress_status,"info":info,"itineraries":segment_keys}|itinerary_dict}
        elif first_time:
            inside_thread = threading.Thread(target=self.release_hold, args=(booking_id,False))
            inside_thread.start()
            return {"session_id":session_id,"status":"success","flight_hold_release_response":{"status":"In-Progress","itineraries":segment_keys}|itinerary_dict}
        else:
            pass
                   
        def process_itinerary(**kwargs):
            itinerary = kwargs["itinerary"]
            manager = self.get_manager_from_id(itinerary.vendor.id)
            manager.release_hold(**kwargs) 

        def process_all_itineraries_for_release_hold(**kwargs):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(
                        process_itinerary,itinerary=itinerary,**kwargs
                    )
                    for itinerary in itinerary_details
                ]
                for future in concurrent.futures.as_completed(futures):
                        result = future.result()
        process_all_itineraries_for_release_hold(
            itinerary_details=itinerary_details,booking = booking
        )
        return {"Info":"Release Hold Shouldnt be here"}

    def get_unified_data(self,unified_data, segment_id,journey_type="One Way"):
        itineraries = unified_data.get("data").get("itineraries")
        for itinerary in itineraries:
            flightSegments = unified_data.get("data").get(itinerary)
            
            for flightSegment in flightSegments:
                if flightSegment.get("segmentID") == segment_id:
                    return {"itineraries":itineraries,itinerary:flightSegment,"itinerary":itinerary}

def generate_booking_display_id():
    now = timezone.now()
    today = now.date()
    with transaction.atomic():
        counter, created = DailyCounter.objects.select_for_update().get_or_create(date=today,module="flight")
        counter.count += 1
        counter.save()
        booking_number = counter.count
    formatted_booking_number = f"{booking_number:04d}"
    day_month = now.strftime("%d%m")  # DDMM format
    year_suffix = now.strftime("%y")  # Last two digits of the year
    return f"FLT{year_suffix}-{day_month}-{formatted_booking_number}"


