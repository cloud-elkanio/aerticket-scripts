
import uuid

from vendors.buses import mongo_handler,utils
from .flyshop.api import get_city_list
from users.models import SupplierIntegration, OrganizationSupplierIntegeration, UserDetails
from .flyshop.manager import Manager as FlyshopManager
from .TBO.TBO import Manager as TBO
from django.db import transaction
import json
from .models import BusCity,BusBooking,BusBookingSearchDetail,BusBookingFareDetail,BusBookingPaxDetail,BusBookingPaymentDetail
import time
from datetime import datetime
from common.models import DailyCounter
from django.utils import timezone
from rapidfuzz import process, fuzz

import difflib
import threading



class BusManager:


    def __init__(self, user):
        self.user = user
        self.mongo_client = mongo_handler.Mongo()
        self.master_doc={}
        # self.creds = self.get_credentials()


    def create_uuid(self, suffix=""):
        if suffix == "":
            return str(uuid.uuid4())
        else:
            return suffix + "-" + str(uuid.uuid4())

    def sync_city(self):

        vendors = []
        associated_suppliers_list = OrganizationSupplierIntegeration.objects.filter(organization=self.user.organization,
                                                                                    is_enabled=True).values_list(
            'supplier_integeration', flat=True)

        supplier_integrations = SupplierIntegration.objects.filter(id__in=associated_suppliers_list,
                                                                   integration_type='Bus', is_active=True)

        data = None
        cities = {}
        for x in supplier_integrations:
            if x.name == "FlyShop":
                data = x.data
                manager = FlyshopManager(credentials=data, uuid=x.id, mongo_client=self.mongo_client)

                vendors.append(manager)
            if x.name == "TBO":
                data = x.data
                if  x.expired_at>int(time.time()) and x.token!=None:
                    data = x.data | {"token":x.token,"expired_at":x.expired_at}
                    manager = TBO(credentials=data,uuid =x.id,mongo_client=self.mongo_client,is_auth = False)

                else:
                    manager = TBO(credentials=data,uuid =x.id,mongo_client=self.mongo_client,is_auth = True)
                    x.update_token(manager.token)
                
                vendors.append(manager)
        city_data = {}
        new_objs = []
        update_objs = []
        for manager in vendors:
            cities = manager.create_city_list()
            errors = []
            city_objs = []
            city_ids = [str(city_data['city_id']) for city_data in cities]
            existing = BusCity.objects.filter(city_id__in=city_ids,supplier=manager.vendor_uuid)
            existing_map = {str(obj.city_id): obj for obj in existing}
            new_objs = []
            update_objs = []

            for city_data in cities:
                if str(city_data['city_id']) in existing_map:
                    # Update the existing instance
                    obj = existing_map[str(city_data['city_id'])]
                    obj.city_id = city_data['city_id']
                    obj.supplier_id = manager.vendor_uuid
                    obj.city_name = city_data['city_name']
                    obj.country = city_data['country']
                    obj.created_at = time.time()  # or update with new timestamp
                    update_objs.append(obj)
                else:
                    new_objs.append(BusCity(
                        supplier_id=manager.vendor_uuid,
                        city_id=city_data['city_id'],
                        city_name=city_data['city_name'],
                        country = city_data['country'],
                        created_at=time.time()
                    ))

            if new_objs:
                BusCity.objects.bulk_create(new_objs)
            if update_objs:

                # Specify the fields you want to update
                BusCity.objects.bulk_update(update_objs, ['supplier_id', 'city_name','country', 'created_at'])


        return new_objs+update_objs

    def search_city(self, search_query):
        # Get the filtered queryset
        start = time.time()
        cities = BusCity.objects.select_related('supplier').filter(
            city_name__icontains=search_query,
            supplier__is_active=True
        ).order_by('id')
        
        # Initialize groups and a lookup list for group names
        grouped_cities = []
        group_names = []
        
        start = time.time()
        for city in cities:
            city_key = f"{city.city_id}_{city.supplier_id}"
            if grouped_cities:
                # Find the best matching group using RapidFuzz
                match = process.extractOne(
                    city.city_name,
                    group_names,
                    scorer=fuzz.ratio
                )
                if match is not None:
                    matched_name, score, idx = match
                    if score >= 95:
                        grouped_cities[idx]['ids'].append(city_key)
                        continue
            
            # No similar group found; create a new group
            grouped_cities.append({
                'name': city.city_name,
                'country': city.country.country_name if city.country else "",
                'ids': [city_key]
            })
            group_names.append(city.city_name)
        
        start = time.time()
        final_response = [
            {
                'id': '_$_'.join(group['ids']),
                'name': group['name'],
                'country': group['country']
            }
            for group in grouped_cities
        ]
        return final_response

    def create_session(self, data):
        self.vendors = self.get_vendors()

        if len(self.vendors)>0:
            status = {"status":"success"}
        else:
            status = {"status":"failure","info":"Sorry, we couldn't find any Bus data for your search. Please contact support for further assistance.",
                      "vendors":self.vendors}
        session_id = utils.create_uuid()
        thread = threading.Thread(target = self.get_buses, args=(session_id,data))
        thread.start()
        return {"session_id":session_id}|status

    def get_buses(self, session_id,data):
        
        from_segments = data['from'].split('_$_')
        to_segments = data['to'].split('_$_')
        from_id,from_vendor_id = from_segments[0].split('_')
        to_id,to_vendor_id = to_segments[0].split('_')
        from_data = BusCity.objects.filter(city_id = from_id,supplier__id = from_vendor_id).first()
        to_data = BusCity.objects.filter(city_id = to_id,supplier__id = to_vendor_id).first()
        data = data | {"from_city":from_data.city_name,"to_city":to_data.city_name}
        session = self.mongo_client.create_session(data,self.user,self.vendors,session_id)
        filtered_data = {}
        currency_code = self.user.organization.organization_country.currency_code

        # Process the 'from' segments
        for segment in from_segments:
            from_city, vendor_id = segment.split('_')
            # Initialize the vendor entry with the from city
            filtered_data[vendor_id] = {'from': from_city}

        # Process the 'to' segments
        for segment in to_segments:
            to_city, vendor_id = segment.split('_')
            # Add the to city to the corresponding vendor entry
            if vendor_id in filtered_data:
                filtered_data[vendor_id]['to'] = to_city
        
        for key in filtered_data:
            filtered_data[key] = filtered_data[key]|{"session_id":session_id,"date":data["date"],'currency':currency_code}
        threads = []
        raw_results = []
        unified_results = []
        def fetch_from_vendor(vendor):
            start = time.time()
            result = vendor.search_bus(filtered_data[str(vendor.vendor_uuid)])
            end = time.time()
            vendor_data = {"name":vendor.name(),"id":vendor.get_vendor_id(),"duration":end-start,"status":result.get("status")}
            raw_results.append(
                            self.store_raw_data(
                                session_id,vendor_data, result.get("data"),
                                filtered_data[str(vendor.vendor_uuid)]
                                            )
                            )
            if result.get("status") == "success":
                self.mongo_client.update_vendor_search_status(session_id,vendor.get_vendor_id(),"Raw")
                start = time.time()
                fare_detatils = utils.get_fare_markup(self.user)
                unified_response = vendor.converter(result.get("data"),filtered_data[str(vendor.vendor_uuid)],fare_detatils)
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

    def get_seatmap(self,data):
        self.session_id = data.get('session_id')
        segment_id = data.get('segment_id')
        # VEN-9f0ed9c4-941b-41a8-847c-dd37ab24168e_$_SEG-eb465621-ae67-4bcb-964d-71e9198055ff
        vendor_uuid = segment_id.split("_$_")[0].split("VEN-")[1]
        manager = self.get_manager_from_id(vendor_uuid)
        raw_data = self.mongo_client.fetch_all_with_sessionid(session_id = self.session_id, type =  "raw")[0]
        unified_data = self.mongo_client.fetch_all_with_sessionid(session_id = self.session_id, type =  "unified")[0]
        current_segment =self.get_unified_segment(segment_id,unified_data)
        fare_detatils = utils.get_fare_markup(self.user)
        response = manager.get_seatmap(self.session_id,segment_id,raw_data,current_segment,fare_detatils)
        mongo_doc = {
                    "raw": response.get('raw'),
                    "unified":response.get('data'),
                    "type":"seatmap",
                    "session_id":self.session_id,
                    "segment_id":segment_id,
                    "createdAt":datetime.now()
                    }
        self.mongo_client.searches.update_one(
                    {"session_id": self.session_id, "segment_id": segment_id,"type":"seatmap",},
                    {"$set": mongo_doc},
                    upsert=True
                    )
        return {'data':response.get('data'),"status":response.get('status')}
    
    def get_pickup_drop(self,data):
        self.session_id = data.get('session_id')
        segment_id = data.get('segment_id')
        # VEN-9f0ed9c4-941b-41a8-847c-dd37ab24168e_$_SEG-eb465621-ae67-4bcb-964d-71e9198055ff
        vendor_uuid = segment_id.split("_$_")[0].split("VEN-")[1]
        manager = self.get_manager_from_id(vendor_uuid)
        raw_data = self.mongo_client.fetch_all_with_sessionid(session_id = self.session_id, type =  "raw")[0]
        unified_data = self.mongo_client.fetch_all_with_sessionid(session_id = self.session_id, type =  "unified")[0]
        current_segment =self.get_unified_segment(segment_id,unified_data)
        response = manager.pickup_drop_fetch(self.session_id,segment_id,raw_data,current_segment)
        mongo_doc = {
                    "raw": response.get('raw'),
                    "unified":response.get('data'),
                    "type":"pickup_drop",
                    "session_id":self.session_id,
                    "segment_id":segment_id,
                    "createdAt":datetime.now()
                    }
        self.mongo_client.searches.update_one(
                    {"session_id": self.session_id, "segment_id": segment_id,"type":"pickup_drop",},
                    {"$set": mongo_doc},
                    upsert=True
                    )
        return {'data':response.get('data'),"status":response.get('status')}
            

    def get_unified_segment(self,segment_id,unified_data):
        unified = [x for x in unified_data.get("data") if x["segmentID"]==segment_id]
        return unified[0] if len(unified)>0 else []
    def get_unified_seatmap(self,segment_id,unified_data):
        unified = [
                seat
                for section in unified_data["layoutData"].values()      # iterates over 'lower' and 'upper'
                for row in section                             # iterates over rows in each section
                for seat in row["seats"]                         # iterates over seats in a row
                          # check for matching seatmapID
            ]
        
        return unified[0] if len(unified)>0 else []
    def store_raw_data(self, session_id, vendor, data,misc):        
        raw_doc = self.mongo_client.store_raw_data( session_id, vendor, data,misc)
        return raw_doc
    def store_unified_data(self, session_id, vendor, data):        
        unified = self.mongo_client.store_unified_data( session_id, vendor, data)
        return unified

    def update_session_status(self, session_id, status):
        self.mongo_client.update_session_status(session_id, status)



    def get_vendors(self,**kwargs):
        vendors = []
        associated_suppliers_list = OrganizationSupplierIntegeration.objects.filter(organization=self.user.organization,is_enabled=True).values_list('supplier_integeration', flat=True)
        supplier_integrations = SupplierIntegration.objects.filter(id__in=associated_suppliers_list,integration_type="Bus",is_active = True)
        for x in supplier_integrations:
            if x.name == "TBO":
                data = x.data
                if  x.expired_at>int(time.time()) and x.token!=None:
                    data = x.data | {"token":x.token,"expired_at":x.expired_at}
                    manager = TBO(credentials=data,uuid =x.id,mongo_client=self.mongo_client,is_auth =False)
                else:
                    manager = TBO(credentials=data,uuid =x.id,mongo_client=self.mongo_client,is_auth =True)
                    x.update_token(manager.token)
                vendors.append(manager)
        return vendors

    def create_booking(self,data):
        session_id = data.get("session_id")
        segment_id = data.get("segment_id")
        vendor_uuid = segment_id.split("_$_")[0].split("VEN-")[1]
        manager = self.get_manager_from_id(vendor_uuid)
        date =self.master_doc.get('search_data').get('date')
        pickup_id = data.get("pickup_id")
        dropoff_id = data.get("dropoff_id")
  

        unified_data = self.mongo_client.fetch_all_with_sessionid(session_id = self.session_id, type =  "unified")[0]
        current_segment =self.get_unified_segment(segment_id,unified_data)
        raw_segment_data = self.mongo_client.fetch_all_with_sessionid(session_id = self.session_id, type =  "raw")[0]
        raw_segment = manager.get_raw_segment(segment_id,raw_segment_data)
        TraceId = raw_segment_data.get("data").get("BusSearchResult").get("TraceId")
        seatmap_data = self.mongo_client.fetch_all_with_sessionid(session_id = self.session_id,segment_id=segment_id, type =  "seatmap")[0]
        locations_data = self.mongo_client.fetch_all_with_sessionid(session_id = self.session_id,segment_id=segment_id, type =  "pickup_drop")[0]
       
        pickup_data = [x for x in locations_data.get('unified').get('BoardingPoints') if x["locationID"]== pickup_id][0]
        dropoff_data = [x for x in locations_data.get('unified').get('DropoffPoints') if x["locationID"]== dropoff_id][0]
        seatmaps = [x for x in seatmap_data] 

        seletced_seat_ids = [x.get('seat_id') for x in data.get('pax_details')]
        selected_seatmaps = [self.get_unified_seatmap(x,seatmap_data.get('unified')) for x in seletced_seat_ids ]
        

        from_id = raw_segment_data.get('from')
        from_obj = BusCity.objects.filter(city_id =from_id,supplier_id =vendor_uuid ).first()
        to_id = raw_segment_data.get('to')
        to_obj = BusCity.objects.filter(city_id =to_id,supplier_id =vendor_uuid ).first()


        pax_details = data.get("pax_details")

        search_details = BusBookingSearchDetail.objects.create(
                    travel_date = date,
                    origin = from_obj,
                    destination=to_obj,
                    pickup_id = pickup_data.get("index"),
                    pickup_name = pickup_data.get("name"),
                    pickup_time = pickup_data.get("time"),
                    pickup_address = pickup_data.get("address"),
                    pickup_contact = pickup_data.get("contact"),
                    dropoff_id = dropoff_data.get("index"),
                    dropoff_name = dropoff_data.get("name"),
                    dropoff_time = dropoff_data.get("time"),
                    dropoff_address = dropoff_data.get("address"),
                    dropoff_contact = dropoff_data.get("name"),
                )

        bus_booking_payment_details = BusBookingPaymentDetail.objects.create(
                    supplier_published_fare = sum([selected_seatmap.get('price',{}).get('supplier_published_fare') for selected_seatmap in selected_seatmaps]),
                    supplier_offered_fare =  sum([selected_seatmap.get('price',{}).get('supplier_offered_fare') for selected_seatmap in selected_seatmaps]),
                    created_at = int(time.time()),
                    new_published_fare =  sum([selected_seatmap.get('price',{}).get('publishedPrice') for selected_seatmap in selected_seatmaps]),
                    new_offered_fare =  sum([selected_seatmap.get('price',{}).get('offeredPrice') for selected_seatmap in selected_seatmaps])
                )

        booking = BusBooking.objects.create(
                            display_id = generate_booking_display_id(),
                            session_id=session_id,
                            segment_id=segment_id,
                            user=self.user,
                            search_detail=search_details,
                            bus_payment_details = bus_booking_payment_details,
                            pax_count = len(pax_details),
                            gst_details=json.dumps(data.get("gstDetails")),
                            contact=json.dumps(data.get("contact")),
                            status='Enquiry',
                            booked_at=time.time(),  
                            cancelled_at=None, 
                            cancelled_by=None,
                            modified_at=time.time(), 
                            modified_by=self.user,
                            misc = {"ResultIndex":raw_segment.get('ResultIndex'),"TraceId":TraceId},
                            departure_time = current_segment.get('departureTime'),
                            arrival_time = current_segment.get('arrivalTime'),
                            bus_type = current_segment.get('busType'),
                            operator = current_segment.get('operator'),
                            provider = current_segment.get('provider'),
                            cancellation_details = current_segment.get('cancellationPolicies')
                        )
        for pax in pax_details:
            seat_id = pax.get('seat_id')
            seat_data = self.get_unified_seatmap(seat_id,seatmap_data.get('unified'))
            raw_seat_data = manager.get_raw_seatmap(seat_id,seatmap_data.get('raw'))
            seatmapID = raw_seat_data.pop('seatmapID')
            date_obj  = datetime.strptime(pax.get('dob'), "%d-%m-%Y")
            dob = date_obj.strftime("%Y-%m-%dT00:00:00.000Z")
            pax_detail = BusBookingPaxDetail.objects.create(
                booking=booking,
                title=pax.get('title'),
                pax_type=pax.get('type'),
                seat_type=seat_data.get('seatType'),
                seat_name=seat_data.get('seatName'),
                gender=pax.get('gender'),
                first_name=pax.get('first_name'),
                last_name=pax.get('last_name'),
                dob=dob,
                seat_id=pax.get('seat_id'),
                misc = {"seat":raw_seat_data} 
            )


            fare_markup = utils.get_fare_markup(self.user)
            # Create BusBookingFareDetail instance linked to the pax_detail
            BusBookingFareDetail.objects.create(
                pax=pax_detail,
                published_fare=seat_data.get('price').get('publishedPrice', 0),
                offered_fare=seat_data.get('price').get('offeredPrice', 0),
                organization_discount=seat_data.get('price').get('discount', 0),
                dist_agent_markup=fare_markup.get('distributor_markup', 0),
                dist_agent_cashback=fare_markup.get('distributor_cashback', 0),
                fare_breakdown=json.dumps(seat_data.get('price')),
            )
        self.mongo_client.bus_supplier.insert_one({"session_id":session_id,"booking_id":str(booking.id),
                                                "booking_display_id":booking.display_id,"type":"create_booking","createdAt":  datetime.now(),})
        
        return {"status" :"success", "booking":str(booking.id)}

    def purchase(self,**kwargs):
        booking_amount = float(kwargs["data"].get("amount",0))
        from_razorpay = kwargs["data"].get("from_razorpay",False)
        booking = BusBooking.objects.filter(id = kwargs["data"]["booking_id"]).first()
        if booking and not from_razorpay:
            payment_instance = booking.bus_payment_details
            payment_instance.payment_type = kwargs["data"].get("payment_mode","wallet")
            payment_instance.save(update_fields = ["payment_type"])
        if not kwargs.get("wallet") and not from_razorpay:
            from common.razor_pay import razorpay_payment # imported here to solve circular import error
            razor_response = razorpay_payment(user = booking.user,amount = booking_amount,module = "bus",
                                            booking_id = kwargs["data"]["booking_id"], 
                                            session_id = kwargs["data"]["session_id"])
            print("razor_response",razor_response)
            payment_status = True if razor_response.get("status") else False
            booking.save(update_fields = ["status"])
            return {"payment_status":payment_status,"payment_url":razor_response.get("short_url"),
                    "error":razor_response.get("error")}
        else:
            pax_details= BusBookingPaxDetail.objects.filter(booking=booking)
            vendor_uuid = booking.segment_id.split("_$_")[0].split("VEN-")[1]
            manager = self.get_manager_from_id(vendor_uuid)
            response_data = manager.purchase(booking.session_id,booking ,pax_details)

    def cancellation_charges(self,booking_id):
        booking = BusBooking.objects.filter(id = booking_id).first()
        vendor_uuiid = booking.segment_id.split("_$_")[0].split("VEN-")[1]
        manager = self.get_manager_from_id(vendor_uuiid)
        cancellation_charges_data = manager.get_cancellation_charges(booking.session_id,booking)    
        return cancellation_charges_data

    def cancel_ticket(self,booking_id,remarks):
        booking = BusBooking.objects.filter(id = booking_id).first()
        if booking.status == "Confirmed":
            vendor_uuiid = booking.segment_id.split("_$_")[0].split("VEN-")[1]
            manager = self.get_manager_from_id(vendor_uuiid)
            cancel_data = manager.cancel_ticket(booking.session_id,booking,remarks)    
            return cancel_data
        else:
            return {"status":"failure","info":"It looks like this ticket isn't eligible for cancellation. Please contact our customer support team for further assistance."}
       
    def get_manager_from_id(self,id):
        supplier_integration = SupplierIntegration.objects.filter(id=id).first()
        if supplier_integration.name == "TBO":
            data = supplier_integration.data
            if  supplier_integration.expired_at>int(time.time()) and supplier_integration.token!=None:
                data = supplier_integration.data | {"token":supplier_integration.token,"expired_at":supplier_integration.expired_at}
                manager = TBO(credentials=data,uuid =supplier_integration.id,mongo_client=self.mongo_client,is_auth =False)
            else:
                manager = TBO(credentials=data,uuid =supplier_integration.id,mongo_client=self.mongo_client,is_auth =True)
                supplier_integration.update_token(manager.token)
        return manager
    def check_session_validity(self, session_id,fast_mode =False):
        current_epoch = int(time.time())
        self.master_doc = self.get_master_doc(session_id,fast_mode)
        status = self.mongo_client.check_session_validity(self.master_doc)
        return status
    
    def update_is_showed_unified_docs(self,session_id,unified_ids):
        filter_query = {
                "unified_id": {"$in": unified_ids},
                "type" : "unified",
                "service_type":"bus",
                "session_id" :session_id
            }
        self.mongo_client.searches.update_many(filter_query, {"$set": {"is_shown": True}})
    
    def get_unified_doc(self,unified_ids):
        filter_data = {
                "unified_id": {"$in": unified_ids},
                "type" : "unified",
                "service_type":"bus"
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

    def get_bus_list(self, **kwargs):


        vendors = []
        associated_suppliers_list = OrganizationSupplierIntegeration.objects.filter(organization=self.user.organization,
                                                                                    is_enabled=True).values_list(
            'supplier_integeration', flat=True)

        supplier_integrations = SupplierIntegration.objects.filter(id__in=associated_suppliers_list,
                                                                   integration_type='Bus', is_active=True)

        data = None
        cities = {}
        for x in supplier_integrations:
            if x.name == "FlyShop":
                data = x.data
                data.update(kwargs)
                manager = FlyshopManager(creds=data, vendor=x, mongo_client=self.mongo_client)

                vendors.append(manager)

                buses = manager.fetch_city_list()
                if len(cities.get('CityDetails')) > 0:
                    cities['supplier_id'] = x.id
        return cities   

def generate_booking_display_id():
    now = timezone.now()
    today = now.date()
    with transaction.atomic():
        counter, created = DailyCounter.objects.select_for_update().get_or_create(date=today,module ='bus')
        counter.count += 1
        counter.save()
        booking_number = counter.count
    formatted_booking_number = f"{booking_number:04d}"
    day_month = now.strftime("%d%m")  # DDMM format
    year_suffix = now.strftime("%y")  # Last two digits of the year
    return f"BUS{year_suffix}-{day_month}-{formatted_booking_number}"
