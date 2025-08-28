from vendors.flights.abstract.abstract_flight_manager import AbstractFlightManager
from vendors.flights.stt_travelshop.api  import (flight_search,fare_rule,fare_quote,
                                        temp_ticket_book,book_ticket_flow,
                                        release_hold,cancel_ticket,get_ssr_data,get_ssr_seat_data,
                                        air_reprint,get_current_ticket_status)
from datetime import datetime,timedelta
from vendors.flights.utils import create_uuid,set_fare_details,create_segment_keys,invoke_email
from vendors.flights.finance_manager import FinanceManager
from common.models import LookupEasyLinkSupplier,FlightBookingUnifiedDetails
from users.models import LookupAirports
import concurrent.futures
import os
from datetime import datetime
import copy
import re
import traceback as tb
import time
import json
from vendors.flights.stt_travelshop import assistant_manager as AM
from dotenv import load_dotenv
load_dotenv() 

class Manager(AbstractFlightManager):
    def __init__(self,data,uuid,mongo_client):
        self.vendor_id = "VEN-"+str(uuid)
        self.credentials = data
        self.mongo_client = mongo_client

    def name (self):
        return "STT-Travelshop"
    
    def get_vendor_journey_types(self,kwargs):
        if kwargs.get("journey_type","").upper() == "ROUND TRIP" and kwargs.get("flight_type","").upper() == "INT":
            return False
        else:
            return True
        
    def get_vendor_id(self):
        return self.vendor_id
    
    def get_cabin_class(self,cabin_class):
        cabin_map = {"Economy":0,"Premium Economy":3,"Business Class":1,"First Class":2}
        return cabin_map.get(cabin_class,0)

    def get_journey_type(self,journey_type):
        journey_type_map = {"One Way":1,"Round Trip":2,"Multi Stop":3}
        return journey_type_map.get(journey_type,1)
    
    def search_data_modify(self,search_data):
        modified_journey_detail = {"journey_details":[]}
        modified_journey_detail["passenger_details"] = {"adult_Count": str(search_data["passenger_details"]["adults"]), 
                                                        "child_Count": str(search_data["passenger_details"]["children"]), 
                                                        "infant_Count": str(search_data["passenger_details"]["infants"])}
        modified_journey_detail["travel_type"] = 0 if search_data["flight_type"] == "DOM" else 1
        modified_journey_detail["booking_type"] = 1 if (search_data["journey_type"] == "Round Trip" and  \
                                                       search_data["flight_type"] == "INT") else 0  
        modified_journey_detail["cabin_class"] = search_data["cabin_class"]
        for journy_info in search_data["journey_details"]:
            journe_info_modified = copy.deepcopy(journy_info)
            date_object = datetime.strptime(journy_info["travel_date"], '%d-%m-%Y')
            journe_info_modified["travel_date"] = date_object.strftime('%m/%d/%Y')
            modified_journey_detail["journey_details"].append(journe_info_modified)
        return modified_journey_detail
    
    def refund_status(self,**kwargs):
        rT_list = []
        if "ADULT" in kwargs["fare_data"]:
            if kwargs["fare_data"]["ADULT"].get("rT"):
                rT_list.append(kwargs["fare_data"]["ADULT"].get("rT"))
        if "CHILD" in kwargs["fare_data"]:
            if kwargs["fare_data"]["CHILD"].get("rT"):
                rT_list.append(kwargs["fare_data"]["CHILD"].get("rT"))
        if "INFANT" in kwargs["fare_data"]:
            if kwargs["fare_data"]["INFANT"].get("rT"):
                rT_list.append(kwargs["fare_data"]["INFANT"].get("rT"))  
        elif all(element == 1 for element in rT_list):
            return  True 
        else:
            return  False        
    
    def search_flights(self,journey_details):
        session_id = journey_details.get("session_id")
        modified_journey_details = self.search_data_modify(journey_details)
        journey_type = journey_details.get("journey_type")
        flight_type = journey_details.get("flight_type")
        segment_details = modified_journey_details.get("journey_details")
        segment_keys = create_segment_keys(journey_details)
        modified_journey_details["cabin_class"] = self.get_cabin_class(modified_journey_details.get("cabin_class",""))
        book_filters = self.booking_filters({"journey_type":journey_type,"flight_type":flight_type,
                                             "supplier_id":str(self.vendor_id),"fare_type":journey_details.get("fare_type")}) 
        def process_segment(seg, index,session_id):
            """Function to process each segment in a thread."""
            flight_search_response = flight_search(credentials = self.credentials,search_data = modified_journey_details,
                                                   segment_details = [seg], session_id= session_id,book_filters = book_filters
            )
            flight_search_response = self.add_uuid_to_segments(
                flight_search_response, flight_type, journey_type
            )
            return index, flight_search_response
        
        if (journey_type =="Round Trip" and flight_type ==  "DOM") or journey_details["journey_type"] == "Multi City":
            def run_in_threads(segments, segment_keys):
                final = {}
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = {
                        executor.submit(process_segment, seg, index, session_id): index
                        for index, seg in enumerate(segments)
                    }
                    for future in concurrent.futures.as_completed(futures):
                        index, response = future.result()
                        final[segment_keys[index]] = response
                return final
            final_result = run_in_threads(segment_details, segment_keys)
            return {"data":final_result,"status":"success"}
        else:
            flight_search_response = flight_search(credentials = self.credentials,search_data = modified_journey_details,
                                                   segment_details = segment_details, session_id= session_id,book_filters = book_filters)                                                   
            flight_search_response = self.add_uuid_to_segments(flight_search_response,flight_type,journey_type)
            return {"data":flight_search_response,"status":"success"}

    def get_updated_fare_details(self,index,segment_data, search_details,raw_data,raw_doc,
                                 currentfare,fare_details,session_id):
        try:
            stt_fare_id = currentfare["stt_fare_id"] 
            search_key = raw_data["Search_key"]
            fare_adjustment,tax_condition= set_fare_details(fare_details)
            segment_keys = create_segment_keys(search_details)
            flight_key = raw_data["Flight_Key"]
            if search_details["journey_type"] =="One Way" or  search_details["journey_type"] =="Multi City" or\
                (search_details["journey_type"] =="Round Trip" and search_details["flight_type"] == "DOM"):
                fareDetails = {}
                result = {}
                flightSegment = segment_keys[index]
                segment_id = segment_data['segment_id']
                fare_quote_response = fare_quote(credentials = self.credentials,stt_fare_id = stt_fare_id,
                                                flight_key = flight_key, search_key = search_key,session_id = session_id)
                fqr_modified = AM.get_updated_fare_details(fare_quote_response = fare_quote_response,
                                                                type = "NO_ROUND_INT")
                is_ffn = fqr_modified["is_ffn"]
                pax_DOB = AM.dob_validations(fare_quote_response = fare_quote_response)
                result['fare_id'] = segment_data['fare_id']
                calculated_fares = calculate_fares(fare_details = fqr_modified["calculate_fares"],fare_adjustment = fare_adjustment,
                                                    tax_condition = tax_condition,
                                                        pax_data = search_details["passenger_details"])
                result["offeredFare"] = calculated_fares["offered_fare"]
                result["Discount"] = calculated_fares["discount"]
                result["publishedFare"] = calculated_fares["publish_fare"]
                result["supplier_publishFare"] = calculated_fares["supplier_published_fare"]
                result["supplier_offerFare"] = calculated_fares["supplier_offered_fare"]
                result['currency'] = fqr_modified["currency"]
                result['colour'] = "Red"
                result['fareBreakdown'] = get_fareBreakdown(fqr_modified["fare_breakdown"],result["publishedFare"],
                                                            search_details["passenger_details"])
                result['isRefundable'] = fqr_modified["reFundable"]
                fareDetails[flightSegment] = result
                unified_seg = {"itineraries":[flightSegment],flightSegment:[],"fareDetails":fareDetails}
                flight_legs = fqr_modified["flight_legs"]
                IsPriceChanged = True if fare_quote_response.get("alerts") else False
                updated = True
                unified_structure = unify_seg_quote(fqr_modified["unify_seg_quote"],
                                                    flightSegment,flight_legs)
                unified_structure["segmentID"] = segment_id
                # calculated_fares = calculate_fares(fare_details = fqr_modified["calculate_fares"],fare_adjustment = fare_adjustment,
                #                                     tax_condition = tax_condition,
                #                                         pax_data = search_details["passenger_details"])
                # unified_structure["offeredFare"] = calculated_fares["offered_fare"]
                # unified_structure["Discount"] = calculated_fares["discount"]
                # unified_structure["publishedFare"] = calculated_fares["publish_fare"]
                # unified_structure["supplier_publishFare"] = calculated_fares["supplier_published_fare"]
                # unified_structure["supplier_offerFare"] = calculated_fares["supplier_offered_fare"]
                # unified_structure["currency"] = fqr_modified["currency"] 
                unified_seg[flightSegment] = unified_structure
                misc_data = {"flight_key":fqr_modified["latest_flight_key"],"search_key":search_key} 
                misc_doc = {"session_id":session_id,"segment_id":segment_id,"data":misc_data,
                            "createdAt":datetime.now(),"type":"misc"}
                self.mongo_client.searches.insert_one(misc_doc)
                return {"updated":updated,"data":unified_seg,"raw":fare_quote_response,"IsPriceChanged":IsPriceChanged,
                        "status":"success",'frequent_flyer_number':False,"pax_DOB":pax_DOB,'frequent_flyer_number':is_ffn} \
                    if updated else {"updated":updated,"data":unified_seg,"close":True,"raw":fare_quote_response,"status":"failure",
                                    "IsPriceChanged":IsPriceChanged,'frequent_flyer_number':False,"pax_DOB":pax_DOB,'frequent_flyer_number':is_ffn}
            else:
                updated = False    
            return {"updated":updated,"data":unified_seg,"raw":fare_quote_response,"IsPriceChanged":IsPriceChanged,
                    "status":"success",'frequent_flyer_number':False}\
                if updated else {"updated":updated,"data":unified_seg,"close":True,"raw":fare_quote_response,"status":"failure",
                                "IsPriceChanged":IsPriceChanged,'frequent_flyer_number':False}
        except Exception as e:
            return {"updated":False,"status":"failure","close":True,"IsPriceChanged":False,"raw":str(e)}
            
    def get_ssr(self, **kwargs):
        def find_max_length(seat_data):
            max_length = 0 
            prev_len = 0 
            reference_row = None
            seat_index_dict = {} 
            for seat_row in seat_data["Seat_Row"]:
                if len(seat_row["Seat_Details"]) >= prev_len:
                    reference_row = seat_row["Seat_Details"]
                max_length = max(max_length, len(seat_row["Seat_Details"]))
            if reference_row:
                for seat_index,seat in enumerate(reference_row):
                    try:
                        seat_letter = ''.join(filter(str.isalpha, seat.get("SSR_Code")))
                        if seat.get("SSR_Status") != 0:
                            seat_index_dict[seat_letter] = seat_index
                    except:
                        pass
            return max_length,seat_index_dict
        air_pricing_mongo = self.mongo_client.fetch_all_with_sessionid(session_id = kwargs["session_id"],type = "air_pricing")[0]
        payload_ssr = {"Search_Key":kwargs["raw_data"]["Search_key"],"AirSSRRequestDetails":[]}
        payload_seat_ssr = {"Search_Key":kwargs["raw_data"]["Search_key"],"Flight_Keys":[]}
        for flight_leg in air_pricing_mongo["fareQuote"][kwargs["segment_key"]]["AirRepriceResponses"]:
            payload_ssr["AirSSRRequestDetails"].append({"Flight_Key":flight_leg["Flight"]["Flight_Key"]})
            payload_seat_ssr["Flight_Keys"].append(flight_leg["Flight"]["Flight_Key"])
        ssr_response = get_ssr_data(credentials = self.credentials, payload = payload_ssr, session_id = kwargs["session_id"])
        ssr_seat_response = get_ssr_seat_data(credentials = self.credentials, payload = payload_seat_ssr, session_id = kwargs["session_id"])
        segment_by_ids = [segment["Origin"] + "-" + segment["Destination"] for segment in \
                          air_pricing_mongo["fareQuote"][kwargs["segment_key"]]["AirRepriceResponses"][0]["Flight"]["Segments"]]
        sub_ssr = {}
        flight_ssr_response = {kwargs["segment_key"]:[]}
        for segment_id in segment_by_ids:
            sub_ssr[segment_id] = {"baggage_ssr":{"adults":[],"children":[]},
                                   "meals_ssr":{"adults":[],"children":[]},"seats_ssr":{"adults":{"seatmap":[],"seat_data":{}},
                                   "children":{"seatmap":[],"seat_data":{}}},"journey_segment":segment_id,
                                   "is_baggage":False,"is_meals":False,"is_deats":False}
        try:
            if ssr_response.get("status"):
                for ssr_flight_data in ssr_response["data"]["SSRFlightDetails"][0]["SSRDetails"]: 
                    if ssr_flight_data["SSR_TypeName"].upper() == "BAGGAGE":
                        baggage_out = {}
                        baggage_out["Code"] = ssr_flight_data.get("SSR_Code")
                        baggage_out["Weight"] = ssr_flight_data.get('SSR_TypeDesc','').capitalize()
                        baggage_out["Unit"] = ""
                        baggage_out["Quantity"] = ssr_flight_data.get("quantity",1)
                        baggage_out["Price"] = ssr_flight_data["Total_Amount"]
                        baggage_out['Description'] = ssr_flight_data['SSR_TypeDesc']
                        if 0 in ssr_flight_data["ApplicablePaxTypes"]:
                            if int(ssr_flight_data["Segment_Id"]) !=0:
                                if  ssr_flight_data["Segment_Wise"]:
                                    is_baggage = True
                                    sub_ssr[segment_by_ids[ssr_flight_data["Segment_Id"]]]["baggage_ssr"]["adults"].append(baggage_out)
                            else:
                                is_baggage = True
                                sub_ssr[segment_by_ids[ssr_flight_data["Segment_Id"]]]["baggage_ssr"]["adults"].append(baggage_out)
                        if 1 in ssr_flight_data["ApplicablePaxTypes"]:
                            if int(ssr_flight_data["Segment_Id"]) !=0:
                                if ssr_flight_data["Segment_Wise"]:
                                    is_baggage = True
                                    sub_ssr[segment_by_ids[ssr_flight_data["Segment_Id"]]]["baggage_ssr"]["children"].append(baggage_out) 
                            else:
                                is_baggage = True
                                sub_ssr[segment_by_ids[ssr_flight_data["Segment_Id"]]]["baggage_ssr"]["children"].append(baggage_out) 
                        if not sub_ssr[segment_by_ids[ssr_flight_data["Segment_Id"]]].get("is_baggage"):
                            sub_ssr[segment_by_ids[ssr_flight_data["Segment_Id"]]]["is_baggage"] = is_baggage

                    if ssr_flight_data["SSR_TypeName"].upper() == "MEALS":
                        meals_out = {}
                        meals_out["Code"] = ssr_flight_data.get("SSR_Code")
                        meals_out["Unit"] = ""
                        meals_out["Quantity"] = ssr_flight_data.get("quantity",1)
                        meals_out["Price"] = ssr_flight_data["Total_Amount"]
                        meals_out['Description'] = ssr_flight_data['SSR_TypeDesc']
                        if 0 in ssr_flight_data["ApplicablePaxTypes"]:
                            if int(ssr_flight_data["Segment_Id"]) !=0:
                                if ssr_flight_data["Segment_Wise"]:
                                    is_meals = True                                
                                    sub_ssr[segment_by_ids[ssr_flight_data["Segment_Id"]]]["meals_ssr"]["adults"].append(meals_out)
                            else:
                                is_meals = True
                                sub_ssr[segment_by_ids[ssr_flight_data["Segment_Id"]]]["meals_ssr"]["adults"].append(meals_out)
                        if 1 in ssr_flight_data["ApplicablePaxTypes"]:
                            if int(ssr_flight_data["Segment_Id"]) !=0:
                                if ssr_flight_data["Segment_Wise"]:  
                                    is_meals = True                          
                                    sub_ssr[segment_by_ids[ssr_flight_data["Segment_Id"]]]["meals_ssr"]["children"].append(meals_out)
                            else:
                                is_meals = True
                                sub_ssr[segment_by_ids[ssr_flight_data["Segment_Id"]]]["meals_ssr"]["children"].append(meals_out)
                        if not sub_ssr[segment_by_ids[ssr_flight_data["Segment_Id"]]].get("is_meals"):
                            sub_ssr[segment_by_ids[ssr_flight_data["Segment_Id"]]]["is_meals"] = is_meals
        except:
            for segment_id in segment_by_ids:
                sub_ssr[segment_id]["baggage_ssr"] = {"adults":[],"children":[]}
                sub_ssr[segment_id]["is_baggage"] = False
                sub_ssr[segment_id]["meals_ssr"] = {"adults":[],"children":[]}
                sub_ssr[segment_id]["is_meals"] = False
        try:
            if ssr_seat_response.get("status"):
                for ssr_seat_leg in ssr_seat_response["data"]["AirSeatMaps"]:
                    for seg_index,ssr_seat_segment in enumerate(ssr_seat_leg["Seat_Segments"]):
                        max_length,seat_ref_dict = find_max_length(ssr_seat_segment)
                        row_len = len(ssr_seat_segment["Seat_Row"])
                        for seat_row in ssr_seat_segment["Seat_Row"]:
                            seat_list = {"adults":[{"SeatType": None} for _ in range(max_length)],"children":[{"SeatType": None} for _ in range(max_length)]}
                            is_segment_wise = [False]
                            for seat_detail in seat_row["Seat_Details"]:
                                seat_out = {}
                                if seat_detail.get("SSR_Status"):
                                    if seat_detail.get("SSR_Code") !=0:
                                        row_letter = ''.join(filter(str.isalpha, seat_detail.get("SSR_Code"))).upper()
                                        row_num = int(''.join(filter(str.isdigit, seat_detail.get("SSR_Code"))))
                                        seat_out["Code"] = seat_detail.get("SSR_Code")
                                        seat_out["isBooked"] = False if seat_detail.get("SSR_Status") == 1 else True
                                        seat_out["seatType"] = 1
                                        seat_out["Price"] = seat_detail.get("Total_Amount",0)
                                        if 0 in seat_detail.get("ApplicablePaxTypes",[]):
                                            seat_list["adults"][seat_ref_dict.get(row_letter)] = seat_out
                                        else:
                                            seat_list["adults"][seat_ref_dict.get(row_letter)] = {"seatType":-1}
                                        if 1 in seat_detail.get("ApplicablePaxTypes",[]):
                                            seat_list["children"][seat_ref_dict.get(row_letter)] = seat_out    
                                        else:
                                            seat_list["children"][seat_ref_dict.get(row_letter)] = {"seatType":-1}
                                is_segment_wise.append(seat_detail.get("Segment_Wise"))
                            if seg_index != 0:
                                if any(is_segment_wise):
                                    sub_ssr[segment_by_ids[seg_index]]["is_seats"] = True
                                    sub_ssr[segment_by_ids[seg_index]]["seats_ssr"]["adults"]["seatmap"].append({"row" :row_num,"seats":seat_list["adults"]})
                                    sub_ssr[segment_by_ids[seg_index]]["seats_ssr"]["children"]["seatmap"].append({"row" :row_num,"seats":seat_list["children"]})
                            else:   
                                sub_ssr[segment_by_ids[seg_index]]["is_seats"] = True
                                sub_ssr[segment_by_ids[seg_index]]["seats_ssr"]["adults"]["seatmap"].append({"row" :row_num,"seats":seat_list["adults"]})
                                sub_ssr[segment_by_ids[seg_index]]["seats_ssr"]["children"]["seatmap"].append({"row" :row_num,"seats":seat_list["children"]})
                    sub_ssr[segment_by_ids[seg_index]]["seats_ssr"]["adults"]["seat_data"]["column"] = max_length
                    sub_ssr[segment_by_ids[seg_index]]["seats_ssr"]["adults"]["seat_data"]["row"] = row_len
        except:
            for segment_id in segment_by_ids:
                sub_ssr[segment_id]["seats_ssr"] = {"adults":{"seatmap":[],"seat_data":{}},
                                                    "children":{"seatmap":[],"seat_data":{}}}
                sub_ssr[segment_id]["is_seats"] = False
        flight_ssr_response[kwargs["segment_key"]] = list(sub_ssr.values())
        return {"data":flight_ssr_response} | {"raw":{"ssr":ssr_response.get("data",{}),"seat_ssr":ssr_seat_response["data"]}}
    
    def generate_fare_rules_html(self,response, currency = "INR"):
        try:
            fare_rule = response["FareRules"]
            html = f"""
            <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        margin: 20px;
                        background-color: #F5F5F5;
                    }}
                    h1 {{
                        color: #333;
                        text-align: center;
                        margin-bottom: 20px;
                    }}
                    table {{
                        width: 80%;
                        margin: 0 auto;
                        border-collapse: collapse;
                        background-color: #fff;
                        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                    }}
                    th, td {{
                        padding: 12px 15px;
                        text-align: left;
                        border-bottom: 1px solid #ddd;
                    }}
                    th {{
                        background-color: #4CAF50;
                        color: white;
                    }}
                    tr:hover {{
                        background-color: #F1F1F1;
                    }}
                    .amount {{
                        font-weight: bold;
                        color: #D32F2F;
                    }}
                </style>
            </head>
            """
            for rule in fare_rule:
                html += f"""
                    <tr>
                        <td>{rule["FareRuleDesc"]}</td>
                    </tr>
                """
            html += """
                </table>
            </body>
            </html>
            """
            return html
        except:
            return "No Fare Rules Available!"
        
    def find_baggage_info(self,fare_detail):
        baggage_info = {"checkin_baggage" :"N/A","hand_baggage" :"N/A"}
        try:
            for pax_data in fare_detail["FareDetails"]:
                if pax_data["PAX_Type"] == 0:
                    baggage_info["checkin_baggage"]= pax_data.get("Free_Baggage",{}).get("Check_In_Baggage","N/A")
                    baggage_info["hand_baggage"] = pax_data.get("Free_Baggage",{}).get("Hand_Baggage","N/A")
                    break
            return baggage_info
        except:
            return baggage_info
    
    def get_fare_details(self,**kwargs):
        try:
            pax_data = kwargs["master_doc"]["passenger_details"]
            fare_adjustment,tax_condition = set_fare_details(kwargs.get("fare_details"))
            fareDetails = []
            sorted_price_list = self.sort_prices(fares = kwargs["raw_data"]["Fares"],pax_data = pax_data )
            for fare_index,fare_detail in enumerate(sorted_price_list):
                result = {}
                fare_id = fare_detail["Fare_Id"]
                flight_key = kwargs["raw_data"]["Flight_Key"]
                search_key = kwargs["raw_data"]["Search_key"]
                default_baggage_info = self.find_baggage_info(fare_detail)
                result['baggage'] = {"checkInBag" : default_baggage_info["checkin_baggage"],
                                    "cabinBag":default_baggage_info["hand_baggage"]}
                result['fare_id'] = create_uuid("FARE")
                result["transaction_id"] = fare_detail["Fare_Id"]
                result['segment_id'] = kwargs.get("segment_id")
                calculated_fares = calculate_fares(fare_details = sorted_price_list[fare_index]["FareDetails"],
                                                    fare_adjustment = fare_adjustment,
                                                    tax_condition = tax_condition,
                                                    pax_data = kwargs["master_doc"]["passenger_details"])
                result['publishedFare'] = calculated_fares["publish_fare"]
                result['offeredFare'] = calculated_fares["offered_fare"]
                result["Discount"] = calculated_fares["discount"]
                result['vendor_id'] = self.vendor_id.split("VEN-")[-1]
                result['fareType'] = AM.get_uiName(fare_detail)
                result['uiName'] = AM.get_uiName(fare_detail)
                result['currency'] = "INR"
                result['colour'] = "RED"
                result['fareBreakdown'] = get_fareBreakdown(fare_detail,result['publishedFare'],
                                                            kwargs["master_doc"]["passenger_details"])
                result['isRefundable'] = fare_detail["Refundable"]
                result["misc"] = {result['fare_id']:{"search_key":search_key,"flight_key":flight_key,
                                                     "fare_id":fare_id}}
                fareDetails.append(result)
            return fareDetails,"success"
        except:
            return [],"failure"
    
    def sort_prices(self,**kwargs):
        try:
            fares = kwargs.get("fares")
            pax_data = kwargs.get("pax_data")
            for fare in fares:
                sorted_offer_fare = 0
                for fare_detail in fare["FareDetails"]:
                    if int(fare_detail["PAX_Type"]) == 0:
                        sorted_offer_fare = int(pax_data["adults"]) * (fare_detail["Basic_Amount"] + fare_detail["AirportTax_Amount"] - \
                                fare_detail["Gross_Commission"])
                    elif int(fare_detail["PAX_Type"]) == 1:
                        sorted_offer_fare = int(pax_data["children"]) * (fare_detail["Basic_Amount"] + fare_detail["AirportTax_Amount"] - \
                            fare_detail["Gross_Commission"])
                    elif int(fare_detail["PAX_Type"]) == 2:
                        sorted_offer_fare = int(pax_data["infants"]) * (fare_detail["Basic_Amount"] + fare_detail["AirportTax_Amount"] - \
                            fare_detail["Gross_Commission"])
                fare["sorted_offer_fare"] = sorted_offer_fare
            sorted_price_list = sorted(fares, key = lambda x: x["sorted_offer_fare"])
            return sorted_price_list
        except:
            return fares

    def hold_booking(self,**kwargs):
        kwargs["ticketing_type"] = 0
        hold_response = self.purchase(**kwargs)
        return hold_response

    def get_fare_rule(self,**kwargs):
        try:
            session_id = kwargs["session_id"]
            fare_id = kwargs["fare_id"]
            fares = kwargs["fares"]
            fare_rules = "No Fare Rule Available"
            is_fare_rule = False
            for vendor_fare  in fares:
                for fare_detail in vendor_fare["fareDetails"]:
                    if fare_id == fare_detail["fare_id"]:
                        price_dict = vendor_fare["misc"][fare_id]
                        search_key = price_dict["search_key"]
                        flight_key = price_dict["flight_key"]
                        fare_id = price_dict["fare_id"]
                        fare_rule_response = fare_rule(credentials = self.credentials,search_key = search_key,
                                                    fare_id = fare_id,flight_key = flight_key,
                                                    session_id = session_id)
                        fare_rules = self.generate_fare_rules_html(fare_rule_response, currency="INR")
                        is_fare_rule = True
                        break
                if is_fare_rule:
                    break
            return fare_rules,""
        except:
            return "No Fare Rule Available"

    def add_uuid_to_segments(self,vendor_data,flight_type,journey_type):
        if vendor_data:
            if journey_type =="One Way" or  journey_type  == "Multi City" or \
                (journey_type == "Round Trip" and flight_type == "DOM"):
                segments = vendor_data["TripDetails"][0]["Flights"]
                for segment in segments:
                    seg = str(self.vendor_id)+"_$_"+create_uuid("SEG")
                    segment["segmentID"] = seg
                    segment["Search_key"] = vendor_data["Search_Key"]
                        
            elif journey_type =="Round Trip" and flight_type == "INT":
                segments = vendor_data["searchResult"]["tripInfos"].get("COMBO")
                for segment in segments:
                    seg = str(self.vendor_id)+"_$_"+create_uuid("SEG")
                    segment["segmentID"] = seg
            return vendor_data
        else:
            return {}
    
    def find_segment_by_id(self, data, segment_id, journey_details):
        vendor_data = data.get("data")
        if journey_details["journey_type"] =="One Way":
            segments = vendor_data["TripDetails"][0]["Flights"]
            for segment in segments:
                if segment["segmentID"] == segment_id:
                    return segment
        elif (journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "DOM") \
             or journey_details["journey_type"] == "Multi City":
            segment_keys = create_segment_keys(journey_details)
            for segment_key in segment_keys:
                segments = vendor_data[segment_key]["TripDetails"]
                for trip_index,_ in enumerate(segments):
                    for segment in segments[trip_index]["Flights"]:
                        if segment["segmentID"] == segment_id:
                            return segment
        elif journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "INT":
            segments = vendor_data["searchResult"]["tripInfos"].get("COMBO")
            for segment in segments:
                if segment["segmentID"] == segment_id:
                    return segment
        return None
    
    def check_hold(self,fare_quote,itinerary):
        try:
            is_hold = all(flight["Flight"]["Block_Ticket_Allowed"] for flight in fare_quote["AirRepriceResponses"])
            return {"is_hold":is_hold,"is_hold_ssr":True}
        except:
            return {"is_hold":False,"is_hold_ssr":False}
        
    def get_repricing(self,**kwargs):
        return{"is_fare_change": False,"new_fare":None,"old_fare":None,"is_hold_continue":True,"error":""}

    def convert_hold_to_ticket(self,**kwargs):
        kwargs["ticketing_type"] = 2
        convert_hold_response = self.purchase(**kwargs)
        return convert_hold_response
    
    def release_hold(self,**kwargs):
        itinerary = kwargs["itinerary"]
        misc = json.loads(itinerary.misc)
        itinerary.status = "Release-Hold-Initiated"
        itinerary.modified_at = int(time.time())
        itinerary.save(update_fields=["status","modified_at"])
        payload = {"Booking_RefNo":misc["booking_refno"]}
        release_hold_response = release_hold(credentials = self.credentials, payload = payload)
        if release_hold_response["status"] == True :
            itinerary.status = "Hold-Released"
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["status","modified_at"])
            return { "itinerary_id": str(itinerary.id),"status": "success", "cancellation_status":"Ticket-Released",
                    "info":"Successfully released your booking" }
        else:
            try:
                info = release_hold_response["data"]["Response_Header"].get("Error_Desc")
            except:
                info = "Failed to release PNR"
            itinerary.status = "Release-Hold-Failed"
            itinerary.error = info
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["error","status","modified_at"])
            return { "itinerary_id": str(itinerary.id),"status": "failure","info":info, 
                    "cancellation_status":"Cancel-Ticket-Failed" }

    def cancel_ticket(self,kwargs):
        itinerary = kwargs["itinerary"]
        pax_ids = kwargs["pax_ids"]
        ssr_details_all_pax = itinerary.flightbookingssrdetails_set.all()
        misc = json.loads(itinerary.misc)
        booking_refno = misc["booking_refno"]
        airline_pnr = itinerary.airline_pnr
        payload = {"Airline_PNR": airline_pnr,
                    "RefNo": booking_refno,
                    "CancelCode": "015",
                    "ReqRemarks": "I cancelled the ticket directly with Airline",
                    "CancellationType" : 0,
                    "AirTicketCancelDetails" : []}
        for passenger_id in misc["cancellation_passenger_ids"]:
            for seg_id in range(misc["cancellation_segments"]):
                payload["AirTicketCancelDetails"].append({"FlightId":misc["flight_id"],"PassengerId":passenger_id,
                                                          "SegmentId":str(seg_id)})
        ssr_details_pax_wise = [ssr for ssr in ssr_details_all_pax if str(ssr.pax_id) in pax_ids]
        ssr_details_cancelled_pax = [ssr for ssr in ssr_details_all_pax if ssr.cancellation_status == "Cancelled"]
        itinerary.status = "Cancel-Ticket-Initiated"
        itinerary.save(update_fields=["status"])
        cancel_ticket_response = cancel_ticket(credentials = self.credentials, payload = payload)
        if cancel_ticket_response["status"] == True:
            for passenger_ssr in ssr_details_pax_wise:
                if str(passenger_ssr.pax_id) in pax_ids:
                    passenger_ssr.cancellation_status = "CANCELLATION " + "REQUESTED"
                    passenger_ssr.save()
            if len(pax_ids) + len(ssr_details_cancelled_pax) == len(ssr_details_all_pax):
                itinerary.status = "Confirmed"
            else:
                itinerary.status = "Confirmed" 
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["status","modified_at"])
            return { "itinerary_id": str(itinerary.id),"status": "success"}
        else:
            itinerary.status = "Cancel-Ticket-Failed"
            try:
                error = cancel_ticket_response["data"]["Response_Header"].get("Error_Desc","")
            except:
                error = "Failed to cancel Ticket"
            itinerary.error = error
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["status","error","modified_at"])
            return { "itinerary_id": str(itinerary.id),"status": "failure",
                    "info":"Your cancellation request failed from supplier side!"}
    
    def cancellation_charges(self,**kwargs):
        total_additional_charge = float(kwargs.get("additional_charge",0))
        itinerary = kwargs["itinerary"]
        pax_data = kwargs["pax_data"]
        pax_ids = kwargs["pax_ids"]
        org_fare_details = kwargs["fare_details"]
        per_pax_additional_charge = round(total_additional_charge/len(pax_data),2)
        per_pax_cancellation_charge = round(float(org_fare_details.get("fare",{}).get("cancellation_charges",0)) \
                                        + float(org_fare_details.get("fare",{}).get("distributor_cancellation_charges",0)),2)
        itinerary = kwargs["itinerary"]
        misc = json.loads(itinerary.misc)
        booking_details = misc["booking_detail"]
        pax_data = kwargs["pax_data"]
        pax_ids = kwargs["pax_ids"]
        pax_dict = {}
        for pax_info in pax_data:
            if str(pax_info.id) in pax_ids:
                pax_name = (pax_info.title.lower() if pax_info.title else "") + pax_info.first_name.lower() + pax_info.last_name.lower()
                pax_dict[pax_name] = str(pax_info.id)
        cancellation_charges,cancellation_amount,misc_updated = AM.get_cancellation_charges(booking_details = booking_details,selected_pax_names = pax_dict,
                                                           per_pax_additional_charge = per_pax_additional_charge,
                                                          per_pax_cancellation_charge = per_pax_cancellation_charge,misc = misc,
                                                          itinerary = itinerary)
        
        if cancellation_charges == True:
            itinerary.misc = json.dumps({**misc,**misc_updated})
            itinerary.save(update_fields=["misc"])
            return { "itinerary_id": itinerary.id,"status": "success",
                    "cancellation_charge": cancellation_amount, "currency":"₹"}
        else:
            error = "Ticket Cancellation charges not available!"
            return { "itinerary_id": itinerary.id,"status": "failure",
                    "info":error, "currency":"₹" }

    def find_pnr(self,api_response):
        try:
            return api_response["AirPNRDetails"][0]["Airline_PNR"],api_response["AirPNRDetails"][0]["CRS_PNR"]
        except:
            return "",""

    def converter(self, search_response, journey_details,fare_details):
        book_filters = self.booking_filters({"journey_type":journey_details["journey_type"],"flight_type":journey_details["flight_type"],
                                             "supplier_id":str(self.vendor_id),"fare_type":journey_details.get("fare_type")}) 
        lcc_filter = book_filters.get("is_lcc",False)
        gds_filter = book_filters.get("is_gds",False)
        fare_adjustment,tax_condition = set_fare_details(fare_details)
        if journey_details["journey_type"] == "One Way":
            date = "".join(journey_details["journey_details"][0]["travel_date"].split('-')[:2])
            flightSegment = journey_details["journey_details"][0]["source_city"]+"_"+journey_details["journey_details"][0]["destination_city"]+"_"+date
            result = {"itineraries":[flightSegment],flightSegment:[]}
            segment_keys = create_segment_keys(journey_details)
            if search_response:
                segments = search_response["TripDetails"][0]["Flights"]
                for segment in segments:
                    sorted_price_list = self.sort_prices(fares = segment["Fares"],pax_data = journey_details["passenger_details"])
                    unified_structure = unify_seg(segment["Segments"],flightSegment,sorted_price_list[0])
                    unified_structure["segmentID"] = segment.get("segmentID")
                    calculated_fares = calculate_fares(fare_details = sorted_price_list[0]["FareDetails"],
                                                    fare_adjustment = fare_adjustment,
                                                    tax_condition = tax_condition,
                                                        pax_data = journey_details["passenger_details"])
                    unified_structure["offerFare"] = calculated_fares["offered_fare"]
                    unified_structure["Discount"] = calculated_fares["discount"]
                    unified_structure["publishFare"] = calculated_fares["publish_fare"]
                    unified_structure["currency"] = segment["Fares"][0]["FareDetails"][0]["Currency_Code"]
                    unified_structure["IsLCC"] = segment["IsLCC"]
                    unified_structure["isRefundable"] =  sorted_price_list[0]["Refundable"]
                    if lcc_filter:
                        if unified_structure["IsLCC"]:
                            result[flightSegment].append(unified_structure)
                    if gds_filter:
                        if not unified_structure["IsLCC"]:
                            result[flightSegment].append(unified_structure)
                    if not lcc_filter and not gds_filter:
                        pass

        elif (journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "DOM") \
            or journey_details["journey_type"] =="Multi City":
            segment_keys = create_segment_keys(journey_details)
            result = {"itineraries":segment_keys}
            for flightSegment in segment_keys:
                result[flightSegment] = []
                if search_response[flightSegment]:
                    segments = search_response[flightSegment]["TripDetails"][0]["Flights"][:1]
                    for segment in segments:
                        sorted_price_list = self.sort_prices(fares = segment["Fares"],pax_data = journey_details["passenger_details"])
                        unified_structure = unify_seg(segment["Segments"],flightSegment,sorted_price_list[0])
                        unified_structure["segmentID"] = segment.get("segmentID")
                        calculated_fares = calculate_fares(fare_details = sorted_price_list[0]["FareDetails"],
                                                        fare_adjustment = fare_adjustment,
                                                        tax_condition = tax_condition,
                                                            pax_data = journey_details["passenger_details"])
                        unified_structure["offerFare"] = calculated_fares["offered_fare"]
                        unified_structure["Discount"] = calculated_fares["discount"]
                        unified_structure["publishFare"] = calculated_fares["publish_fare"]
                        unified_structure["currency"] = segment["Fares"][0]["FareDetails"][0]["Currency_Code"]
                        unified_structure["IsLCC"] = segment["IsLCC"]
                        unified_structure["isRefundable"] =  sorted_price_list[0]["Refundable"]
                        if lcc_filter:
                            if unified_structure["IsLCC"]:
                                result[flightSegment].append(unified_structure)
                        if gds_filter:
                            if not unified_structure["IsLCC"]:
                                result[flightSegment].append(unified_structure)
                        if not lcc_filter and not gds_filter:
                            pass

        elif journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "INT":
            fs = []
            for journey_detail in journey_details['journey_details']:
                date = "".join(journey_detail["travel_date"].split('-')[:2])
                flightSegment = journey_detail["source_city"]+"_"+journey_detail["destination_city"]+"_"+date
                fs.append(flightSegment)
            arrival_airport = journey_details['journey_details'][0]["destination_city"]
            result = {"itineraries":["_R_".join(fs)],"_R_".join(fs):[]}
            main_seg_name = "_R_".join(fs)
            segments = search_response["searchResult"]["tripInfos"].get("COMBO")
            for segment in segments:
                res = {"flightSegments":{}}
                for flight_index,_ in enumerate(segment["sI"]):
                    condition = lambda d: d['aa']["code"] == arrival_airport
                    one_way_index = next((i for i, d in enumerate(segment["sI"]) if condition(d)), -1)
                    flightSegment = fs[0] if flight_index <= one_way_index else fs[1]
                    split_segment = segment["sI"][:one_way_index+1] if flightSegment == fs[0] else segment["sI"][one_way_index+1:]
                    if not res['flightSegments'].get(flightSegment):
                        unified_structure = unify_seg(split_segment ,flightSegment,segment)
                        res['flightSegments'][flightSegment] = unified_structure["flightSegments"][flightSegment]
                res["segmentID"] = segment["segmentID"]
                sorted_price_list = self.sort_prices(segment["totalPriceList"])
                calculated_fares = calculate_fares(sorted_price_list[0]["fd"],fare_adjustment,tax_condition,
                                                    journey_details["passenger_details"])
                res["offerFare"] = calculated_fares["offered_fare"]
                res["Discount"] = calculated_fares["discount"]
                res["publishFare"] = calculated_fares["publish_fare"]
                res["currency"] = "INR" 
                result[main_seg_name].append(res)
        return {"data":result,"status":"success"}
    
    def purchase(self,**kwargs):
        itinerary = kwargs["itinerary"]
        booking = kwargs["booking"]
        try:
            booking = kwargs["booking"]
            display_id = booking.display_id
            name = booking.user.first_name + booking.user.last_name
            supplier_id = self.credentials.get("supplier_id","")
            booking_dict = booking.__dict__
            payload = {}
            booking_flight_details = [] 
            itinerary_key = itinerary.itinerary_key
            flight_booking_unified_data = FlightBookingUnifiedDetails.objects.filter(itinerary = itinerary.id).first()
            isLCC = flight_booking_unified_data.fare_quote[itinerary_key]["AirRepriceResponses"][0]["Flight"]["IsLCC"]
            ssr_response_selected =  flight_booking_unified_data.ssr_raw[itinerary_key]
            ssr_details = list(kwargs["ssr_details"].values())
            fare_details = flight_booking_unified_data.fare_details[itinerary_key]
            payment_details_easylink = {"new_published_fare": fare_details["publishedFare"],
                            "new_offered_fare":fare_details["offeredFare"],
                            "supplier_offered_fare":fare_details["supplier_offerFare"],
                            "supplier_published_fare":fare_details["supplier_publishFare"]}
            booking_flight_details.append({"Flight_Key":flight_booking_unified_data.misc["flight_key"],
                                            "Search_Key":flight_booking_unified_data.misc["search_key"],
                                            "BookingSSRDetails": []})

            payload["Customer_Mobile"] = os.getenv('BTA_PHONE',"")
            payload["WhatsAPP_Mobile"] = None
            payload["Passenger_Mobile"] = json.loads(booking_dict["contact"])["phone"]
            payload["Passenger_Email"] = json.loads(booking_dict["contact"])["email"]
            payload["BookingFlightDetails"] = booking_flight_details
            pax_data = []
            pax_details = kwargs["pax_details"]       
            for passenger_num,pax in enumerate(pax_details):
                filtered_ssr = list(filter(lambda x: str(x["pax_id"]) == str(pax.id), ssr_details))
                if filtered_ssr:
                    BookingSSRDetails = AM.get_selected_ssr_data(filtered_ssr,ssr_response_selected,passenger_num + 1)
                    if BookingSSRDetails:
                        booking_flight_details[0]["BookingSSRDetails"].extend(BookingSSRDetails) 
                passenger = {}
                passenger["Pax_Id"] = passenger_num + 1
                passenger["Pax_type"] = str(AM.pax_type_mapping.get(pax.pax_type))
                passenger["Title"] = self.passenger_title_creation(gender = pax.gender,title = pax.title,
                                                                pax_type = pax.pax_type)
                passenger["First_Name"] = pax.first_name 
                passenger["Last_Name"] = pax.last_name
                passenger["Gender"] = str(AM.gender_mapping.get(pax.gender))
                passenger["Age"] = None
                passenger["DOB"] = dob_passport_date_correction(pax.dob) if pax.dob else None
                passenger["Passport_Number"] = pax.passport if pax.passport else None
                passenger["Passport_Expiry"] = dob_passport_date_correction(pax.passport_expiry) if pax.passport else None
                passenger["Passport_Issuing_Country"] = pax.passport_issue_country_code if pax.passport else None
                passenger["Nationality"] = None
                passenger["Pancard_Number"] = None
                passenger["FrequentFlyerDetails"] = None
                pax_data.append(passenger)
            payload["PAX_Details"] = pax_data
            payload["GST"] = False
            payload["GST_Number"] = None
            payload["GST_HolderName"] = None
            payload["GST_Address"] = None
            payload["CostCenterId"] = 0
            payload["ProjectId"]= 0
            payload["BookingRemark"] = None
            payload["CorporateStatus"] = 0
            payload["CorporatePaymentMode"]= 0
            payload["MissedSavingReason"] = None
            payload["CorpTripType"]= None
            payload["CorpTripSubType"]= None
            payload["TripRequestId"]= None
            payload["BookingAlertIds"]= None
            ticketing_type = str(kwargs.get("ticketing_type",1))
            if int(ticketing_type) in ["1","2"]:
                itinerary.status = "Ticketing-Initiated"
            else:
                itinerary.status = "Hold-Initiated"
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields = ["status","modified_at"])
            if int(ticketing_type) != 2:
                ticket_book_temp = temp_ticket_book(credentials = self.credentials, payload = payload, session_id = booking.session_id)
            else:
                misc_log = json.loads(itinerary.misc)
                ticket_book_temp = {"status":True,"data":{"Booking_RefNo":misc_log["booking_refno"]}}  
            if ticket_book_temp.get("status"):
                booking_refno = ticket_book_temp.get("data",{}).get("Booking_RefNo","")
                itinerary.supplier_booking_id = booking_refno
                payload = {"Booking_RefNo":booking_refno,"Ticketing_Type":str(ticketing_type)}
                ticket_booking_details = book_ticket_flow(credentials = self.credentials, payload = payload, session_id = booking.session_id,
                                                        ticketing_type = ticketing_type)
                if ticket_booking_details.get("status"):
                    itinerary.status = "Confirmed"
                    itinerary.soft_fail = False
                    itinerary.error = ""
                    to_easy_link = True
                    is_pnr = True
                    air_reprint_details = air_reprint(credentials = self.credentials,payload = {"Booking_RefNo":booking_refno})
                    ticket_status = self.generate_ticket_status(air_reprint_details.get("data",{}))
                    airline_pnr,gds_pnr = self.find_pnr(air_reprint_details.get("data",{}))
                    misc = {"booking_refno":booking_refno,"booking_detail":air_reprint_details}
                    if ticket_status:
                        if not isLCC:
                            if not gds_pnr and not airline_pnr:
                                itinerary.soft_fail = True if int(ticketing_type) != 0 else False
                                itinerary.error = "GDS PNR not available"
                                itinerary.status = "Ticketing-Failed" if int(ticketing_type) != 0 else "Hold-Failed"
                                is_pnr = False
                        else:
                            if not airline_pnr:
                                itinerary.soft_fail = True if int(ticketing_type) != 0 else False
                                itinerary.error = "Airline PNR not available"
                                itinerary.status = "Ticketing-Failed" if int(ticketing_type) != 0 else "Hold-Failed"
                                is_pnr = False
                        itinerary.airline_pnr = airline_pnr
                        itinerary.gds_pnr = gds_pnr
                        itinerary.modified_at = int(time.time())
                        itinerary.misc =  json.dumps(misc)
                        if is_pnr:
                            if int(ticketing_type) == 1 or int(ticketing_type) == 2:
                                for pax_ssr in kwargs["ssr_details"].filter(itinerary = itinerary):
                                    if "PAXTicketDetails" in air_reprint_details["data"]["AirPNRDetails"][0]:
                                        passenger_response = air_reprint_details["data"]["AirPNRDetails"][0]["PAXTicketDetails"]
                                        first_name = pax_ssr.pax.first_name
                                        last_name = pax_ssr.pax.last_name
                                        for pax_data_response in passenger_response:
                                            if pax_data_response.get("First_Name") == first_name and pax_data_response.get("Last_Name") == last_name:
                                                try:
                                                    supplier_ticket_number = pax_data_response["TicketDetails"][0].get("Ticket_Number","")
                                                except:
                                                    supplier_ticket_number = ""
                                                pax_ssr.supplier_ticket_number = supplier_ticket_number
                                                pax_ssr.save()
                                                if not supplier_ticket_number and not isLCC:
                                                    itinerary.soft_fail = True
                                                    to_easy_link = False
                                                    itinerary.error = "Ticket number not available"
                                                    itinerary.status = "Ticketing-Failed"
                                    else:
                                        itinerary.soft_fail = True if not isLCC else False
                                        itinerary.error = "Ticket number not available" if not isLCC else ""
                                        to_easy_link = False if not isLCC else True
                                        itinerary.status = "Ticketing-Failed" if not isLCC else "Confirmed"
                                try:
                                    if to_easy_link:
                                        finance_manager = FinanceManager(booking.user)
                                        finance_manager.book_stt_common(booking_data = air_reprint_details["data"], display_id = display_id,
                                                                name = name,payment_details = payment_details_easylink,
                                                                supplier_id = supplier_id,itinerary = itinerary,pax_length = len(kwargs["pax_details"]))
                                        new_published_fare = booking.payment_details.new_published_fare if booking.payment_details.new_published_fare else 0
                                        ssr_price = booking.payment_details.ssr_price if booking.payment_details.ssr_price else 0
                                        total_fare = round(float(new_published_fare) + float(ssr_price),2)
                                        self.update_credit(booking = booking,total_fare = total_fare)
                                except Exception as e:
                                    error_trace = tb.format_exc()
                                    easylink_error_log = {"display_id":booking.display_id,
                                            "error":str(e),
                                            "error_trace":error_trace,
                                            "type":"easy_link"}
                                    self.mongo_client.vendors.insert_one(easylink_error_log)
                                purchase_response = {"status":True}
                            else:
                                itinerary.status = "On-Hold"
                                itinerary.soft_fail =  False
                                purchase_response = {"status":True}
                            itinerary.hold_till = ticket_booking_details["data"]["AirlinePNRDetails"][0].get("Hold_Validity","")
                            itinerary.save(update_fields=["status","misc","modified_at","airline_pnr","hold_till","soft_fail",
                                                        "gds_pnr","error","supplier_booking_id"])
                        else:
                            itinerary.soft_fail =  False if int(ticketing_type) == 0 else True
                            itinerary.hold_till = ""
                            itinerary.status = "Hold-Failed" if int(ticketing_type) == 0 else "Ticketing-Failed"
                            purchase_response = {"status":True if itinerary.soft_fail else False}
                            itinerary.save(update_fields=["status","misc","airline_pnr","hold_till","soft_fail",
                                                            "gds_pnr","error","supplier_booking_id"])
                    else:
                        itinerary.soft_fail =  False
                        itinerary.hold_till = ""
                        itinerary.error = "Hold Failed from supplier side" if int(ticketing_type) == 0 else "Ticketing Failed from supplier side"
                        itinerary.status = "Hold-Failed" if int(ticketing_type) == 0 else "Ticketing-Failed"
                        purchase_response = {"status": False}
                        itinerary.save(update_fields=["status","misc","airline_pnr","hold_till","soft_fail",
                                                            "gds_pnr","error","supplier_booking_id"])  
                else:
                    itinerary.error = ticket_booking_details.get("data",{}).get("Response_Header",{}).get("Error_Desc", "Ticketing Failed from supplier side")
                    itinerary.status = "Ticketing-Failed"
                    itinerary.modified_at = int(time.time())
                    misc = {"booking_id":booking_refno,"booking_detail":{}}
                    itinerary.misc =  json.dumps(misc)
                    itinerary.save(update_fields=["error","status","misc","modified_at"])
                    purchase_response = {"status":False}
            else:
                itinerary.error = ticket_book_temp.get("data",{}).get("Response_Header",{}).get("Error_Desc", "Ticketing Failed from supplier side")
                itinerary.status = "Ticketing-Failed"
                itinerary.modified_at = int(time.time())
                misc = {"booking_id":"","booking_detail":{}}
                itinerary.misc =  json.dumps(misc)
                itinerary.save(update_fields=["error","status","misc","modified_at"])
                purchase_response = {"status":False}
            return purchase_response
        except Exception as e:
            error_trace = tb.format_exc()
            invoke_log = {"vendor":self.name(),"session_id":booking.session_id,"status":"failure","api":"purchase_error",
                          "createdAt": datetime.now(),"error":str(e),"error_trace":error_trace}
            self.mongo_client.flight_supplier.insert_one(invoke_log)
            itinerary.status = "Ticketing-Failed"
            itinerary.error = "Ticketing Failed"
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["status","modified_at","error"])
            return {"status":False}
    
    def find_flight_ids(self,**kwargs):
        out = []
        for sI_index in range(len(kwargs["data"])):
            sI_selected = kwargs["data"][sI_index]["sI"]
            for ssr_si_info in sI_selected:
                flight_key = ssr_si_info["da"]["code"] + "-" + ssr_si_info["aa"]["code"]
                out.append({ssr_si_info["id"]:flight_key})
        return out
    
    def passenger_title_creation(self,**kwargs):
        if kwargs["gender"].lower() == "male" and kwargs["pax_type"].lower() in ["child","infant"]:
            return "Master"
        elif kwargs["gender"].lower() == "female" and kwargs["pax_type"].lower() in ["child","infant"]:
            return "Ms"
        else:
            return kwargs["title"].upper()
        
    def date_format_correction(self,dob):
        dt = datetime.strptime(dob, '%Y-%m-%dT%H:%M:%S.%fZ')
        date_only = dt.strftime('%Y-%m-%d')
        return date_only
    
    def check_cancellation_status(self,itinerary):
        return {"status":"success"}
    
    def save_failed_finance(self,master_doc,data,itinerary,pax_details,fare_details,data_unified_dict):
        fare_adjustment,tax_condition = set_fare_details(fare_details)
        search_details = master_doc
        pax_details = pax_details
        booking_dict = {"BookingId":itinerary.supplier_booking_id,
                        "airline_pnr":data.get("airline_pnr"),
                        "gds_pnr":data.get("gds_pnr"),
                        "status":itinerary.status,
                        "itinerary_id":itinerary.id}
        booking_details = booking_dict
        booking = itinerary.booking
        unified_booking = FlightBookingUnifiedDetails.objects.filter(itinerary = itinerary.id).first()
        unified_booking_fare = unified_booking.fare_details[itinerary.itinerary_key]
        display_id =booking.display_id
        Org = booking.user.organization
        easy_link_billing_code = Org.easy_link_billing_code 
        supplier_id = LookupEasyLinkSupplier.objects.filter(id= data.get("supplier")).first().supplier_id
        easy_link_account_name = Org.easy_link_account_name 
        booked_at = booking.created_at
        fare_quote =  unified_booking.fare_quote[itinerary.itinerary_key]
        try:
            finance_manager = FinanceManager(booking.user)
            finance_manager.book_failed_stt_common(fare_adjustment,tax_condition,search_details,itinerary,
                                                    pax_details,booking_details,display_id,
                                                    easy_link_billing_code,supplier_id,
                                                    easy_link_account_name,booked_at,fare_quote,unified_booking_fare)
            new_published_fare = booking.payment_details.new_published_fare if booking.payment_details.new_published_fare else 0
            ssr_price = booking.payment_details.ssr_price if booking.payment_details.ssr_price else 0
            total_fare = round(float(new_published_fare) + float(ssr_price),2)
            self.update_credit(booking = booking,total_fare = total_fare)
        except Exception as e:
            error_trace = tb.format_exc()
            easylink_error_log = {"display_id":booking.display_id,
                    "error":str(e),
                    "error_trace":error_trace,
                    "type":"easy_link"}
            self.mongo_client.vendors.insert_one(easylink_error_log)

    def generate_ticket_status(self,data):
        try:
            status_id = data["AirPNRDetails"][0]["Ticket_Status_Id"]
            if int(status_id) in [5,8,6]: # failed,rejected,cancelled
                return False
            else:
                return True
        except:
            return False

    def current_ticket_status(self,**kwargs):
        soft_deleted_itinerary = kwargs["soft_deleted_itinerary"]
        booking = soft_deleted_itinerary.booking
        display_id = booking.display_id
        try:
            invoke_status = "success"
            supplier_id = self.credentials.get("supplier_id","")
            unified_itinerary = soft_deleted_itinerary.flightbookingunifieddetailsitinerary_set.first()
            ssr_details = soft_deleted_itinerary.flightbookingssrdetails_set.all()
            booking = soft_deleted_itinerary.booking
            misc = json.loads(soft_deleted_itinerary.misc)
            booking_refno = misc["booking_refno"]
            updated_ticket_status = get_current_ticket_status(credentials = self.credentials,payload = {"Booking_RefNo":booking_refno})
            fare_details = unified_itinerary.fare_details[soft_deleted_itinerary.itinerary_key]
            payment_details_easylink = {"new_published_fare": fare_details["publishedFare"],
                        "new_offered_fare":fare_details["offeredFare"],
                        "supplier_offered_fare":fare_details["supplier_offerFare"],
                        "supplier_published_fare":fare_details["supplier_publishFare"]}
            if updated_ticket_status.get('status'):
                ticket_status = self.generate_ticket_status(updated_ticket_status.get("data",{}))
                airline_pnr,gds_pnr = self.find_pnr(updated_ticket_status["data"])
                if ticket_status:
                    is_all_ticket_num = True
                    is_pnr = True
                    if not airline_pnr and gds_pnr:
                        is_pnr = False
                        invoke_status = "failure"
                    else:
                        for pax_ssr in ssr_details:
                            if "PAXTicketDetails" in updated_ticket_status["data"]["AirPNRDetails"][0]:
                                passenger_response = updated_ticket_status["data"]["AirPNRDetails"][0]["PAXTicketDetails"]
                                first_name = pax_ssr.pax.first_name
                                last_name = pax_ssr.pax.last_name
                                for pax_data_response in passenger_response:
                                    if pax_data_response.get("First_Name") == first_name and pax_data_response.get("Last_Name") == last_name:
                                        try:
                                            supplier_ticket_number = pax_data_response["TicketDetails"][0].get("Ticket_Number","")
                                        except:
                                            supplier_ticket_number = ""
                                        pax_ssr.supplier_ticket_number = supplier_ticket_number
                                        pax_ssr.save()
                                        if not supplier_ticket_number:
                                            is_all_ticket_num = False
                            else:
                                is_all_ticket_num = False
                        if is_pnr and is_all_ticket_num:
                            soft_deleted_itinerary.soft_fail = False
                            soft_deleted_itinerary.airline_pnr = airline_pnr
                            soft_deleted_itinerary.gds_pnr = gds_pnr
                            soft_deleted_itinerary.status = "Failed-Confirmed"
                            soft_deleted_itinerary.modified_at = int(time.time())
                            soft_deleted_itinerary.save(update_fields= ["soft_fail","status","modified_at","airline_pnr","gds_pnr"])
                            try:
                                finance_manager = FinanceManager(booking.user)
                                finance_manager.book_stt_common(booking_data = updated_ticket_status["data"], display_id = booking.display_id,
                                                        payment_details = payment_details_easylink,
                                                        supplier_id = supplier_id,itinerary = soft_deleted_itinerary,pax_length = len(ssr_details))
                                new_published_fare = booking.payment_details.new_published_fare if booking.payment_details.new_published_fare else 0
                                ssr_price = booking.payment_details.ssr_price if booking.payment_details.ssr_price else 0
                                total_fare = round(float(new_published_fare) + float(ssr_price),2)
                                self.update_credit(booking = booking,total_fare = total_fare)
                            except:
                                error_trace = tb.format_exc()
                                easylink_error_log = {"display_id":booking.display_id,
                                        "error":str(e),
                                        "error_trace":error_trace,
                                        "type":"easy_link"}
                                self.mongo_client.vendors.insert_one(easylink_error_log)
                            invoke_email({"user": str(booking.user.id),"sec" : 86400,"event":"Ticket_Confirmation",
                                            "booking_id":booking.display_id})
                        else:
                            invoke_status = "failure"
                else:
                    invoke_status = "failure"
                    soft_deleted_itinerary.soft_fail = False
                    soft_deleted_itinerary.status = "Ticketing-Failed"
                    soft_deleted_itinerary.modified_at = int(time.time())
                    soft_deleted_itinerary.error = "Ticketing Failed from supplier side"
                    soft_deleted_itinerary.save(update_fields= ["status","modified_at","error","soft_fail"])
            else:
                invoke_status = "failure"
            invoke_log = {"vendor":self.name(),"session_id":booking.session_id,"status":invoke_status,"api":"event_bridge",
                          "display_id":display_id,"createdAt": datetime.now()}
            self.mongo_client.flight_supplier.insert_one(invoke_log)    
        except Exception as e:
            error_trace = tb.format_exc()
            invoke_log = {"vendor":self.name(),"session_id":booking.session_id,"status":"failure","api":"event_bridge",
                          "display_id":display_id,"createdAt": datetime.now(),"error":str(e),"error_trace":error_trace}
            self.mongo_client.flight_supplier.insert_one(invoke_log)
     
