
from datetime import datetime
import time
import uuid
from common import utils
from common.utils import calculate_fare
from users.models import SupplierIntegration, UserDetails
from vendors.hotels import mongo_handler
from vendors.hotels.grn.api import booking_cancellation, bundled_rates_booking, hotel_availability, non_bundled_rates_booking
from vendors.hotels.models import GiataCity, GiataDestination, GiataProperties, GiataProviderCode, GrnCity, GrnDestination, GrnHotel
from vendors.hotels.tbo.api import get_destinations, perform_search,authentication
from vendors.hotels.utils import add_icon_types
from rapidfuzz import process

import json
import requests
from django.core.exceptions import ObjectDoesNotExist
from vendors.hotels.models import (
    HotelBooking, HotelBookedRoom, HotelBookedRoomPax
)
from collections import defaultdict
import concurrent.futures
from django import db

def divide_list(lst, n):
    """Divides a list into n sublists as evenly as possible."""
    k, m = divmod(len(lst), n)
    return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

def purchase(booking_id):
    """Fetches booking details from the database and calls the vendor booking API."""
    print("i'm purchasing.....")
    try:
        # Fetch booking details
        booking = HotelBooking.objects.select_related("hotel", "vendor").get(id=booking_id)

        # Fetch booked rooms
        booked_rooms = HotelBookedRoom.objects.filter(booking=booking).select_related("room")

        if not booked_rooms.exists():
            return {"error": "No rooms found for this booking"}

        # Prepare API request data
        hotel_code = booking.hotel.hotel_code if booking.hotel else None
        hotel_code = str(hotel_code).split("_$_")[-1]
        city_code = None # You might need a mapping function
        group_code = None  # Modify if needed
        check_in = booking.check_in.strftime("%Y-%m-%d")
        check_out = booking.check_out.strftime("%Y-%m-%d")
        payment_type = "AT_WEB"  # Adjust as needed
        base_url = booking.vendor.data['base_url']  # Replace with actual vendor API host
        headers = {"api-key": booking.vendor.data['api_key'],"Accept": "application/json",
        "Content-Type": "application/json"}  # Adjust headers as needed

        # Fetch customer details (holder)
        customer = booking.hotelbookingcustomer_set.first()  # Assuming at least one customer exists
        if not customer:
            return {"error": "No customer details found"}

        holder_details = {
            "title": customer.title,
            "name": customer.first_name,
            "surname": customer.last_name,
            "email": customer.email,
            "phone_number": customer.mobile_no,
            "client_nationality":customer.client_nationality,
            "pan_number":customer.pan,
            "pan_company_name":customer.pan_company_name,
            "fema_declaration":True
        }

        booking_items = []
        search_id = None
        for booked_room in booked_rooms:
            room = booked_room.room
            # import pdb;pdb.set_trace(
            # )
            booking_data = booked_room.booking_data
            if not room:
                continue

            # Fetch room paxes
            paxes = list(
                HotelBookedRoomPax.objects.filter(room=booked_room).values(
                    "title", "first_name", "last_name", "email", "mobile_no",'type',"age"
                )
            )
            # import pdb;pdb.set_trace()
            # pax_per_room = len(paxes)/booked_room.no_of_rooms
            paxes = divide_list(paxes,booked_room.no_of_rooms)

            booking_items.append({
                "room_code": booking_data['room_code'],
                "rate_key": booking_data['rate_key'],  # You may need a mapping
                "rooms":[{
                "room_reference": booking_data['room_reference'],  # Adjust as needed
                "paxes": room_pax} for room_pax in paxes]

            })
            search_id = booking_data['search_id']
            city_code = booking_data['city_code']
            group_code = booking_data['group_code']

            # Call external booking API
        # if booking_data['is_bundled']:
            # import pdb;pdb.set_trace()
        response,payload_dict,url,status = bundled_rates_booking(
            booking_items = booking_items,
            check_in=check_in,
            check_out=check_out,
            group_code=group_code,
            city_code=city_code,
            search_id=search_id,
            hotel_code=hotel_code,
            headers=headers,
            base_url=base_url,
            holder_details=holder_details,
            payment_type=payment_type,
        )
        booking.vendor_booking_reference = response.get('booking_reference')
        booking.save()
        result = {
            "response":response,
            "payload":payload_dict,
            "url":url,
            "status":status
        }
        return result

    except ObjectDoesNotExist:
        return {"error": "Booking not found"}
    except ValueError as e:
        return {"error": str(e)}



