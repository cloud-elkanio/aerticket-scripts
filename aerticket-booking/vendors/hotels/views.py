
import time
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.http import JsonResponse
from rest_framework.views import APIView
from django.db.models import Q
from datetime import datetime
from django.shortcuts import get_object_or_404
from rest_framework import  status
from common.models import PaymentDetail
from common.razor_pay import razorpay_payment # imported here to solve circular import error

# from vendors.flights.views import deduplicate_master
# from vendors.flights.utils import create_segment_keys
from common.razor_pay import razorpay_payment
from vendors.hotels.hotel_manager import HotelManager
from users.models import SupplierIntegration, UserDetails
from vendors.hotels.models import GiataCity, GiataDestination, GiataProperties, HotelBookedRoom, HotelBookedRoomPax, HotelBooking, HotelBookingCustomer, HotelDetails, HotelEasylinkBilling, HotelRoom
from rapidfuzz import fuzz, process
from vendors.hotels.serializers import HotelBookingSerializer
from vendors.hotels.utils import generate_hotel_booking_display_id

def fuzzy_match_amenities(hotel_amenities, required_amenities, threshold=80):
    """
    Checks if the hotel has all required amenities using fuzzy matching.

    :param hotel_amenities: List of amenities in the hotel
    :param required_amenities: Set of required amenities
    :param threshold: Minimum similarity score (0-100)
    :return: True if all selected amenities have a close match in hotel amenities
    """
    for required in required_amenities:
        required = required.lower()
        match, score, _ = process.extractOne(required, hotel_amenities, scorer=fuzz.ratio, processor=None)
        if score < threshold:
            return False  # Reject if any required amenity does not match closely
    return True

def filter_hotels_by_amenities(hotels, required_amenities, threshold=80):
    """
    Filters hotels based on fuzzy-matched amenities.

    :param hotels: List of hotel dictionaries, each containing an 'amenities' key
    :param required_amenities: Set of required amenities
    :param threshold: Matching score threshold
    :return: List of hotels that match selected amenities
    """
    return [hotel for hotel in hotels if fuzzy_match_amenities(hotel['amenity_list'], required_amenities, threshold)]

def filter_hotels(unified_data,filters = {}):
    results = unified_data['result']
    amenities = filters.get("amenities",[])
    rating_items = filters.get("rating",[])
    has_unrated = any([True if x == "unrated" else False for x in rating_items])
    if "unrated" in rating_items:
        rating_items.remove("unrated")

    if len(amenities)!=0:
       results =  filter_hotels_by_amenities(results,amenities)
    if has_unrated:
        results = [hotel for hotel in results if hotel['rating']== "" ]
    if rating_items:
        results = [hotel for hotel in results if hotel['rating']!= "" and str(int(hotel['rating'])) in rating_items]
    unified_data['result'] = results
    return unified_data

class SuggestionView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        print("here")
        query = request.query_params.get('query')
        if not query:
            cities = [{
                "id": item.id, "name": item.city_name,
                "type":"city",
                "sub_heading":f"{item.destination_id.destination_name}, {item.destination_id.country_id.country_name}"}
                  for item in GiataCity.objects.order_by('city_name')[0:5]]
            locations = [{
                "id": item.id, "name": item.destination_name,
                "type":"destination",
                "sub_heading":f"{item.country_id.country_name}"}\
                      for item in GiataDestination.objects.\
                        order_by('destination_name')[0:5]]
            properties = [{"id":item.id, "name": item.name,
                           "type":"property",
                           "sub_heading":f"{item.city_id.city_name}, {item.city_id.destination_id.country_id.country_name}"}\
                              for item in GiataProperties.objects.order_by('name')[0:5]]
            
            suggestions = cities+locations+properties
            type_order = {"city": 0, "destination": 1, "property": 2}

            # Sort using the defined type order
            suggestions = sorted(suggestions, key=lambda x: (type_order.get(x["type"], 3), x["name"].lower()))

            print(suggestions[0])
            data = {
            "suggestions": suggestions,
            "default":cities[0] if len(cities)>0 else {}
            }
        else:
            cities = [{
                "id": item.id, "name": item.city_name,
                "type":"city",
                "sub_heading":f"{item.destination_id.destination_name}, {item.destination_id.country_id.country_name}"}
                      for item in GiataCity.objects.filter(Q(city_name__icontains=query)).order_by('city_name')[0:5]]
            locations = [{
                        "id": item.id, "name": item.destination_name,
                        "type":"destination",
                        "sub_heading":f"{item.country_id.country_name}"}\
                          for item in GiataDestination.objects.filter(Q(destination_name__icontains=query)).order_by('destination_name')[0:5]]
            properties = [{"id":item.id, "name": item.name,
                           "type":"property",
                           "sub_heading":f"{item.city_id.city_name}, {item.city_id.destination_id.country_id.country_name}"}\
                            for item in GiataProperties.objects.filter(Q(name__icontains=query)).order_by('name')[0:5]]
            suggestions = cities+locations+properties
            type_order = {"city": 0, "destination": 1, "property": 2}

            # Sort using the defined type order
            suggestions = sorted(suggestions, key=lambda x: type_order.get(x["type"], 3))
            data = {
            "suggestions":  suggestions,
            "default":{}
            }

        return JsonResponse(data, status=200)
    
