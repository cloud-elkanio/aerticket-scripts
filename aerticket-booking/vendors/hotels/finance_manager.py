from datetime import datetime
import os
import requests

from vendors.hotels import mongo_handler
from vendors.hotels.models import HotelEasylinkBilling


class FinanceManager:
    def __init__(self,user):
        self.user = user
        self.bta_env = os.getenv('BTA_ENV')
        self.org = user.organization
        self.easy_link = user.organization.easy_link_billing_account
        data = self.easy_link.data[0]
        self.base_url = data.get("url")
        self.branch_code = data.get("branch_code")
        self.portal_reference_code = data.get("portal_reference_code")
        self.mongo_client = mongo_handler.Mongo()
    
    def hotel_billing(self,booking_id):
        easy_link_data = {data.key:data.value for data in HotelEasylinkBilling.objects.filter(booking_id = booking_id)}
        self.process_hotel_billing([easy_link_data])


    def process_hotel_billing(self,data_list,itinerary_id = "",display_id = ""):
        url = self.base_url+"/processEasyMiscBillImp/?sBrCode="+self.branch_code+"&PortalRefCode="+self.portal_reference_code
        easy_link_payload = "<Invoicedata>\r\n"
        easy_link_payload += "    <Invoice\r\n"

        for data in data_list:
            for key, value in data.items():
                easy_link_payload += f'    {key}="{value}"\r\n'

            easy_link_payload += "    />\r\n</Invoicedata>"
        print("\n\n")
        print("easy_link_payload = ",easy_link_payload)

        headers = {
        }
        response = requests.post(
            url,
            headers=headers,
            data=easy_link_payload,
            timeout=200
        )
        print("easy_link_response = ",response.text)
        print("\n\n")
        easy_doc = {"url":url,"payload": easy_link_payload,"response": response.text,"type":"easy_link","itinerary_id":str(itinerary_id),
                    "display_id":display_id,"payload_json":data_list,"refund":False,"createdAt":datetime.now()}
        self.mongo_client.vendors.insert_one(easy_doc)
