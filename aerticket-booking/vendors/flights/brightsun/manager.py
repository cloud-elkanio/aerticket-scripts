from vendors.flights.abstract.abstract_flight_manager import AbstractFlightManager
from vendors.flights.brightsun.api  import flight_search,pricing_availability_search,purchase_api
from datetime import datetime,timedelta
import re


from vendors.flights.utils import create_uuid,set_fare_details

JOURNEY_TYPES = ['One Way','Round Trip', 'Multi City']

class Manager(AbstractFlightManager):
    def __init__(self,data,uuid):
        self.vendor_id = "VEN-"+str(uuid)
        self.base_url = "https://api.brightsun.co.uk/api/BSFlight/"
        self.credentials = data |{"account_code":"BS1333"}

    def get_journey_types(self):
        return JOURNEY_TYPES
    def name(self):
        return "Brightson"
    def get_vendor_id(self):
        return self.vendor_id
    def purchase(self,search_details,booking_details,raw_details):
        response = purchase_api(self.base_url,self.credentials,search_details,booking_details,raw_details)
        return response
    def search_flights(self,journey_details):
        journey_type = journey_details.get("journey_type")

        if journey_type== "Mutli City":
            return
        joruney =  journey_details.get("journey_details")[0]
        source = joruney.get("source_city")
        destination = joruney.get("destination_city")
        departure_date = joruney.get("travel_date")
        cabin_class = journey_details.get("cabin_class","Economy")
        pax = journey_details.get("passenger_details")
        if journey_type== "One Way":

            flight_search_response = flight_search(self.base_url,self.credentials,trip_type="OW",
                                               origin=source,destination=destination,cabin_class=cabin_class,
                                               depart_date=departure_date,arrival_date = None,pax = pax)
            
        if journey_type== "Round Trip":
            return_journey =  journey_details.get("journey_details")[1]
            arrival_date = return_journey.get("travel_date")
            flight_search_response = flight_search(self.base_url,self.credentials,trip_type="RT",
                                               origin=source,destination=destination,cabin_class=cabin_class,
                                               depart_date=departure_date,arrival_date = arrival_date,pax=pax)
        
        for x in flight_search_response['result']['airSolutions']:
            for y in x["journey"]:
                for z in y ["optionInfos"]:
                    seg = str(self.vendor_id)+"_$_"+create_uuid("SEG")
                    z["segmentID"] = seg
        
        return flight_search_response

    def converter(self, search_response, journey_details,fare_details):
        fare_adjustment,tax_condition= set_fare_details(fare_details)

        if journey_details["journey_type"] =="One Way":
            date = "".join(journey_details["journey_details"][0]["travel_date"].split('-')[:2])
            flightSegment = journey_details["journey_details"][0]["source_city"]+"_"+journey_details["journey_details"][0]["destination_city"]+"_"+date
            result = {"itineraries":[flightSegment],flightSegment:[]}
            for air_solution in search_response['result']['airSolutions']:
                journey = air_solution['journey'][0]
                for option in journey['optionInfos']:
                    unified_structure = {"flightSegments":{flightSegment:[]}}
                    flight = option['airSegmentInfos'][0]
                    unified_flight_segment = {
                        "airlineCode": flight.get("carrier", None),
                        "airlineName": flight.get("airlineName", None),
                        "flightNumber": flight.get("flightNumber", None),
                        "equipmentType": None,  # Not available in vendor data
                        "departure": {
                            "airportCode": flight['airport'][0].get("airportCode", None),
                            "airportName": flight['airport'][0].get("airportName", None),
                            "city": flight['airport'][0]['city'].get("cityName", None),
                            "country": flight['originAirportCountry'] if 'originAirportCountry' in flight else None,
                            "countryCode": None,  
                            "terminal": flight.get("originTerminal", None),
                            "departureDatetime": convert_to_iso(flight.get("departDatetime", None))
                        },
                        "arrival": {
                            "airportCode": flight['airport'][1].get("airportCode", None),
                            "airportName": flight['airport'][1].get("airportName", None),
                            "city": flight['airport'][1]['city'].get("cityName", None),
                            "country": flight['destinationAirportCountry'] if 'destinationAirportCountry' in flight else None,
                            "countryCode": None,  
                            "terminal": flight.get("destinationTerminal", None),
                            "arrivalDatetime": convert_to_iso(flight.get("arrivalDatetime", None))
                        },
                        "durationInMinutes": int(flight.get("flightTime", 0)),
                        "stop": option['stop'],
                        "cabinClass": flight.get("cabinClass", None),
                        "fareBasisCode": air_solution.get("fareBasis", None),
                        "seatsRemaining": int(flight.get("seatsLeft", 0)),
                        "isRefundable": None,  # Not available in the vendor data
                        "isChangeAllowed": None  # Not available in the vendor data
                    }
                    unified_structure['flightSegments'][flightSegment].append(unified_flight_segment)
                    if len(option['airSegmentInfos']) >1:
                        for flight in option['airSegmentInfos'][1:]:
                            durationInMinutes = connection_time_to_minutes(flight['connectionTime'])
                            arrivalDatetime = convert_to_iso(flight.get("arrivalDatetime", None))
                            unified_flight_segment = {
                                "airlineCode": flight.get("carrier", None),
                                "airlineName": flight.get("airlineName", None),
                                "flightNumber": flight.get("flightNumber", None),
                                "equipmentType": None,  # Not available in vendor data
                                "departure": {
                                    "airportCode": flight['airport'][0].get("airportCode", None),
                                    "airportName": flight['airport'][0].get("airportName", None),
                                    "city": flight['airport'][0]['city'].get("cityName", None),
                                    "country": flight['originAirportCountry'] if 'originAirportCountry' in flight else None,
                                    "countryCode": None,  
                                    "terminal": flight.get("originTerminal", None),
                                    "departureDatetime": convert_to_iso(flight.get("departDatetime", None))
                                },
                                "arrival": {
                                    "airportCode": flight['airport'][1].get("airportCode", None),
                                    "airportName": flight['airport'][1].get("airportName", None),
                                    "city": flight['airport'][1]['city'].get("cityName", None),
                                    "country": flight['destinationAirportCountry'] if 'destinationAirportCountry' in flight else None,
                                    "countryCode": None,  
                                    "terminal": flight.get("destinationTerminal", None),
                                    "arrivalDatetime": arrivalDatetime
                                },
                                "durationInMinutes": int(flight.get("flightTime", 0)),
                                "stop": option['stop'],
                                "cabinClass": flight.get("cabinClass", None),
                                "fareBasisCode": air_solution.get("fareBasis", None),
                                "seatsRemaining": int(flight.get("seatsLeft", 0)),
                                "isRefundable": None,  # Not available in the vendor data
                                "isChangeAllowed": None,  # Not available in the vendor data
                                "stopDetails":{
                                    "isLayover":True,
                                    "durationInMinutes":durationInMinutes,
                                    "stopPoint":{
                                        "airportCode": flight['airport'][0].get("airportCode", None),
                                        "arrivalTime": arrivalDatetime,
                                        "departureTime": add_minutes_to_datetime(arrivalDatetime,durationInMinutes)}
                                    }
                                }
                            unified_structure['flightSegments'][flightSegment].append(unified_flight_segment)
                            
                    unified_structure["publishFare"] = air_solution.get("totalPrice", 0)
                    calculated_fares = calculate_fares(air_solution.get("totalPrice", 0),air_solution.get("totalPrice", 0),fare_adjustment,tax_condition)
                    unified_structure["offerFare"] = calculated_fares["offered_fare"]
                    unified_structure["Discount"] = calculated_fares["discount"]
                    unified_structure["currency"] = "GBP"  
                    unified_structure["segmentID"] =  option["segmentID"]
                    result[flightSegment].append(unified_structure)
            
        elif journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "DOM":
            result = {"itineraries":[]}
            for journey_details in journey_details['journey_details']:
                date = "".join(journey_details["travel_date"].split('-')[:2])
                flightSegment = journey_details["source_city"]+"_"+journey_details["destination_city"]+"_"+date
                result["itineraries"].append(flightSegment)
                result[flightSegment] = []
            for air_solution in search_response['result']['airSolutions']:
                for journey in air_solution['journey']:
                    flightSegment = result["itineraries"][air_solution['journey'].index(journey)]
                    for option in journey['optionInfos']:
                        unified_structure = {"flightSegments":{flightSegment:[]}}
                        flight = option['airSegmentInfos'][0]
                        unified_flight_segment = {
                            "airlineCode": flight.get("carrier", None),
                            "airlineName": flight.get("airlineName", None),
                            "flightNumber": flight.get("flightNumber", None),
                            "equipmentType": None,  # Not available in vendor data
                            "departure": {
                                "airportCode": flight['airport'][0].get("airportCode", None),
                                "airportName": flight['airport'][0].get("airportName", None),
                                "city": flight['airport'][0]['city'].get("cityName", None),
                                "country": flight['originAirportCountry'] if 'originAirportCountry' in flight else None,
                                "countryCode": None,  
                                "terminal": flight.get("originTerminal", None),
                                "departureDatetime": convert_to_iso(flight.get("departDatetime", None))
                            },
                            "arrival": {
                                "airportCode": flight['airport'][1].get("airportCode", None),
                                "airportName": flight['airport'][1].get("airportName", None),
                                "city": flight['airport'][1]['city'].get("cityName", None),
                                "country": flight['destinationAirportCountry'] if 'destinationAirportCountry' in flight else None,
                                "countryCode": None,  
                                "terminal": flight.get("destinationTerminal", None),
                                "arrivalDatetime": convert_to_iso(flight.get("arrivalDatetime", None))
                            },
                            "durationInMinutes": int(flight.get("flightTime", 0)),
                            "stop": option['stop'],
                            "cabinClass": flight.get("cabinClass", None),
                            "fareBasisCode": air_solution.get("fareBasis", None),
                            "seatsRemaining": int(flight.get("seatsLeft", 0)),
                            "isRefundable": None,  # Not available in the vendor data
                            "isChangeAllowed": None  # Not available in the vendor data
                        }
                        unified_structure['flightSegments'][flightSegment].append(unified_flight_segment)
                        if len(option['airSegmentInfos']) >1:
                            for flight in option['airSegmentInfos'][1:]:
                                durationInMinutes = connection_time_to_minutes(flight['connectionTime'])
                                arrivalDatetime = convert_to_iso(flight.get("arrivalDatetime", None))
                                unified_flight_segment = {
                                    "airlineCode": flight.get("carrier", None),
                                    "airlineName": flight.get("airlineName", None),
                                    "flightNumber": flight.get("flightNumber", None),
                                    "equipmentType": None,  # Not available in vendor data
                                    "departure": {
                                        "airportCode": flight['airport'][0].get("airportCode", None),
                                        "airportName": flight['airport'][0].get("airportName", None),
                                        "city": flight['airport'][0]['city'].get("cityName", None),
                                        "country": flight['originAirportCountry'] if 'originAirportCountry' in flight else None,
                                        "countryCode": None,  
                                        "terminal": flight.get("originTerminal", None),
                                        "departureDatetime": convert_to_iso(flight.get("departDatetime", None))
                                    },
                                    "arrival": {
                                        "airportCode": flight['airport'][1].get("airportCode", None),
                                        "airportName": flight['airport'][1].get("airportName", None),
                                        "city": flight['airport'][1]['city'].get("cityName", None),
                                        "country": flight['destinationAirportCountry'] if 'destinationAirportCountry' in flight else None,
                                        "countryCode": None,  
                                        "terminal": flight.get("destinationTerminal", None),
                                        "arrivalDatetime": arrivalDatetime
                                    },
                                    "durationInMinutes": int(flight.get("flightTime", 0)),
                                    "stop": option['stop'],
                                    "cabinClass": flight.get("cabinClass", None),
                                    "fareBasisCode": air_solution.get("fareBasis", None),
                                    "seatsRemaining": int(flight.get("seatsLeft", 0)),
                                    "isRefundable": None,  # Not available in the vendor data
                                    "isChangeAllowed": None,  # Not available in the vendor data
                                    "stopDetails":{
                                        "isLayover":True,
                                        "durationInMinutes":durationInMinutes,
                                        "stopPoint":{
                                            "airportCode": flight['airport'][0].get("airportCode", None),
                                            "arrivalTime": arrivalDatetime,
                                            "departureTime": add_minutes_to_datetime(arrivalDatetime,durationInMinutes)}
                                        }
                                    }
                                unified_structure['flightSegments'][flightSegment].append(unified_flight_segment)
                                
                        unified_structure["publishFare"] = air_solution.get("totalPrice", 0)
                        calculated_fares = calculate_fares(air_solution.get("totalPrice", 0),air_solution.get("totalPrice", 0),fare_adjustment,tax_condition)
                        unified_structure["offerFare"] = calculated_fares["offered_fare"]
                        unified_structure["Discount"] = calculated_fares["discount"] 
                        unified_structure["currency"] = "GBP"  
                        unified_structure["segmentID"] =  option["segmentID"]

                        result[flightSegment].append(unified_structure)
                    
            
        elif journey_details["journey_type"] =="Round Trip" and journey_details["flight_type"] == "INT":
            fs = []
            for journey_details in journey_details['journey_details']:
                date = "".join(journey_details["travel_date"].split('-')[:2])
                flightSegment = journey_details["source_city"]+"_"+journey_details["destination_city"]+"_"+date
                fs.append(flightSegment)
            result = {"itineraries":["_R_".join(fs)],"_R_".join(fs):[]}





            
        return result
    
    
    def find_segment_by_id(self,data, segment_id,journey_details):
        """
        This function searches for the segment with the provided segment_id.
        """
        journey_type = journey_details.get("journey_type")
        if journey_type == "One Way":
            # Navigate to airSolutions in the JSON data
            air_solutions = data.get('data', {}).get('result', {}).get('airSolutions', [])
            token = data.get('data', {}).get('result', {}).get('token',"")
            # Iterate through the air solutions to find the matching segmentID
            for solution in air_solutions:
                for journey in solution.get('journey', []):
                    for option_info in journey.get('optionInfos', []):
                        if option_info['segmentID'] == segment_id:
                            return [solution, journey, option_info, token]
        return "Bla"



    def get_fare_details(self,search_details,raw_data,fare_details,raw_doc,segment_id):

        fare_adjustment,tax_condition= set_fare_details(fare_details)
        air_solution, journey, option_info,token = raw_data
        key = air_solution.get('key',"")
        supp = air_solution.get('supp')
        OptionKeyList = [option_info.get('optionKey')]
        pricing_availability_response = pricing_availability_search(self.base_url,self.credentials,trip_type="OW",key=key,token=token,supp=supp,OptionKeyList=OptionKeyList)
        air_solutions = pricing_availability_response.get("result").get("airSolutions")
        fareDetails = []
        for air_solution in air_solutions:
            result = {}
            result['fare_id'] = create_uuid("FARE")
            result['segment_id'] = segment_id
            result["publishedFare"] = air_solution.get("totalPrice", 0)
            calculated_fares = calculate_fares(air_solution.get("totalPrice", 0),air_solution.get("totalPrice", 0),fare_adjustment,tax_condition)
            result["offeredFare"] = calculated_fares["offered_fare"]

            result["vendor_id"] = self.vendor_id
            result["transaction_id"] = air_solution["key"]
            result["fareType"] = air_solution.get("brand").get("brandName")
            result["uiName"] = air_solution.get("brand").get("brandName")
            result["fare_rule"] = air_solution.get("brand").get("brandDetails", "No Details Available")
            result["currency"] = "GBP"
            result["colour"] = "Peach"

            # Mapping the pricingInfos as fareBreakdown
            pricing_infos = air_solution.get("pricingInfos", [])
            fare_breakdown = []
            for pricing_info in pricing_infos:
                breakdown = {
                    "passengerType": pricing_info.get("paxTypeName", "").lower() + 's' if pricing_info["paxType"] in ["ADT", "CHD", "INF"] else "Unknown",
                    "baseFare": pricing_info.get("basePrice"),
                    "tax": pricing_info.get("tax")
                }
                fare_breakdown.append(breakdown)
            
            result["fareBreakdown"] = fare_breakdown
            
            # Handling isRefundable logic
            result["isRefundable"] = [
                opService for opService in air_solution['optionalServices']
                if opService['description'] in ["Refundable Ticket", "Refunds"]
            ][0]['chargeable'] != 'Not offered'
            
            # Adding baggage information


            result["baggage"] = {"checkInBag": None, "cabinBag": None}
            try:
                checkInBag = extracted_segment['Segments'][0][0]['Baggage']
            except:
                checkInBag = "-"
            try:
                cabinBag = extracted_segment['Segments'][0][0]['CabinBaggage']
            except:
                cabinBag = "-"
            result["baggage"] = {"checkInBag": checkInBag, "cabinBag": cabinBag}


            if "checkedBaggage" in air_solution.get("brand"):
                result["baggage"]["checkInBag"] =  air_solution.get("brand").get("checkedBaggage")
            if "carryBaggage" in air_solution.get("brand"):
                result["baggage"]["cabinBag"] =  air_solution.get("brand").get("carryBaggage")
            if result["baggage"]["checkInBag"] == None or result["baggage"]["cabinBag"] == None:
                checkin_bag,cabin_bag = extract_bag_weights(air_solution.get("brand").get("brandDetails",""))
                if result["baggage"]["checkInBag"] == None:
                    result["baggage"]["checkInBag"] = checkin_bag
                if result["baggage"]["carryBaggage"] == None:
                    result["baggage"]["cabinBag"] = cabin_bag
            fareDetails.append(result)
        return fareDetails