def calculate_arrival_time(departure_time_str, ground_time_in_minutes):
    departure_time = datetime.strptime(departure_time_str, "%Y-%m-%dT%H:%M:%S")
    arrival_time = departure_time - timedelta(minutes=ground_time_in_minutes)
    arrival_time_str = arrival_time.strftime("%Y-%m-%dT%H:%M:%S")
    return arrival_time_str

def unify_seg_quote(flight_segments,flightSegment,segment):
    flight_segment = flight_segments[0]
    unified_structure = {"flightSegments":{flightSegment:[]}}
    cabin_class = segment["FareDetails"][0]["FareClasses"][0]["Class_Code"]
    unified_segment = {
        "airlineCode": flight_segment["Airline_Code"],
        "airlineName": flight_segment["Airline_Name"],
        "flightNumber": flight_segment["Flight_Number"],
        "equipmentType": "", 
        "departure": {
            "airportCode": flight_segment["Origin"],
            "airportName": "",
            "city": flight_segment["Origin_City"],
            "country": "",
            "countryCode": "",
            "terminal": modify_terminal_name(flight_segment.get("Origin_Terminal","")),
            "departureDatetime": modify_arrival_departure_time(flight_segment.get("Departure_DateTime",""))
        },
        "arrival": {
            "airportCode": flight_segment["Destination"],
            "airportName": "",
            "city": flight_segment["Destination_City"],
            "country": "",
            "countryCode": "",
            "terminal": modify_terminal_name(flight_segment.get("Destination_Terminal","N/A")),
            "arrivalDatetime": modify_arrival_departure_time(flight_segment.get("Arrival_DateTime",""))
        },
        "durationInMinutes":find_flight_duration(flight_segment.get("Duration","0:0")),
        "stop": len(flight_segments)-1,
        "cabinClass": cabin_class,
        "fareBasisCode": "N/A",
        "seatsRemaining": "N/A",
        "isChangeAllowed": True  
    }
    unified_structure['flightSegments'][flightSegment].append(unified_segment)
    if len(flight_segments) >1:
        for flight_segment in flight_segments[1:]:
            stop_airport_codes =  [flight["Origin"]for flight in flight_segments[1:]]
            unified_segment = {
                "airlineCode": flight_segment["Airline_Code"],
                "airlineName": flight_segment["Airline_Name"],
                "flightNumber": flight_segment["Flight_Number"],
                "equipmentType": "", 
                "departure": {
                    "airportCode": flight_segment["Origin"],
                    "airportName": "",
                    "city": flight_segment["Origin_City"],
                    "country": "",
                    "countryCode": "",
                    "terminal": modify_terminal_name(flight_segment.get("Origin_Terminal","")),
                    "departureDatetime": modify_arrival_departure_time(flight_segment.get("Departure_DateTime",""))
                },
                "arrival": {
                    "airportCode": flight_segment["Destination"],
                    "airportName": "",
                    "city": flight_segment["Destination_City"],
                    "country": "",
                    "countryCode": "",
                    "terminal": modify_terminal_name(flight_segment.get("Origin_Terminal","")),
                    "arrivalDatetime": modify_arrival_departure_time(flight_segment.get("Arrival_DateTime",""))
                },
                "durationInMinutes":find_flight_duration(flight_segment.get("Duration","0:0")),
                "stop" :len(flight_segments)-1,
                "cabinClass": cabin_class,
                "fareBasisCode": "N/A",
                "seatsRemaining": "N/A",
                "isChangeAllowed": True,
                "stopDetails": {
                "isLayover": True,
                "stopPoint": {
                    "airportCode": stop_airport_codes,
                            }  } 
            }
            unified_structure['flightSegments'][flightSegment].append(unified_segment)
    return unified_structure

