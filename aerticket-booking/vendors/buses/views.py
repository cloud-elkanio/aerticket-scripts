from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from users.models import UserDetails
from .bus_manager import BusManager
from .models import BusCity,BusBooking,BusBookingFareDetail,BusBookingPaxDetail,BusBookingSearchDetail
from rest_framework import status
import threading,os,json
from  datetime import datetime,timezone

import time
class CreateCities(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        user = UserDetails.objects.filter(id=user_id).first()
        bus_manager = BusManager(user)
        response_data = bus_manager.sync_city()
        cities = response_data
        errors = []
        if len(cities) > 0:

            final_response = {

                "status": True,
                "response_meta_data": {"session_break": False, "info": ""},
                "error":errors
            }
        else:
            final_response = {

                "status": False,
                "response_meta_data": {"session_break": False, "info": ""},
                "errors":errors
            }

            # Otherwise, return the data
        return JsonResponse(final_response, safe=False)





class CityListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        user = UserDetails.objects.filter(id=user_id).first()
        manager = BusManager(user)
        search_query= self.request.query_params.get('search_query')

        response_data = manager.search_city(search_query.strip())


        # If `None` (or null list) is returned from the manager, respond with a standard error
        if response_data is None or len(response_data) == 0:
            return JsonResponse(
                {"error": "Unable to retrieve city list at this time."},
                status=400
            )

        final_response = {
            "city_list": response_data,
            "status": True,
            "response_meta_data": {"session_break": False, "info": ""}
        }


        # Otherwise, return the data
        return JsonResponse(final_response, safe=False)


class SearchBus(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user = UserDetails.objects.filter(id=user_id).first()
        bus_manager = BusManager(user)
        search_query= self.request.data
        data = bus_manager.create_session(search_query)
        return JsonResponse(data, status=201)

class SearchBusData(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user = UserDetails.objects.filter(id=user_id).first()
        self.user = user
        bus_manager = BusManager(user)
        session_id= self.request.data.get("session_id")
        start = time.time()
        validity = bus_manager.check_session_validity(session_id,True)
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"bus_search_response":{},"response_meta_data":response_meta_data,"session_id":session_id})
        master_doc = bus_manager.master_doc
        vendors = bus_manager.get_vendors()
        duration = time.time()-start
        misc_data = {"duration":duration}
        if not master_doc:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"bus_search_response":{},"response_meta_data":response_meta_data,"session_id":session_id})

        contact = {
                        "email":self.user.email,\
                        "phone_code":self.user.phone_code,
                       "phone_number":self.user.phone_number,
                       "support_email":self.user.organization.support_email,
                       "support_phone":self.user.organization.support_phone,
        }
        search_details ={"search_details": master_doc.get("search_data",{})}|{"contact":contact}

        if 'raw' in master_doc:
            raw_statuses = [item.get("status") for key, item in master_doc.get('raw').items() if item.get("status") == "failure"]
            if raw_statuses:
                if all(status == "failure" for status in raw_statuses):
                    response_meta_data = {"session_break": True,"info":"Looks like we couldn't get any buses for this search. <br> Please redo the search in other dates."}
                    return JsonResponse({"bus_search_response":search_details,"response_meta_data":response_meta_data,"session_id":session_id})
           

        if "unified" in master_doc:
            start = time.time()
            unified_ids = list(master_doc["unified"].keys())
            is_all_vendors = len(unified_ids) == len(vendors)
            unified_responses = bus_manager.get_unified_doc(unified_ids)
            is_shown = [unified_vendor.get("is_shown") for unified_vendor in unified_responses]
            if not all(is_shown) :
                is_data_change = True
                bus_manager.update_is_showed_unified_docs(session_id,unified_ids)
            else:
                is_data_change = False
            duration = time.time() -start
            misc_data["unified"] = duration
            if len(unified_responses) == 0:
                response_meta_data = {"session_break": True,"info":"Looks like we couldn't get any buses for this search. <br> Please redo the search in other dates."}
                return JsonResponse({"bus_search_response":search_details,"response_meta_data":response_meta_data,"session_id":session_id})
            bus_data = list(unified_responses)

            
            start = time.time()
            for x in bus_data:
                if '_id' in x:
                    del x['_id']
            duration = time.time()-start
            misc_data["id"] = duration
            start = time.time()
            unified_data = [data.get('data') for data in bus_data][0]

            duration = time.time()-start
            misc_data["deduplicate"] = duration
            vendors = master_doc["vendors"]
            status_list = [y for x,y in vendors.items()]
            is_unified = "Unified" in status_list
            has_start_or_raw = "Start" in status_list or "Raw" in status_list
            search_metadata = {
                "error_status": not is_unified and not has_start_or_raw,
                "is_complete": is_unified and not has_start_or_raw and is_all_vendors,
                "is_data_change" :is_data_change
            } 
            response_meta_data = {"session_break":search_metadata.get("error_status")}
            if response_meta_data.get("error_status"):
                response_meta_data["info"] = "Supplier services are temporarily unavailable. Please try again later."
            return_data = {"data":unified_data} |{"search_metadata":search_metadata} |search_details
            return JsonResponse({"bus_search_response":return_data,"response_meta_data":response_meta_data,"session_id":session_id,"misc":misc_data})
        else:

            search_meta_data = {
            "error_status": False,
            "is_complete": False,
            "is_data_change":True
            }
            response_meta_data = {"session_break": False,"info":""}
            return JsonResponse({"bus_search_response":{"search_metadata":search_meta_data}|search_details,"session_id":session_id,"misc":misc_data,"response_meta_data":response_meta_data})