def extract_bag_weights(description):
    """
    This function extracts the weights for checked and carry-on bags from the provided description
    and formats them with a space and 'Kg'. It handles variations where carry-on and checked bag
    might appear in different formats.
    """
    checked_bag_weight = "Chargeable"  # Default to "Chargeable" if checked bag is not free
    carryon_bag_weight = None
    # Updated regex to handle both "10kg carry on bag" and "carry-on bag 10kg"
    carryon_bag_pattern = re.compile(r"(carry[-\s]*on bag|carry on bag)\s*(\d+)\s*kg|(\d+)\s*kg\s*(carry[-\s]*on bag|carry on bag)", re.IGNORECASE)
    checked_bag_pattern = re.compile(r"(checked bag|chargeable checked bag)\s*(\d+)?\s*kg?", re.IGNORECASE)
    # Search for carry-on bag weight (in both formats)
    carryon_bag_match = carryon_bag_pattern.search(description)
    if carryon_bag_match:
        if carryon_bag_match.group(2):  # Handle "carry-on bag 10kg"
            carryon_bag_weight = carryon_bag_match.group(2) + " Kg"
        elif carryon_bag_match.group(3):  # Handle "10kg carry-on bag"
            carryon_bag_weight = carryon_bag_match.group(3) + " Kg"
    # Search for checked bag weight, handling chargeable checked bag cases
    checked_bag_match = checked_bag_pattern.search(description)
    if checked_bag_match:
        if checked_bag_match.group(2):  # If there's a specific weight mentioned
            checked_bag_weight = checked_bag_match.group(2) + " Kg"
    return checked_bag_weight, carryon_bag_weight
