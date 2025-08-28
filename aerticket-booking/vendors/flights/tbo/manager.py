from vendors.flights.abstract.abstract_flight_manager import AbstractFlightManager
from vendors.flights.tbo.api  import (flight_search,authentication,cancel_ticket,
                                      fare_rule,fare_quote,ssr,
                                      hold,release_hold,
                                      ticket,ticket_lcc,
                                      cancellation_charges,check_cancellation_status,
                                      get_current_ticket_status
                                      )
from datetime import datetime,timedelta
from vendors.flights.utils import create_uuid,set_fare_details,create_segment_keys,invoke_email
from vendors.flights.finance_manager import FinanceManager
from users.models import LookupCountry
from common.models import FlightBookingFareDetails,FlightBookingSSRDetails,FlightBookingItineraryDetails,\
    LookupEasyLinkSupplier,FlightBookingUnifiedDetails
import concurrent.futures
import re,json
import time
import traceback as tb

class Manager(AbstractFlightManager):
    def __init__(self,data,uuid,mongo_client,is_auth):
        self.vendor_id = "VEN-"+str(uuid)
        self.credentials = data
        self.base_url = data["base_url"]
        self.auth_url = data["auth_url"]
        self.ticketing_url = data["ticketing_url"]
        self.mongo_client = mongo_client
        if is_auth:
            self.token = authentication(self.auth_url,self.credentials)
        else:
            self.token = data["token"]
        self.credentials["token"] =  self.token
        
    def name (self):
        return "TBO"
    def get_vendor_id(self):
        return self.vendor_id
    def get_cabin_class(self,cabin_class):
        cabin_map = {"Any":1,"Economy":2,"PremiumEconomy":3,"Business Class":4,"First Class":6}
        return cabin_map.get(cabin_class,1)

    def get_journey_type(self,journey_type):
        journey_type_map = {"One Way":1,"Round Trip":2,"Multi Stop":1}
        return journey_type_map.get(journey_type,1)
    def create_segments(self,journey_details,cabin_class):
        result = []
        for detail in journey_details:
            origin = detail.get("source_city")
            destination = detail.get("destination_city")
            travel_date = datetime.strptime(detail.get("travel_date"), "%d-%m-%Y")
            preferred_time = travel_date.strftime("%Y-%m-%dT%H:%M:%S")
            
            flight_detail = {
                "Origin": origin,
                "Destination": destination,
                "FlightCabinClass": cabin_class,
                "PreferredDepartureTime": preferred_time,
                "PreferredArrivalTime": preferred_time
            }
            result.append(flight_detail)
        return result
    
    def search_flights(self,journey_details):
        journey_type = journey_details.get("journey_type")
        flight_type = journey_details.get("flight_type")
        pax = journey_details.get("passenger_details")
        cabin_class = journey_details.get("cabin_class")
        segment_details = journey_details.get("journey_details")
        fare_type = fare_type_mapping.get(journey_details.get("fare_type"),2)
        session_id = journey_details.get("session_id")
        cabin_class = self.get_cabin_class(cabin_class)
        trip_type = self.get_journey_type(journey_type)
        segments = self.create_segments(segment_details,cabin_class)
        segment_keys = create_segment_keys(journey_details)
        book_filters = self.booking_filters({"journey_type":journey_type,"flight_type":flight_type,
                                             "supplier_id":str(self.vendor_id),"fare_type":journey_details.get("fare_type")}) 
        def process_segment(seg, index):
            """Function to process each segment in a thread."""
            flight_search_response = flight_search(
                baseurl=self.base_url,
                credentials=self.credentials,
                trip_type=1,
                pax=pax,
                segments=[seg],
                fare_type = fare_type,
                session_id = session_id,
                book_filters = book_filters
            )
            flight_search_response = self.add_uuid_to_segments(
                flight_search_response, flight_type, journey_type
                )
            return index, flight_search_response
        if journey_type =="Multi City" or \
            (journey_type =="Round Trip" and flight_type == "DOM") :
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
            final_result = run_in_threads(segments, segment_keys)
            return {"data":final_result,"status":"success"}

        else:
            flight_search_response = flight_search(baseurl= self.base_url,credentials=self.credentials,
                                                    trip_type=trip_type,pax=pax,segments=segments,
                                                    fare_type = fare_type, session_id = session_id,book_filters = book_filters)
            flight_search_response = self.add_uuid_to_segments(flight_search_response,flight_type,journey_type)
            return {"data":flight_search_response,"status":"success"}
        
    def get_updated_fare_details(self,index,segment_data, search_details,raw_data,raw_doc,currentfare,fare_details,session_id):
        try:
            total_pax_count = sum(list(map(int,list(search_details["passenger_details"].values()))))
            fare_adjustment,tax_condition= set_fare_details(fare_details)
            if search_details["journey_type"] =="Multi City" or \
                (search_details["journey_type"] =="Round Trip" and search_details["flight_type"] == "DOM"):
                segment_keys = create_segment_keys(search_details)
                flightSegment= segment_keys[index]
                segment_id = segment_data['segment_id']
                fare_id = segment_data['fare_id']
                extracted_segment = raw_data
                TraceId = extracted_segment['TraceId']
                ResultIndex = extracted_segment['ResultIndex']
                fare_quote_response = fare_quote(self.base_url,self.credentials,
                                                TraceId,ResultIndex,session_id)
                if fare_quote_response['Response']['ResponseStatus'] == 1:
                    updated =True
                    vendor_data = fare_quote_response
                    IsPriceChanged = fare_quote_response['Response']['IsPriceChanged']
                    FlightDetailChangeInfo = fare_quote_response['Response']['FlightDetailChangeInfo']
                    info = ""
                    if IsPriceChanged == True:
                        info = "Airline Price Change Detected."
                    if FlightDetailChangeInfo != None:
                        info = info + str(FlightDetailChangeInfo)+" Value Change Detected."
                
                    if info != "":
                        info += " Please refer to the updated details."
                    fareDetails = {}
                    result = {}
                    is_gst_mandatory = fare_quote_response['Response']["Results"].get("IsGSTMandatory",False)
                    result['fare_id'] = fare_id
                    calculated_fares = calculate_fares(fare_quote_response['Response']['Results']["Fare"]["PublishedFare"],
                                                    fare_quote_response['Response']['Results']["Fare"]["OfferedFare"],
                                                    fare_adjustment,tax_condition,total_pax_count)
                    result['publishedFare'] = calculated_fares["published_fare"]
                    result['offeredFare'] = calculated_fares["offered_fare"]
                    result["supplier_publishFare"] = calculated_fares["supplier_published_fare"]
                    result["supplier_offerFare"] = calculated_fares["supplier_offered_fare"]
                    result["Discount"] = calculated_fares["discount"]
                    result['fareType'] = fare_quote_response['Response']['Results'].get('FareClassification',{}).get("Type","N/A")
                    if not result['fareType']:
                        result['fareType'] = 'N/A'
                    result['currency'] = fare_quote_response['Response']['Results']['Fare']['Currency']
                    result['colour'] = "Peach"
                    result['fareBreakdown'] = get_fareBreakdown(fare_quote_response['Response']['Results']['FareBreakdown'],
                                                                calculated_fares["published_fare"],search_details["passenger_details"])
                    result['isRefundable'] = fare_quote_response['Response']['Results']['IsRefundable']
                    fareDetails[flightSegment] = result
                    unified_seg = {"itineraries":[flightSegment],flightSegment:[],"fareDetails":fareDetails}
                    flight_legs = vendor_data["Response"]["Results"]["Segments"]
                    for flight_leg in flight_legs:
                        unified_structure = unify_seg_quote(flight_leg,flightSegment,IsPriceChanged,vendor_data["Response"]["Results"]['FareRules'][0]['FareBasisCode'])
                        unified_structure["segmentID"] = segment_id
                        # calculated_fares = calculate_fares(vendor_data["Response"]["Results"]["Fare"]["PublishedFare"],
                        #                                 vendor_data["Response"]["Results"]["Fare"]["OfferedFare"],
                        #                                 fare_adjustment,tax_condition,total_pax_count)
                        # unified_structure["publishFare"] = calculated_fares["published_fare"]
                        # unified_structure["offerFare"] = calculated_fares["offered_fare"]
                        # unified_structure["supplier_publishFare"] = calculated_fares["supplier_published_fare"]
                        # unified_structure["supplier_offerFare"] = calculated_fares["supplier_offered_fare"]
                        # unified_structure["Discount"] = calculated_fares["discount"]
                        # unified_structure["currency"] = vendor_data["Response"]["Results"]["Fare"]["Currency"]
                        unified_seg[flightSegment] = unified_structure
                else:
                    IsPriceChanged = False
                    updated = False
                    is_gst_mandatory = False
                misc_data = {"TraceId":TraceId,"ResultIndex":ResultIndex} 
                misc_doc = {"session_id":session_id,"segment_id":segment_id,"data":misc_data,
                            "createdAt":datetime.now(),"type":"misc"}
                self.mongo_client.searches.insert_one(misc_doc)          
                return {"updated":updated,"data":unified_seg,"raw":fare_quote_response,"status":"success",
                        "IsPriceChanged":IsPriceChanged,"is_gst_mandatory":is_gst_mandatory,'frequent_flyer_number':True} if \
                    updated else {"updated":updated,"status":"failure","raw":fare_quote_response,
                                "is_gst_mandatory":is_gst_mandatory,"IsPriceChanged":IsPriceChanged,'frequent_flyer_number':True}
            
            if search_details["journey_type"] =="One Way":
                date = "".join(search_details["journey_details"][0]["travel_date"].split('-')[:2])
                flightSegment = search_details["journey_details"][0]["source_city"]+"_"+search_details["journey_details"][0]["destination_city"]+"_"+date
                segment_id = segment_data['segment_id']
                fare_id = segment_data['fare_id']
                extracted_segment = raw_data
                TraceId = extracted_segment['TraceId']
                ResultIndex = extracted_segment['ResultIndex']
                fare_quote_response = fare_quote(baseurl=self.base_url,credentials=self.credentials,
                                                TraceId=TraceId,ResultIndex=ResultIndex,session_id=session_id)
                if fare_quote_response['Response']['ResponseStatus'] == 1:
                    updated = True
                    vendor_data = fare_quote_response
                    IsPriceChanged = fare_quote_response['Response']['IsPriceChanged']
                    FlightDetailChangeInfo = fare_quote_response['Response']['FlightDetailChangeInfo']
                    is_gst_mandatory = fare_quote_response['Response']["Results"].get("IsGSTMandatory",False)
                    info = ""
                    if IsPriceChanged == True:
                        info = "Airline Price Change Detected."
                    if FlightDetailChangeInfo != None:
                        info = info + str(FlightDetailChangeInfo)+" Value Change Detected."
                    if info != "":
                        info += " Please refer to the updated details."    
                    fareDetails = {}
                    result = {}
                    result['fare_id'] = fare_id
                    calculated_fares = calculate_fares(fare_quote_response['Response']['Results']["Fare"]["PublishedFare"],
                                                    fare_quote_response['Response']['Results']["Fare"]["OfferedFare"],
                                                    fare_adjustment,tax_condition,total_pax_count)
                    result['publishedFare'] = calculated_fares["published_fare"]
                    result['offeredFare'] = calculated_fares["offered_fare"]
                    result["supplier_publishFare"] = calculated_fares["supplier_published_fare"]
                    result["supplier_offerFare"] = calculated_fares["supplier_offered_fare"]
                    result["Discount"] = calculated_fares["discount"]
                    result['fareType'] = fare_quote_response['Response']['Results'].get('FareClassification',{}).get("Type","N/A")
                    if not result['fareType']:
                        result['fareType'] = 'N/A'
                    result['currency'] = fare_quote_response['Response']['Results']['Fare']['Currency']
                    result['colour'] = "Peach"
                    result['fareBreakdown'] = get_fareBreakdown(fare_quote_response['Response']['Results']['FareBreakdown'],
                                                                calculated_fares["published_fare"],search_details["passenger_details"])
                    result['isRefundable'] = fare_quote_response['Response']['Results']['IsRefundable']
                    fareDetails[flightSegment] = result
                    unified_seg = {"itineraries":[flightSegment],flightSegment:[],"fareDetails":fareDetails}
                    flight_legs = vendor_data["Response"]["Results"]["Segments"]
                    for flight_leg in flight_legs:
                        unified_structure = unify_seg_quote(flight_leg,flightSegment,IsPriceChanged,
                                                            vendor_data["Response"]["Results"]['FareRules'][0]['FareBasisCode'])
                        unified_structure["segmentID"] = segment_id
                        # calculated_fares = calculate_fares(vendor_data["Response"]["Results"]["Fare"]["PublishedFare"],
                        #                                 vendor_data["Response"]["Results"]["Fare"]["OfferedFare"],
                        #                                 fare_adjustment,tax_condition,total_pax_count)
                        # unified_structure["publishFare"] = calculated_fares["published_fare"]
                        # unified_structure["offerFare"] = calculated_fares["offered_fare"]
                        # unified_structure["Discount"] = calculated_fares["discount"]
                        # unified_structure["supplier_publishFare"] = calculated_fares["supplier_published_fare"]
                        # unified_structure["supplier_offerFare"] = calculated_fares["supplier_offered_fare"]
                        # unified_structure["currency"] = vendor_data["Response"]["Results"]["Fare"]["Currency"]
                        unified_seg[flightSegment] = unified_structure
                else:
                    IsPriceChanged = False
                    updated = False
                    is_gst_mandatory = False
                misc_data = {"TraceId":TraceId,"ResultIndex":ResultIndex} 
                misc_doc = {"session_id":session_id,"segment_id":segment_id,"data":misc_data,
                            "createdAt":datetime.now(),"type":"misc"}
                self.mongo_client.searches.insert_one(misc_doc)
                return {"updated":updated,"data":unified_seg,"raw":fare_quote_response,"status":"success",
                        "IsPriceChanged":IsPriceChanged,"is_gst_mandatory" :is_gst_mandatory,'frequent_flyer_number':True} \
                    if updated else {"updated":updated,"status":"failure","raw":fare_quote_response,
                        "IsPriceChanged":IsPriceChanged,"is_gst_mandatory":is_gst_mandatory,'frequent_flyer_number':True}

            elif search_details["journey_type"] =="Round Trip" and search_details["flight_type"] == "INT":
                unified_seg = {}
                fs = []
                for journey_details in search_details['journey_details']:
                    date = "".join(journey_details["travel_date"].split('-')[:2])
                    flightSegment = journey_details["source_city"]+"_"+journey_details["destination_city"]+"_"+date
                    fs.append(flightSegment)
                flightSegment = "_R_".join(fs)
                extracted_segment = raw_data
                fare_id = segment_data['fare_id']
                segment_id = segment_data['segment_id']
                TraceId = extracted_segment['TraceId']
                ResultIndex = extracted_segment['ResultIndex']
                fare_quote_response = fare_quote(baseurl=self.base_url,credentials=self.credentials,
                                                TraceId=TraceId,ResultIndex=ResultIndex,session_id=session_id)
                if fare_quote_response['Response']['ResponseStatus'] == 1:
                    updated = True
                    vendor_data = fare_quote_response
                    IsPriceChanged = fare_quote_response['Response']['IsPriceChanged']
                    FlightDetailChangeInfo = fare_quote_response['Response']['FlightDetailChangeInfo']
                    info = ""
                    if IsPriceChanged == True:
                        info = "Airline Price Change Detected."
                    if FlightDetailChangeInfo != None:
                        info = info + str(FlightDetailChangeInfo)+" Value Change Detected."
                    if info != "":
                        info += " Please refer to the updated details."
                    fareDetails = {}
                    result = {}
                    is_gst_mandatory = fare_quote_response['Response']["Results"].get("IsGSTMandatory",False)
                    result['fare_id'] = fare_id
                    calculated_fares = calculate_fares(fare_quote_response['Response']['Results']["Fare"]["PublishedFare"],
                                                    fare_quote_response['Response']['Results']["Fare"]["OfferedFare"],
                                                    fare_adjustment,tax_condition,total_pax_count)
                    result['publishedFare'] = calculated_fares["published_fare"]
                    result['offeredFare'] = calculated_fares["offered_fare"]
                    result["supplier_publishFare"] = calculated_fares["supplier_published_fare"]
                    result["supplier_offerFare"] = calculated_fares["supplier_offered_fare"]
                    result["Discount"] = calculated_fares["discount"]
                    result['fareType'] = fare_quote_response['Response']['Results'].get('FareClassification',{}).get("Type","N/A")
                    if not result['fareType']:
                        result['fareType'] = 'N/A'
                    result['currency'] = fare_quote_response['Response']['Results']['Fare']['Currency']
                    result['colour'] = "Peach"
                    result['fareBreakdown'] = get_fareBreakdown(fare_quote_response['Response']['Results']['FareBreakdown'],
                                                                calculated_fares["published_fare"],search_details["passenger_details"])
                    result['isRefundable'] = fare_quote_response['Response']['Results']['IsRefundable']
                    fareDetails[flightSegment] = result
                    unified_seg = {"itineraries":[flightSegment],"fareDetails":fareDetails,flightSegment:{}}
                    flight_legs = vendor_data["Response"]["Results"]["Segments"]
                    out = {"flightSegments": {}}
                    for flight_leg in flight_legs:
                        unified_structure = unify_seg_quote(flight_leg,flightSegment.split("_R_")[flight_legs.index(flight_leg)],IsPriceChanged,vendor_data["Response"]["Results"]['FareRules'][0]['FareBasisCode'])
                        out['flightSegments'].update(unified_structure['flightSegments'])
                    
                    unified_seg[flightSegment]["segmentID"] = segment_id
                    # calculated_fares = calculate_fares(vendor_data["Response"]["Results"]["Fare"]["PublishedFare"],
                    #                                 vendor_data["Response"]["Results"]["Fare"]["OfferedFare"],
                    #                                 fare_adjustment,tax_condition,total_pax_count)
                    # unified_seg[flightSegment]["publishFare"] = calculated_fares["published_fare"]
                    # unified_seg[flightSegment]["offerFare"] = calculated_fares["offered_fare"]
                    # unified_seg[flightSegment]["Discount"] = calculated_fares["discount"]
                    # unified_seg[flightSegment]["supplier_publishFare"] = calculated_fares["supplier_published_fare"]
                    # unified_seg[flightSegment]["supplier_offerFare"] = calculated_fares["supplier_offered_fare"]
                    # unified_seg[flightSegment]["currency"] = vendor_data["Response"]["Results"]["Fare"]["Currency"]
                    unified_seg[flightSegment]['flightSegments'] = out['flightSegments']
                else:
                    updated = False
                    IsPriceChanged = False
                    is_gst_mandatory = False
                misc_data = {"TraceId":TraceId,"ResultIndex":ResultIndex} 
                misc_doc = {"session_id":session_id,"segment_id":segment_id,"data":misc_data,
                            "createdAt":datetime.now(),"type":"misc"}
                self.mongo_client.searches.insert_one(misc_doc)
                return {"updated":updated,"data":unified_seg,"raw":fare_quote_response,"status":"success",
                        "IsPriceChanged":IsPriceChanged,"is_gst_mandatory":is_gst_mandatory,'frequent_flyer_number':True}\
                    if updated else {"updated":updated,"status":"failure","raw":fare_quote_response,
                            "IsPriceChanged":IsPriceChanged,"is_gst_mandatory":is_gst_mandatory,'frequent_flyer_number':True}
        except Exception as e:
            error = tb.format_exc()
            self.mongo_client.flight_supplier.insert_one({"vendor":"TBO","error":error,"type":"air_pricing",
                                                            "createdAt": datetime.now(),"session_id":session_id})
            return {"updated":False,"status":"failure","close":True,"IsPriceChanged":False,"raw":str(e)}
    
    def get_ssr(self, **kwargs):
        extracted_segment = kwargs["raw_data"]
        TraceId = extracted_segment['TraceId']
        ResultIndex = extracted_segment['ResultIndex']
        session_id = kwargs.get("session_id")
        ssr_response = ssr(self.base_url,self.credentials,TraceId,ResultIndex,session_id)
        flightSegment = kwargs["segment_key"]
        aisle_seats = [2,10,11,12,13,14,15,31,32,33,34,36,37,38,46,47,49,54,55,56,57,58,59,60,61]
        flight_ssr_response = {flightSegment:[]}
        status = True
        def find_seat_dynamic(ssr_response,journey_segment):
            Origin,Destination = journey_segment.split("-")
            for seat_dynamics in ssr_response['Response']['SeatDynamic']:
                for seat_dynamic in seat_dynamics['SegmentSeat']:
                    if (seat_dynamic['RowSeats'][0]['Seats'][0]['Origin'] == Origin and
                        seat_dynamic['RowSeats'][0]['Seats'][0]['Destination'] == Destination):
                        return seat_dynamic
                    else:
                        continue
            return None
        if "_R_" not in flightSegment:
            try:
                if ssr_response['Response']['ResponseStatus'] == 1:
                    status = True
                    if "Baggage" in ssr_response['Response']:
                        for idx, seg in enumerate(extracted_segment["Segments"][0]):
                            journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                            try:
                                baggage_master = ssr_response['Response']['Baggage'][idx]
                            except:
                                baggage_dict = {"is_baggage":False,"baggage_ssr":{"adults":[],"children":[]},"Currency": "INR"}
                                baggage_dict["journey_segment"] = journey_segment
                                flight_ssr_response[flightSegment].append(baggage_dict)
                                continue
                            try:
                                if len(baggage_master) >0:
                                    result = []
                                    baggage_ssr = {"adults":[],"children":[]}
                                    for baggage in baggage_master:
                                        out = {}
                                        if "Text" in baggage:
                                            replacements = {str(baggage["Weight"]): "","KG": ""}
                                            baggage["Text"] = replace_multiple_case_insensitive(baggage["Text"], replacements)
                                        else:
                                            baggage["Text"] = ""
                                        out["Code"] = baggage["Code"]
                                        out["Weight"] =  baggage["Weight"]  
                                        out["Unit"] = "KG" + baggage["Text"]
                                        out["Price"] = baggage["Price"]
                                        out['Description'] = baggage['Description']
                                        result.append(out)
                                    baggage_ssr["adults"] = result
                                    baggage_ssr["children"] = result
                                    baggage_dict = {"is_baggage":True,"baggage_ssr":baggage_ssr,"Currency": baggage["Currency"]}
                                    baggage_dict["journey_segment"] = journey_segment
                                    flight_ssr_response[flightSegment].append(baggage_dict)
                                else:
                                    baggage_dict = {"is_baggage":False,"baggage_ssr":{"adults":[],"children":[]},"Currency": "INR"}
                                    baggage_dict["journey_segment"] = journey_segment
                                    flight_ssr_response[flightSegment].append(baggage_dict)
                            except:
                                baggage_dict = {"is_baggage":False,"baggage_ssr":{"adults":[],"children":[]},"Currency": "INR"}
                                baggage_dict["journey_segment"] = journey_segment
                                flight_ssr_response[flightSegment].append(baggage_dict)
                    else:
                        for idx, seg in enumerate(extracted_segment["Segments"][0]):
                            journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                            baggage_dict = {"is_baggage":False,"baggage_ssr":{"adults":[],"children":[]},"Currency": "INR"}
                            baggage_dict["journey_segment"] = journey_segment
                            flight_ssr_response[flightSegment].append(baggage_dict)
                    try:
                        if "MealDynamic" in ssr_response['Response']:
                            for idx, seg in enumerate(extracted_segment["Segments"][0]):
                                journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                try:
                                    meal_master = ssr_response['Response']['MealDynamic'][0]
                                    meal_master = [ x for x in meal_master if x['FlightNumber'] == seg['Airline']['FlightNumber']]
                                except:
                                    meal_dict = {"is_meals":False,"meals_ssr":{"adults":[],"children":[]}}
                                    meal_dict["journey_segment"] = journey_segment
                                    flight_ssr_response[flightSegment].append(meal_dict)
                                    continue
                                if len(meal_master) >0:
                                    result = []
                                    meals_ssr = {"adults":[],"children":[]}
                                    for meal in meal_master:
                                        out = {}
                                        out["Code"] = meal["Code"]
                                        out["Description"] = meal["AirlineDescription"]
                                        out["Quantity"] = meal["Quantity"]
                                        out["Price"] = meal["Price"]
                                        result.append(out)
                                    meals_ssr["adults"] = result
                                    meals_ssr["children"] = result
                                    meal_dict = {"is_meals":True,"meals_ssr":meals_ssr}
                                    meal_dict["journey_segment"] = journey_segment
                                    flight_ssr_response[flightSegment].append(meal_dict)
                                else:
                                    meal_dict = {"is_meals":False,"meals_ssr":{"adults":[],"children":[]}}
                                    meal_dict["journey_segment"] = journey_segment
                                    flight_ssr_response[flightSegment].append(meal_dict)
                        else:
                            if 'Meal' in ssr_response['Response']:
                                if len(ssr_response['Response']['Meal']) >0:
                                    for idx, seg in enumerate(extracted_segment["Segments"][0]):
                                        journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']

                                        meal_master = ssr_response['Response']['Meal']
                                        result = []
                                        meals_ssr = {"adults":[],"children":[]}
                                        for meal in meal_master:
                                            out = {}
                                            out["Code"] = meal["Code"]
                                            out["Description"] = meal["Description"]
                                            out["Quantity"] = meal.get("Quantity",1)
                                            out["Price"] = meal.get("Price",0)
                                            result.append(out)
                                        meals_ssr["adults"] = result
                                        meals_ssr["children"] = result
                                        meal_dict = {"is_meals":True,"meals_ssr":meals_ssr}
                                        meal_dict["journey_segment"] = journey_segment
                                        flight_ssr_response[flightSegment].append(meal_dict)
                                else:
                                    for idx, seg in enumerate(extracted_segment["Segments"][0]):
                                        journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                        meal_dict = {"is_meals":False,"meals_ssr":{"adults":[],"children":[]}}
                                        meal_dict["journey_segment"] = journey_segment
                                        flight_ssr_response[flightSegment].append(meal_dict)
                            else:
                                for idx, seg in enumerate(extracted_segment["Segments"][0]):
                                    journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                    meal_dict = {"is_meals":False,"meals_ssr":{"adults":[],"children":[]}}
                                    meal_dict["journey_segment"] = journey_segment
                                    flight_ssr_response[flightSegment].append(meal_dict)
                    except:
                        for idx, seg in enumerate(extracted_segment["Segments"][0]):
                            journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                            meal_dict = {"is_meals":False,"meals_ssr":{"adults":[],"children":[]}}
                            meal_dict["journey_segment"] = journey_segment
                            flight_ssr_response[flightSegment].append(meal_dict)
                    try:
                        if len(ssr_response['Response']['SeatDynamic'][0]) >0:
                            for idx, seg in enumerate(extracted_segment["Segments"][0]):
                                journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                try:
                                    seat_master = ssr_response['Response']['SeatDynamic'][0]['SegmentSeat'][idx]
                                except:
                                    seat_dict = {"is_seats":False,"seats_ssr":[]}
                                    seat_dict["journey_segment"] = journey_segment
                                    flight_ssr_response[flightSegment].append(seat_dict)
                                    continue
                                result = []
                                seats_ssr = {"adults":{},"children":{}}
                                for index,seat in enumerate(seat_master['RowSeats']):
                                    out = {"row":index}
                                    row_out = []
                                    for idx,row_seat in enumerate(seat['Seats']):
                                        row_seat_out = {}
                                        if row_seat['AvailablityType'] in [0,48,50,51,52,53]:
                                            row_out.append({"seatType": -1})
                                        else:
                                            row_seat_out["Code"] = row_seat["Code"]
                                            if row_seat['AvailablityType'] != 1:
                                                row_seat_out["isBooked"] = True
                                            else:
                                                row_seat_out["isBooked"] = False
                                            row_seat_out["Price"] = row_seat["Price"]
                                            row_seat_out["seatType"] = row_seat["SeatType"]
                                            if row_seat_out["seatType"] == 1:
                                                row_seat_out["info"] = "Window Seat"
                                            elif row_seat_out["seatType"] == 2:
                                                row_seat_out["info"] = "Aisle Seat"
                                            elif row_seat_out["seatType"] == 3:
                                                row_seat_out["info"] = "Middle Seat"
                                            else:
                                                row_seat_out["info"] = ""
                                            row_out.append(row_seat_out)
                                            if row_seat_out["seatType"] in aisle_seats:
                                                if seat['Seats'][idx+1]["SeatType"] in aisle_seats:
                                                    row_out.append({"seatType": None})

                                    out["seats"] = row_out
                                    result.append(out)
                                if len(result[0]['seats']) == 1  and result[0]['seats'][0]['seatType'] == -1:
                                    result = result[1:]
                                max_column = max([len(x['seats']) for x in result ])
                                seats_ssr["adults"]["seatmap"] = result
                                seats_ssr["adults"]["CraftType"] = seat['Seats'][0]["CraftType"]
                                seats_ssr["adults"]["seat_data"] = {"row":len(result),"column":max_column}
                                seats_ssr["children"]["seatmap"] = result
                                seats_ssr["children"]["CraftType"] = seat['Seats'][0]["CraftType"]
                                seats_ssr["children"]["seat_data"] = {"row":len(result),"column":max_column}
                                seat_dict = {"is_seats":True,"seats_ssr":seats_ssr}
                                seat_dict["journey_segment"] = journey_segment
                                flight_ssr_response[flightSegment].append(seat_dict)
            
                        else:
                            for idx, seg in enumerate(extracted_segment["Segments"][0]):
                                journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                seat_dict = {"is_seats":False,"seats_ssr":{"adults":{},"children":{}}}
                                seat_dict["journey_segment"] = journey_segment
                                flight_ssr_response[flightSegment].append(seat_dict)
                    except:
                        for idx, seg in enumerate(extracted_segment["Segments"][0]):
                            journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                            seat_dict = {"is_seats":False,"seats_ssr":{"adults":{},"children":{}}}
                            seat_dict["journey_segment"] = journey_segment
                            flight_ssr_response[flightSegment].append(seat_dict)
                else:
                    status = False

                    flight_ssr_response[flightSegment] = [{
                                                            "is_baggage": False,
                                                            "Currency": "INR",
                                                            "baggage_ssr":{"adults":[],"children":[]},
                                                            "is_meals": False,
                                                            "meals_ssr":{"adults":[],"children":[]},
                                                            "is_seats": False,
                                                            "seats_ssr":{"adults":{},"children":{}}}]
            except:
                status = False
                flight_ssr_response[flightSegment] = [{
                                                        "is_baggage": False,
                                                        "Currency": "INR",
                                                        "baggage_ssr":{"adults":[],"children":[]},
                                                        "is_meals": False,
                                                        "meals_ssr":{"adults":[],"children":[]},
                                                        "is_seats": False,
                                                        "seats_ssr":{"adults":{},"children":{}}}]
        else:
            try:
                if ssr_response['Response']['ResponseStatus'] == 1:
                    status = True
                    if "Baggage" in ssr_response['Response']:
                        for idx1, segs in enumerate(extracted_segment["Segments"]):
                            for idx, seg in enumerate(segs):
                                journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                try:
                                    baggage_master = ssr_response['Response']['Baggage'][idx]
                                except:
                                    baggage_dict = {"is_baggage":False,"baggage_ssr":{"adults":[],"children":[]},"Currency": "INR"}
                                    baggage_dict["journey_segment"] = journey_segment
                                    flight_ssr_response[flightSegment].append(baggage_dict)
                                    continue
                                try:
                                    if len(baggage_master) >0:
                                        result = []
                                        baggage_ssr = {"adults":[],"children":[]}
                                        for baggage in baggage_master:
                                            out = {}
                                            if "Text" in baggage:
                                                replacements = {str(baggage["Weight"]): "","KG": ""}
                                                baggage["Text"] = replace_multiple_case_insensitive(baggage["Text"], replacements)
                                            else:
                                                baggage["Text"] = ""
                                            out["Code"] = baggage["Code"]
                                            out["Weight"] =  baggage["Weight"]  
                                            out["Unit"] = "KG" + baggage["Text"]
                                            out["Price"] = baggage["Price"]
                                            out['Description'] = baggage['Description']
                                            result.append(out)
                                        baggage_ssr["adults"] = result
                                        baggage_ssr["children"] = result
                                        if idx == 0:
                                            baggage_dict = {"is_baggage":True,"baggage_ssr":baggage_ssr,"Currency": baggage["Currency"]}
                                        else:
                                            baggage_dict = {"is_baggage":False,"baggage_ssr":{"adults":[],"children":[]},"Currency": "INR"}
                                        baggage_dict["journey_segment"] = journey_segment
                                        flight_ssr_response[flightSegment].append(baggage_dict)
                                    else:
                                        baggage_dict = {"is_baggage":False,"baggage_ssr":{"adults":[],"children":[]},"Currency": "INR"}
                                        baggage_dict["journey_segment"] = journey_segment
                                        flight_ssr_response[flightSegment].append(baggage_dict)
                                except:
                                    baggage_dict = {"is_baggage":False,"baggage_ssr":{"adults":[],"children":[]},"Currency": "INR"}
                                    baggage_dict["journey_segment"] = journey_segment
                                    flight_ssr_response[flightSegment].append(baggage_dict)
                    else:
                        for idx1, segs in enumerate(extracted_segment["Segments"]):
                            for idx, seg in enumerate(segs):
                                journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                baggage_dict = {"is_baggage":False,"baggage_ssr":{"adults":[],"children":[]},"Currency": "INR"}
                                baggage_dict["journey_segment"] = journey_segment
                                flight_ssr_response[flightSegment].append(baggage_dict)
                    try:
                        if "MealDynamic" in ssr_response['Response']:
                            for idx1, segs in enumerate(extracted_segment["Segments"]):
                                for idx, seg in enumerate(segs):
                                    journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                    try:
                                        meal_master = ssr_response['Response']['MealDynamic'][idx1]
                                        meal_master = [ x for x in meal_master if x['FlightNumber'] == seg['Airline']['FlightNumber']]
                                    except:
                                        meal_dict = {"is_meals":False,"meals_ssr":{"adults":[],"children":[]}}
                                        meal_dict["journey_segment"] = journey_segment
                                        flight_ssr_response[flightSegment].append(meal_dict)
                                        continue
                                    if len(meal_master) >0:
                                        result = []
                                        meals_ssr = {"adults":[],"children":[]}
                                        for meal in meal_master:
                                            out = {}
                                            out["Code"] = meal["Code"]
                                            out["Description"] = meal["AirlineDescription"]
                                            out["Quantity"] = meal["Quantity"]
                                            out["Price"] = meal["Price"]
                                            result.append(out)
                                        meals_ssr["adults"] = result
                                        meals_ssr["children"] = result
                                        meal_dict = {"is_meals":True,"meals_ssr":meals_ssr}
                                        meal_dict["journey_segment"] = journey_segment
                                        flight_ssr_response[flightSegment].append(meal_dict)
                                    else:
                                        meal_dict = {"is_meals":False,"meals_ssr":{"adults":[],"children":[]}}
                                        meal_dict["journey_segment"] = journey_segment
                                        flight_ssr_response[flightSegment].append(meal_dict)
                        else:
                            if 'Meal' in ssr_response['Response']:
                                if len(ssr_response['Response']['Meal']) >0:
                                    for idx1, segs in enumerate(extracted_segment["Segments"]):
                                        for idx, seg in enumerate(segs):
                                            journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                            meal_master = ssr_response['Response']['Meal']
                                            result = []
                                            meals_ssr = {"adults":[],"children":[]}
                                            for meal in meal_master:
                                                out = {}
                                                out["Code"] = meal["Code"]
                                                out["Description"] = meal["Description"]
                                                out["Quantity"] = meal.get("Quantity",1)
                                                out["Price"] = meal.get("Price",0)
                                                result.append(out)
                                            meals_ssr["adults"] = result
                                            meals_ssr["children"] = result
                                            meal_dict = {"is_meals":True,"meals_ssr":meals_ssr}
                                            meal_dict["journey_segment"] = journey_segment
                                            flight_ssr_response[flightSegment].append(meal_dict)
                                else:
                                    for idx1, segs in enumerate(extracted_segment["Segments"]):
                                        for idx, seg in enumerate(segs):
                                            journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                            meal_dict = {"is_meals":False,"meals_ssr":{"adults":[],"children":[]}}
                                            meal_dict["journey_segment"] = journey_segment
                                            flight_ssr_response[flightSegment].append(meal_dict)
                            else:
                                for idx1, segs in enumerate(extracted_segment["Segments"]):
                                    for idx, seg in enumerate(segs):
                                        journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                        meal_dict = {"is_meals":False,"meals_ssr":{"adults":[],"children":[]}}
                                        meal_dict["journey_segment"] = journey_segment
                                        flight_ssr_response[flightSegment].append(meal_dict)
                    except:
                        for idx1, segs in enumerate(extracted_segment["Segments"]):
                            for idx, seg in enumerate(segs):
                                journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                meal_dict = {"is_meals":False,"meals_ssr":{"adults":[],"children":[]}}
                                meal_dict["journey_segment"] = journey_segment
                                flight_ssr_response[flightSegment].append(meal_dict)
                    try:
                        if 'SeatDynamic' in ssr_response['Response']:
                            for idx1, segs in enumerate(extracted_segment["Segments"]):
                                for idx, seg in enumerate(segs):
                                    journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                    seat_master = find_seat_dynamic(ssr_response,journey_segment)
                                    if seat_master == None:
                                        seat_dict = {"is_seats":False,"seats_ssr":{"adults":{},"children":{}}}
                                        seat_dict["journey_segment"] = journey_segment
                                        flight_ssr_response[flightSegment].append(seat_dict)
                                        continue
                                    else:
                                        seats_ssr = {"adults":{},"children":{}}
                                        result = []
                                        for index,seat in enumerate(seat_master['RowSeats']):
                                            out = {"row":index}
                                            row_out = []
                                            for idx,row_seat in enumerate(seat['Seats']):
                                                row_seat_out = {}
                                                if row_seat['AvailablityType']  in [0,48,50,51,52,53]:
                                                    row_out.append({"seatType": -1})
                                                else:
                                                    row_seat_out["Code"] = row_seat["Code"]
                                                    if row_seat['AvailablityType'] != 1:
                                                        row_seat_out["isBooked"] = True
                                                    else:
                                                        row_seat_out["isBooked"] = False
                                                    row_seat_out["Price"] = row_seat["Price"]
                                                    row_seat_out["seatType"] = row_seat["SeatType"]
                                                    if row_seat_out["seatType"] == 1:
                                                        row_seat_out["info"] = "Window Seat"
                                                    elif row_seat_out["seatType"] == 2:
                                                        row_seat_out["info"] = "Aisle Seat"
                                                    elif row_seat_out["seatType"] == 3:
                                                        row_seat_out["info"] = "Middle Seat"
                                                    else:
                                                        row_seat_out["info"] = ""
                                                    row_out.append(row_seat_out)
                                                    if row_seat_out["seatType"] in aisle_seats:
                                                        if seat['Seats'][idx+1]["SeatType"] in aisle_seats:
                                                            row_out.append({"seatType": None})
                                            out["seats"] = row_out
                                            result.append(out)
                                        if len(result[0]['seats']) == 1  and result[0]['seats'][0]['seatType'] == -1:
                                            result = result[1:]
                                        max_column = max([len(x['seats']) for x in result ])
                                        seats_ssr["adults"]["seatmap"] = result
                                        seats_ssr["adults"]["CraftType"] = seat['Seats'][0]["CraftType"]
                                        seats_ssr["adults"]["seat_data"] = {"row":len(result),"column":max_column}
                                        seats_ssr["children"]["seatmap"] = result
                                        seats_ssr["children"]["CraftType"] = seat['Seats'][0]["CraftType"]
                                        seats_ssr["children"]["seat_data"] = {"row":len(result),"column":max_column}
                                        seat_dict = {"is_seats":True,"seats_ssr":seats_ssr}   
                                        seat_dict["journey_segment"] = journey_segment
                                        flight_ssr_response[flightSegment].append(seat_dict)
            
                        else:
                            for idx1, segs in enumerate(extracted_segment["Segments"]):
                                for idx, seg in enumerate(segs):
                                    journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                    seat_dict = {"is_seats":False,"seats_ssr":{"adults":{},"children":{}}}
                                    seat_dict["journey_segment"] = journey_segment
                                    flight_ssr_response[flightSegment].append(seat_dict)
                    except:
                        for idx1, segs in enumerate(extracted_segment["Segments"]):
                            for idx, seg in enumerate(segs):
                                journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                                seat_dict = {"is_seats":False,"seats_ssr":{"adults":{},"children":{}}}
                                seat_dict["journey_segment"] = journey_segment
                                flight_ssr_response[flightSegment].append(seat_dict)
                else:
                    status=  False
                    flight_ssr_response[flightSegment] = [{
                                                            "is_baggage": False,
                                                            "Currency": "INR",
                                                            "baggage_ssr":{"adults":[],"children":[]},
                                                            "is_meals": False,
                                                            "meals_ssr":{"adults":[],"children":[]},
                                                            "is_seats": False,
                                                            "seats_ssr":{"adults":{},"children":{}}}]
            except:
                status = False

                flight_ssr_response[flightSegment] = [{
                                                        "is_baggage": False,
                                                        "Currency": "INR",
                                                        "baggage_ssr":{"adults":[],"children":[]},
                                                        "is_meals": False,
                                                        "meals_ssr":{"adults":[],"children":[]},
                                                        "is_seats": False,
                                                        "seats_ssr":{"adults":{},"children":{}},}]
        final_flight_ssr_response = {}
        if status:
            for key, value in flight_ssr_response.items():
                final_flight_ssr_response[key] = []
                unique_segs = list(set([ x['journey_segment'] for x in value]))
                for unique_seg in unique_segs:
                    out_dict = {}
                    for val in value:
                        if val['journey_segment'] == unique_seg:
                            out_dict = out_dict|val
                    final_flight_ssr_response[key].append(out_dict)

            segments = []
            for idx1, segs in enumerate(extracted_segment["Segments"]):
                for idx, seg in enumerate(segs):
                    journey_segment = seg['Origin']['Airport']['AirportCode']+"-"+seg['Destination']['Airport']['AirportCode']
                    segments.append(journey_segment)

            order_dict = {segment: index for index, segment in enumerate(segments)}
            sorted_data = sorted(final_flight_ssr_response[flightSegment], key=lambda x: order_dict.get(x['journey_segment'], float('inf')))

            final_flight_ssr_response[flightSegment] = sorted_data
            return {"data":final_flight_ssr_response} | {"raw":ssr_response,"status":status}
        else:
            return  {"raw":ssr_response,"status":status,"data":{flightSegment:{
                                                        "is_baggage": False,
                                                        "Currency": "INR",
                                                        "baggage_ssr":{"adults":[],"children":[]},
                                                        "is_meals": False,
                                                        "meals_ssr":{"adults":[],"children":[]},
                                                        "is_seats": False,
                                                        "seats_ssr":{"adults":{},"children":{}}}}}
    
    
    def get_fare_details(self, master_doc, raw_data, fare_details,raw_doc,segment_id,session_id):
        try:
            total_pax_count = sum(list(map(int,list(master_doc["passenger_details"].values()))))
            fare_adjustment,tax_condition= set_fare_details(fare_details)
            extracted_segment = raw_data
            fareDetails = []
            result = {}
            result['fare_id'] = create_uuid("FARE")
            result['segment_id'] = segment_id
            calculated_fares = calculate_fares(extracted_segment["Fare"]["PublishedFare"],extracted_segment["Fare"]["OfferedFare"],
                                    fare_adjustment,tax_condition,total_pax_count)
            result['publishedFare'] = calculated_fares['published_fare']
            result['offeredFare'] = calculated_fares["offered_fare"]
            result["Discount"] = calculated_fares["discount"]
            result['vendor_id'] = self.vendor_id.split("VEN-")[-1]
            result['fareType'] = extracted_segment.get('FareClassification',{}).get("Type","BTA-Fare")
            result['uiName'] = extracted_segment.get('FareClassification',{}).get("Type","BTA-Fare")
            result['currency'] = extracted_segment['Fare']['Currency']
            result['colour'] = "Peach"
            result['IsFreeMealAvailable'] = extracted_segment.get('IsFreeMealAvailable',False)
            result['transaction_id'] = extracted_segment['ResultIndex']
            result['fareBreakdown'] = get_fareBreakdown(extracted_segment['FareBreakdown'],
                                                        calculated_fares['published_fare'],master_doc["passenger_details"])
            result['isRefundable'] = extracted_segment['IsRefundable']
            checkInBag = ''
            cabinBag = ''
            for baggage_segment in extracted_segment['Segments']:
                checkInBag = checkInBag + baggage_segment[0].get("Baggage","N/A)")+ ","
                cabinBag = cabinBag + baggage_segment[0].get("CabinBaggage","N/A)") + ","
            result["baggage"] = {"checkInBag": checkInBag.strip(","), "cabinBag": cabinBag.strip(",")}
            fareDetails.append(result)
            return fareDetails,"success"
        except:
            error = tb.format_exc()
            self.mongo_client.flight_supplier.insert_one({"vendor":"TBO","error":error,"type":"get_fare_details",
                                                            "createdAt": datetime.now(),"session_id":session_id})
            return [],"failure"
    
    def check_hold(self,fare_quote,itinerary:FlightBookingItineraryDetails):
        ssr_detail = FlightBookingSSRDetails.objects.filter(itinerary=itinerary)
        data = fare_quote["Response"]["Results"]
        is_seats = any(x.is_seats for x in ssr_detail)
        is_hold = not is_seats and data.get("IsHoldAllowed", False)
        return {
            "is_hold":is_hold,
            "is_hold_ssr":data.get("IsHoldAllowedWithSSR",False),
            "info" :"Additional Services will not be applicable for Hold Booking!" if not data.get("IsHoldAllowedWithSSR",False) else  ""
                }

    def get_fare_rule(self,**kwargs):
        try:
            extracted_segment = kwargs["raw_data"]
            mini_fare_rule = extracted_segment.get("MiniFareRules","")
            session_id = kwargs["session_id"]
            TraceId = extracted_segment['TraceId']
            ResultIndex = extracted_segment['ResultIndex']
            fare_rule_response = fare_rule(self.base_url,self.credentials,
                                        TraceId,ResultIndex,session_id)
            def remove_duplicates_and_style_response(response: str) -> str:
                lines = re.split(r'(?:<br\s*/?>|\.\s*)', response)
                clean_lines = [line.strip() for line in lines if line.strip()]
                seen = set()
                unique_lines = []
                for line in clean_lines:
                    if line not in seen:
                        seen.add(line)
                        unique_lines.append(line)
                formatted_response = '<br/>'.join(unique_lines)
                return formatted_response.strip()

            if fare_rule_response !=None:
                if len(fare_rule_response['Response']['FareRules'])>0:
                    fare_rules = ""
                    for fr in fare_rule_response['Response']['FareRules']:
                        fare_rules+=("<h1>"+ fr['Origin'] + " - " + fr['Destination']+ "</h1><br>")
                        fare_rules+=(remove_duplicates_and_style_response(fr['FareRuleDetail']))
                else:
                    fare_rules = ""
            else:
                fare_rules = ""
            return fare_rules,mini_fare_rule
        except:
            return "No Fare Rule Available",""

    def hold_booking(self,**kwargs):
        itinerary = kwargs["itinerary"]
        booking = kwargs["booking"]
        try:
            booking = kwargs["booking"]
            pax_details = kwargs["pax_details"]
            ssr_details = kwargs["ssr_details"]
            is_direct_booking = kwargs.get("is_direct_booking")
            flight_booking_unified_data = FlightBookingUnifiedDetails.objects.filter(itinerary = itinerary.id).first()
            fare_details = flight_booking_unified_data.fare_quote[itinerary.itinerary_key]['Response']['Results']
            is_gst_mandatory = fare_details.get("IsGSTMandatory",False)
            ssr_response_list = flight_booking_unified_data.ssr_raw[itinerary.itinerary_key]
            TraceId = flight_booking_unified_data.misc['TraceId']
            ResultIndex = flight_booking_unified_data.misc['ResultIndex']
            isLCC_flight = fare_details.get('IsLCC')
            is_hold = not isLCC_flight if is_direct_booking else fare_details.get("IsHoldAllowed")
            if is_hold:
                Passengers = []
                booking = booking
                for idx, pax in enumerate(pax_details):
                    passenger = {}
                    passenger["FirstName"] = pax.first_name
                    passenger["LastName"] = pax.last_name
                    passenger["PaxType"] = pax_type_mapping.get(pax.pax_type, 1)
                    passenger["Title"] = "Inf" if passenger["PaxType"] == 3 else "CHD" if passenger["PaxType"] == 2 else pax.title
                    gst_details = json.loads(booking.gst_details) if booking.gst_details !="null" else {}
                    passenger["DateOfBirth"]  = format_datetime(pax.dob)
                    passenger["PassportExpiry"] = format_datetime(pax.passport_expiry)
                    passenger["PassportIssueDate"] = format_datetime(pax.passport_issue_date)
                    passenger["PassportIssueCountryCode"] = pax.passport_issue_country_code if pax.passport_issue_country_code else ""
                    passenger["Gender"] = gender_mapping.get(pax.gender, 1)
                    passenger["PassportNo"] = pax.passport
                    passenger["AddressLine1"] = pax.address_1 if pax.address_1 else gst_details.get("address_1", "Thrive Space, C.S.E.Z, 17/1684,")
                    passenger["AddressLine2"] = pax.address_2 if pax.address_2 else gst_details.get("address_2", "PO, Chittethukara, Kakkanad, Kerala 682037")
                    pax_fare_details = [x for x in fare_details['FareBreakdown'] if x['PassengerType'] == passenger["PaxType"]][0]
                    passenger["Fare"] = {
                        "BaseFare": pax_fare_details.get("BaseFare", 0)/pax_fare_details["PassengerCount"],
                        "Tax": pax_fare_details.get("Tax", 0)/pax_fare_details["PassengerCount"],
                        "YQTax": pax_fare_details.get("YQTax", 0)/pax_fare_details["PassengerCount"],
                        "AdditionalTxnFeePub": pax_fare_details.get("AdditionalTxnFeePub", 0)/pax_fare_details["PassengerCount"],
                        "AdditionalTxnFeeOfrd": pax_fare_details.get("AdditionalTxnFeeOfrd", 0)/pax_fare_details["PassengerCount"],
                        "OtherCharges": fare_details.get("OtherCharges", 0)/len(pax_details)
                    }
                    ffn = pax.frequent_flyer_number.get(itinerary.itinerary_key,{})
                    if ffn:
                        if ffn.get("frequent_flyer_number","").strip():
                            passenger["FFAirlineCode"] = ffn.get("airline_code","")
                            passenger["FFNumber"] = ffn.get("frequent_flyer_number","")
                    country = LookupCountry.objects.filter(country_code = pax.passport_issue_country_code).first()
                    contact = json.loads(booking.contact)
                    passenger["City"] = ""
                    passenger["CountryCode"] = pax.passport_issue_country_code if pax.passport_issue_country_code else \
                                                booking.user.organization.organization_country.lookup.country_code
                    passenger["CountryName"] = country.country_name if pax.passport_issue_country_code else \
                                                booking.user.organization.organization_country.lookup.country_name
                    passenger["Nationality"] = pax.passport_issue_country_code if pax.passport_issue_country_code else \
                                                booking.user.organization.organization_country.lookup.country_code
                    passenger["ContactNo"] = contact.get("phone", "")
                    passenger["Email"] = contact.get("email", "")
                    passenger["IsLeadPax"] = idx == 0
                    ssr = ssr_details.filter(pax = pax).first()
                    if ssr:
                        if ssr_response_list:
                            baggage_ssr = json.loads(ssr.baggage_ssr)
                            if baggage_ssr  !={}:
                                baggage_item = find_original_baggage_ssr(baggage_ssr,ssr_response_list)
                                if baggage_item != []:
                                    passenger["Baggage"] = baggage_item
                            meals_ssr = json.loads(ssr.meals_ssr)
                            if meals_ssr  !={}:
                                meals_item = find_original_meals_ssr(meals_ssr,ssr_response_list)
                                if meals_item:
                                    passenger["MealDynamic"] = meals_item
                            seats_ssr = json.loads(ssr.seats_ssr)
                            if seats_ssr  !={}:
                                seats_item = find_original_seats_ssr(seats_ssr,ssr_response_list)
                                if seats_item:
                                    passenger["SeatDynamic"] = seats_item
                    if is_gst_mandatory:
                        passenger["GSTCompanyAddress"] = gst_details.get("address", "")
                        passenger["GSTCompanyContactNumber"] = str(gst_details.get("phone", ""))
                        passenger["GSTCompanyName"] = gst_details.get("name", "")
                        passenger["GSTNumber"] = gst_details.get("gstNumber", "")
                        passenger["GSTCompanyEmail"] = gst_details.get("email", "")
                    Passengers.append(passenger)
                itinerary.status = "Hold-Initiated"
                itinerary.save(update_fields=["status"])
                booking.booked_at = int(time.time())
                session_id = booking.session_id
                book_response = hold(self.ticketing_url,self.credentials,
                                    TraceId,ResultIndex,Passengers,session_id)
                if book_response.get("status"):
                    if book_response["data"]['Response']['ResponseStatus'] == 1:
                        hold_booking_output = {"success": True, "response":book_response["data"],"status":True,
                                            "pnr":book_response["data"]['Response']['Response']['PNR'],
                                            "booking_id":book_response["data"]['Response']['Response']['BookingId'],
                                            "misc":{"source":book_response["data"]['Response']['Response']['FlightItinerary']['Source']},
                                            "is_web_checkin_allowed":book_response["data"]['Response']['Response']['FlightItinerary']['IsWebCheckInAllowed']}
                    hold_pnr = hold_booking_output.get("pnr","")
                    if hold_pnr.upper() == "REQUESTED" or not hold_pnr:
                        itinerary.error = "PNR not available"
                        itinerary.status = "Hold-Failed"
                    else:
                        itinerary.error = ""
                        itinerary.status = "On-Hold"
                    itinerary.airline_pnr = hold_pnr
                    itinerary.supplier_booking_id = hold_booking_output.get("booking_id")
                    itinerary.modified_at = int(time.time())
                    itinerary.misc =  json.dumps(hold_booking_output.get("misc"))
                    itinerary.save(update_fields = ["airline_pnr", "status", "supplier_booking_id","misc",
                                                    "modified_at","error"])
                if not book_response.get("status") or book_response.get("data",{}).get('Response',{}).get('ResponseStatus') != 1: 
                    hold_booking_output = {"status": False,"response":book_response["data"]}
                    error = book_response["data"].get("Response",{}).get("Error",{}).get("ErrorMessage","Hold failed from supplier side")
                    itinerary.error = error
                    itinerary.status = "Hold-Failed"
                    itinerary.modified_at = int(time.time())
                    itinerary.save(update_fields=["status","modified_at","error"])
            else:
                hold_booking_output = {"status": False,"response":"Hold not available"} 
                itinerary.status = "Hold-Unavailable"
                itinerary.error = "Hold unavailavle!"
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at","error"])
            return hold_booking_output
        except Exception as e:
            error_trace = tb.format_exc()
            error_log = {"vendor":self.name(),"session_id":booking.session_id,"status":"failure","api":"hold_error",
                          "createdAt": datetime.now(),"error":str(e),"error_trace":error_trace}
            self.mongo_client.flight_supplier.insert_one(error_log)
            itinerary.status = "Hold-Failed"
            itinerary.error = "Hold Failed"
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["status","modified_at","error"])
            return {"status":False}
    
    def release_hold(self,**kwargs):
        itinerary = kwargs["itinerary"]
        session_id = itinerary.booking.session_id
        try:
            booking_id = itinerary.supplier_booking_id
            misc = json.loads(itinerary.misc)
            source = misc.get("source")
            itinerary.status = "Release-Hold-Initiated"
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["status","modified_at"])
            release_hold_data = release_hold(self.ticketing_url,self.credentials,booking_id,source,session_id)
            if release_hold_data["data"]["Response"]["ResponseStatus"]==1:
                itinerary.status = "Hold-Released"
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at"])
                return { "itinerary_id": str(itinerary.id),"status": "success", 
                        "cancellation_status":"Ticket-Released","info":"Successfully released your booking" }
            else:
                itinerary.status = "Release-Hold-Failed"
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at"])
                return { "itinerary_id": str(itinerary.id),"status": "failure","info":"Failed to cancel Ticket", 
                        "cancellation_status":"Cancel-Ticket-Failed"}
        except Exception as e:
            error_trace = tb.format_exc()
            error_log = {"vendor":self.name(),"session_id":session_id,"status":"failure","api":"release_hold_error",
                          "createdAt": datetime.now(),"error":str(e),"error_trace":error_trace}
            self.mongo_client.flight_supplier.insert_one(error_log)
            return {"status": "failure","info":"Failed to Release Ticket"}

    def cancellation_charges(self,**kwargs):
        itinerary = kwargs["itinerary"]
        session_id = itinerary.booking.session_id
        try:
            total_additional_charge = float(kwargs.get("additional_charge",0))
            pax_data = kwargs["pax_data"]
            pax_ids = kwargs["pax_ids"]
            org_fare_details = kwargs["fare_details"]
            per_pax_additional_charge = round(total_additional_charge/len(pax_data),2)
            per_pax_cancellation_charge = round(float(org_fare_details.get("fare",{}).get("cancellation_charges",0)) \
                                            + float(org_fare_details.get("fare",{}).get("distributor_cancellation_charges",0)),2)
            booking_id = itinerary.supplier_booking_id
            total_cancellation_charge = 0
            total_refund_amount = 0
            booking_id = itinerary.supplier_booking_id
            cancellation_data = cancellation_charges(self.base_url,self.credentials,booking_id,session_id)
            if cancellation_data["data"]["Response"]["ResponseStatus"] == 1:
                cancellation_charge_paxs = cancellation_data["data"]["Response"]["CancelChargeDetails"]
                for pax_id in pax_ids:
                    fn = [name.first_name for name in pax_data if str(name.id) == pax_id][0]
                    ln = [name.last_name for name in pax_data if str(name.id)== pax_id][0]
                    full_name = fn.lower() + ln.lower()
                    for api_pax in cancellation_charge_paxs:
                        if api_pax["FirstName"].lower() + api_pax["LastName"].lower() == full_name:
                            supplier_cancellation_charge = api_pax.get("CancellationCharge",0)
                            supplier_refund_amount = api_pax.get("RefundAmount",0)
                            customer_cancellation_charge = per_pax_additional_charge + per_pax_cancellation_charge
                            total_cancellation_charge += supplier_cancellation_charge + customer_cancellation_charge
                            total_refund_amount += supplier_refund_amount
                            pax_ssr = FlightBookingSSRDetails.objects.filter(itinerary_id = itinerary.id,pax_id = pax_id).first()
                            cancellation_fee_per_pax = {"supplier_cancellation_charge":supplier_cancellation_charge,
                                                        "customer_cancellation_charge":customer_cancellation_charge + supplier_cancellation_charge}
                            pax_ssr.cancellation_fee = cancellation_fee_per_pax
                            pax_ssr.save(update_fields = ["cancellation_fee"])
                return { "status": "success",
                        "cancellation_charge": total_cancellation_charge,"refund_amount":total_refund_amount,
                        "currency":cancellation_data["data"]["Response"]["Currency"] }
            else:
                return { "status": "failure","info":"Failed to fetch Cancel Ticket Charges","currency":""}
        except Exception as e:
            error_trace = tb.format_exc()
            error_log = {"vendor":self.name(),"session_id":session_id,"status":"failure","api":"cancellation_charges_error",
                          "createdAt": datetime.now(),"error":str(e),"error_trace":error_trace}
            self.mongo_client.flight_supplier.insert_one(error_log)
            return { "status": "failure","info":"Failed to fetch Cancel Ticket Charges","currency":""}

    def cancel_ticket(self,kwargs):
        itinerary = kwargs["itinerary"]
        session_id = itinerary.booking.session_id
        try:
            misc = json.loads(itinerary.misc)
            pax_ids = kwargs["pax_ids"]
            booking_id = itinerary.supplier_booking_id
            ssr_details_all_pax = itinerary.flightbookingssrdetails_set.all()
            ssr_details_pax_wise = [ssr for ssr in ssr_details_all_pax if str(ssr.pax_id) in pax_ids]
            ssr_details_pax_wise_name = []
            journey_details = itinerary.flightbookingjourneydetails_set.all()
            cancellation_fee_dict = {}
            if len(pax_ids) == len(ssr_details_all_pax):
                is_full_trip = True
                cancel_ticket_data = cancel_ticket(self.ticketing_url,self.credentials,booking_id,
                                                [],[],is_full_trip,session_id)
            else:
                TicketId = [ssr_data.supplier_ticket_id for ssr_data in ssr_details_pax_wise]
                Sectors = [{"Origin":journey_info.source,"Destination":journey_info.destination} 
                        for journey_info in journey_details]
                is_full_trip = False
                cancel_ticket_data = cancel_ticket(self.ticketing_url,self.credentials,booking_id,
                                                TicketId,Sectors,is_full_trip,session_id)
            if cancel_ticket_data["data"]["Response"]["ResponseStatus"] == 1:
                cancellation_data = misc.get("cancellation_data",{})
                for ticket_info in cancel_ticket_data["data"]["Response"]["TicketCRInfo"]:
                    cancellation_data[ticket_info["ChangeRequestId"]] = ticket_info["TicketId"]
                misc["cancellation_data"] = cancellation_data
                itinerary.misc = json.dumps(misc)
                for paxwise_cancel in cancel_ticket_data["data"]["Response"]["TicketCRInfo"]:
                    ChangeRequestStatus = paxwise_cancel["ChangeRequestStatus"]
                    selected_pax = [pax for pax in ssr_details_pax_wise if str(pax.supplier_ticket_id) == str(paxwise_cancel["TicketId"])]
                    if selected_pax:
                        if cancellation_statuses_mapping[ChangeRequestStatus] == "Completed":
                            selected_pax[0].cancellation_status = "Cancelled"
                            cancelled_pax_name = selected_pax[0].pax.first_name + " " +  selected_pax[0].pax.last_name
                            cancellation_pax_fee = selected_pax[0].cancellation_fee
                            cancellation_fee_dict[cancelled_pax_name] = cancellation_pax_fee
                            ssr_details_pax_wise_name.append(cancelled_pax_name)
                        elif cancellation_statuses_mapping[ChangeRequestStatus] == "Rejcted":
                            selected_pax[0].cancellation_status = "CANCELLATION REJECTED"
                        else:
                            selected_pax[0].cancellation_status = "CANCELLATION REQUESTED"  
                        selected_pax[0].save()
                cancellation_statuses = FlightBookingSSRDetails.objects.filter(itinerary_id = itinerary.id).values_list("cancellation_status", flat = True)
                if all(cancellation_status == "Cancelled" for cancellation_status in cancellation_statuses):
                    itinerary.status = "Ticket-Released"
                else:
                    itinerary.status = "Confirmed"
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields = ["status","modified_at","misc"])
                if cancellation_fee_dict:
                    try:
                        easy_link_data = self.mongo_client.vendors.find_one({"type":"easy_link","itinerary_id":str(itinerary.id)})
                        if easy_link_data:
                            refund_manager = FinanceManager(itinerary.booking.user)
                            refund_manager.process_easylink_refund(payload = easy_link_data["payload_json"],cancellation_fee_dict = cancellation_fee_dict,
                                                                pax_names = ssr_details_pax_wise_name)
                    except Exception as e:
                        error_trace = tb.format_exc()
                        easylink_error_log = {"display_id":itinerary.booking.diaplay_id,
                            "error":str(e),
                            "error_trace":error_trace,
                            "createdAt":datetime.now(),
                            "type":"easy_link"}
                        self.mongo_client.vendors.insert_one(easylink_error_log)
                return { "status": "success",
                        "info":"Successfully submitted your cancellation Request" }
            else:
                itinerary.status = "Cancel-Ticket-Failed"
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at"])
                return { "status": "failure","info":"Failed to cancel Ticket"}
        except Exception as e:
            error_trace = tb.format_exc()
            error_log = {"vendor":self.name(),"session_id":session_id,"status":"failure","api":"cancel_ticket_error",
                          "createdAt": datetime.now(),"error":str(e),"error_trace":error_trace}
            self.mongo_client.flight_supplier.insert_one(error_log)
            return { "status": "failure","info":"Failed to Cancel Ticket","currency":""}           
        
    def check_cancellation_status(self,itinerary):
        session_id = itinerary.booking.session_id
        try:
            misc = json.loads(itinerary.misc)
            for ChangeRequestId in misc.get("cancellation_data",[]):
                supllier_ticket_id = misc["cancellation_data"][ChangeRequestId]
                cancellation_fee_dict = {}
                ssr_details_pax_wise_name = []
                pax_under_process = FlightBookingSSRDetails.objects.filter(supplier_ticket_id = str(supllier_ticket_id)).first()
                if pax_under_process.cancellation_status !="Cancelled":
                    cancellation_status = check_cancellation_status(self.ticketing_url,self.credentials,ChangeRequestId,session_id)
                    if cancellation_status["data"]["Response"]["ResponseStatus"] == 1:
                        ChangeRequestStatus = cancellation_status["data"]["Response"]["ChangeRequestStatus"]
                        if cancellation_statuses_mapping[ChangeRequestStatus] == "Completed":
                            pax_under_process.cancellation_status = "Cancelled"
                            cancelled_pax_name = pax_under_process.pax.first_name + " " +  pax_under_process.pax.last_name
                            cancellation_pax_fee = pax_under_process.cancellation_fee
                            cancellation_fee_dict[cancelled_pax_name] = cancellation_pax_fee
                            ssr_details_pax_wise_name.append(cancelled_pax_name)
                        elif cancellation_statuses_mapping[ChangeRequestStatus] == "Rejcted":
                            pax_under_process.cancellation_status = "CANCELLATION REJECTED"
                        else:
                            pax_under_process.cancellation_status = "CANCELLATION REQUESTED"  
                        pax_under_process.save()
                    if cancellation_fee_dict:
                        try:
                            easy_link_data = self.mongo_client.vendors.find_one({"type":"easy_link","itinerary_id":str(itinerary.id)})
                            if easy_link_data:
                                refund_manager = FinanceManager(itinerary.booking.user)
                                refund_manager.process_easylink_refund(payload = easy_link_data["payload_json"],cancellation_fee_dict = cancellation_fee_dict,
                                                                    pax_names = ssr_details_pax_wise_name)
                        except Exception as e:
                            error_trace = tb.format_exc()
                            easylink_error_log = {"display_id":itinerary.booking.diaplay_id,
                                "error":str(e),
                                "error_trace":error_trace,
                                "createdAt":datetime.now(),
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

    def get_repricing(self,**kwargs):
        itinerary = kwargs["itinerary"]
        fare_detail = FlightBookingFareDetails.objects.filter(itinerary=itinerary).first()
        return_data = {"is_fare_change": False,"new_fare":fare_detail.published_fare,
                       "old_fare":fare_detail.published_fare,"is_hold_continue":True,"error":None}
        return return_data

    def purchase(self,**kwargs):
        itinerary = kwargs["itinerary"]
        booking = kwargs["booking"]
        try: 
            session_id = booking.session_id
            flight_booking_unified_data = FlightBookingUnifiedDetails.objects.filter(itinerary = itinerary.id).first()
            ssr_response_list = flight_booking_unified_data.ssr_raw[itinerary.itinerary_key]
            fare_details = flight_booking_unified_data.fare_details[itinerary.itinerary_key]
            payment_details_easylink = {"new_published_fare": fare_details["publishedFare"],
                            "new_offered_fare":fare_details["offeredFare"],
                            "supplier_offered_fare":fare_details["supplier_offerFare"],
                            "supplier_published_fare":fare_details["supplier_publishFare"]}
            pax_details = kwargs["pax_details"]
            ssr_details = kwargs["ssr_details"]
            if itinerary.status == "Enquiry" :
                kwargs["is_direct_booking"] = True
                hold_out = self.hold_booking(**kwargs)
                itinerary = FlightBookingItineraryDetails.objects.filter(id = itinerary.id).first()
            pnr = itinerary.airline_pnr
            booking_id = itinerary.supplier_booking_id
            fare_details = flight_booking_unified_data.fare_quote[itinerary.itinerary_key]['Response']['Results']
            is_gst_mandatory = fare_details.get("IsGSTMandatory",False)
            TraceId = flight_booking_unified_data.misc['TraceId']
            ResultIndex = flight_booking_unified_data.misc['ResultIndex']
            ticket_response = {"status":False,"data":{}}
            isLCC_flight = fare_details.get('IsLCC')
            if isLCC_flight and not kwargs.get("is_convert_to_hold"):
                Passengers = []
                booking = booking
                for idx, pax in enumerate(pax_details):
                    passenger = {}
                    passenger["FirstName"] = pax.first_name
                    passenger["LastName"] = pax.last_name
                    passenger["PaxType"] = pax_type_mapping.get(pax.pax_type, 1)
                    passenger["Title"] = "Inf" if passenger["PaxType"] == 3 else "CHD" if passenger["PaxType"] == 2 else pax.title
                    gst_details = json.loads(booking.gst_details)
                    if not gst_details:
                        gst_details = {}
                    ffn = pax.frequent_flyer_number.get(itinerary.itinerary_key,{})
                    if ffn:
                        if ffn.get("frequent_flyer_number","").strip():
                            passenger["FFAirlineCode"] = ffn.get("airline_code","")
                            passenger["FFNumber"] = ffn.get("frequent_flyer_number","")
                    passenger["DateOfBirth"]  = format_datetime(pax.dob)
                    passenger["PassportExpiry"] = format_datetime(pax.passport_expiry)
                    passenger["PassportIssueDate"] = format_datetime(pax.passport_issue_date)
                    passenger["PassportIssueCountryCode"] = pax.passport_issue_country_code if pax.passport_issue_country_code else ""
                    passenger["Gender"] = gender_mapping.get(pax.gender, 1)
                    passenger["PassportNo"] = pax.passport
                    passenger["AddressLine1"] = pax.address_1 if pax.address_1 else gst_details.get("address_1", "Thrive Space, C.S.E.Z, 17/1684,") if gst_details else "Thrive Space, C.S.E.Z, 17/1684,"
                    passenger["AddressLine2"] = pax.address_2 if pax.address_2 else gst_details.get("address_2", "PO, Chittethukara, Kakkanad, Kerala 682037") if gst_details else "PO, Chittethukara, Kakkanad, Kerala 682037"
                    pax_fare_details = [x for x in fare_details['FareBreakdown'] if x['PassengerType'] == passenger["PaxType"]][0]
                    passenger["Fare"] = {
                        "BaseFare": pax_fare_details.get("BaseFare", 0)/pax_fare_details["PassengerCount"],
                        "Tax": pax_fare_details.get("Tax", 0)/pax_fare_details["PassengerCount"],
                        "YQTax": pax_fare_details.get("YQTax", 0)/pax_fare_details["PassengerCount"],
                        "AdditionalTxnFeePub": pax_fare_details.get("AdditionalTxnFeePub", 0)/pax_fare_details["PassengerCount"],
                        "AdditionalTxnFeeOfrd": pax_fare_details.get("AdditionalTxnFeeOfrd", 0)/pax_fare_details["PassengerCount"],
                        "OtherCharges": fare_details.get("OtherCharges", 0)/len(pax_details)
                    }
                    country = LookupCountry.objects.filter(country_code = pax.passport_issue_country_code).first()
                    contact = json.loads(booking.contact)
                    passenger["City"] = ""
                    passenger["CountryCode"] = pax.passport_issue_country_code if pax.passport_issue_country_code else \
                                                booking.user.organization.organization_country.lookup.country_code
                    passenger["CountryName"] = country.country_name if pax.passport_issue_country_code else  \
                                                booking.user.organization.organization_country.lookup.country_name
                    passenger["Nationality"] = pax.passport_issue_country_code if pax.passport_issue_country_code else \
                                                booking.user.organization.organization_country.lookup.country_code
                    passenger["ContactNo"] = contact.get("phone", "")
                    passenger["Email"] = contact.get("email", "")
                    passenger["IsLeadPax"] = idx == 0
                    ssr = ssr_details.filter(pax = pax).first()
                    if ssr_response_list:
                        baggage_ssr = json.loads(ssr.baggage_ssr)
                        if baggage_ssr  !={}:
                            baggage_item = find_original_baggage_ssr(baggage_ssr,ssr_response_list)
                            if baggage_item:
                                passenger["Baggage"] = baggage_item
                        meals_ssr = json.loads(ssr.meals_ssr)
                        if meals_ssr  !={}:
                            meals_item = find_original_meals_ssr(meals_ssr,ssr_response_list)
                            if meals_item:
                                passenger["MealDynamic"] = meals_item
                        seats_ssr = json.loads(ssr.seats_ssr)
                        if seats_ssr  !={}:
                            seats_item = find_original_seats_ssr(seats_ssr,ssr_response_list)
                            if seats_item:
                                passenger["SeatDynamic"] = seats_item
                    if is_gst_mandatory:
                        passenger["GSTCompanyAddress"] = gst_details.get("address", "")
                        passenger["GSTCompanyContactNumber"] = str(gst_details.get("phone", ""))
                        passenger["GSTCompanyName"] = gst_details.get("name", "")
                        passenger["GSTNumber"] = gst_details.get("gstNumber", "")
                        passenger["GSTCompanyEmail"] = gst_details.get("email", "")
                    Passengers.append(passenger)
                itinerary.status = "Ticketing-Initiated"
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at"])
                ticket_response = ticket_lcc(baseurl=self.ticketing_url,credentials=self.credentials,
                                            TraceId=TraceId,ResultIndex=ResultIndex,Passengers=Passengers,session_id= session_id)
            else:
                if itinerary.status in ("On-Hold","Hold-Unavailable"):
                    itinerary.status = "Ticketing-Initiated"
                    itinerary.modified_at = int(time.time())
                    itinerary.save(update_fields=["status","modified_at"])
                    ticket_response = ticket(baseurl=self.ticketing_url,credentials=self.credentials,
                                            TraceId=TraceId,ResultIndex=ResultIndex,pnr=pnr,bookingId=booking_id,session_id=session_id)  
            if ticket_response.get("status"):
                soft_error = ""
                is_soft_ticket_num = False
                is_soft_pnr = False
                to_easylink = True
                if ticket_response["data"]['Response']['ResponseStatus'] == 1:
                    passengers = ticket_response["data"]['Response']['Response']['FlightItinerary']['Passenger']
                    PNR = ticket_response.get("data",{}).get('Response',{}).get('Response',{}).get('PNR',"")
                    bookingId = ticket_response.get("data",{}).get('Response',{}).get('Response',{}).get('BookingId',"")
                    ticket_status = self.generate_ticket_status(ticket_response.get("data",{}).get('Response',{}).get('Response',{}).get('TicketStatus',-1))
                    if ticket_status:
                        if PNR.upper() == "REQUESTED":
                            is_soft_pnr = True
                            response = {"status":False}
                        else:
                            pax_details = []
                            for x in passengers:
                                ticket_id = x.get('Ticket',{}).get('TicketId',"") if x.get('Ticket') else ""
                                ticket_number = x.get('Ticket',{}).get('TicketNumber',"") if x.get('Ticket') else ""
                                if not ticket_number:
                                    is_soft_ticket_num = True
                                pax_data = {"pax_id":x.get('PaxId'),
                                            "first_name":x.get('FirstName'),
                                            "last_name":x.get('LastName'),
                                            "ticket_id":ticket_id,
                                            "ticket_number":ticket_number
                                            }
                                pax_details.append(pax_data)
                            invoice = ticket_response["data"]['Response']['Response']['FlightItinerary'].get('Invoice',{})
                            if isinstance(invoice,list):
                                if len(invoice) == 1:
                                    invoice = invoice[0]
                            response = {"success": True, "pnr":PNR,
                                        "is_web_checkin_allowed":ticket_response["data"]['Response']['Response']['FlightItinerary']['IsWebCheckInAllowed'],
                                        "misc":{"source":ticket_response["data"]['Response']['Response']['FlightItinerary']['Source']},
                                        'pax_details':pax_details,
                                        "invoice_id":invoice.get('InvoiceId',""),
                                        "invoice_number":invoice.get('InvoiceNo',""),
                                        "invoice_amount":invoice.get('InvoiceAmount',0),
                                        "status":True,
                                        }
                    else:
                        itinerary.airline_pnr = PNR
                        itinerary.status = "Ticketing-Failed"
                        itinerary.modified_at = int(time.time())
                        itinerary.error = ticket_response.get("data",{}).get("Response",{}).get("Error",{}).get("ErrorMessage",
                                                                                                         "Ticketing failed from supplier side")
                        itinerary.save(update_fields= ["status","modified_at","error","airline_pnr"])
                        response = {"status": False}
                else:
                    response = {"status": False}
                if response.get("success"):
                    if is_soft_ticket_num:
                        if not isLCC_flight:
                            itinerary.status = "Ticketing-Failed"
                            itinerary.soft_fail = True
                            to_easylink = False
                            soft_error = "Ticket number not available!"
                        else:
                            itinerary.status = "Confirmed"
                            itinerary.soft_fail  = False 
                    else:
                        itinerary.status = "Confirmed"
                        itinerary.soft_fail  = False
                    itinerary.error = soft_error
                    itinerary.modified_at = int(time.time())
                    itinerary.misc = json.dumps(response.get("misc"))
                    itinerary.supplier_booking_id = bookingId
                    itinerary.airline_pnr = response.get("pnr")
                    itinerary.invoice_id = response.get("invoice_id")
                    itinerary.invoice_number = response.get("invoice_number")
                    itinerary.invoice_amount = response.get("invoice_amount")
                    itinerary.save(update_fields=["airline_pnr", "status", "supplier_booking_id", "error","soft_fail",
                                                "invoice_id", "invoice_number", "invoice_amount","misc","modified_at"])
                    for x in ssr_details.filter(itinerary=itinerary):
                        first_name = x.pax.first_name
                        last_name = x.pax.last_name
                        for y in response.get("pax_details", []):
                            if y.get("first_name") == first_name and y.get("last_name") == last_name:
                                x.supplier_pax_id = y.get("pax_id")
                                x.supplier_ticket_id = y.get("ticket_id")
                                x.supplier_ticket_number = y.get("ticket_number")
                                x.save()
                    try:
                        if to_easylink:
                            finance_manager = FinanceManager(booking.user)
                            finance_manager.book_tbo(ticket_response["data"],itinerary,self.credentials,payment_details_easylink,
                                                    len(kwargs["pax_details"]),soft_fail = False)
                            new_published_fare = booking.payment_details.new_published_fare if booking.payment_details.new_published_fare else 0
                            ssr_price = booking.payment_details.ssr_price if booking.payment_details.ssr_price else 0
                            total_fare = round(float(new_published_fare) + float(ssr_price),2)
                            self.update_credit(booking = booking,total_fare = total_fare)
                    except Exception as e:
                        error_trace = tb.format_exc()
                        easylink_error_log = {"display_id":booking.display_id,
                            "error":str(e),
                            "error_trace":error_trace,
                            "createdAt":datetime.now(),
                            "type":"easy_link"}
                        self.mongo_client.vendors.insert_one(easylink_error_log)
                else:
                    itinerary.status = "Ticketing-Failed"
                    itinerary.modified_at = int(time.time())
                    itinerary.supplier_booking_id = bookingId
                    if is_soft_pnr:
                        itinerary.error = "PNR not available!"
                        itinerary.soft_fail = True
                        response["status"] = True
                    else:
                        error = ticket_response["data"].get("Response",{}).get("Error",{}).get("ErrorMessage","Ticketing failed from supplier side")
                        itinerary.soft_fail = False
                        itinerary.error = error
                    itinerary.save(update_fields=["status","modified_at","error","soft_fail","supplier_booking_id"])
                return response
            else:
                error = ticket_response["data"].get("Response",{}).get("Error",{}).get("ErrorMessage","Ticketing failed from supplier side")
                itinerary.status = "Ticketing-Failed"
                itinerary.error = error
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at","error"])
                return {"status":False}
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
        
    def convert_hold_to_ticket(self,**kwargs):
        kwargs["is_convert_to_hold"] = True
        response = self.purchase(**kwargs)
        return response

    def add_uuid_to_segments(self,vendor_data,flight_type,journey_type):
        if vendor_data:
            if vendor_data.get("Response",{}).get("Results"):
                segments = vendor_data["Response"]["Results"][0]
                if journey_type =="One Way" or journey_type =="Multi City" or \
                    ( journey_type == "Round Trip" and flight_type == "DOM"):
                    
                    for segment in segments:
                        seg = str(self.vendor_id)+"_$_"+create_uuid("SEG")
                        segment["segmentID"] = seg
                elif journey_type =="Round Trip" and flight_type == "INT":
                    for segment in segments:
                        seg = str(self.vendor_id)+"_$_"+create_uuid("SEG")
                        segment["segmentID"] = seg
            return vendor_data
        else:
            return {}
    
    def find_segment_by_id(self, data, segment_id, journey_details):
        vendor_data = data.get("data")
        if journey_details["journey_type"] =="One Way":
            TraceId = vendor_data['Response']['TraceId']
            segments = vendor_data["Response"]["Results"][0]
            for segment in segments:
                if segment["segmentID"] == segment_id:
                    segment["TraceId"] = TraceId
                    return segment
        elif journey_details["journey_type"] =="Multi City" or \
            (journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "DOM"):
            segment_keys = create_segment_keys(journey_details)
            for journey in segment_keys:
                TraceId = vendor_data[journey]['Response']['TraceId']
                segments = vendor_data[journey]["Response"]["Results"][0]
                for segment in segments:
                    if segment["segmentID"] == segment_id:
                        segment["TraceId"] = TraceId
                        return segment
        elif journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "INT":
            TraceId = vendor_data['Response']['TraceId']
            segments = vendor_data["Response"]["Results"][0]
            for segment in segments:
                if segment["segmentID"] == segment_id:
                    segment["TraceId"] = TraceId
                    return segment
        return None
    
    def converter(self, search_response, journey_details,fare_details):
        book_filters = self.booking_filters({"journey_type":journey_details["journey_type"],"flight_type":journey_details["flight_type"],
                                             "supplier_id":str(self.vendor_id),"fare_type":journey_details.get("fare_type")}) 
        lcc_filter = book_filters.get("is_lcc",False)
        gds_filter = book_filters.get("is_gds",False)
        total_pax_count = sum(list(map(int,list(journey_details["passenger_details"].values()))))
        fare_adjustment,tax_condition= set_fare_details(fare_details)
        if journey_details["journey_type"] =="Multi City" or \
            (journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "DOM"):
            segment_keys = create_segment_keys(journey_details)
            result = {"itineraries":segment_keys}
            for flightSegment in segment_keys:
                single_response = search_response[flightSegment]
                result[flightSegment] = []
                if single_response.get("Response",{}).get("Results"):
                    for segments in single_response["Response"]["Results"]:
                        for segment in segments:
                            for flight_segments in segment["Segments"]:
                                unified_structure = unify_seg(flight_segments,flightSegment,segment)
                                unified_structure["default_baggage"] = {flightSegment:{}}
                                unified_structure["segmentID"] = segment["segmentID"]
                                calculated_fares = calculate_fares(segment["Fare"]["PublishedFare"],segment["Fare"]["OfferedFare"],
                                                                    fare_adjustment,tax_condition,total_pax_count)
                                unified_structure["publishFare"] = calculated_fares["published_fare"]
                                unified_structure["offerFare"] = calculated_fares["offered_fare"]
                                unified_structure["Discount"] = calculated_fares["discount"]
                                unified_structure["currency"] = segment["Fare"]["Currency"]
                                unified_structure["IsLCC"] = segment["IsLCC"]
                                unified_structure["isRefundable"] = segment["IsRefundable"]
                                unified_structure["default_baggage"][flightSegment]["checkInBag"] = flight_segments[0].get("Baggage","N/A")
                                unified_structure["default_baggage"][flightSegment]["cabinBag"] = flight_segments[0].get("CabinBaggage","N/A")
                                if lcc_filter:
                                    if segment["IsLCC"]:
                                        result[flightSegment].append(unified_structure)
                                if gds_filter:
                                    if not segment["IsLCC"]:
                                        result[flightSegment].append(unified_structure)
                                if not lcc_filter and not gds_filter:
                                    pass

        elif journey_details["journey_type"] =="One Way":
            date = "".join(journey_details["journey_details"][0]["travel_date"].split('-')[:2])
            flightSegment = journey_details["journey_details"][0]["source_city"]+"_"+\
                                journey_details["journey_details"][0]["destination_city"]+"_"+date
            result = {"itineraries":[flightSegment],flightSegment:[]}
            if search_response.get("Response",{}).get("Results"):
                for segments in search_response["Response"]["Results"]:
                    for segment in segments:
                        for flight_segments in segment["Segments"]: # looping onward and return flight (here onward only)
                            unified_structure = unify_seg(flight_segments,flightSegment,segment) # will handle connection flight
                            unified_structure["default_baggage"] = {flightSegment:{}}
                            unified_structure["segmentID"] = segment["segmentID"]
                            calculated_fares = calculate_fares(segment["Fare"]["PublishedFare"],
                                                            segment["Fare"]["OfferedFare"],fare_adjustment,tax_condition,
                                                            total_pax_count)
                            unified_structure["publishFare"] = calculated_fares["published_fare"]
                            unified_structure["offerFare"] = calculated_fares["offered_fare"]
                            unified_structure["Discount"] = calculated_fares["discount"]
                            unified_structure["currency"] = segment["Fare"]["Currency"]
                            unified_structure["IsLCC"] = segment["IsLCC"]
                            unified_structure["isRefundable"] = segment["IsRefundable"]
                            unified_structure["default_baggage"][flightSegment]["checkInBag"] = flight_segments[0].get("Baggage","N/A")
                            unified_structure["default_baggage"][flightSegment]["cabinBag"] = flight_segments[0].get("CabinBaggage","N/A")
                            if lcc_filter:
                                if segment["IsLCC"]:
                                    result[flightSegment].append(unified_structure)
                            if gds_filter:
                                if not segment["IsLCC"]:
                                    result[flightSegment].append(unified_structure)
                            if not lcc_filter and not gds_filter:
                                pass

        elif journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "INT":
            fs = []
            for journey_details in journey_details['journey_details']:
                date = "".join(journey_details["travel_date"].split('-')[:2])
                flightSegment = journey_details["source_city"]+"_"+journey_details["destination_city"]+"_"+date
                fs.append(flightSegment)
            result = {"itineraries":["_R_".join(fs)],"_R_".join(fs):[]}
            main_seg_name = "_R_".join(fs)
            if search_response.get("Response",{}).get("Results"):
                segments = search_response["Response"]["Results"][0]
                for segment in segments: # looping every result of total results (say each in total of 65 results)
                    res = {"flightSegments":{},"default_baggage":{}}
                    for flight_segments in segment["Segments"]: # looping onward and return flight
                        flightSegment = fs[segment["Segments"].index(flight_segments)]
                        res["default_baggage"][flightSegment] = {}
                        unified_structure = unify_seg(flight_segments,flightSegment,segment) # will handle connection flight
                        res["default_baggage"][flightSegment]["checkInBag"] = flight_segments[0].get("Baggage","N/A")
                        res["default_baggage"][flightSegment]["cabinBag"] = flight_segments[0].get("CabinBaggage","N/A")
                        res['flightSegments'][flightSegment] = unified_structure["flightSegments"][flightSegment]
                        res["segmentID"] = segment["segmentID"]
                        calculated_fares = calculate_fares(segment["Fare"]["PublishedFare"],segment["Fare"]["OfferedFare"],
                                                            fare_adjustment,tax_condition,total_pax_count)
                        res["publishFare"] = calculated_fares["published_fare"]
                        res["offerFare"] = calculated_fares["offered_fare"]
                        res["Discount"] = calculated_fares["discount"]
                        res["currency"] = segment["Fare"]["Currency"]
                        res["IsLCC"] = segment["IsLCC"]
                        res["isRefundable"] = segment["IsRefundable"]
                    if lcc_filter:
                        if segment["IsLCC"]:
                            result[main_seg_name].append(res)
                    if gds_filter:
                            if not segment["IsLCC"]:
                                result[main_seg_name].append(res)
                    if not lcc_filter and not gds_filter:
                        pass
                    
        is_any_itinerary_empty = lambda d: any(isinstance(d[k], list) and not d[k] for k in d if k != 'itineraries')
        if is_any_itinerary_empty(result):
            result.update({k: [] for k in result if k != 'itineraries'})
        return {"data":result,"status":"success"}
    
    def generate_ticket_status(self,status):
        if int(status) in [1,5,6,8]:
            return True
        else:
            return False
    
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
        display_id = booking.display_id
        Org = booking.user.organization
        supplier_id = LookupEasyLinkSupplier.objects.filter(id= data.get("supplier")).first().supplier_id
        fare_quote =  unified_booking.fare_quote[itinerary.itinerary_key]
        try:
            finance_manager = FinanceManager(booking.user)
            finance_manager.book_failed_tbo(fare_adjustment,tax_condition,search_details,itinerary,
                                                    pax_details,booking_details,display_id,
                                                    Org.easy_link_billing_code,supplier_id,
                                                    Org.easy_link_account_name,booking.created_at,fare_quote,data_unified_dict.get(itinerary.itinerary_key).get("flightSegments"),
                                                    unified_booking_fare)
            new_published_fare = booking.payment_details.new_published_fare if booking.payment_details.new_published_fare else 0
            ssr_price = booking.payment_details.ssr_price if booking.payment_details.ssr_price else 0
            total_fare = round(float(new_published_fare) + float(ssr_price),2)
            self.update_credit(booking = booking,total_fare = total_fare)
        except Exception as e:
            error_trace = tb.format_exc()
            easylink_error_log = {"display_id":booking.display_id,
                    "error":str(e),
                    "error_trace":error_trace,
                    "createdAt":datetime.now(),
                    "type":"easy_link"}
            self.mongo_client.vendors.insert_one(easylink_error_log)

    def current_ticket_status(self,**kwargs):
        soft_deleted_itinerary = kwargs["soft_deleted_itinerary"]
        booking = soft_deleted_itinerary.booking
        session_id = booking.session_id
        display_id = booking.display_id
        try:
            invoke_status = "success"
            unified_itinerary = soft_deleted_itinerary.flightbookingunifieddetailsitinerary_set.first()
            ssr_details = soft_deleted_itinerary.flightbookingssrdetails_set.all()
            TraceId = unified_itinerary.misc['TraceId']
            updated_ticket_status = get_current_ticket_status(self.ticketing_url,self.credentials,
                                                TraceId,session_id)
            fare_details = unified_itinerary.fare_details[soft_deleted_itinerary.itinerary_key]
            payment_details_easylink = {"new_published_fare": fare_details["publishedFare"],
                        "new_offered_fare":fare_details["offeredFare"],
                        "supplier_offered_fare":fare_details["supplier_offerFare"],
                        "supplier_published_fare":fare_details["supplier_publishFare"]}
            if updated_ticket_status.get('status'):
                if updated_ticket_status.get("data",{}).get("Response",{}).get("ResponseStatus") == 1:
                    PNR = updated_ticket_status.get("data",{}).get('Response',{}).get('FlightItinerary',{}).get('PNR',"")
                    is_all_ticket_num = True
                    is_pnr = True
                    status_object  = updated_ticket_status.get("data",{}).get('Response',{}).get("FlightItinerary",{})
                    if "TicketStatus" in status_object:
                        ticket_status = status_object['TicketStatus']
                    else:
                        ticket_status = status_object['Status'] 
                    if int(ticket_status) in [1,5,6,8]:
                        if PNR.upper() == "REQUESTED" or not PNR:
                            is_pnr = False
                            invoke_status = "failure"
                        else:
                            for pax_ssr in ssr_details:
                                first_name = pax_ssr.pax.first_name.strip().lower()
                                last_name = pax_ssr.pax.last_name.strip().lower()
                                for passenger in updated_ticket_status.get("data",{}).get('Response',{}).get('FlightItinerary',{}).get('Passenger',[]):
                                    FirstName = passenger["FirstName"].strip().lower()
                                    LastName = passenger["LastName"].strip().lower()
                                    if FirstName == first_name and LastName == last_name:
                                        ticket_number = passenger.get('Ticket',{}).get('TicketNumber',"") if passenger.get('Ticket') else""
                                        if ticket_number:
                                            pax_ssr.supplier_ticket_number = ticket_number
                                            pax_ssr.save(update_fields= ["supplier_ticket_number"])
                                        else:
                                            is_all_ticket_num = False
                            if is_pnr and is_all_ticket_num:
                                soft_deleted_itinerary.soft_fail = False
                                soft_deleted_itinerary.airline_pnr = PNR
                                soft_deleted_itinerary.status = "Failed-Confirmed"
                                soft_deleted_itinerary.modified_at = int(time.time())
                                soft_deleted_itinerary.save(update_fields= ["soft_fail","status","modified_at","airline_pnr"])
                                try:
                                    finance_manager = FinanceManager(booking.user)
                                    finance_manager.book_tbo(updated_ticket_status["data"],soft_deleted_itinerary,self.credentials,payment_details_easylink,
                                                            len(ssr_details),soft_fail = True)
                                    new_published_fare = booking.payment_details.new_published_fare if booking.payment_details.new_published_fare else 0
                                    ssr_price = booking.payment_details.ssr_price if booking.payment_details.ssr_price else 0
                                    total_fare = round(float(new_published_fare) + float(ssr_price),2)
                                    self.update_credit(booking = booking,total_fare = total_fare)
                                except Exception as e:
                                    error_trace = tb.format_exc()
                                    easylink_error_log = {"display_id":booking.display_id,
                                        "error":str(e),
                                        "error_trace":error_trace,
                                        "createdAt":datetime.now(),
                                        "type":"easy_link"}
                                    self.mongo_client.vendors.insert_one(easylink_error_log)
                                invoke_email({"user": str(booking.user.id),"sec" : 86400,"event":"Ticket_Confirmation",
                                            "booking_id":booking.display_id})
                            else:
                                invoke_status = "failure"
                    elif int(ticket_status) in [0,4,9]:
                        invoke_status = "failure"
                        soft_deleted_itinerary.soft_fail = False
                        soft_deleted_itinerary.error = "Ticketing Failed From Supplier"
                        soft_deleted_itinerary.status = "Ticketing-Failed"
                        soft_deleted_itinerary.modified_at = int(time.time())
                        soft_deleted_itinerary.save(update_fields= ["status","modified_at","soft_fail","error"])
                    else:
                        invoke_status = "failure"
                        soft_deleted_itinerary.status = "Ticketing-Failed"
                        soft_deleted_itinerary.modified_at = int(time.time())
                        soft_deleted_itinerary.save(update_fields= ["status","modified_at"])  
                else:
                    invoke_status = "failure"
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

def unify_seg_quote(flight_segments,flightSegment,IsPriceChanged,fareBasisCode):
    flight_segment = flight_segments[0]
    unified_structure = {"flightSegments":{flightSegment:[]}}
    unified_segment = {
        "airlineCode": flight_segment["Airline"]["AirlineCode"],
        "airlineName": flight_segment["Airline"]["AirlineName"],
        "flightNumber": flight_segment["Airline"]["FlightNumber"],
        "equipmentType": flight_segment.get("Craft", None), 
        "departure": {
            "airportCode": flight_segment["Origin"]["Airport"]["AirportCode"],
            "airportName": flight_segment["Origin"]["Airport"]["AirportName"],
            "city": flight_segment["Origin"]["Airport"]["CityName"],
            "country": flight_segment["Origin"]["Airport"]["CountryName"],
            "countryCode": flight_segment["Origin"]["Airport"]["CountryCode"],
            "terminal": flight_segment["Origin"]["Airport"].get("Terminal", "N/A"),
            "departureDatetime": flight_segment["Origin"]["DepTime"]
        },
        "arrival": {
            "airportCode": flight_segment["Destination"]["Airport"]["AirportCode"],
            "airportName": flight_segment["Destination"]["Airport"]["AirportName"],
            "city": flight_segment["Destination"]["Airport"]["CityName"],
            "country": flight_segment["Destination"]["Airport"]["CountryName"],
            "countryCode": flight_segment["Destination"]["Airport"]["CountryCode"],
            "terminal": flight_segment["Destination"]["Airport"].get("Terminal", "N/A"),
            "arrivalDatetime": flight_segment["Destination"]["ArrTime"]
        },
        "durationInMinutes": flight_segment["Duration"],
        "stop": len(flight_segments)-1,
        "cabinClass": "Economy" if flight_segment["CabinClass"] == 2 else None,
        "fareBasisCode": fareBasisCode,
        "seatsRemaining": flight_segment.get("NoOfSeatAvailable", None),
        "isChangeAllowed": True 
    }
    unified_structure['flightSegments'][flightSegment].append(unified_segment)
    if len(flight_segments) >1:
        for flight_segment in flight_segments[1:]:
            unified_segment = {
                "airlineCode": flight_segment["Airline"]["AirlineCode"],
                "airlineName": flight_segment["Airline"]["AirlineName"],
                "flightNumber": flight_segment["Airline"]["FlightNumber"],
                "equipmentType": flight_segment.get("Craft", None), 
                "departure": {
                    "airportCode": flight_segment["Origin"]["Airport"]["AirportCode"],
                    "airportName": flight_segment["Origin"]["Airport"]["AirportName"],
                    "city": flight_segment["Origin"]["Airport"]["CityName"],
                    "country": flight_segment["Origin"]["Airport"]["CountryName"],
                    "countryCode": flight_segment["Origin"]["Airport"]["CountryCode"],
                    "terminal": flight_segment["Origin"]["Airport"].get("Terminal", "N/A"),
                    "departureDatetime": flight_segment["Origin"]["DepTime"]
                },
                "arrival": {
                    "airportCode": flight_segment["Destination"]["Airport"]["AirportCode"],
                    "airportName": flight_segment["Destination"]["Airport"]["AirportName"],
                    "city": flight_segment["Destination"]["Airport"]["CityName"],
                    "country": flight_segment["Destination"]["Airport"]["CountryName"],
                    "countryCode": flight_segment["Destination"]["Airport"]["CountryCode"],
                    "terminal": flight_segment["Destination"]["Airport"].get("Terminal", "N/A"),
                    "arrivalDatetime": flight_segment["Destination"]["ArrTime"]
                },
                "durationInMinutes": flight_segment["Duration"],
                "stop": len(flight_segments)-1,
                "cabinClass": "Economy" if flight_segment["CabinClass"] == 2 else None,
                "fareBasisCode": fareBasisCode,
                "seatsRemaining": flight_segment.get("NoOfSeatAvailable", None),
                "isChangeAllowed": True,  
                "stopDetails": {
                "isLayover": True,
                "durationInMinutes": flight_segment.get("GroundTime", None),
                "stopPoint": {
                    "airportCode": [flight_segment["Origin"]["Airport"]["AirportCode"]],
                    "arrivalTime": calculate_arrival_time(flight_segment["Origin"]["DepTime"], flight_segment.get("GroundTime", None)),
                    "departureTime": flight_segment["Origin"]["DepTime"]
                            }
                    }
            }
            unified_structure['flightSegments'][flightSegment].append(unified_segment)
    return unified_structure

def unify_seg(flight_segments,flightSegment,segment):
    flight_segment = flight_segments[0]
    unified_structure = {"flightSegments":{flightSegment:[]}}
    unified_segment = {
        "airlineCode": flight_segment["Airline"]["AirlineCode"],
        "airlineName": flight_segment["Airline"]["AirlineName"],
        "flightNumber": flight_segment["Airline"]["FlightNumber"],
        "equipmentType": flight_segment.get("Craft", None),  
        "departure": {
            "airportCode": flight_segment["Origin"]["Airport"]["AirportCode"],
            "airportName": flight_segment["Origin"]["Airport"]["AirportName"],
            "city": flight_segment["Origin"]["Airport"]["CityName"],
            "country": flight_segment["Origin"]["Airport"]["CountryName"],
            "countryCode": flight_segment["Origin"]["Airport"]["CountryCode"],
            "terminal": flight_segment["Origin"]["Airport"].get("Terminal", 'N/A'),
            "departureDatetime": flight_segment["Origin"]["DepTime"]
        },
        "arrival": {
            "airportCode": flight_segment["Destination"]["Airport"]["AirportCode"],
            "airportName": flight_segment["Destination"]["Airport"]["AirportName"],
            "city": flight_segment["Destination"]["Airport"]["CityName"],
            "country": flight_segment["Destination"]["Airport"]["CountryName"],
            "countryCode": flight_segment["Destination"]["Airport"]["CountryCode"],
            "terminal": flight_segment["Destination"]["Airport"].get("Terminal", "N/A"),
            "arrivalDatetime": flight_segment["Destination"]["ArrTime"]
        },
        "durationInMinutes": flight_segment["Duration"],
        "stop": len(flight_segments)-1,
        "cabinClass": "Economy" if flight_segment["CabinClass"] == 2 else None,
        "fareBasisCode": segment.get("FareRules", [{}])[0].get("FareBasisCode", None),
        "seatsRemaining": flight_segment.get("NoOfSeatAvailable", None),
        "isChangeAllowed": True 
    }
    unified_structure['flightSegments'][flightSegment].append(unified_segment)
    if len(flight_segments) >1:
        for flight_segment in flight_segments[1:]:
            unified_segment = {
                "airlineCode": flight_segment["Airline"]["AirlineCode"],
                "airlineName": flight_segment["Airline"]["AirlineName"],
                "flightNumber": flight_segment["Airline"]["FlightNumber"],
                "equipmentType": flight_segment.get("Craft", None),  
                "departure": {
                    "airportCode": flight_segment["Origin"]["Airport"]["AirportCode"],
                    "airportName": flight_segment["Origin"]["Airport"]["AirportName"],
                    "city": flight_segment["Origin"]["Airport"]["CityName"],
                    "country": flight_segment["Origin"]["Airport"]["CountryName"],
                    "countryCode": flight_segment["Origin"]["Airport"]["CountryCode"],
                    "terminal": flight_segment["Origin"]["Airport"].get("Terminal", "N/A"),
                    "departureDatetime": flight_segment["Origin"]["DepTime"]
                },
                "arrival": {
                    "airportCode": flight_segment["Destination"]["Airport"]["AirportCode"],
                    "airportName": flight_segment["Destination"]["Airport"]["AirportName"],
                    "city": flight_segment["Destination"]["Airport"]["CityName"],
                    "country": flight_segment["Destination"]["Airport"]["CountryName"],
                    "countryCode": flight_segment["Destination"]["Airport"]["CountryCode"],
                    "terminal": flight_segment["Destination"]["Airport"].get("Terminal", "N/A"),
                    "arrivalDatetime": flight_segment["Destination"]["ArrTime"]
                },
                "durationInMinutes": flight_segment["Duration"],
                "stop": len(flight_segments)-1,
                "cabinClass": "Economy" if flight_segment["CabinClass"] == 2 else None,
                "fareBasisCode": segment.get("FareRules", [{}])[0].get("FareBasisCode", None),
                "seatsRemaining": flight_segment.get("NoOfSeatAvailable", None),
                "isChangeAllowed": True, 
                "stopDetails": {
                "isLayover": True,
                "durationInMinutes": flight_segment.get("GroundTime", None),
                "stopPoint": {
                    "airportCode": [flight_segment["Origin"]["Airport"]["AirportCode"]],
                    "arrivalTime": calculate_arrival_time(flight_segment["Origin"]["DepTime"], flight_segment.get("GroundTime", None)),
                    "departureTime": flight_segment["Origin"]["DepTime"]
                            }
                    }
            }
            unified_structure['flightSegments'][flightSegment].append(unified_segment)
    return unified_structure

def calculate_fares(supplier_published_fare,supplier_offered_fare,fare_adjustment,
                    tax_condition,total_pax_count):
    new_published_fare = supplier_published_fare + ((float(fare_adjustment["markup"]))+(float(fare_adjustment["distributor_markup"]))-\
                            float(fare_adjustment["cashback"]) - float(fare_adjustment["distributor_cashback"]))*total_pax_count
    new_offered_fare = supplier_published_fare + (float(fare_adjustment["markup"]) + float(fare_adjustment["distributor_markup"]) -\
         float(fare_adjustment["cashback"])-float(fare_adjustment["distributor_cashback"]))*total_pax_count -\
          (supplier_published_fare-supplier_offered_fare)*(float(fare_adjustment["parting_percentage"])/100)*(float(fare_adjustment["distributor_parting_percentage"])/100)*(1-float(tax_condition["tax"])/100)
    discount = new_published_fare - new_offered_fare
    return {"offered_fare":round(new_offered_fare,2),"discount":round(discount,2),
            "published_fare":round(new_published_fare,2),"supplier_published_fare":supplier_published_fare,
            "supplier_offered_fare":supplier_offered_fare}

def get_unified_cabin_class(cabin_class):
    cabin_map = {2:"Economy",3:"PremiumEconomy",4:"Business Class",6:"First Class"}
    return cabin_map.get(cabin_class,"Economy")

def replace_multiple_case_insensitive(text, replacements):
    try:
        for old, new in replacements.items():
            pattern = re.compile(re.escape(old), re.IGNORECASE)
            text = " " + pattern.sub(new, text)
        return text
    except:
        return ""

def get_fareBreakdown(FareBreakdown,new_published_fare,pax_data):
    FareBreakdownResults = []
    tatal_base_fare = sum(d['BaseFare'] for d in FareBreakdown if 'BaseFare' in d)
    total_pax_count =  sum(d['PassengerCount'] for d in FareBreakdown if 'PassengerCount' in d)
    if total_pax_count == 0:
        total_pax_count = sum(map(int, pax_data.values()))
    tax_per_pax = round((new_published_fare-tatal_base_fare)/total_pax_count,2)
    for fares in FareBreakdown:
        FareBreakdownResult = {}
        if fares['PassengerType'] == 1:
            FareBreakdownResult['passengerType'] = "adults"
        elif fares['PassengerType'] == 2:
            FareBreakdownResult['passengerType'] = "children"
        elif fares['PassengerType'] == 3:
            FareBreakdownResult['passengerType'] = "infants"
        if fares["PassengerCount"] == 0:
            fares["PassengerCount"] = int(pax_data[FareBreakdownResult['passengerType']])
        FareBreakdownResult['baseFare'] = fares['BaseFare']/fares["PassengerCount"]
        FareBreakdownResult['tax'] = tax_per_pax
        FareBreakdownResults.append(FareBreakdownResult)
    return FareBreakdownResults

pax_type_mapping = {"adults": 1,"adult": 1,"children": 2,"child":2,"infants": 3,"infant": 3}

gender_mapping = {"Male": 1,"M": 1,"Female": 2,"F": 2}

fare_type_mapping = {"Student":3,"Regular":2,"Senior Citizen":5}

cancellation_statuses_mapping = {0:"NotSet",1:"Unassigned",2:"Assigned",3:"Acknowledged",
                                 4:"Completed",5:"Rejected",6:"Closed",7:"Pending",8:"Other"}

def find_original_baggage_ssr(baggages_ssr,ssr_response):
    try:
        result = []
        for x in baggages_ssr.keys():
            if len(baggages_ssr[x])>0:
                Origin, _ = x.split("-")
                for bag in ssr_response['Response']['Baggage']:
                    for bag_data in bag:
                        if (bag_data['Origin'] == Origin) and (baggages_ssr[x]['Weight'] == bag_data["Weight"]):
                            result.append(bag_data)
    except:
        result = []
    return result

def find_original_meals_ssr(meals_ssr,ssr_response):
    try:
        result = []
        if "MealDynamic" in ssr_response['Response']:
            for x in meals_ssr.keys():
                if len(meals_ssr[x]) >0:
                    Origin, Destination = x.split("-")
                    for MealData in ssr_response['Response']['MealDynamic']:
                        for meal in MealData:
                            if (meal['Origin'] == Origin and meal['Destination'] == Destination) and  (meals_ssr[x]['Code'] == meal["Code"]):
                                result.append(meal)
        elif 'Meal' in ssr_response['Response']:
            for x in meals_ssr.keys():
                if len(meals_ssr[x])>0:
                    for selected_meal in ssr_response['Response']['Meal']:
                        if selected_meal['Code'] == meals_ssr[x]['Code']:
                            result.append(selected_meal)
    except:
        result = []
    return result

def find_original_seats_ssr(seats_ssr,ssr_response):
    try:
        result = []
        seats_master = []
        SeatDynamic_data = ssr_response['Response']['SeatDynamic']
        for seg_seat in SeatDynamic_data:
            for data in seg_seat["SegmentSeat"]:
                seats_master.append(data["RowSeats"])
        for x in seats_ssr.keys():
            if len(seats_ssr[x]) >0:
                Origin, Destination = x.split("-")
                for seat_master in seats_master:
                    if seat_master[0]['Seats'][0]['Origin'] == Origin and seat_master[0]['Seats'][0]['Destination'] == Destination:
                        result.append([b for a in seat_master for b in a['Seats'] if b['Code'] == seats_ssr[x]['Code']][0])
    except:
        result = []
    return result

def format_datetime(date_string):
    try:
        if date_string:
            datetime_obj = datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S.%fZ")
            formatted_date = datetime_obj.strftime("%Y-%m-%dT00:00:00")
            return formatted_date
        else:
            return ""
    except (ValueError, AttributeError):
        return ""
