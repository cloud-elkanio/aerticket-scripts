from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .transfers_manager import TransferManager
from users.models import UserDetails

from common.models_transfers import TransferBookingSearchDetail, TransferBookingPaymentDetail, TransferBooking, \
                                    TransferBookingContactDetail, TransferBookingFareDetail, TransferBookingLocationDetail
import os, json
from datetime import datetime

class CountryListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        manager = TransferManager(user)
        if manager.auth_success:
            response_data = manager.get_country_list()
        else:
            return JsonResponse(
                {"error": "No suppliers are associated with your account. Kindly contact support for assistance."},
                status=401
            )
        
        # If `None` (or null list) is returned from the manager, respond with a standard error
        if response_data is None or len(response_data) == 0:
            return JsonResponse(
                {"error": "Unable to retrieve country list at this time."},
                status=400
            )
        
        final_response = {
            "country_list":response_data,
            "status":True,
            "response_meta_data":{"session_break":False,"info":""}
        }
            
        # Otherwise, return the data
        return JsonResponse(final_response, safe=False)

class CityDataView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        module = self.request.query_params.get('type', "City")
        country_code = self.request.query_params.get('country_code', "IN")
        if module == "City":
            search_type = "1"
        elif module == "Hotel":
            search_type = "2"
        else:
            search_type = "1"
        kwargs = {
                "search_type": search_type,
                "country_code": country_code,
            }
        user =  UserDetails.objects.filter(id=user_id ).first()
        manager = TransferManager(user)
        if manager.auth_success:
            response_data = manager.get_city_data(kwargs)
        else:
            return JsonResponse(
                {"error": "No suppliers are associated with your account. Kindly contact support for assistance."},
                status=401
            )
        # If `None` (or null list) is returned from the manager, respond with a standard error
        if response_data is None or len(response_data) == 0:
            return JsonResponse(
                {"error": "Unable to retrieve Hotel/City details at this time."},
                status=400
            )
        
        final_response = {
            "city_hotel_list":response_data,
            "status":True,
            "response_meta_data":{"session_break":False,"info":""}
        }
        # Otherwise, return the data
        return JsonResponse(final_response, safe=False)

