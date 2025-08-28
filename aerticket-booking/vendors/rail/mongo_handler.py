import time
from pymongo import MongoClient
from datetime import datetime
# import pytz

import os

from dotenv import load_dotenv
load_dotenv() # put .env in settings containing folder

from vendors.flights.utils import create_uuid
class Mongo:
    def __init__(self):
        monog_uri = os.getenv('MONGO_URL')
        self.mongo_client = MongoClient(monog_uri)
        self.db = self.mongo_client['project']
        self.searches = self.db['rail_searches']
        self.staticData = self.db['rail_staticData']
        self.rail_supplier = self.db['rail_suppliers']

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
            self.rail_supplier.insert_one(master_doc)
        except:
            pass
    
    def store_raw_data(self, data, type):
        try:
            raw_doc = {

                "type": type,

                "data": data,

                "createdAt":  datetime.now()
            }
            self.searches.insert_one(raw_doc)
        except:
            pass
