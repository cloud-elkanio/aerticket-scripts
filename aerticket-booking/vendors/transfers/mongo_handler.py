import time
from pymongo import MongoClient
from datetime import datetime
# import pytz

import os

from dotenv import load_dotenv
load_dotenv() # put .env in settings containing folder

from vendors.flights.utils import create_uuid
from users.models import LookupAirports,Organization,Country,LookupCountry
class Mongo:
    def __init__(self):
        monog_uri = os.getenv('MONGO_URL')
        self.mongo_client = MongoClient(monog_uri)
        self.db = self.mongo_client['project']
        self.searches = self.db['transfers_searches']
        self.staticData = self.db['transfers_staticData']
        self.transfers_supplier = self.db['transfers_suppliers']

    def create_session(self,data,user,supplier_id,session_id):
        try:
            vendor_status =  {str(supplier_id):{"status":"Start"}}
            master_doc = {
                "service_type": "transfers",
                "type": "master",
                "session_id": session_id,
                "user_id": user.email,
                "name":user.first_name +" " + user.last_name if user.last_name else "",
                "email":user.email,
                "phone":user.phone_number,
                "organaization":str(user.organization_id),
                "status": "in_progress",
                "vendors":vendor_status,
                "search_data":data,
                "createdAt":  datetime.now()
            }
            self.searches.insert_one(master_doc)
            return True
        except:
            return False


    def store_raw_data(self, session_id, vendor, data, TraceId):
        raw_id = create_uuid("RAW")

        raw_doc = {
            "raw_id":raw_id,
            "service_type": "transfers",
            "session_id":session_id,
            "type": "raw",
            "vendor": vendor.get("id"),
            "vendor_name": vendor.get("name"),
            "duration": vendor.get("duration"),
            "data": data,
            "TraceId":TraceId,
            "createdAt":  datetime.now()
        }
        vendor["raw"] = raw_id
        self.searches.insert_one(raw_doc)
        self.update_session_raw_status(session_id,vendor)
        return raw_doc
    def store_unified_data(self, session_id, vendor, data):
        unified_id = create_uuid("UNI")

        unified_doc = {
            "unified_id":unified_id,
            "service_type": "transfers",
            "session_id":session_id,
            "type": "unified",
            "vendor": vendor.get("id"),
            "vendor_name": vendor.get("name"),
            "duration": vendor.get("duration"),
            "data": data,
            "createdAt":  datetime.now()
        }
        vendor["unified"] = unified_id
        self.searches.insert_one(unified_doc)
        self.update_session_unified_status(session_id,vendor)

        return unified_doc

    def update_session_status(self, session_id, status):
        self.searches.update_one(
            {"session_id": session_id, "type": "master"},
            {"$set": {"status": status}}
        )
    def update_session_raw_status(self, session_id,vendor):
        update_data = {}
        condition = vendor.get("raw")
        vendor["updated_at"] = datetime.now()
        update_data[f"{condition}"] = vendor
        self.searches.update_one(
            {"session_id": session_id, "type": "master"},
            {
                "$set": {
                    f"raw.{key}": value for key, value in update_data.items()
                }
            }
        )
    def update_session_unified_status(self, session_id,vendor):
        update_data = {}
        condition = vendor.get("unified")
        vendor["updated_at"] = datetime.now()

        update_data[f"{condition}"] = vendor
        self.searches.update_one(
            {"session_id": session_id, "type": "master"},
            {
                "$set": {
                    f"unified.{key}": value for key, value in update_data.items()
                }
            }
        )
    def update_vendor_search_status(self, session_id,vendor_id,status):
        self.searches.update_one(
            {"session_id": session_id, "type": "master"},
            {
                "$set": {
                    f"vendors.{vendor_id}": status
                }
            }
        )


    def unify_responses(self, results):
        # Process the results into a unified format
        unified_response = []
        for result in results:
            unified_response.append(self.process_result(result))
        return unified_response

    def process_result(self, result):
        # Logic to process each vendor's response into a unified format
        return result  # Placeholder for the actual processing logic

    
    def log_vendor_api(self,data):
        try:
            # current_epoch_seconds = int(datetime.now().timestamp())
            # ttl_seconds = 259200
            # expiry_time = datetime.fromtimestamp(current_epoch_seconds + ttl_seconds)
            # india_timezone = pytz.timezone("Asia/Kolkata")
            # current_time_ist = datetime.now(india_timezone)
            master_doc = {
                "session_id": data.get("session_id"),
                "vendor": data.get("vendor"),
                "url":data.get("url",""),
                "headers": data.get("headers",""),
                "request_type": data.get("request_type","POST"),
                "payload": data.get("payload"),
                "response":data.get("response"),
                "createdAt":  datetime.now(),
                "api":data.get("api","")
            }
            self.transfers_supplier.insert_one(master_doc)
        except:
            pass
    def fetch_static_data(self,data):
        try:
            data = list(self.staticData.find(data))
            return data
        except:
            return []
    

    def insert_static_data(self,data, filter_condition):
        try:
            master_doc = {"createdAt":  datetime.now()} | data
            update_data = {"$set": master_doc}
            self.staticData.update_one(filter_condition,update_data, upsert=True)
        except:
            pass
        
    def fetch_all_with_sessionid(self,session_id):
        try:
            session_data = list(self.searches.find({"session_id": session_id,"type": {"$in": ["master",'raw', "unified"]}}))
            return session_data
        except:
            return []

    def fetch_master_doc(self,session_id):
        try:
            session_data = list(self.searches.find({"session_id": session_id,"type": "master"}))
            return session_data
        except:
            return []
    
    def fetch_raw_with_sessionid(self,session_id):
        try:
            session_data = list(self.searches.find({"session_id": session_id,"type": {"$in": ["raw"]}}))
            return session_data
        except:
            return []