class SelectDestination(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        manager = TransferManager(user)
        if manager.auth_success:
            response_data = manager.pre_fetch_transfer_data(data)
        else:
            return JsonResponse(
                {"error": "No suppliers are associated with your account. Kindly contact support for assistance."},
                status=401
            )
        final_response = {
            "status":response_data,
            "response_meta_data":{"session_break":False,"info":""}
            }
        return JsonResponse(final_response, safe=False)

class SearchLocation(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        query = self.request.query_params.get('query', "")
        city_code = self.request.query_params.get('city_code', None)
        if city_code == None:
            return JsonResponse(
                {"error": "Please select destination, before proceeding with this."},
                status=400
            )
        kwargs = {
                "query": query,
                "city_code": city_code,
            }
        user =  UserDetails.objects.filter(id=user_id ).first()
        manager = TransferManager(user)
        if manager.auth_success:
            response_data = manager.search_location(kwargs)
        else:
            return JsonResponse(
                {"error": "No suppliers are associated with your account. Kindly contact support for assistance."},
                status=401
            )
        
        # If `None` (or null list) is returned from the manager, respond with a standard error
        if response_data is None:
            return JsonResponse(
                {"error": "Unable to retrieve location details at this time."},
                status=400
            )
        elif len(response_data) == 0:
            final_response = {
            "suggections_list":response_data,
            "status":False,
            "response_meta_data":{"session_break":False,"info":"No results found."}
            }
        else:
            final_response = {
                "suggections_list":response_data,
                "status":True,
                "response_meta_data":{"session_break":False,"info":""}
            }
        # Otherwise, return the data
        return JsonResponse(final_response, safe=False)

class TransferSearchInitView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        manager = TransferManager(user)
        if manager.auth_success:
            response_data = manager.initiate_search(data)
        else:
            return JsonResponse(
                {"error": "No suppliers are associated with your account. Kindly contact support for assistance."},
                status=401
            )
        
        # If `None`  is returned from the manager, respond with a standard error
        if response_data is None:
            return JsonResponse(
                {"error": "Unable to retrieve Transfer details at this time."},
                status=400
            )
        elif len(response_data) == 0:
            final_response = {
            "status":False,
            "response_meta_data":{"session_break":False,"info":"Unable to create session. Please try again after some time."}
            }
        else:
            final_response = {
                "status":True,
                "response_meta_data":{"session_break":False,"info":""}
            } | response_data[0]
        # Otherwise, return the data
        return JsonResponse(final_response, safe=False)

class TransferSearchDataView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        session_id = data.get('session_id')
        manager = TransferManager(user)
        if manager.auth_success:
            result = manager.get_transfers_search_data(session_id)
        else:
            return JsonResponse(
                {"error": "No suppliers are associated with your account. Kindly contact support for assistance."},
                status=401
            )
        
        if result.get("session_break") == True:
            final_response = {
                "status":False,
                "response_meta_data":{"session_break":True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            }
        elif result.get("status") == False:
            final_response = {
                "status":False,
                "response_meta_data":{"session_break":False,"info":"Apologies, we are unable to retrieve Transfer details at this time."}
            }
        elif result.get("status") == True:
            if result.get("is_completed") == True:
                final_response = {
                    "transfer_list":result.get("transfer_list"),
                    "status":True,
                    "is_completed":True,
                    "is_new_data": True,
                    "response_meta_data":{"session_break":False,"info":""},
                    "search_data": result.get("search_data",{})
                }
            else:
                final_response = {
                    "transfer_list":[],
                    "status":True,
                    "is_completed":False,
                    "is_new_data": False,
                    "response_meta_data":{"session_break":False,"info":""},
                    "search_data": result.get("search_data",{})
                }
        # Otherwise, return the data
        return JsonResponse(final_response, safe=False)

class CreateBookingView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        manager = TransferManager(user)
        if manager.auth_success:
            result = manager.create_booking(data)
        else:
            return JsonResponse(
                {"error": "No suppliers are associated with your account. Kindly contact support for assistance."},
                status=401
            )
        
        if result == None:
            final_response = {
                "status":False,
                "response_meta_data":{"session_break":False,"info":"Apologies, we are unable to create Transfer booking at this time."}
            }
        elif result.get("session_break",False) == True:
            final_response = {
                "status":False,
                "response_meta_data":{"session_break":True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            }
        else:
            final_response = {
                "booking_details":result,
                "status":True,
                "response_meta_data":{"session_break":False,"info":""},
            }
        return JsonResponse(final_response, safe=False)

class PurchaseView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        manager = TransferManager(user)
        if manager.auth_success:
            result = manager.purchase_start(data)
        else:
            return JsonResponse(
                {"error": "No suppliers are associated with your account. Kindly contact support for assistance."},
                status=401
            )
        
        if result.get("session_break",False) == True:
            final_response = {
                "status":False,
                "response_meta_data":{"session_break":True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            }
        else:
            final_response = {
                "purchase_info":result,
                "status":True,
                "response_meta_data":{"session_break":False,"info":""},
            }
        return JsonResponse(final_response, safe=False)

class PurchaseStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        booking = TransferBooking.objects.filter(id = data["booking_id"]).first()
        final_response = {
            "purchase_status":booking.status,
            "status":True,
            "response_meta_data":{"session_break":False,"info":""},
        }
        return JsonResponse(final_response, safe=False)

class PurchaseDetailsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        booking = TransferBooking.objects.filter(id = data["booking_id"]).first()
        # Retrieve related one-to-one details using the ForeignKey relationships
        search_detail = booking.search_detail
        payment_detail = booking.payment_detail
        fare_detail = TransferBookingFareDetail.objects.filter(booking_id=booking).first()
        aws_bucket = os.getenv('AWS_STORAGE_BUCKET_NAME',"")
        profile_pic = "https://{}.s3.amazonaws.com/media/{}".format(aws_bucket,str(booking.user.organization.profile_picture))
        organization_details = {"support_email":booking.user.organization.support_email,"support_phone":booking.user.organization.support_phone,
                                    "profile_img_url":profile_pic,"profile_address":booking.user.organization.address,
                                    "profile_name":booking.user.organization.organization_name}
        # Get contact details (assumed to be one-to-many)
        contact_qs = TransferBookingContactDetail.objects.filter(booking_id=booking)
        contact_details = []
        for contact in contact_qs:
            contact_details.append({
                "pax_id": contact.id,
                "title": contact.title,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "pan": contact.pan,
                "contact_number": contact.contact_number,
                "age": contact.age,
                "email":contact.email,
                "country_code":contact.country_code
            })
        
        # Get location details and separate into pickup and drop
        location_qs = TransferBookingLocationDetail.objects.filter(booking_id=booking)
        pickup_location = location_qs.filter(transfer_type='pickup').first()
        drop_location = location_qs.filter(transfer_type='drop').first()
        
        location_details = {
            "pickup": {
                "name": pickup_location.name if pickup_location else None,
                "code": pickup_location.code if pickup_location else None,
                "date": pickup_location.date if pickup_location else None,
                "time": pickup_location.time if pickup_location else None,
                "city_name": pickup_location.city_name if pickup_location else None,
                "country": pickup_location.country if pickup_location else None,
                "AddressLine1": pickup_location.AddressLine1 if pickup_location else None,
                "AddressLine2": pickup_location.AddressLine2 if pickup_location else None,
                "details": pickup_location.details if pickup_location else None,
                "ZipCode": pickup_location.ZipCode if pickup_location else None,
                "type": pickup_location.type if pickup_location else None,
            },
            "drop": {
                "name": drop_location.name if drop_location else None,
                "code": drop_location.code if drop_location else None,
                "date": drop_location.date if drop_location else None,
                "time": drop_location.time if drop_location else None,
                "city_name": drop_location.city_name if drop_location else None,
                "country": drop_location.country if drop_location else None,
                "AddressLine1": drop_location.AddressLine1 if drop_location else None,
                "AddressLine2": drop_location.AddressLine2 if drop_location else None,
                "details": drop_location.details if drop_location else None,
                "ZipCode": drop_location.ZipCode if drop_location else None,
                "type": drop_location.type if drop_location else None,
            }
        }
        # Build the unified response dictionary
        response_data = {
            "booking": {
                "display_id": booking.display_id,
                "session_id": booking.session_id,
                "segment_id": booking.segment_id,
                "booking_ref_no": booking.booking_ref_no,
                "booking_id": booking.booking_id,
                "transfer_id": booking.transfer_id,
                "status": booking.status,
                "pax_data": booking.pax_data,
                "error": booking.error,
                "max_passengers": booking.max_passengers,
                "category": booking.category,
                "max_bags":booking.max_bags,
                "image_url":booking.url,
                "booking_remarks":booking.booking_remarks,
                "confirmation_number":booking.confirmation_number
            },
            "search_details": {
                "transfer_time": search_detail.transfer_time,
                "transfer_date": search_detail.transfer_date,
                "pax_count": search_detail.pax_count,
                "preferred_language": search_detail.preferred_language,
                "alternate_language": search_detail.alternate_language,
                "pickup_type": search_detail.pickup_type,
                "pickup_point_code": search_detail.pickup_point_code,
                "city_id": search_detail.city_id,
                "dropoff_type": search_detail.dropoff_type,
                "dropoff_point_code": search_detail.dropoff_point_code,
                "country_code": search_detail.country_code,
                "preferred_currency": search_detail.preferred_currency,
            },
            "payment_details": {
                "payment_type": payment_detail.payment_type,
                "status": payment_detail.status,
                "new_published_fare": payment_detail.new_published_fare,
                "new_offered_fare": payment_detail.new_offered_fare,
                "tax":fare_detail.tax
            },
            "contact_details": contact_details,
            "location_details": location_details,
            "organization_details":organization_details
        }
        return JsonResponse(response_data, safe=False)

class ProcessFailedView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        manager = TransferManager(user)
        if manager.auth_success:
            result = manager.process_failed(data)
        else:
            return JsonResponse(
                {"error": "No suppliers are associated with your account. Kindly contact support for assistance."},
                status=401
            )
        if result == None:
            final_response = {
                "info":"An internal error occured during processing. Please check back again in 5 minutes.",
                "status":False,
                "response_meta_data":{"session_break":False,"info":""},
            }
        else:
            final_response = {
                "info":result,
                "status":True,
                "response_meta_data":{"session_break":False,"info":""},
            }
        return JsonResponse(final_response, safe=False)
    
class GetCancellationChargesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        try:
            data = request.data 
            booking_id =  data.get("booking_id")
            if not booking_id:
                return JsonResponse(
                    {"error": "Booking ID is required to check cancellation charges."},
                    status=401
                )
            try:
                fare_detail = TransferBookingFareDetail.objects.get(booking_id=booking_id)
            except TransferBookingFareDetail.DoesNotExist:
                return JsonResponse(
                    {"is_cancellation_permitted": False,
                    "info":"Cancellation is not permitted for this Booking ID"},safe=False
                )
            try:
                policies = json.loads(fare_detail.cancellation_details)
            except:
                return JsonResponse(
                    {"is_cancellation_permitted": False,
                    "info":"Cancellation is not permitted for this Booking ID"},safe=False
                )
            pickup_detail = TransferBookingLocationDetail.objects.filter(
                                booking_id=booking_id, transfer_type='pickup'
                            ).first()
            if not pickup_detail:
                return JsonResponse(
                    {"is_cancellation_permitted": False,
                    "info":"Cancellation is not permitted for this Booking ID"},safe=False
                )
            travel_date = pickup_detail.date
            travel_time = pickup_detail.time
            try:
                travel_datetime = datetime.strptime(f"{travel_date} {travel_time}", "%d-%m-%Y %H%M")
            except Exception:
                return JsonResponse(
                    {"is_cancellation_permitted": False,
                    "info":"Cancellation is not permitted for this Booking ID"},safe=False
                )
            booking_amount = fare_detail.published_fare

            travel_datetime = datetime.strptime(f"{travel_date} {travel_time}", "%d-%m-%Y %H%M")
            fee = 0
            # Iterate over the cancellation policies
            for policy in policies:
                # Parse the policy period (using fromisoformat which handles ISO formatted strings)
                policy_from = datetime.fromisoformat(policy["from"])
                policy_to = datetime.fromisoformat(policy["to"])
                
                # Check if the travel datetime falls within the policy period
                if policy_from <= travel_datetime <= policy_to:
                    if policy["type"] == "percentage":
                        fee = booking_amount * (policy["value"] / 100)
                    elif policy["type"] == "flat":
                        fee = policy["value"]
                    break  # stop after applying the first matching policy


            final_response = {
                "cancellation_charge":fee,
                "is_cancellation_permitted":True,
                "published_fare":booking_amount,
            }
            return JsonResponse(final_response, safe=False)
        except Exception as e:
            return JsonResponse(
                    {"is_cancellation_permitted": False,
                    "info":"Cancellation is not permitted for this Booking ID. " + str(e)},safe=False
                )
    
class MarkCancelledView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        try:
            data = request.data 
            booking = TransferBooking.objects.filter(id = data["booking_id"]).first()
            booking.status = 'Cancelled'
            booking.save(update_fields = ["status"])
            final_response = {
                "status":True,
            }
            return JsonResponse(final_response, safe=False)
        except Exception as e:
            final_response = {
                "status":False,
                "error": str(e)
            }
            return JsonResponse(final_response, safe=False)


class GetBookingDetailsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        manager = TransferManager(user)
        if manager.auth_success:
            result = manager.get_booking_details(data)
        else:
            return JsonResponse(
                {"error": "No suppliers are associated with your account. Kindly contact support for assistance."},
                status=401
            )
        if result == None:
            final_response = {
                "info":"An internal error occured during processing. Please check back again in 5 minutes.",
                "status":False,
            }
        else:
            final_response = {
                "status":result,
            }
        return JsonResponse(final_response, safe=False)

class CheckEasyLink(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        manager = TransferManager(user)
        if manager.auth_success:
            manager.check_easy_link(data)
        else:
            return JsonResponse(
                {"error": "No suppliers are associated with your account. Kindly contact support for assistance."},
                status=401
            )

        final_response = {
                "status":True,
            }
        return JsonResponse(final_response, safe=False)