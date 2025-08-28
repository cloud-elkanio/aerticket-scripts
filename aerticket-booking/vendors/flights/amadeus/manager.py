from vendors.flights.abstract.abstract_flight_manager import AbstractFlightManager
from vendors.flights.amadeus.api  import (flight_search,create_fare_rules,fare_quote,get_seatmap,get_baggage,
                                          add_pnr_data,add_form_of_payment,add_upsell,add_baggage,
                                          import_pnr_data,repricing_with_pnr,create_ticket,
                                          close_PNR,issue_Ticket,signout,add_permission)
                                    #     ,authentication,fare_rule,
                                    #   ssr,hold,release_hold,ticket,ticket_lcc,cancellation_charges,
                                    #   cancel_ticket)
from datetime import datetime,timedelta
from django.db.models import QuerySet
from timezonefinder import TimezoneFinder
import pytz,os
from vendors.flights.utils import create_uuid,set_fare_details,create_segment_keys,extract_data_recursive,dictlistconverter
from vendors.flights.finance_manager import FinanceManager
from users.models import LookupCountry,LookupAirline,LookupAirports,AirlineDeals,SupplierDealManagement
from common.models import FlightBookingFareDetails,FlightBookingSegmentDetails,FlightBookingItineraryDetails,FlightBookingUnifiedDetails,FlightBookingPaxDetails
from vendors.flights import mongo_handler
from collections import Counter
import concurrent.futures
import re,json
import threading
import time
from typing import Optional

