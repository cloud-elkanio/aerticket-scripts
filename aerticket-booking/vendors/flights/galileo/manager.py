from vendors.flights.abstract.abstract_flight_manager import AbstractFlightManager
from vendors.flights.galileo.api  import (import_pnr_data)
                                    #     ,authentication,fare_rule,fare_quote,
                                    #   ssr,hold,release_hold,ticket,ticket_lcc,cancellation_charges,
                                    #   cancel_ticket)
from datetime import datetime,timedelta
from django.db.models import QuerySet
from vendors.flights.utils import create_uuid,set_fare_details,create_segment_keys,extract_data_recursive,dictlistconverter
from vendors.flights.finance_manager import FinanceManager
from users.models import LookupCountry,LookupAirline,LookupAirports
from common.models import FlightBookingFareDetails,FlightBookingSSRDetails,FlightBookingItineraryDetails
from vendors.flights import mongo_handler
from collections import Counter
import concurrent.futures
import re,json
import threading
import time
from typing import Optional

class Manager(AbstractFlightManager):
    def __init__(self,data,uuid):
        self.vendor_id = "VEN-"+str(uuid)
        self.base_url = data.get("base_url")
        self.credentials = data
        self.mongo_client = mongo_handler.Mongo()
        
    def name (self):
        return "Galileo"
    def get_vendor_id(self):
        return self.vendor_id
    
    def retrieve_imported_pnr(self,pnr):
        response = import_pnr_data(self.base_url,self.credentials,pnr)
        if response.get("SOAP_Envelope").get("SOAP_Body").get("SOAP_Fault"):
            info =  "Supplier Response : " + response.get("SOAP_Envelope").get("SOAP_Body").get("SOAP_Fault").get("faultstring")
            return {"status":False,"info":info}
        offline_billing_response = self.unify_pnr_response(response)
        return offline_billing_response

    def unify_pnr_response(self,response):
        airports = LookupAirports.objects.all()
        def get_passenger_type(key,pax_type_data,pax_type_map):
            pax_type_master = [ extract_data_recursive(x,["air_PassengerType","Code"],"") for x in pax_type_data if extract_data_recursive(x,["air_PassengerType","BookingTravelerRef"],"") == key]
            if len(pax_type_master)>0:
                pax_type_master = pax_type_master[0]
                return pax_type_map[pax_type_master] if pax_type_master in pax_type_map else 'adults'
            else:
                return 'adults'

        def get_passenger_ticket(key,pax_ticket_data):
            pax_ticket = [x['Number'] for x in pax_ticket_data if x.get('BookingTravelerRef','') == key]
            if len(pax_ticket) >0:
                return pax_ticket[0]
            else:
                return ""
            
        def parse_datetime_with_offset(datetime_str):
            match = re.match(r'(.*)([+-]\d{2}:\d{2})$', datetime_str)
            if not match:
                raise ValueError(f"Invalid datetime string: {datetime_str}")
            date_part = match.group(1)  
            offset = match.group(2)     

            try:
                datetime_obj = datetime.strptime(date_part, "%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                datetime_obj = datetime.strptime(date_part, "%Y-%m-%dT%H:%M:%S")
            sign = offset[0] 
            offset_hours, offset_minutes = map(int, offset[1:].split(":"))
            offset_delta = timedelta(hours=offset_hours, minutes=offset_minutes)
            if sign == '-':
                offset_delta = -offset_delta

            adjusted_datetime = datetime_obj - offset_delta

            formatted_datetime = adjusted_datetime.strftime("%Y-%m-%dT%H:%M:%S")
            return formatted_datetime

        offline_billing_response = {}
        pnr_reply = response.get('SOAP_Envelope',{}).get('SOAP_Body',{}).get('universal_UniversalRecordRetrieveRsp',None)
        pax_details = []
        pax_type_map = {'ADT':'adults','CHD':'children','INF':'infants','CNN':'children'}
        pax_datas = pnr_reply.get('universal_UniversalRecord',{}).get('common_v42_0_BookingTraveler',{})
        pax_datas = dictlistconverter(pax_datas)
        pax_type_data = pnr_reply.get('universal_UniversalRecord',{}).get('air_AirReservation',{}).get('air_AirPricingInfo',{})
        pax_type_data = dictlistconverter(pax_type_data)
        pax_ticket_data = pnr_reply.get('universal_UniversalRecord',{}).get('air_AirReservation',{}).get('air_DocumentInfo',{}).get('air_TicketInfo',{})
        pax_ticket_data = dictlistconverter(pax_ticket_data)
        for pax_data in pax_datas:
            pax_type = get_passenger_type(pax_data['Key'],pax_type_data,pax_type_map)
            firstName = pax_data.get('common_v42_0_BookingTravelerName',{}).get('First',"")
            lastName = pax_data.get('common_v42_0_BookingTravelerName',{}).get('Last',"")
            dob = ''
            ticketNumber = get_passenger_ticket(pax_data['Key'],pax_ticket_data)
            pax_details.append({"pax_type": pax_type,"firstName": firstName,"lastName": lastName,"dob": dob,"ticketNumber": ticketNumber})
        offline_billing_response['pax_details'] = pax_details
        passenger_details = dict(Counter(item["pax_type"] for item in pax_details))
        offline_billing_response['passenger_details'] = passenger_details
        flightSegments = []
        seg_datas = pnr_reply.get('universal_UniversalRecord',{}).get('air_AirReservation',{}).get('air_AirSegment',{})
        seg_datas = dictlistconverter(seg_datas)
        for seg_data in seg_datas:
            converted_response = {
                                "airlineCode": seg_data.get("Carrier",""),
                                "flightNumber": f"{seg_data.get('Carrier','')}{seg_data.get('FlightNumber','')}",
                                "equipmentType": seg_data.get('Equipment',""),
                                "stop": 0 if seg_data.get('ChangeOfPlane',"").lower() == "false" else 1,
                                "departure": {
                                    "airportCode": seg_data.get('Origin',""),
                                    "airportName": get_airport(seg_data.get('Origin',""),airports).name,
                                    "city":get_airport_city(seg_data.get('Origin',""),airports),
                                    "country":get_airport_country(seg_data.get('Origin',""),airports),
                                    "terminal": seg_data.get('air_FlightDetails',"").get('OriginTerminal',""),
                                    # "departureDatetime": parse_datetime_with_offset(seg_data.get('DepartureTime',"")),
                                    "departureDatetime": seg_data.get('DepartureTime',"").split(".")[0]
                                },
                                "cabinClass":seg_data.get('ClassOfService',""),
                                "arrival": {
                                    "airportCode": seg_data.get('Destination',""),
                                    "airportName": get_airport(seg_data.get('Destination',""),airports).name, 
                                    "city":get_airport_city(seg_data.get('Destination',""),airports),
                                    "country":get_airport_country(seg_data.get('Origin',""),airports),
                                    "terminal": seg_data.get('air_FlightDetails',"").get('DestinationTerminal',""),
                                    # "arrivalDatetime": parse_datetime_with_offset(seg_data.get('ArrivalTime',"")),
                                    "arrivalDatetime": seg_data.get('ArrivalTime',"").split(".")[0]
                                },
                                "isRefundable":True,
                                "durationInMinutes": int(seg_data.get('air_FlightDetails',"").get('FlightTime',""))
                                }
            flightSegments.append(converted_response)
        offline_billing_response['flightSegments'] = flightSegments

        fareBreakdown = []
        fare_datas = pnr_reply.get('universal_UniversalRecord',{}).get('air_AirReservation',{}).get('air_AirPricingInfo',[])
        fare_datas = dictlistconverter(fare_datas)
        for fare_data in fare_datas:
            passengerType = extract_data_recursive(fare_data,["air_PassengerType","Code"],"")
            passengerType = pax_type_map[passengerType] if passengerType in pax_type_map else 'adults'
            try:
                baseFare = float(re.sub(r"[^\d.]", "", fare_data.get("ApproximateBasePrice",'')))
            except:
                baseFare = float(re.sub(r"[^\d.]", "", fare_data.get("BasePrice",'')))
            try:
                totalFare = float(re.sub(r"[^\d.]", "", fare_data.get("ApproximateTotalPrice",'')))
            except:
                totalFare = float(re.sub(r"[^\d.]", "", fare_data.get("TotalPrice",'')))
            taxes = fare_data.get('air_TaxInfo',{})
            taxes = dictlistconverter(taxes)
            YR = [x.get('Amount') for x in taxes if x.get('Category','') == 'YR']
            if len(YR)>0:
                YR = float(re.sub(r"[^\d.]", "", YR[0]))
            else:
                YR = 0
            YQ = [x.get('Amount') for x in taxes if x.get('Category','') == 'YQ']
            if len(YQ)>0:
                YQ = float(re.sub(r"[^\d.]", "", YQ[0]))
            else:
                YQ = 0
            K3 = [x.get('Amount') for x in taxes if x.get('Category','') == 'K3']
            if len(K3)>0:
                K3 = float(re.sub(r"[^\d.]", "", K3[0]))
            else:
                K3 = 0
            # tax = totalFare-baseFare-K3
            tax = float(re.sub(r"[^\d.]", "", fare_data.get("Taxes",'')))
            other_taxes = tax - K3
            fareBreakdown.append({"passengerType":passengerType,"baseFare":baseFare,"totalFare":totalFare,
                                "YR":YR,"YQ":YQ,"K3":K3,"tax":tax,"other_taxes":other_taxes})

        fareBreakdown = list({tuple(sorted(d.items())): d for d in fareBreakdown}.values())
        fareBasis = extract_data_recursive(pnr_reply,['universal_UniversalRecord','air_AirReservation','air_AirPricingInfo','air_FareInfo','FareBasis'],'')
        baggage_result = find_baggage_info(pnr_reply,['universal_UniversalRecord','air_AirReservation','air_AirPricingInfo','air_FareInfo'],None)
        fareDetails = {"baggage":{"default_baggage":baggage_result},"fareBasis":fareBasis,"fareBreakdown":fareBreakdown,"meals_ssr":0,
                    "baggage_ssr":0,"seats_ssr":0}

        offline_billing_response['fareDetails'] = fareDetails               
        offline_billing_response['booking_id'] = create_uuid("OFFLINE")
        SupplierLocatorCodes = dictlistconverter(pnr_reply.get('universal_UniversalRecord',{}).get('air_AirReservation',{}).get('common_v42_0_SupplierLocator',{}))
        airline_pnr =  [x.get("SupplierLocatorCode") for x in SupplierLocatorCodes]
        offline_billing_response['airline_pnr'] = ",".join(airline_pnr)
        offline_billing_response['gds_pnr'] = extract_data_recursive(pnr_reply,['universal_UniversalRecord','universal_ProviderReservationInfo','LocatorCode'],'')
        current_date = datetime.now()
        ticketing_date = current_date - timedelta(days=5)
        ticketing_date = ticketing_date.strftime("%Y-%m-%dT%H:%M:%S")
        start_date = current_date + timedelta(days=5)
        start_date = start_date.strftime("%Y-%m-%dT%H:%M:%S")
        offline_billing_response['ticketing_date'] = ticketing_date
        offline_billing_response['start_date'] =start_date
        return offline_billing_response

def extract_currency_and_amount(input_str):
    # Match patterns like "AED220", "AED 220", or "220"
    match = re.match(r'([A-Za-z]{3})?\s?(\d+)', input_str)
    if match:
        currency = match.group(1)  # First capture group (currency, if present)
        amount = match.group(2)    # Second capture group (amount)
        return currency, int(amount)
    else:
        raise ValueError(f"Invalid input string: {input_str}")
    
def get_airport(airport_code,airports):
    try:
        airport = airports.filter(code = airport_code).first()
        return airport
    except:
        return ""
    
def get_airport_city(airport_code,airports):
    try:
        airport = airports.filter(code = airport_code).first()
        if airport:
            city = airport.city
        else:
            city = airport_code
        return city
    except:
        return airport_code

def get_airport_country(airport_code,airports):
    try:
        airport = airports.filter(code = airport_code).first()
        if airport:
            country = airport.country.country_name
        else:
            country = "N/A"
        return country
    except:
        return "N/A"
    
def find_baggage_info(data, keys, default_response):
    try:
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
        if isinstance(data, list) and data:
            baggage_dict = {}
            for bagg_data in data:
                origin = bagg_data["Origin"]
                destination = bagg_data["Destination"]
                baggage_value = bagg_data.get("air_BaggageAllowance",{}).get("air_MaxWeight",{}).get("Value","N/A")
                baggage_unit = bagg_data.get("air_BaggageAllowance",{}).get("air_MaxWeight",{}).get("Unit","")
                chheckin_bag_info = {"checkInBag": baggage_value + " " + baggage_unit}

                baggage_dict [origin+"_" + destination] = chheckin_bag_info
            return baggage_dict
        else:
            return {}
    except:
        return {}