def generate_room_selection_title(paxes):
    #paxes = (adult_no, child_no, no_of_rooms_in_rate, children_ages)
    print("paxes",paxes)
    return f"Select {paxes['no_of_rooms']} rooms for {paxes['no_of_adults']} Adults {paxes['no_of_children']} Children"

def converter(search_responses, journey_details,fare_details):
    hotel_details = []
    unified_response = {}
    check_in = datetime.strptime(journey_details['check_in_date'], "%d-%m-%Y")
    check_out = datetime.strptime(journey_details['check_out_date'], "%d-%m-%Y")

    # Calculate the difference in days
    no_of_days = (check_out - check_in).days
    for search_response in search_responses:
        if "hotels" not in search_response:
            continue
        for hotel in search_response["hotels"]:
            hotel_code = f'GRN_$_{hotel.get("hotel_code", "")}'
            heading = hotel.get("name", "")
            rating = hotel.get("category", "")
            address = hotel.get("address", "")
            recommended = hotel.get("recommended", False)
            featured = hotel.get("featured", False)
            if recommended:
                image_tag = "recommended"
            elif featured:
                image_tag = "featured"
            else:
                image_tag = ""
            latitude = str(hotel.get("geolocation", {}).get("latitude",""))
            longitude = str(hotel.get("geolocation", {}).get("longitude",""))
            review_count = ""  # No review count available in given JSON
            amenity_list = hotel.get("facilities", "").split(" ; ")
            amenities = add_icon_types(amenity_list)
            room_pax = journey_details.get('room_pax',[])
            no_of_rooms = len(room_pax)
            
            # min_rate = hotel.get("min_rate", {})
            # minimum_price_value = min([rate['price'] for rate in hotel.get("rates", [])] +[0])
            
            booking_options = []
            # room_options = [{'room_index':i + 1, "title":self.generate_room_selection_title(room_pax,i),"pax":room_pax[i]} for i in range(no_of_rooms)]
            

            

            grouped_booking_options = defaultdict(list)

            for rate_item in hotel.get("rates", []):
                for room_item in rate_item.get("rooms", []):
                    features = []
                    adult_no = room_item.get("no_of_adults", 0)
                    child_no = room_item.get("no_of_children", 0)
                    children_ages = tuple(map(str, room_item.get("children_ages", [])))  # Convert list to tuple for dict key
                    no_of_rooms_in_rate = rate_item.get("no_of_rooms", 1)

                    room_code = f"{str(uuid.uuid4())}"

                    # Feature Extraction
                    if rate_item.get("includes_wifi"):
                        features.append("Wifi is included")
                    if room_item.get("description"):
                        features.append(room_item["description"])
                    if room_item.get("max_room_occupancy"):
                        features.append(f"Ideal for {room_item['max_room_occupancy']} persons")
                    if adult_no:
                        pax_string = f"Ideal for {adult_no} adult{'s' if adult_no != 1 else ''}"
                        if child_no:
                            pax_string += f" and {child_no} child{'ren' if child_no != 1 else ''}"
                        features.append(pax_string)

                    # Extend features with additional details
                    features.extend(rate_item.get("rate_comments", {}).values())
                    features.extend(rate_item.get("other_inclusions", []))
                    features.extend(rate_item.get("promotions_details", []))
                    features.extend(rate_item.get("boarding_details", []))

                    if rate_item.get("pan_required"):
                        features.append("PAN is required")

                    features = add_icon_types(features)

                    is_bundled = no_of_rooms_in_rate == journey_details["room_count"]

                    room_dict = {
                        "room_code": room_code,
                        "name": room_item["room_type"],
                        "features": features,
                        "price": calculate_fare(rate_item.get("price"), fare_details),
                        "price_currency": rate_item.get("currency", ""),
                        "no_of_adults": adult_no or room_item.get("max_room_occupancy"),
                        "no_of_children": child_no,
                        "no_of_rooms": no_of_rooms_in_rate,
                        "children_ages": children_ages,
                        "select_button_text": f"Select {no_of_rooms_in_rate} room{'s' if no_of_rooms_in_rate != 1 else ''}",
                        "booking_data": {
                            "room_reference": room_item.get("room_reference"),
                            "rate_key": rate_item.get("rate_key"),
                            "rate_type": rate_item.get("rate_type"),  # 'bookable' or 'recheck'
                            "room_code": rate_item.get("room_code"),
                            "search_id": search_response["search_id"],
                            "city_code": hotel.get("city_code", ""),
                            "group_code": rate_item.get("group_code"),
                            "is_bundled": is_bundled,
                        },
                    }

                    # Group rooms by (no_of_adults, no_of_children, no_of_rooms, children_ages)
                    # Group rooms by (no_of_adults, no_of_children, no_of_rooms, children_ages)
                    key = (adult_no, child_no, no_of_rooms_in_rate, children_ages)
                    grouped_booking_options[key].append(room_dict)
                    booking_options.append(room_dict)

            # Convert grouped dictionary back to a list
            # room_options = [{'room_index':index +1 ,"title":self.generate_room_selection_title(grouped_booking_options[index][0]),
            #                  "booking_options":grouped_booking_options[index][1]
            #                  } for index in range(len(grouped_booking_options))]
            room_options = [
            {
                "room_index": index + 1,
                "title": generate_room_selection_title(group[0]),  # First room in the group used for title
                "booking_options":  [
                    {**room, "room_code": f"{index + 1}_$_{room['room_code']}"} for room in group
                ],# All grouped rooms
                "pax":{
                    "adults_count": group[0]['no_of_adults'] * group[0]['no_of_rooms'],
                    "child_ages": group[0]['children_ages'] * group[0]['no_of_rooms']
                }
            }
            for index, group in enumerate(grouped_booking_options.values())
            ]



            minimum_price_item = min(booking_options, key=lambda x: x["price"])
            description = hotel.get("description", "")
            currency_symbol = minimum_price_item.get("price_currency", "")
            price = minimum_price_item.get("price", "")
            image = hotel.get("images",{}).get("url","")
            amenities = sorted(amenities, key=len)
            hotel_details.append({
                "hotel_code":hotel_code,
                "heading": heading,
                "description":description,
                "address":address,
                "latitude":latitude,
                "longitude":longitude,
                "rating": rating,
                "review_rating":"9.5",
                "rating_text":"Very Good",
                "review_count": review_count,
                "amenities": amenities,
                "top_facilities":amenities[0:3],
                "no_of_days": no_of_days,
                "minimum_price_item":minimum_price_item,
                "check_in":journey_details['check_in_date'],
                "check_out":journey_details['check_out_date'],
                "image":image,
                "images":[image],
                "price": price,
                "no_of_rooms":no_of_rooms,
                "currency_symbol": currency_symbol,
                "image_tag":image_tag,
                # "booking_options":booking_options,
                "room_options":room_options,
                "amenity_list":amenity_list
            })
        
    unified_response['data'] = hotel_details
    unified_response['status'] = 'success'
    return unified_response