class Manager(AbstractFlightManager):
    def __init__(self,data,uuid,mongo_client):
        self.vendor_id = "VEN-"+str(uuid)
        self.base_url = data.get("base_url")
        self.credentials = data
        self.mongo_client = mongo_client
        
    def name (self):
        return "Amadeus"
    def get_vendor_id(self):
        return self.vendor_id
    def search_flights (self, journey_details):
        session_id = journey_details.get("session_id")
        fare_type = journey_details.get('fare_type')
        journey_type = journey_details.get("journey_type")
        flight_type = journey_details.get("flight_type")
        pax = journey_details.get("passenger_details")
        cabin_class = journey_details.get("cabin_class")
        segment_details = journey_details.get("journey_details")
        cabin_class = get_amadeus_cabins(cabin_class)
        # segments = self.create_segments(segment_details,cabin_class)
        segment_keys = create_segment_keys(journey_details)

        def process_segment(seg, index,cabin_class):
            """Function to process each segment in a thread."""
            flight_search_response = flight_search(session_id=session_id,
                base_url= self.base_url,credentials=self.credentials,
                passenger_details=pax,journey_details=[seg],cabin_class=cabin_class
            )
            return index, flight_search_response

        if journey_type =="Multi City" or journey_type =="One Way" or\
            (journey_type =="Round Trip" and flight_type == "DOM") :
            def run_in_threads(segments, segment_keys,cabin_class):
                final = {}
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = {
                        executor.submit(process_segment, seg, index,cabin_class): index
                        for index, seg in enumerate(segments)
                    }
                    for future in concurrent.futures.as_completed(futures):
                        index, response = future.result()
                        final[segment_keys[index]] = response

                return final

            final_result = run_in_threads(segment_details, segment_keys,cabin_class)
            if fare_type.upper()!="REGULAR":
                return {"data":{},"status":"failure"}
            return {"data":final_result,"status":"success"}

        else:
            flight_search_response = flight_search(session_id=session_id,base_url= self.base_url,credentials=self.credentials,
                                                    passenger_details=pax,journey_details=segment_details,cabin_class=cabin_class)
            flight_segment = segment_keys[0]
            if fare_type.upper()!="REGULAR":
                return {"data":{flight_segment:{}},"status":"failure"}
            return {"data":{flight_segment:flight_search_response},"status":"success"}
        
    def converter(self, search_response, journey_details,fare_details):
        deals = AirlineDeals.objects.filter(status= True)
        airline_objs = LookupAirline.objects.all()
        airlines = { airline.code: airline for airline in airline_objs }
        airport_objs = LookupAirports.objects.all()
        airports = { airport.code: airport for airport in airport_objs }
        fare_adjustment,tax_condition= set_fare_details(fare_details)
        user = fare_details.get("user")
        user_country = user.organization.organization_country.lookup.country_code
        passenger_details = journey_details.get("passenger_details")
        search_query = journey_details
        segment_keys = create_segment_keys(journey_details)
        return_data = {"itineraries":segment_keys}

        def is_ticket_refundable(texts):
            # Combine input texts into one string.
            if isinstance(texts, list):
                # If items are nested lists, take their first element.
                data = ' '.join([d[0] if isinstance(d, list) else d for d in texts])
            else:
                data = texts

            # Normalize the text: lowercase, replace hyphens with spaces, remove punctuation.
            data_norm = data.lower().replace('-', ' ')
            data_norm = re.sub(r'[^\w\s]', '', data_norm)

            # Define phrases corresponding to the monitored Amadeus codes.
            # Note: Code 71 ("non refundable after departure") is considered refundable.
            refundable_after_departure_phrases = [
                "tkts are non refundable after departure",
                "tickets are non refundable after departure",
                "non refundable after departure",
                "penalty applies",                               # code 73
                "percent penalty applies",                       # code 74
                "penalty applies check rules",                   # code 75
            ]
            # All other phrases (codes 70, 72, 73, 74, 75, 76) indicate non-refundable.
            non_refundable_phrases = [
                "tickets are non refundable",                    # code 70
                "tkts are non refundable before departure",      # code 72
                "subject to cancellation",                       # code 76
                # Also catch common generic phrases from the normal scenario:
                "no show  non refundable",
                "ticket is non refundable",
                "yq is non refundable"
            ]
            
            # Check if any non-refundable phrase is present.
            found_non_refundable = any(phrase in data_norm for phrase in non_refundable_phrases)
            # Check if any refundable-after-departure phrase is present.
            found_refundable_after = any(phrase in data_norm for phrase in refundable_after_departure_phrases)
            
            # If any non-refundable phrase is found, then overall the fare is non-refundable.
            # Even if a refundable-after-departure phrase is found alongside, we assume the presence
            # of any other code (or generic indicator) should override.
            if found_non_refundable:
                return False
            # Otherwise, if only a refundable-after-departure indication is found, consider it refundable.
            elif found_refundable_after:
                return True
            else:
                # If none of the monitored phrases are found, default to non-refundable.
                return False

        def unify_segment(idx,flight_info,result_segment):
            # Extract airline code and name
            airlineCode = flight_info['companyId']['marketingCarrier']
            airlineName = get_airline(airlineCode,airlines).name
            
            # Extract flight number and equipment type
            flightNumber = flight_info['flightOrtrainNumber']
            equipmentType = flight_info['productDetail']['equipmentType']
            
            # Extract departure information
            departure_info = flight_info['location'][0]
            departure_airportCode = departure_info['locationId']
            departure_terminal = departure_info.get('terminal', '')
            
            # Extract arrival information
            arrival_info = flight_info['location'][1]
            arrival_airportCode = arrival_info['locationId']
            arrival_terminal = arrival_info.get('terminal', '')
            
            # Extract and parse dates and times
            dateOfDeparture = flight_info['productDateTime']['dateOfDeparture']
            timeOfDeparture = flight_info['productDateTime']['timeOfDeparture']
            dateOfArrival = flight_info['productDateTime']['dateOfArrival']
            timeOfArrival = flight_info['productDateTime']['timeOfArrival']
            dateVariation = int(flight_info['productDateTime'].get('dateVariation', '0'))

            departure_date = datetime.strptime(dateOfDeparture, "%d%m%y")
            departure_time = datetime.strptime(timeOfDeparture, "%H%M").time()
            departure_datetime = datetime.combine(departure_date, departure_time)

            arrival_date = datetime.strptime(dateOfArrival, "%d%m%y")
            arrival_time = datetime.strptime(timeOfArrival, "%H%M").time()
            arrival_datetime = datetime.combine(arrival_date, arrival_time) + timedelta(days=dateVariation)
            start = time.time()
            durationInMinutes,gmt_departed_time = get_gmt_converted_duration(airports,departure_airportCode,arrival_airportCode,
                                                           departure_datetime.strftime("%Y-%m-%dT%H:%M:%S"),arrival_datetime.strftime("%Y-%m-%dT%H:%M:%S"))
            
            isRefundable_datas = dictlistconverter(result_segment.get('paxFareProduct',{}))
            text_data = []
            texts = [x.get('fare',[]) for x in isRefundable_datas]
            for text in texts:
                text = dictlistconverter(text)
                if len(text)>0:
                    list_of_lists = [x.get('pricingMessage',{}).get('description','') for x in text]
                    for item in list_of_lists:
                        if type(item) == list:
                            text_data += item
                        else:
                            text_data.append(item)
                    
            isRefundable = is_ticket_refundable(text_data)

            cabinClass = extract_data_recursive(result_segment,['paxFareProduct','fareDetails','groupOfFares','productInformation','cabinProduct'],{})
            if type(cabinClass) == dict:
                cabin = cabinClass.get('cabin','')
                rbd = cabinClass.get('rbd','')
            else:
                cabin = cabinClass[0].get('cabin','')
                rbd = cabinClass[0].get('rbd','')

                     
            cabinClass= cabin 
            cabin =rbd
            cabinClass = get_cabin_class(cabinClass)
            fareBasisCode = extract_data_recursive(result_segment,['paxFareProduct','fareDetails','groupOfFares','productInformation','fareProductDetail','fareBasis'],None)
            seatsRemaining = extract_data_recursive(result_segment,['paxFareProduct','fareDetails','groupOfFares','productInformation','cabinProduct','avlStatus'],None)
            # Create segment dictionary
            dep_airport = get_airport(departure_airportCode,airports)

            arr_airport = get_airport(arrival_airportCode,airports)
            leg = {
                'airlineCode': airlineCode,
                'airlineName': airlineName,
                'flightNumber': flightNumber,
                'equipmentType': equipmentType,
                'departure': {
                    'airportCode': departure_airportCode,
                    'airportName': dep_airport.name if dep_airport else "-",
                    'city': dep_airport.city if dep_airport else "N/A",
                    'country': dep_airport.country.country_name if dep_airport and dep_airport.country and dep_airport.country.country_name else "-",
                    'countryCode':dep_airport.country.country_code if dep_airport and dep_airport.country and dep_airport.country.country_code else "-",
                    'terminal': departure_terminal,
                    'departureDatetime': departure_datetime.isoformat()
                },
                'arrival': {
                    'airportCode': arrival_airportCode,
                    'airportName': arr_airport.name if arr_airport else "-",
                    'city': arr_airport.city if arr_airport else "-",
                    'country': arr_airport.country.country_name if arr_airport and arr_airport.country and arr_airport.country.country_name else "-",
                    'countryCode':arr_airport.country.country_code if arr_airport and arr_airport.country and arr_airport.country.country_code else "-",
                    'terminal': arrival_terminal,
                    'arrivalDatetime': arrival_datetime.isoformat()
                },
                
                'durationInMinutes': durationInMinutes,
                "stop":0,
                "cabinClass": cabinClass,
                "cabin": cabin,
                "fareBasisCode": fareBasisCode,
                "seatsRemaining": seatsRemaining,
                "isRefundable": isRefundable,
                "isChangeAllowed": False
            }
            
            if idx == 0:
                return leg
            else:
                leg['stop']=1
                layover_duration =  datetime.fromisoformat(leg['departure']['departureDatetime']) - datetime.fromisoformat(results[-1]['arrival']['arrivalDatetime'])
                layover_durationInMinutes = int(layover_duration.total_seconds() / 60)
                stop_point = {
                    'isLayover': True,
                    'durationInMinutes': layover_durationInMinutes,
                    'stopPoint': {
                        'airportCode': leg['departure']['airportCode'],
                        'arrivalTime': results[-1]['arrival']['arrivalDatetime'],
                        'departureTime': leg['departure']['departureDatetime']
                    }
                }
                leg['stopDetails'] = stop_point
                return leg

        def unify_fare(search_query,paxFareProduct):
            finalFareAmount = 0
            finalTaxAmount = 0
            finalYR = 0
            finalYQ = 0
            finalBasic = 0
            type_map = {"ADT":'adults',"CHD":'children',"INF":'infants','CNN':'children'} 
            paxFareProduct = dictlistconverter(paxFareProduct)   
            for elem in paxFareProduct:
                is_avail = extract_data_recursive(result,['fareDetails','groupOfFares','productInformation','cabinProduct','cabinProduct','avlStatus'],False)
                if is_avail:
                    continue 
                mul_factor = int(search_query['passenger_details'][type_map[elem['paxReference']['ptc']]])
                totalFareAmount = float(elem.get('paxFareDetail',{}).get('totalFareAmount',0)) * mul_factor
                totalTaxAmount = float(elem.get('paxFareDetail',{}).get('totalTaxAmount',0))* mul_factor
                YR = sum([
                    float(x.get('rate', 0))  # Default to 0 if 'rate' is missing
                    for x in dictlistconverter(elem.get('passengerTaxDetails', {}).get('taxDetails', []) or [])  
                    if str(x.get('type', '')).strip() == 'YR'  # Convert to str before strip()
                ]) * mul_factor

                YQ = sum([
                    float(x.get('rate', 0))  # Default to 0 if 'rate' is missing
                    for x in dictlistconverter(elem.get('passengerTaxDetails', {}).get('taxDetails', []) or [])  
                    if str(x.get('type', '')).strip() == 'YQ'  # Convert to str before strip()
                ]) * mul_factor
                Basic = totalFareAmount - totalTaxAmount
                
                finalFareAmount += totalFareAmount
                finalTaxAmount += totalTaxAmount
                finalYR += YR
                finalYQ += YQ
                finalBasic += Basic
            
            return {"finalFareAmount":finalFareAmount, "finalTaxAmount":finalTaxAmount,
                    "finalYR":finalYR, "finalYQ":finalYQ, "finalBasic":finalBasic}

        if journey_details["journey_type"] =="Multi City" or journey_details["journey_type"] =="One Way" or\
            (journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "DOM"):

            for flightSegment in segment_keys:
                single_response = search_response[flightSegment]
                return_data[flightSegment] = []
                result_segments = []
                amadeus_data = single_response['soap_Envelope']['soap_Body']['Fare_MasterPricerTravelBoardSearchReply']        
                for recommendation in amadeus_data['recommendation']:
                    result ={}
                    result['itemNumber'] = recommendation['itemNumber']
                    result['recPriceInfo'] = recommendation['recPriceInfo']
                    result['paxFareProduct'] = recommendation['paxFareProduct']
                    data = []
                    segmentFlightRef = recommendation['segmentFlightRef'] 
                    segmentFlightRef = dictlistconverter(segmentFlightRef)
                    serviceCoverageInfoGrp = []
                    for segmentFlightRefelem in segmentFlightRef:
                        serviceCoverageInfoGrp.append([ x['refNumber'] for x in dictlistconverter(segmentFlightRefelem['referencingDetail']) if x['refQualifier'] == 'B'][0])
                    serviceCoverageInfoGrp = list(set(serviceCoverageInfoGrp))
                    serviceCoverageInfoGrpData = [x['serviceCovInfoGrp']['refInfo']['referencingDetail']['refNumber'] for x in amadeus_data['serviceFeesGrp']['serviceCoverageInfoGrp'] if x['itemNumberInfo']['itemNumber']['number'] in serviceCoverageInfoGrp]
                                    
                    baggage_datas = [x for x in dictlistconverter(amadeus_data['serviceFeesGrp']['freeBagAllowanceGrp']) if x['itemNumberInfo']['itemNumberDetails']['number'] in serviceCoverageInfoGrpData] 
                    for baggage_data in baggage_datas:
                        checkin_baggage = baggage_data.get("freeBagAllownceInfo").get('baggageDetails')
                        if checkin_baggage:
                            if 'quantityCode' in checkin_baggage.keys():
                                if checkin_baggage.get('quantityCode',"")  == "N":
                                    if int(checkin_baggage.get('freeAllowance'))  > 1:
                                        checkin_baggage = checkin_baggage.get('freeAllowance',2) + ' Pieces'
                                    else:
                                        checkin_baggage = checkin_baggage.get('freeAllowance',1) + ' Piece'
                                elif checkin_baggage.get('quantityCode',"")  == "700":
                                    checkin_baggage = checkin_baggage.get('freeAllowance',0) + ' Kilos'
                                else:
                                    checkin_baggage = ""
                            else:
                                checkin_baggage = ""
                                    
                        else:
                            checkin_baggage = ""

                    for segmentFlightRefelem in segmentFlightRef:
                        s = [ x['refNumber'] for x in dictlistconverter(segmentFlightRefelem['referencingDetail']) if x['refQualifier'] == 'S']
                        if len(s):
                            s =s[0]
                            data.append(amadeus_data['flightIndex']['groupOfFlights'][int(s)-1])
                        else:
                            continue
                    result['data'] = data

                    unified_fare = unify_fare(search_query,result.get('paxFareProduct',{}))
                    fare_class = extract_data_recursive(result,['paxFareProduct','fareDetails','groupOfFares','productInformation','cabinProduct','rbd'],'')
                    fare_cabin = extract_data_recursive(result,['paxFareProduct','fareDetails','groupOfFares','productInformation','cabinProduct','cabin'],'')
                    validating_carrier = extract_data_recursive(result,['paxFareProduct','paxFareDetail','codeShareDetails'],{}).get('company',None)
                    for segment in result['data']:
                        flight_details = segment['flightDetails']
                        flight_details = dictlistconverter(flight_details)
                        results = []
                        for idx,flight_detail in enumerate(flight_details):
                            flight_info = flight_detail['flightInformation']
                            leg = unify_segment(idx,flight_info,result)
                            results.append(leg)
                        one_seg  = {'flightSegments':{flightSegment:results}}
                        applicable_deal = find_applicable_deal(deals,results,fare_class,fare_cabin,user_country)
                        deal_applied_result = apply_deal(applicable_deal,unified_fare,tax_condition,fare_adjustment)
                        total_passengers = sum(int(value) for value in passenger_details.values()) 
                        calculated_fares = calculate_fares(deal_applied_result['publishFare'],deal_applied_result['offerFare'],deal_applied_result['discount'],fare_adjustment,tax_condition,1)
                        one_seg['publishFare'] = calculated_fares['publish_fare']
                        one_seg['offerFare'] = calculated_fares['offered_fare']                        
                        one_seg['Discount'] = calculated_fares['discount']
                        one_seg['currency'] = deal_applied_result['currency']
                        one_seg['supplier_published_fare'] = calculated_fares['supplier_published_fare']
                        one_seg['supplier_offered_fare'] = calculated_fares['supplier_offered_fare']
                        one_seg['misc'] = {"fare_data":unified_fare,"deal":deal_applied_result.get("deal")}
                        one_seg['default_baggage']={"checkInBag":checkin_baggage,"cabinBag":"7 Kg"}



                        if validating_carrier != None:
                            one_seg['vc'] = validating_carrier
                        else:
                            one_seg['vc'] = flight_info.get('companyId').get('marketingCarrier','')
                        one_seg  = one_seg|{'flightSegments':{flightSegment:results},'segmentID':str(self.vendor_id)+"_$_"+create_uuid("SEG")}

                        result_segments.append(one_seg)
                return_data[flightSegment] = result_segments

        elif journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "INT":
            flightSegment = segment_keys[0]
            return_data[flightSegment] = []
            single_response = search_response[flightSegment]
            amadeus_data = single_response['soap_Envelope']['soap_Body']['Fare_MasterPricerTravelBoardSearchReply']        

            result_segments = []

            for recommendation in amadeus_data['recommendation']:
                result ={}
                result['itemNumber'] = recommendation['itemNumber']
                result['recPriceInfo'] = recommendation['recPriceInfo']
                result['paxFareProduct'] = recommendation['paxFareProduct']
                data = []
                segmentFlightRef = recommendation['segmentFlightRef'] 
                segmentFlightRef = dictlistconverter(segmentFlightRef)
                serviceCoverageInfoGrp = []
                for segmentFlightRefelem in segmentFlightRef:
                    serviceCoverageInfoGrp.append([ x['refNumber'] for x in dictlistconverter(segmentFlightRefelem['referencingDetail']) if x['refQualifier'] == 'B'][0])
                serviceCoverageInfoGrp = list(set(serviceCoverageInfoGrp))
                serviceCoverageInfoGrpData = [x['serviceCovInfoGrp']['refInfo']['referencingDetail']['refNumber'] for x in amadeus_data['serviceFeesGrp']['serviceCoverageInfoGrp'] if x['itemNumberInfo']['itemNumber']['number'] in serviceCoverageInfoGrp]
                                
                baggage_datas = [x for x in amadeus_data['serviceFeesGrp']['freeBagAllowanceGrp'] if x['itemNumberInfo']['itemNumberDetails']['number'] in serviceCoverageInfoGrpData] 
                for baggage_data in baggage_datas:
                    checkin_baggage = baggage_data.get("freeBagAllownceInfo").get('baggageDetails')
                    if checkin_baggage:
                        if 'quantityCode' in checkin_baggage.keys():
                            if checkin_baggage.get('quantityCode',"")  == "N":
                                if int(checkin_baggage.get('freeAllowance'))  > 1:
                                    checkin_baggage = checkin_baggage.get('freeAllowance',2) + ' Pieces'
                                else:
                                    checkin_baggage = checkin_baggage.get('freeAllowance',1) + ' Piece'
                            elif checkin_baggage.get('quantityCode',"")  == "700":
                                checkin_baggage = checkin_baggage.get('freeAllowance',0) + ' Kilos'
                            else:
                                checkin_baggage = ""
                        else:
                            checkin_baggage = ""
                                
                    else:
                        checkin_baggage = ""


                for segmentFlightRefelem in segmentFlightRef:
                    referencingDetail = dictlistconverter(segmentFlightRefelem['referencingDetail'])
                    s = [ x['refNumber'] for x in referencingDetail if x['refQualifier'] == 'S']
                    if s:
                        data.append([amadeus_data['flightIndex'][0]['groupOfFlights'][int(s[0])-1],amadeus_data['flightIndex'][1]['groupOfFlights'][int(s[1])-1]])
                result['data'] = data

                unified_fare = unify_fare(search_query,result.get('paxFareProduct',{}))
                fare_class = extract_data_recursive(result,['paxFareProduct','fareDetails','groupOfFares','productInformation','cabinProduct','rbd'],'')
                fare_cabin = extract_data_recursive(result,['paxFareProduct','fareDetails','groupOfFares','productInformation','cabinProduct','cabin'],'')
                validating_carrier = extract_data_recursive(result,['paxFareProduct','paxFareDetail','codeShareDetails'],{}).get('company',None)

                for journey in result['data']:
                    one_seg  = {'flightSegments':{}}
                    for idx,segment in enumerate(journey):
                        flight_details = segment['flightDetails']
                        flight_details = dictlistconverter(flight_details)
                        results = []
                        for idy,flight_detail in enumerate(flight_details):
                            flight_info = flight_detail['flightInformation']
                            leg = unify_segment(idy,flight_info,result)
                            results.append(leg)
                        one_seg['flightSegments'][flightSegment.split('_R_')[idx]]= results
                    legs = one_seg['flightSegments'][flightSegment.split('_R_')[idx]]
                    applicable_deal = find_applicable_deal(deals,legs,fare_class,fare_cabin,user_country)
                    deal_applied_result = apply_deal(applicable_deal,unified_fare,tax_condition,fare_adjustment)
                    total_passengers = sum(int(value) for value in passenger_details.values()) 

                    calculated_fares = calculate_fares(deal_applied_result['publishFare'],deal_applied_result['offerFare'],deal_applied_result['discount'],fare_adjustment,tax_condition,1)
                    one_seg['publishFare'] = calculated_fares['publish_fare']
                    one_seg['offerFare'] = calculated_fares['offered_fare']
                    one_seg['Discount'] = calculated_fares['discount']
                    one_seg['currency'] = deal_applied_result['currency']
                    one_seg['supplier_published_fare'] = calculated_fares['supplier_published_fare']
                    one_seg['supplier_offered_fare'] = calculated_fares['supplier_offered_fare']
                    one_seg['misc'] = {"fare_data":unified_fare,"deal":deal_applied_result.get("deal")}
                    one_seg['default_baggage']={"checkInBag":checkin_baggage,"cabinBag":"7 Kg"}

                    if validating_carrier != None:
                        one_seg['vc'] = validating_carrier
                    else:
                        one_seg['vc'] = flight_info.get('companyId').get('marketingCarrier','')
                    one_seg = one_seg |{'segmentID':str(self.vendor_id)+"_$_"+create_uuid("SEG")}
                    #one_seg  = one_seg|{'flightSegments':{flightSegment.split('_R_')[idx]:results},'segmentID':str(self.vendor_id)+"_$_"+create_uuid("SEG")}

                result_segments.append(one_seg)
            return_data[segment_keys[0]] = result_segments




        return {"data":return_data,"status":"success"}

    def find_segment_by_id(self, data, segment_id, journey_details):
        unified_data= {}
        itineraries = data.get("data").get("itineraries")
        flight_segments_dict = {}
        for itinerary in itineraries:
            flightSegments = unified_data.get("data").get(itinerary)
            for flightSegment in flightSegments:
                if flightSegment.get("segmentID") == segment_id:
                    return {"itineraries":itineraries,itinerary:flightSegment}

    def get_fare_details(self, master_doc, raw_data, fare_details,raw_doc,segment_id,itinerary_key,session_id):
        def generate_fare_rule_html(fare_rules, pax_type):
            
            final_html_output = ""

            for idx,fare_rule in enumerate(fare_rules):
                # Extract Origin and Destination (if available)
                flight_details = fare_rule.get("flightDetails", [])
                origin = destination = ""

                origin = flight_details.get("odiGrp", {}).get("originDestination", {}).get("origin", "")
                destination = flight_details.get("odiGrp", {}).get("originDestination", {}).get("destination", "")

                fare_rule_data = fare_rule.get("tariffInfo", [])
                
                html_output = f'''
                <h1>Fare Rules for {pax_type.upper()}</h1>
                <h3 style="text-align:center;color:#555;">{origin} → {destination}</h3>
                '''
                
                def is_unwanted_dotted_line(text):
                    """Check if the text is an unwanted line of dashes or similar separators."""
                    return text and re.match(r'^-+$', text.strip())

                for rule in fare_rule_data:
                    rule_section_id = rule.get('fareRuleInfo', {}).get('ruleSectionLocalId', 'N/A')
                    rule_category_code = rule.get('fareRuleInfo', {}).get('ruleCategoryCode', 'N/A')
                    
                    # Add rule header
                    html_output += f'''
                    <div class="rule-box">
                        <h2>Rule Section {rule_section_id} - Category Code {rule_category_code}</h2>
                        <div class="rule-content">
                    '''
                    
                    if 'fareRuleText' in rule:
                        paragraph = ''  # Variable to hold combined sentences for a paragraph
                        
                        for text_entry in rule['fareRuleText']:
                            free_text = text_entry.get('freeText', '')

                            # Skip unwanted dotted lines or None values
                            if free_text is None or is_unwanted_dotted_line(free_text):
                                continue
                            
                            # If the current free_text ends with a punctuation, end the current paragraph and start a new one
                            if free_text.endswith(('.', '!', '?')):
                                paragraph += f'{free_text} '
                                html_output += f'<p>{paragraph.strip()}</p>'
                                paragraph = ''  # Reset paragraph
                            else:
                                paragraph += f'{free_text} '
                        
                        # Add remaining paragraph if any
                        if paragraph.strip():
                            html_output += f'<p>{paragraph.strip()}</p>'
                    
                    html_output += '</div></div>'  # Close the rule-content and rule-box divs

                final_html_output += html_output
                
                if len(fare_rules) > 1:
                    final_html_output += "<br>"
                
            return final_html_output


        session_id = session_id
        segment_key = flightSegment =itinerary_key
        fare_adjustment,tax_condition= set_fare_details(fare_details)
        unified_Segment = raw_data[segment_key]["flightSegments"]
        segments = create_segment_from_unified(unified_Segment)
        passenger_details = master_doc.get("passenger_details")
        passenger_counts = convert_pax_types(passenger_details)
        pricingOptions = ["RP","RU","VC"]
        pricingOptions = [{"pricingOptionKey":x} for x in pricingOptions]
        is_round_trip = True if "_R_" in segment_key else False
        user = fare_details.get("user")
        user_country = user.organization.organization_country.lookup.country_code

        fares = create_fare_rules(session_id,self.base_url,self.credentials,passenger_counts,segments,pricingOptions,is_round_trip)
        pax_type_map = {'ADT':'adults','CHD':'children','CH':'children','INF':'infants','CNN':'children','IN':'infants'}
        fareDetails= []
        fare_doc = {
            "hold": fares,
            "type":"fare_data"
            }
        self.mongo_client.searches.insert_one(fare_doc)
        if fares != None:
            fares = dictlistconverter(fares)
            for idx,fare in enumerate(fares):
                fare_rule = fare.get("fare_rule",[])
                if fare_rule==[]:
                    continue
                result = {}
                if fare.get("is_upsell"):
                    segmentInformation = fare.get("segmentInformation")
                    final_checkin_baggage = []
                    for segement in segmentInformation:
                        connexType = extract_data_recursive(segement,["connexInformation","connecDetails","connexType"],"")
                        if connexType == "O":
                            checkin_baggage = extract_data_recursive(segement,['bagAllowanceInformation','bagAllowanceDetails'],None)
                            if checkin_baggage:
                                if 'baggageWeight' in checkin_baggage:
                                    checkin_baggage = checkin_baggage.get('baggageWeight','') + ' ' + checkin_baggage.get('measureUnit','')
                                    checkin_baggage = checkin_baggage.strip()
                                elif 'baggageQuantity' in checkin_baggage:
                                    checkin_baggage = checkin_baggage.get('baggageQuantity','') + ' ' + checkin_baggage.get('baggageType','')
                                    checkin_baggage = checkin_baggage.strip()
                            else:
                                checkin_baggage = '' 
                            final_checkin_baggage.append(checkin_baggage)
                    final_checkin_baggage = ",".join([str(item) for item in final_checkin_baggage])
                    result['baggage'] = {"checkInBag":final_checkin_baggage,"cabinBag":"7 Kg"}
                    uiname = [x.get("fareFamilyDetails",{}).get("fareFamilyname","") for x in dictlistconverter(fare.get("fareComponentDetailsGroup"))]
                    uiname = '_'.join(uiname) if len(uiname) > 1 else (uiname[0] if uiname else '')
                    # if uiname[0]=="_":
                    #     continue
                    result['uiName'] = uiname
                    result['fareType'] = uiname
                    result['validatingCarrier'] = extract_data_recursive(fare,['validatingCarrier','carrierInformation','carrierCode'],'')
                    result['currency'] = extract_data_recursive(fare, ['fareDataInformation','fareDataSupInformation','fareCurrency'], 'INR')
                    result['colour'] = 'RED'
                    result['isUpsell'] = True
                    upsell = True
                    # Extract refundability status
                    is_refundable = True  # Assume refundable by default
                    for warning in fare.get('warningInformation', []):
                        warning_text = warning.get('warningText', {}).get('errorFreeText', '')
                        if 'NON-REFUNDABLE' in warning_text.upper():
                            is_refundable = False
                            break
                    
                    result['isRefundable'] = is_refundable
                    result['fareBreakdown'] = {}
                    fare_details = fare.get('fareDataInformation',{}).get('fareDataSupInformation',None)
                    fare_details = dictlistconverter(fare_details)
                    base_fare = [
                        float(x.get('fareAmount', 0)) for x in fare_details 
                        if x.get('fareDataQualifier') == 'E'
                    ]
                    # If no 'E' fare exists, fallback to 'B'
                    if not base_fare:
                        base_fare = [
                            float(x.get('fareAmount', 0)) for x in fare_details 
                            if x.get('fareDataQualifier') == 'B'
                        ]
                    
                    if len(base_fare)>0:
                        base_fare = sum(base_fare)
                        base_fare = base_fare
                    else:
                        base_fare = 0
                    result['fareBreakdown']['baseFare'] = base_fare
                    total_fare = [float(x.get('fareAmount',0)) for x in fare_details if x.get('fareDataQualifier') in ['712','T']]
                    if len(total_fare)>0:
                        total_fare = sum(total_fare)
                        total_fare = total_fare
                        tax_fare = total_fare - base_fare
                    else:
                        tax_fare = 0
                    result['fareBreakdown']['tax'] = tax_fare
                    tax_details = fare.get('taxInformation',{})
                    tax_details = dictlistconverter(tax_details)
                    YR = [float(x.get('amountDetails',{}).get('fareDataMainInformation',{}).get('fareAmount',0)) for x in tax_details if x.get('taxDetails',{}).get('taxType',{}).get('isoCountry','') == 'YR']
                    if len(YR)>0:
                        YR = sum(YR)
                    else:
                        YR = 0
                    YQ = [float(x.get('amountDetails',{}).get('fareDataMainInformation',{}).get('fareAmount',0)) for x in tax_details if x.get('taxDetails',{}).get('taxType',{}).get('isoCountry','') == 'YQ']
                    if len(YQ)>0:
                        YQ = sum(YQ)
                    else:
                        YQ = 0
                    K3 = [float(x.get('amountDetails',{}).get('fareDataMainInformation',{}).get('fareAmount',0)) for x in tax_details if x.get('taxDetails',{}).get('taxType',{}).get('isoCountry','') == 'K3']
                    if len(K3)>0:
                        K3 = sum(K3)
                    else:
                        K3 = 0
                
                    Other = [float(x.get('amountDetails',{}).get('fareDataMainInformation',{}).get('fareAmount',0)) for x in tax_details if x.get('taxDetails',{}).get('taxType',{}).get('isoCountry','') not in ['YR','YQ','K3']]
                    if len(Other)>0:
                        Other = sum(Other)
                    else:
                        Other = 0
                    other_taxes = YR + YQ + K3 + Other
                    result['fareBreakdown']['tax_splitp'] = {"YR":YR,"YQ":YQ,"K3":K3,"other_taxes":other_taxes}
                    pax_type = extract_data_recursive(fare,['segmentInformation','fareQualifier','fareBasisDetails','discTktDesignator'],'ADT')
                    result['fareBreakdown']['passengerType'] = pax_type_map[pax_type] if pax_type in pax_type_map else 'adults'
                    uniqueReference = extract_data_recursive(fare, ['offerReferences','offerIdentifier','uniqueOfferReference'], '')
                    result['uniqueReference'] = uniqueReference
                    try:
                        group = uniqueReference.split('-')[2]
                    except:
                        continue
                    result['group'] = group
                    result['fare_rule'] = generate_fare_rule_html(fare_rule,result['fareBreakdown']['passengerType'])

                    fare_class = [extract_data_recursive(x, ['flightProductInformationType','cabinProduct','rbd'], '') for x in dictlistconverter(fare.get("segmentInformation"))]
                    
                    fare_cabin = extract_data_recursive(fare, ['segmentInformation','flightProductInformationType','cabinProduct','cabin'], '')
                    cabin = extract_data_recursive(fare, ['segmentInformation','segDetails','segmentDetail','classOfService'], '')
                    result['cabin']  = cabin
                    result['fare_class']  = fare_class
                    result['fare_cabin']  = fare_cabin

                    fareDetails.append( result)
                else:
                    checkin_baggage = extract_data_recursive(fare,['fareInfoGroup','segmentLevelGroup','baggageAllowance',"baggageDetails"],None)
                    if checkin_baggage:
                        if 'quantityCode' in checkin_baggage.keys():
                            if checkin_baggage.get('quantityCode',"")  == "N":
                                if int(checkin_baggage.get('freeAllowance'))  > 1:
                                    checkin_baggage = checkin_baggage.get('freeAllowance',2) + ' Pieces'
                                else:
                                    checkin_baggage = checkin_baggage.get('freeAllowance',1) + ' Piece'
                            elif checkin_baggage.get('quantityCode',"")  == "700":
                                checkin_baggage = checkin_baggage.get('freeAllowance',0) + ' Kilos'
                            else:
                                checkin_baggage = ""
                        else:
                            checkin_baggage = ""
                            
                    else:
                        checkin_baggage = ""
                    result['baggage'] = {"checkInBag":checkin_baggage,"cabinBag":"7 Kg"}
                    result['validatingCarrier'] = oc = extract_data_recursive(fare,['fareInfoGroup','pricingIndicators','companyDetails','otherCompany'],'')
                    designator = extract_data_recursive(fare,['fareInfoGroup','segmentLevelGroup','cabinGroup','cabinSegment','bookingClassDetails','designator'],'')
                    result['uiName']  = result['fareType'] = oc+" "+designator+" Class Fare"
                    result['currency'] = extract_data_recursive(fare, ['fareInfoGroup','fareAmount','monetaryDetails','currency'], 'INR')
                    result['colour'] = 'RED'
                    result['isUpsell'] = False
                    upsell =  False
                    is_refundable = True  # Assume refundable by default

                    for _fare in fare_rule :
                        for fare_warning in _fare.get('tariffInfo', []):
                            for warning in fare_warning.get('fareRuleText', []):
                                warning_text = warning.get('freeText', "")  if warning.get('freeText') else ""
                                if 'NON-REFUNDABLE' in warning_text.upper():
                                    is_refundable = False
                                    break
                    result['isRefundable'] = is_refundable
                    result['fareBreakdown'] = {}
                    fare_details = extract_data_recursive(fare,['fareInfoGroup',"fareAmount"],{})
                    try:
                        base_fare = next(
                        (float(details["amount"]) for key, details in fare_details.items()
                        if isinstance(details, dict) and details.get("typeQualifier") == "E")
                    )
                    except:
                        base_fare = next(
                        (float(details["amount"]) for key, details in fare_details.items()
                        if isinstance(details, dict) and details.get("typeQualifier") == "B"),
                        0.0  # Default value if not found
                    )
                    total_fare = next(
                                (
                                    float(detail["amount"])
                                    for value in fare_details.values()
                                    for detail in (value if isinstance(value, list) else [value])
                                    if isinstance(detail, dict) and detail.get("typeQualifier") == "712"
                                ),
                                0.0  # Default value if not found
                            )

                    tax_fare = total_fare - base_fare
                    result['fareBreakdown']['baseFare'] = base_fare
                    result['fareBreakdown']['tax'] = tax_fare
                    tax_details = dictlistconverter(extract_data_recursive(fare,['fareInfoGroup','surchargesGroup','taxesAmount','taxDetails'],[]))
                    required_taxes = ["YQ", "YR", "K3"]
                    tax_summary = {"YQ": 0, "YR": 0, "K3": 0, "Other Taxes": {}}
                    for tax in tax_details:
                        code = tax["countryCode"]
                        rate = int(tax["rate"])  # Convert rate to integer
                        
                        if code in required_taxes:
                            tax_summary[code] = rate
                        else:
                            tax_summary["Other Taxes"][code] = rate
                    result['fareBreakdown']['tax_splitp'] = tax_summary
                    pax_type = extract_data_recursive(fare,['fareInfoGroup','segmentLevelGroup','ptcSegment','quantityDetails','unitQualifier'],"ADT")
                    result['fareBreakdown']['passengerType'] = pax_type_map[pax_type] if pax_type in pax_type_map else 'adults'
                    result['fare_rule'] = generate_fare_rule_html(fare_rule,result['fareBreakdown']['passengerType'])

                    fare_class=extract_data_recursive(fare,['fareInfoGroup','segmentLevelGroup','fareBasis','additionalFareDetails','rateClass'],"")
                    fare_cabin=extract_data_recursive(fare,['fareInfoGroup','segmentLevelGroup','fareBasis','additionalFareDetails','secondRateClass'],"")
                    cabin = extract_data_recursive(fare,['fareInfoGroup','segmentLevelGroup','cabinGroup','cabinSegment','bookingClassDetails',"designator"],"")
                    result['cabin']  = cabin
                    result['fare_class']  = fare_class
                    result['fare_cabin']  = fare_cabin

                    fareDetails.append(result)       
        new_fareDetails = []    
        groups = list(set([x['uiName'] for x in fareDetails]))
        for group in groups:
            fare_list = [x for x in fareDetails if x['uiName'] == group]
            if (len(fare_list) == int(1 if eval(str(passenger_details['adults']))>=1 else 0) + int(1 if eval(str(passenger_details.get('children',0)))>=1 else 0) + int(1 if eval(str(passenger_details.get('infants',0)))>=1 else 0))  or not upsell:
                idx = [i for i,x in enumerate(fare_list) if x['fareBreakdown']['passengerType'] == 'adults']
                if len(idx)>0:
                    res = fare_list[idx[0]].copy()
                else:
                    res = fare_list[0].copy()
                fB = [x['fareBreakdown'] for x in fare_list]
                res['fareBreakdown'] = fB
                seg_fare_rule = f'''
                                <html>
                                <head>
                                    <style>
                                        body {{
                                            font-family: Arial, sans-serif;
                                            line-height: 1.6;
                                            background-color: #f9f9f9;
                                            margin: 20px;
                                            padding: 20px;
                                        }}
                                        h1 {{
                                            text-align: center;
                                            color: #C02122;
                                        }}
                                        h3 {{
                                            text-align: center;
                                            color: #1150A0;
                                        }}
                                        h2 {{
                                            margin-top: 20px;
                                            color: #1150A0;
                                        }}
                                        .rule-box {{
                                            background: white;
                                            border: 2px solid #1150A0;
                                            border-radius: 8px;
                                            padding: 15px;
                                            margin-bottom: 20px;
                                            box-shadow: 3px 3px 10px rgba(0, 0, 0, 0.1);
                                        }}
                                        .rule-content {{
                                            margin-left: 20px;
                                            padding-left: 10px;
                                            border-left: 3px solid #1150A0;
                                        }}
                                        p {{
                                            margin-bottom: 10px;
                                            color: #333;
                                        }}
                                    </style>
                                </head>
                                <body>
                                '''

                                # Loop through each fare in fare_list and append the generated fare rule HTML
                for _fare in fare_list:
                    if 'fare_rule' in _fare:
                        seg_fare_rule += f'<div class="rule-box">{_fare["fare_rule"]}</div><br>'

                # Closing the HTML structure
                seg_fare_rule += '''
                                </body>
                                </html>
                                '''
                deals = AirlineDeals.objects.filter(status= True)
                #master_doc, raw_data, fare_details,raw_doc,segment_id,itinerary_key
                fare_data = fare_list[0]
                fare_class = fare_data.get("fare_class")
                fare_cabin = fare_data.get("fare_cabin")                

                final_base_fare = 0
                final_tax = 0
                final_YR = 0
                final_YQ = 0
                final_K3 = 0
                final_other_taxes = 0

                # Calculate totals
                for _fare in fare_list:
                    fare_breakdown = _fare["fareBreakdown"]
                    mul_factor = eval(str(passenger_details.get(fare_breakdown["passengerType"],0)))
                    final_base_fare += fare_breakdown["baseFare"]*mul_factor
                    final_tax += fare_breakdown["tax"]*mul_factor
                    final_YR += fare_breakdown["tax_splitp"].get("YR", 0)*mul_factor
                    final_YQ += fare_breakdown["tax_splitp"].get("YQ", 0)*mul_factor
                    final_K3 += fare_breakdown["tax_splitp"].get("K3", 0)*mul_factor
                    final_other_taxes += fare_breakdown["tax_splitp"].get("other_taxes", 0)*mul_factor
                total_fare_before = float(final_base_fare)+float(final_tax)
                unified_fare =  {'finalFareAmount': float(final_base_fare)+float(final_tax),
                                  'finalTaxAmount': float(final_tax),
                                    'finalYR':float(final_YR),
                                      'finalYQ': float(final_YQ),
                                      'finalK3': float(final_K3),
                                        'finalBasic': float(final_base_fare)}
                legs = raw_data[raw_data["itinerary"]]["flightSegments"][raw_data["itinerary"].split('_R_')[0]]

                applicable_deal = find_applicable_deal(deals,legs,fare_class,fare_cabin,user_country)
                deal_applied_result = apply_deal(applicable_deal,unified_fare,tax_condition,fare_adjustment)
                total_passengers = sum(int(value) for value in passenger_details.values()) 
                
                calculated_fares = calculate_fares(deal_applied_result['publishFare'],deal_applied_result['offerFare'],deal_applied_result['discount'],fare_adjustment,tax_condition,1)
                res['fare_rule'] = seg_fare_rule
                res['publishedFare'] = calculated_fares['publish_fare']

                tax_per_pax = round((calculated_fares['publish_fare']-final_base_fare)/total_passengers,2)

                res['misc'] = {"deal":deal_applied_result.get("deal")}

                for _fare in fare_list:
                    fare_breakdown = _fare["fareBreakdown"]
                    fare_breakdown["tax"] = tax_per_pax
                res['offeredFare'] = calculated_fares['offered_fare']
                res['Discount'] = calculated_fares['discount']
                res["fare_id"]= create_uuid("FARE")
                res["segment_id"]= segment_id
                new_fareDetails.append(res)
        return new_fareDetails,"success"

    def get_updated_fare_details(self,index,segment_data, search_details,raw_data,raw_doc,currentfare,fare_details,itinerary_key,session_id):
        session_id = session_id

        vendor_data_raw = raw_doc.get("data")
        fare_adjustment,tax_condition= set_fare_details(fare_details)
        segment_key = flightSegment =itinerary_key
        unified_Segment = raw_data[segment_key]["flightSegments"]
        segments = create_segment_from_unified(unified_Segment)
        passenger_details = search_details.get("passenger_details")
        passenger_counts = convert_pax_types(passenger_details)
        pax_count = sum(passenger_counts.values())
        fare_class = currentfare.get("fare_class")
        TPCBRQ = farequote =fare_quote(session_id,self.base_url,self.credentials,segments,pax_count,fare_class)
        iserror = extract_data_recursive(farequote,["soap_Envelope","soap_Body","Air_SellFromRecommendationReply","errorAtMessageLevel"],"")
        credentials = farequote.get("soap_Envelope").get("soap_Header").get("awsse_Session")
        credentials = {"SessionId": credentials.get("awsse_SessionId"),
                            "SequenceNumber": int(credentials.get("awsse_SequenceNumber")) + 1,
                            "SecurityToken": credentials.get("awsse_SecurityToken")
                            }
        is_round_trip = True if "_R_" in segment_key else False
        is_upsell = currentfare.get('isUpsell',False)
        if is_upsell:
            fare_class = currentfare.get('fareType')
        else:
            fare_class = None
        validating_carrier  = currentfare.get('validatingCarrier')
        currency_iso_code = fare_details.get("currency")
        #TPCBRQ = add_upsell(session_id,self.base_url,credentials,fare_class,validating_carrier,currency_iso_code,is_round_trip)
        credentials = {
            "SessionId": credentials.get("SessionId"),
            "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
            "SecurityToken": credentials.get("SecurityToken")


        }
        progress = "TPCBRQ"
        #info = extract_data_recursive(TPCBRQ,["soap_Envelope","soap_Body","Fare_PricePNRWithBookingClassReply","applicationError","errorWarningDescription","freeText"],"")

        
        
        
        session_break = {}
        IsPriceChanged = False
        updated = True       
        if iserror:
            session_break = {"session_break":iserror}
            print("736 session_break",session_break)
            updated = False

        raw_data[segment_key]['default_baggage'] = currentfare['baggage']
        unified_seg = raw_data|{"fareDetails":currentfare} |session_break
        return {"updated":updated,"data":unified_seg,"raw":TPCBRQ,"status":"success",
                    "IsPriceChanged":IsPriceChanged} if \
                 updated else {"updated":updated,"status":session_break,"data":unified_seg,"raw":farequote,"IsPriceChanged":IsPriceChanged}|session_break

    def get_ssr(self,**kwargs):
        segment_key = kwargs["segment_key"]
        raw_data = kwargs["raw_data"]
        raw_doc = kwargs["raw_doc"]
        session_id = kwargs["session_id"]
        passenger_details =  kwargs["passenger_details"]
        unified_Segment = raw_data[segment_key]["flightSegments"]
        segments = create_segment_from_unified(unified_Segment)
        seatmap =get_seatmap(session_id,self.base_url,self.credentials,segments,passenger_details)
        results = []
        baggage = get_baggage(session_id,self.base_url,self.credentials,segments,passenger_details)
        meals_ssr = {}
        seat_ssr = {}
        baggage_ssr = {}
        is_seats = False
        is_baggage = True
        for segment in segments:
            seg_key = segment.get("trueLocationIdBoard") + "-" + segment.get("trueLocationIdOff")
            raw_baggage = baggage[seg_key]
            corrected_baggage =transform_baggage(raw_baggage)
            for key,val in passenger_details.items():
                if int(val) !=0:
                    meals_ssr[key] = []
                    raw_seatmap = seatmap[seg_key][key]
                    corrected_seatmap =transform_seatmap(raw_seatmap)

                    if corrected_seatmap.get("status") == True:
                        seat_ssr[key] = corrected_seatmap
                        is_seats = True
                    else:
                        seat_ssr[key] = {}
            ssr = {"baggage_ssr":corrected_baggage,"meals_ssr":meals_ssr,"seats_ssr":seat_ssr}
            result = {"Currency":"INR","is_baggage":is_baggage,"is_seats":is_seats,"is_meals":False,"journey_segment":seg_key}|ssr
            results.append(result)


        return {"data":{kwargs.get("segment_key"):results}}
    
    def check_hold(self,fare_quote,itinerary:FlightBookingItineraryDetails):
        return {
            "is_hold":True,
            "is_hold_ssr":True
                }


    def hold_booking(self, raw_data ,fare_details,ssr_response_list,booking,itinerary,pax_details,ssr_details,itinerary_key):

        session_id = booking.session_id
        segment_key = flightSegment =itinerary_key
        progress =""
        info = ""
        try : 
            itinerary.status = "Hold-Initiated"
            itinerary.save(update_fields=["status"])
            unified_Segment = raw_data[segment_key]["flightSegments"]
            segments = create_segment_from_unified(unified_Segment)
            selected_fare = fare_details.get("fareDetails").get(segment_key)
            applied_deal = selected_fare.get("misc",{})
            fare_quote = fare_details.get("fareQuote").get(segment_key)

            credentials = fare_quote.get("soap_Envelope").get("soap_Header").get("awsse_Session")
            credentials = {"SessionId": credentials.get("awsse_SessionId"),
                            "SequenceNumber": int(credentials.get("awsse_SequenceNumber")) + 1,
                            "SecurityToken": credentials.get("awsse_SecurityToken")
                            }
            pax_list = []
            contact =  safe_json_loads(booking.contact)
            contact_phone =  contact.get("phone") ##TODO ADD DEFAULT CONTACTS 
            contact_email = contact.get("email")
            for pax in pax_details:
                if pax.dob:
                    parsed_date = datetime.strptime(pax.dob, "%Y-%m-%dT%H:%M:%S.%fZ")
                    dob = parsed_date.strftime("%d%b%y").upper()
                else:
                    dob = ""
                issue_date =expiry_date= ""
                filtered_ssr = ssr_details.filter(pax=pax).first()
                if pax.passport_issue_date:
                    parsed_issue_date = datetime.strptime(pax.passport_issue_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                    issue_date = parsed_issue_date.strftime("%d%b%y").upper()
                if pax.passport_expiry:
                    parsed_expiry_date = datetime.strptime(pax.passport_expiry, "%Y-%m-%dT%H:%M:%S.%fZ")
                    expiry_date = parsed_expiry_date.strftime("%d%b%y").upper()
                pax_data = {'surname': pax.last_name,
                            'first_name': pax.first_name,
                            'type': reverse_pax_type_map.get(pax.pax_type),
                            'date_of_birth': dob,
                            "email":contact_email,
                            "phone":contact_phone,
                            "passport":pax.passport,
                            "passport_issue_date":issue_date,
                            "passport_expiry_date":expiry_date,
                            "passport_issue_country":pax.passport_issue_country_code,
                            'gender': "M" if pax.gender=="Male" else "F"}
                if filtered_ssr and filtered_ssr.is_seats:
                    pax_data["seat_data"] = {}
                    try:
                        seat_data = []
                        seats_ssr = json.loads(filtered_ssr.seats_ssr)
                        for flight_key in seats_ssr:
                            pax_data["seat_data"][flight_key] = seats_ssr[flight_key]["Code"]
                    except:
                        pass
                if filtered_ssr.is_baggage :
                    pax_data["baggage_data"] = {}
                    try:
                        baggage_data = []
                        baggage_ssr = json.loads(filtered_ssr.baggage_ssr)
                        for flight_key in baggage_ssr:
                            pax_data["baggage_data"][flight_key] = baggage_ssr[flight_key]["Code"]
                    except:
                        pass
                pax_list.append(pax_data)
            ticket_datetime = datetime.now() + timedelta(hours=6)
            ticket_date = ticket_datetime.strftime("%d%m%y")  # Format: DDMMYY
            ticket_time = ticket_datetime.strftime("%H%M")
            pax_list = create_ssr_elements(pax_list,segments,itinerary_key,contact_email,contact_phone)



            PNRADD = add_pnr_data(session_id,self.base_url,credentials, pax_list,ticket_date, ticket_time, segments)
            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")
            }


            progress = "PNRADD"
            TFOPCQ = add_form_of_payment(session_id,self.base_url,credentials)
            progress = "TFOPCQ"

            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")
            }
            is_round_trip = True if "_R_" in segment_key else False
            is_upsell = selected_fare.get('isUpsell',False)
            if is_upsell:
                fare_class = selected_fare.get('fareType')
            else:
                fare_class = None
            validating_carrier  = selected_fare.get('validatingCarrier')
            currency_iso_code = booking.user.organization.organization_country.currency_code
            TPCBRQ = add_upsell(session_id,self.base_url,credentials,fare_class,validating_carrier,currency_iso_code,is_round_trip)
            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")


            }
            progress = "TPCBRQ"
            info = extract_data_recursive(TPCBRQ,["soap_Envelope","soap_Body","Fare_PricePNRWithBookingClassReply","applicationError","errorWarningDescription","freeText"],"")

            
            fareList= TPCBRQ.get("soap_Envelope").get("soap_Body")\
                .get("Fare_PricePNRWithBookingClassReply").get("fareList")
            
            fareList = dictlistconverter(fareList)
            filter_fare_list = fareList
            if fare_class:
                fare_classes = fare_class.split("_")
                filter_fare_list = {}
                pax_types = [pax_data.get("type") for  pax_data in pax_list] 
                for pax_type in pax_types:
                    for fare  in fareList:
                        matched= True
                        discTktDesignator = extract_data_recursive(fare,["segmentInformation","fareQualifier","fareBasisDetails","discTktDesignator"],"ADT")

                        
                        if any({pax_type, discTktDesignator}.issubset(group) for group in pax_mapping):
                            fareComponentDetailsGroup = dictlistconverter(fare.get("fareComponentDetailsGroup"))
                            for idx, fareComponentDetail in enumerate(fareComponentDetailsGroup):
                                fareFamilyname = fareComponentDetail.get("fareFamilyDetails").get("fareFamilyname")
                                if fareFamilyname != fare_classes[idx]:
                                    matched =False
                            if matched:
                                filter_fare_list[pax_type] =fare
                                break
                filter_fare_list = list(filter_fare_list.values())
            if len(filter_fare_list) == 0:
                filter_fare_list = [fareList[0]]
            TAUTCQ = create_ticket(session_id,self.base_url,credentials,filter_fare_list)
            progress = "TAUTCQ"

            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")
            }
            BAGGAGE = add_baggage(session_id,self.base_url,credentials, pax_list, segments)
            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")
            }

            PNRADD_2 = close_PNR(session_id,self.base_url,credentials,comment="TICKETS ARE HOLDED")
            PNR = extract_data_recursive(PNRADD_2,['soap_Envelope','soap_Body','PNR_Reply','pnrHeader','reservationInfo','reservation','controlNumber'],"")
            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")
            }
            progress = "PNRADD_2"

            book_response = extract_data_recursive(PNRADD_2,["soap_Envelope","soap_Body","PNR_Reply"],{})
            if book_response:
                hold_booking_output = {"success": True, "response":book_response,"status":True,
                                    "pnr":PNR,
                                    "booking_id":"",#TODO#
                                    "misc":{},
                                    "is_web_checkin_allowed":False }#TODO#
                itinerary.airline_pnr = hold_booking_output.get("pnr")
                itinerary.supplier_booking_id = hold_booking_output.get("booking_id")
                itinerary.status = "On-Hold"
                itinerary.modified_at = int(time.time())
                itinerary.misc =  json.dumps(hold_booking_output.get("misc"))
                itinerary.save(update_fields=["airline_pnr", "status", "supplier_booking_id","misc","modified_at"])

            else: 
                hold_booking_output = {"status": False,"response":book_response}
                try:
                    error = book_response.get("Response",{}).get("Error",{}).get("ErrorMessage")
                except:
                    error = ""
                itinerary.error = error
                itinerary.status = "Hold-Failed"
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at","error"])
            fare_doc = {
                        "itinerary_id": str(itinerary.id),
                        "hold": book_response,
                        "type":"hold"
                        }
            self.mongo_client.searches.insert_one(fare_doc)
        except:
            hold_booking_output = {"status": False,"response":""}
            itinerary.status = "Hold-Failed"
            itinerary.error = "Hold-Failed"
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["status","modified_at","error"])
            booking.booked_at = int(time.time())
            booking.save(update_fields=["booked_at"])
        return hold_booking_output

    def purchase(self, raw_data ,fare_details,ssr_response_list,booking,itinerary,pax_details,ssr_details,itinerary_key):
        session_id = booking.session_id
        segment_key = flightSegment =itinerary_key
        progress =""
        info = ""
        journey_type = booking.search_details.flight_type
        user_country = booking.user.organization.organization_country.lookup.country_code
        try:
            itinerary.status = "Hold-Initiated"
            itinerary.save(update_fields=["status"])
            unified_Segment = raw_data[segment_key]["flightSegments"]
            segments = create_segment_from_unified(unified_Segment)
            selected_fare = fare_details.get("fareDetails").get(segment_key)
            applied_deal = selected_fare.get("misc",{})
            fare_quote = fare_details.get("fareQuote").get(segment_key)

            credentials = fare_quote.get("soap_Envelope").get("soap_Header").get("awsse_Session")
            credentials = {"SessionId": credentials.get("awsse_SessionId"),
                            "SequenceNumber": int(credentials.get("awsse_SequenceNumber")) + 1,
                            "SecurityToken": credentials.get("awsse_SecurityToken")
                            }
            pax_list = []
            contact =  safe_json_loads(booking.contact)
            contact_phone =  contact.get("phone") ##TODO ADD DEFAULT CONTACTS 
            contact_email = contact.get("email")
            for pax in pax_details:
                if pax.dob:
                    parsed_date = datetime.strptime(pax.dob, "%Y-%m-%dT%H:%M:%S.%fZ")
                    dob = parsed_date.strftime("%d%b%y").upper()
                else:
                    dob = ""
                issue_date =expiry_date= ""
                filtered_ssr = ssr_details.filter(pax=pax).first()
                if pax.passport_issue_date:
                    parsed_issue_date = datetime.strptime(pax.passport_issue_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                    issue_date = parsed_issue_date.strftime("%d%b%y").upper()
                if pax.passport_expiry:
                    parsed_expiry_date = datetime.strptime(pax.passport_expiry, "%Y-%m-%dT%H:%M:%S.%fZ")
                    expiry_date = parsed_expiry_date.strftime("%d%b%y").upper()
                pax_data = {'surname': pax.last_name,
                            'first_name': pax.first_name,
                            'type': reverse_pax_type_map.get(pax.pax_type),
                            'date_of_birth': dob,
                            "email":contact_email,
                            "phone":contact_phone,
                            "passport":pax.passport,
                            "passport_issue_date":issue_date,
                            "passport_expiry_date":expiry_date,
                            "passport_issue_country":pax.passport_issue_country_code,
                            'gender': "M" if pax.gender=="Male" else "F"}
                if filtered_ssr.is_seats :
                        pax_data["seat_data"] = {}
                        try:
                            seat_data = []
                            seats_ssr = json.loads(filtered_ssr.seats_ssr)
                            for flight_key in seats_ssr:
                                pax_data["seat_data"][flight_key] = seats_ssr[flight_key]["Code"]
                        except:
                            pass
                if filtered_ssr.is_baggage :
                    pax_data["baggage_data"] = {}
                    try:
                        baggage_data = []
                        baggage_ssr = json.loads(filtered_ssr.baggage_ssr)
                        for flight_key in baggage_ssr:
                            pax_data["baggage_data"][flight_key] = baggage_ssr[flight_key]["Code"]
                    except:
                        pass
                pax_list.append(pax_data)
            ticket_datetime = datetime.now() + timedelta(hours=6)
            ticket_date = ticket_datetime.strftime("%d%m%y")  # Format: DDMMYY
            ticket_time = ticket_datetime.strftime("%H%M")
            pax_list = create_ssr_elements(pax_list,segments,itinerary_key,contact_email,contact_phone)
        
            PNRADD = add_pnr_data(session_id,self.base_url,credentials, pax_list,ticket_date, ticket_time, segments)
            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")
            }
            progress = "PNRADD"

            TFOPCQ = add_form_of_payment(session_id,self.base_url,credentials)
            progress = "TFOPCQ"

            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")
            }
            is_round_trip = True if "_R_" in segment_key else False
            is_upsell = selected_fare.get('isUpsell',False)
            if is_upsell:
                fare_class = selected_fare.get('fareType')
            else:
                fare_class = None
            validating_carrier  = selected_fare.get('validatingCarrier')
            currency_iso_code = booking.user.organization.organization_country.currency_code
            TPCBRQ = add_upsell(session_id,self.base_url,credentials,fare_class,validating_carrier,currency_iso_code,is_round_trip)
            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")


            }
            progress = "TPCBRQ"
            info = extract_data_recursive(TPCBRQ,["soap_Envelope","soap_Body","Fare_PricePNRWithBookingClassReply","applicationError","errorWarningDescription","freeText"],"")

            
            fareList= TPCBRQ.get("soap_Envelope").get("soap_Body")\
                .get("Fare_PricePNRWithBookingClassReply").get("fareList")
            
            fareList = dictlistconverter(fareList)
            if fare_class:
                fare_classes = fare_class.split("_")
                filter_fare_list = {}
                pax_types = [pax_data.get("type") for  pax_data in pax_list] 
                for pax_type in pax_types:
                    for fare  in fareList:
                        matched= True
                        discTktDesignator = extract_data_recursive(fare,["segmentInformation","fareQualifier","fareBasisDetails","discTktDesignator"],"ADT")

                        if any({pax_type, discTktDesignator}.issubset(group) for group in pax_mapping):
                            fareComponentDetailsGroup = dictlistconverter(fare.get("fareComponentDetailsGroup"))
                            for idx, fareComponentDetail in enumerate(fareComponentDetailsGroup):
                                if fare_classes[idx] !="":
                                    fareFamilyname = fareComponentDetail.get("fareFamilyDetails").get("fareFamilyname")
                                    if fareFamilyname != fare_classes[idx]:
                                        matched =False
                            if matched:
                                filter_fare_list[pax_type] =fare
                                break
                filter_fare_list = list(filter_fare_list.values())
            else:
                filter_fare_list = fareList[0]

            if len(filter_fare_list) == 0:
                filter_fare_list = [fareList[0]]

            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")
            }
            TAUTCQ = create_ticket(session_id,self.base_url,credentials,filter_fare_list)
            progress = "TAUTCQ"

            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")
            }
            BAGGAGE = add_baggage(session_id,self.base_url,credentials, pax_list, segments)
            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")
            }
            billing_code = self.credentials.get("billing_city_code")
            city_code = self.credentials.get("city_code")

            
            PNRADD_2 = close_PNR(session_id,self.base_url,credentials,comment="TICKETS ARE HOLDED")
            
            PNR = extract_data_recursive(PNRADD_2,['soap_Envelope','soap_Body','PNR_Reply','pnrHeader','reservationInfo','reservation','controlNumber'],"")
            if PNR:
                itinerary.status = "On-Hold"
                itinerary.save(update_fields=["status"])

            else:
                itinerary.status = "Hold-Failed"
                itinerary.save(update_fields=["status"])
                return              
        except:
            itinerary.status = "Hold-Failed"
            itinerary.error = "Hold-Failed"
            itinerary.save(update_fields=["status","error"])
            return
        try:
            if itinerary.status == "On-Hold":
                itinerary.status = "Ticketing-Initiated"
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at"])


                if billing_code!=city_code:
                    self.credentials["city_code"] = billing_code
                    PNRRET ,soap_message = import_pnr_data(session_id,self.base_url,self.credentials,PNR,first_time=True)
                    session_info = PNRRET.get(
                        "soap_Envelope").get("soap_Header").get("awsse_Session")
                    
                    credentials = {
                        "SessionId": session_info.get("awsse_SessionId"),
                        "SequenceNumber": int(session_info.get("awsse_SequenceNumber")) + 1,
                        "SecurityToken": session_info.get("awsse_SecurityToken")
                    }  
                    TPCBRQ = add_upsell(session_id,self.base_url,credentials,fare_class,validating_carrier,currency_iso_code,is_round_trip)
                    credentials = {
                        "SessionId": credentials.get("SessionId"),
                        "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                        "SecurityToken": credentials.get("SecurityToken")
                    }
                    progress = "TPCBRQ"
                    info = extract_data_recursive(TPCBRQ,["soap_Envelope","soap_Body","Fare_PricePNRWithBookingClassReply","applicationError","errorWarningDescription","freeText"],"")

                    fareList= TPCBRQ.get("soap_Envelope").get("soap_Body")\
                        .get("Fare_PricePNRWithBookingClassReply").get("fareList")
                    
                    fareList = dictlistconverter(fareList)
                    filter_fare_list = fareList
                    if fare_class:
                        fare_classes = fare_class.split("_")
                        filter_fare_list = {}
                        pax_types = [pax_data.get("type") for  pax_data in pax_list] 
                        for pax_type in pax_types:
                            for fare  in fareList:
                                matched= True
                                discTktDesignator = extract_data_recursive(fare,["segmentInformation","fareQualifier","fareBasisDetails","discTktDesignator"],"ADT")

                                
                                if any({pax_type, discTktDesignator}.issubset(group) for group in pax_mapping):
                                    fareComponentDetailsGroup = dictlistconverter(fare.get("fareComponentDetailsGroup"))
                                    for idx, fareComponentDetail in enumerate(fareComponentDetailsGroup):
                                        fareFamilyname = fareComponentDetail.get("fareFamilyDetails").get("fareFamilyname")
                                        if fareFamilyname != fare_classes[idx]:
                                            matched =False
                                    if matched:
                                        filter_fare_list[pax_type] =fare
                                        break
                        filter_fare_list = list(filter_fare_list.values())
                    if len(filter_fare_list) == 0:
                        filter_fare_list = [fareList[0]]
                    TAUTCQ = create_ticket(session_id,self.base_url,credentials,filter_fare_list)
                    progress = "TAUTCQ"

                    credentials = {
                        "SessionId": credentials.get("SessionId"),
                        "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                        "SecurityToken": credentials.get("SecurityToken")
                    }
                    PNRADD_2 = close_PNR(session_id,self.base_url,credentials,comment="CITY CHANGED")
                    PNR = extract_data_recursive(PNRADD_2,['soap_Envelope','soap_Body','PNR_Reply','pnrHeader','reservationInfo','reservation','controlNumber'],"")
                
                PNRRET ,soap_message = import_pnr_data(session_id,self.base_url,self.credentials,PNR,first_time=True)
                session_info = PNRRET.get(
                    "soap_Envelope").get("soap_Header").get("awsse_Session")
                
                credentials = {
                    "SessionId": session_info.get("awsse_SessionId"),
                    "SequenceNumber": int(session_info.get("awsse_SequenceNumber")) + 1,
                    "SecurityToken": session_info.get("awsse_SecurityToken")
                }  

                TTKTIQ = issue_Ticket(session_id,self.base_url,credentials,indicator="ET")
                progress = "TTKTIQ"
                print(1372,TTKTIQ)

                if TTKTIQ.get("soap_Envelope").get("soap_Body").get("soap_Fault"):
                    info =   TTKTIQ.get("soap_Envelope").get("soap_Body").get("soap_Fault").get("faultstring")
                    return {"status":"failed","info":info}

                book_response = extract_data_recursive(PNRADD_2,["soap_Envelope","soap_Body","PNR_Reply"],{})

                PNRRET ,soap_message = import_pnr_data(session_id,self.base_url,self.credentials,PNR)
                pnr_reply = PNRRET.get("soap_Envelope").get("soap_Body").get("PNR_Reply")
                travellerInfo = pnr_reply.get('travellerInfo')
                travellerInfo = dictlistconverter(travellerInfo)
                ticket_number = ""
                unique_pax_dictionary = {}
                progress = "PNRRET"

                for pax in travellerInfo:
                    unique = extract_data_recursive(pax,['elementManagementPassenger','reference'],'')
                    pax_type = get_pax_type(pax)
                    pax_type = pax_type_map[pax_type] if pax_type in pax_type_map else 'adults'
                    firstName = extract_data_recursive(pax,['enhancedPassengerData','enhancedTravellerInformation','otherPaxNamesDetails','givenName'],'')
                    lastName = extract_data_recursive(pax,['enhancedPassengerData','enhancedTravellerInformation','otherPaxNamesDetails','surname'],'')
                    dob = extract_data_recursive(pax,['enhancedPassengerData','dateOfBirthInEnhancedPaxData','dateAndTimeDetails','date'],'')
                    if len(dob)>0:
                        dob = dob[:2]+'-'+dob[2:4]+'-'+dob[4:]
                    ticket_numbers = [x for x in pnr_reply['dataElementsMaster']['dataElementsIndiv'] if x.get('otherDataFreetext',{}).get('freetextDetail',{}).get('type',"") == 'P06']
                    
                    result = find_matching_element(ticket_numbers, unique)
                    longtext = ""
                    if result:
                        longtext = result.get("otherDataFreetext",{}).get("longFreetext","")
                    if len(longtext)>0:
                        ticket_number = longtext.split('/')[0].replace('PAX','').strip()
                    ticket_numbers = make_ticket_list(ticket_number)
                    for x in ticket_numbers:
                        if firstName + lastName not in unique_pax_dictionary:    
                            unique_pax_dictionary[firstName + lastName] = {'pax_type':pax_type,'firstName':firstName,'lastName':lastName,'dob':dob,'ticketNumber':x} 
                        else:
                            old_ticket_number =  unique_pax_dictionary[firstName + lastName].pop("ticketNumber")
                            new_ticket_number = old_ticket_number +"," + x 
                            unique_pax_dictionary[firstName + lastName].update({'pax_type':pax_type,'firstName':firstName,'lastName':lastName,'dob':dob,'ticketNumber':new_ticket_number})
                progress = "TICKET"

                finance_manager = FinanceManager(booking.user)
                agency_id = str(booking.user.organization.id)
                supplier = self.credentials.get("eazylink_supplier_code")
                ticketing_date = datetime.now().strftime("%Y-%m-%d")

                deals = SupplierDealManagement.objects.all()
                legs = raw_data[raw_data["itinerary"]]["flightSegments"][raw_data["itinerary"].split('_R_')[0]]
                supplier_deal= find_applicable_deal(deals,legs,selected_fare.get("fare_class"),selected_fare.get("fare_cabin"),user_country)
                if len(supplier_deal):
                    supplier_deal = supplier_deal[0]
                else:
                    supplier_deal = {}
                billing_data = {'booking_id':str(booking.id),"customer_end":
                                {
                                    'iata': applied_deal.get("iata_commission",0), 'basic': applied_deal.get("basic",0),
                                    'yq': applied_deal.get("basic_yq",0), 'yr': applied_deal.get("basic_yr",0),
                                        'sfee': 0, 'addamt': 0
                                },
                                "supplier_end":{'iata': supplier_deal.get("iata_commission",0), 'basic': supplier_deal.get("basic",0),
                                    'yq': supplier_deal.get("basic_yq",0), 'yr': supplier_deal.get("basic_yr",0), 'sfee': 0, 'agency_id':agency_id,'supplier':supplier}
                                ,'fop': {'type': 'cash', 'card': ''},'ticketing_date': ticketing_date, 'airline_pnr': PNR
                                }
                response = self.unify_pnr_response(PNRRET)
                unified_booking = FlightBookingUnifiedDetails.objects.filter(itinerary = itinerary.id).first()
                unified_booking_fare = unified_booking.fare_details[itinerary.itinerary_key]

                Discount = unified_booking_fare.get('Discount',0)
                discount_per_pax = Discount/len(pax_list)
                finance_manager.create_offline_billing(data = billing_data,pnr_doc=response,discount_per_pax = discount_per_pax,is_online=True)

                
                if book_response:
                    ticketing_booking_output = {"success": True, "response":book_response,"status":True,
                                        "pnr":extract_data_recursive(book_response,['pnrHeader','reservationInfo','reservation','controlNumber'],""),
                                        "booking_id":"",#TODO#
                                        "misc":{},
                                        "is_web_checkin_allowed":False }#TODO#
                    itinerary.airline_pnr = ticketing_booking_output.get("pnr")
                    itinerary.supplier_booking_id = ticketing_booking_output.get("booking_id")
                    itinerary.status = "Confirmed"
                    itinerary.modified_at = int(time.time())
                    itinerary.misc =  json.dumps(ticketing_booking_output.get("misc"))
                    itinerary.save(update_fields=["airline_pnr", "status", "supplier_booking_id","misc","modified_at"])
                    for pax in pax_details:
                        filtered_ssr = ssr_details.filter(pax=pax).first()
                        first_name = pax.first_name.upper()
                        last_name = pax.last_name.upper()
                        unique_pax_data =  unique_pax_dictionary[first_name+last_name]
                        filtered_ssr.supplier_ticket_number = unique_pax_data["ticketNumber"]
                        filtered_ssr.save()
                else: 
                    ticketing_booking_output = {"status": False,"response":book_response}
                    try:
                        error = book_response.get("Response",{}).get("Error",{}).get("ErrorMessage")
                    except:
                        error = ""
                    itinerary.error = error
                    itinerary.status = "Ticketing-Failed"
                    itinerary.modified_at = int(time.time())
                    itinerary.save(update_fields=["status","modified_at","error"])
                fare_doc = {
                            "itinerary_id": str(itinerary.id),
                                
                            "book": book_response,
                            "type":"book"
                            }
                self.mongo_client.searches.insert_one(fare_doc)

            return ticketing_booking_output
        except:
            ticketing_booking_output ={"status": False,"response":progress}
            itinerary.error = "Ticketing-Failed"
            itinerary.status = "Ticketing-Failed"
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["status","modified_at","error"])
            return ticketing_booking_output


    
    def get_repricing(self,**kwargs):
        itinerary = kwargs["itinerary"]
        airline_pnr = itinerary.airline_pnr
        billing_code = self.credentials.get("billing_city_code")
        self.credentials['city_code']= billing_code
        session_id = itinerary.booking.session_id
        PNRRET ,soap_message = import_pnr_data(session_id,self.base_url,self.credentials,airline_pnr,first_time=True)
        pnr_reply = PNRRET.get("soap_Envelope").get("soap_Body").get("PNR_Reply")
        
        credentials = PNRRET.get("soap_Envelope").get("soap_Header").get("awsse_Session")
        credentials = {"SessionId": credentials.get("awsse_SessionId"),
                            "SequenceNumber": int(credentials.get("awsse_SequenceNumber")) + 1,
                            "SecurityToken": credentials.get("awsse_SecurityToken")
                            }
        is_round_trip = True if "_R_" in itinerary.itinerary_key else False
        fare_detail = FlightBookingFareDetails.objects.filter(itinerary=itinerary).first()
        unified_booking = FlightBookingUnifiedDetails.objects.filter(itinerary = itinerary.id).first()
        selected_fare = unified_booking.fare_details[itinerary.itinerary_key]
        is_upsell = selected_fare.get('isUpsell',False)
        if is_upsell:
            fare_class = selected_fare.get('fareType')
        else:
            fare_class = None
        validating_carrier  = selected_fare.get('validatingCarrier')
        currency_iso_code = itinerary.booking.user.organization.organization_country.currency_code
        TPCBRQ = add_upsell(session_id,self.base_url,credentials,fare_class,validating_carrier,currency_iso_code,is_round_trip)
        credentials = {
            "SessionId": credentials.get("SessionId"),
            "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
            "SecurityToken": credentials.get("SecurityToken")


        }
        progress = "TPCBRQ"
        info = extract_data_recursive(TPCBRQ,["soap_Envelope","soap_Body","Fare_PricePNRWithBookingClassReply","applicationError","errorWarningDescription","freeText"],"")

        
        fareList= TPCBRQ.get("soap_Envelope").get("soap_Body")\
            .get("Fare_PricePNRWithBookingClassReply").get("fareList")

        fareList = dictlistconverter(fareList)
        filter_fare_list = fareList
        pax_objs = FlightBookingPaxDetails.objects.filter(booking = itinerary.booking)
        pax_list= [{"type":pax.pax_type} for pax in pax_objs ]
        if fare_class:
            fare_classes = fare_class.split("_")
            filter_fare_list = {}
            pax_types = [pax_data.get("type") for  pax_data in pax_list] 
            for pax_type in pax_types:
                for fare  in fareList:
                    matched= True
                    discTktDesignator = extract_data_recursive(fare,["segmentInformation","fareQualifier","fareBasisDetails","discTktDesignator"],"ADT")

                    
                    if any({pax_type, discTktDesignator}.issubset(group) for group in pax_mapping):
                        fareComponentDetailsGroup = dictlistconverter(fare.get("fareComponentDetailsGroup"))
                        for idx, fareComponentDetail in enumerate(fareComponentDetailsGroup):
                            fareFamilyname = fareComponentDetail.get("fareFamilyDetails").get("fareFamilyname")
                            if fareFamilyname != fare_classes[idx]:
                                matched =False
                        if matched:
                            filter_fare_list[pax_type] =fare
                            break
            filter_fare_list = list(filter_fare_list.values())
        if len(filter_fare_list) == 0:
            filter_fare_list = [fareList[0]]

        total_fares =  []
        base_fares =  []
        for _fare in filter_fare_list:
            _pax_type = extract_data_recursive(_fare,['segmentInformation','fareQualifier','fareBasisDetails','discTktDesignator'],"ADT") 

            fare_details = _fare.get('fareDataInformation',{}).get('fareDataSupInformation',None)
            fare_details = dictlistconverter(fare_details)
            total_fare = [float(x.get('fareAmount',0)) for x in fare_details if x.get('fareDataQualifier') in ['712','T']]
            base_fare = [
                        float(x.get('fareAmount', 0)) for x in fare_details 
                        if x.get('fareDataQualifier') == 'E'
                    ]
            if not base_fare:
                base_fare = [
                    float(x.get('fareAmount', 0)) for x in fare_details 
                    if x.get('fareDataQualifier') == 'B'
                ]
            if len(base_fare)>0:
                base_fare = sum(base_fare)
            else:
                base_fare = 0
            if len(total_fare)>0:
                total_fare = sum(total_fare)
            else:
                total_fare = 0
            total_fares.append(total_fare)
            base_fares.append(base_fare)
        if len(base_fares)>0:
            base_fare = sum(base_fares)
        else:
            base_fare = 0
        if len(total_fares)>0:
            total_fare = sum(total_fares)
        else:
            total_fare = 0

        is_fare_change = float(total_fare)!=float(fare_detail.published_fare)
        unified_booking.fare_quote = {itinerary.itinerary_key:TPCBRQ}
        unified_booking.save()


        return_data = {"is_fare_change": is_fare_change,"new_fare":total_fare,
                       "old_fare":fare_detail.published_fare,"is_hold_continue":True,"error":None}
        return return_data

    def convert_hold_to_ticket(self,booking,itinerary ,pax_details ,ssr_details ,first_time) :
        session_id = booking.session_id
        try:
            itinerary.status = "Ticketing-Initiated"
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["status","modified_at"])
            unified_booking = FlightBookingUnifiedDetails.objects.filter(itinerary = itinerary.id).first()
            TPCBRQ = unified_booking.fare_quote[itinerary.itinerary_key]
            credentials = TPCBRQ.get("soap_Envelope").get("soap_Header").get("awsse_Session")
            credentials = {"SessionId": credentials.get("awsse_SessionId"),
                                "SequenceNumber": int(credentials.get("awsse_SequenceNumber")) + 1,
                                "SecurityToken": credentials.get("awsse_SecurityToken")
                                }
            selected_fare = unified_booking.fare_details[itinerary.itinerary_key]
            is_upsell = selected_fare.get('isUpsell',False)
            if is_upsell:
                fare_class = selected_fare.get('fareType')
            else:
                fare_class = None
            fareList= TPCBRQ.get("soap_Envelope").get("soap_Body")\
                .get("Fare_PricePNRWithBookingClassReply").get("fareList")

            fareList = dictlistconverter(fareList)
            filter_fare_list = fareList
            pax_objs = FlightBookingPaxDetails.objects.filter(booking = itinerary.booking)
            pax_list= [{"type":pax.pax_type} for pax in pax_objs ]
            if fare_class:
                fare_classes = fare_class.split("_")
                filter_fare_list = {}
                pax_types = [pax_data.get("type") for  pax_data in pax_list] 
                for pax_type in pax_types:
                    for fare  in fareList:
                        matched= True
                        discTktDesignator = extract_data_recursive(fare,["segmentInformation","fareQualifier","fareBasisDetails","discTktDesignator"],"ADT")

                        
                        if any({pax_type, discTktDesignator}.issubset(group) for group in pax_mapping):
                            fareComponentDetailsGroup = dictlistconverter(fare.get("fareComponentDetailsGroup"))
                            for idx, fareComponentDetail in enumerate(fareComponentDetailsGroup):
                                fareFamilyname = fareComponentDetail.get("fareFamilyDetails").get("fareFamilyname")
                                if fareFamilyname != fare_classes[idx]:
                                    matched =False
                            if matched:
                                filter_fare_list[pax_type] =fare
                                break
                filter_fare_list = list(filter_fare_list.values())
            if len(filter_fare_list) == 0:
                filter_fare_list = [fareList[0]]

            TAUTCQ = create_ticket(session_id,self.base_url,credentials,filter_fare_list)
            progress = "TAUTCQ"

            credentials = {
                "SessionId": credentials.get("SessionId"),
                "SequenceNumber": int(credentials.get("SequenceNumber")) + 1,
                "SecurityToken": credentials.get("SecurityToken")
            }
            PNRADD_2 = close_PNR(session_id,self.base_url,credentials,comment="CITY CHANGED")
            PNR = extract_data_recursive(PNRADD_2,['soap_Envelope','soap_Body','PNR_Reply','pnrHeader','reservationInfo','reservation','controlNumber'],"")
            
            PNRRET ,soap_message = import_pnr_data(session_id,self.base_url,self.credentials,PNR,first_time=True)
            session_info = PNRRET.get(
                "soap_Envelope").get("soap_Header").get("awsse_Session")
            
            credentials = {
                "SessionId": session_info.get("awsse_SessionId"),
                "SequenceNumber": int(session_info.get("awsse_SequenceNumber")) + 1,
                "SecurityToken": session_info.get("awsse_SecurityToken")
            }  

            TTKTIQ = issue_Ticket(session_id,self.base_url,credentials,indicator="ET")
            progress = "TTKTIQ"
            print(1372,TTKTIQ)

            if TTKTIQ.get("soap_Envelope").get("soap_Body").get("soap_Fault"):
                info =   TTKTIQ.get("soap_Envelope").get("soap_Body").get("soap_Fault").get("faultstring")
                return {"status":"failed","info":info}

            book_response = extract_data_recursive(PNRADD_2,["soap_Envelope","soap_Body","PNR_Reply"],{})

            PNRRET ,soap_message = import_pnr_data(session_id,self.base_url,self.credentials,PNR)
            pnr_reply = PNRRET.get("soap_Envelope").get("soap_Body").get("PNR_Reply")
            travellerInfo = pnr_reply.get('travellerInfo')
            travellerInfo = dictlistconverter(travellerInfo)
            ticket_number = ""
            unique_pax_dictionary = {}
            progress = "PNRRET"
            user_country = booking.user.organization.organization_country.lookup.country_code
            applied_deal = selected_fare.get("misc",{})

            for pax in travellerInfo:
                unique = extract_data_recursive(pax,['elementManagementPassenger','reference'],'')
                pax_type = get_pax_type(pax)
                pax_type = pax_type_map[pax_type] if pax_type in pax_type_map else 'adults'
                firstName = extract_data_recursive(pax,['enhancedPassengerData','enhancedTravellerInformation','otherPaxNamesDetails','givenName'],'')
                lastName = extract_data_recursive(pax,['enhancedPassengerData','enhancedTravellerInformation','otherPaxNamesDetails','surname'],'')
                dob = extract_data_recursive(pax,['enhancedPassengerData','dateOfBirthInEnhancedPaxData','dateAndTimeDetails','date'],'')
                if len(dob)>0:
                    dob = dob[:2]+'-'+dob[2:4]+'-'+dob[4:]
                ticket_numbers = [x for x in pnr_reply['dataElementsMaster']['dataElementsIndiv'] if x.get('otherDataFreetext',{}).get('freetextDetail',{}).get('type',"") == 'P06']
                
                result = find_matching_element(ticket_numbers, unique)
                longtext = ""
                if result:
                    longtext = result.get("otherDataFreetext",{}).get("longFreetext","")
                if len(longtext)>0:
                    ticket_number = longtext.split('/')[0].replace('PAX','').strip()
                ticket_numbers = make_ticket_list(ticket_number)
                for x in ticket_numbers:
                    if firstName + lastName not in unique_pax_dictionary:    
                        unique_pax_dictionary[firstName + lastName] = {'pax_type':pax_type,'firstName':firstName,'lastName':lastName,'dob':dob,'ticketNumber':x} 
                    else:
                        old_ticket_number =  unique_pax_dictionary[firstName + lastName].pop("ticketNumber")
                        new_ticket_number = old_ticket_number +"," + x 
                        unique_pax_dictionary[firstName + lastName].update({'pax_type':pax_type,'firstName':firstName,'lastName':lastName,'dob':dob,'ticketNumber':new_ticket_number})
            progress = "TICKET"

            finance_manager = FinanceManager(booking.user)
            agency_id = str(booking.user.organization.id)
            supplier = self.credentials.get("eazylink_supplier_code")
            ticketing_date = datetime.now().strftime("%Y-%m-%d")

            deals = SupplierDealManagement.objects.all()

            def build_legs_from_segments(segments):
                # Order the segments by index so the legs are in the correct sequence
                segments_sorted = sorted(segments, key=lambda seg: seg.index)
                legs = []
                for segment in segments_sorted:
                    leg = {
                        "departure": {
                            "airportCode": segment.origin,
                            # Convert your stored Unix timestamp into an ISO formatted string.
                            "departureDatetime": datetime.fromtimestamp(segment.departure_datetime).isoformat(),
                        },
                        "arrival": {
                            "airportCode": segment.destination,
                            "arrivalDatetime": datetime.fromtimestamp(segment.arrival_datetime).isoformat(),
                        },
                        "airlineCode": segment.airline_code,
                        "flightNumber": segment.flight_number,
                        "duration": segment.duration,
                    }
                    legs.append(leg)
                return legs


            legs = build_legs_from_segments(FlightBookingSegmentDetails.objects.filter(journey__itinerary = itinerary ))
            supplier_deal= find_applicable_deal(deals,legs,selected_fare.get("fare_class"),selected_fare.get("fare_cabin"),user_country)
            if len(supplier_deal):
                supplier_deal = supplier_deal[0]
            else:
                supplier_deal = {}
            billing_data = {'booking_id':str(booking.id),"customer_end":
                            {
                                'iata': applied_deal.get("iata_commission",0), 'basic': applied_deal.get("basic",0),
                                    'yq': applied_deal.get("basic_yq",0), 'yr': applied_deal.get("basic_yr",0),
                                    'sfee': 0, 'addamt': 0
                                },
                                "supplier_end":{'iata': supplier_deal.get("iata_commission",0), 'basic': supplier_deal.get("basic",0),
                                    'yq': supplier_deal.get("basic_yq",0), 'yr': supplier_deal.get("basic_yr",0), 'sfee': 0, 'agency_id':agency_id,'supplier':supplier}
                            ,'fop': {'type': 'cash', 'card': ''},'ticketing_date': ticketing_date, 'airline_pnr': PNR
                            }
            response = self.unify_pnr_response(PNRRET)
            unified_booking = FlightBookingUnifiedDetails.objects.filter(itinerary = itinerary.id).first()
            unified_booking_fare = unified_booking.fare_details[itinerary.itinerary_key]

            Discount = unified_booking_fare.get('Discount',0)
            discount_per_pax = Discount/len(pax_list)
            finance_manager.create_offline_billing(data = billing_data,pnr_doc=response,discount_per_pax = discount_per_pax,is_online=True)


            
            if book_response:
                ticketing_booking_output = {"success": True, "response":book_response,"status":True,
                                    "pnr":extract_data_recursive(book_response,['pnrHeader','reservationInfo','reservation','controlNumber'],""),
                                    "booking_id":"",#TODO#
                                    "misc":{},
                                    "is_web_checkin_allowed":False }#TODO#
                itinerary.airline_pnr = ticketing_booking_output.get("pnr")
                itinerary.supplier_booking_id = ticketing_booking_output.get("booking_id")
                itinerary.status = "Confirmed"
                itinerary.modified_at = int(time.time())
                itinerary.misc =  json.dumps(ticketing_booking_output.get("misc"))
                itinerary.save(update_fields=["airline_pnr", "status", "supplier_booking_id","misc","modified_at"])
                for pax in pax_details:
                    filtered_ssr = ssr_details.filter(pax=pax).first()
                    first_name = pax.first_name.upper()
                    last_name = pax.last_name.upper()
                    unique_pax_data =  unique_pax_dictionary[first_name+last_name]
                    filtered_ssr.supplier_ticket_number = unique_pax_data["ticketNumber"]
                    filtered_ssr.save()
            else: 
                ticketing_booking_output = {"status": False,"response":book_response}
                try:
                    error = book_response.get("Response",{}).get("Error",{}).get("ErrorMessage")
                except:
                    error = ""
                itinerary.error = error
                itinerary.status = "Ticketing-Failed"
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at","error"])
            fare_doc = {
                        "itinerary_id": str(itinerary.id),
                            
                        "book": book_response,
                        "type":"book"
                        }
        except:
            itinerary.error = "Ticketing-Failed"
            itinerary.status = "Ticketing-Failed"
            itinerary.modified_at = int(time.time())
            itinerary.save(update_fields=["status","modified_at","error"])
        self.mongo_client.searches.insert_one(fare_doc)

        return ticketing_booking_output


    def retrieve_imported_pnr(self,pnr):
        session_id = ""
        response,soap_message = import_pnr_data(session_id,self.base_url,self.credentials,pnr)
        if response.get("soap_Envelope").get("soap_Body").get("soap_Fault"):
            info = "Supplier Response : " + response.get("soap_Envelope").get("soap_Body").get("soap_Fault").get("faultstring")
            return {"status":False,"info":info}
        offline_billing_response = self.unify_pnr_response(response)
        return offline_billing_response

    def ticketing_import_pnr(self,data,first_time=True):
        session_id = ""
        if first_time:
            pnr = data
            response,soap_message = import_pnr_data(session_id,self.base_url,self.credentials,pnr,first_time)
        else:
            session = data.get("soap_Envelope").get("soap_Header").get("awsse_Session")
            session_info = {
                "SessionId": session.get("awsse_SessionId"),
                "SequenceNumber": int(session.get("awsse_SequenceNumber")) + 1,
                "SecurityToken": session.get("awsse_SecurityToken")
            }
            response,soap_message = import_pnr_data(session_id,self.base_url,session_info,data["pnr"],first_time)

        if response.get("soap_Envelope").get("soap_Body").get("soap_Fault"):
            info =   response.get("soap_Envelope").get("soap_Body").get("soap_Fault").get("faultstring")
            return {"status":"failed","info":info}
        ticketing_billing_response = self.unify_pnr_response(response)
        return {"status":"success","unified":ticketing_billing_response,"raw":response}

    def ticketing_repricing(self,unified,raw,currency_code):
        session_id = ""
        other_company = extract_data_recursive(raw,["soap_Envelope","soap_Body","PNR_Reply","pricingRecordGroup","productPricingQuotationRecord","documentDetailsGroup","fareComponentDetailsGroup","fareFamilyOwner","companyIdentification","otherCompany"],"")
        tst = extract_data_recursive(raw,["soap_Envelope","soap_Body","PNR_Reply"],{})
            #segmentAssociation.selection[1].option
        tst = dictlistconverter(tst.get("tstData"))
        fare_list = []
        response_list = []

        if tst =={}:
            info = "TST Data Not Available"
            return {"status":"failed","info":info}
        tst = dictlistconverter(tst)
        references = []
        for x in tst:
            references.append(x.get("referenceForTstData").get("reference"))
        data = {"currency_iso_code":currency_code,"other_company":other_company,"reference":references}
        session = raw.get("soap_Envelope").get("soap_Header").get("awsse_Session")
        session_info = {
            "SessionId": session.get("awsse_SessionId"),
            "SequenceNumber": int(session.get("awsse_SequenceNumber")) +1,
            "SecurityToken": session.get("awsse_SecurityToken")
        }

        response = repricing_with_pnr(session_id,self.base_url,session_info,data)
        if response.get("soap_Envelope").get("soap_Body").get("soap_Fault"):
            info =   response.get("soap_Envelope").get("soap_Body").get("soap_Fault").get("faultstring")
            return {"status":"failed","info":info}

        new_fare = self.unify_fare_details(raw,response)
        fare_list = new_fare
        response_list = response
        fare_details= unified.get("fareDetails").copy()
        fare_details["fareBreakdown"] = fare_list
        new_raw = response
        new_unified = {"old_fare":unified.get("fareDetails"),"new_fare":fare_details} #TODO change thisto unifiy response

        return {"status":"success","unified":new_unified,"raw":response_list}

    def unify_fare_details(self,PNRRET,TPCBRQ):
                
        fare_details = TPCBRQ.get('soap_Envelope',{}).get('soap_Body',{}).get('Fare_PricePNRWithBookingClassReply',{}).get('fareList',[])
        pnr_reply = PNRRET['soap_Envelope']['soap_Body']['PNR_Reply']

        fare_details = dictlistconverter(fare_details)
        fareBreakdown = []
        for fare_detail in fare_details:
            PT_ref = fare_detail['paxSegReference']['refDetails']
            PT_ref = dictlistconverter(PT_ref)
            PTs = [x['refNumber'] for x in PT_ref if x['refQualifier'] =='PA']
            if len(PTs)==0:
                PTs = [x['refNumber'] for x in PT_ref if x['refQualifier'] =='PI']
            paxes = find_pax_types(pnr_reply['travellerInfo'],PTs)
            if len(paxes)>0:
                if "ADT" in paxes and "INF" in paxes:
                    paxes.remove("INF")
                pax_type = paxes[0]
            else:
                pax_type = 'ADT'
            passengerType = pax_type_map[pax_type] if pax_type in pax_type_map else 'adults'
            Fare = fare_detail.get('fareDataInformation',{}).get('fareDataSupInformation',[])
            baseFare = int(float([x['fareAmount'] for x in Fare if x['fareDataQualifier'] == 'B'][0]))
            totalFare = int(float([x['fareAmount'] for x in Fare if x['fareDataQualifier'] != 'B'][0]))
            taxes = fare_detail.get('taxInformation',{})
            YR = [int(float(extract_data_recursive(x,['amountDetails','fareDataMainInformation','fareAmount'],0))) for x in taxes if extract_data_recursive(x,['taxDetails','taxType','isoCountry'],'') == 'YR']
            if len(YR)>0:
                YR = sum(YR)
            else:
                YR = 0
            YQ = [int(float(extract_data_recursive(x,['amountDetails','fareDataMainInformation','fareAmount'],0))) for x in taxes if extract_data_recursive(x,['taxDetails','taxType','isoCountry'],'') == 'YQ']
            if len(YQ)>0:
                YQ = sum(YQ)
            else:
                YQ = 0
            K3 = [int(float(extract_data_recursive(x,['amountDetails','fareDataMainInformation','fareAmount'],0))) for x in taxes if extract_data_recursive(x,['taxDetails','taxType','isoCountry'],'') == 'K3']
            if len(K3)>0:
                K3 = sum(K3)
            else:
                K3 = 0
            P2 = [int(float(extract_data_recursive(x,['amountDetails','fareDataMainInformation','fareAmount'],0))) for x in taxes if extract_data_recursive(x,['taxDetails','taxType','isoCountry'],'') == 'P2']
            if len(P2)>0:
                P2 = sum(P2)
            else:
                P2 = 0
            IN = [int(float(extract_data_recursive(x,['amountDetails','fareDataMainInformation','fareAmount'],0))) for x in taxes if extract_data_recursive(x,['taxDetails','taxType','isoCountry'],'') == 'IN']
            if len(IN)>0:
                IN = sum(IN)
            else:
                IN = 0
            WO = [int(float(extract_data_recursive(x,['amountDetails','fareDataMainInformation','fareAmount'],0))) for x in taxes if extract_data_recursive(x,['taxDetails','taxType','isoCountry'],'') == 'WO']
            if len(WO)>0:
                WO = sum(WO)
            else:
                WO = 0
            ZR = [int(float(extract_data_recursive(x,['amountDetails','fareDataMainInformation','fareAmount'],0))) for x in taxes if extract_data_recursive(x,['taxDetails','taxType','isoCountry'],'') == 'ZR']
            if len(ZR)>0:
                ZR = sum(ZR)
            else:
                ZR = 0
            Other = [int(float(extract_data_recursive(x,['amountDetails','fareDataMainInformation','fareAmount'],0))) for x in taxes if extract_data_recursive(x,['taxDetails','taxType','isoCountry'],'') not in ['YR','YQ','K3','P2','IN','WO','ZR']]
            if len(Other)>0:
                Other = sum(Other)
            else:
                Other = 0
            other_taxes = totalFare-baseFare-K3
            
            fareBreakdown.append({'passengerType':passengerType,'baseFare':baseFare,
                                'totalFare':totalFare,'YR':YR,'YQ':YQ,'K3':K3,
                                'P2':P2,'IN':IN,'WO':WO,'ZR':ZR,'otherTax':Other,'tax':other_taxes})

        return fareBreakdown

    def ticketing_create(self,unified,raw):
        session_id = ""
        session =raw.get("soap_Envelope").get("soap_Header").get("awsse_Session")
        session_info = {
            "SessionId": session.get("awsse_SessionId"),
            "SequenceNumber": int(session.get("awsse_SequenceNumber")) + 1,
            "SecurityToken": session.get("awsse_SecurityToken")
        }
        fareList = extract_data_recursive(raw,["soap_Envelope","soap_Body","Fare_PricePNRWithBookingClassReply","fareList"],{})
        if fareList == []:
            info = "Fare List not in Ticket Journey"
            return {"status":"failed","info":info} 
        fareList = dictlistconverter(fareList)
        
        response = create_ticket(session_id,self.base_url,session_info,fareList)

        if response.get("soap_Envelope").get("soap_Body").get("soap_Fault"):
            info =   response.get("soap_Envelope").get("soap_Body").get("soap_Fault").get("faultstring")
            return {"status":"failed","info":info}
        return {"status":"success","raw":response}
    
    def ticketing_close_PNR(self,raw):
        session_id = ""
        session = raw.get("soap_Envelope").get("soap_Header").get("awsse_Session")
        session_info = {
            "SessionId": session.get("awsse_SessionId"),
            "SequenceNumber": int(session.get("awsse_SequenceNumber")) + 1,
            "SecurityToken": session.get("awsse_SecurityToken")
        }

        response = close_PNR(session_id,self.base_url,session_info,comment="IMPORT PNR CHANGES ADDED")

        if response.get("soap_Envelope").get("soap_Body").get("soap_Fault"):
            info =   response.get("soap_Envelope").get("soap_Body").get("soap_Fault").get("faultstring")
            return {"status":"failed","info":info}
        return {"status":"success","raw":response}

    def ticketing_issue_ticket(self,raw):
        session_id = ""
        session = raw.get("soap_Envelope").get("soap_Header").get("awsse_Session")
        session_info = {
            "SessionId": session.get("awsse_SessionId"),
            "SequenceNumber": int(session.get("awsse_SequenceNumber")) + 1,
            "SecurityToken": session.get("awsse_SecurityToken")
        }
        response = issue_Ticket(session_id,self.base_url,session_info,indicator="ET")

        if response.get("soap_Envelope").get("soap_Body").get("soap_Fault"):
            info =   response.get("soap_Envelope").get("soap_Body").get("soap_Fault").get("faultstring")
            return {"status":"failed","info":info}
        return {"status":"success","raw":response}

    def security_signout(self,raw):
        session_id = ""
        session = raw.get("soap_Envelope").get("soap_Header").get("awsse_Session")
        session_info = {
            "SessionId": session.get("awsse_SessionId"),
            "SequenceNumber": int(session.get("awsse_SequenceNumber")) + 1,
            "SecurityToken": session.get("awsse_SecurityToken")
        }
        response = signout(session_id,self.base_url,session_info)

        if response.get("soap_Envelope").get("soap_Body").get("soap_Fault"):
            info =   response.get("soap_Envelope").get("soap_Body").get("soap_Fault").get("faultstring")
            return {"status":"failed","info":info}
        return {"status":"success","raw":response}

    def unify_pnr_response(self,resposnse):
        airline_objs = LookupAirline.objects.all()
        airlines = { airline.code: airline for airline in airline_objs }
        airport_objs = LookupAirports.objects.all()
        airports = { airport.code: airport for airport in airport_objs }
        def convert_datetime(date_str,time_str):
            day = int(date_str[:2])
            month = int(date_str[2:4])
            year = int(date_str[4:6])
            if year < 50:
                year += 2000
            else:
                year += 1900
            if not time_str:
                time_str = "0000"
            hour = int(time_str[:2])
            minute = int(time_str[2:])
            dt = datetime(year, month, day, hour, minute)
            dt_str = dt.strftime('%Y-%m-%dT%H:%M:%S')
            return dt_str



        pnr_reply = resposnse['soap_Envelope']['soap_Body']['PNR_Reply']
        itineraryInfo = pnr_reply.get("originDestinationDetails", {}).get("itineraryInfo", {})
        singleItineraryInfo = itineraryInfo if isinstance(itineraryInfo,dict) else itineraryInfo[0]
        classOfService = singleItineraryInfo.get("travelProduct", {}).get("productDetails", {}).get("classOfService", "M")
        booking_class = get_cabin_class(classOfService)  
        offline_billing_response = {}
        pax_types_list = []
        pax_details = []
        travellerInfo = pnr_reply['travellerInfo']
        travellerInfo = dictlistconverter(travellerInfo)
        ticket_number = ""
        unique_pax_dictionary = {}
        for pax in travellerInfo:
            unique = extract_data_recursive(pax,['elementManagementPassenger','reference'],'')
            pax_type = get_pax_type(pax)
            pax_types_list.append(pax_type)
            pax_type = pax_type_map[pax_type] if pax_type in pax_type_map else 'adults'
            firstName = extract_data_recursive(pax,['enhancedPassengerData','enhancedTravellerInformation','otherPaxNamesDetails','givenName'],'')
            lastName = extract_data_recursive(pax,['enhancedPassengerData','enhancedTravellerInformation','otherPaxNamesDetails','surname'],'')
            dob = extract_data_recursive(pax,['enhancedPassengerData','dateOfBirthInEnhancedPaxData','dateAndTimeDetails','date'],'')
            if len(dob)>0:
                dob = dob[:2]+'-'+dob[2:4]+'-'+dob[4:]
            ticket_numbers = [x for x in pnr_reply['dataElementsMaster']['dataElementsIndiv'] if x.get('otherDataFreetext',{}).get('freetextDetail',{}).get('type',"") == 'P06']
            result = find_matching_element(ticket_numbers, unique)
            longtext = ""
            if result:
                longtext = result.get("otherDataFreetext",{}).get("longFreetext","")
            if len(longtext)>0:
                ticket_number = longtext.split('/')[0].replace('PAX','').strip()
            ticket_numbers = make_ticket_list(ticket_number)
            for x in ticket_numbers:
                if firstName + lastName not in unique_pax_dictionary:    
                    unique_pax_dictionary[firstName + lastName] = {'pax_type':pax_type,'firstName':firstName,'lastName':lastName,'dob':dob,'ticketNumber':x} 
                else:
                    old_ticket_number =  unique_pax_dictionary[firstName + lastName].pop("ticketNumber")
                    new_ticket_number = old_ticket_number +"," + x 
                    unique_pax_dictionary[firstName + lastName].update({'pax_type':pax_type,'firstName':firstName,'lastName':lastName,'dob':dob,'ticketNumber':new_ticket_number})
                # pax_details.append({'pax_type':pax_type,'firstName':firstName,'lastName':lastName,'dob':dob,'ticketNumber':x})
        pax_details = list(unique_pax_dictionary.values())
        offline_billing_response['pax_details'] = pax_details
        passenger_details = dict(Counter(item["pax_type"] for item in pax_details))
        if "adults" not in passenger_details:
            passenger_details["adults"] = 0
        if "children" not in passenger_details:
            passenger_details["children"] = 0
        if "infants" not in passenger_details:
            passenger_details["infants"] = 0
        offline_billing_response['passenger_details'] = passenger_details
        flightSegmentsData = pnr_reply['originDestinationDetails']
        flightSegments = []
        if type(flightSegmentsData['itineraryInfo']) == dict:
            itineraryInfo = flightSegmentsData['itineraryInfo']
            airlineCode = extract_data_recursive(itineraryInfo,['travelProduct','companyDetail','identification'],'')
            flightNumber = airlineCode+extract_data_recursive(itineraryInfo,['travelProduct','productDetails','identification'],'')
            equipmentType = extract_data_recursive(itineraryInfo,['flightDetail','productDetails','equipment'],'')
            stop = int(extract_data_recursive(itineraryInfo,['flightDetail','productDetails','numOfStops'],0))
            departure = {}
            departure['airportCode'] = extract_data_recursive(itineraryInfo,['travelProduct','boardpointDetail','cityCode'],'')
            departure['airportName'] = get_airport(departure['airportCode'],airports).name
            departure['country'] = get_airport_country(departure['airportCode'],airports)
            departure['city'] = get_airport_city(departure['airportCode'],airports)
            departure['terminal'] = extract_data_recursive(itineraryInfo,['flightDetail','departureInformation','departTerminal'],'')
            dep_date = extract_data_recursive(itineraryInfo,['travelProduct','product','depDate'],'')
            dep_time = extract_data_recursive(itineraryInfo,['travelProduct','product','depTime'],'')
            departure['departureDatetime'] = convert_datetime(dep_date,dep_time)
            arrival = {}
            arrival['airportCode'] = extract_data_recursive(itineraryInfo,['travelProduct','offpointDetail','cityCode'],'')
            arrival['airportName'] = get_airport(arrival['airportCode'],airports).name
            arrival['country'] = get_airport_country(arrival['airportCode'],airports)
            arrival['city'] = get_airport_city(arrival['airportCode'],airports)
            arrival['terminal'] = extract_data_recursive(itineraryInfo,['flightDetail','arrivalStationInfo','terminal'],'')
            arr_date = extract_data_recursive(itineraryInfo,['travelProduct','product','arrDate'],'')
            arr_time = extract_data_recursive(itineraryInfo,['travelProduct','product','arrTime'],'')
            arrival['arrivalDatetime'] = convert_datetime(arr_date,arr_time)
            durationInMinutes,gmt_departed_time = get_gmt_converted_duration(airports,departure['airportCode'],arrival['airportCode'],
                                                           departure['departureDatetime'],arrival['arrivalDatetime'])
            departure['gmt_departed_time'] = gmt_departed_time
            cabinClass = extract_data_recursive(itineraryInfo,['travelProduct','productDetails','classOfService'],'')
            flightSegments_data = {'airlineCode':airlineCode,'airlineName':get_airline(airlineCode,airlines).name,'flightNumber':flightNumber,
                                'equipmentType':equipmentType,'stop':stop,'departure':departure,"isRefundable":True,
                                'arrival':arrival,'durationInMinutes':durationInMinutes,"cabinClass":cabinClass}
            flightSegments.append(flightSegments_data)
        else:
            for idx, itinerary in enumerate(flightSegmentsData['itineraryInfo']):
                business_action  = extract_data_recursive(itinerary,['itineraryMessageAction','business','function'],'1')
                if business_action in ('32','47'):#32 Miscellaneous 47 Additional service (SVC)
                    continue
                airlineCode = extract_data_recursive(itinerary,['travelProduct','companyDetail','identification'],'')
                flightNumber = airlineCode+extract_data_recursive(itinerary,['travelProduct','productDetails','identification'],'')
                equipmentType = extract_data_recursive(itinerary,['flightDetail','productDetails','equipment'],'')
                stop = int(extract_data_recursive(itinerary,['flightDetail','productDetails','numOfStops'],0))
                arnk = extract_data_recursive(itinerary,['travelProduct','productDetails','identification'],'')
                if arnk =="ARNK":
                    continue
                departure = {}
                departure['airportCode'] = extract_data_recursive(itinerary,['travelProduct','boardpointDetail','cityCode'],'')
                departure['airportName'] = get_airport(departure['airportCode'],airports).name
                departure['country'] = get_airport_country(departure['airportCode'],airports)
                departure['city'] = get_airport_city(departure['airportCode'],airports)
                departure['terminal'] = extract_data_recursive(itinerary,['flightDetail','departureInformation','departTerminal'],'')
                dep_date = extract_data_recursive(itinerary,['travelProduct','product','depDate'],'')
                dep_time = extract_data_recursive(itinerary,['travelProduct','product','depTime'],'')
                departure['departureDatetime'] = convert_datetime(dep_date,dep_time)
                arrival = {}
                arrival['airportCode'] = extract_data_recursive(itinerary,['travelProduct','offpointDetail','cityCode'],'')
                arrival['airportName'] = get_airport(arrival['airportCode'],airports).name
                arrival['country'] = get_airport_country(arrival['airportCode'],airports)
                arrival['city'] = get_airport_city(arrival['airportCode'],airports)
                arrival['terminal'] = extract_data_recursive(itinerary,['flightDetail','arrivalStationInfo','terminal'],'')
                arr_date = extract_data_recursive(itinerary,['travelProduct','product','arrDate'],'')
                arr_time = extract_data_recursive(itinerary,['travelProduct','product','arrTime'],'')
                arrival['arrivalDatetime'] = convert_datetime(arr_date,arr_time)
                durationInMinutes,gmt_departed_time = get_gmt_converted_duration(airports,departure['airportCode'],arrival['airportCode'],
                                                           departure['departureDatetime'],arrival['arrivalDatetime'])
                departure['gmt_departed_time'] = gmt_departed_time
                cabinClass = extract_data_recursive(itinerary,['travelProduct','productDetails','classOfService'],'')
                flightsegments_data = {'airlineCode':airlineCode,'airlineName':get_airline(airlineCode,airlines).name,'flightNumber':flightNumber,
                                    'equipmentType':equipmentType,'stop':stop,'departure':departure,"isRefundable":True,
                                    'arrival':arrival,'durationInMinutes':durationInMinutes,"cabinClass":cabinClass}
                flightSegments.append(flightsegments_data)
        sorted_flights = sorted(flightSegments, key=lambda flight: flight["departure"]["gmt_departed_time"])
        offline_billing_response['flightSegments'] = sorted_flights
        tstData = pnr_reply['tstData']
        fareDetails = {}
        baggage = {'checkInBag':extract_data_recursive(tstData,['fareBasisInfo','fareElement','baggageAllowance'],'7 Kg')}
        fareBasis = extract_data_recursive(tstData,['fareBasisInfo','fareElement','fareBasis'],'')
        fareBreakdown = []
        tstData = dictlistconverter(tstData)
        for tst in tstData:
            PT_ref = tst['referenceForTstData']['reference']
            if type(PT_ref) == list:
                PTs = [x['number'] for x in PT_ref if x['qualifier'] =='PT']
            else:
                PTs = [PT_ref['number']]
            paxes = find_pax_types(pnr_reply['travellerInfo'],PTs)
            if len(paxes)>0:
                if "ADT" in paxes and "INF" in paxes:
                    paxes.remove("INF")
                pax_type = paxes[0]
            else:
                pax_type = 'ADT'
            passengerType = pax_type_map[pax_type] if pax_type in pax_type_map else 'adults'
            Fare = tst.get('fareData',{}).get('monetaryInfo',[])
            taxes = tst.get('fareData',{}).get('taxFields',[])
            try:
                baseFare = float([x['amount'] for x in Fare if x['qualifier'] == 'E'][0])
            except:
                baseFare = float([x['amount'] for x in Fare if x['qualifier'] == 'F'][0])

            totalFare = float([x['amount'] for x in Fare if x['qualifier'] == 'T'][0])
            if totalFare == 0:
                totalFare = baseFare +sum([int(x['taxAmount']) for x in taxes])
            taxes = dictlistconverter(taxes)
            YR = [int(x.get('taxAmount',0)) for x in taxes if x.get('taxCountryCode') == 'YR']
            if len(YR)>0:
                YR = sum(YR)
            else:
                YR = 0
            YQ = [int(x.get('taxAmount',0)) for x in taxes if x.get('taxCountryCode') == 'YQ']
            if len(YQ)>0:
                YQ = sum(YQ)
            else:
                YQ = 0
            K3 = [int(x.get('taxAmount',0)) for x in taxes if x.get('taxCountryCode') == 'K3']
            if len(K3)>0:
                K3 = sum(K3)
            else:
                K3 = 0
            P2 = [int(x.get('taxAmount',0)) for x in taxes if x.get('taxCountryCode') == 'P2']
            if len(P2)>0:
                P2 = sum(P2)
            else:
                P2 = 0
            IN = [int(x.get('taxAmount',0)) for x in taxes if x.get('taxCountryCode') == 'IN']
            if len(IN)>0:
                IN = sum(IN)
            else:
                IN = 0
            WO = [int(x.get('taxAmount',0)) for x in taxes if x.get('taxCountryCode') == 'WO']
            if len(WO)>0:
                WO = sum(WO)
            else:
                WO = 0
            ZR = [int(x.get('taxAmount',0)) for x in taxes if x.get('taxCountryCode') == 'ZR']
            if len(ZR)>0:
                ZR = sum(ZR)
            else:
                ZR = 0
            Other = [int(x.get('taxAmount',0)) for x in taxes if x.get('taxCountryCode') not in ['YR','YQ','K3','P2','IN','WO','ZR']]
            if len(Other)>0:
                Other = sum(Other)
            else:
                Other = 0
            tax = totalFare-baseFare
            other_taxes = tax-K3
            fareBreakdown.append({'passengerType':passengerType,'baseFare':baseFare,
                          'totalFare':totalFare,'YR':YR,'YQ':YQ,'K3':K3,
                          'P2':P2,'IN':IN,'WO':WO,'ZR':ZR,'otherTax':Other,'other_taxes':other_taxes,"tax":tax})
        fareBreakdown = list({tuple(sorted(d.items())): d for d in fareBreakdown}.values())
        fareDetails['baggage'] = baggage
        fareDetails['fareBasis'] = fareBasis
        fareDetails['fareBreakdown'] = fareBreakdown
        fareDetails['meals_ssr'] = 0
        fareDetails['baggage_ssr'] = 0
        fareDetails['seats_ssr'] = 0
        offline_billing_response['fareDetails'] = fareDetails               
        offline_billing_response['booking_id'] = create_uuid("OFFLINE")
        offline_billing_response['gds_pnr'] = extract_data_recursive(pnr_reply,['pnrHeader','reservationInfo','reservation','controlNumber'],'')

        airline_pnr_data = pnr_reply.get('originDestinationDetails',{}).get('itineraryInfo',[])
        if type(airline_pnr_data) == list:
            airline_pnr = [ extract_data_recursive(x,['itineraryReservationInfo','reservation','controlNumber'],'') for x in airline_pnr_data]
        else:
            airline_pnr = [extract_data_recursive(airline_pnr_data,['itineraryReservationInfo','reservation','controlNumber'],'')]
        if len(airline_pnr[0])>0:
            offline_billing_response['airline_pnr'] = airline_pnr[0]
        else:
            offline_billing_response['airline_pnr'] = offline_billing_response['gds_pnr']
        offline_billing_response['cabin_class'] = booking_class
        current_date = datetime.now()
        ticketing_date = current_date - timedelta(days=5)
        ticketing_date = ticketing_date.strftime("%Y-%m-%dT%H:%M:%S")
        start_date = current_date + timedelta(days=5)
        start_date = start_date.strftime("%Y-%m-%dT%H:%M:%S")
        offline_billing_response['ticketing_date'] = ticketing_date
        offline_billing_response['start_date'] = start_date
        return offline_billing_response