class SeatMap(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user = UserDetails.objects.filter(id=user_id).first()
        bus_manager = BusManager(user)
        search_query= self.request.data
        data = request.data 
        session_id = data.get('session_id')

        validity = bus_manager.check_session_validity(session_id)
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"bus_seat_pricing":{},"response_meta_data":response_meta_data,"session_id":session_id})
        start= time.time()
        response = bus_manager.get_seatmap(search_query)
        duration = time.time()-start
        response_meta_data = {"session_break":response.get("status",False)!="success","duration":duration}
        if response.get("status","failure")!="success":
            response_meta_data["info"] = "Unable to retrieve latest fare details from suppliers."     
        return JsonResponse({"bus_seat_pricing":response,"status":"success","response_meta_data":response_meta_data}, 
                            status = status.HTTP_201_CREATED)

class PickupDrop(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user = UserDetails.objects.filter(id=user_id).first()
        bus_manager = BusManager(user)
        search_query= self.request.data
        data = request.data 
        session_id = data.get('session_id')

        validity = bus_manager.check_session_validity(session_id)
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"bus_pickup_drop":{},"response_meta_data":response_meta_data,"session_id":session_id})
        start= time.time()
        response = bus_manager.get_pickup_drop(search_query)
        duration = time.time()-start
        response_meta_data = {"session_break":response.get("status",False)!="success","duration":duration}
        if response.get("status","failure")!="success":
            response_meta_data["info"] = "Unable to retrieve latest fare details from suppliers."    
        return JsonResponse({"bus_pickup_drop":response,"status":"success","response_meta_data":response_meta_data}, 
                            status = status.HTTP_201_CREATED)


class CreateBooking(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user = UserDetails.objects.filter(id=user_id).first()
        bus_manager = BusManager(user)
        booking_data= self.request.data
        data = request.data 
        session_id = data.get('session_id')

        validity = bus_manager.check_session_validity(session_id)
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"bus_seat_pricing":{},"response_meta_data":response_meta_data,"session_id":session_id})
        start= time.time()
        response = bus_manager.create_booking(booking_data)
        duration = time.time()-start
        response_meta_data = {"session_break":response.get("status",False)!="success","duration":duration}
        if response.get("status","failure")!="success":
            response_meta_data["info"] = "Unable to retrieve latest fare details from suppliers."     
        return JsonResponse({"booking":response.get('booking'),"status":"success","response_meta_data":response_meta_data}, 
                            status = status.HTTP_201_CREATED)

class BookingDetailsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        booking = BusBooking.objects.filter(id = data["booking_id"]).first()
        # Retrieve related one-to-one details using the ForeignKey relationships
        search_details = booking.search_detail
        payment_details = booking.bus_payment_details
        aws_bucket = os.getenv('AWS_STORAGE_BUCKET_NAME',"")
        profile_pic = "https://{}.s3.amazonaws.com/media/{}".format(aws_bucket,str(booking.user.organization.profile_picture))
        organization_details = {"support_email":booking.user.organization.support_email,"support_phone":booking.user.organization.support_phone,
                                    "profile_img_url":profile_pic,"profile_address":booking.user.organization.address,
                                    "profile_name":booking.user.organization.organization_name}
        # Get contact details (assumed to be one-to-many)
        pax_data = BusBookingPaxDetail.objects.filter(booking_id=booking)
        fare_data = BusBookingFareDetail.objects.filter(pax_id__booking_id=booking.id)
        pax_details = []

        for pax in pax_data:
            fare = fare_data.filter(pax_id = pax).first()
            fare_breakdown = json.loads(fare.fare_breakdown)
            pax_details.append({ 
                "title": pax.title,
                "first_name": pax.first_name,
                "last_name": pax.last_name,
                "dob": pax.dob,
                "pax_type": pax.pax_type,
                "seat_type": pax.seat_type,
                "gender": pax.gender,
                "seat_name":pax.seat_name,
                "price":{ 
                    "publishedPrice": fare.published_fare,
                        "offeredPrice": fare.offered_fare,
                        "discount":  fare.organization_discount,
                        "basePrice":fare_breakdown.get('baseFare')

                }
            })
        contact_details = json.loads(booking.contact)
        
        def get_location(city):
            return_data = ""
            if city.city_name:
                return_data += city.city_name 
                if city.country: 
                    return_data += " _ " +city.country.country_name
            return return_data
        location_details = {
            "pickup": {
                "name": search_details.pickup_name,
                "time": search_details.pickup_time,
                "address": search_details.pickup_address,
                "contact": search_details.pickup_contact,
            },
            "drop": {
                "name": search_details.dropoff_name,
                "time": search_details.dropoff_time,
                "address": search_details.dropoff_address,
                "contact": search_details.dropoff_contact,
            }
        }
        dt = datetime.fromtimestamp(booking.created_at, tz=timezone.utc)
        booked_at = dt.strftime("%d-%m-%YT%H:%M:%SZ")
        response_data = {
            "booking": {
                "display_id": booking.display_id,
                "session_id": booking.session_id,
                "segment_id": booking.segment_id,
                "pnr": booking.pnr,
                "ticket_number": booking.ticket_number,
                "status": booking.status,
                "error": booking.error,
                "departure_time": booking.departure_time,
                "arrival_time" : booking.arrival_time,
                "bus_type" : booking.bus_type,
                "operator" : booking.operator,
                "provider" : booking.provider,
                "booking_date": booked_at
            },
            "search_details": {
                "travel_date": search_details.travel_date,
                "origin":get_location(search_details.origin),
                "destination":get_location(search_details.destination)
            },
            "payment_details": {
                "payment_type": payment_details.payment_type,
                "status": payment_details.status,
                "published_fare": payment_details.new_published_fare,
                "offered_fare": payment_details.new_offered_fare,
            },
            "contact_details": contact_details,
            "location_details": location_details,
            "organization_details":organization_details,
            "passenger_details":pax_details,
            "cancellation_details":booking.cancellation_details
        }
        return JsonResponse(response_data, safe=False)