class CreateSessionView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    # authentication_classes = []
    # permission_classes = []

    def post(self, request, *args, **kwargs):
        data = request.data 
        # user_id = request.user.id
        # user =  UserDetails.objects.filter(id=user_id ).first()
        hotel_manager = HotelManager(request.user)#request.user)
        data = hotel_manager.create_session(data)
        return JsonResponse(data, status=201)

def deduplicate_master(hotel_data,master_doc):
    """
    TODO:perform deduplication here
    """
    hotel_data = [j for i in hotel_data  for j in i['data']]
    # import pdb;pdb.set_trace()
    return {"result":hotel_data}

class HotelSearchDataView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        data = request.data  
        filters = data.get('filters',{})
        hotel_manager = HotelManager(user)
        session_id = data.get('session_id')
        start = time.time()
        validity = hotel_manager.check_session_validity(session_id,True)
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"hotel_search_response":{},"response_meta_data":response_meta_data,"session_id":session_id})
        master_doc = hotel_manager.master_doc
        vendors = hotel_manager.get_vendors()
        duration = time.time()-start
        misc_data = {"duration":duration}
        if not master_doc:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"hotel_search_response":{},"response_meta_data":response_meta_data,"session_id":session_id})
        search_details = master_doc.get("search_payload",{})
        print(master_doc)
        print("unified" in master_doc)
        if "unified" in master_doc:
            start = time.time()
            unified_ids = list(master_doc["unified"].keys())
            is_all_vendors = len(unified_ids) == len(vendors)
            unified_responses = hotel_manager.get_unified_doc(unified_ids)
            is_shown = [unified_vendor.get("is_shown") for unified_vendor in unified_responses]
            if not all(is_shown) :
                is_data_change = True
                hotel_manager.update_is_showed_unified_docs(session_id,unified_ids)
            else:
                is_data_change = False
            duration = time.time() -start
            misc_data["unified"] =duration
            hotel_data = list(unified_responses)
            if len(unified_responses) == 0:
                response_meta_data = {"session_break": True,"info":"Looks like we couldn't get any hotels for this search. <br> Please redo the search in other dates."}
                return JsonResponse({"search_response":{},"response_meta_data":response_meta_data,"session_id":session_id})
            hotel_data = list(unified_responses)
            start = time.time()
            for x in hotel_data:
                if '_id' in x:
                    del x['_id']
            duration = time.time()-start
            misc_data["id"] =duration
            start = time.time()
            unified_data =  deduplicate_master(hotel_data,master_doc)
            duration = time.time()-start
            misc_data["deduplicate"] = duration
            # unified_data["itineraries"] = create_segment_keys(master_doc)
            vendors = master_doc["vendors"]
            status_list = [y for x,y in vendors.items()]
            is_unified = "Unified" in status_list
            has_start_or_raw = "Start" in status_list or "Raw" in status_list
            # import pdb;pdb.set_trace()
            search_metadata = {
                "error_status": not is_unified and not has_start_or_raw,
                # "is_complete": is_unified and not has_start_or_raw and is_all_vendors,
                "is_complete":master_doc.get("status")=="completed",
                "is_data_change" :is_data_change
            } 
            response_meta_data = {"session_break":search_metadata.get("error_status")}
            if response_meta_data.get("error_status"):
                response_meta_data["info"] = "Supplier services are temporarily unavailable. Please try again later."

            filtered_results = filter_hotels(unified_data, filters)

            return_data = filtered_results | {"search_details":search_details} |{"search_metadata":search_metadata}
            return JsonResponse({"search_response":return_data,"response_meta_data":response_meta_data,\
                                 "session_id":session_id,"misc":misc_data,
                                 "total_results":len(return_data.get('result',[]))})
        else:
            search_meta_data = {
            "error_status": False,
            "is_complete": master_doc.get("status")=="completed",
            "is_data_change":True
            }
            response_meta_data = {"session_break": False,"info":""}
            return JsonResponse({"search_response":{"search_metadata":search_meta_data, "search_details":search_details},"session_id":session_id,"misc":misc_data,"response_meta_data":response_meta_data})


class HotelDetailsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        session_id = request.query_params.get('session_id')
        hotel_code = request.query_params.get('hotel_code')
        room_code = request.GET.getlist("room_code",[])
        is_dynamic_form = request.query_params.get('is_dynamic_form',False)
        user = request.user
        hotel_manager = HotelManager(user)
        hotel_details = hotel_manager.get_hotel_details(**{"session_id":session_id,
                                           "hotel_code":hotel_code,"room_code":room_code,
                                           "is_dynamic_form":is_dynamic_form})
        
        
        
        return JsonResponse(hotel_details,safe=False)

class HotelBookingEnquiry(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        data = request.data
        session_id = data['session_id']
        hotel_code = data['hotel_code']
        selected_rooms = request.data.get("selected_rooms",[])
        is_dynamic_form = True
        booking_holder = data['booking_holder']

        user = request.user
        hotel_manager = HotelManager(user)
        room_codes = [i['room_code'] for i in selected_rooms]
        hotel_details = hotel_manager.get_hotel_details(**{"session_id":session_id,
                                           "hotel_code":hotel_code,"room_code":room_codes,
                                           "is_dynamic_form":is_dynamic_form})
        hotel_details = hotel_details['data']
        # price = hotel_details["minimum_price_item"]['price']
        # import pdb;pdb.set_trace()
        
        master_doc = hotel_manager.get_master_doc(session_id)

        # import pdb;pdb.set_trace()
        hotel, created = HotelDetails.objects.update_or_create(
        hotel_code=hotel_code,
        defaults={
            "heading": hotel_details['heading'],
            "address": hotel_details['address'],
            "latitude": hotel_details['latitude'],
            "longitude": hotel_details['longitude'],
            "description": hotel_details['description'],
            "amenities": hotel_details['amenity_list'],
            "image": hotel_details['image'],
            "base_price": hotel_details["minimum_price_item"]['price'],
            "currency_code": hotel_details["minimum_price_item"]['price_currency'],
            "star_rating":hotel_details["rating"],
            "review_rating":hotel_details["review_rating"]

        }
    )
        
        vendor = SupplierIntegration.objects.filter(name = hotel_details['hotel_code'].split("_$_")[0]).first()
        check_in = master_doc['search_payload']['check_in_date']
        check_out = master_doc['search_payload']['check_out_date']
        check_in = datetime.strptime(check_in, "%d-%m-%Y")
        check_out = datetime.strptime(check_out, "%d-%m-%Y")
        display_id = generate_hotel_booking_display_id()
        booking_data = {
            "created_by":request.user,
            "hotel":hotel,
            "status":"enquiry",
            "vendor":vendor,
            "check_in":check_in,
            "check_out":check_out,
            "total_amount":0.0,
            "display_id":display_id
        }
        booking = HotelBooking.objects.create(**booking_data)
        
        
        booking_customer = {
            "booking":booking,
            "title":booking_holder.get('title'),
            "first_name":booking_holder.get('first_name'),
            "last_name":booking_holder.get('last_name'),
            "email":booking_holder.get('email'),
            "pan":booking_holder.get('pan'),
            "client_nationality":booking_holder.get('client_nationality'),
            "pan_company_name":booking_holder.get('pan_company_name'),
            "mobile_country_code":booking_holder.get('mobile_country_code'),
            "mobile_no":booking_holder.get('mobile_no')


        }
        booking_customer = HotelBookingCustomer.objects.create(**booking_customer)
        # booked_rooms = [

        #     for room in 
        # ]

        # for room in hotel_details['room_options']:
        total_amount = 0.0
        for room in selected_rooms:
            room_index = room['room_code'].split("_$_")[0]
            selected_room = next((i for i in hotel_details['room_options'] if str(i['room_index']) == str(room_index)), None)
            selected_room = selected_room['selected_room']
            # print("selected_room = ",selected_room)
            room_instance, created = HotelRoom.objects.get_or_create(
            hotel=hotel,
            room_code=selected_room['room_code'],
            defaults={
                "name":selected_room['name'],
                "features":selected_room['features'],
                "price": selected_room['price'],
                "currency_code": selected_room['price_currency'],
                "booking_data": selected_room['booking_data']
            }
            )
            # for selected_room
            print("selected_room = ",selected_room)
            booked_room = HotelBookedRoom.objects.create(
                room = room_instance,
                booking = booking,
                no_of_rooms = selected_room['no_of_rooms'],
                no_of_adults = selected_room['no_of_adults'],
                no_of_children = selected_room['no_of_children'],
                price = selected_room['price'],
                booking_data = selected_room['booking_data']

            )
            total_amount += float(selected_room['price'])
            
            # import pdb;pdb.set_trace()
            for pax_form in room['paxes']:
                # pax_data = {
                # field['key']:field['value']
                # for field in pax_form['fields']}
                pax_data = pax_form
                #TODO: validate here whether every data required is passed in API

                
                print("pax_data = ",pax_data)
                HotelBookedRoomPax.objects.create(
                    **{
                    "room":booked_room,
                    "title":pax_data.get('title'),
                    "first_name":pax_data.get('first_name'),
                    "last_name":pax_data.get('last_name'),
                    "email":pax_data.get('email'),
                    "pan":pax_data.get('pan'),
                    "mobile_country_code":pax_data.get('mobile_country_code'),
                    "mobile_no":pax_data.get('mobile_no'),
                    "type":pax_data.get('type'),
                    "age":pax_data.get('age')


                }
                )

        
    
        
        payment = PaymentDetail.objects.create(
            amount = total_amount,
            status = 'pending',
            created_by = request.user,
            payment_handler = 'HotelManager',

        )
        booking.payment = payment
        booking.total_amount = total_amount
        booking.save()

        rooms = HotelBookedRoom.objects.filter(booking_id = booking.id)
        no_of_adults = sum([int(i.no_of_adults) for i in rooms])
        no_of_children = sum([int(i.no_of_children) for i in rooms])
        no_of_rooms = sum([int(i.no_of_rooms) for i in rooms])

        easy_link_data = {
            "InvoiceDate": datetime.today().strftime('%d-%m-%y'),
            "tktDt": datetime.today().strftime('%d-%m-%y'),
            "SuppType": "S",
            "CustCode": f"{booking.created_by.first_name} {booking.created_by.last_name}",
            "ServiceType": "H",
            "HCheckInDate": booking.check_in.strftime('%d-%m-%y'),
            "HCheckOutDate": booking.check_out.strftime('%d-%m-%y'),
            "SPName": booking.hotel.heading,
            "HAddress": booking.hotel.address,
            "HNoOfRooms": no_of_rooms,
            "HNoOfAdult": no_of_adults,
            "HNoOfChild":no_of_children,
            "Amount": booking.total_amount,
            "CustPercGTAX": booking.total_amount * 0.05,
            "CreditType": "H"
        }
        easy_link_data = data = {
            "InvoiceRefID": booking.display_id,
            "InvoiceDate": datetime.today().strftime("%d/%m/%Y"),
            "XORef": booking.hotel.hotel_code,
            "SuppType": "S",
            "CustCode": f"{booking.created_by.first_name} {booking.created_by.last_name}",
            "suppcode": vendor.name,
            "SuppCCIssue": "N",
            "ServiceType": "H",
            "IntDom": "D",
            "tktRef": f"{booking.created_by.first_name} {booking.created_by.last_name}",
            "PaxName": f"{booking.created_by.first_name} {booking.created_by.last_name}",
            "SPName": booking.hotel.heading,
            "Remark1": "",
            "Remark2": "",
            "HCheckInDate":  booking.check_in.strftime("%d/%m/%Y"),
            "HCheckInTime": "",
            "HCheckOutDate": booking.check_out.strftime("%d/%m/%Y"),
            "HCheckOutTime": "",
            "HConfirmedBy": "",
            "HConfirmedOn": "",
            "HAddress": booking.hotel.address,
            "HTelNo": "",#test from here
            "HBookingPlan": "Business",
            "HRoomType": booking.hotel.heading,
            "HNoOfRooms": no_of_rooms,
            "HNoOfAdult": no_of_adults,
            "HNoOfChild":no_of_children,
            "HNoOfExtra": "",
            "HComingFrom": "",
            "HComingBy": "",
            "HProceedingTo": "",
            "HProceedingBy": "",
            "HPkgInclusions": "",
            "HPkgExclusions": "",
            "HPaymentMode": "",
            "HRefNo": booking.hotel.hotel_code,
            "HIssuedBy": "",
            "HIssuedOn": "",
            "HRoomRentPerDay": "",
            "HSpecialTC": "",
            "Amount": str(booking.total_amount),
            "TaxA": "000.00",
            "TaxB": "00.00",
            "TaxC": "00.00",
            "OthChgs": "00.00",
            "StdComm": "000.00",
            "SrvChrgs": "000.00",
            "MGTFee": "00.00",
            "CustStdComm": "00.00",
            "CustSrvChrgs": "00.00",
            "CustMGTFee": "00.00",
            "PercTDS": "",
            "TDS": "",
            "CustPercTDS": "",
            "CustTDS": "",
            "PercGTAX": "5",
            "GTAX": "",
            "CustPercGTAX": "5",
            "CustGTAX": str(booking.total_amount * 0.05),
            "CreditType": "H"
        }
        easy_link_datas = [HotelEasylinkBilling(
            booking_id = booking.id,
            key = key,
            value = value
            ) for key,value in easy_link_data.items()]
        HotelEasylinkBilling.objects.bulk_create(easy_link_datas)
        return JsonResponse({"success":True,"booking_id":booking.id,'payment_id':payment.id})


class HotelBookingDetailsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request,booking_id, *args, **kwargs):
        booking = get_object_or_404(HotelBooking, id=booking_id)
        serializer = HotelBookingSerializer(booking)
        return JsonResponse(serializer.data, status=200)


class HotelPaymentDetailsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request,payment_id, *args, **kwargs):
        payment = get_object_or_404(PaymentDetail, id=payment_id)
        booking = payment.hotel_booking if payment else None
        if not booking:
            return JsonResponse({"error":"invalid payment id"}, status=400)
        serializer = HotelBookingSerializer(booking)
        return JsonResponse(serializer.data, status=200)

class DisplayId(APIView):

    authentication_classes = []
    permission_classes = []


    def get(self, request, *args, **kwargs):

        for i in HotelBooking.objects.all():
            i.display_id = generate_hotel_booking_display_id()
            i.save()
        
        return JsonResponse({"success":True}, status=200) 

class BookingCanellationView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request,booking_id, *args, **kwargs):
        """
        TO BE COMPLETED
        """
        user = request.user
        hotel_manager = HotelManager(user)
        response = hotel_manager.cancel_booking(booking_id)
        if response["status"] == True:
            return JsonResponse({"success":True}, status=200)
        else:
            return JsonResponse({"success":False,
                                 "message":"cancellation failed for this booking",
                                 "vendor_cancellation_response":response
                                 }, status=400)


class FaledBookingConfirmationView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request,booking_id, *args, **kwargs):
        """
        TO BE COMPLETED
        """
        user = request.user
        hotel_manager = HotelManager(user)
        response = hotel_manager.confirm_failed_booking(booking_id)
        if response["status"] == True:
            return JsonResponse({"success":True}, status=200)
        else:
            return JsonResponse({"success":False,
                                 "message":"process failed for this booking",
                                 "vendor_cancellation_response":response
                                 }, status=400)

class FaledBookingRejectView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request,booking_id, *args, **kwargs):
        user = request.user
        hotel_manager = HotelManager(user)
        response = hotel_manager.reject_failed_booking(booking_id)
        if response["status"] == True:
            return JsonResponse({"success":True}, status=200)
        else:
            return JsonResponse({"success":False,
                                 "message":"process failed for this booking",
                                 "vendor_cancellation_response":response
                                 }, status=400)