def get_gmt_converted_duration(airports,dep_airport,arrival_airport,
                               dep_date,arrival_date):
    try:
        dep_airport_data = get_airport(dep_airport,airports) 
        arr_airport_data = get_airport(arrival_airport,airports)
        dep_airport_latitude = dep_airport_data.latitude
        dep_airport_longitude = dep_airport_data.longitude
        dep_airport_timezone = get_timezone(dep_airport_latitude,dep_airport_longitude,dep_airport_data)
        arrival_airport_latitude = arr_airport_data.latitude
        arrival_airport_longitude = arr_airport_data.longitude
        arrival_airport_timezone = get_timezone(arrival_airport_latitude,arrival_airport_longitude,arr_airport_data)
        if dep_airport_timezone and arrival_airport_timezone:
            local_dep_time = datetime.strptime(dep_date, "%Y-%m-%dT%H:%M:%S")
            local_dep_tz = pytz.timezone(dep_airport_timezone)
            local_dep_time = local_dep_tz.localize(local_dep_time)
            gmt_dep_time = local_dep_time.astimezone(pytz.utc)
            local_arrival_time = datetime.strptime(arrival_date, "%Y-%m-%dT%H:%M:%S")
            local_arrival_tz = pytz.timezone(arrival_airport_timezone)
            local_arrival_time = local_arrival_tz.localize(local_arrival_time)
            gmt_arrival_time = local_arrival_time.astimezone(pytz.utc)
            durationInMinutes = int((gmt_arrival_time - gmt_dep_time).total_seconds()/60)
            return durationInMinutes,gmt_dep_time.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            start_time = datetime.strptime(dep_date,'%Y-%m-%dT%H:%M:%S')
            end_time = datetime.strptime(arrival_date,'%Y-%m-%dT%H:%M:%S')
            time_difference = end_time - start_time
            durationInMinutes = int(time_difference.total_seconds()/60)
            return durationInMinutes,dep_date
    except:
        start_time = datetime.strptime(dep_date,'%Y-%m-%dT%H:%M:%S')
        end_time = datetime.strptime(arrival_date,'%Y-%m-%dT%H:%M:%S')
        time_difference = end_time - start_time
        durationInMinutes = int(time_difference.total_seconds()/60)
        return durationInMinutes,dep_date

