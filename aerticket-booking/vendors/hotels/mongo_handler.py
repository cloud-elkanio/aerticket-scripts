
from datetime import datetime
import os
from common.models import LookupAirports
from pymongo import MongoClient
import time

from common.utils import create_uuid


class Mongo:
    def __init__(self):
        monog_uri = os.getenv('MONGO_URL')
        self.mongo_client = MongoClient(monog_uri)
        self.db = self.mongo_client['project']
        self.searches = self.db['searches'] 
        self.vendors = self.db['vendors']
        self.offline_billing = self.db['offline_billing']
        self.session_data = []
    
    def create_session(self,data,user,vendors,session_id):
        timestamp = int(time.time())
        vendor_status = {}
        for x in vendors:
            vendor_dict = {x.get_vendor_id():{"status":"Start"}}
            vendor_status.update(vendor_dict)

        master_doc = {
            "service_type": "hotel",
            "type": "master",
            "session_id": str(session_id),
            "user_id": user.email,
            "name":user.first_name +" " + user.last_name if user.last_name else "",
            "email":user.email,
            "phone":user.phone_number,
            "organaization":str(user.organization_id),
            "organaization_type":str(user.organization.organization_type),
            "status": "in_progress",
            "vendors":vendor_status,
            "timestamp": timestamp,
            "search_payload":data
        }
        self.searches.insert_one(master_doc)
        return session_id
    
    def update_session_status(self, session_id, status):
        self.searches.update_one(
            {"session_id": session_id, "type": "master"},
            {"$set": {"status": status}}
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
    
    def store_raw_data(self, session_id, vendor, data):
        timestamp = int(time.time())
        raw_id = create_uuid("RAW")

        raw_doc = {
            "raw_id":raw_id,
            "service_type": "Hotels",
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

    def check_session_validity(self, master_doc):
        current_epoch = int(time.time())
        session = master_doc
        if session and current_epoch - session["timestamp"] < 1500:  # 25 minutes = 1500 seconds
            return True
        return False

    def update_session_unified_status(self, session_id,vendor):
        update_data = {}
        condition = vendor.get("unified")
        vendor["updated_at"] = time.time()

        update_data[f"{condition}"] = vendor
        print("update_data = ",update_data)
        self.searches.update_one(
            {"session_id": session_id, "type": "master"},
            {
                "$set": {
                    f"unified.{key}": value for key, value in update_data.items()
                }
            }
        )
    
    def store_unified_data(self, session_id, vendor, data):
        timestamp = int(time.time())
        unified_id = create_uuid("UNI")

        unified_doc = {
            "unified_id":unified_id,
            "service_type": "hotels",
            "session_id":session_id,
            "type": "unified",
            "vendor": vendor.get("id"),
            "vendor_name": vendor.get("name"),
            "data": data,
            "timestamp": timestamp
        }
        vendor["unified"] = unified_id

        self.searches.insert_one(unified_doc)
        self.update_session_unified_status(session_id,vendor)

        return unified_doc

    def fetch_all_with_sessionid(self,**kwargs):
        try:
            if not self.session_data:
                self.session_data = list(self.searches.find({"session_id": kwargs.get("session_id")}))
                filterd_data = list(filter(lambda x:x["type"] == kwargs.get("type"),self.session_data))
            else:
                filterd_data = list(filter(lambda x:x["type"] == kwargs.get("type"),self.session_data))
            return filterd_data
        except Exception as e:
            print(str(e))
            return []
    
    # def fetch_hotel_details(self,**kwargs):
    #     self.session_data = list(self.searches.find({"session_id": kwargs.get("session_id")})) 
    #     if self.session_data != []:
    #         # import pdb;pdb.set_trace()
    #         for session in self.session_data:
    #             result = next((hotel for hotel in session['data'] if hotel['hotel_code'] == kwargs['hotel_code']), None)
    #             if result:
    #                 return result
    #         return {}
    #     else:
    #         return {}

    def fetch_hotel_details(self,**kwargs):
        return list(self.searches.find({"session_id": kwargs.get("session_id"),"type":"unified"})) 
        # room_code = kwargs.get('room_code',[])
        # print(room_code)
        # if self.session_data != []:
        #     # import pdb;pdb.set_trace()
        #     for session in self.session_data:
        #         result = next((hotel for hotel in session['data'] if hotel['hotel_code'] == kwargs['hotel_code']), None)
        #         if result:
        #             if room_code != []:
        #                 result['booking_options'] = [option for option in result['booking_options'] if option['room_code'] in room_code]
        #             for i in result['booking_options']:
        #                     print(i['room_code'])
        #             return result
        #     return {}
        # else:
        #     return {}
        