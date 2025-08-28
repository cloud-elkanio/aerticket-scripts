from datetime import datetime, timedelta, timezone
import uuid
import time
import os
import jwt
import requests
import json
from uuid import UUID
from users.models import UserDetails,OrganizationFareAdjustment,CountryTax,\
    DistributorAgentFareAdjustment, LookupAirports
from common.models import Booking,FareManagement
from django.db.models import Count, Q,F, ExpressionWrapper, fields
from collections import defaultdict
from api.settings import SECRET_KEY
from itertools import groupby
from dotenv import load_dotenv
load_dotenv() 

def create_uuid(suffix=""):
    if suffix == "":
        return str(uuid.uuid4())
    else:
        return suffix+"-"+str(uuid.uuid4())
from users.models import LookupAirports
from common.utils import *
        
def create_segment_keys(journey_data):
    journey_details = journey_data.get("journey_details", [])
    segment_keys = []

    for detail in journey_details:
        source_city = detail.get("source_city")
        destination_city = detail.get("destination_city")
        travel_date = detail.get("travel_date")
        
        # Convert the travel_date to the MMDD format
        travel_date_obj = datetime.strptime(travel_date, "%d-%m-%Y")
        formatted_date = travel_date_obj.strftime("%d%m")
        
        # Create the segment key
        segment_key = f"{source_city}_{destination_city}_{formatted_date}"
        segment_keys.append(segment_key)

    if journey_data.get("journey_type") == "Round Trip" and journey_data.get("flight_type") == "INT":
        segment_keys = ["_R_".join(segment_keys)]
    return segment_keys

def set_fare_details(fare_details):
    default_fare = {
        "markup": 0,
        "cashback": 0,
        "parting_percentage": 100,
        "distributor_markup": 0,
        "distributor_cashback": 0,
        "distributor_parting_percentage":100
    }
    default_tax = {
        "tax": 18,
        "tds": 2
    }   
    fare_adjustment = fare_details.get("fare", {})
    for key, value in default_fare.items():
        fare_adjustment.setdefault(key, value)
    tax_condition = fare_details.get("tax", {})
    for key, value in default_tax.items():
        tax_condition.setdefault(key, value)
    return fare_adjustment,tax_condition

def get_fare_markup(user:UserDetails):
    fare_obj = OrganizationFareAdjustment.objects.filter(organization = user.organization,module = 'flight').first()
    fare = {
            "markup":fare_obj.markup if fare_obj else 0,
            "cashback":fare_obj.cashback if fare_obj else 0,
            "parting_percentage":fare_obj.parting_percentage if fare_obj else 100,
            "cancellation_charges":fare_obj.cancellation_charges if fare_obj else 0,
            }
    if user.role.name == "distributor_agent":
        dafa_obj = DistributorAgentFareAdjustment.objects.filter(user = user,module = 'flight').first()
        dafa = {"distributor_markup":dafa_obj.markup if dafa_obj else 0 ,
            "distributor_cashback":dafa_obj.cashback if dafa_obj else 0,
            "distributor_parting_percentage":dafa_obj.parting_percentage if dafa_obj else 100,
            "distributor_cancellation_charges":dafa_obj.cancellation_charges if dafa_obj else 0}
    else:
        dafa = {"distributor_markup":0,
            "distributor_cashback":0,
            "distributor_parting_percentage":100,
            "distributor_cancellation_charges" :0}
    fare = fare | dafa
    tax_obj = CountryTax.objects.filter(country_id = user.organization.organization_country).first()
    tax = {"tax":tax_obj.tax if tax_obj else 18,"tds":tax_obj.tds if tax_obj else 2}
    return  {"fare":fare,"tax":tax,"user":user}

def extract_data_recursive(data, keys, default_response):
    for key in keys:
        while isinstance(data, list):
            if data:
                data = data[0]
            else:
                return default_response
        if isinstance(data, dict):
            if key in data:
                data = data[key]
            else:
                return default_response
        else:
            return default_response
    while isinstance(data, list) and data:
        data = data[0]
    return data if data is not None else default_response

def dictlistconverter(dictorlist):
    data = dictorlist if isinstance(dictorlist,list) else [dictorlist]
    return data

def get_flight_type(data,user):
    user_country = user.organization.organization_country.lookup
    city_codes = {journey.get("source_city") for journey in data.get("journey_details", [])} | \
                    {journey.get("destination_city") for journey in data.get("journey_details", [])}
    airports = LookupAirports.objects.filter(code__in=city_codes).only("code", "country")
    airport_country_map = {airport.code: airport.country for airport in airports}
    flight_type = all(
            airport_country_map.get(journey.get("source_city")) == user_country and
            airport_country_map.get(journey.get("destination_city")) == user_country
            for journey in data.get("journey_details", [])
        )
    return "DOM" if flight_type else "INT"

    