def get_timezone(latitude,longitude,airport):
    if airport:
        if airport.timezone:
            return airport.timezone
    try:
        tf = TimezoneFinder()
        timezone_name = tf.timezone_at(lat=latitude, lng=longitude)
        if airport:
            airport.timezone = timezone_name
            airport.save()
        return timezone_name
    except:
        return False

def get_airport_country(airport_code,airports):
    try:
        airport = get_airport(airport_code,airports)
        if airport:
            country = airport.country.country_name
        else:
            country = "N/A"
        return country
    except:
        return "N/A"

def get_airport_city(airport_code,airports):
    try:
        airport = get_airport(airport_code,airports)
        if airport:
            city = airport.city
        else:
            city = airport_code
        return city
    except:
        return airport_code



def get_airline(airline_code,airlines) -> Optional[LookupAirline]:
    return airlines.get(airline_code) 
def get_airport(airport_code,airports) -> Optional[LookupAirports]:
    return airports.get(airport_code)
def get_cabin_class(data):
    map_dict = {'F': 'First Class',
                'C': 'Club (Business)', 'W': 'Economy/Coach Premium', 'M': 'Economy', 'Y': 'Economy'}
    if data.upper() in map_dict and len(data) > 0:
        return map_dict[data.upper()]
    else:
        return ''