def find_flight_duration(duration):
    clean_duration = re.sub(r"[^\d:]", "", duration)
    minutes, seconds = map(int, clean_duration.split(":"))
    total_duration = minutes * 60 + seconds
    return total_duration

def unify_seg(flight_segments,flightSegment,segment):
    airports = LookupAirports.objects.all()
    flight_segment = flight_segments[0]
    unified_structure = {"flightSegments":{flightSegment:[]}}
    cabin_class = segment["FareDetails"][0]["FareClasses"][0]["Class_Code"]
    unified_segment = {
        "airlineCode": flight_segment["Airline_Code"],
        "airlineName": flight_segment["Airline_Name"],
        "flightNumber": flight_segment["Flight_Number"],
        "equipmentType": "", 
        "departure": {
            "airportCode": flight_segment["Origin"],
            "airportName": AM.get_airport(flight_segment["Origin"],airports),
            "city": flight_segment["Origin_City"],
            "country": AM.get_airport_country(flight_segment["Origin"],airports),
            "countryCode": "",
            "terminal": modify_terminal_name(flight_segment.get("Origin_Terminal","N/A")),
            "departureDatetime": modify_arrival_departure_time(flight_segment.get("Departure_DateTime",""))
        },
        "arrival": {
            "airportCode": flight_segment["Destination"],
            "airportName": AM.get_airport(flight_segment["Destination"],airports),
            "city": flight_segment["Destination_City"],
            "country": AM.get_airport_country(flight_segment["Destination"],airports),
            "countryCode": "",
            "terminal": modify_terminal_name(flight_segment.get("Destination_Terminal","N/A")),
            "arrivalDatetime": modify_arrival_departure_time(flight_segment.get("Arrival_DateTime",""))
        },
        "durationInMinutes":find_flight_duration(flight_segment.get("Duration","0:0")),
        "stop": len(flight_segments)-1,
        "cabinClass": cabin_class,
        "fareBasisCode": "",
        "seatsRemaining": "",
        "isChangeAllowed": True  
    }
    unified_structure['flightSegments'][flightSegment].append(unified_segment)
    if len(flight_segments) >1:
        for flight_segment in flight_segments[1:]:
            stop_airport_codes =  [flight["Origin"]for flight in flight_segments[1:]]
            unified_segment = {
                "airlineCode": flight_segment["Airline_Code"],
                "airlineName": flight_segment["Airline_Name"],
                "flightNumber": flight_segment["Flight_Number"],
                "equipmentType": "",  
                "departure": {
                    "airportCode": flight_segment["Origin"],
                    "airportName": AM.get_airport(flight_segment["Origin"],airports),
                    "city": flight_segment["Origin_City"],
                    "country": AM.get_airport_country(flight_segment["Origin"],airports),
                    "countryCode": "",
                    "terminal": modify_terminal_name(flight_segment.get("Origin_Terminal","N/A")),
                    "departureDatetime": modify_arrival_departure_time(flight_segment.get("Departure_DateTime",""))
                },
                "arrival": {
                    "airportCode": flight_segment["Destination"],
                    "airportName": AM.get_airport(flight_segment["Destination"],airports),
                    "city": flight_segment["Destination_City"],
                    "country": AM.get_airport_country(flight_segment["Destination"],airports),
                    "countryCode": "",
                    "terminal": modify_terminal_name(flight_segment.get("Origin_Terminal","N/A")),
                    "arrivalDatetime": modify_arrival_departure_time(flight_segment.get("Arrival_DateTime",""))
                },
                "durationInMinutes":find_flight_duration(flight_segment.get("Duration","0:0")),
                "stop" :len(flight_segments)-1,
                "cabinClass": cabin_class,
                "fareBasisCode": "",
                "seatsRemaining": "",
                "isChangeAllowed": True,
                "stopDetails": {
                "isLayover": True,
                "stopPoint": {
                    "airportCode": stop_airport_codes,
                            }  } 
            }
            unified_structure['flightSegments'][flightSegment].append(unified_segment)
    return unified_structure

