
import json
import re
from datetime import datetime
import pytz
from users.models import LookupAirports
from common.models import FlightBookingSSRDetails

def get_updated_fare_details(**kwargs):
    response = {}
    fare_quote_response = kwargs["fare_quote_response"]

    if kwargs["type"] != "ROUND_INT":
        response["stt_fare_id"] = fare_quote_response["AirRepriceResponses"][0]["Flight"]["Fares"][0]["Fare_Id"]
        response["currency"] = fare_quote_response["AirRepriceResponses"][0]["Flight"]["Fares"][0]["FareDetails"][0]["Currency_Code"]
        response["fare_breakdown"] = fare_quote_response["AirRepriceResponses"][0]["Flight"]["Fares"][0]
        response["flight_legs"] = fare_quote_response["AirRepriceResponses"][0]["Flight"]["Fares"][0]
        response["unify_seg_quote"] = fare_quote_response["AirRepriceResponses"][0]["Flight"]["Segments"]
        response["calculate_fares"] = fare_quote_response["AirRepriceResponses"][0]["Flight"]["Fares"][0]["FareDetails"]
        response["latest_flight_key"] = fare_quote_response["AirRepriceResponses"][0]["Flight"]["Flight_Key"]
        response["reFundable"] = fare_quote_response["AirRepriceResponses"][0]["Flight"]["Fares"][0]["Refundable"]
        response["is_ffn"] = fare_quote_response["AirRepriceResponses"][0].get("Frequent_Flyer_Accepted",False)
    return response

product_class_mapping = {
                        "LT":"Xpress Lite","OF":"Xpress Flex","VV":"Xpress Biz","FS":"Corporate Flex",
                        "EC":"Xpress Value","SM":"Corporate Value","EP":"Sales Fare","BT":"Promo Fare",
                        "FM":"Friends and Family","DF":"Defence Fare",  
                        "NT":"Return Fare"
                        }

def get_uiName(fare_detail):
    try:
        fare_details = fare_detail.get("FareDetails",[])
        if len(fare_details)>0:
            name = fare_details[-1].get("FareClasses")[-1].get("Class_Desc")
            if len(name) <= 2:
                name = "BTA Fare"
        else:
            name = fare_detail.get("ProductClass","BTA Fare")
    except:
        name = fare_detail.get("ProductClass","BTA Fare")
    return name

def get_selected_ssr_data(filtered_ssr,ssr_response_selected,Pax_Id):
    try:
        baggage_meal_seat_keys = []
        meal_baggage_data = ssr_response_selected["ssr"]["SSRFlightDetails"][0]["SSRDetails"]
        seat_data = ssr_response_selected["seat_ssr"]["AirSeatMaps"][0]["Seat_Segments"]
        result = []
        if filtered_ssr[0].get("is_baggage"):
            baggage_ssr_codes = json.loads(filtered_ssr[0]["baggage_ssr"])
            for index, (_, val) in enumerate(baggage_ssr_codes.items()):
                if val:
                        baggage_meal_seat_keys.append({"segment":index,"code":val["Code"],"type":"baggage"})
        if filtered_ssr[0].get("is_meals"):
            meal_ssr_codes = json.loads(filtered_ssr[0]["meals_ssr"])
            for index, (_, val) in enumerate(meal_ssr_codes.items()):
                if val:
                        baggage_meal_seat_keys.append({"segment":index,"code":val["Code"],"type":"meal"})
        if filtered_ssr[0].get("is_seats"):
            seat_ssr_codes = json.loads(filtered_ssr[0]["seats_ssr"])
            for index, (_, val) in enumerate(seat_ssr_codes.items()):
                if val:
                        baggage_meal_seat_keys.append({"segment":index,"code":val["Code"],"type":"seat"})
        for ssr_codes in baggage_meal_seat_keys:
            if ssr_codes["type"] != "seat":
                for ssr_data in meal_baggage_data:
                    if ssr_data.get("SSR_Code") == ssr_codes["code"] and ssr_data.get("Segment_Id") == ssr_codes["segment"]:
                        result.append({"Pax_Id":Pax_Id,"SSR_Key":ssr_data["SSR_Key"]})
            else:
                seat_data_segment = seat_data[ssr_codes["segment"]]
                for ssr_seat_data in seat_data_segment["Seat_Row"]:
                    for ssr_seat_row in ssr_seat_data["Seat_Details"]:
                         if ssr_seat_row.get("SSR_Code") == ssr_codes["code"]:
                            result.append({"Pax_Id":Pax_Id,"SSR_Key":ssr_seat_row["SSR_Key"]})
        return result
    except:
         return []
    
def get_airport(airport_code,airports):
    try:
        airport = airports.filter(code = airport_code).first()
        if airport:
            return airport.name
        else:
            return ""
    except:
        return ""

def get_airport_country(airport_code,airports):
    try:
        airport = airports.filter(code = airport_code).first()
        if airport:
            country = airport.country.country_name
        else:
            country = ""
        return country
    except:
        return ""
    