def get_amadeus_cabins(data):
    map_dict = { 'First Class':['F'],
                'Business Class': ['C'], 'Premium Economy':["W"], 'Economy':['F', 'Y']}
    if data in map_dict:
        return map_dict[data]
    else:
        return ['F', 'Y']

def get_pax_type(pax):
    pax_type = extract_data_recursive(pax,['enhancedPassengerData','enhancedTravellerInformation','travellerNameInfo','type'],'')
    if pax_type == '':
        pax_type = extract_data_recursive(pax,['passengerData','travellerInformation','passenger'],'')
        if "infantIndicator" in pax_type:
            if pax_type['infantIndicator'] == "1":
                pax_type = "INF"
            else:
                pax_type = "ADT"
        else:
            pax_type = "ADT"
    
    return pax_type

def find_pax_types(travellerInfo,PTs):
    pax_types = []
    if type(travellerInfo) == list:
        for x in travellerInfo:
            if x['elementManagementPassenger']['reference']['number'] in PTs:
                pax_type = get_pax_type(x)
                pax_types.append(pax_type)
    else:
        x = travellerInfo
        if x['elementManagementPassenger']['reference']['number'] in PTs:
            pax_type = get_pax_type(x)
            pax_types.append(pax_type)    
    
    return pax_types

pax_type_map = {'ADT':'adults','CHD':'children','CNN':'children','INF':'infants'}
reverse_pax_type_map = {'adults':'ADT','children':'CHD','infants':'INF','child':'CHD','infant':'INF'}
def convert_pax_types(pax_counts):
    mapping = {'adults': 'ADT', 'children': 'CHD', 'infants': 'INF'}
    converted = {mapping[key]: int(value) for key,
                 value in pax_counts.items() if key in mapping}

    return converted