def calculate_fares(**kwargs):
    total_pax_count = sum(list(map(int,list(kwargs["pax_data"].values()))))
    supplier_published_fare = 0
    supplier_offered_fare = 0
    for fare in kwargs["fare_details"]:
        if fare["PAX_Type"] == 0:
            supplier_published_fare = supplier_published_fare + int(kwargs["pax_data"]["adults"])*fare.get("Total_Amount",0)
            supplier_offered_fare = supplier_offered_fare + int(kwargs["pax_data"]["adults"])*fare.get("Total_Amount",0) -\
                  int(kwargs["pax_data"]["adults"])*(fare.get("Net_Commission",0))
        elif fare["PAX_Type"] == 1:
            supplier_published_fare = supplier_published_fare + int(kwargs["pax_data"]["children"])*fare.get("Total_Amount",0)
            supplier_offered_fare = supplier_offered_fare + int(kwargs["pax_data"]["children"])*fare.get("Total_Amount",0) -\
                  int(kwargs["pax_data"]["children"])*(fare.get("Net_Commission",0))
        elif fare["PAX_Type"] == 2:
            supplier_published_fare = supplier_published_fare + int(kwargs["pax_data"]["infants"])*fare.get("Total_Amount",0)
            supplier_offered_fare = supplier_offered_fare + int(kwargs["pax_data"]["infants"])*fare.get("Total_Amount",0) -\
                  int(kwargs["pax_data"]["infants"])*(fare.get("Net_Commission",0))
    new_published_fare = supplier_published_fare + ((float(kwargs["fare_adjustment"]["markup"]))+(float(kwargs["fare_adjustment"]["distributor_markup"]))-\
                            float(kwargs["fare_adjustment"]["cashback"]) - float(kwargs["fare_adjustment"]["distributor_cashback"]))*total_pax_count
    new_offered_fare = supplier_published_fare + (float(kwargs["fare_adjustment"]["markup"]) + float(kwargs["fare_adjustment"]["distributor_markup"]) -\
        float(kwargs["fare_adjustment"]["cashback"])-float(kwargs["fare_adjustment"]["distributor_cashback"]))*total_pax_count -\
        (supplier_published_fare-supplier_offered_fare)*(float(kwargs["fare_adjustment"]["parting_percentage"])/100)*(float(kwargs["fare_adjustment"]["distributor_parting_percentage"])/100)*(1-float(kwargs["tax_condition"]["tax"])/100)
    discount = (new_published_fare-new_offered_fare)
    return {"offered_fare":round(float(new_offered_fare),2),"discount":round(float(discount),2),
            "publish_fare":round(float(new_published_fare),2),
            "supplier_published_fare":round(float(supplier_published_fare),2),
            "supplier_offered_fare":round(float(supplier_offered_fare),2)}

