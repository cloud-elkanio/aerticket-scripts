import time
from pymongo import MongoClient
from datetime import datetime
# import pytz

import os

from dotenv import load_dotenv
load_dotenv() # put .env in settings containing folder

from vendors.insurance.utils import create_uuid
from users.models import LookupAirports,Organization,Country,LookupCountry
class Mongo:
    def __init__(self):
        monog_uri = os.getenv('MONGO_URL')
        self.mongo_client = MongoClient(monog_uri)
        self.db = self.mongo_client['project']
        self.searches = self.db['insurance_searches']
        self.insurance_supplier = self.db['insurance_suppliers']
        self.session_data = []

    def create_session(self,data,user,vendors,session_id):
        if True:
            vendor_status = {}
            for x in vendors:
                vendor_dict = {x.get_vendor_id():{"status":"Start"}}
                vendor_status.update(vendor_dict)            
            master_doc = {
                "service_type": "insurance",
                "type": "master",
                "session_id": str(session_id),
                "user_id": user.email,
                "name":user.first_name +" " + user.last_name if user.last_name else "",
                "email":user.email,
                "phone":user.phone_number,
                "organaization":str(user.organization_id),
                "status": "in_progress",
                "vendors":vendor_status,
                "search_data":data,
                "timestamp": time.time(),
                "createdAt":  datetime.now(),
            }
            self.searches.insert_one(master_doc)
            return True
        else:
            return False


    def store_raw_data(self, session_id, vendor, data,misc):
        raw_id = create_uuid("RAW")

        raw_doc = {
            "raw_id":raw_id,
            "service_type": "insurance",
            "session_id":session_id,
            "type": "raw",
            "vendor": vendor.get("id"),
            "vendor_name": vendor.get("name"),
            "duration": vendor.get("duration"),
            "data": data,
            "from": misc.get("from"),
            "to": misc.get("to"),
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
            "service_type": "insurance",
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
    def check_session_validity(self, master_doc):
        current_epoch = int(time.time())
        session = master_doc
        if session and current_epoch - session["timestamp"] < 1500:  # 25 minutes = 1500 seconds
            return True
        return False

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
            master_doc = {
                "booking_id": str(data.get("booking_id")),
                "vendor": str(data.get("vendor")),
                "url":data.get("url",""),
                "headers": data.get("headers",""),
                "request_type": data.get("request_type","POST"),
                "payload": data.get("payload"),
                "xml_data": data.get("xml_data",""),
                "response":data.get("response"),
                "createdAt":  datetime.now(),
                "api":data.get("api","")
            }
            self.insurance_supplier.insert_one(master_doc)
        except Exception as e:
            print("Exception",e)
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
        
    def fetch_all_with_sessionid(self,**kwargs):
        if True:
            if not self.session_data:
                self.session_data = list(self.searches.find({"session_id": kwargs.get("session_id")}))
                filtered_data = list(filter(lambda x:x["type"] == kwargs.get("type"),self.session_data))
            else:
                filtered_data = list(filter(lambda x:x["type"] == kwargs.get("type"),self.session_data))
            if kwargs.get("segment_id"):
                filtered_data = list(filter(lambda x: x.get("segment_id") == kwargs.get("segment_id"), filtered_data))
            return filtered_data
        else:
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