class Purchase(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        purchase_data = request.data
        user =  UserDetails.objects.filter(id = request.user.id).first()
        bus_manager = BusManager(user)
        session_id = request.data.get('session_id')
        booking_id = purchase_data.get("booking_id")
        validity = bus_manager.check_session_validity(session_id)
        bus_manager.mongo_client.searches.insert_one({"session_id":session_id,"booking_id":purchase_data.get("booking_id"),
                                                         "type":"purchase_initiated","payment_mode":purchase_data.get("payment_mode"),
                                                         "createdAt":datetime.now()})
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"bus_purchase_response":{},"response_meta_data":response_meta_data,"session_id":session_id})
        if purchase_data.get("payment_mode","wallet").strip().lower() == "wallet":
            wallet_thread = threading.Thread(target = bus_manager.purchase, kwargs={'data': purchase_data,"wallet":True})
            wallet_thread.start()
            return JsonResponse({"status":True,"razorpay_url":None,"response_meta_data":{"session_break":False, "info":""}}, status = status.HTTP_201_CREATED) 
        else:
            response = bus_manager.purchase(data = purchase_data,wallet = False)
            return JsonResponse({"status":True,"razorpay_url":response.get("payment_url"),"error":response.get("error"),"response_meta_data":{"session_break":False, "info":""}}, 
                                status = status.HTTP_201_CREATED) 

class PurchaseStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        booking = BusBooking.objects.filter(id = data["booking_id"]).first()
        final_response = {
            "purchase_status":booking.status,
            "status":True,
            "response_meta_data":{"session_break":False,"info":""},
        }
        return JsonResponse(final_response, safe=False)

class ProcessFailedView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 

        booking = BusBooking.objects.filter(id = data["booking_id"]).first()
        if booking:
            if data.get("status" == "Confirmed"):
                if booking.status != 'Confirmed':
                    booking.pnr = data.get('pnr',"")
                    booking.ticket_number = data.get('ticket_number',"")
                    booking.status = 'Confirmed'
                    booking.save(update_fields = ["pnr","ticket_number","status"])
                    final_response = {
                        "booking_status":booking.status,
                        "status":True,
                        "response_meta_data":{"session_break":False,"info":""},
                    }
                else:
                    final_response = {
                        "booking_status":booking.status,
                        "status":False,
                        "response_meta_data":{"info":"This is already a confirmed Booking"},
                    }
            else:
                booking.status = 'Rejected'
                booking.save(update_fields = ["status"])
                final_response = {
                        "booking_status":booking.status,
                        "status":True,
                        "response_meta_data":{"info":""},
                    }
        else:
            final_response = {
                        "status":False,
                        "response_meta_data":{"info":"There is no booking associated with the provided Booking id"},
                    }
        return JsonResponse(final_response, safe=False)

class CancellationCharges(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated] 
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = BusManager(user)
        data = request.data
        booking_id = data.get('booking_id')
        cancellation=  flight_manager.cancellation_charges(booking_id)
        return JsonResponse(cancellation, status=201)

class CancelTicket(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated] 
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        bus_manager = BusManager(user)
        data = request.data
        
        booking_id = data.get('booking_id')
        remarks = data.get('remarks')
        cancellation=  bus_manager.cancel_ticket(booking_id,remarks)
        return JsonResponse(cancellation, status=201)