def get_cancellation_charges(**kwargs):
    try:
        pax_info = kwargs["selected_pax_names"]
        selected_pax_names = list(pax_info.keys())
        air_reprint_data = kwargs["booking_details"]["data"]
        per_pax_additional_charge = kwargs["per_pax_additional_charge"]
        per_pax_cancellation_charge = kwargs["per_pax_cancellation_charge"]
        customer_cancellation_charge = per_pax_additional_charge + per_pax_cancellation_charge
        departure_flight_data = air_reprint_data["AirPNRDetails"][0]["Flights"][0]["Segments"][0]
        hours = calculate_time_diff_in_hours_days(departure_flight_data)
        cancellation_amount = 0
        flight_id = air_reprint_data["AirPNRDetails"][0]["Flights"][0]["Flight_Id"]
        segments = len(air_reprint_data["AirPNRDetails"][0]["Flights"][0]["Segments"])
        misc_updated = {"flight_id":flight_id,"cancellation_segments":segments,"cancellation_passenger_ids":[]}
        if hours:
            for pax_detail in air_reprint_data["AirPNRDetails"][0]["PAXTicketDetails"]:
                pax_name = pax_detail["Title"].lower() + pax_detail["First_Name"].lower() + pax_detail["Last_Name"].lower()
                if pax_name in selected_pax_names:
                    misc_updated["cancellation_passenger_ids"].append(str(pax_detail["Pax_Id"]))
                    cancellation_charge = False
                    cancellation_conditions = pax_detail["Fares"][0]["FareDetails"][0]["CancellationCharges"]
                    total_amount = pax_detail["Fares"][0]["FareDetails"][0]["Total_Amount"]
                    for cancellation_condition in cancellation_conditions:
                        if cancellation_condition["DurationTypeFrom"] == 1:
                            cancellation_condition["DurationFrom"] = cancellation_condition["DurationFrom"]*24
                        if cancellation_condition["DurationTypeTo"] == 1:
                            cancellation_condition["DurationTo"] = cancellation_condition["DurationTo"]*24
                        if hours >= cancellation_condition["DurationFrom"] and hours <= cancellation_condition["DurationTo"]:
                            cancellation_charge = True
                            if cancellation_condition["ValueType"] == 0:
                                supplier_cancellation_charge = float(cancellation_condition["Value"])
                                cancellation_amount +=  supplier_cancellation_charge + customer_cancellation_charge
                            else:
                                supplier_cancellation_charge = total_amount * float(cancellation_condition["Value"]) /100
                                cancellation_amount +=  supplier_cancellation_charge + customer_cancellation_charge
                        else:
                            continue
                        if cancellation_charge:
                            pax_ssr = FlightBookingSSRDetails.objects.filter(itinerary_id = kwargs["itinerary"].id,pax_id = pax_info[pax_name]).first()
                            cancellation_fee_per_pax = {"supplier_cancellation_charge":supplier_cancellation_charge,
                                                        "customer_cancellation_charge":customer_cancellation_charge + supplier_cancellation_charge}
                            pax_ssr.cancellation_fee = cancellation_fee_per_pax
                            pax_ssr.save(update_fields = ["cancellation_fee"])
                            break
            return cancellation_charge,cancellation_amount,misc_updated
        else:
            return False,False,misc_updated
    except:
        return False,False,False

def calculate_time_diff_in_hours_days(departure_flight_data):
    try:
        airport_matches = re.findall(r"\((.*?)\)", departure_flight_data["Origin"])
        if airport_matches:
            airport_code = airport_matches[0].upper().strip()
            airport_object = LookupAirports.objects.filter(code = airport_code).first()
            if airport_object:
                airport_timezone = airport_object.timezone
                departure_timezone = pytz.timezone(airport_timezone)
                gmt_tz = pytz.timezone("GMT")
                departure_time = datetime.strptime(departure_flight_data["Departure_DateTime"], "%m/%d/%Y %H:%M:%S")
                departure_time = departure_timezone.localize(departure_time)
                departure_time_gmt = departure_time.astimezone(gmt_tz)
                local_time = datetime.now()
                local_time_gmt = local_time.astimezone(gmt_tz) 
                time_diff = departure_time_gmt - local_time_gmt
                hours_diff = time_diff.total_seconds() / 3600
                return hours_diff
            else:
                return False
        else:
            return False
    except:
        return False
    
def dob_validations(**kwargs):
    fare_quote_response = kwargs["fare_quote_response"]
    pax_DOB = {"is_adultDOB":False,"is_childDOB":True,"is_infantDOB":True}
    if "Required_PAX_Details" in fare_quote_response["AirRepriceResponses"][0]:
        pax_conditions = fare_quote_response["AirRepriceResponses"][0]["Required_PAX_Details"]
        for pax in pax_conditions:
            if pax.get("Pax_type") == 0:
                pax_DOB["is_adultDOB"] = pax.get("DOB",True)
            elif pax.get("Pax_type") == 1:
                pax_DOB["is_childDOB"] = pax.get("DOB",True)
            elif pax.get("Pax_type") == 2:
                pax_DOB["is_infantDOB"] = pax.get("DOB",True)
    return pax_DOB

pax_type_mapping = {"adults": 0,"child": 1,"infant": 2}

gender_mapping = {"Male": 0,"Female": 1}