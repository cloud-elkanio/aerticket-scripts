
from common.models import PaymentDetail
from users.models import OrganizationSupplierIntegeration,SupplierIntegration
from vendors.hotels.finance_manager import FinanceManager
from vendors.hotels import mongo_handler
from common import utils
from vendors.hotels.models import HotelBooking
from vendors.hotels.tbo.manager import Manager as TBO  
from vendors.hotels.grn.manager import Manager as GRN  


import time
import threading

class HotelManager:
    def __init__(self, user):
        self.user = user
        self.mongo_client = mongo_handler.Mongo()
        self.module_name = 'hotel'
        self.master_doc = None
    
    def get_vendors(self):
        vendors=  []
        associated_suppliers_list = OrganizationSupplierIntegeration.objects.filter(organization=self.user.organization,is_enabled=True).values_list('supplier_integeration', flat=True)
        # import pdb;pdb.set_trace()
        supplier_integrations = SupplierIntegration.objects.filter(id__in=associated_suppliers_list,integration_type="Hotels",is_active = True)
        for x in supplier_integrations:
            manager = eval(x.name)(data = x.data,vendor = x,mongo_client = self.mongo_client)
            vendors.append(manager)
        return vendors
    
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
    
    def create_session(self,data):
        self.vendors = self.get_vendors()
        if len(self.vendors)>0:
            status = {"status":"success"}
        else:
            status = {"status":"failure","info":"No suppliers are associated with your account. Kindly contact support for assistance.",
                      "vendors":self.vendors}
        session_id = utils.create_uuid()
        thread = threading.Thread(target=self.get_hotels, args=(session_id,data))
        thread.start()
        return {"session_id":session_id}|status
    

    def get_hotels(self, session_id,data):
        session_id = self.mongo_client.create_session(data,self.user,self.vendors,session_id)
        data = data | {"session_id":session_id}
        threads = []
        raw_results = []
        unified_results = []
        def fetch_from_vendor(vendor):
            # start = time.time()
            result = vendor.search_results(data,session_id,self.user)
            # end = time.time()
            # vendor_data = {"name":vendor.name(),"id":vendor.get_vendor_id(),"duration":end-start,"status":result.get("status")}
            # raw_results.append(self.mongo_client.store_raw_data(session_id,vendor_data, result.get("data")))
            # self.mongo_client.update_vendor_search_status(session_id,vendor.get_vendor_id(),"Raw")
            # if result.get("status") == "success":
            #     start = time.time()
            #     fare_detatils = utils.get_fare_markup(self.user)
            #     unified_response = vendor.converter(result.get("data"),data,fare_detatils)
            #     end = time.time()
            #     if unified_response.get("status") == "success":
            #         vendor_data = {"name":vendor.name(),"id":vendor.get_vendor_id(),"duration":end-start,"status":unified_response.get("status")}
            #         unified_results.append(self.mongo_client.store_unified_data(session_id, vendor_data, unified_response.get("data")))
            #         self.mongo_client.update_vendor_search_status(session_id,vendor.get_vendor_id(),"Unified")
            #     else:
            #         self.mongo_client.update_vendor_search_status(session_id,vendor.get_vendor_id(),"Unified_Failed")
            # else:
            #     self.mongo_client.update_vendor_search_status(session_id,vendor.get_vendor_id(),"Raw_Failed")
        for vendor in self.vendors:
            thread = threading.Thread(target=fetch_from_vendor, args=(vendor,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Once all threads are done, update the master session status
        self.mongo_client.update_session_status(session_id, "completed")


    def hotel_search_data(self, session_id,data):
        pass

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

    def check_session_validity(self, session_id,fast_mode =False):
        self.master_doc = self.get_master_doc(session_id,fast_mode)
        status = self.mongo_client.check_session_validity(self.master_doc)
        return status
    
    def get_unified_doc(self,unified_ids):
        filter_data = {
                "unified_id": {"$in": unified_ids},
                "type" : "unified",
                "service_type":"hotel"
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
                "service_type":"hotels",
                "session_id" :session_id
            }
        self.mongo_client.searches.update_many(filter_query, {"$set": {"is_shown": True}})


    def get_hotel_details(self,**kwargs):
        self.session_data = self.mongo_client.fetch_hotel_details(**kwargs)
        is_dynamic_form = kwargs.get('is_dynamic_form',False)
        room_code = kwargs.get('room_code',[])
        result = {}
        vendor_name = None
        if self.session_data != []:            
            for session in self.session_data:
                result = next((hotel for hotel in session['data'] if hotel['hotel_code'] == kwargs['hotel_code']), None)
                vendor_name = session['vendor_name']
                if is_dynamic_form and vendor_name:
                    vendor_class = eval(vendor_name)()
                else:
                    vendor_class = None
                if result:
                    if room_code != []:
                        for room_option in result['room_options']:
                            # room_option['booking_options'] = [{**option,**{vendor_class.get_dynamic_form(option['pax'])}}\
                            #             for option in room_option['booking_options']\
                            #                 if option['room_code'] in room_code]  
                            # import pdb;pdb.set_trace()
                            if vendor_class:
                                room_option['pax_form'] = vendor_class.get_pax_form(room_option['pax'])
                            for option in room_option['booking_options']:
                                if option['room_code'] in room_code:
                                    room_option['selected_room'] = option
                                    room_option['heading'] = f"Room {room_option['room_index']}: {option['name']}"
                    if vendor_class:
                        result['booking_holder_form'] = vendor_class.get_booking_holder_form()
                    break

        
            # result["dynamic_form"] = vendor_class.get_dynamic_form(self.master_doc['search_payload']['room_pax'])
        return {"data":result,"session_break":result == {}}

        #     return {}
        # else:
        #     return {}

        
        # if is_dynamic_form:
        #     hotel_details['dynamic_form'] = self.get_dynamic_form(hotel_details)
        # return hotel_details
    
    
    
    def initiate_payment(self,payment_id):
        pass

    def purchase(self,payment_id):
        payment = PaymentDetail.objects.filter(id = payment_id).first()
        supplier = payment.hotel_booking.vendor
        hotel_booking = payment.hotel_booking
        booking_id = payment.hotel_booking.id
        manager = eval(supplier.name)(data = supplier.data,vendor = supplier,mongo_client = self.mongo_client)
        try:
            result = manager.purchase(booking_id)
        except:
            raise Exception(f'missing "purchase" function in {supplier.name} class')
        hotel_booking.vendor_booking_endpoint = result.get('url')
        hotel_booking.vendor_booking_payload = result.get('payload')
        hotel_booking.vendor_booking_response = result.get('response')
        if result.get('status') in ["success",200]:
            hotel_booking.status = "confirmed"
            FinanceManager(hotel_booking.created_by).hotel_billing(hotel_booking.id)
        else:
            hotel_booking.status = "failed"
        hotel_booking.save()
    
    def cancel_booking(self,booking_id):
        hotel_booking = HotelBooking.objects.select_related("hotel", "vendor").get(id=booking_id)
        supplier = hotel_booking.vendor
        manager = eval(supplier.name)(data = supplier.data,vendor = supplier,mongo_client = self.mongo_client)
        try:
            result = manager.cancel_booking(booking_id)
        except:
            raise Exception(f'missing "cancel_booking" function in {supplier.name} class')
        if result["status"] == True:
            hotel_booking.status = "cancelled"
            hotel_booking.save()
        return result
    
    def reject_failed_booking(self,booking_id):
        hotel_booking = HotelBooking.objects.select_related("hotel", "vendor").get(id=booking_id)
        hotel_booking.status = "rejected"
        hotel_booking.save()
        result = {
            "status":True
        }
        
        return result
    
    def confirm_failed_booking(self,booking_id):
        hotel_booking = HotelBooking.objects.select_related("hotel", "vendor").get(id=booking_id)
        hotel_booking.status = "confirmed"
        hotel_booking.save()
        FinanceManager(hotel_booking.created_by).hotel_billing(hotel_booking.id)
        result = {
            "status":True
        }
        return result
        