def check_duplicate_booking(**kwargs):
    try:
        journey_details = kwargs["journey"]
        pax_details = kwargs["pax"]
        journey_pairs = [(journey["source_city"], journey["destination_city"], journey["travel_date"]) 
                         for journey in journey_details]
        pax_name_pairs = [(pax["firstName"].strip().lower(), pax["lastName"].strip().lower()) for pax in pax_details]
        journey_query = Q()
        for departure, destination, date in journey_pairs:
            journey_query |= Q(
                flightbookingjourneydetails_set__source=departure,
                flightbookingjourneydetails_set__destination=destination,
                flightbookingjourneydetails_set__date=date
            )
        pax_query = Q()
        for first_name, last_name in pax_name_pairs:
            pax_query |= Q(flightbookingpaxdetails_set__first_name__iexact = first_name, 
                           flightbookingpaxdetails_set__last_name__iexact = last_name)

        booking = Booking.objects.annotate(
            valid_journeys = Count('flightbookingjourneydetails_set', filter = journey_query, distinct = True),
            valid_pax = Count('flightbookingpaxdetails_set', filter = pax_query, distinct = True),
            epoch_diff = ExpressionWrapper(int(time.time()) - F('created_at'), output_field = fields.IntegerField()),
            total_pax = Count('flightbookingpaxdetails_set', distinct=True),
            total_journey = Count('flightbookingjourneydetails_set', distinct=True),
        ).filter(
            valid_journeys = len(journey_pairs),
            valid_pax = len(pax_name_pairs),
            epoch_diff__lt = 3600,
            user = kwargs["user"],
            total_pax = len(pax_details),
            total_journey = len(journey_details)
        ).exclude(
           Q(status__in = ["Enquiry", "Hold-Unavailable","Hold-Released","Ticket-Released",
                           "Failed-Rejected","Hold-Failed"]) &
             ~Q(session_id = kwargs["session_id"])
        ).distinct().first()
        return booking if booking else False
    except:
        return False
    
def unique_fares(result):
    fare_mappings = list(FareManagement.objects.values())
    try:
        grouped_data = defaultdict(list)
        for item in result:
            grouped_data[item["offeredFare"]].append(item)
        grouped_data = dict(grouped_data)
        for vendor_fare in result:
            mapped_fare = []
            vendor_fare["priority"] = 1
            vendor_fare["is_mapped"] = False
            for fare_map in fare_mappings:
                if vendor_fare.get("fareType","").upper() == fare_map["supplier_fare_name"].upper() and\
                    str(fare_map["supplier_id_id"]) == vendor_fare["vendor_id"]:
                    mapped_fare = fare_map
                if mapped_fare:
                    vendor_fare["fareType"] = mapped_fare["brand_name"]
                    vendor_fare["priority"] = mapped_fare["priority"]
                    vendor_fare["is_mapped"] = True
                    break
        result = list({
                (d["vendor_id"], d["fareType"]): min(
                    [x for x in result if x["vendor_id"] == d["vendor_id"] and x["fareType"] == d["fareType"]],
                    key = lambda x: x["offeredFare"]
                )
                for d in result
            }.values())
        result.sort(key = lambda x: (x['fareType'], x['priority']))
        filtered_data = []
        for brand, items in groupby(result, key=lambda x: x['fareType']):
            items = list(items)
            non_mapped = [item for item in items if not item["is_mapped"]]
            mapped = [item for item in items if item["is_mapped"]]
            if mapped:
                unique_vendor_ids = {item['vendor_id'] for item in mapped}
                # print("unique_vendor_ids ",unique_vendor_ids)
                if len(unique_vendor_ids) == 1: # taking all fares from this vendor
                    filtered_data.extend(mapped)
                else:
                    if len(set(x['offeredFare'] for x in mapped)) == 1: #same offeredFare for all vendors
                        filtered_data.append(min(mapped, key=lambda x: x['priority'])) # fare with most priority
                    else:
                        filtered_data.append(min(mapped, key =  lambda x: x['offeredFare']))
            filtered_data.extend(non_mapped)
        # print("final" ,len(filtered_data))
        filtered_data = sorted(filtered_data, key = lambda x: x["offeredFare"])
        return filtered_data
    except:
        return result

def invoke_email(kwargs):
    try:
        invoke_url = os.getenv('INVOKE_EMAIL_URL',"")
        payload = {"user_id":kwargs["user"],"sec":kwargs["sec"],"jti": str(uuid.uuid4()),"token_type":"access"}
        payload["exp"] = datetime.now(timezone.utc) + timedelta(seconds = kwargs.get("sec"))
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        headers = {
            "Authorization": f"Bearer {token}",  
            "Content-Type": "application/json"  
        }
        data = {"event": "Ticket_Confirmation","booking_id": kwargs["booking_id"], "is_queue": True}
        mail_invoke = requests.post(invoke_url,data = json.dumps(data),headers = headers)
    except:
        pass