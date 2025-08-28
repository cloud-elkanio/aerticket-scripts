from vendors.flights.abstract.abstract_flight_manager import AbstractFlightManager
from vendors.flights.tripjack.api  import (flight_search,fare_rule,fare_quote,ssr,hold,seat_ssr,\
                                        ticket_book_api,ticket_booking_details_api,conform_holded_fare,conform_holded_book,\
                                        release_hold,get_cancellation_charges,cancel_ticket,check_cancellation_status,
                                        get_current_ticket_status)
from datetime import datetime,timedelta
from vendors.flights.utils import create_uuid,set_fare_details,create_segment_keys,invoke_email
from vendors.flights.finance_manager import FinanceManager
from common.models import (FlightBookingItineraryDetails,LookupEasyLinkSupplier,FlightBookingUnifiedDetails,
                        FlightBookingJourneyDetails,FlightBookingSSRDetails)
import concurrent.futures
import re
from datetime import datetime
import time
import json
import traceback as tb

class Manager(AbstractFlightManager):
    def __init__(self,data,uuid,mongo_client):
        self.vendor_id = "VEN-"+str(uuid)
        self.credentials = data
        self.mongo_client = mongo_client

    def name (self):
        return "TRIPJACK"
    
    def get_vendor_id(self):
        return self.vendor_id
    
    def get_cabin_class(self,cabin_class):
        cabin_map = {"Economy":"ECONOMY","Premium Economy":"PREMIUM_ECONOMY","Business Class":"BUSINESS","First Class":"FIRST"}
        return cabin_map.get(cabin_class,"ECONOMY")

    def get_vendor_journey_types(self,kwargs):
        if kwargs.get("journey_type","").upper() == "ROUND TRIP" and kwargs.get("flight_type","").upper() == "INT":
            return False
        else:
            return True
    
    def pax_modify(self,input_pax_data):
        return {"ADULT": str(input_pax_data["adults"]), "CHILD": str(input_pax_data["children"]), 
                "INFANT": str(input_pax_data["infants"])}
    
    def insert_ticket_response_mongo(self,fare_doc):
        try:
            self.mongo_client.searches.insert_one(fare_doc)
        except:
            pass
    
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
        journey_type = journey_details.get("journey_type")
        flight_type = journey_details.get("flight_type")
        pax_data = self.pax_modify(journey_details.get("passenger_details"))
        cabin_class = journey_details.get("cabin_class")
        segment_details = journey_details.get("journey_details")
        session_id = journey_details.get("session_id")
        cabin_class = self.get_cabin_class(journey_details.get("cabin_class",""))
        segment_keys = create_segment_keys(journey_details)
        fare_type = fare_type_mapping.get(journey_details.get("fare_type"),"Regular")
        book_filters = self.booking_filters({"journey_type":journey_type,"flight_type":flight_type,
                                             "supplier_id":str(self.vendor_id),"fare_type":journey_details.get("fare_type")})
        def process_segment(seg, index): 
            """Function to process each segment in a thread."""
            flight_search_response = flight_search(
                baseurl=self.credentials.get("base_url",""),
                apikey=self.credentials.get("apikey",""),
                journey_type=journey_type,
                pax_data=pax_data,
                segment_details=[seg],
                flight_type = flight_type,cabin_class = cabin_class,
                fare_type = fare_type,
                session_id = session_id,
                book_filters = book_filters
            )
            
            flight_search_response = self.add_uuid_to_segments(
                flight_search_response, flight_type, journey_type
            )
            return index, flight_search_response
        
        if (journey_type =="Round Trip" and flight_type ==  "DOM") or journey_details["journey_type"] == "Multi City" :
            def run_in_threads(segments, segment_keys):
                final = {}
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = {
                        executor.submit(process_segment, seg, index): index
                        for index, seg in enumerate(segments)
                    }
                    for future in concurrent.futures.as_completed(futures):
                        index, response = future.result()
                        final[segment_keys[index]] = response
                return final
            final_result = run_in_threads(segment_details, segment_keys)
            return {"data":final_result,"status":"success"}
        else:
            flight_search_response = flight_search(baseurl= self.credentials.get("base_url",""),apikey = self.credentials.get("apikey",""),flight_type = flight_type,
                                                    pax_data = pax_data,segment_details = segment_details, book_filters = book_filters,
                                                    journey_type = journey_type, cabin_class = cabin_class,fare_type = fare_type,session_id= session_id
                                                    )
            flight_search_response = self.add_uuid_to_segments(flight_search_response,flight_type,journey_type)
            return {"data":flight_search_response,"status":"success"}

    def get_updated_fare_details(self,index,segment_data, search_details,raw_data,raw_doc,
                                 currentfare,fare_details,session_id):
        try:
            pax_DOB = {}
            transaction_id = currentfare["transaction_id"] 
            fare_adjustment,tax_condition= set_fare_details(fare_details)
            segment_keys = create_segment_keys(search_details)
            if search_details["journey_type"] =="One Way" or  search_details["journey_type"] =="Multi City" or\
                (search_details["journey_type"] =="Round Trip" and search_details["flight_type"] == "DOM"):
                date = "".join(search_details["journey_details"][0]["travel_date"].split('-')[:2])
                flightSegment = segment_keys[index]
                segment_id = segment_data['segment_id']
                fare_id = segment_data['fare_id']
                fare_quote_response = fare_quote(baseurl=self.credentials.get("base_url",""),
                                                api_key=self.credentials.get("apikey",""),transaction_id = transaction_id,
                                                session_id = session_id)
                vendor_data = fare_quote_response       
                fareDetails = {}
                result = {}
                result['fare_id'] = fare_id
                calculated_fares = calculate_fares(fare_quote_response["totalPriceInfo"]["totalFareDetail"]["fC"],fare_adjustment,
                                                    tax_condition,search_details["passenger_details"],fare_quote = True)
                result["offeredFare"] = calculated_fares["offered_fare"]
                result["Discount"] = calculated_fares["discount"]
                result["publishedFare"] = calculated_fares["publish_fare"]
                result["supplier_publishFare"] = calculated_fares["supplier_published_fare"]
                result["supplier_offerFare"] = calculated_fares["supplier_offered_fare"]
                result['fareType'] = fare_quote_response["tripInfos"][0]["totalPriceList"][0].get("fareIdentifier","N/A")
                result['currency'] = "INR"
                result['colour'] = "Red"
                result['fareBreakdown'] = get_fareBreakdown(FareBreakdown = fare_quote_response["tripInfos"],fare_details = False,
                                                            pax_data = search_details["passenger_details"],
                                                            new_published_fare = calculated_fares["publish_fare"])
                result['isRefundable'] = bool(fare_quote_response["tripInfos"][0]["totalPriceList"][0]["fd"]["ADULT"].get("rT",0))
                fareDetails[flightSegment] = result
                unified_seg = {"itineraries":[flightSegment],flightSegment:[],"fareDetails":fareDetails}
                flight_legs = vendor_data["tripInfos"][0]
                IsPriceChanged = True if fare_quote_response.get("alerts") else False
                updated = True
                unified_structure = unify_seg_quote(flight_legs["sI"],flightSegment,flight_legs)
                unified_structure["segmentID"] = segment_id
                # calculated_fares = calculate_fares(flight_legs["totalPriceList"][0]["fd"],fare_adjustment,tax_condition,
                #                                     search_details["passenger_details"])
                # unified_structure["offerFare"] = calculated_fares["offered_fare"]
                # unified_structure["Discount"] = calculated_fares["discount"]
                # unified_structure["publishFare"] = calculated_fares["publish_fare"]
                # unified_structure["supplier_publishFare"] = calculated_fares["supplier_published_fare"]
                # unified_structure["supplier_offerFare"] = calculated_fares["supplier_offered_fare"]
                # unified_structure["currency"] = "INR" 
                unified_seg[flightSegment] = unified_structure
                if not fare_quote_response.get("conditions",{}).get("pcs",{}).get("dobe"):
                    pax_DOB["is_adultDOB"] = fare_quote_response.get("conditions",{}).get("dob",{}).get("adobr",False)
                    pax_DOB["is_childDOB"] = fare_quote_response.get("conditions",{}).get("dob",{}).get("cdobr",True)
                    pax_DOB["is_infantDOB"] = fare_quote_response.get("conditions",{}).get("dob",{}).get("idobr",True)
                else:
                    pax_DOB = {"is_adultDOB":True,"is_childDOB":True,"is_infantDOB":True}
                is_gst_mandatory = fare_quote_response.get("conditions",{}).get("gst",{}).get("igm",False)
                return {"updated":updated,"data":unified_seg,"raw":fare_quote_response,"IsPriceChanged":IsPriceChanged,
                        "status":"success",'frequent_flyer_number':True,"pax_DOB":pax_DOB,"is_gst_mandatory":is_gst_mandatory}\
                    if updated else {"updated":updated,"data":unified_seg,"close":True,"raw":fare_quote_response,
                                    "IsPriceChanged":IsPriceChanged,"status":"failure",'frequent_flyer_number':True,
                                    "pax_DOB":pax_DOB,"is_gst_mandatory":is_gst_mandatory}

            elif search_details["journey_type"] == "Round Trip" and search_details["flight_type"] == "INT":
                unified_seg = {}
                fs = []
                for journey_details in search_details['journey_details']:
                    date = "".join(journey_details["travel_date"].split('-')[:2])
                    flightSegment = journey_details["source_city"]+"_"+journey_details["destination_city"]+"_"+date
                    fs.append(flightSegment)
                flightSegment = "_R_".join(fs)
                fare_id = segment_data['fare_id']
                segment_id = segment_data['segment_id']
                fare_quote_response = fare_quote(baseurl=self.credentials.get("base_url",""),
                                                api_key=self.credentials.get("apikey",""),transaction_id = transaction_id,
                                                session_id = session_id)
                updated = True
                vendor_data = fare_quote_response
                fareDetails = {}
                result = {}
                result['fare_id'] = fare_id
                calculated_fares = calculate_fares(fare_quote_response["totalPriceInfo"]["totalFareDetail"]["fC"],fare_adjustment,
                                                    tax_condition,search_details["passenger_details"],fare_quote = True)
                result["offeredFare"] = calculated_fares["offered_fare"]
                result["Discount"] = calculated_fares["discount"]
                result["publishedFare"] = calculated_fares["publish_fare"]
                result["supplier_publishFare"] = calculated_fares["supplier_published_fare"]
                result["supplier_offerFare"] = calculated_fares["supplier_offered_fare"]
                result['fareType'] = fare_quote_response["tripInfos"][0]["totalPriceList"][0].get("fareIdentifier","N/A")
                result['currency'] = "INR"
                result['colour'] = "Peach"
                result['fareBreakdown'] = get_fareBreakdown(FareBreakdown = fare_quote_response["tripInfos"],fare_details = False,
                                                            pax_data = search_details["passenger_details"],
                                                            new_published_fare = calculated_fares["publish_fare"])
                result['isRefundable'] = bool(fare_quote_response["tripInfos"][0]["totalPriceList"][0]["fd"]["ADULT"].get("rT",0))
                IsPriceChanged = True if fare_quote_response.get("alerts") else False
                fareDetails[flightSegment] = result
                unified_seg = {"itineraries":[flightSegment],"fareDetails":fareDetails,flightSegment:{}}
                flight_legs = vendor_data["tripInfos"]
                out = {"flightSegments": {}}
                for trip in flight_legs:
                    unified_structure = unify_seg_quote(trip["sI"],flightSegment.split("_R_")[flight_legs.index(trip)],trip)
                    out['flightSegments'].update(unified_structure['flightSegments'])
                    unified_seg[flightSegment]["segmentID"] = segment_id
                    # calculated_fares = calculate_fares(trip["totalPriceList"][0]["fd"],fare_adjustment,tax_condition,
                    #                                     search_details["passenger_details"])
                    # unified_structure["offerFare"] = calculated_fares["offered_fare"]
                    # unified_structure["Discount"] = calculated_fares["discount"]
                    # unified_structure["publishFare"] = calculated_fares["publish_fare"]
                    # unified_structure["supplier_publishFare"] = calculated_fares["supplier_published_fare"]
                    # unified_structure["supplier_offerFare"] = calculated_fares["supplier_offered_fare"]
                    # unified_structure["currency"] = "INR"
                    unified_seg[flightSegment]['flightSegments'] = out['flightSegments']
                if not fare_quote_response.get("conditions",{}).get("pcs",{}).get("dobe"):
                    pax_DOB["is_adultDOB"] = fare_quote_response.get("conditions",{}).get("dob",{}).get("adobr",False)
                    pax_DOB["is_childDOB"] = fare_quote_response.get("conditions",{}).get("dob",{}).get("cdobr",True)
                    pax_DOB["is_infantDOB"] = fare_quote_response.get("conditions",{}).get("dob",{}).get("idobr",True)
                else:
                    pax_DOB = {"is_adultDOB":True,"is_childDOB":True,"is_infantDOB":True}
                is_gst_mandatory = fare_quote_response.get("conditions",{}).get("gst",{}).get("igm",False)
            else:
                updated = False    
            return {"updated":updated,"data":unified_seg,"raw":fare_quote_response,"IsPriceChanged":IsPriceChanged,
                    "status":"success",'frequent_flyer_number':True,"is_gst_mandatory":is_gst_mandatory}\
                if updated else {"updated":updated,"data":unified_seg,"close":True,"raw":fare_quote_response,
                                "IsPriceChanged":IsPriceChanged,"status":"failure",'frequent_flyer_number':True,
                                "is_gst_mandatory":is_gst_mandatory}
        except Exception as e:
            error = tb.format_exc()
            self.mongo_client.flight_supplier.insert_one({"vendor":"TripjackTBO","error":error,"type":"air_pricing",
                                                            "createdAt": datetime.now(),"session_id":session_id})
            return {"updated":False,"status":"failure","close":True,"IsPriceChanged":False,"raw":str(e)}
            
    def get_ssr(self, **kwargs):
        ssr_response_data_mongo = self.mongo_client.fetch_all_with_sessionid(session_id = kwargs["session_id"],
                                                                             type = "air_pricing")[0]
        ssr_response = ssr_response_data_mongo["fareQuote"][kwargs["segment_key"]]
        flight_ssr_response = {kwargs["segment_key"]:[]}
        ssr_response_data = ssr_response["tripInfos"]
        booking_id = ssr_response_data_mongo["fareQuote"][kwargs["segment_key"]]["bookingId"]
        session_id = kwargs["session_id"]
        seat_ssr_response = seat_ssr(baseurl = self.credentials.get("base_url",""),api_key = self.credentials.get("apikey",""),booking_id = booking_id,session_id = session_id)
        try:
            for ssr_index in range(len(ssr_response_data)):
                ssr_response_data_selected = ssr_response_data[ssr_index]["sI"]
                for ssr_info in ssr_response_data_selected:
                    sub_ssr = {}
                    try:
                        seats_ssr_data = seat_ssr_response["tripSeatMap"]["tripSeat"][ssr_info["id"]]["sInfo"]
                        seat_rows_num = seat_ssr_response["tripSeatMap"]["tripSeat"][ssr_info["id"]]["sData"]["row"]
                        seat_column_num = seat_ssr_response["tripSeatMap"]["tripSeat"][ssr_info["id"]]["sData"]["column"]
                        seatmap =  [{"row": row_number, "seats": [{"seatType":None} for col in range(1, seat_column_num+1)]} for row_number in range(1, seat_rows_num+1)]
                        seat_rows_data = {"seatmap":seatmap,
                                        "seat_data":{"row":seat_rows_num,"column":seat_column_num}}
                    except:
                        seats_ssr_data = {}
                    if ssr_info.get("ssrInfo"):
                        try:
                            if len(ssr_info["ssrInfo"].get('BAGGAGE',[]))>0:
                                sub_ssr["baggage_ssr"] = {"adults":[],"children":[]}
                                result = []  
                                for baggage in ssr_info["ssrInfo"]['BAGGAGE']:
                                    match = re.search(r"(\d+)\s*kg", baggage.get("desc",""), re.IGNORECASE)
                                    out = {}
                                    out["Code"] = baggage.get("code","")
                                    out["Unit"] = "KG" if match else ""
                                    out["Weight"] = int(match.group(1)) if match else baggage.get("desc","")
                                    out["Quantity"] = baggage.get("quantity",1)
                                    out["Price"] = baggage.get("amount",0)
                                    out['Description'] = baggage.get("desc","")
                                    result.append(out)
                                sub_ssr["baggage_ssr"]["adults"] = result
                                sub_ssr["baggage_ssr"]["children"] = result
                                sub_ssr["is_baggage"] = True
                                sub_ssr["Currency"]  = "INR"
                            else:
                                sub_ssr["baggage_ssr"] = {"adults":[],"children":[]}
                                sub_ssr["is_baggage"] = False
                        except:
                            sub_ssr["baggage_ssr"] = {"adults":[],"children":[]}
                            sub_ssr["is_baggage"] = False
                        try:
                            if len(ssr_info["ssrInfo"].get('MEAL',[])) >0:
                                result = []
                                sub_ssr["meals_ssr"] = {"adults":[],"children":[]}
                                for meal in ssr_info["ssrInfo"]['MEAL']:
                                    out = {}
                                    out["Code"] = meal.get("code","")
                                    out["Description"] = meal.get("desc","")
                                    out["Quantity"] = meal.get("quantity",1)
                                    out["Price"] = meal.get("amount",0)
                                    result.append(out)
                                sub_ssr["is_meals"] = True
                                sub_ssr["meals_ssr"]["adults"] = result
                                sub_ssr["meals_ssr"]["children"] = result
                                sub_ssr["Currency"]  = "INR"
                            else:
                                sub_ssr["meals_ssr"] = {"adults":[],"children":[]} 
                                sub_ssr["is_meals"] = False
                        except :
                            sub_ssr["is_meals"] = False
                            sub_ssr["meals_ssr"] = {"adults":[],"children":[]}
                    else:
                        sub_ssr = {
                                    "is_baggage": False,
                                    "Currency": "INR",
                                    "baggage_ssr":{"adults":[],"children":[]},
                                    "is_meals": False,
                                    "meals_ssr":{"adults":[],"children":[]}
                                    }
                    if seats_ssr_data:
                        try:
                            sub_ssr["seats_ssr"] = {"adults":{},"children":{}}
                            for seat_data in seats_ssr_data:
                                seat_info_dict = {}
                                column_num = seat_data.get("seatPosition")["column"]
                                row_num = seat_data["seatPosition"]["row"]
                                seat_info_dict["Code"] = seat_data.get("seatNo")
                                seat_info_dict["isBooked"] = seat_data.get("isBooked")
                                seat_info_dict["Price"] = seat_data.get("amount",0)
                                seat_info_dict["seatType"] = seat_data.get("seatType",1)
                                seat_info_dict["info"] = "Aisle Seat" if seat_data.get("isAisle")  else ""
                                seat_rows_data["seatmap"][row_num-1]["seats"][column_num-1] = seat_info_dict
                            sub_ssr["seats_ssr"]["adults"] = seat_rows_data
                            sub_ssr["seats_ssr"]["children"] = seat_rows_data
                            sub_ssr["is_seats"] = True
                        except:
                            sub_ssr["is_seats"] = False
                            sub_ssr["seats_ssr"] = {"adults":{},"children":{}}
                    else:
                        sub_ssr["is_seats"] = False
                        sub_ssr["seats_ssr"] = {"adults":{},"children":{}}
                    sub_ssr["journey_segment"] = ssr_info["da"]["code"] + "-" + ssr_info["aa"]["code"]
                    flight_ssr_response[kwargs["segment_key"]].append(sub_ssr)
        except Exception as e:
            sub_ssr = {
                    "is_baggage": False,
                    "Currency": "INR",
                    "baggage_ssr":{"adults":[],"children":[]},
                    "is_meals": False,
                    "meals_ssr":{"adults":[],"children":[]},
                    "is_seats": False,
                    "seats_ssr":{"adults":[],"children":[]},
                    "error":str(e)
                    }
            flight_ssr_response[kwargs["segment_key"]].append(sub_ssr)

        return {"data":flight_ssr_response} | {"raw":{"ssr":ssr_response,"seat_ssr":seat_ssr_response}}
    
    def generate_fare_rules_html(self,response, currency="INR"):
        try:
            fare_rule = response["fareRule"]
            route = list(fare_rule.keys())[0]
            rules = fare_rule[route]["fr"]
            mini_fare_rules = "" if "miscInfo" in fare_rule[route] else fare_rule[route]
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
            <body>
                <h1>Fare Rules for {route}</h1>
                <table>
                    <tr>
                        <th>Rule Type</th>
                        <th>Policy Information</th>
                        <th>Amount ({currency})</th>
                    </tr>
            """
            # Populate the table with rules
            for rule_type, rule_data in rules.items():
                default = rule_data.get("DEFAULT", {})
                policy_info = default.get("policyInfo", "N/A").replace("__nls__", "\n").strip()
                policy_parts = policy_info.split("\n")  # Split by colon for better readability
                amount = default.get("amount", 0.0)
                # Create HTML for policy information sections
                policy_html = "".join(
                    f"<div class='policy-section'>{part.strip()}</div>" for part in policy_parts
                )
                html += f"""
                    <tr>
                        <td>{rule_type.capitalize()}</td>
                        <td>{policy_html}</td>
                        <td class="amount">{currency} {amount}</td>
                    </tr>
                """
            # Closing the HTML structure
            html += """
                </table>
            </body>
            </html>
            """
            return html,mini_fare_rules
        except:
            return "No Fare Rules!"
    
    def get_fare_details(self,**kwargs):
        try:
            fare_adjustment,tax_condition = set_fare_details(kwargs.get("fare_details"))
            fareDetails = []
            sorted_price_list = self.sort_prices(kwargs["raw_data"]["totalPriceList"])
            first_flight_indices = [str(d.get("id",0)) for d in  kwargs["raw_data"]["sI"] if d.get("sN") == 0]
            session_id = kwargs.get("session_id")
            for Index,FD in enumerate(sorted_price_list):
                result = {}
                price_id = sorted_price_list[Index]["id"]
                result["baggage"] = get_default_baggage(sorted_price_list[Index],first_flight_indices)
                result['fare_id'] = create_uuid("FARE")
                result['segment_id'] = kwargs.get("segment_id")
                result['transaction_id'] = sorted_price_list[Index]["id"]
                calculated_fares = calculate_fares(sorted_price_list[Index]["fd"],fare_adjustment,
                                                tax_condition,kwargs.get("master_doc").get("passenger_details"))
                result['publishedFare'] = calculated_fares["publish_fare"]
                result['offeredFare'] = calculated_fares["offered_fare"]
                result["Discount"] = calculated_fares["discount"]
                result['vendor_id'] = self.vendor_id.split("VEN-")[-1]
                result['fareType'] = sorted_price_list[Index]["fareIdentifier"]
                result['uiName'] = sorted_price_list[Index]["fareIdentifier"]
                result['currency'] = "INR"
                result['colour'] = "RED"
                result['fareBreakdown'] = get_fareBreakdown(FareBreakdown = sorted_price_list[Index]["fd"],fare_details = True,
                                                            pax_data = kwargs["master_doc"]["passenger_details"],
                                                            new_published_fare = calculated_fares["publish_fare"])
                
                result['isRefundable'] = bool(sorted_price_list[Index]["fd"]["ADULT"].get("rT",0))
                result['IsFreeMealAvailable'] = sorted_price_list[Index]["fd"]["ADULT"].get('IsFreeMealAvailable',False)
                result["misc"] = {result['fare_id']:price_id}
                fareDetails.append(result)
            return fareDetails,"success"
        except:
            error = tb.format_exc()
            self.mongo_client.flight_supplier.insert_one({"vendor":"Tripjack","error":error,"type":"get_fare_details",
                                                            "createdAt": datetime.now(),"session_id":session_id})
            return [],"failure" 
            
    def sort_prices(self,price_list):
        try:
            for price_data in price_list:
                sorted_offer_fare = 0
                for pax_type in price_data.get("fd",{}):
                    sorted_offer_fare = sorted_offer_fare + price_data["fd"][pax_type].get("fC",{}).get("NF",0)
                price_data["sorted_offer_fare"] = sorted_offer_fare 
            sorted_price_list = sorted(price_list, key = lambda x: x["sorted_offer_fare"])
            return sorted_price_list
        except:
            return price_list

    def hold_booking(self,**kwargs):
        itinerary = kwargs["itinerary"]
        booking = kwargs["booking"]
        try:
            booking_dict = booking.__dict__
            pax_details = kwargs["pax_details"]
            flight_booking_unified_data = FlightBookingUnifiedDetails.objects.filter(itinerary = itinerary.id).first()
            fare_quote = flight_booking_unified_data.fare_quote[itinerary.itinerary_key]
            ssr_response_itinerary = flight_booking_unified_data.ssr_raw[itinerary.itinerary_key]
            bookingId = ssr_response_itinerary["ssr"]["bookingId"]
            is_gst_mandatory = fare_quote.get("conditions",{}).get("gst",{}).get("igm",False)
            travellerInfo = []        
            email = json.loads(booking_dict["contact"])["email"]
            phone = json.loads(booking_dict["contact"])["phone"]
            gst_details = json.loads(booking_dict["gst_details"])
            payload = {"bookingId":bookingId}
            if gst_details and is_gst_mandatory:
                payload["gstInfo"] = {
                    "gstNumber": gst_details.get("gstNumber",""),
                    "email": gst_details.get("email", ""),
                    "registeredName": gst_details.get("name",""),
                    "mobile": str(gst_details.get("phone",""))[-10:],
                    "address": gst_details.get("address","")
                }
            payload["deliveryInfo"] =  {"emails": [email],"contacts": [phone]}
            for  pax in pax_details:
                passenger = {}
                passenger["ti"] = self.passenger_title_creation(gender = pax.gender,title = pax.title,
                                                                pax_type = pax.pax_type)
                passenger["fN"] = pax.first_name
                passenger["lN"] = pax.last_name
                passenger["pt"] = pax_type_mapping.get(pax.pax_type, 1)
                if pax.dob:
                    passenger["dob"] = self.date_format_correction(pax.dob)
                if pax.passport:
                    passenger["pNum"] = pax.passport
                    passenger["eD"] = self.date_format_correction(pax.passport_expiry)
                    passenger["pNat"] = pax.passport_issue_country_code
                    passenger["pid"] = self.date_format_correction(pax.passport_issue_date)
                ffn = pax.frequent_flyer_number.get(itinerary.itinerary_key,{})
                if ffn:
                    if ffn.get("frequent_flyer_number","").strip():
                        passenger["ff"] = {ffn.get("airline_code",""):ffn.get("frequent_flyer_number","")}
                travellerInfo.append(passenger)
            payload["travellerInfo"]  = travellerInfo
            itinerary.status = "Hold-Initiated"
            itinerary.save(update_fields=["status"])
            session_id = booking_dict.get("session_id")
            book_response = hold(baseurl = self.credentials.get("base_url",""),api_key = self.credentials.get("apikey",""),
                                payload = payload,session_id = session_id)
            if book_response.get('status'):
                ticket_booking_details = ticket_booking_details_api(baseurl = self.credentials.get("base_url",""),
                                                                    api_key = self.credentials.get("apikey",""), booking_id = bookingId,
                                                                    session_id = session_id)
                if ticket_booking_details.get("status"):
                    ticket_status = ticket_booking_details.get("data",{}).get("order",{}).get("status","").upper()
                    if ticket_status not in ["FAILED","ABORTED"]:   
                        itinerary.airline_pnr,itinerary.gds_pnr = self.find_pnrs(ticket_booking_details["data"])
                        if itinerary.airline_pnr:
                            hold_error = ""
                            itinerary.status = "On-Hold"
                        else:
                            hold_error = "PNR not available!"
                            itinerary.status = "Hold-Failed"
                        misc = {"booking_id":bookingId,"booking_detail":ticket_booking_details}
                        itinerary.misc =  json.dumps(misc)
                        itinerary.supplier_booking_id = bookingId
                        itinerary.soft_fail = False
                        itinerary.modified_at = int(time.time())
                        itinerary.hold_till = ticket_booking_details.get("data",{}).get("itemInfos",{}).get("AIR",{}).get("timeLimit","N/A")
                        itinerary.save(update_fields=["airline_pnr","status", "supplier_booking_id","misc","modified_at",
                                                    "hold_till","soft_fail","gds_pnr"])
                        hold_booking_output = {"success": True}
                    else:
                        itinerary.status = "Hold-Failed"
                        itinerary.soft_fail = False 
                        itinerary.modified_at = int(time.time())
                        itinerary.error = "Hold Aborted/Failed from supplier side"
                        misc = {"booking_id":bookingId,"booking_detail":ticket_booking_details}
                        itinerary.supplier_booking_id = bookingId
                        itinerary.save(update_fields=["status","misc","modified_at","error","soft_fail",
                                                    "supplier_booking_id"])
                        hold_booking_output = {"status":False}
                else:
                    itinerary.status = "Hold-Failed"
                    itinerary.error = "Ticket details pending from supplier"
                    itinerary.soft_fail = True if ticket_booking_details.get("status_code") == 504 else False
                    itinerary.supplier_booking_id = bookingId
                    itinerary.modified_at = int(time.time())
                    itinerary.misc =  json.dumps({"booking_id":bookingId,"booking_detail":{}})
                    itinerary.save(update_fields=["status","error","modified_at","soft_fail","supplier_booking_id","misc"])
                    hold_booking_output = {"status":True if ticket_booking_details.get("status_code") == 504 else False}                     
            else:
                itinerary.save(update_fields=["status","misc"])
                try:
                    hold_error = book_response["data"]["errors"][0]["message"]
                except:
                    hold_error = "Hold booking Failed from supplier side!"
                misc = {"booking_id":bookingId,"booking_detail":book_response.get("data",{})}
                itinerary.status = "Hold-Failed"
                itinerary.misc =  json.dumps(misc)
                itinerary.error = hold_error
                itinerary.modified_at = int(time.time())
                itinerary.supplier_booking_id = bookingId
                itinerary.save(update_fields=["error","status","misc","modified_at","supplier_booking_id"])
                hold_booking_output = {"success": False}
            return hold_booking_output
        except Exception as e:
            error_trace = tb.format_exc()
            error_log = {"vendor":self.name(),"session_id":booking.session_id,"status":"failure","api":"hold_error",
                          "createdAt": datetime.now(),"error":str(e),"error_trace":error_trace}
            self.mongo_client.flight_supplier.insert_one(error_log)
            itinerary.status = "Hold-Failed"
            itinerary.error = "Hold Failed"
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["error","status","modified_at"])
            return{"status":False}

    def add_uuid_to_segments(self,vendor_data,flight_type,journey_type):
        if vendor_data:
            if vendor_data.get("searchResult"):
                if journey_type =="One Way" or  journey_type  == "Multi City" or \
                    (journey_type == "Round Trip" and flight_type == "DOM"):
                    segments = vendor_data["searchResult"]["tripInfos"]["ONWARD"]
                    for segment in segments:
                        seg = str(self.vendor_id)+"_$_"+create_uuid("SEG")
                        segment["segmentID"] = seg
                            
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
            segments = vendor_data["searchResult"]["tripInfos"]["ONWARD"]
            for segment in segments:
                if segment["segmentID"] == segment_id:
                    return segment
        elif (journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "DOM") \
             or journey_details["journey_type"] == "Multi City":
            segment_keys = create_segment_keys(journey_details)
            for segment_key in segment_keys:
                segments = vendor_data[segment_key]["searchResult"]["tripInfos"]
                for trip_type in segments:
                    for segment in segments[trip_type]:
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
            return {
                "is_hold":fare_quote["conditions"]["isBA"],
                "is_hold_ssr":False,
                "info":"Additional Services will not be applicable for Hold Booking!"}
        except:
            return {
                "is_hold":False,
                "is_hold_ssr":False}

    def get_fare_rule(self,**kwargs):
        try:
            session_id = kwargs["session_id"]
            fare_id = kwargs["fare_id"]
            fares = kwargs["fares"]
            fare_rules = "No Fare Rule Available"
            is_fare_rule = False
            mini_fare_rule = ""
            for vendor_fare  in fares:
                for fare_detail in vendor_fare["fareDetails"]:
                    if fare_id == fare_detail["fare_id"]:
                        price_id = vendor_fare["misc"][fare_id]
                        fare_rule_response = fare_rule(baseurl = self.credentials.get("base_url",""),apikey=self.credentials.get("apikey",""),
                                                    fare_id = price_id,session_id= session_id)
                        if fare_rule_response !=None:
                            fare_rules,mini_fare_rule = self.generate_fare_rules_html(fare_rule_response, currency="INR")
                        is_fare_rule = True
                        break
                if is_fare_rule:
                    break
            return fare_rules,mini_fare_rule
        except:
            return "No Fare Rule Available",""
        
    def get_repricing(self,**kwargs):
        itinerary: FlightBookingItineraryDetails  = kwargs["itinerary"]
        misc = json.loads(itinerary.misc)
        is_holded_fare = conform_holded_fare(baseurl = self.credentials.get("base_url",""),
                                            api_key = self.credentials.get("apikey",""), booking_id = misc["booking_id"])
        if is_holded_fare["status"] == True:
            total_fare = misc["booking_detail"]["data"]["itemInfos"]["AIR"]["totalPriceInfo"]["totalFareDetail"]["fC"]["TF"]
            return {"is_fare_change": False,"new_fare":total_fare,"old_fare":total_fare,"is_hold_continue":True}
        else:
            error = is_holded_fare["data"]["errors"][0]["message"]
            self.mongo_client.searches.update_one(
                    {'itinerary_id': str(itinerary.id),"type":"hold"}, 
                    {'$set': {'error': error,"hold":is_holded_fare["data"]}} 
                )
            return{"is_fare_change": False,"new_fare":None,"old_fare":None,"is_hold_continue":False,"error":error}

    def convert_hold_to_ticket(self,**kwargs):
        itinerary = kwargs["itinerary"]
        booking = kwargs["booking"]
        try:
            misc = json.loads(itinerary.misc)
            booking_id = misc["booking_id"]
            display_id = booking.display_id
            name = booking.user.first_name + booking.user.last_name
            supplier_id = self.credentials.get("supplier_id","")
            total_fare = misc["booking_detail"]["data"]["itemInfos"]["AIR"]["totalPriceInfo"]["totalFareDetail"]["fC"]["TF"]
            itinerary.status = "Ticketing-Initiated"
            itinerary.save(update_fields = ["status"])
            session_id = booking.session_id
            flight_booking_unified_data = FlightBookingUnifiedDetails.objects.filter(itinerary = itinerary.id).first()
            fare_quote = flight_booking_unified_data.fare_quote[itinerary.itinerary_key]
            isLCC_flight = self.is_lcc_flight(fare_quote)
            holded_booking_fare_response = conform_holded_fare(baseurl = self.credentials.get("base_url",""),
                                                api_key = self.credentials.get("apikey",""), booking_id = booking_id,
                                                price = total_fare,session_id = session_id)
            if holded_booking_fare_response.get("status"):
                hold_booking_confirm_response = conform_holded_book(baseurl = self.credentials.get("base_url",""),
                                                api_key = self.credentials.get("apikey",""), booking_id = booking_id,
                                                price = total_fare,session_id = session_id)
                if hold_booking_confirm_response.get("status"):
                    ticket_booking_details = ticket_booking_details_api(baseurl = self.credentials.get("base_url",""),
                                                                    api_key = self.credentials.get("apikey",""), booking_id = booking_id,
                                                                    session_id = session_id)
                    if ticket_booking_details.get("status"):
                        ticket_status = ticket_booking_details.get("data",{}).get("order",{}).get("status","").upper()
                        airline_pnr,gds_pnr = self.find_pnrs(ticket_booking_details["data"])
                        if ticket_status not in ["FAILED","ABORTED"]:                        
                            if airline_pnr:
                                itinerary.status = "Confirmed"
                                to_easylink = True
                                itinerary.soft_fail = False
                                itinerary.error = ""
                                for pax_ssr in kwargs["ssr_details"].filter(itinerary = itinerary):
                                    passenger_response = ticket_booking_details.get("data",{}).get("itemInfos",{}).get("AIR",{}).get("travellerInfos",[])
                                    first_name = pax_ssr.pax.first_name
                                    last_name = pax_ssr.pax.last_name
                                    for pax_data_response in passenger_response:
                                        if pax_data_response.get("fN") == first_name and pax_data_response.get("lN") == last_name:
                                            ticket_number = self.find_ticket_num(pax_data_response.get("ticketNumberDetails",{}))
                                            if ticket_number:
                                                pax_ssr.supplier_ticket_number = ticket_number
                                                pax_ssr.save()
                                            else:
                                                if not isLCC_flight:
                                                    itinerary.status = "Ticketing-Failed"
                                                    itinerary.error = "Ticket number not available"
                                                    itinerary.soft_fail = True
                                                    to_easylink = False
                                                else:
                                                    itinerary.status = "Confirmed"
                                                    itinerary.soft_fail = False
                                try:
                                    if to_easylink:
                                        finance_manager = FinanceManager(booking.user)
                                        finance_manager.book_tripjack(booking_data = ticket_booking_details["data"], display_id = display_id,
                                                                    name = name,
                                                                    supplier_id = supplier_id,itinerary = itinerary)
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
                                itinerary.modified_at = int(time.time())
                                itinerary.save(update_fields=["status","error","modified_at","soft_fail"])
                                response = {"status" : True}
                            else:
                                itinerary.status = "Ticketing-Failed"
                                itinerary.error = "PNR not available"
                                itinerary.modified_at = int(time.time())
                                itinerary.save(update_fields=["status","error","modified_at"])
                                response = {"status" : False}
                        else:
                            itinerary.airline_pnr = "airline_pnr"
                            itinerary.status = "Ticketing-Failed"
                            itinerary.soft_fail = False 
                            itinerary.modified_at = int(time.time())
                            itinerary.error = "Ticket Aborted/Failed from supplier side"
                            misc = {"booking_id":booking_id,"booking_detail":ticket_booking_details}
                            itinerary.supplier_booking_id = booking_id
                            itinerary.save(update_fields=["status","misc","modified_at","error","soft_fail",
                                                        "supplier_booking_id","airline_pnr"])
                            response = {"status":False}
                    else:
                        itinerary.status = "Ticketing-Failed"
                        itinerary.error = "Ticket details pending from supplier"
                        itinerary.soft_fail = True if ticket_booking_details.get("status_code") == 504 else False
                        itinerary.modified_at = int(time.time())
                        itinerary.save(update_fields=["status","error","modified_at","soft_fail"])
                        response = {"status":True if ticket_booking_details.get("status_code") == 504 else False}  
                else:
                    try:
                        error = hold_booking_confirm_response["data"]["errors"][0]["message"]
                    except:
                        error = "Hold to Ticket Failed from supplier side!"
                    itinerary.status = "Ticketing-Failed"
                    itinerary.error = error
                    itinerary.modified_at = int(time.time())
                    itinerary.save(update_fields=["status","error","modified_at"])
                    response = {"status" : False}
            else:
                try:
                    error = holded_booking_fare_response["data"]["errors"][0]["message"]
                except:
                    error = "Hold to Ticket Failed from supplier side!"
                self.mongo_client.searches.update_one(
                        {'itinerary_id': str(itinerary.id),"type":"book"}, 
                        {'$set': {'error': error,"book":holded_booking_fare_response.get("data")}} 
                    )
                itinerary.status = "Ticketing-Failed"
                itinerary.error = error
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","error","modified_at"])
                response = {"status" : False}
            return response
        except Exception as e:
            error_trace = tb.format_exc()
            invoke_log = {"vendor":self.name(),"session_id":booking.session_id,"status":"failure","api":"convert_hold_to_ticket_error",
                          "createdAt": datetime.now(),"error":str(e),"error_trace":error_trace}
            self.mongo_client.flight_supplier.insert_one(invoke_log)
            itinerary.status = "Ticketing-Failed"
            itinerary.error = "Hold to Ticket Failed"
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["status","error","modified_at"])
            return {"status" : False}

    def release_hold(self,**kwargs):
        itinerary = kwargs["itinerary"]
        session_id = itinerary.booking.session_id
        misc = json.loads(itinerary.misc)
        airline_pnrs,_ = self.find_pnrs(misc["booking_detail"]["data"])
        booking_id = misc["booking_id"]
        itinerary.status = "Release-Hold-Initiated"
        itinerary.save(update_fields=["status"])
        continue_release = misc["booking_detail"]["data"]["order"]["status"]
        if continue_release == "ON_HOLD":
            release_hold_response = release_hold(baseurl = self.credentials.get("base_url",""),
                                                api_key = self.credentials.get("apikey",""), booking_id = booking_id,
                                                pnrs = airline_pnrs,session_id = session_id)
            if release_hold_response["status"] == True :
                itinerary.status = "Hold-Released"
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at"])
                return { "itinerary_id": str(itinerary.id),"status": "success", "cancellation_status":"Ticket-Released",
                        "info":"Successfully released your booking" }
            else:
                try:
                    info = release_hold_response["data"]["errors"][0]["message"]
                except:
                    info = "Failed to release PNR"
                itinerary.status = "Release-Hold-Failed"
                itinerary.error = info
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["error","status","modified_at"])
                return { "itinerary_id": str(itinerary.id),"status": "failure","info":info, 
                        "cancellation_status":"Cancel-Ticket-Failed" }
        else:
            itinerary.status = "Release-Hold-Failed"
            itinerary.error = "Failed to cancel PNR"
            itinerary.save(update_fields=["error","status"])
            return { "itinerary_id": str(itinerary.id),"status": "failure","info":"Release-Hold-Failed",
                     "cancellation_status":"Cancel-Ticket-Failed" }

    def cancel_ticket(self,kwargs):
        itinerary = kwargs["itinerary"]
        session_id = itinerary.booking.session_id
        try:
            pax_ids = kwargs["pax_ids"]
            ssr_details_all_pax = itinerary.flightbookingssrdetails_set.all()
            ssr_details_pax_wise = [ssr for ssr in ssr_details_all_pax if str(ssr.pax_id) in pax_ids]
            journey_details = itinerary.flightbookingjourneydetails_set.all()
            misc = json.loads(itinerary.misc)
            booking_id = misc["booking_id"]
            itinerary.status = "Cancel-Ticket-Initiated"
            itinerary.save(update_fields=["status"])
            ssr_details_pax_wise_name = [name.pax.first_name + " " +  name.pax.last_name for name in ssr_details_pax_wise]
            trips = []
            cancellation_fee_dict = {}
            if len(pax_ids) == len(ssr_details_all_pax):
                cancel_ticket_response = cancel_ticket(baseurl = self.credentials.get("base_url",""),remarks = kwargs["remarks"],
                                                        api_key = self.credentials.get("apikey",""), booking_id = booking_id,
                                                        is_full_trip = True, trips = [],session_id = session_id)
            else:
                for journey in journey_details:
                    if journey.itinerary_id == itinerary.id:
                        cancel_dict = {}
                        travellers = []
                        cancel_dict["src"] = journey.source.upper()
                        cancel_dict["dest"] = journey.destination.upper()
                        cancel_dict["departureDate"] = datetime.strptime(journey.date, "%d-%m-%Y").strftime("%Y-%m-%d")
                        for pax_id in pax_ids:
                            fn = [passenger.pax.first_name for passenger in ssr_details_pax_wise if str(passenger.pax_id) == pax_id][0]
                            ln = [passenger.pax.last_name for passenger in ssr_details_pax_wise if str(passenger.pax_id) == pax_id][0]
                            travellers.append({"fn":fn,"ln":ln})
                            cancel_dict["travellers"] = travellers
                        trips.append(cancel_dict)
                cancel_ticket_response = cancel_ticket(baseurl = self.credentials.get("base_url",""),remarks = kwargs["remarks"],
                                                        api_key = self.credentials.get("apikey",""), booking_id = booking_id,
                                                        is_full_trip = False, trips = trips,session_id = session_id)
            if cancel_ticket_response["status"] == True:
                cancellation_data = misc.get("cancellation_data",{})
                amendmentId = cancel_ticket_response["data"].get("amendmentId","")
                cancellation_data = {**cancellation_data,**{amendmentId : pax_ids}}
                misc["cancellation_data"] = cancellation_data
                cancellation_status = check_cancellation_status(baseurl = self.credentials.get("base_url",""),
                                                    api_key = self.credentials.get("apikey",""), 
                                                    amendmentId = amendmentId, session_id = session_id)
                cancellation_status_tripjack = cancellation_status["data"]["amendmentStatus"].upper()
                for passenger_ssr in ssr_details_pax_wise:
                    if str(passenger_ssr.pax_id) in pax_ids:
                        passenger_ssr.cancellation_status = "CANCELLATION " + cancellation_status_tripjack if cancellation_status_tripjack != "SUCCESS" \
                                                            else "Cancelled"
                        passenger_ssr.save()
                        cancelled_pax_name =  passenger_ssr.pax.first_name + " " +  passenger_ssr.pax.last_name
                        cancellation_pax_fee = passenger_ssr.cancellation_fee
                        cancellation_fee_dict[cancelled_pax_name] = cancellation_pax_fee
                if cancellation_status_tripjack == "SUCCESS":
                    try:
                        easy_link_data = self.mongo_client.vendors.find_one({"type":"easy_link","itinerary_id":str(itinerary.id)})
                        if easy_link_data:
                            refund_manager = FinanceManager(itinerary.booking.user)
                            refund_manager.process_easylink_refund(payload = easy_link_data["payload_json"],cancellation_fee_dict = cancellation_fee_dict,
                                                                pax_names = ssr_details_pax_wise_name)
                    except Exception as e:
                        error_trace = tb.format_exc()
                        easylink_error_log = {"display_id":itinerary.booking.display_id,
                                "error":str(e),
                                "error_trace":error_trace,
                                "type":"easy_link"}
                        self.mongo_client.vendors.insert_one(easylink_error_log)
                cancellation_statuses = FlightBookingSSRDetails.objects.filter(itinerary_id = itinerary.id).values_list("cancellation_status", flat = True)
                if all(cancellation_status == "Cancelled" for cancellation_status in cancellation_statuses):
                    itinerary.status = "Ticket-Released"
                else:
                    itinerary.status = "Confirmed"
                itinerary.modified_at = int(time.time())
                itinerary.misc = json.dumps(misc)
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at","misc"])
                return { "status": "success", 
                        "info":"Successfully submitted your cancellation Request"}
            else:
                itinerary.status = "Cancel-Ticket-Failed"
                try:
                    error = cancel_ticket_response["data"]["errors"][0]["message"]
                except:
                    error = "Failed to cancel Ticket"
                itinerary.error = error
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","error","modified_at"])
                return { "status": "failure","info":error}
        except Exception as e:
            error_trace = tb.format_exc()
            error_log = {"vendor":self.name(),"session_id":session_id,"status":"failure","api":"cancel_ticket_error",
                          "createdAt": datetime.now(),"error":str(e),"error_trace":error_trace}
            self.mongo_client.flight_supplier.insert_one(error_log)
            return { "status": "failure","info":"Cancel Ticket Failed"}
        
    def check_cancellation_status(self,itinerary):
        session_id = itinerary.booking.session_id
        try:
            misc = json.loads(itinerary.misc)
            for amendmentid,pax_ids in misc.get("cancellation_data",[]).items():
                cancellation_fee_dict = {}
                ssr_details_pax_wise_name = []
                cancellation_status = check_cancellation_status(baseurl = self.credentials.get("base_url",""),
                                            api_key = self.credentials.get("apikey",""), 
                                                amendmentId = amendmentid, session_id = session_id)
                if cancellation_status["status"]:
                    cancellation_status_tripjack = cancellation_status["data"]["amendmentStatus"].upper()
                    cancellation_status_local = "Cancelled" if cancellation_status_tripjack == "SUCCESS" else "CANCELLATION " + cancellation_status_tripjack
                    pax_ssr = FlightBookingSSRDetails.objects.filter(itinerary_id = itinerary.id,pax_id__in = pax_ids)
                    pax_ssr.update(cancellation_status = cancellation_status_local)
                    for pax_info in pax_ssr:
                        cancelled_pax_name =  pax_info.pax.first_name + " " +  pax_info.pax.last_name
                        cancellation_pax_fee = pax_info.cancellation_fee
                        cancellation_fee_dict[cancelled_pax_name] = cancellation_pax_fee
                        ssr_details_pax_wise_name.append(cancelled_pax_name)
                    if cancellation_status_tripjack == "SUCCESS":
                        try:
                            easy_link_data = self.mongo_client.vendors.find_one({"type":"easy_link","itinerary_id":str(itinerary.id)})
                            if easy_link_data:
                                refund_manager = FinanceManager(itinerary.booking.user)
                                refund_manager.process_easylink_refund(payload = easy_link_data["payload_json"],cancellation_fee_dict = cancellation_fee_dict,
                                                                    pax_names = ssr_details_pax_wise_name)
                        except Exception as e:
                            error_trace = tb.format_exc()
                            easylink_error_log = {"display_id":itinerary.booking.display_id,
                                    "error":str(e),
                                    "error_trace":error_trace,
                                    "type":"easy_link"}
                            self.mongo_client.vendors.insert_one(easylink_error_log)
            cancellation_statuses = FlightBookingSSRDetails.objects.filter(itinerary_id = itinerary.id).values_list("cancellation_status", flat = True)
            if all(cancellation_status == "Cancelled" for cancellation_status in cancellation_statuses):
                itinerary.status = "Ticket-Released"
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at"])
            return {"status":"success"}     
        except Exception as e:
            error_trace = tb.format_exc()
            error_log = {"vendor":self.name(),"session_id":session_id,"status":"failure","api":"check_cancellation_status_error",
                          "createdAt": datetime.now(),"error":str(e),"error_trace":error_trace}
            self.mongo_client.flight_supplier.insert_one(error_log)
            return {"status":"failure","info":"The cancellation status is currently unavailable!"}
        
    def cancellation_charges(self,**kwargs):
        itinerary = kwargs["itinerary"]
        session_id = itinerary.booking.session_id
        try:
            pax_types = []
            total_additional_charge = float(kwargs.get("additional_charge",0))
            misc = json.loads(itinerary.misc)
            booking_id = misc["booking_id"]
            pax_data = kwargs["pax_data"]
            pax_ids = kwargs["pax_ids"]
            org_fare_details = kwargs["fare_details"]
            total_cancellation_charge = 0
            total_refund_amount = 0
            per_pax_additional_charge = round(total_additional_charge/len(pax_data),2)
            per_pax_cancellation_charge = round(float(org_fare_details.get("fare",{}).get("cancellation_charges",0)) \
                                            + float(org_fare_details.get("fare",{}).get("distributor_cancellation_charges",0)),2)
            trips = []
            journey_details = kwargs["journey_details"]
            if len(pax_data) == len(pax_ids):
                is_full_trip = True
                cancellation_charges = get_cancellation_charges(baseurl = self.credentials.get("base_url",""),
                                                    api_key = self.credentials.get("apikey",""), booking_id = booking_id,
                                                    is_full_trip = is_full_trip , trips = [],session_id = session_id)
            else:
                is_full_trip = False
                for journey in journey_details:
                    if journey.itinerary_id == itinerary.id:
                        cancel_dict = {}
                        travellers = []
                        cancel_dict["src"] = journey.source.upper()
                        cancel_dict["dest"] = journey.destination.upper()
                        cancel_dict["departureDate"] = datetime.strptime(journey.date, "%d-%m-%Y").strftime("%Y-%m-%d")
                        for pax_id in pax_ids:
                            fn = [name.first_name for name in pax_data if str(name.id) == pax_id][0]
                            ln = [name.last_name for name in pax_data if str(name.id)== pax_id][0]
                            pax_types.append([pax.pax_type for pax in pax_data if str(pax.id) == pax_id][0])
                            travellers.append({"fn":fn,"ln":ln})
                            cancel_dict["travellers"] = travellers
                        trips.append(cancel_dict)           
                cancellation_charges = get_cancellation_charges(baseurl = self.credentials.get("base_url",""),
                                            api_key = self.credentials.get("apikey",""), booking_id = booking_id,
                                            is_full_trip = is_full_trip , trips = trips,session_id = session_id)
            if cancellation_charges["status"] == True:
                for trip in cancellation_charges["data"]["trips"]:
                    adult_cancellation_amount = trip["amendmentInfo"].get("ADULT",{}).get("amendmentCharges",0)
                    child_cancellation_amount = trip["amendmentInfo"].get("CHILD",{}).get("amendmentCharges",0)
                    infant_cancellation_amount = trip["amendmentInfo"].get("INFANT",{}).get("amendmentCharges",0)
                    adult_refund_amount = trip["amendmentInfo"].get("ADULT",{}).get("refundAmount",0)
                    child_refund_amount = trip["amendmentInfo"].get("CHILD",{}).get("refundAmount",0)
                    infant_refund_amount = trip["amendmentInfo"].get("INFANT",{}).get("refundAmount",0)
                for pax_id in pax_ids:
                    pax_charge_ssr = FlightBookingSSRDetails.objects.filter(itinerary_id = itinerary.id,pax_id = pax_id).first()
                    customer_cancellation_charge = per_pax_additional_charge + per_pax_cancellation_charge
                    if pax_charge_ssr.pax.pax_type == "adults":
                        supplier_cancellation_charge = adult_cancellation_amount
                        supplier_refund_amount = adult_refund_amount
                    elif pax_charge_ssr.pax.pax_type == "child":   
                        supplier_cancellation_charge = child_cancellation_amount
                        supplier_refund_amount = child_refund_amount
                    else:
                        supplier_cancellation_charge = infant_cancellation_amount
                        supplier_refund_amount = infant_refund_amount
                    cancellation_fee_per_pax = {"supplier_cancellation_charge":supplier_cancellation_charge,
                                                "customer_cancellation_charge":customer_cancellation_charge + supplier_cancellation_charge}
                    pax_charge_ssr.cancellation_fee = cancellation_fee_per_pax
                    pax_charge_ssr.save(update_fields = ["cancellation_fee"])
                    total_cancellation_charge += supplier_cancellation_charge + customer_cancellation_charge
                    total_refund_amount += supplier_refund_amount
                return { "status": "success","refund_amount":total_refund_amount,
                        "cancellation_charge": total_cancellation_charge, "currency":"₹" }
            else:
                try:
                    error = cancellation_charges["data"]["errors"][0]["message"]
                except:
                    error = "Ticket Cancellation charges not available!"
                return {"status": "failure","info":error, "currency":"₹"}
        except Exception as e:
            error_trace = tb.format_exc()
            error_log = {"vendor":self.name(),"session_id":session_id,"status":"failure","api":"cancellation_charges_error",
                          "createdAt": datetime.now(),"error":str(e),"error_trace":error_trace}
            self.mongo_client.flight_supplier.insert_one(error_log)
            return {"status":"failure","info":"Ticket Cancellation charges not available!","currency":"₹"}
        
    def find_pnrs(self,api_response):
        airline_pnr = ""
        gds_pnr = ""
        try:
            pnr_list = list(set(api_response["itemInfos"]["AIR"]["travellerInfos"][0]["pnrDetails"].values()))
            if len(pnr_list) == 1:
                airline_pnr = pnr_list[0]
            else:
                airline_pnr = "_$_".join(pnr_list)
        except:
            airline_pnr =  ""
        try:
            pnr_list = list(set(api_response["itemInfos"]["AIR"]["travellerInfos"][0]["gdsPnrs"].values()))
            if len(pnr_list) == 1:
                gds_pnr = pnr_list[0]
            else:
                gds_pnr = "_$_".join(pnr_list)
        except:
            gds_pnr =  ""
        return airline_pnr,gds_pnr
        
    def is_lcc_flight(self,fare_quote):
        flight_segment = fare_quote["tripInfos"][0]["sI"][0]
        is_lcc = flight_segment.get("fD",{}).get("aI",{}).get("isLcc",True)
        return is_lcc

    def find_ticket_num(self,ticket_num_details):
        try:
            if not ticket_num_details:
                return ""
            ticketno_list = list(set(ticket_num_details.values()))
            if len(ticketno_list) == 1:
                return ticketno_list[0]
            else:
                return  "_$_".join(ticketno_list)
        except:
            return ""        

    def converter(self, search_response, journey_details,fare_details):
        book_filters = self.booking_filters({"journey_type":journey_details["journey_type"],"flight_type":journey_details["flight_type"],
                                             "supplier_id":str(self.vendor_id),"fare_type":journey_details.get("fare_type")}) 
        lcc_filter = book_filters.get("is_lcc",False)
        gds_filter = book_filters.get("is_gds",False)
        try:
            fare_adjustment,tax_condition = set_fare_details(fare_details)
            if journey_details["journey_type"] == "One Way":
                date = "".join(journey_details["journey_details"][0]["travel_date"].split('-')[:2])
                flightSegment = journey_details["journey_details"][0]["source_city"]+"_"+journey_details["journey_details"][0]["destination_city"]+"_"+date
                result = {"itineraries":[flightSegment],flightSegment:[]}
                segment_keys = create_segment_keys(journey_details)
                if search_response.get("searchResult"):
                    segments = search_response["searchResult"]["tripInfos"]["ONWARD"]
                    for segment in segments: # looping every result of total results (say each in total of 65 results)
                        sorted_price_list = self.sort_prices(segment["totalPriceList"])
                        first_flight_indices = [str(d.get("id",0)) for d in  segment["sI"] if d.get("sN") == 0]
                        unified_structure = unify_seg(segment["sI"],flightSegment,sorted_price_list) # will handle connection flight
                        unified_structure["segmentID"] = segment.get("segmentID")
                        unified_structure["default_baggage"] = {flightSegment:{}}
                        calculated_fares = calculate_fares(sorted_price_list[0]["fd"],fare_adjustment,tax_condition,
                                                            journey_details["passenger_details"])
                        unified_structure["offerFare"] = calculated_fares["offered_fare"]
                        unified_structure["Discount"] = calculated_fares["discount"]
                        unified_structure["publishFare"] = calculated_fares["publish_fare"]
                        unified_structure["currency"] = "INR"
                        unified_structure["IsLCC"] = segment["sI"][0]["fD"]["aI"]["isLcc"]
                        unified_structure["isRefundable"] =  bool(sorted_price_list[0]["fd"]["ADULT"].get("rT",0))
                        unified_structure["default_baggage"][flightSegment]["checkInBag"] = get_default_baggage(sorted_price_list[0],first_flight_indices).get("checkInBag")
                        unified_structure["default_baggage"][flightSegment]["cabinBag"] = get_default_baggage(sorted_price_list[0],first_flight_indices).get("cabinBag")
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
                    if search_response[flightSegment].get("searchResult"):
                        segments = search_response[flightSegment]["searchResult"]["tripInfos"]["ONWARD"]
                        for segment in segments:
                            sorted_price_list = self.sort_prices(segment["totalPriceList"])
                            first_flight_indices = [str(d.get("id",0)) for d in  segment["sI"] if d.get("sN") == 0]
                            unified_structure = unify_seg(segment["sI"],flightSegment,sorted_price_list)
                            unified_structure["segmentID"] = segment.get("segmentID")
                            unified_structure["default_baggage"] = {flightSegment:{}}
                            calculated_fares = calculate_fares(sorted_price_list[0]["fd"],fare_adjustment,tax_condition,
                                                            journey_details["passenger_details"])
                            unified_structure["offerFare"] = calculated_fares["offered_fare"]
                            unified_structure["Discount"] = calculated_fares["discount"]
                            unified_structure["publishFare"] = calculated_fares["publish_fare"]
                            unified_structure["currency"] = "INR"
                            unified_structure["IsLCC"] = segment["sI"][0]["fD"]["aI"]["isLcc"]
                            unified_structure["isRefundable"] =  bool(sorted_price_list[0]["fd"]["ADULT"].get("rT",0))
                            unified_structure["default_baggage"][flightSegment]["checkInBag"] = get_default_baggage(sorted_price_list[0],first_flight_indices).get("checkInBag")
                            unified_structure["default_baggage"][flightSegment]["cabinBag"] = get_default_baggage(sorted_price_list[0],first_flight_indices).get("cabinBag")
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
                if search_response.get("searchResult"):
                    segments = search_response["searchResult"]["tripInfos"].get("COMBO")
                    for segment in segments:
                        res = {"flightSegments":{},"default_baggage":{}}
                        sorted_price_list = self.sort_prices(segment["totalPriceList"])
                        for flight_index,_ in enumerate(segment["sI"]):
                            condition = lambda d: d['aa']["code"] == arrival_airport
                            one_way_index = next((i for i, d in enumerate(segment["sI"]) if condition(d)), -1)
                            flightSegment = fs[0] if flight_index <= one_way_index else fs[1]
                            if flightSegment not in res["default_baggage"]:
                                res["default_baggage"][flightSegment] = {}
                            split_segment = segment["sI"][:one_way_index+1] if flightSegment == fs[0] else segment["sI"][one_way_index+1:]
                            first_flight_indices = [str(d.get("id",0)) for d in  split_segment if d.get("sN") == 0]
                            if not res['flightSegments'].get(flightSegment):
                                unified_structure = unify_seg(split_segment ,flightSegment,sorted_price_list)
                                res['flightSegments'][flightSegment] = unified_structure["flightSegments"][flightSegment]
                                res["default_baggage"][flightSegment]["checkInBag"] = get_default_baggage(sorted_price_list[0],first_flight_indices).get("checkInBag")
                                res["default_baggage"][flightSegment]["cabinBag"] = get_default_baggage(sorted_price_list[0],first_flight_indices).get("cabinBag")  
                        if fs[0] in res['flightSegments'] and fs[1] in res['flightSegments']:
                            res["segmentID"] = segment["segmentID"]
                            calculated_fares = calculate_fares(sorted_price_list[0]["fd"],fare_adjustment,tax_condition,
                                                                journey_details["passenger_details"])
                            res["offerFare"] = calculated_fares["offered_fare"]
                            res["Discount"] = calculated_fares["discount"]
                            res["publishFare"] = calculated_fares["publish_fare"]
                            res["currency"] = "INR" 
                            res["IsLCC"] = segment["sI"][0]["fD"]["aI"]["isLcc"]
                            res["isRefundable"] =  bool(sorted_price_list[0]["fd"]["ADULT"].get("rT",0))
                            if lcc_filter:
                                if res["IsLCC"]:
                                    result[main_seg_name].append(res)
                            if gds_filter:
                                if not res["IsLCC"]:
                                    result[main_seg_name].append(res)
                            if not lcc_filter and not gds_filter:
                                pass
            is_any_itinerary_empty = lambda d: any(isinstance(d[k], list) and not d[k] for k in d if k != 'itineraries')
            if is_any_itinerary_empty(result):
                result.update({k: [] for k in result if k != 'itineraries'})
            return {"data":result,"status":"success"}
        except Exception as e:
            error = tb.format_exc()
            self.mongo_client.flight_supplier.insert_one({"vendor":"Tripjack","error":error,"type":"converter",
                                                            "createdAt": datetime.now()})
            return {"data":[],"status":"failiure"}
    
    def purchase(self,**kwargs):
        itinerary = kwargs["itinerary"]
        booking = kwargs["booking"]
        try:
            display_id = booking.display_id
            name = booking.user.first_name + booking.user.last_name
            supplier_id = self.credentials.get("supplier_id","")
            booking_dict = booking.__dict__
            itinerary = kwargs["itinerary"]
            flight_booking_unified_data = FlightBookingUnifiedDetails.objects.filter(itinerary = itinerary.id).first()
            fare_details = flight_booking_unified_data.fare_details[itinerary.itinerary_key]
            payment_details_easylink = {"new_published_fare": fare_details["publishedFare"],
                            "new_offered_fare":fare_details["offeredFare"],
                            "supplier_offered_fare":fare_details["supplier_offerFare"],
                            "supplier_published_fare":fare_details["supplier_publishFare"]}
            pax_details = kwargs["pax_details"]
            ssr_response_itinerary = flight_booking_unified_data.ssr_raw[itinerary.itinerary_key]
            fare_quote = flight_booking_unified_data.fare_quote[itinerary.itinerary_key]
            isLCC_flight = self.is_lcc_flight(fare_quote)
            is_gst_mandatory = fare_quote.get("conditions",{}).get("gst",{}).get("igm",False)
            ssr_details = list(kwargs["ssr_details"].values())
            bookingId = ssr_response_itinerary["ssr"]["bookingId"]
            total_price = ssr_response_itinerary["ssr"]["totalPriceInfo"]["totalFareDetail"]["fC"]["TF"]
            ssr_si = ssr_response_itinerary["ssr"]["tripInfos"]
            flight_ids = self.find_flight_ids(data = ssr_si)
            travellerInfo = []
            email = json.loads(booking_dict["contact"])["email"]
            phone = json.loads(booking_dict["contact"])["phone"]
            gst_details = json.loads(booking_dict["gst_details"])
            payload = {"bookingId":bookingId}
            if gst_details and is_gst_mandatory:
                payload["gstInfo"] = {
                    "gstNumber": gst_details.get("gstNumber", ""),
                    "email": gst_details.get("email", ""),
                    "registeredName": gst_details.get("name", ""),
                    "mobile": str(gst_details.get("phone", ""))[-10:],
                    "address": gst_details.get("address", "")
                }             	
            payload["deliveryInfo"] =  {
                        "emails": [
                        email
                        ],
                        "contacts": [phone
                        ]
                    }
            for  pax in pax_details:
                passenger = {}
                pax_id = pax.id
                filtered_ssr = list(filter(lambda x: str(x["pax_id"]) == str(pax_id), ssr_details))
                passenger["ti"] = self.passenger_title_creation(gender = pax.gender,title = pax.title,
                                                                pax_type = pax.pax_type)
                passenger["fN"] = pax.first_name 
                passenger["lN"] = pax.last_name
                passenger["pt"] = pax_type_mapping.get(pax.pax_type, 1)
                if pax.dob:
                    passenger["dob"] = self.date_format_correction(pax.dob)
                if pax.passport:
                    passenger["pNum"] = pax.passport
                    passenger["eD"] = self.date_format_correction(pax.passport_expiry)
                    passenger["pNat"] = pax.passport_issue_country_code
                    passenger["pid"] = self.date_format_correction(pax.passport_issue_date)
                ffn = pax.frequent_flyer_number.get(itinerary.itinerary_key,{})
                if ffn:
                    if ffn.get("frequent_flyer_number","").strip():
                        passenger["ff"] = {ffn.get("airline_code",""):ffn.get("frequent_flyer_number","")}
                if filtered_ssr:
                    if filtered_ssr[0].get("is_baggage"):
                        try:
                            baggage_ssr = json.loads(filtered_ssr[0]["baggage_ssr"])
                            ssrBaggageInfos = []
                            for flight_key in baggage_ssr:
                                baggage_code = baggage_ssr[flight_key].get("Code")
                                if baggage_code:
                                    for ssr_si_info_baggage_index in range(len(ssr_si)):
                                        ssr_si_info_baggage_selected = ssr_si[ssr_si_info_baggage_index]["sI"]
                                        for ssr_si_info_baggage in ssr_si_info_baggage_selected:
                                            if ssr_si_info_baggage["da"]["code"] + "-" + ssr_si_info_baggage["aa"]["code"] == flight_key:
                                                flight_id = ssr_si_info_baggage["id"]
                                                break
                                    segment_key = flight_id
                                    ssrBaggageInfos.append({"key":segment_key,"code":baggage_code})
                                    total_price += float(baggage_ssr[flight_key]["Price"])
                            passenger["ssrBaggageInfos"] = ssrBaggageInfos
                        except:
                            pass
                    if filtered_ssr[0].get("is_meals"):
                        try:
                            meals_ssr = json.loads(filtered_ssr[0]["meals_ssr"])
                            ssrMealInfos = []
                            for flight_key in meals_ssr:
                                meals_code =  meals_ssr[flight_key].get("Code")
                                if meals_code:
                                    for ssr_si_info_meals_index in range(len(ssr_si)):
                                        ssr_si_info_meals_selected = ssr_si[ssr_si_info_meals_index]["sI"]
                                        for ssr_si_info_meals in ssr_si_info_meals_selected:
                                            if ssr_si_info_meals["da"]["code"] + "-" + ssr_si_info_meals["aa"]["code"] == flight_key:
                                                flight_id = ssr_si_info_meals["id"]
                                                break
                                    segment_key = flight_id
                                    ssrMealInfos.append({"key":segment_key,"code":meals_code})
                                    total_price += float(meals_ssr[flight_key]["Price"])
                            passenger["ssrMealInfos"] = ssrMealInfos
                        except:
                            pass
                    if filtered_ssr[0].get("is_seats"):
                        try:
                            ssrSeatInfos = []
                            seats_ssr = json.loads(filtered_ssr[0]["seats_ssr"])
                            for flight_key in seats_ssr:
                                for flight_id in flight_ids:
                                    for key,value in flight_id.items():
                                        if value == flight_key:
                                            seats_code = seats_ssr[flight_key].get("Code")
                                            if seats_code:
                                                ssrSeatInfos.append({"key":key,"code":seats_code})
                                                total_price += float(seats_ssr[flight_key]["Price"])
                            passenger["ssrSeatInfos"] = ssrSeatInfos
                        except:
                            pass
                travellerInfo.append(passenger)
            payload["travellerInfo"] = travellerInfo
            paymentInfos = [{"amount":total_price}]
            payload["paymentInfos"]  = paymentInfos 
            itinerary.status = "Ticketing-Initiated"
            itinerary.save(update_fields=["status"])
            session_id = booking_dict.get("session_id")
            ticket_book = ticket_book_api(baseurl = self.credentials.get("base_url",""),vendor_name = self.name(), 
                                        api_key = self.credentials.get("apikey",""), payload = payload,session_id = session_id)
            if ticket_book["status"] == True:
                ticket_booking_details = ticket_booking_details_api(baseurl = self.credentials.get("base_url",""),vendor_name = self.name(),
                                                                    api_key = self.credentials.get("apikey",""), booking_id = bookingId,session_id = session_id)
                if ticket_booking_details.get("status"):
                    ticket_status = ticket_booking_details.get("data",{}).get("order",{}).get("status","").upper()
                    airline_pnr,gds_pnr = self.find_pnrs(ticket_booking_details["data"])
                    if ticket_status and ticket_status not in ["FAILED","ABORTED"]:
                        if airline_pnr:
                            itinerary.status = "Confirmed"
                            to_easylink = True
                            itinerary.error = ""
                            itinerary.soft_fail = False
                            for pax_ssr in kwargs["ssr_details"].filter(itinerary = itinerary):
                                passenger_response = ticket_booking_details.get("data",{}).get("itemInfos",{}).get("AIR",{}).get("travellerInfos",[])
                                first_name = pax_ssr.pax.first_name
                                last_name = pax_ssr.pax.last_name
                                for pax_data_response in passenger_response:
                                    if pax_data_response.get("fN") == first_name and pax_data_response.get("lN") == last_name:
                                        ticket_number = self.find_ticket_num(pax_data_response.get("ticketNumberDetails",{}))
                                        if ticket_number:
                                            pax_ssr.supplier_ticket_number = ticket_number
                                            pax_ssr.save()
                                        else:
                                            if not isLCC_flight:
                                                itinerary.status = "Ticketing-Failed"
                                                itinerary.error = "Ticket number not available"
                                                itinerary.soft_fail = True
                                                to_easylink = False
                                            else:
                                                itinerary.status = "Confirmed"
                                                itinerary.soft_fail = False
                            try:
                                if to_easylink:
                                    finance_manager = FinanceManager(booking.user)
                                    finance_manager.book_tripjack(booking_data = ticket_booking_details["data"], display_id = display_id,
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
                            itinerary.status = "Ticketing-Failed"
                            itinerary.soft_fail = True 
                            itinerary.error = "PNR not available!"
                            purchase_response = {"status":True}
                        itinerary.airline_pnr = airline_pnr
                        itinerary.gds_pnr = gds_pnr
                        itinerary.modified_at = int(time.time())
                        itinerary.supplier_booking_id = bookingId
                        misc = {"booking_id":bookingId,"booking_detail":ticket_booking_details}
                        itinerary.misc =  json.dumps(misc)
                        itinerary.save(update_fields=["airline_pnr","status","misc","modified_at","error","soft_fail",
                                                    "supplier_booking_id","gds_pnr"])
                    else:
                        itinerary.airline_pnr = airline_pnr
                        itinerary.gds_pnr = gds_pnr
                        itinerary.status = "Ticketing-Failed"
                        itinerary.soft_fail = False 
                        itinerary.modified_at = int(time.time())
                        itinerary.error = "Ticket Aborted/Failed from supplier side"
                        misc = {"booking_id":bookingId,"booking_detail":ticket_booking_details}
                        itinerary.supplier_booking_id = bookingId
                        itinerary.save(update_fields=["airline_pnr","status","misc","modified_at","error","soft_fail",
                                                    "supplier_booking_id","gds_pnr"])
                        purchase_response = {"status":False}
                else:
                    itinerary.status = "Ticketing-Failed"
                    itinerary.error = "Ticket details pending from supplier"
                    itinerary.soft_fail = True if ticket_booking_details.get("status_code") == 504 else False
                    itinerary.supplier_booking_id = bookingId
                    itinerary.modified_at = int(time.time())
                    itinerary.misc =  json.dumps({"booking_id":bookingId,"booking_detail":{}})
                    itinerary.save(update_fields=["status","error","modified_at","soft_fail","supplier_booking_id","misc"])
                    purchase_response = {"status":True if ticket_booking_details.get("status_code") == 504 else False}  
            else:
                try:
                    error = ticket_book["data"]["errors"][0]["message"]
                except:
                    error = "Ticketing Failed from supplier side!"
                itinerary.soft_fail = False
                itinerary.status = "Ticketing-Failed"
                itinerary.modified_at = int(time.time())
                itinerary.supplier_booking_id = bookingId
                misc = {"booking_id":bookingId,"booking_detail":{}}
                itinerary.misc =  json.dumps(misc)
                itinerary.error = error
                itinerary.save(update_fields=["error","status","misc","modified_at","soft_fail","supplier_booking_id"])
                purchase_response = {"status":False}
            return purchase_response
        except Exception as e:
            error_trace = tb.format_exc()
            invoke_log = {"vendor":self.name(),"session_id":booking.session_id,"status":"failure","api":"purchase",
                          "createdAt": datetime.now(),"error":str(e),"error_trace":error_trace}
            self.mongo_client.flight_supplier.insert_one(invoke_log)
            itinerary.status = "Ticketing-Failed"
            itinerary.error = "Ticketing Failed"
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["error","status","misc","modified_at"])
            return{"status":False}

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
            return kwargs["title"]
        
    def date_format_correction(self,dob):
        dt = datetime.strptime(dob, '%Y-%m-%dT%H:%M:%S.%fZ')
        date_only = dt.strftime('%Y-%m-%d')
        return date_only
    
    def save_failed_finance(self,master_doc,data,itinerary,pax_details,fare_details,data_unified_dict):
        fare_adjustment,tax_condition = set_fare_details(fare_details)
        search_details = master_doc
        pax_details = pax_details
        booking_dict = {"BookingId":itinerary.supplier_booking_id,
                        "airline_pnr":data.get("airline_pnr"),
                        "gds_pnr":data.get("gds_pnr"),
                        "status":itinerary.status,
                        "itinerary_id":itinerary.id}
        booking = itinerary.booking
        unified_booking = FlightBookingUnifiedDetails.objects.filter(itinerary = itinerary.id).first()
        unified_booking_fare = unified_booking.fare_details[itinerary.itinerary_key]
        display_id = booking.display_id
        Org = booking.user.organization
        supplier_id = self.credentials.get("supplier_id","")
        fare_quote =  unified_booking.fare_quote[itinerary.itinerary_key]
        try:
            finance_manager = FinanceManager(booking.user)
            finance_manager.book_failed_tripjack(fare_adjustment,tax_condition,search_details,itinerary,
                                                    pax_details,booking_dict,display_id,
                                                    Org.easy_link_billing_code,supplier_id,
                                                    Org.easy_link_account_name,booking.created_at,fare_quote,unified_booking_fare)
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

    def current_ticket_status(self,**kwargs):
        soft_deleted_itinerary = kwargs["soft_deleted_itinerary"]
        booking = soft_deleted_itinerary.booking
        display_id = booking.display_id
        remarks = ""
        modified_at = int(time.time())
        try:
            to_easy_link = False
            invoke_status = "success"
            unified_itinerary = soft_deleted_itinerary.flightbookingunifieddetailsitinerary_set.first()
            ssr_details = soft_deleted_itinerary.flightbookingssrdetails_set.all()
            misc = json.loads(soft_deleted_itinerary.misc)
            bookingId = misc["booking_id"]
            fare_quote = unified_itinerary.fare_quote[soft_deleted_itinerary.itinerary_key]
            isLCC_flight = self.is_lcc_flight(fare_quote)
            updated_ticket_status = get_current_ticket_status(baseurl = self.credentials.get("base_url",""),vendor_name = self.name(),
                                                                    api_key = self.credentials.get("apikey",""), booking_id = bookingId,
                                                                    session_id = booking.session_id)
            fare_details = unified_itinerary.fare_details[soft_deleted_itinerary.itinerary_key]
            payment_details_easylink = {"new_published_fare": fare_details["publishedFare"],
                        "new_offered_fare":fare_details["offeredFare"],
                        "supplier_offered_fare":fare_details["supplier_offerFare"],
                        "supplier_published_fare":fare_details["supplier_publishFare"]}
            if updated_ticket_status.get('status'):
                ticket_status = updated_ticket_status.get("data",{}).get("order",{}).get("status","").upper()
                if ticket_status not in ["FAILED","ABORTED"]:
                    airline_pnr,gds_pnr = self.find_pnrs(updated_ticket_status["data"])
                    is_all_ticket_num = True
                    is_pnr = True
                    if not airline_pnr:
                        is_pnr = False
                        invoke_status = "failure"
                        remarks = "PNR not available"
                        if soft_deleted_itinerary.status =="Hold-Failed":
                            soft_deleted_itinerary.soft_fail = False
                            soft_deleted_itinerary.modified_at = modified_at
                            soft_deleted_itinerary.error = "PNR Not Available"
                            soft_deleted_itinerary.save(update_fields= ["status","modified_at","error","soft_fail"])
                    else:
                        if soft_deleted_itinerary.status =="Hold-Failed":
                            soft_deleted_itinerary.status = "On-Hold"
                            soft_deleted_itinerary.soft_fail = False
                            soft_deleted_itinerary.modified_at = modified_at
                            soft_deleted_itinerary.save(update_fields= ["status","modified_at","soft_fail"])
                        else:
                            for pax_ssr in ssr_details:
                                passenger_response = updated_ticket_status.get("data",{}).get("itemInfos",{}).get("AIR",{}).get("travellerInfos",[])
                                first_name = pax_ssr.pax.first_name
                                last_name = pax_ssr.pax.last_name
                                for pax_data_response in passenger_response:
                                    if pax_data_response.get("fN") == first_name and pax_data_response.get("lN") == last_name:
                                        ticket_number = self.find_ticket_num(pax_data_response.get("ticketNumberDetails",{}))
                                        if ticket_number:
                                            pax_ssr.supplier_ticket_number = ticket_number
                                            pax_ssr.save()
                                        else:
                                            is_all_ticket_num = False
                            if is_pnr and is_all_ticket_num:
                                remarks = "PNR and Ticket number available"
                                to_easy_link = True
                                soft_deleted_itinerary.soft_fail = False
                                soft_deleted_itinerary.airline_pnr = airline_pnr
                                soft_deleted_itinerary.gds_pnr = gds_pnr
                                soft_deleted_itinerary.status = "Confirmed"
                                soft_deleted_itinerary.modified_at = modified_at
                                soft_deleted_itinerary.save(update_fields= ["soft_fail","status","modified_at",
                                                                            "airline_pnr","gds_pnr"])
                            else:
                                remarks = "PNR available,Ticket Number not available"
                                if not isLCC_flight:
                                    invoke_status = "failure"
                                else:
                                    to_easy_link = True
                                    soft_deleted_itinerary.soft_fail = False
                                    soft_deleted_itinerary.airline_pnr = airline_pnr
                                    soft_deleted_itinerary.gds_pnr = gds_pnr
                                    soft_deleted_itinerary.status = "Confirmed"
                                    soft_deleted_itinerary.modified_at = modified_at
                                    soft_deleted_itinerary.save(update_fields= ["soft_fail","status","modified_at",
                                                                                "airline_pnr","gds_pnr"])
                            if to_easy_link:
                                try:
                                    finance_manager = FinanceManager(booking.user)
                                    finance_manager.book_tripjack(booking_data = updated_ticket_status["data"], display_id = booking.display_id,
                                                                payment_details = payment_details_easylink,
                                                                supplier_id = self.credentials.get("supplier_id",""),itinerary = soft_deleted_itinerary,pax_length = len(ssr_details))
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
                                invoke_email({"user": str(booking.user.id),"sec" : 86400,"event":"Ticket_Confirmation",
                                            "booking_id":display_id})
                else:
                    remarks = "Ticket Aborted/Failed from supplier side"
                    soft_deleted_itinerary.soft_fail = False
                    soft_deleted_itinerary.modified_at = modified_at
                    soft_deleted_itinerary.error = "Ticket Aborted/Failed from supplier side"
                    soft_deleted_itinerary.save(update_fields= ["modified_at","error","soft_fail"])
            else:
                invoke_status = "failure"
                remarks = "Failed to fetch Ticket Booking Details"
                soft_deleted_itinerary.soft_fail = True if updated_ticket_status.get("status_code") == 504 else False
                soft_deleted_itinerary.modified_at = modified_at
                soft_deleted_itinerary.save(update_fields= ["modified_at","soft_fail"])
            invoke_log = {"vendor":self.name(),"session_id":booking.session_id,"status":invoke_status,"api":"event_bridge",
                          "display_id":display_id,"isLCC":isLCC_flight,"remarks":remarks,"createdAt": datetime.now()}
            self.mongo_client.flight_supplier.insert_one(invoke_log)
        except Exception as e:
            error_trace = tb.format_exc()
            invoke_log = {"vendor":self.name(),"session_id":booking.session_id,"status":"failure","api":"event_bridge",
                          "display_id":display_id,"createdAt": datetime.now(),"error":str(e),"error_trace":error_trace,
                          "remarks":remarks}
            self.mongo_client.flight_supplier.insert_one(invoke_log)
            
def calculate_arrival_time(departure_time_str, ground_time_in_minutes):
    departure_time = datetime.strptime(departure_time_str, "%Y-%m-%dT%H:%M:%S")
    arrival_time = departure_time - timedelta(minutes=ground_time_in_minutes)
    arrival_time_str = arrival_time.strftime("%Y-%m-%dT%H:%M:%S")
    return arrival_time_str

def unify_seg_quote(flight_segments,flightSegment,segment):
    flight_segment = flight_segments[0]
    unified_structure = {"flightSegments":{flightSegment:[]}}
    price_details = segment["totalPriceList"][0]["fd"]
    unified_segment = {
        "airlineCode": flight_segment["fD"]["aI"].get("code",""),
        "airlineName": flight_segment["fD"]["aI"].get("name",""),
        "flightNumber": flight_segment["fD"]["fN"],
        "equipmentType": flight_segment["fD"].get("eT",""),
        "departure": {
            "airportCode": flight_segment["da"].get("code",""),
            "airportName": flight_segment["da"].get("name",""),
            "city": flight_segment["da"].get("city",""),
            "country": flight_segment["da"].get("country",""),
            "countryCode": flight_segment["da"].get("countryCode",""),
            "terminal": modify_terminal_name(flight_segment["da"].get("terminal","N/A")),
            "departureDatetime": flight_segment.get("dt","")
        },
        "arrival": {
            "airportCode": flight_segment["aa"].get("code",""),
            "airportName": flight_segment["aa"].get("name",""),
            "city": flight_segment["aa"].get("city",""),
            "country": flight_segment["aa"].get("country",""),
            "countryCode": flight_segment["aa"].get("countryCode",""),
            "terminal": modify_terminal_name(flight_segment["aa"].get("terminal","N/A")),
            "arrivalDatetime": flight_segment.get("at","")
        },
        "durationInMinutes":flight_segment.get("duration",0),
        "stop": len(flight_segments)-1,
        "cabinClass": price_details["ADULT"].get("cc","").replace("_"," ").title(),
        "fareBasisCode": price_details["ADULT"].get("fB"),
        "seatsRemaining": price_details["ADULT"].get("sR"),
        "isChangeAllowed": True
    }
    unified_structure['flightSegments'][flightSegment].append(unified_segment)
    if len(flight_segments) >1:
        stop_airport_codes =  [flight["da"].get("code","") for flight in flight_segments[1:]]
        for more_flight_segment in flight_segments[1:]:
            unified_segment = {
                "airlineCode": more_flight_segment["fD"]["aI"].get("code",""),
                "airlineName": more_flight_segment["fD"]["aI"].get("name",""),
                "flightNumber": more_flight_segment["fD"]["fN"],
                "equipmentType": more_flight_segment["fD"].get("eT",""),  # Aircraft type, if available
                "departure": {
                    "airportCode": more_flight_segment["da"].get("code",""),
                    "airportName": more_flight_segment["da"].get("name",""),
                    "city": more_flight_segment["da"].get("city",""),
                    "country": more_flight_segment["da"].get("country",""),
                    "countryCode": more_flight_segment["da"].get("countryCode",""),
                    "terminal": modify_terminal_name(more_flight_segment["da"].get("terminal","N/A")),
                    "departureDatetime": more_flight_segment.get("dt","")
                },
                "arrival": {
                    "airportCode": more_flight_segment["aa"].get("code",""),
                    "airportName": more_flight_segment["aa"].get("name",""),
                    "city": more_flight_segment["aa"].get("city",""),
                    "country": more_flight_segment["aa"].get("country",""),
                    "countryCode": more_flight_segment["aa"].get("countryCode",""),
                    "terminal": modify_terminal_name(more_flight_segment["aa"].get("terminal","N/A")),
                    "arrivalDatetime": more_flight_segment.get("at","")
                },
                "durationInMinutes":more_flight_segment.get("duration",0),
                "stop": len(flight_segments)-1,
                "cabinClass": price_details["ADULT"].get("cc","").replace("_"," ").title(),
                "fareBasisCode": price_details["ADULT"].get("fB"),
                "seatsRemaining": price_details["ADULT"].get("sR"),
                "isChangeAllowed": True,  
                "stopDetails": {
                "isLayover": True,
                "stopPoint": {
                    "airportCode": stop_airport_codes,
                            }
                    }
            }
            unified_structure['flightSegments'][flightSegment].append(unified_segment)
    return unified_structure

def unify_seg(flight_segments,flightSegment,sesorted_price_list):
    flight_segment = flight_segments[0]
    unified_structure = {"flightSegments":{flightSegment:[]}}
    price_details = sesorted_price_list[0]["fd"]
    unified_segment = {
        "airlineCode": flight_segment["fD"]["aI"].get("code",""),
        "airlineName": flight_segment["fD"]["aI"].get("name",""),
        "flightNumber": flight_segment["fD"].get("fN",""),
        "equipmentType": flight_segment["fD"].get("eT",""),  # Aircraft type, if available
        "departure": {
            "airportCode": flight_segment["da"].get("code",""),
            "airportName": flight_segment["da"].get("name",""),
            "city": flight_segment["da"].get("city",""),
            "country": flight_segment["da"].get("country",""),
            "countryCode": flight_segment["da"].get("countryCode",""),
            "terminal": modify_terminal_name(flight_segment["da"].get("terminal","N/A")),
            "departureDatetime": flight_segment.get("dt","")
        },
        "arrival": {
            "airportCode": flight_segment["aa"].get("code",""),
            "airportName": flight_segment["aa"].get("name",""),
            "city": flight_segment["aa"].get("city",""),
            "country": flight_segment["aa"].get("country",""),
            "countryCode": flight_segment["aa"].get("countryCode",""),
            "terminal": modify_terminal_name(flight_segment["aa"].get("terminal","N/A")),
            "arrivalDatetime": flight_segment.get("at","")
        },
        "durationInMinutes":flight_segment.get("duration",0),
        "stop": len(flight_segments)-1,
        "cabinClass": price_details["ADULT"].get("cc","").replace("_"," ").title(),
        "fareBasisCode": price_details["ADULT"].get("fB"),
        "seatsRemaining": price_details["ADULT"].get("sR"),
        "isChangeAllowed": True  
    }
    unified_structure['flightSegments'][flightSegment].append(unified_segment)
    if len(flight_segments) >1:
        stop_airport_codes =  [flight["da"].get("code","") for flight in flight_segments[1:]]
        for flight_segment in flight_segments[1:]:
            unified_segment = {
                "airlineCode": flight_segment["fD"]["aI"].get("code",""),
                "airlineName": flight_segment["fD"]["aI"].get("name",""),
                "flightNumber": flight_segment["fD"]["fN"],
                "equipmentType": flight_segment["fD"].get("eT",""),  # Aircraft type, if available
                "departure": {
                    "airportCode": flight_segment["da"].get("code",""),
                    "airportName": flight_segment["da"].get("name",""),
                    "city": flight_segment["da"].get("city",""),
                    "country": flight_segment["da"].get("country",""),
                    "countryCode": flight_segment["da"].get("countryCode",""),
                    "terminal": modify_terminal_name(flight_segment["da"].get("terminal","N/A")),
                    "departureDatetime": flight_segment.get("dt","")
                },
                "arrival": {
                    "airportCode": flight_segment["aa"].get("code",""),
                    "airportName": flight_segment["aa"].get("name",""),
                    "city": flight_segment["aa"].get("city",""),
                    "country": flight_segment["aa"].get("country",""),
                    "countryCode": flight_segment["aa"].get("countryCode",""),
                    "terminal": modify_terminal_name(flight_segment["aa"].get("terminal","N/A")),
                    "arrivalDatetime": flight_segment.get("at","")
                },
                "durationInMinutes":flight_segment.get("duration",0),
                "stop" :len(flight_segments)-1,
                "cabinClass": price_details["ADULT"].get("cc","").replace("_"," ").title(),
                "fareBasisCode": price_details["ADULT"].get("fB"),
                "seatsRemaining": price_details["ADULT"].get("sR"),
                "isChangeAllowed": True,  
                "stopDetails": {
                "isLayover": True,
                "stopPoint": {
                    "airportCode": stop_airport_codes,
                            }                  
            }                       
            }
            unified_structure['flightSegments'][flightSegment].append(unified_segment)
    return unified_structure

def calculate_fares(fare_dict,fare_adjustment,tax_condition,pax_data,fare_quote = False):
    total_pax_count = sum(list(map(int,list(pax_data.values()))))
    supplier_published_fare = 0
    supplier_offered_fare = 0
    if fare_quote:
        supplier_published_fare = fare_dict.get("TF",0)
        supplier_offered_fare = fare_dict.get("NF",0)
    else:
        if "ADULT" in fare_dict:
            supplier_published_fare = supplier_published_fare +int(pax_data["adults"])*fare_dict["ADULT"].get("fC",{}).get("TF",0)
            supplier_offered_fare = supplier_offered_fare + int(pax_data["adults"])*fare_dict["ADULT"].get("fC",{}).get("NF",0)
        if "CHILD" in fare_dict:
            supplier_published_fare = supplier_published_fare + int(pax_data["children"])*fare_dict["CHILD"].get("fC",{}).get("TF",0)
            supplier_offered_fare = supplier_offered_fare + int(pax_data["children"])*fare_dict["CHILD"].get("fC",{}).get("NF",0)
        if "INFANT" in fare_dict:
            supplier_published_fare = supplier_published_fare + int(pax_data["infants"])*fare_dict["INFANT"].get("fC",{}).get("TF",0)
            supplier_offered_fare = supplier_offered_fare + int(pax_data["infants"])*fare_dict["INFANT"].get("fC",{}).get("NF",0)
    new_published_fare = supplier_published_fare + ((float(fare_adjustment["markup"]))+(float(fare_adjustment["distributor_markup"]))-\
                            float(fare_adjustment["cashback"]) - float(fare_adjustment["distributor_cashback"]))*total_pax_count
    new_offered_fare = supplier_published_fare + (float(fare_adjustment["markup"]) + float(fare_adjustment["distributor_markup"]) -\
         float(fare_adjustment["cashback"])-float(fare_adjustment["distributor_cashback"]))*total_pax_count -\
          (supplier_published_fare-supplier_offered_fare)*(float(fare_adjustment["parting_percentage"])/100)*(float(fare_adjustment["distributor_parting_percentage"])/100)*(1-float(tax_condition["tax"])/100)
    discount = (new_published_fare-new_offered_fare)
    return {"offered_fare":new_offered_fare,"discount":discount,"publish_fare":new_published_fare,
            "supplier_published_fare":supplier_published_fare,"supplier_offered_fare":supplier_offered_fare}

def get_unified_cabin_class(cabin_class):
    cabin_map = {2:"Economy",3:"PremiumEconomy",4:"Business Class",6:"First Class"}
    return cabin_map.get(cabin_class,"Economy")

def get_fareBreakdown(**kwargs):
    kwargs["pax_data"] = {key: int(float(value)) for key, value in kwargs["pax_data"].items()}
    FareBreakdownResults = []
    total_base_fare = 0
    total_pax_count = sum(list(map(int,list(kwargs["pax_data"].values()))))
    if not kwargs["fare_details"]:
        result_dict  = {}
        for trip_info in kwargs["FareBreakdown"]:
            for price_list in trip_info["totalPriceList"]:
                if "ADULT" in price_list["fd"]:
                    if "adults" not in result_dict:
                        result_dict["adults"] = {}
                        result_dict["adults"]['passengerType'] = "adults"
                        result_dict["adults"]['baseFare'] = price_list["fd"]["ADULT"].get("fC",{}).get('BF',0)
                        total_base_fare += price_list["fd"]["ADULT"].get("fC",{}).get('BF',0)
                    else:
                        result_dict["adults"]['passengerType'] = "adults"
                        result_dict["adults"]['baseFare'] = result_dict["adults"]['baseFare'] + price_list["fd"]["ADULT"].get("fC",{}).get('BF',0)
                        total_base_fare += price_list["fd"]["ADULT"].get("fC",{}).get('BF',0)
                        
                if "CHILD" in price_list["fd"]:
                    if "children" not in result_dict:
                        result_dict["children"] = {}
                        result_dict["children"]['passengerType'] = "children"
                        result_dict["children"]['baseFare'] = price_list["fd"]["CHILD"].get("fC",{}).get('BF',0)
                        total_base_fare += price_list["fd"]["CHILD"].get("fC",{}).get('BF',0)
                    else:
                        result_dict["children"]['passengerType'] = "children"
                        result_dict["children"]['baseFare'] = result_dict["children"]['baseFare'] + price_list["fd"]["CHILD"].get("fC",{}).get('BF',0)
                        total_base_fare += price_list["fd"]["CHILD"].get("fC",{}).get('BF',0)
                
                if "INFANT" in price_list["fd"]:
                    if "infants" not in result_dict:
                        result_dict["infants"] = {}
                        result_dict["infants"]['passengerType'] = "infants"
                        result_dict["infants"]['baseFare'] = price_list["fd"]["INFANT"].get("fC",{}).get('BF',0)
                        total_base_fare += price_list["fd"]["INFANT"].get("fC",{}).get('BF',0)
                    else:
                        result_dict["infants"]['passengerType'] = "infants"
                        result_dict["infants"]['baseFare'] = result_dict["infants"]['baseFare'] + price_list["fd"]["INFANT"].get("fC",{}).get('BF',0)
                        total_base_fare += price_list["fd"]["INFANT"].get("fC",{}).get('BF',0)
        total_base_fare = result_dict.get("adults",{}).get("baseFare",0)*kwargs["pax_data"].get("adults",0)+\
                        result_dict.get("children",{}).get("baseFare",0)*kwargs["pax_data"].get("children",0) + \
                        result_dict.get("infants",{}).get("baseFare",0)*kwargs["pax_data"].get("infants",0)
        tax_per_pax = round((kwargs["new_published_fare"]-total_base_fare)/total_pax_count,2)
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
    else:
        total_base_fare = kwargs["FareBreakdown"].get("CHILD",{}).get("fC",{}).get("BF",0)*kwargs["pax_data"].get("children",0)+\
                            kwargs["FareBreakdown"].get("ADULT",{}).get("fC",{}).get("BF",0)*kwargs["pax_data"].get("adults",0) +\
                            kwargs["FareBreakdown"].get("INFANT",{}).get("fC",{}).get("BF",0)*kwargs["pax_data"].get("infants",0)
        tax_per_pax = round((kwargs["new_published_fare"]-total_base_fare)/total_pax_count,2)
        if "ADULT" in kwargs["FareBreakdown"]:
            FareBreakdownResult = {}
            FareBreakdownResult['passengerType'] = "adults"
            FareBreakdownResult['baseFare'] = kwargs["FareBreakdown"]["ADULT"]["fC"]['BF']
            FareBreakdownResult['tax'] = tax_per_pax
            FareBreakdownResults.append(FareBreakdownResult)
        if "CHILD" in kwargs["FareBreakdown"]:
            FareBreakdownResult = {}
            FareBreakdownResult['passengerType'] = "children"
            FareBreakdownResult['baseFare'] = kwargs["FareBreakdown"]["CHILD"]["fC"]['BF']
            FareBreakdownResult['tax'] = tax_per_pax
            FareBreakdownResults.append(FareBreakdownResult)
        if "INFANT" in kwargs["FareBreakdown"]:
            FareBreakdownResult = {}
            FareBreakdownResult['passengerType'] = "infants"
            FareBreakdownResult['baseFare'] = kwargs["FareBreakdown"]["INFANT"]["fC"]['BF']
            FareBreakdownResult['tax'] = tax_per_pax
            FareBreakdownResults.append(FareBreakdownResult)
        
        return FareBreakdownResults

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

def get_default_baggage(fare_data,first_flight_indices):
    checkInBag = ''
    cabinBag = ''
    additional_info = fare_data.get("tai",{}).get("tbi",[])
    for flight_key in additional_info:
        if flight_key in first_flight_indices:
            for adult_check in additional_info[flight_key]:
                if "ADULT" in adult_check:
                    checkInBag = checkInBag + adult_check.get("ADULT",{}).get("iB","")+ ","
                    cabinBag = cabinBag +adult_check.get("ADULT",{}).get("cB","")+ "," 
    if not checkInBag.strip(","):
        checkInBag = fare_data.get("fd",{}).get("ADULT",{}).get("bI",{}).get("iB","")
    if not cabinBag.strip(","):
        cabinBag = fare_data.get("fd",{}).get("ADULT",{}).get("bI",{}).get("cB","")
    response = {"checkInBag": checkInBag.strip(","), "cabinBag": cabinBag.strip(",")}
    return response
    
pax_type_mapping = {"adults": "ADULT","child": "CHILD","infant": "INFANT"}

gender_mapping = {"Male": 1,"M": 1,"Female": 2,"F": 2}

fare_type_mapping = {"Student":"STUDENT","Regular":"REGULAR","Senior Citizen":"SENIOR_CITIZEN"}