
from .asego_sync import SyncData
from.asego_api import book,cancel,endorse
from vendors.insurance.models import InsuranceAsegoCategory,InsuranceAsegoPlan,InsuranceAsegoPlanRider,InsuranceAsegoPremiumChart,InsuranceAsegoRiderMaster,InsuranceAsegoVisitingCountry,InsuranceBooking,InsuranceBookingFareDetail,InsuranceBookingPaxDetail,InsuranceBookingSearchDetail
from datetime import datetime, date
from vendors.insurance.utils import fare_calculation
import json,time
from typing import cast
from django.db.models import QuerySet

class Manager():
    def __init__(self, **kwargs):
        self.credentials = kwargs['credentials']
        self.mongo_client = kwargs['mongo_client']
        self.vendor_uuid = kwargs['uuid']
        self.vendor_id = "VEN-"+str(kwargs['uuid'])
        self.base_url = self.credentials.get("base_url")

    def name(self):
        return "Asego"
    
    def get_vendor_id(self):
        return self.vendor_id
    
    def data_sync(self,sync_info):
        print(17,sync_info)
        sync = SyncData(sync_info)
        sync.sync_vendor_data()
        print(22)
    def get_travel_categories(self):
        categories = InsuranceAsegoCategory.objects.all()
        return_data =  {"status":"success","data":[{"id":str(z.id)+"_$_"+str(self.vendor_uuid),"name":z.description} for z in categories]}
        print("return_data",return_data)
        return return_data
    
    def get_plans(self,category_id):
        plans = InsuranceAsegoPlan.objects.filter(category=category_id)
        for x in plans:
            print(x.__dict__)
        return_data =  {"status":"success","data":[{"id":str(z.id)+"_$_"+str(self.vendor_uuid),"name":z.name} for z in plans]}
        print("return_data",return_data)
        return return_data
    
    def get_plan_addons(self,plan_id):

        plan_riders = InsuranceAsegoPlanRider.objects.filter(plan_id=plan_id).select_related('rider')
        riders_data = []
        
        for plan_rider in plan_riders:
            rider = plan_rider.rider  # The associated InsuranceAsegoRiderMaster object
            data = {
                "id":str(rider.id)+"_$_"+str(self.vendor_uuid),
                "name": rider.name,
                "amount": rider.amount,
                "restricted_amount": rider.restricted_amount,
                "deductibles": rider.deductibles,
                "deductible_text": rider.deductible_text,
                "currency": rider.currency,
                "trawell_assist_charges_percent": float(plan_rider.trawell_assist_charges_percent)
            }
            riders_data.append(data)

        return_data =  {"status":"success","data":riders_data}
        print("return_data",return_data)
        return return_data
    
    def get_modified_data(self,data,fare_detatils):
        plan_id = data.get('plan_id')
        duration = data.get('travel_details').get('duration')
        plan_uuid,vendor_uuid = plan_id.split('_$_')
        plan = InsuranceAsegoPlan.objects.filter(id=plan_uuid).first()
        all_addons = InsuranceAsegoPlanRider.objects.filter(plan = plan)  # Corrected: use .all() instead of .filter.all()
        pax_details = data['pax_details']
        tax =fare_detatils['tax']['tax']
        for pax in pax_details:
            # Ensure you have a list to extend; you may provide a default empty list
            addon_list = pax.get('addons', [])
            addon_list = [x.split('_')[0] for x in addon_list]
            print("addon_list",addon_list)
            print("all_addons",all_addons)
            pax_addons =  all_addons.filter(rider__in=addon_list)
            percentage = 0
            print("pax_addons",pax_addons)
            pax['addons'] = [{"ridercode": str(z_addon.rider.rider_code),
                    "percent": float(z_addon.trawell_assist_charges_percent),"name":z_addon.rider.name} for z_addon in pax_addons]
            percentage =sum(z.get('percent') for z in pax['addons']) 
            age = calculate_age(pax.get('dob'))

            premium_record = InsuranceAsegoPremiumChart.objects.filter(
                    plan=plan,
                    day_limit__gte=duration,
                    age_limit__gte=age
                ).order_by('premium').first()
           
            print("tax",tax)
            totalcharges = round(float(premium_record.premium)*float(1+percentage/100),2)
            pax['fare'] = {"basecharges": round(float(premium_record.premium),2), #Premium chart 100
            "totalbasecharges":  round(float(premium_record.premium)-float(premium_record.premium)*tax/100,2), #base charge - service tax 
            "servicetax":  round(float(premium_record.premium)*tax/100,2),# 18% base charge
            "totalcharges":  totalcharges, #sameas base 103
                            }
            modified_price= fare_calculation(fare_detatils,totalcharges,totalcharges)
            pax['fareBreakdown']={"supplier_published_fare":totalcharges,"supplier_offered_fare":totalcharges,"offeredPrice":modified_price.get('published_fare'),"publishedPrice":modified_price.get('published_fare'),"discount":modified_price.get('discount')} 
           
            
        data['misc'] = {"categorycode":str(plan.category.category_code),"plancode":str(plan.plan_code),"plan":plan.name,"category":plan.category.description}
        # Using a list comprehension with the __in lookup to filter by addon IDs
     
        print("data",data)
        return {"data":data,"status":"success"}

    def purchase(self,booking,pax_details):

        print("booking",booking.__dict__)
        pax_details = cast(QuerySet[InsuranceBookingPaxDetail], pax_details)
        booking = cast(InsuranceBooking, booking)
        pax_list = []
        print("credentials",self.credentials)
        booking.status = "Ticketing-Initiated"
        booking.save(update_fields=["status"]) 

        def calculate_age(birth_date):
            today = date.today()
            # Calculate age by subtracting birth year from current year
            age = today.year - birth_date.year
            # Subtract one if today's month and day is before the birth month and day
            if (today.month, today.day) < (birth_date.month, birth_date.day):
                age -= 1
            return age

        status = True
        for idx,pax in enumerate(pax_details):
            print("pax_details",pax.__dict__)
            pax.status = "Ticketing-Initiated"
            pax.save(update_fields=["status"])
            parsed_datetime = datetime.strptime(pax.dob, "%Y-%m-%dT%H:%M:%S.%fZ")
            formatted_date = parsed_datetime.strftime("%Y-%m-%d")
            purchase_data = {"policy": 
                                {
                                    "identity": {
                                        "sign": self.credentials.get('sign'),
                                        "branchsign":self.credentials.get('branch_sign'),
                                        "username": self.credentials.get('user_name'),
                                        "reference": "B2BTRAVEL-"+str(pax.id.int)
                                    },
                                    "plan": {
                                        "categorycode": str(pax.misc.get('plan').get("categorycode")),
                                        "plancode": str(pax.misc.get('plan').get("plancode")),
                                        "basecharges": pax.misc.get('fare').get("basecharges"),
                                        "riders": {"ridercode": 
                                                   [{"#text": x.get('ridercode'),"@percent": x.get('percent')} for x in (pax.addons if pax.addons else [])]
                                        },
                                        "totalbasecharges": pax.misc.get('fare').get("totalbasecharges"),
                                        "servicetax": pax.misc.get('fare').get("servicetax"),
                                        "totalcharges": pax.misc.get('fare').get("totalcharges"),
                                        },
                                    "traveldetails": {
                                        "departuredate": booking.search_detail.commensing_date,
                                        "days": booking.search_detail.duration,
                                        "arrivaldate": booking.search_detail.end_date
                                    },
                                    "passengerreference": "reference1",  #not mandatory but pass uuid
                                    "insured": {
                                        "passport": pax.passport,
                                        "contactdetails": {
                                            "address1": pax.address1,
                                            "address2": pax.address2,
                                            "city": pax.city,
                                            "district": pax.district,
                                            "state": pax.state.lower(),
                                            "pincode": pax.pincode,
                                            "country":  pax.country.country_name.lower(),
                                            "phoneno": pax.phone_number,
                                            "mobileno": pax.phone_number,
                                            "emailaddress": pax.email
                                        },
                                        "name": pax.first_name+" "+pax.last_name,
                                        "dateofbirth": formatted_date,
                                        "age": calculate_age(parsed_datetime.date()),
                                        # "trawelltagnumber":int(time.time()),
                                        "nominee": pax.nominee_name,
                                        "relation": pax.relation,
                                        "pastillness": pax.past_illness     
                                        },
                                    "otherdetails":{"policycomment":"BTA"}
                                    }
                                }
                            
            response = book(self.base_url,self.credentials,purchase_data,booking.id)
            print("response",response)
            if response.get("data",{}).get("status") =="Ok":
                pax.policy = response.get("data",{}).get("policy")
                pax.document = response.get("data",{}).get("document")
                pax.reference = response.get("data",{}).get("reference")
                pax.claimcode = response.get("data",{}).get("claimcode")
                pax.status = "Confirmed"
                pax.save(update_fields = ["policy","document","reference","claimcode","status"])
            else:
                pax.status = "Ticketing-Failed"
                pax.save(update_fields=["status"])
                status = False
        booking.status = "Confirmed" if status else "Ticketing-Failed"
        booking.save(update_fields=["status"]) 
        
    def endorse_ticket(self,pax):
        pax = cast(InsuranceBookingPaxDetail, pax)
        print("pax",pax.__dict__)
        endorse_data = {
                        "policy": {
                            "identity": {
                                "sign": str(self.credentials.get('sign')),
                                "branchsign":str(self.credentials.get('branch_sign')),
                                "username": str(self.credentials.get('user_name')),
                                "policynumber": str(pax.policy)
                            }
                        }
                    }

        endorse_ticket = endorse(self.base_url,self.credentials,endorse_data,pax.booking.id)

        return_data =  {"status":"success","data":endorse_ticket}
        print("return_data",return_data)
        return return_data
    
    def cancel_ticket(self,pax,remarks):
        pax = cast(InsuranceBookingPaxDetail, pax)
        print("pax",pax.__dict__)
        cancel_data = {
                "Certificate": {
                    "identity": {
                        "sign": str(self.credentials.get('sign')),
                        "branchsign":str(self.credentials.get('branch_sign')),
                        "username": str(self.credentials.get('user_name')),
                        "certificatenumber": "SX"+str(pax.policy)
                    }
                }
            }

        cancel_ticket = cancel(self.base_url,self.credentials,cancel_data,pax.booking.id)

        return_data =  {"status":"success","data":cancel_ticket}
        print("return_data",return_data)
        return return_data

def calculate_age(dob_str):
    # Convert the string to a date object
    dob = datetime.strptime(dob_str, "%d-%m-%Y").date()
    today = date.today()
    # Calculate age, subtract one if birthday hasn't occurred yet this year
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age