def update_data_on_mongo(data,search_response,session_id,status,
                         mongo_client,vendor_name,vendor_id,user,duration):
        vendor_data = {"name":vendor_name,"id":vendor_id,"duration":duration,"status":"success"}
        mongo_client.store_raw_data(session_id,vendor_data, search_response)
        mongo_client.update_vendor_search_status(session_id,vendor_id,"Raw")

        if status == "success":
            start = time.time()
            fare_detatils = utils.get_fare_markup(user)
            unified_response = converter(search_response,data,fare_detatils)
            end = time.time()
            if unified_response.get("status") in ["success","partial_success"]:
                vendor_data = {"name":vendor_name,"id":vendor_id,"duration":end-start,"status":unified_response.get("status")}
                mongo_client.store_unified_data(session_id, vendor_data, unified_response.get("data"))
                mongo_client.update_vendor_search_status(session_id,vendor_id,"Unified")
            else:
                mongo_client.update_vendor_search_status(session_id,vendor_id,"Unified_Failed")
        else:
            mongo_client.update_vendor_search_status(session_id,vendor_id,"Raw_Failed")

def process_hotel_code(hotel_code, check_in_date, check_out_date, room_pax, token,base_url,data,session_id,vendor_name,vendor_id,user):
    # Define a top-level helper function for the proend-startcessing
    start = time.time()
    search_response = hotel_availability(
        hotel_code,
        check_in_date,
        check_out_date,
        room_pax,
        token,
        purpose_of_travel=2,
        currency="INR",
        client_nationality="IN",
        base_url=base_url
    )
    duration = time.time()-start
    db.close_old_connections()

    user = UserDetails.objects.filter(id = user).first()
    mongo_client = mongo_handler.Mongo()
    if "errors" not in search_response.keys():
        update_data_on_mongo(data,[search_response],session_id,"success",
                         mongo_client,vendor_name,vendor_id,user,duration)


    return search_response
