import time
from pymongo import MongoClient
from datetime import datetime
import os
from .utils import get_flight_type
from dotenv import load_dotenv
load_dotenv()

from vendors.flights.utils import create_uuid
from users.models import LookupAirports
class Mongo:
    def __init__(self):
        monog_uri = os.getenv('MONGO_URL')
        self.mongo_client = MongoClient(monog_uri)
        self.db = self.mongo_client['project']
        self.searches = self.db['searches'] 
        self.vendors = self.db['vendors']
        self.offline_billing = self.db['offline_billing']
        self.flight_supplier = self.db['flight_suppliers']
        self.session_data = []

    def create_session(self,data,user,vendors,session_id):
        timestamp = int(time.time())
        vendor_status = {}
        for x in vendors:
            vendor_dict = {x.get_vendor_id():{"status":"Start"}}
            vendor_status.update(vendor_dict)
        flight_type = get_flight_type(data,user)
        master_doc = {
            "service_type": "flight",
            "type": "master",
            "session_id": session_id,
            "flight_type":flight_type,
            "user_id": user.email,
            "name":user.first_name +" " + user.last_name if user.last_name else "",
            "email":user.email,
            "phone":user.phone_number,
            "organaization":str(user.organization_id),
            "organaization_type":str(user.organization.organization_type),
            "journey_type": data.get("journey_type"),
            "journey_details":data.get("journey_details"),
            "passenger_details":data.get("passenger_details"),
            "cabin_class":data.get("cabin_class"),
            "fare_type":data.get("fare_type","Regular"),
            "preffered_airline":data.get("preffered_airline"),
            "is_direct_flight":data.get("is_direct_flight"),
            "status": "in_progress",
            "vendors":vendor_status,
            "timestamp": timestamp,
            "createdAt":  datetime.now(),
        }
        self.searches.insert_one(master_doc)
        return session_id,flight_type


    def store_raw_data(self, session_id, vendor, data):
        timestamp = int(time.time())
        raw_id = create_uuid("RAW")

        raw_doc = {
            "raw_id":raw_id,
            "service_type": "flight",
            "session_id":session_id,
            "type": "raw",
            "vendor": vendor.get("id"),
            "vendor_name": vendor.get("name"),
            "data": data,
            "timestamp": timestamp,
            "createdAt":  datetime.now(),
        }
        vendor["raw"] = raw_id
        self.searches.insert_one(raw_doc)
        self.update_session_raw_status(session_id,vendor)
        return raw_doc
    def store_unified_data(self, session_id, vendor, data):
        timestamp = int(time.time())
        unified_id = create_uuid("UNI")

        unified_doc = {
            "unified_id":unified_id,
            "service_type": "flight",
            "session_id":session_id,
            "type": "unified",
            "vendor": vendor.get("id"),
            "vendor_name": vendor.get("name"),
            "data": data,
            "timestamp": timestamp,
            "createdAt":  datetime.now(),
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
        vendor["updated_at"] = time.time()
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
        vendor["updated_at"] = time.time()

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

    def check_session_validity(self, master_doc):
        current_epoch = int(time.time())
        session = master_doc
        if session and current_epoch - session["timestamp"] < 1500:  # 25 minutes = 1500 seconds
            return True
        return False
    
    def log_vendor_api(self,data):
        
            misc_value = data.get("misc", "").strip()
            session_id = data.get('session_id')
            booking_id = data.get('booking_id')
            master_doc = {
                "vendor": data.get("vendor"),
                "url": data.get("url", ""),
                "headers": data.get("headers", ""),
                "request_type": data.get("request_type", ""),
                "payload": data.get("payload"),
                "response": data.get("response"),
                "createdAt": datetime.now(),
                "api": data.get("api", "POST")}|\
                ({"misc": misc_value} if misc_value else {})|\
                    ({"session_id": session_id} if session_id else {})|\
                    ({"booking_id": booking_id} if booking_id else {})
            self.flight_supplier.insert_one(master_doc)
       

    def fetch_all_with_sessionid(self,**kwargs):
        try:
            if not self.session_data:
                self.session_data = list(self.searches.find({"session_id": kwargs.get("session_id")}))
                filterd_data = list(filter(lambda x:x["type"] == kwargs.get("type"),self.session_data))
            else:
                filterd_data = list(filter(lambda x:x["type"] == kwargs.get("type"),self.session_data))
            return filterd_data
        except:
            return []
