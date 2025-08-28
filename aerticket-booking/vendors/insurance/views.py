import threading,os,json
from  datetime import datetime,timezone
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from users.models import UserDetails
from .insurance_manager import InsuranceManager
from .models import InsuranceBooking,InsuranceBookingFareDetail,InsuranceBookingPaxDetail,InsuranceBookingPaymentDetail,InsuranceBookingSearchDetail
from rest_framework import status

import time
# Create your views here.
class SyncData(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user = UserDetails.objects.filter(id=user_id).first()
        insurance_manager = InsuranceManager(user)
        sync_info= self.request.data
        response_data = insurance_manager.sync_data(sync_info)

        return JsonResponse(response_data, safe=False)
    
class TravelCategories(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user = UserDetails.objects.filter(id=user_id).first()
        insurance_manager = InsuranceManager(user)
        response_data = insurance_manager.get_travel_categories()
        return JsonResponse({"data":response_data,"status":True}, safe=False)

class TravelPlans(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user = UserDetails.objects.filter(id=user_id).first()
        insurance_manager = InsuranceManager(user)
        data= self.request.data
        category_id = data.get('category_id')
        response_data = insurance_manager.get_travel_plans(category_id)
        return JsonResponse({"data":response_data,"status":True}, safe=False)

class PlanAddons(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user = UserDetails.objects.filter(id=user_id).first()
        insurance_manager = InsuranceManager(user)
        data= self.request.data
        plan_id = data.get('plan_id')
        response_data = insurance_manager.get_plan_adddons(plan_id)
        return JsonResponse({"data":response_data,"status":True}, safe=False)

class CreateBooking(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user = UserDetails.objects.filter(id=user_id).first()
        insurance_manager = InsuranceManager(user)
        data= self.request.data
        response_data = insurance_manager.create_booking(data)
        return JsonResponse({"data":response_data,"status":True}, safe=False)
    

class BookingDetailsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        booking = InsuranceBooking.objects.filter(id = data["booking_id"]).first()
        
        search_details = booking.search_detail
        print("search_details",search_details.__dict__)
        payment_details = booking.insurance_payment_details
        aws_bucket = os.getenv('AWS_STORAGE_BUCKET_NAME',"")
        profile_pic = "https://{}.s3.amazonaws.com/media/{}".format(aws_bucket,str(booking.user.organization.profile_picture))
        organization_details = {"support_email":booking.user.organization.support_email,"support_phone":booking.user.organization.support_phone,
                                    "profile_img_url":profile_pic,"profile_address":booking.user.organization.address,
                                    "profile_name":booking.user.organization.organization_name}
        # Get contact details (assumed to be one-to-many)
        pax_data = InsuranceBookingPaxDetail.objects.filter(booking_id=booking)
        fare_data =InsuranceBookingFareDetail.objects.filter(pax_id__booking_id=booking.id)
        pax_details = []

        for pax in pax_data:
            fare = fare_data.filter(pax_id = pax).first()
            fare_breakdown = json.loads(fare.fare_breakdown)
            print("fare_breakdown",fare_breakdown)
            pax_details.append({ 
                "id":pax.id,
                "title": pax.title,
                "first_name": pax.first_name,
                "last_name": pax.last_name,
                "dob": pax.dob,
                "gender": pax.gender,
                "address1":pax.address1,
                "address2":pax.address2,
                "passport":pax.passport,
                "city":pax.city,
                "district":pax.district,
                "state":pax.state,
                "pincode":pax.pincode,
                "phone_code":pax.phone_code,
                "phone_number":pax.phone_number,
                "email":pax.email,
                "nominee_name":pax.nominee_name,
                "relation":pax.relation,
                "country":pax.country.country_name if pax.country else "",
                "relation":pax.relation,
                "status":pax.status,
                "policy":pax.policy,
                "document":pax.document,
                "claimcode":pax.claimcode,
                "addons":[x.get("name") for x in pax.addons],
                "price":{ 
                    "publishedPrice": fare.published_fare,
                        "offeredPrice": fare.offered_fare,
                        "discount":  fare.organization_discount,
                        "basePrice":fare_breakdown.get('supplier_published_fare')

                }
            })
    
        dt = datetime.fromtimestamp(booking.created_at, tz=timezone.utc)
        booked_at = dt.strftime("%d-%m-%YT%H:%M:%SZ")
        
        response_data = {
            "booking": {
                "display_id": booking.display_id,
                "session_id": booking.session_id,
                "plan":booking.misc.get('plan'),
                "category":booking.misc.get('category'),
                "status": booking.status,
                "error": booking.error,
                "booking_date": booked_at
            },
            "search_details": {
                "commensing_date": search_details.commensing_date,
                "end_date":search_details.end_date,
                "duration":search_details.duration
            },
            "payment_details": {
                "payment_type": payment_details.payment_type,
                "status": payment_details.status,
                "published_fare": payment_details.new_published_fare,
                "offered_fare": payment_details.new_offered_fare,
            },
            "organization_details":organization_details,
            "passenger_details":pax_details,
        }
        return JsonResponse(response_data, safe=False)


class Purchase(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        purchase_data = request.data
        user =  UserDetails.objects.filter(id = request.user.id).first()
        insurance_manager = InsuranceManager(user)
        session_id = request.data.get('session_id')
        booking_id = purchase_data.get("booking_id")
        insurance_manager.mongo_client.searches.insert_one({"session_id":session_id,"booking_id":purchase_data.get("booking_id"),
                                                         "type":"purchase_initiated","payment_mode":purchase_data.get("payment_mode"),
                                                         "createdAt":datetime.now()})
        if purchase_data.get("payment_mode","wallet").strip().lower() == "wallet":
            wallet_thread = threading.Thread(target = insurance_manager.purchase, kwargs={'data': purchase_data,"wallet":True})
            wallet_thread.start()
            return JsonResponse({"status":True,"razorpay_url":None,"response_meta_data":{"session_break":False, "info":""}}, status = status.HTTP_201_CREATED) 
        else:
            response = insurance_manager.purchase(data = purchase_data,wallet = False)
            return JsonResponse({"status":True,"razorpay_url":response.get("payment_url"),"error":response.get("error"),"response_meta_data":{"session_break":False, "info":""}}, 
                                status = status.HTTP_201_CREATED) 

class PurchaseStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        data = request.data 
        booking = InsuranceBooking.objects.filter(id = data["booking_id"]).first()
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
    
class EndorseTicket(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated] 
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        insurance_manager = InsuranceManager(user)
        data = request.data
        
        pax_id = data.get('pax_id')
        cancellation=  insurance_manager.endorse_ticket(pax_id)
        return JsonResponse(cancellation, status=201)

class CancelTicket(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated] 
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        insurance_manager = InsuranceManager(user)
        data = request.data
        
        pax_id = data.get('pax_id')
        remarks = data.get('remarks')
        cancellation=  insurance_manager.cancel_ticket(pax_id,remarks)
        return JsonResponse(cancellation, status=201)