def calculate_fare(passenger_details,fareBreakdown):

    base = 0
    tax = 0
    for fB in fareBreakdown:
        base += (fB.get('baseFare',0) * int(passenger_details.get(fB.get('passengerType',''),0)))
        tax += (fB.get('tax',0) * int(passenger_details.get(fB.get('passengerType',''),0)))
    return {"baseFare":base,"tax":tax}

def create_segment_from_unified(unified_Segment):
    segments = []
    item_number =1
    for idx,(flight_key, segments_list) in enumerate(unified_Segment.items(),start = 1):
        flight_indicator = idx                
        for flight_segment in segments_list:
            departure_date = datetime.strptime(flight_segment["departure"]["departureDatetime"], "%Y-%m-%dT%H:%M:%S")
            arrival_date = datetime.strptime(flight_segment["arrival"]["arrivalDatetime"], "%Y-%m-%dT%H:%M:%S")
            segment = {
                "departureDate": departure_date.strftime("%d%m%y"),
                "departureTime": departure_date.strftime("%H%M"),
                "arrivalDate": arrival_date.strftime("%d%m%y"),
                "arrivalTime": arrival_date.strftime("%H%M"),
                "trueLocationIdBoard": flight_segment["departure"]["airportCode"],
                "trueLocationIdOff": flight_segment["arrival"]["airportCode"],
                "marketingCompany": flight_segment["airlineCode"],
                "flightNumber": flight_segment["flightNumber"],
                "bookingClass": flight_segment["cabin"],
                "flightIndicator": flight_indicator,
                "fareBasisCode": flight_segment["fareBasisCode"],
                "flightIndicator": flight_indicator,
                "itemNumber": item_number
            }
            item_number+=1
            segments.append(segment)
    return segments