class Manager(object):

    def __init__(self,**kwargs):
        self.data = kwargs.get('data')
        self.vendor = kwargs.get('vendor')
        self.mongo_client = kwargs.get('mongo_client')
        if not self.vendor:
            self.supplier_instance = SupplierIntegration.objects.filter(name = 'GRN',integration_type = 'Hotels').first()
        else:
            self.supplier_instance = self.vendor
        if not self.data:
            self.base_url = self.supplier_instance.data['base_url'] if self.supplier_instance else None
            self.token =   self.supplier_instance.data['api_key'] if self.supplier_instance else None
        else:
            self.base_url = self.data['base_url'] if self.supplier_instance else None
            self.token =  self.data['api_key'] if self.supplier_instance else None
        if not self.mongo_client:
            self.mongo_client = mongo_handler.Mongo()

    def name (self):
        return "GRN"
    
    def get_vendor_id(self):
        return str(self.vendor.id)
    
    def vendor_direct_search(self,data):
        # import pdb;pdb.set_trace()
        if data["search_type"] == "property":
            search_term = data["search_term"]
            hotels = list(GrnHotel.objects.values_list("name", flat=True))
            best_match = process.extractOne(search_term, hotels, score_cutoff=90) 
            hotels = GrnHotel.objects.filter(name__in = list(best_match)).values_list('code', flat=True)
            hotel_codes = list(hotels)

        elif data["search_type"] == "city":
            search_term = data["search_term"]
            cities = list(GrnCity.objects.values_list("name", flat=True))
            best_match = process.extractOne(search_term, cities, score_cutoff=80) 
            matched_city = GrnCity.objects.get(name=best_match[0])
            hotels = GrnHotel.objects.filter(city=matched_city).values_list('code', flat=True)
            hotel_codes = list(hotels)
            
        elif data["search_type"] == "destination":
            search_term = data["search_term"]
            destinations = list(GrnDestination.objects.values_list("name", flat=True))
            best_match = process.extractOne(search_term, destinations, score_cutoff=80) 
            matched_destination = GrnDestination.objects.get(name=best_match[0])
            hotels = GrnHotel.objects.filter(destination = matched_destination).values_list('code', flat=True)
            hotel_codes = list(hotels)

        return hotel_codes
    
        
    def search_results(self,data,session_id,user):
        check_in_date = data['check_in_date']
        check_out_date = data['check_out_date']
        room_pax = data['room_pax']
        if data["search_type"] == "property":
            property_id = data["search_query"]
            hotels = GiataProviderCode.objects.filter(property_id_id = property_id)
            hotel_codes = [str(code) for hotel_item in hotels for code in hotel_item.provider_code]

        elif data["search_type"] == "city":
            city_id = data["search_query"]
            hotels = GiataProviderCode.objects.filter(property_id__city_id = city_id)
            hotel_codes = [str(code) for hotel_item in hotels for code in hotel_item.provider_code]
            
        elif data["search_type"] == "destination":
            city_id = data["search_query"]
            hotels = GiataProviderCode.objects.filter(property_id__city_id__destination_id_id = city_id,provider_name = "grnconnect")
            hotel_codes = [str(code) for hotel_item in hotels for code in hotel_item.provider_code]
        
        print("hotel_codes",hotel_codes)
        # import pdb;pdb.set_trace()
        if not self.supplier_instance:
            print("here2")
            return {"data":{},"status":"failure","error":"missing supplier integration"}
        else:
            room_pax = [{"adults":pax["adults_count"],"children_ages":pax['child_ages']} for pax in room_pax]
            check_in_date = datetime.strptime(check_in_date, "%d-%m-%Y").strftime("%Y-%m-%d")
            check_out_date = datetime.strptime(check_out_date, "%d-%m-%Y").strftime("%Y-%m-%d")

            #test
            # hotel_codes = [
            #     "1386724",
            #     "1386377",
            #     "1380443",
            #     "1386364"

            # ]
           # test end
            end = time.time()
            search_response = hotel_availability(
                hotel_codes,
                check_in_date,
                check_out_date,#"2024-12-16",
                room_pax,
                self.token,
                purpose_of_travel = 2,
                currency = "INR",
                client_nationality =  "IN",
                base_url=self.base_url
                
            )
            start = time.time()
            
            # import pdb;pdb.set_trace()
            if "hotels" not in search_response.keys() or search_response['hotels'] == []:
                """CASE : When giata contents missing...."""
                search_response = None
            else:
                duration = end-start
                if "errors" not in search_response.keys():
                    update_data_on_mongo(data,[search_response],session_id,"success",
                                          self.mongo_client,self.name(),self.get_vendor_id(),user,duration)
                search_response = {"data":search_response,"status":"success"}

            if search_response == None:
                print("none search....")
                hotel_codes = self.vendor_direct_search(data)
                hotel_codes = divide_list(hotel_codes,99)
                # hotel_codes = [[
                #     "1386724",
                #     "1386377",
                #     "1380443",  
                #     "1386364"

                # ]]
                search_responses = []

                # for i in hotel_codes:
                #     search_response = hotel_availability(
                #     i,
                #     check_in_date,
                #     check_out_date,#"2024-12-16",
                #     room_pax,
                #     self.token,
                #     purpose_of_travel = 2,
                #     currency = "INR",
                #     client_nationality =  "IN",
                    
                #     )
                #     search_responses.append(search_response)
                #     print("search_response = ",search_response)

                # Assuming these variables are defined:

                # hotel_codes, check_in_date, check_out_date, room_pax, and self.token

                # If inside a class, extract self.token to a local variable.
                token = self.token

                # Using ProcessPoolExecutor to process each hotel code concurrently.
                with concurrent.futures.ProcessPoolExecutor() as executor:
                    # Create a list of futures, one for each hotel code.
                    futures = [
                        executor.submit(
                            process_hotel_code,
                            code, 
                            check_in_date, 
                            check_out_date, 
                            room_pax, 
                            token,
                            self.base_url,
                            data,
                            session_id,
                            self.name(),
                            self.get_vendor_id(),
                            user.id
                        )
                        for code in hotel_codes
                    ]

                    # Retrieve results as they complete.
                    search_responses = [future.result() for future in concurrent.futures.as_completed(futures)]

                # Now search_responses contains the response from each multiprocess call

                search_response = {"data":search_responses,"status":"success"}
            return search_response
            
    def get_pax_form(self,paxes):
        pax_forms = [{
        "form_type":"pax_form",
        "title": f"Adult ({i+1}) Details",
        "fields": [
                {
                    "label": "Title",
                    "key": "title",
                    "type": "select",
                    "disabled":False,
                    "value":None,
                    "options": ["Mr.", "Ms.", "Mrs.", "Dr."]
                },
                {
                    "label": "First Name",
                    "key": "first_name",
                    "type": "text",
                    "disabled":False,
                    "value":None,
                    "required": True
                },
                {
                    "label": "Last Name",
                    "key": "last_name",
                    "type": "text",
                    "disabled":False,
                    "value":None,
                    "required": True
                },
                {
                    "label": "Type",
                    "key": "type",
                    "disabled":True,
                    "type": "select",
                    "value": "AD",
                    "options": [
                        {"label": "Adult", "value": "AD"},
                        # {"label": "Child", "value": "CH"}
                    ],
                    "required": True
                },
                # {
                #     "label": "Age",
                #     "key": "age",
                #     "type": "number",
                #     "visibleIf": {"type": "CH"},
                #     "required": true
                # }
            ]
        }  for i in range(paxes['adults_count'])]
        
        pax_forms += [{
        "form_type":"pax_form",
        "title": f"Child (Age:{paxes['child_ages'][i]}) Details",
        "fields": [
                {
                    "label": "Title",
                    "key": "title",
                    "disabled":False,
                    "value":None,
                    "type": "select",
                    "options": ["Mr.", "Ms.", "Mrs.", "Dr."]
                },
                {
                    "label": "First Name",
                    "key": "first_name",
                    "disabled":False,
                    "value":None,
                    "type": "text",
                    "required": True
                },
                {
                    "label": "Last Name",
                    "key": "last_name",
                    "disabled":False,
                    "value":None,
                    "type": "text",
                    "required": True
                },
                {
                    "label": "Type",
                    "key": "type",
                    "disabled":False,
                    "value":"CH",
                    "type": "select",
                    "options": [
                        {"label": "Child", "value": "CH"}
                    ],
                    "required": True
                },
                # {
                #     "label": "Age",
                #     "key": "age",
                #     "disabled":False,
                #     "type": "number",
                #     "value":str(paxes['child_ages'][i]),            
                #     "visibleIf": {"type": "CH"},
                #     "required": True
                # }
                {
                    "label": "Age",
                    "key": "age",
                    "disabled":False,
                    "value":str(paxes['child_ages'][i]),
                    "type": "select",
                    "options": [
                        {"label": str(paxes['child_ages'][i]), "value":str(paxes['child_ages'][i])}
                    ],
                    "required": True
                },
            ]
        } for i in range(len(paxes['child_ages']))]

        return pax_forms

    def get_booking_holder_form(self):
        booking_holder_form = {
            "title": "Booking Holder Information Form",
            "fields": [
                {
                    "label": "Title",
                    "key": "title",
                    "type": "select",
                    "disabled":False,
                    "value":None,
                    "options": ["Mr.", "Ms.", "Mrs.", "Dr."],
                    "required": True
                },
                {
                    "label": "First Name",
                    "key": "first_name",
                    "type": "text",
                    "disabled":False,
                    "value":None,
                    "required": True
                },
                {
                    "label": "Last Name",
                    "key": "last_name",
                    "type": "text",
                    "disabled":False,
                    "value":None,
                    "required": True
                },
                {
                    "label": "Email",
                    "key": "email",
                    "type": "email",
                    "disabled":False,
                    "value":None,
                    "required": True,
                    "validation": {
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                        "message": "Enter a valid email address"
                    }
                },
                {
                    "label": "Phone Number",
                    "key": "mobile_no",
                    "type": "tel",
                    "disabled":False,
                    "value":None,
                    "required": True,
                    "validation": {
                        "pattern": "^[0-9]{10,15}$",
                        "message": "Enter a valid phone number (10-15 digits)"
                    }
                },
                {
                    "label": "Client Nationality",
                    "key": "client_nationality",
                    "type": "select",
                    "disabled":False,
                    "value":None,
                    "options": ["In", "US", "UK"],
                    "required": True
                },
                {
                    "label": "PAN Number",
                    "key": "pan",
                    "type": "text",
                    "required": True,
                    "disabled":False,
                    "value":None,
                    "validation": {
                        "pattern": "^[A-Z]{5}[0-9]{4}[A-Z]$",
                        "message": "Enter a valid PAN number (e.g., AAGCB9852N)"
                    }
                },
                {
                    "label": "Company Name (if applicable)",
                    "key": "pan_company_name",
                    "type": "text",
                    "disabled":False,
                    "value":None,
                    "visibleIf": {
                        "client_nationality": "In"
                    },
                    "required": False
                }
            ]
        }
        booking_holder_form
        return booking_holder_form


    def purchase(self,booking_id):
        return purchase(booking_id)
    
    def cancel_booking(self,booking_id):
        """cancel booking """
        booking = HotelBooking.objects.select_related("hotel", "vendor").get(id=booking_id)
        booking_reference = booking.vendor_booking_reference
        api_key = booking.vendor.data['api_key']
        base_url = booking.vendor.data['base_url']
        response = booking_cancellation(
        booking_reference,
        api_key,
        base_url=base_url,
        comments="Cancelled by client",
        reason=13,
        
        )
        response["status"] = response.get("status") == "confirmed"
        return response
        

