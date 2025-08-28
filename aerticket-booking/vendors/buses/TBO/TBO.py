from vendors.buses import utils

from vendors.buses.TBO.TBO_api import (authentication,get_city_list,bus_search,
                                       seatmap,pickup_drop,block,book,
                                       booking_detail,cancellation_charges,cancel_ticket)
from datetime import datetime
from vendors.buses.models import BusCity
from common.models import LookupCountry
from collections import defaultdict
import json

SEAT_TYPES = {"1":"Seat","2":"Sleeper","3":"Semi-Sleeper", "4":"Upper Berth","5":"Lower Berth"}
GENDER_TYPES = {"male":1,"female":2}

class Manager():
    def __init__(self, **kwargs):
        self.credentials = kwargs['credentials']
        self.mongo_client = kwargs['mongo_client']
        self.vendor_uuid = kwargs['uuid']
        self.vendor_id = "VEN-"+str(kwargs['uuid'])
        self.base_url =  self.credentials["base_url"]
        self.auth_url =  self.credentials["auth_url"]
        self.static_data_url =  self.credentials["static_data_url"]
        if kwargs["is_auth"]:
            self.token = authentication(self.auth_url,self.credentials)
        else:
            self.token = self.credentials["token"]
        self.credentials["token"] =  self.token

    def name(self):
        return "TBO"
    
    def get_vendor_id(self):
        return self.vendor_id

    def create_city_list(self):

        try:
            response = get_city_list(credentials=self.credentials,
                 base_url =self.static_data_url
            )
            BusCities =response.get("BusCities",[])
            X = LookupCountry.objects.filter(country_code = 'IN').first()
            converted = [{"city_id":x.get('CityId'),"city_name":x.get('CityName'),"country":X} for x in BusCities]
            return converted
        except:
            return []

    def search_bus(self,data):
        date_str = data['date']
        date_obj = datetime.strptime(date_str, "%d-%m-%Y")
        formatted_date = date_obj.strftime("%Y/%m/%d")
        data['date'] = formatted_date
        try:
            response = bus_search(credentials=self.credentials,
                 base_url =self.base_url,data=data,session_id=data['session_id']
            )
            response = self.add_uuid_to_segments(response)
            return {"status":"success","data":response}
        except:
            return {"status":"failure","data":{}}

    def converter(self,datalist,search_query,fareDetails):
        results = []
        City_objs = BusCity.objects.filter(supplier=self.vendor_uuid)
        existing_map = {str(obj.city_id): obj for obj in City_objs}
        buslist = datalist.get('BusSearchResult').get("BusResults")
        for data in buslist :
            unified = {}
    
            # Extract departure time and derive travel date.
            departure_time = data.get("DepartureTime", None)
            unified["travelDate"] = departure_time[:10] if departure_time else None
            unified["departureTime"] = departure_time
            unified["arrivalTime"] = data.get("ArrivalTime", None)
            unified["availableSeats"] = data.get("AvailableSeats", None)
            unified["busType"] = data.get("BusType", None)
            unified["operator"] = data.get("TravelName", None)
            unified["provider"] = data.get("ServiceName", None)
            
            # Amenities: use vendor data if available, otherwise set to None.
            unified["amenities"] = {
                "ac": data.get("AC", None),  # 'AC' is not present in vendor_data so likely will be None.
                "mTicketEnabled": data.get("MTicketEnabled", None)
            }
            
            unified["partialCancellationAllowed"] = data.get("PartialCancellationAllowed", None)
            
            supplier_published_price = data.get('BusPrice').get('PublishedPrice')
            supplier_offer_price = data.get('BusPrice').get('OfferedPrice')
            modified_price= utils.fare_calculation(fareDetails,supplier_published_price,supplier_offer_price)
            unified["price"] = {
                "amount": {
                    "pub_fare": modified_price.get('published_fare'),
                    "off_fare": modified_price.get('offered_fare'),
                    "discount": modified_price.get('discount'),
                    "currency": search_query.get("currency","inr"),
                    "base_fare": supplier_published_price,
                    "tax": 0
                },
                "supplier_published_fare": supplier_published_price,
                "supplier_offered_fare": supplier_offer_price
            }
            # Boarding points conversion.
            boarding_points = []
            for bp in data.get("BoardingPointsDetails", []):
                bp_dict = {
                    "name": bp.get("CityPointName", None),
                    "time": bp.get("CityPointTime", None),
                    "address": bp.get("CityPointLocation", None),
                    "contact": bp.get("CityPointContact", None)  # Vendor data does not include contact; will default to None.
                }
                boarding_points.append(bp_dict)
            unified["boardingPoints"] = boarding_points if boarding_points else None
            
            # Dropping points conversion.
            dropping_points = []
            for dp in data.get("DroppingPointsDetails", []):
                dp_dict = {
                    "name": dp.get("CityPointName", None),
                    "time": dp.get("CityPointTime", None),
                    "address": dp.get("CityPointLocation", None),
                    "contact": dp.get("CityPointContact", None),  # Defaults to None if not present.
                }
                dropping_points.append(dp_dict)
            unified["droppingPoints"] = dropping_points if dropping_points else None
            cancellationPolicies = data.get("CancellationPolicies",[])
            # Cancellation policies: overriding with the provided cancellation policy format.
            if cancellationPolicies:
                unified["cancellationPolicies"] = [
                {
                    "value": vendor_policy.get("CancellationCharge", None),
                    "type": "percentage" if vendor_policy.get("CancellationChargeType") == 2 else "fixed",
                    "currency": search_query.get("currency","inr"),
                    "from": vendor_policy.get("FromDate", None),
                    "to": vendor_policy.get("ToDate", None)
                } for vendor_policy in cancellationPolicies]
            else:
                unified["cancellationPolicies"] = []
            unified["idProofRequired"] = data.get("IdProofRequired", None)
            unified["liveTrackingAvailable"] = data.get("LiveTrackingAvailable", None)
            
            unified["additionalInfo"] = {
                "maxSeatsPerTicket": data.get("MaxSeatsPerTicket", None),
                "routeId": data.get("RouteId", None),
                "serviceName": data.get("ServiceName", None)
            }
            unified['segmentID'] = data['segmentID']
            results.append(unified)
    

        return {"data":results,"status":"success"}
    def add_uuid_to_segments(self,vendor_data):
        if vendor_data:
            segments = vendor_data["BusSearchResult"]["BusResults"]
            for segment in segments:
                seg = str(self.vendor_id)+"_$_"+utils.create_uuid("SEG")
                segment["segmentID"] = seg
            return vendor_data
        else:
            return {}
    
    def get_seatmap(self,session_id,segment_id,raw_data,current_segment,fare_detatils):
        traceId = raw_data.get('data',{}).get("BusSearchResult",{}).get("TraceId")
        raw_segment = self.get_raw_segment(segment_id,raw_data)
        print("raw_segment",raw_segment)
        ResultIndex = raw_segment.get('ResultIndex')
        data = {"TraceId":traceId,"ResultIndex":ResultIndex}
        print("data",data)
        try:
            response = seatmap(credentials=self.credentials,
                 base_url =self.base_url,data=data,session_id=session_id
            )
            response = self.add_uuid_to_seatmap(response)
            converted = self.unify_seatmap(response.get("GetBusSeatLayOutResult").get("SeatLayoutDetails"),fare_detatils)
            return {"status":"success","data":converted,"raw":response}
        except:
            return {"status":"failure","data":{}}
    
    def pickup_drop_fetch(self,session_id,segment_id,raw_data,current_segment):
        traceId = raw_data.get('data',{}).get("BusSearchResult",{}).get("TraceId")
        raw_segment = self.get_raw_segment(segment_id,raw_data)
        ResultIndex = raw_segment.get('ResultIndex')
        data = {"TraceId":traceId,"ResultIndex":ResultIndex}
        try:
            response = pickup_drop(credentials=self.credentials,
                 base_url =self.base_url,data=data,session_id=session_id
            )
            response = self.add_uuid_to_pickup_drop(response)
            converted = self.unify_pickup_drop(response)
            return {"status":"success","data":converted,"raw":response}
        except:
            return {"status":"failure","data":{},"raw":{}}
    
    def purchase(self,session_id,booking,pax_details):
        traceId = booking.misc.get("TraceId")
        ResultIndex = booking.misc.get('ResultIndex')
        boarding = booking.search_detail.pickup_id
        dropoff = booking.search_detail.dropoff_id
        pax_list = []
        contact  = json.loads(booking.contact)
        booking.status = "Ticketing-Initiated"
        booking.save(update_fields=["status"]) 
        for idx,pax in enumerate(pax_details):
            dob = datetime.strptime(pax.dob, "%Y-%m-%dT%H:%M:%S.%fZ")
            today = datetime.now()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            pax_data = {
            "PassengerId":idx,
            "Title": pax.title,
            "FirstName": pax.first_name,
            "LastName": pax.last_name,
            "Gender": GENDER_TYPES[pax.gender.lower()],               # 1 = Male, 2 = Female
            "Age": age,
            "Seat":pax.misc.get("seat")
            }
            if idx==0:
                pax_data["LeadPassenger"]= True
                pax_data["Email"]= contact.get('email')
                pax_data["Phoneno"]= contact.get('phone')
            pax_list.append(pax_data)
            

       
        data = {"TraceId":traceId,"ResultIndex":ResultIndex,"boarding":boarding,"dropoff":dropoff,"pax_list":pax_list}
        if True:
            response = block(credentials=self.credentials,
                 base_url =self.base_url,data=data,session_id=session_id
            )
            print("BloCK")
            if response['BlockResult']['ResponseStatus']==1:
                response = book(credentials=self.credentials,
                 base_url =self.base_url,data=data,session_id=session_id
                )
                print("BOOK")
                if response['BookResult']['ResponseStatus']==1:


                    booking.pnr = response['BookResult']['TravelOperatorPNR']
                    booking.invoice_amount = response['BookResult']['InvoiceAmount']
                    booking.invoice_number = response['BookResult']['InvoiceNumber']
                    booking.ticket_number = response['BookResult']['TicketNo']
                    booking.status = "Confirmed"
                    booking.misc = booking.misc |{"BusId":response['BookResult']['BusId']}
                    booking.save(update_fields=["status","misc","pnr","invoice_amount","invoice_number","ticket_number"]) 
                    print("SUCCESS") 
                    return {"status":"success","data":response}
            booking.status = "Ticketing-Failed"
            booking.save(update_fields=["status"])  
            return {"status":"failure","data":response}
        else:
            booking.status = "Ticketing-Failed"
            booking.save(update_fields=["status"])
            return {"status":"failure","data":{}}

    def get_cancellation_charges(self,session_id,booking):
        traceId = booking.misc.get("TraceId")
        ResultIndex = booking.misc.get('ResultIndex')
        BusId = booking.misc.get('BusId')
        data = {"TraceId":traceId,"ResultIndex":ResultIndex,"BusId":BusId}
        try:
            response = booking_detail(credentials=self.credentials,
                 base_url =self.base_url,data=data,session_id=session_id
            )
            if response['GetBookingDetailResult']['ResponseStatus']==1:
                
                SourceId = int(response['GetBookingDetailResult']['Itinerary']['SourceId'])
                BookingMode = response['GetBookingDetailResult']['Itinerary']['BookingMode']
                data = data | {"SourceId":3534} #Default
                print("data",data)
                response = cancellation_charges(credentials=self.credentials,
                 base_url =self.base_url,data=data,session_id=session_id
                )
                if response['GetChangeRequestStatusResult']['ResponseStatus']==1:

                    converted = {"cancellation_charge": response['GetChangeRequestStatusResult']['BusCRInfo'][0]['CancellationCharge']}
                    booking.misc = {"SourceId":SourceId,"BookingMode":BookingMode}|booking.misc
                    booking.save(update_fields = ["misc"])
                    return {"status":"success","data":converted}

            return {"status":"failure","data":response}

        except:
            return {"status":"failure","data":{}}

    def cancel_ticket(self,session_id,booking,remarks):
        BookingMode = booking.misc.get("BookingMode")
        ResultIndex = booking.misc.get('ResultIndex')
        BusId = booking.misc.get('BusId')
        data = {"BookingMode":BookingMode,"ResultIndex":ResultIndex,"BusId":BusId}
        try:
            
            booking.status = "Cancel-Ticket-Initiated"
            booking.save(update_fields = ["status"])
            response = cancel_ticket(credentials=self.credentials,
                 base_url =self.base_url,data=data,session_id=session_id
            )
            if response['SendChangeRequestResult']['ResponseStatus']==1:
                booking.status = "Cancelled"
                booking.save(update_fields = ["status"])
                return {"status":"success","data":response}
            else:
                booking.status = "Rejected"
                booking.save(update_fields = ["status"])
                return {"status":"failure","data":{}}
        except:
            booking.status = "Cancel-Ticket-Failed"
            booking.save(update_fields = ["status"])
            return {"status":"failure","data":{}}

    def get_raw_seatmap(self,target_id,raw_data):
        seat_layout = raw_data.get("GetBusSeatLayOutResult",{}).get("SeatLayoutDetails",{}).get("SeatLayout",{}).get("SeatDetails",{})
        for row in seat_layout:         # iterate over each row (which is a list)
            for seat in row:            # iterate over each dictionary (seat) in the row
                if seat.get("seatmapID") == target_id:
                    return seat         # return the dictionary if it matches
        return None
    def get_raw_segment(self,segment_id,raw_data):
        BusResults = raw_data.get('data').get("BusSearchResult",{}).get("BusResults",[])
        raw = [x for x in BusResults if x["segmentID"]==segment_id]
        return raw[0] if len(raw)>0 else {}
    def add_uuid_to_seatmap(self,response):
        for x in response.get("GetBusSeatLayOutResult").get("SeatLayoutDetails").get("SeatLayout").get("SeatDetails"):
            for y in x:
                y["seatmapID"] = utils.create_uuid("SEAT")
        return response
    def add_uuid_to_pickup_drop(self,response):
        for x in response.get("GetBusRouteDetailResult").get("BoardingPointsDetails"):
            x["locationID"] = utils.create_uuid("BOARD")
        for x in response.get("GetBusRouteDetailResult").get("DroppingPointsDetails"):
            x["locationID"] = utils.create_uuid("DROP")
        return response
    def unify_seatmap(self,input_data,fare_detatils):
        new_structure = {
            "availableSeats": {
                "total": 0,
                "lower": 0,
                "upper": 0
            },
            "layoutData": {
                "lower": [],
                "upper": []
            }
        }
        
        # Set total available seats from the input (converted to int)
        total_available = int(input_data.get("AvailableSeats", "0"))
        new_structure["availableSeats"]["total"] = total_available
        
        # The original seat details are nested in SeatLayout->SeatDetails (a list of lists)
        seat_details = input_data.get("SeatLayout", {}).get("SeatDetails", [])
        seat_dict ={
                "lower": [],
                "upper": []
            }
        for row in seat_details:
            for seat in row:
                # Determine the section based on IsUpper flag
                is_upper = seat.get("IsUpper", False)
                section = "upper" if is_upper else "lower"
                
                updated_fare = utils.fare_calculation(fare_detatils,seat.get("Price", {}).get("PublishedPrice", 0),seat.get("Price", {}).get("OfferedPrice", 0))
                # Build the new seat object
                seat_obj = {
                    "seatNumber": seat.get("SeatName"),
                    "seatmapID": seat.get("seatmapID"),
                    # Here, we assume that a SeatStatus==True means available,
                    # so isBooked is the inverse (i.e. not booked)
                    "isBooked": not seat.get("SeatStatus", True),
                    "isLadiesSeat": seat.get("IsLadiesSeat", False),
                    "seatType": SEAT_TYPES[str(seat.get("SeatType", 1))],
                    "seatName":seat.get("SeatName", 1),
                    "price": {
                        "baseFare": seat.get("Price", {}).get("BasePrice", 0),
                        "publishedPrice": updated_fare.get("published_fare"),
                        "offeredPrice": updated_fare.get("offered_fare"),
                        "discount":  updated_fare.get("discount"),
                        "supplier_published_fare":  updated_fare.get("supplier_published_fare"),
                        "supplier_offered_fare":  updated_fare.get("supplier_offered_fare"),
                        "currency": seat.get("Price", {}).get("CurrencyCode", "")
                    },
                    "position": {
                        # Convert row and column strings to integers for easier handling
                        "row": int(seat.get("RowNo", "0")),
                        "column": int(seat.get("ColumnNo", "0")),
                        "width": seat.get("Width", 0),
                        "height": seat.get("Height", 0)
                    }
                }
                
                # Append seat to the appropriate section
                #new_structure["layoutData"][section].append(seat_obj)
                seat_dict[section].append(seat_obj)
                # If the seat is available (SeatStatus True means available),
                # count it as available for that section.
                if seat.get("SeatStatus", True):
                    new_structure["availableSeats"][section] += 1

        for key in seat_dict:
            rows = defaultdict(list)
            for seat in seat_dict[key]:
                row_num = seat["position"]["row"]
                rows[row_num].append(seat)

            # Build the output as a list of dictionaries
            grouped_seats = [{"row": row, "seats": seats} for row, seats in rows.items()]
            new_structure["layoutData"][key] = grouped_seats

        return new_structure
    
    def unify_pickup_drop(self,response):
        BoardingPoints = response.get("GetBusRouteDetailResult").get("BoardingPointsDetails")
        DroppingPoints = response.get("GetBusRouteDetailResult").get("DroppingPointsDetails")
        Pickups=[]
        Dropoffs=[]
        for point in BoardingPoints:
            location = {"locationID":point.get('locationID'),
                        "index":point.get("CityPointIndex", None),
                        "name": point.get("CityPointName", None),
                        "time": point.get("CityPointTime", None),
                        "address": point.get("CityPointLocation", None),
                        "contact": point.get("CityPointContactNumber", None), 
                        }
            Pickups.append(location)
        for point in DroppingPoints:
            location = {"locationID":point.get('locationID'),
                        "index":point.get("CityPointIndex", None),
                        "name": point.get("CityPointName", None),
                        "time": point.get("CityPointTime", None),
                        "address": point.get("CityPointLocation", None),
                        "contact": point.get("CityPointContactNumber", None), 
                        }
            Dropoffs.append(location)
        return {"BoardingPoints":Pickups,"DropoffPoints":Dropoffs}