def convert_to_iso(datetime_str):
    try:
        return datetime.strptime(datetime_str, '%d/%m/%Y %H:%M').isoformat()
    except ValueError:
        return None

def connection_time_to_minutes(connection_time_str):
    # Initialize total minutes to 0
    total_minutes = 0
    
    # Find hours and minutes using regular expressions
    hours_match = re.search(r'(\d+)h', connection_time_str)
    minutes_match = re.search(r'(\d+)m', connection_time_str)
    
    # Convert hours to minutes and add to total
    if hours_match:
        hours = int(hours_match.group(1))
        total_minutes += hours * 60
    
    # Add the minutes to total
    if minutes_match:
        minutes = int(minutes_match.group(1))
        total_minutes += minutes
    
    return total_minutes

def add_minutes_to_datetime(date_str, minutes_to_add):
    # Convert the input string to a datetime object
    date_format = "%Y-%m-%dT%H:%M:%S"
    date_obj = datetime.strptime(date_str, date_format)
    
    # Add the specified number of minutes
    updated_date = date_obj + timedelta(minutes=minutes_to_add)
    
    # Return the updated datetime in the same format
    return updated_date.strftime(date_format)

def calculate_fares(published_fare,offered_fare,fare_adjustment,tax_condition):
    offered_fare = published_fare + float(fare_adjustment["markup"]) + float(fare_adjustment["distributor_markup"]) - (published_fare-offered_fare)*float(fare_adjustment["parting_percentage"])/100 - float(fare_adjustment["cashback"]) - float(fare_adjustment["distributor_cashback"])
    discount = (published_fare-offered_fare)*(1-float(tax_condition["tax"])/100)
    return {"offered_fare":offered_fare,"discount":discount}

pax_type_mapping = {
        "ADT": "Adult",
        "CHD": "Child",
        "INF": "Infant"
    }