def get_unified_cabin_class(cabin_class):
    cabin_map = {2:"Economy",3:"PremiumEconomy",4:"Business Class",6:"First Class"}
    return cabin_map.get(cabin_class,"Economy")

def get_fareBreakdown(FareBreakdown,new_published_fare,passenger_data):
    passenger_data = {key: int(float(value)) for key, value in passenger_data.items()}
    total_pax_count = sum(list(map(int,list(passenger_data.values()))))
    FareBreakdownResults = []
    result_dict  = {}
    total_base_fare = 0
    for pax_data in FareBreakdown["FareDetails"]:
        if pax_data["PAX_Type"] == 0:
            result_dict["adults"] = {}
            result_dict["adults"]['passengerType'] = "adults"
            result_dict["adults"]['baseFare'] = pax_data["Basic_Amount"]
            total_base_fare += pax_data["Basic_Amount"]*passenger_data.get("adults",0)
        elif pax_data["PAX_Type"] == 1:
            result_dict["children"] = {}
            result_dict["children"]['passengerType'] = "children"
            result_dict["children"]['baseFare'] =  pax_data["Basic_Amount"]
            total_base_fare += pax_data["Basic_Amount"]*passenger_data.get("children",0)
        elif pax_data["PAX_Type"] == 2:
            result_dict["infants"] = {}
            result_dict["infants"]['passengerType'] = "infants"
            result_dict["infants"]['baseFare'] = pax_data["Basic_Amount"]
            total_base_fare += pax_data["Basic_Amount"]*passenger_data.get("infants",0)
    tax_per_pax = round((new_published_fare-total_base_fare)/total_pax_count,2)
    if "adults" in result_dict:
        result_dict["adults"]["tax"] = tax_per_pax
        FareBreakdownResults.append(result_dict["adults"])
    if "children" in result_dict:
        result_dict["children"]["tax"] = tax_per_pax
        FareBreakdownResults.append(result_dict["children"])
    if "infants" in result_dict:
        result_dict["infants"]["tax"] = tax_per_pax
        FareBreakdownResults.append(result_dict["infants"]) 
    return FareBreakdownResults

def dob_passport_date_correction(date):
    date_obj = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ')
    formatted_date = date_obj.strftime('%m/%d/%Y')
    return formatted_date

def find_original_baggage_ssr(baggages_ssr,ssr_response):
    try:
        result = []
        for x in baggages_ssr.keys():
            if len(baggages_ssr[x]) >0:
                result.append([y for y in ssr_response['Response']['Baggage'][0] if y['Weight'] == baggages_ssr[x][0]['Weight'] ][0])
    except:
        result = []
    return result

def modify_terminal_name(terminal):
    try:
        return terminal.split(" ")[-1]
    except:
        return terminal
    
def modify_arrival_departure_time(date):
    date_obj = datetime.strptime(date, '%m/%d/%Y %H:%M')
    formatted_date = date_obj.strftime('%Y-%m-%dT%H:%M')
    return formatted_date