type_map = {'ADT':'adults','CHD':'children','CH':'children','INF':'infants','CNN':'children','IN':'infants'}
def safe_json_loads(data):
    """Safely load JSON, returning an empty dictionary if the input is None or invalid."""
    try:
        return json.loads(data) if data else {}
    except (json.JSONDecodeError, TypeError):
        return {}
    
def calculate_fares(published_fare,offered_fare,discount,fare_adjustment,tax_condition,total_pax_count):
    supplier_published_fare = published_fare
    supplier_offered_fare = offered_fare
    new_published_fare = (supplier_published_fare + (float(fare_adjustment["markup"]))+(float(fare_adjustment["distributor_markup"]))-\
                    float(fare_adjustment["cashback"]) - float(fare_adjustment["distributor_cashback"]))*total_pax_count
    new_offered_fare = (supplier_published_fare + (float(fare_adjustment["markup"]) + float(fare_adjustment["distributor_markup"]) -\
        float(fare_adjustment["cashback"])-float(fare_adjustment["distributor_cashback"]))*total_pax_count -\
        (discount)*(float(fare_adjustment["parting_percentage"])/100)*(float(fare_adjustment["distributor_parting_percentage"])/100)*(1-float(tax_condition["tds"])/100))*total_pax_count

    return {"offered_fare":new_offered_fare,"discount":new_published_fare-new_offered_fare,"publish_fare":new_published_fare,
            "supplier_published_fare":supplier_published_fare,"supplier_offered_fare":supplier_offered_fare}

