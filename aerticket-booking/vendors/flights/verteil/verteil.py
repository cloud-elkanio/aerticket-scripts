from vendors.flights.abstract.abstract_flight_manager import AbstractFlightManager
from vendors.flights.verteil.verteil_api import (authentication,flight_search
                                      )
from datetime import datetime,timedelta
from vendors.flights.utils import create_uuid,set_fare_details,create_segment_keys
from vendors.flights.finance_manager import FinanceManager
from users.models import LookupCountry,LookupAirline,LookupAirports
from common.models import FlightBookingFareDetails,FlightBookingSSRDetails,FlightBookingItineraryDetails,\
    LookupEasyLinkSupplier,FlightBookingUnifiedDetails
import concurrent.futures
import re,json
import time
import traceback as tb
from typing import Optional
from timezonefinder import TimezoneFinder
import pytz,os

class Manager(AbstractFlightManager):
    def __init__(self,data,uuid,mongo_client,is_auth):
        self.vendor_id = "VEN-"+str(uuid)
        self.credentials = data
        self.base_url = data["base_url"]
        # self.auth_url = data["auth_url"]
        # self.ticketing_url = data["ticketing_url"]
        self.mongo_client = mongo_client
        if is_auth:
            self.token,self.expires_in = authentication(self.base_url,self.credentials)
            print(25, self.token,self.expires_in)
        else:
            self.token = data["token"]
        self.credentials["token"] =  self.token
        
    def name (self):
        return "Verteil"
    def get_vendor_id(self):
        return self.vendor_id

    def get_cabin_class(self,cabin_class):
        cabin_map = {"Economy":"Y","PremiumEconomy":"W","Business Class":"C","First Class":"F"}
        return cabin_map.get(cabin_class,1)

    def get_fare_type(self,fare_type):
        fare_type_map = {"Regular":"PUBL","Student":"STU","Senior Citizen":"HR"}
        return fare_type_map.get(fare_type,1)  
        
    def get_journey_type(self,journey_type):
        journey_type_map = {"One Way":1,"Round Trip":2,"Multi Stop":1}
        return journey_type_map.get(journey_type,1)
    def add_uuid_to_segments(self,response):
        if response.get('OffersGroup',{}).get('AirlineOffers')[0].get('AirlineOffer'):
            offers = response['OffersGroup']['AirlineOffers'][0]['AirlineOffer']
            for offer in offers:
                seg = str(self.vendor_id)+"_$_"+create_uuid("SEG")
                offer["segmentID"] = seg
            response['OffersGroup']['AirlineOffers'][0]['AirlineOffer'] = offers
        return response 
    
    def create_segments(self,segment_details):
        output = []
        for entry in segment_details:
            source = entry["source_city"]
            destination = entry["destination_city"]
            travel_date = entry["travel_date"]
            dt = datetime.strptime(travel_date, "%d-%m-%Y")
            formatted_date = dt.strftime("%Y-%m-%d")
            transformed_entry = {
                "Departure": {
                    "AirportCode": {
                        "value": source
                    },
                    "Date": formatted_date
                },
                "Arrival": {
                    "AirportCode": {
                        "value": destination
                    }
                },
                "OriginDestinationKey": f"{source}-{destination}"
            }
            output.append(transformed_entry)
        return output
    def create_travellers(self,traveler_counts):
        output = []
        pax_map = {
            "adults": {"PTC": "ADT ", "age": 25},
            "children": {"PTC": "CHD ", "age": 12},
            "infants": {"PTC": "INF ", "age": 1}  
        }
        base_year = datetime.now().year
        for pax_type, count in traveler_counts.items():
            if count > 0:
                details = pax_map[pax_type]
                birth_year = base_year - details["age"]
                birthdate = f"{birth_year}-01-01"
                travelers = [
                    {
                        "PTC": {"value": details["PTC"]},
                        "Age": {
                            "Value": {"value": details["age"]},
                            "BirthDate": {"value": birthdate}
                        }
                    }
                    for _ in range(count)
                ]
                output.append({"AnonymousTraveler": travelers})
        return output

    def get_vendor_journey_types(self,kwargs):
        if kwargs.get("flight_type","").upper() == "DOM":
            print("116")
            return False
        else:
            print("119")
            return True
        
    def search_flights(self,journey_details):
        journey_type = journey_details.get("journey_type")
        flight_type = journey_details.get("flight_type")
        pax = journey_details.get("passenger_details")
        cabin_class = journey_details.get("cabin_class")
        segment_details = journey_details.get("journey_details")
        fare_type = self.get_fare_type(journey_details.get("fare_type"))
        session_id = journey_details.get("session_id")
        cabin_class = self.get_cabin_class(cabin_class)
        trip_type = self.get_journey_type(journey_type)
        segment_keys = create_segment_keys(journey_details)
        segments = self.create_segments(segment_details)
        travellers = self.create_travellers(pax)
        def process_segment(seg, index):
            """Function to process each segment in a thread."""
            flight_search_response = flight_search(baseurl=self.base_url,credentials=self.credentials,
                fare_type=fare_type,pax=travellers,segments=[seg],session_id = session_id)
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
                        response =  self.add_uuid_to_segments(response)
                        final[segment_keys[index]] = response

                return final
            final_result = run_in_threads(segments, segment_keys)
            return {"data":final_result,"status":"success"}
        else:
            final ={}
            flight_search_response = flight_search(baseurl=self.base_url,credentials=self.credentials,
                fare_type=fare_type,pax=travellers,segments=segments,session_id = session_id)
            flight_search_response =  self.add_uuid_to_segments(flight_search_response)

            final[segment_keys[0]] = flight_search_response
            return {"data":final,"status":"success"}
    def converter(self, search_response, journey_details,fare_details):
        print(163,journey_details)
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
        for flightSegment in segment_keys:
            DataList = search_response[flightSegment].get('DataLists')

            AnonymousTravelerList = DataList.get('AnonymousTravelerList',{}).get('AnonymousTraveler',[])
            AnonymousTravelerData = {x['ObjectKey']:x for x in AnonymousTravelerList}

            CarryOnAllowanceList = DataList.get('CarryOnAllowanceList',{}).get('CarryOnAllowance',[])
            CarryOnAllowanceData = {x['ListKey']:x for x in CarryOnAllowanceList}

            CheckedBagAllowanceList = DataList.get('CheckedBagAllowanceList',{}).get('CheckedBagAllowance',[])
            CheckedBagAllowanceData = {x['ListKey']:x for x in CheckedBagAllowanceList}

            DisclosureList = DataList.get('DisclosureList',{}).get('Disclosures',[])
            DisclosureData = {x['ListKey']:x for x in DisclosureList}

            FareList = DataList.get('FareList',{}).get('FareGroup',[])
            FareData = {x['ListKey']:x for x in FareList}

            FlightList = DataList.get('FlightList',{}).get('Flight',[])
            FlightData = {x['FlightKey']:x for x in FlightList}

            FlightSegmentList = DataList.get('FlightSegmentList',{}).get('FlightSegment',[])
            FlightSegmentData = {x['SegmentKey']:x for x in FlightSegmentList}

            MediaList = DataList.get('MediaList',{}).get('Media',[])
            MediaData = {x['ListKey']:x for x in MediaList}

            OriginDestinationList = DataList.get('OriginDestinationList',{}).get('OriginDestination',[])
            OriginDestinationData = {x['OriginDestinationKey']:x for x in OriginDestinationList}

            PenaltyList = DataList.get('PenaltyList',{}).get('Penalty',[])
            PenaltyData = {x['ObjectKey']:x for x in PenaltyList}

            PriceClassList = DataList.get('PriceClassList',{}).get('PriceClass',[])
            PriceClassData = {x['ObjectKey']:x for x in PriceClassList}
            Offers = search_response[flightSegment].get('OffersGroup',{}).get('AirlineOffers')[0].get('AirlineOffer')
            Output = [] 
            def convert_duration(duration_str):
                duration_str = duration_str.replace("PT", "")
                match = re.match(r'(?:(\d+)H)?(?:(\d+)M)?', duration_str)
                hours = int(match.group(1)) if match.group(1) else 0
                minutes = int(match.group(2)) if match.group(2) else 0
                total_minutes = hours * 60 + minutes
                return total_minutes
            def parse_baggage(entry):
                if "WeightAllowance" not in entry or not entry["WeightAllowance"]:
                    if "PieceAllowance" in entry and entry["PieceAllowance"]:
                        total_qty = entry["PieceAllowance"][0].get("TotalQuantity", 0)
                        value = f"{total_qty}N"
                    else:
                        value = "0N"  # Default if no piece allowance info is provided
                else:
                    # Handle the case when weight is provided (e.g., use the weight value)
                    value = entry["WeightAllowance"]["MaximumWeight"][0].get("Value", 0)
                    if value:
                        value = str(value)+" Kg" 
                    else:
                        value= str(value)
                return value
            for offer in Offers:
                flightSegments = {}
                totalprice = offer.get('TotalPrice').get('SimpleCurrencyPrice').get('value')
                currency = offer.get('TotalPrice').get('SimpleCurrencyPrice').get('Code')
                priced_offer = offer.get('PricedOffer')
                OfferPrices = priced_offer.get('OfferPrice')
                for offer_price in OfferPrices:
                    pax_key = offer_price.get("RequestedDate").get("Associations")[0].get("AssociatedTraveler").get("TravelerReferences")[0]
                    AnonymousTraveler = AnonymousTravelerData[pax_key]
                    if AnonymousTraveler.get("PTC").get("value") == "ADT":
                        current_offer_price = offer_price
                        break
                farecomponent= current_offer_price.get("FareDetail").get("FareComponent")


                unique = {}
                for item in farecomponent:
                    # Use the penalty refs as the deduplication key (convert to tuple so it's hashable)
                    if item.get('FareRules'):
                        key = tuple(item.get('FareRules')['Penalty']['refs'])
                        if key not in unique:
                            unique[key] = item
                
                farecomponent = list(unique.values())
                for comp in farecomponent:
                    comp["Penalty"] = {}
                    for ref in comp.get("FareRules").get("Penalty").get("refs"):    
                        comp["Penalty"][ref] = PenaltyData[ref]
                
                priced_associations = priced_offer.get('Associations')
                checkin_bags = []
                carry_in_bags = []
                for idx,association in enumerate(priced_associations):

                    CheckedBagAllowance_key = current_offer_price.get("RequestedDate").get("Associations")[idx].get("ApplicableFlight").get("FlightSegmentReference")[0].get('BagDetailAssociation').get('CheckedBagReferences',[])
                    CarryOnAllowance_key = current_offer_price.get("RequestedDate").get("Associations")[idx].get("ApplicableFlight").get("FlightSegmentReference")[0].get('BagDetailAssociation').get('CarryOnReferences',[])
                    if CheckedBagAllowance_key:
                        CheckedBagAllowance = CheckedBagAllowanceData[CheckedBagAllowance_key[0]]
                        checked_in_bag = parse_baggage(CheckedBagAllowance)
                        checkin_bags.append(checked_in_bag)
                    if CarryOnAllowance_key:
                        CarryOnAllowance = CarryOnAllowanceData[CarryOnAllowance_key[0]]
                        carry_in_bag = parse_baggage(CarryOnAllowance)
                        carry_in_bags.append(carry_in_bag)

                    journey_segments=[]
                    if search_query.get("journey_type") == "Round Trip" and search_query.get("flight_type") =="INT":
                        flight_segment_key = segment_keys[0].split("_R_")[idx]
                    else:
                        flight_segment_key = segment_keys[idx] 
                    flightSegments[flight_segment_key] = []
                    flight_segment_refernce_list = association.get('ApplicableFlight',{}).get('FlightSegmentReference',[])
                    for idy,flight_segment_refernce in enumerate(flight_segment_refernce_list):
                        
                        penalty_segment= farecomponent[idy].get("Penalty") if len(farecomponent) >=idy+1  else  farecomponent[0].get("Penalty")
                        cancelPenalty = [penalty_segment[ref] for ref in penalty_segment.keys() if penalty_segment[ref]['Details']['Detail'][0]['Type'] == 'Cancel']
                        changePenalty = [penalty_segment[ref] for ref in penalty_segment.keys() if penalty_segment[ref]['Details']['Detail'][0]['Type'] == 'Change']

                        flight_segment_refernce_key = flight_segment_refernce.get('ref')
                        flight_segment = FlightSegmentData.get(flight_segment_refernce_key)
                        airlineCode = flight_segment.get("MarketingCarrier", {}).get("AirlineID", {}).get("value")
                        airlineName = flight_segment.get("MarketingCarrier", {}).get("Name")
                        flightNumber = flight_segment.get("MarketingCarrier", {}).get("FlightNumber", {}).get("value")
                        
                        # Equipment field
                        equipmentType = flight_segment.get("Equipment", {}).get("AircraftCode", {}).get("value")
                        
                        # Departure details
                        dep = flight_segment.get("Departure", {})
                        departure_airportCode = dep.get("AirportCode", {}).get("value")

                        departure_terminal = dep.get("Terminal", {}).get("Name","")
                        dep_date = dep.get("Date")
                        dep_time = dep.get("Time")
                        dep_date = dep_date.split('.')[0]
                        departure_datetime = f"{dep_date[:10]}T{dep_time}:00"

                        
                        # Arrival details
                        arr = flight_segment.get("Arrival", {})
                        arrival_airportCode = arr.get("AirportCode", {}).get("value")

                        arrival_terminal = arr.get("Terminal", {}).get("Name", "NON")
                        arr_date = arr.get("Date")
                        arr_time = arr.get("Time")
                        arr_date = arr_date.split('.')[0]
                        arrival_datetime = f"{arr_date[:10]}T{arr_time}:00"
                        dep_airport = get_airport(departure_airportCode,airports)

                        arr_airport = get_airport(arrival_airportCode,airports)
                        
                        # Flight duration
                        duration_str = flight_segment.get("FlightDetail", {}).get("FlightDuration", {}).get("Value", "NON")
                        if duration_str == "NON":
                            durationInMinutes = get_gmt_converted_duration(airports,dep_airport,arr_airport,departure_datetime,arrival_datetime)
                        else:
                            durationInMinutes =convert_duration(duration_str)
                        # Fields not provided in vendor segment: cabinClass, cabin, fareBasisCode, seatsRemaining.
                        print("duration_str",duration_str,"durationInMinutes",durationInMinutes)
                        cabinClass = flight_segment_refernce.get("ClassOfService").get("MarketingName",{}).get("value")
                        cabin =  flight_segment_refernce.get("ClassOfService").get("Code").get("value")
                        seatsRemaining = flight_segment.get("SeatsRemaining", "NON")
                        
                        
                        # Booleans
                        isRefundable = [x.get("RefundableInd") for x in cancelPenalty]
                        isChangeAllowed = [x.get("ChangeAllowedInd") for x in changePenalty]
                        
                        unified = {
                            "airlineCode": airlineCode,
                            "airlineName": airlineName,
                            "flightNumber": flightNumber,
                            "equipmentType": equipmentType,
                            'departure': {
                                'airportCode': departure_airportCode,
                                'airportName': dep_airport.name if dep_airport else "-",
                                'city': dep_airport.city if dep_airport.city else "-" if dep_airport else "-",
                                'country': dep_airport.country.country_name if dep_airport and dep_airport.country and dep_airport.country.country_name else "-",
                                'countryCode':dep_airport.country.country_code if dep_airport and dep_airport.country and dep_airport.country.country_code else "-",
                                'terminal': departure_terminal,
                                'departureDatetime': departure_datetime
                            },
                            'arrival': {
                                'airportCode': arrival_airportCode,
                                'airportName': arr_airport.name if arr_airport else "-",
                                'city': arr_airport.city if arr_airport.city else "-" if arr_airport else "-",
                                'country': arr_airport.country.country_name if arr_airport and arr_airport.country and arr_airport.country.country_name else "-",
                                'countryCode':arr_airport.country.country_code if arr_airport and arr_airport.country and arr_airport.country.country_code else "-",
                                'terminal': arrival_terminal,
                                'arrivalDatetime': arrival_datetime
                            },
                            "durationInMinutes": durationInMinutes,
                            "stop": 0,
                            "cabinClass": cabinClass,
                            "cabin": cabin,
                            "seatsRemaining": seatsRemaining,
                            "isRefundable": isRefundable,
                            "isChangeAllowed": isChangeAllowed
                        }
                        if idy != 0:
                            unified['stop']=idy
                            layover_duration =  datetime.fromisoformat(unified['departure']['departureDatetime']) - datetime.fromisoformat(journey_segments[-1]['arrival']['arrivalDatetime'])
                            layover_durationInMinutes = int(layover_duration.total_seconds() / 60)
                            stop_point = {
                                'isLayover': True,
                                'durationInMinutes': layover_durationInMinutes,
                                'stopPoint': {
                                    'airportCode': [unified['departure']['airportCode']]    ,
                                    'arrivalTime': journey_segments[-1]['arrival']['arrivalDatetime'],
                                    'departureTime': unified['departure']['departureDatetime']
                                }
                            }
                            unified['stopDetails'] = stop_point
                        journey_segments.append(unified)
                    flightSegments[flight_segment_key] = journey_segments
                journey = {"flightSegments":flightSegments}
                
                calculated_fares = calculate_fares(   supplier_published_fare= totalprice,fare_adjustment = fare_adjustment,
                                    tax_condition = tax_condition,
                                        pax_data = journey_details["passenger_details"])

                
                journey["offerFare"] = calculated_fares["offered_fare"]
                journey["Discount"] = calculated_fares["discount"]
                journey["publishFare"] = calculated_fares["publish_fare"]
                journey["currency"] = currency
                journey["IsLCC"] = False
                journey['segmentID'] = offer['segmentID'] 
                journey['default_baggage'] = {flightSegment: {"checkInBag": ','.join(checkin_bags),"cabinBag": carry_in_bags}}
                if idy<2:# Removing all with more than 2 Stops
                    Output.append(journey)
            return_data[flightSegment] = Output
        return {"data":return_data,"status":"success"}

def get_airline(airline_code,airlines) -> Optional[LookupAirline]:
    return airlines.get(airline_code) 
def get_airport(airport_code,airports) -> Optional[LookupAirports]:
    return airports.get(airport_code)
def calculate_fares(**kwargs):
    total_pax_count = sum(list(map(int,list(kwargs["pax_data"].values()))))
    supplier_published_fare = kwargs["supplier_published_fare"]
    supplier_offered_fare = 0
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
        return durationInMinutes

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