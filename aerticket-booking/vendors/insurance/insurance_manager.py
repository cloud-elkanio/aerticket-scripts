import uuid

from vendors.insurance import mongo_handler,utils
from users.models import SupplierIntegration, OrganizationSupplierIntegeration, UserDetails,LookupCountry
from django.db import transaction
import json
from .models import (InsuranceBookingPaymentDetail,InsuranceBookingSearchDetail,InsuranceBooking,
                     InsuranceBookingFareDetail,InsuranceBookingPaxDetail) 
from .asego.asego import Manager as Asego

 
import time
from datetime import datetime
from common.models import DailyCounter
from django.utils import timezone


import difflib
import threading



class InsuranceManager:

    def __init__(self, user):
        self.user = user
        self.mongo_client = mongo_handler.Mongo()
        self.master_doc={}
    
    def sync_data(self,sync_info):
        print("sync_info",sync_info)
        vendors = []
        for key,value in sync_info.items():
            if key == "Asego":
                manager = Asego(credentials="", uuid="", mongo_client=self.mongo_client)
                manager.data_sync(value)
                

    def get_travel_categories(self):
        self.vendors = self.get_vendors()
        category_list = []
        for vendor in self.vendors:
            response =vendor.get_travel_categories()
            category_list.extend(response.get('data'))
        return category_list

    def get_travel_plans(self,category_id):

        category_uuid,vendor_uuid = category_id.split('_$_')
        print("category_uuid,vendor_uuid",category_uuid,vendor_uuid)
        manager = self.get_manager_from_id(vendor_uuid)
        plans = manager.get_plans(category_uuid)

        return plans.get('data')

    def get_plan_adddons(self,plan_id):

        plan_uuid,vendor_uuid = plan_id.split('_$_')
        print("plan_uuid,vendor_uuid",plan_uuid,vendor_uuid)
        manager = self.get_manager_from_id(vendor_uuid)
        addons = manager.get_plan_addons(plan_uuid)

        return addons.get('data')

    def create_booking(self,data):
        plan_id = data.get('plan_id')
        plan_uuid,vendor_uuid = plan_id.split('_$_')
        print("plan_uuid,vendor_uuid",plan_uuid,vendor_uuid)
        manager = self.get_manager_from_id(vendor_uuid)
        fare_detatils = utils.get_fare_markup(self.user)

        response = manager.get_modified_data(data,fare_detatils)
        modified_data = response.get('data')
        print("modified_data",modified_data.get('pax_details'))
        inusurance_search_details = InsuranceBookingSearchDetail.objects.create(
                    commensing_date = modified_data.get('travel_details').get('commensing_date'),
                    end_date =  modified_data.get('travel_details').get('end_date'),
                    duration= modified_data.get('travel_details').get('duration'),
                )
        

        inusurance_payment_details = InsuranceBookingPaymentDetail.objects.create(
                    supplier_published_fare = sum([pax.get('fareBreakdown',{}).get('supplier_published_fare') for pax in modified_data.get('pax_details')]),
                    supplier_offered_fare =  sum([pax.get('fareBreakdown',{}).get('supplier_offered_fare') for pax in modified_data.get('pax_details')]),
                    created_at = int(time.time()),
                    new_published_fare =  sum([pax.get('fareBreakdown',{}).get('publishedPrice') for pax in modified_data.get('pax_details')]),
                    new_offered_fare =  sum([pax.get('fareBreakdown',{}).get('offeredPrice') for pax in modified_data.get('pax_details')])
                )
        vendor = SupplierIntegration.objects.get(id=vendor_uuid)
        booking = InsuranceBooking.objects.create(
                    session_id ="session_id",
                    display_id = generate_booking_display_id(),
                    vendor = vendor,
                    user = self.user,
                    status = 'Enquiry',
                    booked_at=time.time(),  
                    cancelled_at=None, 
                    cancelled_by=None,
                    modified_at=time.time(), 
                    modified_by=self.user,
                    search_detail = inusurance_search_details,
                    insurance_payment_details =inusurance_payment_details,
                    misc = modified_data.get('misc'),
                    )
        data["booking_id"]=str(booking.id)
        pax_details = modified_data.get('pax_details')
        total_published = 0
        total_offered = 0
        total_discount = 0
        for pax in pax_details:
            date_obj  = datetime.strptime(pax.get('dob'), "%d-%m-%Y")
            dob = date_obj.strftime("%Y-%m-%dT00:00:00.000Z")
            country = pax.get('contact_details').get('country')
            country_obj  = LookupCountry.objects.get(id=country)
            print(type(country_obj))
            print(country_obj.pk)

            total_published+=pax.get("fareBreakdown").get('publishedPrice',0)
            total_offered+=pax.get("fareBreakdown").get('offeredPrice',0)
            total_discount+=pax.get("fareBreakdown").get('discount',0)
            pax_detail = InsuranceBookingPaxDetail.objects.create(
                booking=booking,
                title=pax.get('title'),
                gender=pax.get('gender'),
                first_name=pax.get('first_name'),
                last_name=pax.get('last_name'),
                dob=dob,
                
                address1 = pax.get('contact_details').get('address1'),
                address2 = pax.get('contact_details').get('address2'),
                passport = pax.get('passport'),
                city = pax.get('contact_details').get('city'),
                district = pax.get('contact_details').get('district'),
                state =pax.get('contact_details').get('state'),
                pincode = pax.get('contact_details').get('pincode'),
                phone_code = pax.get('contact_details').get('phone_code'),
                phone_number = pax.get('contact_details').get('phone_number'),
                country = country_obj,
                email = pax.get('contact_details').get('email'),
                nominee_name =  pax.get('nominee'),
                relation =  pax.get('relation'),
                past_illness = pax.get('past_illness'),
                addons = pax.get('addons') ,
                misc ={"plan":modified_data.get('misc'),"fare":pax.get('fare')},
                status = "Enquiry"
                )


            fare_markup = utils.get_fare_markup(self.user)
            fare_detail = InsuranceBookingFareDetail.objects.create(
                pax=pax_detail,
                published_fare=pax.get('fareBreakdown').get('publishedPrice', 0),
                offered_fare=pax.get('fareBreakdown').get('offeredPrice', 0),
                organization_discount=pax.get('fareBreakdown').get('discount', 0),
                dist_agent_markup=fare_markup.get('distributor_markup', 0),
                dist_agent_cashback=fare_markup.get('distributor_cashback', 0),
                fare_breakdown=json.dumps(pax.get('fareBreakdown')),
            )
        fare_data = {"fare":{"offered_fare":total_offered,"published_fare":total_published,"discount":total_discount}}
        return data | fare_data 


    def purchase(self,**kwargs):
        booking_amount = float(kwargs["data"].get("amount",0))
        from_razorpay = kwargs["data"].get("from_razorpay",False)
        booking = InsuranceBooking.objects.filter(id = kwargs["data"]["booking_id"]).first()
        print("HEre",booking.status)
        if booking.status != "Enquiry":
            print("HEre",booking.status)

            return {"status":"failure","info":"It looks like this ticket isn't eligible for Booking. Please contact our customer support team for further assistance."}

        if booking and not from_razorpay:
            payment_instance = booking.insurance_payment_details
            payment_instance.payment_type = kwargs["data"].get("payment_mode","wallet")
            payment_instance.save(update_fields = ["payment_type"])
        if not kwargs.get("wallet") and not from_razorpay:
            from common.razor_pay import razorpay_payment # imported here to solve circular import error
            razor_response = razorpay_payment(user = booking.user,amount = booking_amount,module = "insurance",
                                            booking_id = kwargs["data"]["booking_id"])
            print("razor_response",razor_response)
            payment_status = True if razor_response.get("status") else False
            booking.save(update_fields = ["status"])
            return {"payment_status":payment_status,"payment_url":razor_response.get("short_url"),
                    "error":razor_response.get("error")}
        else:
            pax_details= InsuranceBookingPaxDetail.objects.filter(booking=booking)
            vendor_uuid = booking.vendor.id
            manager = self.get_manager_from_id(vendor_uuid)
            response_data = manager.purchase(booking ,pax_details)


    def get_vendors(self,**kwargs):
        vendors = []
        associated_suppliers_list = OrganizationSupplierIntegeration.objects.filter(organization=self.user.organization,is_enabled=True).values_list('supplier_integeration', flat=True)
        supplier_integrations = SupplierIntegration.objects.filter(id__in=associated_suppliers_list,integration_type="Insurance",is_active = True)
        for x in supplier_integrations:
            if x.name == "Asego":
                data = x.data
                print("data",data)
                manager = Asego(credentials=data, uuid=x.id, mongo_client=self.mongo_client)
                vendors.append(manager)
        return vendors
    
    def get_manager_from_id(self,id):
        supplier_integration = SupplierIntegration.objects.filter(id=id).first()
        if supplier_integration.name == "Asego":
            manager = Asego(credentials=supplier_integration.data, uuid=supplier_integration.id, mongo_client=self.mongo_client)
            return manager

    def endorse_ticket(self,pax_id):
        pax = InsuranceBookingPaxDetail.objects.filter(id = pax_id).first()
        InsuranceBooking = pax.booking
        if pax.status == "Confirmed":
            vendor_uuiid = pax.booking.vendor.id
            manager = self.get_manager_from_id(vendor_uuiid)
            endorse_data = manager.endorse_ticket(pax)    
            return endorse_data
        else:
            return {"status":"failure","info":"It looks like this ticket isn't eligible for cancellation. Please contact our customer support team for further assistance."}


    def cancel_ticket(self,pax_id,remarks):
        pax = InsuranceBookingPaxDetail.objects.filter(id = pax_id).first()
        InsuranceBooking = pax.booking
        if pax.status == "Confirmed":
            vendor_uuiid = pax.booking.vendor.id
            manager = self.get_manager_from_id(vendor_uuiid)
            cancel_data = manager.cancel_ticket(pax,remarks)    
            return cancel_data
        else:
            return {"status":"failure","info":"It looks like this ticket isn't eligible for cancellation. Please contact our customer support team for further assistance."}
       


def generate_booking_display_id():
    now = timezone.now()
    today = now.date()
    with transaction.atomic():
        counter, created = DailyCounter.objects.select_for_update().get_or_create(date=today,module ='insurance')
        counter.count += 1
        counter.save()
        booking_number = counter.count
    formatted_booking_number = f"{booking_number:04d}"
    day_month = now.strftime("%d%m")  # DDMM format
    year_suffix = now.strftime("%y")  # Last two digits of the year
    return f"INS{year_suffix}-{day_month}-{formatted_booking_number}"