def find_applicable_deal(deals,legs,fare_class,fare_cabin,user_country):
    final_deal = []
    for deal_obj in deals:
        cabins = deal_obj.cabin.split(",") if deal_obj.cabin else []

        if cabins and fare_cabin not in cabins:
            continue

        
        class_included = deal_obj.class_included.split(",") if deal_obj.class_included else []

        if class_included and fare_class[0] not in class_included:
            continue
        # Class excluded check
        
        class_excluded = deal_obj.class_excluded.split(",") if deal_obj.class_excluded else []
        if fare_class[0] in class_excluded:
            continue

        # Multi-segment handling
        source = legs[0]['departure']['airportCode']
        source_country = legs[0]['departure']['countryCode']
        destination = legs[-1]['arrival']['airportCode']
        destination_country = legs[-1]['arrival']['countryCode']
        travel_date = legs[0]['departure']['departureDatetime']
        airline_codes = [leg['airlineCode'] for leg in legs]

        flight_type = source_country == user_country and destination_country == user_country
        journey_type =  "DOM" if flight_type else "INT"
        soto = source_country == user_country or destination_country == user_country


        if deal_obj.deal_type != journey_type:
            continue


        if deal_obj.code_sharing:
            if deal_obj.airline.code not in airline_codes:
                continue
        else:
            if not (deal_obj.airline.code in airline_codes and len(set(airline_codes)) == 1):
                continue

        if deal_obj.sector:
            if source not in deal_obj.source and destination not in deal_obj.destination:
                continue
        else:
            if source in deal_obj.source or destination in deal_obj.destination:
                continue

        if deal_obj.country_applicability:
            if source_country not in deal_obj.source_country_code and destination_country not in deal_obj.destination_country_code:
                continue
        else:
            if source_country in deal_obj.source_country_code or destination_country in deal_obj.destination_country_code:
                continue
        
        if soto!=deal_obj.soto and deal_obj.soto:
            continue

        # Validity date check
        travel_timestamp = int(datetime.strptime(travel_date, "%Y-%m-%dT%H:%M:%S").timestamp() * 1000)  # Convert to milliseconds
        if travel_timestamp < deal_obj.valid_till:
            final_deal.append({
                'iata_commission': deal_obj.iata_commission,
                'basic': deal_obj.basic,
                'basic_yq': deal_obj.basic_yq,
                'basic_yr': deal_obj.basic_yr
            })
        else:
            # Use post-validity values
            final_deal.append({
                'iata_commission': deal_obj.iata_commission,
                'basic': deal_obj.basic_after_valid_date,
                'basic_yq': deal_obj.yq_after_valid_date,
                'basic_yr': deal_obj.yr_after_valid_date
            })

    return final_deal
    
def apply_deal(applicable_deal,unified_fare,tax_condition,fare_adjustment):
    result = {"publishFare": 0,
                "offerFare": 0,
                "Discount": 0,
                "currency": "INR"
            }
    if len(applicable_deal)>0:
        applicable_deal = applicable_deal[0]
        markup = fare_adjustment.get('markup',0)
        cashback = fare_adjustment.get('cashback',0)
        parting_percentage = fare_adjustment.get('parting_percentage',100) #DEFAULT
        distributor_markup = fare_adjustment.get('distributor_markup',0)
        distributor_cashback = fare_adjustment.get('distributor_cashback',0)
        gst = tax_condition.get("tax",18) #DEFAULT
        tds = tax_condition.get("tds",2) #DEFAULT
        distributor_parting_percentage = fare_adjustment.get('distributor_parting_percentage',100) #DEFAULT
        
        publishedFare = unified_fare['finalFareAmount']        

        Iata_value = unified_fare['finalBasic']*applicable_deal['iata_commission']/100
        PLB = (Iata_value+(( unified_fare['finalBasic'] - Iata_value)*applicable_deal['basic']/100 + \
                            unified_fare['finalYQ']*applicable_deal['basic_yq']/100 + \
                            unified_fare['finalYR']*applicable_deal['basic_yr']/100 )) *(1-gst/100)
        commision = PLB


        offeredFare = publishedFare-commision
        discount  =commision
        result['discount'] = discount
        result['offerFare'] = offeredFare
        result['publishFare'] = publishedFare
        result["deal"] = applicable_deal

    else:
        result["deal"] = False
        result['publishFare'] = unified_fare['finalFareAmount']
        result['discount'] = 0
        result['offerFare'] = unified_fare['finalFareAmount']
    return result

def compute_total_price(monetary_details):
    """Compute a total price from a list of monetary details.
       In this example we simply sum the amounts (after converting to int)."""
    total = 0
    for detail in monetary_details:
        try:
            total += int(detail.get("amount", "0"))
        except ValueError:
            pass
    return total



def transform_seatmap(amadeus_response):
    amadeus_response = amadeus_response.get("soap_Envelope").get("soap_Body")
    def build_price_mapping(customer_centric_data):

        mapping = {}    
        seat_price_list = customer_centric_data.get("seatPrice", [])
        if not isinstance(seat_price_list, list):
            seat_price_list = [seat_price_list]
        
        for price_element in seat_price_list:
            monetary_details = price_element.get("seatPrice", {}).get("monetaryDetails", [])
            total_price = compute_total_price(monetary_details)
            price_ref_raw = price_element.get("priceRef", {})
            if isinstance(price_ref_raw, list):
                price_ref_raw = price_ref_raw[0]
            referenceDetails =  price_ref_raw.get("referenceDetails", {})
            if isinstance(referenceDetails, list):
                referenceDetails = referenceDetails[0]
            price_ref =referenceDetails.get("value")
            row_details = price_element.get("rowDetails", [])
            if isinstance(row_details, dict):
                row_details = [row_details]
            for row_item in row_details:
                row_num = row_item.get("seatRowNumber")
                occ = row_item.get("seatOccupationDetails", [])
                if isinstance(occ, dict):
                    occ = [occ]
                for occ_item in occ:
                    seat_col = occ_item.get("seatColumn")
                    if row_num and seat_col:
                        mapping[(row_num, seat_col)] = {"price": total_price, "ref": price_ref}
        return mapping

    def build_catalog_mapping(catalog_data):
        mapping = {}
        catalog_data = dictlistconverter(catalog_data)
        for item in catalog_data:
            ref_val = item.get("catalogueRef", {}).get("referenceDetails", {}).get("value")
            free_text = item.get("catalogueDescription", {}).get("freeText", "")
            mapping[ref_val] = free_text
        return mapping

    def is_seat_booked(seat_occ_details, col):
        if not seat_occ_details:
            return False
        if isinstance(seat_occ_details, dict):
            seat_occ_details = [seat_occ_details]
        for detail in seat_occ_details:
            if detail.get("seatColumn") == col:
                if detail.get("seatOccupation", "").upper() == "O":
                    return True
        return False

    def get_seat_columns(seatmap_info):
        cabin = seatmap_info.get("cabin")
        if cabin:
            if isinstance(cabin, list):
                for comp in cabin:
                    comp_det = comp.get("compartmentDetails", {})
                    if "columnDetails" in comp_det:
                        return [d.get("seatColumn") for d in comp_det["columnDetails"] if d.get("seatColumn")]
            elif isinstance(cabin, dict):
                comp_det = cabin.get("compartmentDetails", {})
                if "columnDetails" in comp_det:
                    return [d.get("seatColumn") for d in comp_det["columnDetails"] if d.get("seatColumn")]
        return ['A', 'B', 'C', 'D', 'E', 'F']


    if "Air_RetrieveSeatMapReply" in amadeus_response:
        seatmap_info = amadeus_response.get("Air_RetrieveSeatMapReply", {}).get("seatmapInformation", {})
    else:
        seatmap_info = amadeus_response.get("seatmapInformation", {})
    customer_data = seatmap_info.get("customerCentricData", {})
    price_avail = True
    if customer_data =={}:
        price_avail = False
    price_mapping = build_price_mapping(customer_data)
    catalog_mapping = build_catalog_mapping(seatmap_info.get("catalogData", []))
    seat_columns = get_seat_columns(seatmap_info)
    if len(seat_columns) < 6:
        seat_columns = seat_columns + ['A','B','C','D','E','F']
        seat_columns = seat_columns[:6]
    elif len(seat_columns) > 6:
        seat_columns = seat_columns[:6]
    
    total_columns = 7  # 6 seats with a gap inserted after the third seat
    seatmap_output = []
    rows = seatmap_info.get("row", [])
    for row_entry in rows:
        row_details = row_entry.get("rowDetails", {})
        row_num = row_details.get("seatRowNumber")
        if not row_num:
            continue

        occ_details = row_details.get("seatOccupationDetails")
        if occ_details and isinstance(occ_details, dict):
            occ_details = [occ_details]
            
        seats = []
        for i, col in enumerate(seat_columns):
            if i == 3:
                seats.append({"seatType": None})
            
            seat_code = f"{row_num}{col}"
            booked = is_seat_booked(occ_details, col)
            seatType =1
            price_info = price_mapping.get((row_num, col))
            if price_info:
                price = price_info.get("price", 0)
                if price == 0:
                    seatType = -1
                ref = price_info.get("ref")
                cat_text = catalog_mapping.get(ref, "")
                info = f"{cat_text.capitalize()} Seat" if cat_text.upper() == "AISLE" else cat_text.capitalize()
            else:
                price = 0
                seatType = -1

                info = ""
            
            seat_obj = {
                "Code": seat_code,
                "isBooked": booked,
                "Price": price,
                "seatType": seatType,  # assuming normal seat is type 1
                "info": info
            }
            seats.append(seat_obj)
        
        while len(seats) < total_columns:
            seats.append({"seatType": None})
        
        seatmap_output.append({
            "row": int(row_num),
            "seats": seats
        })
    
    output = {
        "status":price_avail,
        "seatmap": seatmap_output,
        "seat_data": {
            "row": len(seatmap_output),
            "column": total_columns
        }
    }
    return output

def transform_baggage(amadeus_response):
    
    def sort_baggage_options(baggage_data):
        def sort_key(option):
            weight = option.get("Weight", 0)
            price = option.get("Price", "0")
            return (weight, float(price))

        for key in ["adults", "children"]:
            if key in baggage_data:
                baggage_data[key] = sorted(baggage_data[key], key=sort_key)
        return baggage_data
    
    def extract_service_name(service_attributes):

        for attr in service_attributes:
            cd = dictlistconverter(attr.get('criteriaDetails'))
            for item in cd:
                if item.get('attributeType') == 'CNM':
                    return item.get('attributeDescription', 'N/A')
        return 'N/A'
    
    def extract_price_info(pricing_group):
        computed = pricing_group.get('computedTaxSubDetails', {})
        monetary = computed.get('monetaryDetails')
        if monetary and monetary.get('amount'):
            return monetary.get('amount'), monetary.get('currency', 'INR')
        # Fallback: mark as free or missing
        return "0", "INR"  # or consider returning (None, "INR") if that makes downstream logic easier

        
    def split_baggage_by_passenger(baggage_response):
       
        def extract_weight_and_unit(service, name):
            # 1. Try extracting weight from the service name first.
            match = re.search(r'(\d+)\s*kg', name, re.IGNORECASE)
            if match:
                return int(match.group(1)), "KG"
            # 2. Try extracting from baggageDescriptionGroup if available.
            baggage_data = service.get("baggageDescriptionGroup", {}).get("baggageData", {})
            details = baggage_data.get("baggageDetails", {})
            text = details.get("attributeDescription", "")
            match = re.search(r'(\d+)\s*kg', text, re.IGNORECASE)
            if match:
                return int(match.group(1)), "KG"
            # 3. Check for weight in serviceFreeText of specialRequirementsInfo.
            special_req = service.get("serviceDetailsGroup", {}).get("serviceDetails", {}).get("specialRequirementsInfo", {})
            free_text = special_req.get("serviceFreeText", [])
            if isinstance(free_text, list) and free_text:
                for item in free_text:
                    # If the text is just a number, assume it's the weight.
                    if re.fullmatch(r'\d+', item):
                        return int(item), "KG"
            # Fallback: could return a default or flag as missing
            return 0, "KG"  # Alternatively, return (None, None) to flag missing weight


        
        result = {"adults": [], "children": []}
        for service in baggage_response:
            code = service.get('serviceCodes', {}).get('otherSpecialCondition', 'N/A')
            attributes = service.get('serviceAttributes', [])
            #Service_StandaloneCatalogueReply.serviceGroup[0].serviceCodes.otherSpecialCondition
            #Service_StandaloneCatalogueReply.serviceGroup[0].serviceDetailsGroup.serviceDetails.specialRequirementsInfo.ssrCode
            rf_code = extract_data_recursive(service,['serviceDetailsGroup','serviceDetails','specialRequirementsInfo','ssrCode'],"XBAG")
            name = extract_service_name(attributes)

            baggage_details = None
            
            pricing_groups = dictlistconverter(service.get('pricingGroup', []))
            for idx,pg in enumerate(pricing_groups):
                price,currency = extract_price_info(pg)
                
                passenger_ref = pg.get('passengerReference', {}).get('referenceDetails', [])
                if not isinstance(passenger_ref, list):
                    passenger_ref = [passenger_ref]
                
                for ref in passenger_ref:
                    if ref.get('type') == 'P':
                        passenger_value = ref.get('value')
                        # Build a simplified baggage option record
                        weight, unit = extract_weight_and_unit(service,name)
                        baggage_option = {
                            'Code': code+"_"+rf_code,
                            'Weight': weight,
                            'Unit': unit,
                            'Price': float(price),
                            'Description': baggage_details
                        }
                        if passenger_value == "1":
                            result["adults"].append(baggage_option)
                        elif passenger_value == "2":
                            result["children"].append(baggage_option)

        return sort_baggage_options(result)
    try:
        baggage_response = amadeus_response.get("soap_Envelope").get("soap_Body").get("Service_StandaloneCatalogueReply")
        baggage_response = baggage_response["serviceGroup"]
        x = split_baggage_by_passenger(baggage_response)
        return x
    except:
        return {'adults':[],'children':[],}

def create_ssr_elements(selected_passengers, flight_segments,itinerary_key,contact_email,contact_phone):
    for idx,passenger in enumerate(selected_passengers):
        ssr_elements = []
        for idy,segment in enumerate(flight_segments):
            seg_key = segment.get("trueLocationIdBoard") + "-" + segment.get("trueLocationIdOff") 
            if passenger.get("seat_data",False):
                if passenger["seat_data"].get(seg_key,False):
                    docs = {        
                        "type": "STR",
                        "data": passenger["seat_data"][seg_key],
                        "segment":idy+1,
                        "pax":idx+2
                    }
                    ssr_elements.append(docs)
        

        if "_R_"  in itinerary_key:
            int_docs = {
                "type": "DOCO",
                "status": "HK",
                "quantity": 1,
                "company_id": flight_segments[0]["marketingCompany"],  # Link to the first flight segment's company
                "freetext": f"/V/{passenger['passport']}///{passenger['passport_issue_country']}//{passenger['passport_issue_date']}"
            }
            ssr_elements.append(int_docs)
        
        docs = {
                        "type": "DOCS",
                        "status": "HK",
                        "company_id": segment["marketingCompany"],  # Link to the first flight segment's company
                        "freetext": f"P-{passenger.get('passport_issue_country', 'IN')}-{passenger.get('passport', '').upper()}-"
                                    f"{passenger.get('passport_issue_country', 'IN')}-"
                                    f"{passenger.get('date_of_birth', '').upper()}-"
                                    f"{passenger.get('gender', '').upper()}-"
                                    f"{passenger.get('passport_expiry_date', '').upper()}-"
                                    f"{passenger.get('first_name', '').upper()}-"
                                    f"{passenger.get('surname', '').upper()}"
                    }
            

        ssr_elements.append(docs)

        # CTCE SSR Element
        ctce = {
            "type": "CTCE",
            "status": "HK",
            "company_id": flight_segments[0]["marketingCompany"],
            "freetext": contact_email.replace("@", "//").upper()  # Replace '@' with '//'
        }
        ssr_elements.append(ctce)

        # CTCM SSR Element
        ctcm = {
            "type": "CTCM",
            "status": "HK",
            "company_id": flight_segments[0]["marketingCompany"],
            "freetext": f"{contact_phone}/IN".upper()  # Append country code '/IN' for India
        }
        ssr_elements.append(ctcm)

        # CTCR SSR Element
        if flight_segments[0]["marketingCompany"] =="AI":
            ai_ctcr = {
                "type": "CTCR",
                "status": "HK",
                "company_id": flight_segments[0]["marketingCompany"],
                "freetext": "NON-CONSENT FOR AI"
            }
            ssr_elements.append(ai_ctcr)

        # Add flight-specific SSR elements (e.g., INFT for infants)
        if passenger["type"] == "INF":
            for segment in flight_segments:
                infant_ssr = {
                    "type": "INFT",
                    "status": "HK",
                    "company_id": segment["marketingCompany"],
                    "freetext": f"{passenger['surname'].upper()}/{passenger['first_name'].upper()} {passenger['date_of_birth'].upper()}"
                }
           # ssr_elements.append(infant_ssr)
        passenger["ssr"] = ssr_elements
    return selected_passengers

def find_matching_element(data, key):
    for element in data:
        references = element.get("referenceForDataElement", {}).get("reference", [])
        if key in references:
            return element
    return None

def make_ticket_list(input_string):
    prefix = input_string.split("-")[0]
    postfix = ("-").join(input_string.split("-")[1:])
    ticket_numbers = [input_string]
    if '-' in postfix:
        before_sep =  postfix.split("-")[0]
        seperation = postfix.split("-")[1]
        len_seperation = len(seperation)
        base = before_sep[:-len_seperation]
        ticket_numbers = [prefix+"-"+before_sep,prefix+"-"+base+seperation]
    return ticket_numbers

pax_mapping = [{"ADT","adults","Adult","Adults"},
                                {"CHD", "CH", "Child","child", "Children", "CNN"},
                                {"INF", "INS", "Infant", "Infants","infant", "IN"},
                            ]