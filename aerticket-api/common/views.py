import html
import requests
import threading
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import *
from rest_framework import status
from .serializers import (
    GallerySerializer,
    GalleryUpdateSerializer,
    OrganizationSerializer,
)
from django.db.models import Q
import json
from rest_framework.exceptions import ValidationError
from rest_framework.generics import RetrieveUpdateDestroyAPIView, ListAPIView
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework import filters
from rest_framework.filters import BaseFilterBackend
from pms.holiday_app.models import HolidayEnquiryHistory, HolidayEnquiry
from coreapi import Field
import time,json
from django.db.models import OuterRef, Subquery
import razorpay
from rest_framework.permissions import IsAuthenticated
from users.models import Country, Organization
from rest_framework_simplejwt.authentication import JWTAuthentication
import stripe
from users.models import OtpDetails
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
# from tools.kafka_config.config import invoke
from django.utils import timezone
from tools.integration.email_engine.main import EmailIntegerations
from tools.integration.sms_engine.main import SMSIntegerations
from integrations.notification.models import Notifications
from tools.kafka_config.config import invoke
from bookings.flight.models import (
    Booking,
    FlightBookingPaxDetails,
    FlightBookingItineraryDetails,
    FlightBookingJourneyDetails,
    FlightBookingSegmentDetails,
    FlightBookingSSRDetails
)
from django.db.models import Prefetch
from datetime import datetime
from users.models import LookupAirports
from integrations.notification.models import Notifications, NotificationIntegeration
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.db.models import Q
from users.models import Country, ErrorLog
from tools.integration.send_email_general import SmtpEngineEmail,AwsEmailEngineMail
from integrations.template.models import NotificationTemplates
import xmltodict
import xml.etree.ElementTree as ET
import pycountry
import phonenumbers
from users.models import LookupCountry,LookupAirline
from bookings.transfers.models import TransferBooking,TransferBookingContactDetail, TransferBookingLocationDetail
from bookings.buses.models import BusBooking,BusBookingPaxDetail
from hotels.models import HotelBooking,HotelBookingCustomer

class CustomPageNumberPagination(PageNumberPagination):
    def __init__(self, page_size=15, *args, **kwargs):
        self.page_size = page_size
        return super().__init__(*args, **kwargs)

    page_size_query_param = "page_size"
    max_page_size = 100

class CustomSearchFilter(filters.SearchFilter):
    search_param = "search_key"

class ModuleChoicesView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        module_choices = dict(Gallery.module_choices)
        return Response(module_choices)

class GalleryUploadView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, format=None):
        serializer = GallerySerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GalleryListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        module = request.query_params.get("module", None)
        page_size = int(request.query_params.get("page_size", 15))

        if module:
            if module not in dict(Gallery.module_choices):
                return Response(
                    {"error": "Invalid module parameter"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = Gallery.objects.filter(module=module).order_by("-created_at")
            total_data = len(queryset)
        else:
            queryset = Gallery.objects.all().order_by("-created_at")
            total_data = len(queryset)
        paginator = CustomPageNumberPagination(page_size=page_size)
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = GallerySerializer(paginated_queryset, many=True)

        data = {
            "results": serializer.data,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next_page": paginator.get_next_link(),
            "prev_page": paginator.get_previous_link(),
            "total_data": total_data,
            "page_size": page_size,
        }

        return Response(data, status=status.HTTP_200_OK)

class GalleryUpdateView(RetrieveUpdateDestroyAPIView):
    queryset = Gallery.objects.all()
    serializer_class = GallerySerializer
    lookup_field = "id"
    authentication_classes = []
    permission_classes = []
    allowed_methods = (
        "GET",
        "DELETE",
        "PATCH",
    )
    def patch(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            data = request.data.pop("url")
            serializer = GalleryUpdateSerializer(
                instance, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(
                {"detail": "Gallery item updated successfully."},
                status=status.HTTP_200_OK,
            )
        except NotFound:
            return Response({"detail": "Gallery item not found."}, status=status.HTTP_404_NOT_FOUND)
    def delete(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response(
                {"detail": "Gallery item deleted successfully."},
                status=status.HTTP_200_OK,
            )
        except NotFound:
            return Response({"detail": "Gallery item not found."}, status=status.HTTP_404_NOT_FOUND)

class HolidayEnquiryStatusFilter(BaseFilterBackend):
    def get_schema_fields(self, view):
        return [
            Field(
                name="status",
                location="query",
                required=False,
                type="string",
            ),
        ]

    def filter_queryset(self, request, queryset, view):
        status_name = request.query_params.get("status")

        if status_name:
            latest_history = (
                HolidayEnquiryHistory.objects.filter(holiday_enquiry_id=OuterRef("pk"))
                .order_by("-updated_at")
                .values("status__name")[:1]
            )

            queryset = queryset.filter(
                id__in=HolidayEnquiry.objects.filter(
                    id__in=HolidayEnquiryHistory.objects.filter(
                        status__name=status_name
                    ).values("holiday_enquiry_id")
                )
                .annotate(latest_status=Subquery(latest_history))
                .filter(latest_status=status_name)
            )

        return queryset

class DateFilter(BaseFilterBackend):

    def filter_queryset(self, request, queryset, view):
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if start_date:
            start_timestamp = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")))
            queryset = queryset.filter(created_at__gte=start_timestamp)

        if end_date:
            end_timestamp = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")))
            queryset = queryset.filter(created_at__lte=end_timestamp)

        return queryset

class HolidaySupplierFilter(BaseFilterBackend):

    def filter_queryset(self, request, queryset, view):
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if start_date:
            start_timestamp = int(time.mktime(time.strptime(start_date, "%Y-%m-%d")))
            queryset = queryset.filter(created_at__gte=start_timestamp)

        if end_date:
            end_timestamp = int(time.mktime(time.strptime(end_date, "%Y-%m-%d")))
            queryset = queryset.filter(created_at__lte=end_timestamp)

        return queryset

class HolidayEnquirySupplierFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        supplier = request.query_params.get("supplier")

        if supplier:
            queryset = queryset.filter(
                holiday_id__organization_id__organization_name=supplier
            )

        return queryset

class CountryCallingCode(APIView):
    def post(self, request):
        country_instances = LookupCountry.objects.all()
        for country_instance in country_instances:
            try:
                country = pycountry.countries.get(alpha_2=country_instance.country_code)
                if country is None:
                    continue
                calling_code = phonenumbers.country_code_for_region(country.alpha_2)
                if calling_code is None:
                    continue
                country_instance.calling_code = "+" + str(calling_code)
                country_instance.save()
            except KeyError:
                continue
        return Response(
            {"detail": "Country calling codes updated successfully."},
            status=status.HTTP_200_OK,
        )

class RazorpayPaymentLinkCreationView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        try:
            amount = request.data.get("amount")
            user_obj = request.user
            current_url = request.data.get("current_url")
            description = request.data.get("description", "razorpay")
            name = request.data.get("name")
            email = request.data.get("email")
            policy_name = request.data.get("policy_name")
            phone_number = request.data.get("phone_number")
            if not amount or not current_url:
                return Response(
                    {"error": "Amount and current_url are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            client = razorpay.Client(
                auth=("rzp_live_oNJ3QElLubofeu", "NPZH4XBKTM7xP1k0WPYUlFLZ")
            )

            response = client.payment_link.create(
                {
                    "amount": int(amount) * 100,
                    "currency": "INR",
                    "description": description,
                    "customer": {
                        "name": name,
                        "email": email,
                        "contact": phone_number,
                    },
                    "notify": {"sms": True, "email": True},
                    "reminder_enable": True,
                    "notes": {"policy_name": policy_name},
                    "callback_url": f"{current_url}status?confirmation=success&payment_method=razor_pay",
                    "callback_method": "get",
                }
            )

            session_id = response.get("id")

            return Response(
                {"response": response, "session_id": session_id},
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StripePaymentLinkCreationView(APIView):
    def post(self, request):
        country_id = request.data.get("country_id")
        amount = request.data.get("amount")
        currency = request.data.get("currency", "cad")
        description = request.data.get("description", "Payment Request")
        current_url = request.data.get("current_url")
        user = request.user

        if country_id is None or amount is None or current_url is None:
            return Response(
                {"error": "country_id, amount, and current_url are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            country = Country.objects.get(id=country_id)
            stripe.api_key = str(country.stripe_api_key).strip()

            if not stripe.api_key:
                return Response(
                    {"error": "Stripe key is not registered for this country."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            unit_amount = int(amount * 100)
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": currency,
                            "product_data": {
                                "name": description,
                            },
                            "unit_amount": unit_amount,
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=f"{current_url}status?confirmation=success&payment_method=stripe",
                cancel_url=f"{current_url}status?confirmation=failure",
            )
            session_id = session.id
            return Response(
                {"session_id": session_id, "url": session.url},
                status=status.HTTP_201_CREATED,
            )
        except Country.DoesNotExist:
            return Response(
                {"error": "Country not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class InvokeNotificationView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        event = request.data.get("event")
        number_list = request.data.get("number_list")
        email_list = request.data.get("email_list")
        data = request.data.get("data")
        try:
            self.invoke(
                event=event, number_list=number_list, email_list=email_list, data=data
            )
            return Response({"message": "Notification sent successfully."}, status=200)
        except Exception as e:
            return Response({"error": str(e)})

    def invoke(
        self, event, number_list: list = None, email_list: list = None, data: dict = {}
    ):

        notification_obj_list = Notifications.objects.filter(event__name=event)
        for notification_obj in notification_obj_list:
            if notification_obj.template.integeration_type == "email":
                email_integeration = EmailIntegerations(
                    notification_obj, email_list, data
                )  #  checking which email provider, inside this class
                email_integeration.send_email()

            if notification_obj.template.integeration_type == "sms":
                sms_integeration = SMSIntegerations(notification_obj, number_list, data)
                sms_integeration.send_sms()


class GetOrganisationListView(ListAPIView):
    queryset = Organization.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer

    #     def get_queryset(self):
    #         user = self.request.user
    #         print(user)
    #         role_name = user.role.name if user.role else None

    #         if role_name in ["super_admin", "admin", "operations", "finance"]:
    #             return Organization.objects.all()

    #         elif role_name == "sales":
    #             return Organization.objects.filter(sales_agent=user)

    #         else:
    #             return Organization.objects.filter(id=user.organization.id) if user.organization else Organization.objects.none()

    def get_queryset(self):
        user = self.request.user
        role_name = user.role.name if user.role else None

        queryset = Organization.objects.none()

        is_search_available = role_name in [
            "super_admin",
            "admin",
            "operations",
            "finance",
        ]

        search_query = self.request.query_params.get("search", "").strip()

        if is_search_available:
            if search_query:
                # Check if search query has at least 3 words
                if len(search_query.split()) < 3:
                    raise ValidationError("Search query must contain at least 3 words.")

                # Filter organizations based on the search query (e.g., name, description, etc.)
                queryset = Organization.objects.filter(name__icontains=search_query)[
                    :10
                ]
            else:
                # No search query provided, return top 10 organizations
                queryset = Organization.objects.none()
        else:
            # For roles without search permission, restrict the queryset
            if role_name == "sales":
                queryset = Organization.objects.filter(sales_agent=user)
            elif user.organization:
                queryset = Organization.objects.filter(id=user.organization.id)

        # Include is_search_available as metadata in the response
        self.extra_context = {"is_search_available": is_search_available}
        return queryset


class GetOrganisationListView(ListAPIView):
    queryset = Organization.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer

    # def get_queryset(self):
    #     user = self.request.user
    #     role_name = user.role.name if user.role else None
    #     search = self.request.query_params.get('search', '').strip()

    #     is_search_available=False

    #     response_data = {
    #         'is_search_available': is_search_available,
    #             'organizations': []
    #     }
    #     if role_name in ["super_admin", "admin", "operations", "finance","sales"]:
    #         is_search_available=True
    #         if is_search_available:
    #             if search and len(search) >= 3:
    #                 response_data['organizations'] = Organization.objects.filter(
    #                     Q(name__icontains=search) | Q(description__icontains=search)
    #                 )[:10]

    #         if role_name == "sales":
    #             response_data['organizations'] = response_data['organizations'].filter(sales_agent=user)

    #     else:
    #         if user.organization:
    #             response_data['organizations'] = Organization.objects.filter(id=user.organization.id)
    #     return Response(response_data)
    #  def get_queryset(self):
    #         user = self.request.user
    #         search = self.request.query_params.get('search', '').strip()
    #         role_name = user.role.name if user.role else None

    #         is_search_available = role_name in ["super_admin", "admin", "operations", "finance", "sales"]

    #         response_data = {
    #             'is_search_available': is_search_available,
    #             'organizations': []
    #         }

    #         if is_search_available:
    #             if search and len(search) >= 3:
    #                 response_data['organizations'] = Organization.objects.filter(
    #                     Q(name__icontains=search) | Q(description__icontains=search)
    #                 )[:10]
    #             else:
    #                 # Return all organizations if no valid search term
    #                 response_data['organizations'] = Organization.objects.all()

    #             # If the user's role is "sales", filter by the sales agent
    #             if role_name == "sales":
    #                 response_data['organizations'] = response_data['organizations'].filter(sales_agent=user)

    #         # If search is not available (when role is not in the allowed list)
    #         # Return only the organization associated with the logged-in user
    #         else:
    #             if user.organization:
    #                 response_data['organizations'] = Organization.objects.filter(id=user.organization.id)
    #             else:
    #                 response_data['organizations'] = Organization.objects.none()

    #         # Return the response data as a JSON response
    #         return Response(response_data)

    # def get_queryset(self):
    #     user = self.request.user
    #     role_name = user.role.name if user.role else None
    #     search = self.request.query_params.get('search', '').strip()

    #     is_search_available = False
    #     organizations = Organization.objects.none()

    #     if role_name in ["super_admin", "admin", "operations", "finance", "sales"]:
    #         is_search_available= True
    #         if search and len(search) >= 3:
    #             organizations = organizations.filter(
    #                 Q(organization_name__icontains=search)
    #             )
    #         if role_name == "sales":
    #             organizations = organizations.filter(
    #                                 Q(organization_name__icontains=search) | Q(sales_agent=user))

    #     else:
    #         if user.organization:
    #             organizations = organizations.filter(id=user.organization.id)
    #     print(organizations)
    #     return organizations
    # def get(self, request, *args, **kwargs):
    #         organizations = self.get_queryset()
    #         serializer = self.serializer_class(organizations, many=True)
    #         return Response(serializer.data)

    def get_queryset(self):
        user = self.request.user
        role_name = user.role.name if user.role else None
        search = self.request.query_params.get("search", "").strip()
        is_search_available = False
        organizations = Organization.objects.none()

        if role_name in ["super_admin", "admin", "operations", "finance", "sales"]:
            is_search_available = True
            if search and len(search) >= 3:

                organizations = Organization.objects.filter(
                    Q(organization_name__icontains=search)
                    | Q(easy_link_billing_code__icontains=search)
                )

                if role_name == "sales":
                    organizations = organizations.filter(
                        Q(organization_name__icontains=search) & Q(sales_agent=user)
                        | Q(easy_link_billing_code__icontains=search)
                    )
            organizations = organizations[:10]

        else:
            if user.organization:
                organizations = Organization.objects.filter(id=user.organization.id)

        # Print organizations for debugging purposes

        # Assign the final value of is_search_available based on whether the search term is valid
        self.is_search_available = is_search_available
        return organizations

    def get(self, request, *args, **kwargs):
        organizations = self.get_queryset()
        serializer = self.serializer_class(organizations, many=True)
        response_data = {
            "is_search_available": self.is_search_available,
            "result": serializer.data,
        }
        return Response(response_data)

class InvokeEventNotificationView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        cancellation_reason = request.data.get("cancellation_reason")
        remarks = request.data.get("remarks")
        event = request.data.get("event")
        booking_reference_id = request.data.get("booking_id")
        booking = Booking.objects.filter(display_id=booking_reference_id).first()
        if not booking:
            return Response(
                {"error": "Booking not found for the provided booking_id."},
                status=status.HTTP_200_OK,
            )
        booking_id = booking.id
        details = FlightBookingPaxDetails.objects.filter(booking_id=booking_id)
        if event != "Flight_Booking_Failed":
            pax_ids = list(details.values_list('id', flat=True))
            list_pax_names = list(details.values_list('first_name', flat=True))
            pax_names  = ','.join(name for name in list_pax_names if name)       
        else:
            from collections import defaultdict
            meals_ssr_entries = FlightBookingSSRDetails.objects.filter(
                pax__booking_id=booking_id
            ).values('pax__first_name', 'meals_ssr')

            # Group meals by pax first name
            pax_meals_map = defaultdict(list)

            for entry in meals_ssr_entries:
                first_name = entry['pax__first_name']
                meals_ssr_json = entry['meals_ssr']
                try:
                    meals_data = json.loads(meals_ssr_json) if isinstance(meals_ssr_json, str) else meals_ssr_json
                    for segment_key, segment_info in meals_data.items():
                        description = segment_info.get('Description')
                        if description:
                            pax_meals_map[first_name].append(f"{description}({segment_key})")
                except (json.JSONDecodeError, TypeError):
                    continue 
            final_output = [
                f"{pax} - {', '.join(descriptions)}"
                for pax, descriptions in pax_meals_map.items()
            ]
            meal_info = ", ".join(final_output)
            pax_names = ', '.join(
            f"{pax.first_name} ({pax.gender})" if pax.pax_type.lower() != 'adults' and pax.gender else pax.first_name
            for pax in details if pax.first_name)
        request_date = self.epoch_to_custom_format(time.time())
        flight_segments = self.flight_Segment(booking_id)
        pax_details = self.pax_details(booking_id)
        journey_details = FlightBookingJourneyDetails.objects.select_related('itinerary','booking').filter(booking__display_id=booking_reference_id).values(
                'itinerary__itinerary_key', "itinerary__hold_till","itinerary__status",
                'source','date','destination','booking__display_id'                    
            )
        
        source_list = [journey['source'] for journey in journey_details]
        sources  = ','.join(source for source in source_list if source)
        destination_list =  [journey['destination'] for journey in journey_details]
        destinations  = ','.join(destination if destination else None for destination in destination_list)
        travel_date_list =  list(set([journey['date'] for journey in journey_details]))
        travel_dates  = ','.join(date for date in travel_date_list if date)
        organization = request.user.organization
        sales_team_mail = (
            organization.sales_agent.email if organization.sales_agent else None
        )
        email = [request.user.email]
        email.append(sales_team_mail)
        user_contact = json.loads(booking.contact)
        user_email = user_contact.get("email","")
        country_name = request.user.organization.organization_country.lookup.country_name
        segment_Details = FlightBookingSegmentDetails.objects.filter(journey__itinerary__booking = booking_id).first()
        itinerary_details = FlightBookingItineraryDetails.objects.filter(booking=booking_id)
        for itinerary in itinerary_details:
            gds_pnr = (itinerary.gds_pnr,)
            airline_pnr = itinerary.airline_pnr
            error = itinerary.error
        if event == "Ticket_Confirmation":
            is_queue = request.data.get('is_queue')
            if is_queue:
                email = [sales_team_mail]
            thread = threading.Thread(target=invoke, kwargs={
                                            "event":"Ticket_Confirmation",
                                            "number_list":[], 
                                            "email_list":email,
                                            "data" :{
                                            "customer_name": pax_names,
                                            "passenger_name": pax_names,
                                            "booking_reference": booking_reference_id,
                                            "travel_date": request_date,
                                            "flight_details": flight_segments,
                                            "agent_support_email": request.user.email,
                                            "agent_name": request.user.organization.organization_name,
                                            "country_name": country_name,
                                            "user_email": user_email,
                                            "sales_agent_email": sales_team_mail,
                                            "agent_email": request.user.organization.support_email
                                            }
                                            })
            thread.start()
        elif event == "Flight_Booking_Failed":
            print({
                    "event":"Flight_Booking_Failed",
                    "number_list":[], 
                    "email_list":["arjun@elkanio.com"],
                    "data" :{
                    "agent_name": request.user.organization.organization_name,
                    "booking_reference": booking_reference_id,
                    "passenger_name": pax_names,
                    "travel_date": travel_dates,
                    "origin": sources,
                    "destination": destinations,
                    "country_name": country_name,
                    "error":error,
                    "user_email":request.user.email,
                    "user_phone":request.user.phone_number
                }
                    })
            thread = threading.Thread(target=invoke, kwargs={
                                            "event":"Flight_Booking_Failed",
                                            "number_list":[], 
                                            "email_list":["arjun@elkanio.com"],
                                            "data" :{
                                            "agent_name": request.user.organization.organization_name,
                                            "booking_reference": booking_reference_id,
                                            "passenger_name": pax_names,
                                            "travel_date": travel_dates,
                                            "origin": sources,
                                            "destination": destinations,
                                            "country_name": country_name,
                                            "error":error,
                                            "user_email":request.user.email,
                                            "user_phone":request.user.phone_number
                                        }
                                            })
            thread.start()
        elif event == "Modification_OR_Reissue":
            segment_Details = FlightBookingSegmentDetails.objects.filter(
                journey__itinerary__booking=booking_id
            ).first()
            thread = threading.Thread(target=invoke, kwargs={
                                "event":"Modification_OR_Reissue",
                                "number_list":[], 
                                "email_list":email,
                                "data" :{
                                    "Agent Name/Travel Agent Team": request.user.organization.organization_name,
                                    "Insert Name(s)": pax_names,
                                    "Insert Phone Number": request.user.phone_number,
                                    "Insert Email Address": request.user.email,
                                    "Insert PNR": airline_pnr,
                                    "Insert Airline Name": segment_Details.airline_name,
                                    "Insert Flight Number": segment_Details.flight_number,
                                    "Insert Date & Time": request_date,
                                    "Remarks": remarks,
                                    "country_name": country_name,
                                    "request_date": request_date,
                                    "booking_reference": booking_reference_id,
                                    "passenger_list": "pax_detail",
                                    "cancellation_reason": cancellation_reason,
                                    "flight_segments": flight_segments,
                                    "user_email": request.user.email,
                                }
                                })
            thread.start()
        elif event == "Hold_Booking_Success":
            thread = threading.Thread(target=invoke, kwargs={
                                "event":"Hold_Booking_Success",
                                "number_list":[], 
                                "email_list":email,
                                "data" :{
                                "agent_name": request.user.organization.organization_name,
                                "passenger_name": pax_names,
                                "booking_reference": booking_reference_id,
                                "travel_date": request_date,
                                "origin": segment_Details.origin,
                                "destination": segment_Details.destination,
                                "passenger_list": "pax_detail",
                                "cancellation_reason": cancellation_reason,
                                "flight_segments": flight_segments,
                                "country_name": country_name,
                                "user_email": user_email,
                            }
                                })
            thread.start()
        elif event == "Flight_Cancelation":
            cancellation_reason = request.data.get("cancellation_reason")
            thread = threading.Thread(target=invoke, kwargs={
                                "event":"Flight_Cancelation",
                                "number_list":[], 
                                "email_list":email,
                                "data" :{
                                    "request_date": request_date,
                                    "booking_reference": booking_reference_id,
                                    "passenger_list": pax_details,
                                    "cancellation_reason": cancellation_reason,
                                    "flight_segments": flight_segments,
                                    "country_name": country_name,
                                    "user_email": user_email,
                                }
                                })
            thread.start()
        return Response({"message": "Notification sent successfully."}, status=200)

    def pax_details(self, booking_id):
        pax_details = FlightBookingPaxDetails.objects.filter(booking_id=booking_id)
        return "".join(
            f"""<tr>
                        <td>{i+1}</td>
                        <td>{v.first_name} {v.last_name}</td>
                        <td>{v.pax_type}</td>
                        </tr>"""
            for i, v in enumerate(pax_details)
        )

    def epoch_to_custom_format(self, epoch_time):
        date_time = datetime.fromtimestamp(epoch_time)
        day = date_time.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]
        return date_time.strftime(f"%b {day}{suffix} %Y %I:%M %p")

    def get_airport_name_from_code(self, code: str):
        try:
            airport_name = LookupAirports.objects.get(code=code).name
        except LookupAirports.DoesNotExist:
            return code
        return airport_name

    def get_airport_city_from_code(self, code: str):
        try:
            airport_name = LookupAirports.objects.get(code=code).city
        except LookupAirports.DoesNotExist:
            return code
        return airport_name

    def get_country_code_from_code(self, code: str):
        try:
            airport_name = LookupAirports.objects.get(code=code).country.country_code
        except LookupAirports.DoesNotExist:
            return code
        return airport_name

    def flight_Segment(self, booking_id):
        itinerary_details = FlightBookingItineraryDetails.objects.filter(
            booking=booking_id
        ).prefetch_related(
            Prefetch(
                "flightbookingjourneydetails_set",
                queryset=FlightBookingJourneyDetails.objects.all().prefetch_related(
                    Prefetch(
                        "flightbookingsegmentdetails_set",
                        queryset=FlightBookingSegmentDetails.objects.all(),
                    )
                ),
                to_attr="journeys",
            )
        )
        flight_segment = """<table style="border-collapse: collapse; width: 100%;">"""
        for itinerary in itinerary_details:
            for journey in itinerary.journeys:
                flight_segment += self.html_block_2_origin_destination(
                    from_origin=journey.source,
                    to_destination=journey.destination,
                    epoc_time=journey.timestamp,
                    gds_pnr=itinerary.gds_pnr,
                    airline_pnr=itinerary.airline_pnr,
                )
                for segment in journey.flightbookingsegmentdetails_set.all():
                    flight_segment += self.html_block_3_segment_details(
                        airline_name=segment.airline_name,
                        airline_code=segment.airline_code,
                        origin=segment.origin,
                        timestamp=segment.timestamp,
                        departure_datetime=segment.departure_datetime,
                        arrival_datetime=segment.arrival_datetime,
                        destination=segment.destination,
                        duration=segment.duration,
                    )
        flight_segment += "</table>"
        return flight_segment

    def html_block_2_origin_destination(
        self, from_origin, to_destination, epoc_time, gds_pnr, airline_pnr
    ):

        body = f"""
            <tr>         
                <th colspan="4" style=" border: 1px solid black; padding: 8px; text-align: left; background-color: #f2f2f2;">
                {self.get_airport_name_from_code(from_origin)}-({from_origin}) → {self.get_airport_name_from_code(to_destination)}-({to_destination}) 
                </th>
                <th colspan="1" style="width: 16.66%; border: 1px solid black; padding: 8px; text-align: left; background-color: #f2f2f2;">Airline PNR</th>
                <th colspan="1" style="width: 16.66%; border: 1px solid black; padding: 8px; text-align: left; background-color: #f2f2f2;">GDS PNR</th>
            </tr>
            <tr>
                <td colspan="4" style="border: 1px solid black; padding: 8px; text-align: left;"></td>
                <td colspan="1" style="width: 16.66%; border: 1px solid black; padding: 8px; text-align: left;">{airline_pnr}</td>
                <td colspan="1" style="width: 16.66%; border: 1px solid black; padding: 8px; text-align: left;">{gds_pnr}</td>
            </tr>
        """
        return body

    def html_block_3_segment_details(
        self,
        airline_name,
        airline_code,
        origin,
        timestamp,
        departure_datetime,
        arrival_datetime,
        destination,
        duration,
    ):
        body = f"""
                <tr>
                    <td style="width: 16.66%; border: 1px solid black; padding: 8px; text-align: left;">
                        <strong>{airline_name}</strong><br> {airline_code}
                    </td>
                    <td colspan="2" style="border: 1px solid black; padding: 8px; text-align: left;">
                        <p style="margin:0px;">{self.epoch_to_custom_format(departure_datetime)}</p>
                        <p style="margin:0px;">{self.get_airport_city_from_code(origin)}, {self.get_country_code_from_code(origin)}</p>
                        <p style="margin:0px;">{self.get_airport_name_from_code(origin)}</p>
                    </td>
                    <td colspan="2" style=" border: 1px solid black; padding: 8px; text-align: left;">
                        <p style="margin:0px;">{self.epoch_to_custom_format(arrival_datetime)}</p>
                        <p style="margin:0px;">{self.get_airport_city_from_code(destination)},
                            {self.get_country_code_from_code(destination)}</p>
                        <p style="margin:0px;">{self.get_airport_name_from_code(destination)}</p>
                    </td>
                    <td style="width: 16.66%; border: 1px solid black; padding: 8px; text-align: left;">
                        <p style="margin:0px;">{ str(round(int(duration) / 60, 2)).split(".")[0] + "hr " + str(round(int(duration) / 60,
                            2)).split(".")[1] + "min"}</p>
                    </td>
                           
                </tr>
                """
        return body

    def passenger_block(self, title, first_name, last_name, gender, passport):
        return f""" 
                                            <tr>
                                                <td
                                                    style="border-bottom:1px #e5e5e5 solid; border-right:1px #e5e5e5 solid; font-weight:bold; padding:5px;">
                                                    1</td>
                                                <td
                                                    style="border-bottom:1px #e5e5e5 solid; border-right:1px #e5e5e5 solid;  padding:5px;">
                                                    <strong>{title} {first_name} {last_name} ( A )</strong> 30/05/1958, PP :
                                                    {passport} , N : IN , ID : 14/02/2023 , ED : 13/02/2033 ,
                                                </td>
                                                <td
                                                    style="border-bottom:1px #e5e5e5 solid; border-right:1px #e5e5e5 solid;  padding:5px;">
                                                    5142360279553
                                                </td>
                                                <td style="border-bottom:1px #e5e5e5 solid; padding:5px;">
                                                    <table width="100%" border="0" cellspacing="0" cellpadding="0">
                                                        <tr>
                                                            <td><img src="images/Meal.png" width="18"></td>
                                                            <td>- 1 Meal</td>
                                                            <td><img src="images/bggage-icon.jpg" width="15"
                                                                    height="14"></td>
                                                            <td>- 20 Kg 1 Piece</td>
                                                        </tr>
                                                        <tr>
                                                            <td><img src="images/seat.png" width="18"></td>
                                                            <td>- 1 Seat(E5)</td>
                                                            <td>&nbsp;</td>
                                                            <td>&nbsp;</td>
                                                        </tr>
                                                    </table>
                                                </td>
                                            </tr>
                                          

    """

class ShareFareView(APIView):
    def post(self, request):
        try:
            email_list = request.data.get('to_email')
            data = request.data.get('data')
            subject = request.data.get('subject')
            if not subject or not data or not email_list:
                return Response({"error": "Missing required parameters."}, status=status.HTTP_400_BAD_REQUEST)

            country_instance = request.user.base_country
            try:
                country_name = Country.objects.get(lookup__country_name__icontains=country_instance)
            except Country.DoesNotExist:
                return Response({"error": "Base country not found."}, status=status.HTTP_404_NOT_FOUND)

            not_obj = NotificationTemplates.objects.filter(name__icontains="Share_Fare").update(
                heading=subject,
                body=data
            )
            notification = NotificationTemplates.objects.filter(name__icontains="Share_Fare").first()
            if notification:
                thread = threading.Thread(target=invoke, kwargs={
                            "event":"Share_Fare", 
                            "email_list":[email_list],
                            "data" :{"country_name":country_name}
                            })
                thread.start()
            else:
                return Response({"error": "Notification template not found."}, status=status.HTTP_404_NOT_FOUND)
            return Response({"message": "Email notification sent successfully."}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)

class VirtualAccountTranslationAPI(APIView):
    permission_classes = []
    def post(self, request):
        data = request.data.get('GenericCorporateAlertRequest', [])
        try:
            if isinstance(data, dict):
                data = [data]
            records = []
            for instance in data:
                virtual_account = instance.get('Virtual Account', '')
                if virtual_account:
                    virtual_account = virtual_account.upper()
                virtual_account_code = virtual_account[6:]
                virtual_easy_link_billing_code ="{}-{}".format(virtual_account_code[:2],virtual_account_code[2:])

                organization_obj = Organization.objects.filter(easy_link_billing_code = virtual_easy_link_billing_code).first()
                record = VirtualAccountTransaction(
                    alert_sequence_no=instance.get('Alert Sequence No', ''),
                    virtual_account=virtual_account,
                    account_number=instance.get('Account number', ''),
                    debit_credit=instance.get('Debit Credit', ''),
                    amount=instance.get('Amount', ''),
                    remitter_name=instance.get('Remitter Name', ''),
                    remitter_account=instance.get('Remitter Account', ''),
                    remitter_bank=instance.get('Remitter Bank', ''),
                    remitter_IFSC=instance.get('Remitter IFSC', ''),
                    cheque_no=instance.get('Cheque No', ''),
                    user_reference_number=instance.get('User Reference Number', ''),
                    mnemonic_code=instance.get('Mnemonic Code', ''),
                    value_date=instance.get('Value Date', ''),
                    transaction_description=instance.get('Transaction Description', ''),
                    transaction_date=instance.get('Transaction Date', ''),
                    organization = organization_obj if organization_obj else None
                )
                if VirtualAccountTransaction.objects.filter(alert_sequence_no=record.alert_sequence_no).exists():
                    return Response({
                        "GenericCorporateAlertResponse": {
                            "errorCode": "0",
                            "errorMessage": "Duplicate",
                            "domainReferenceNo": record.alert_sequence_no
                        }
                    })
                records.append(record)
            VirtualAccountTransaction.objects.bulk_create(records)
            alert_sequence_no = records[-1].alert_sequence_no if records else ''
            for record in records:
                data = {
                    "amount":record.amount,
                    "organization": record.organization,
                    "remitter_name":record.remitter_name,
                    "user_reference_number":record.user_reference_number,
                    "transaction_date":record.transaction_date,

                    "remitter_account":record.remitter_account,
                    "remitter_bank":record.remitter_bank,
                    "remitter_IFSC":record.remitter_IFSC,
                    "cheque_no":record.cheque_no,
                    "mnemonic_code":record.mnemonic_code,
                    "value_date":record.value_date,
                    "transaction_description":record.transaction_description,
                    "record":record
                }
                VirtualAccountTranslationEasyLinkCreationAPI(**data)
            return Response({
                "GenericCorporateAlertResponse": {
                    "errorCode": "0",
                    "errorMessage": "Success",
                    "domainReferenceNo": alert_sequence_no
                }
            })

        except Exception as e:
            return Response({"error": str(e)})

def VirtualAccountTranslationEasyLinkCreationAPI(**kwargs):
    organization = kwargs.get('organization')
    amount = kwargs.get('amount')
    easy_link_billing_obj = organization.easy_link_billing_account
    pax_name = kwargs.get('remitter_name')
    payment_id = kwargs.get('user_reference_number')

    remitter_account= kwargs.get('remitter_account')
    remitter_bank= kwargs.get('remitter_bank')
    remitter_IFSC= kwargs.get('remitter_IFSC')
    cheque_no= kwargs.get('cheque_no')
    mnemonic_code= kwargs.get('mnemonic_code')
    value_date= kwargs.get('value_date')
    transaction_description= kwargs.get('transaction_description')
    NR2 = f'{remitter_account=}remitter_account , {remitter_bank=}remitter_bank'
    NR3=f"{remitter_IFSC=}remitter_IFSC,{cheque_no=}cheque_no" 
    NR4 = f"{mnemonic_code=}mnemonic_code,{value_date=}value_date,{transaction_description=}transaction_description"
    record = kwargs.get('record')
    result = {}
    if easy_link_billing_obj:
        for item in easy_link_billing_obj.data:
            result.update(item)
    base_url = result.get('url')
    branch_code = result.get('branch_code')
    portal_reference_code = result.get('portal_reference_code')

    account_code  = organization.easy_link_billing_code
    txndate = kwargs.get('transaction_date')
    date_format = datetime.strptime(txndate, "%Y-%m-%d %H:%M")
    formated_txndate = date_format.strftime('%d/%m/%Y')
    # today_date= "04/12/2024"
    if base_url :
        full_url = f"{base_url}/GenerateAutoTxn?sBrCode={branch_code}&PortalRefCode={portal_reference_code}&sTxnType=027"
    #-----------------end---------------------------
    headers = {}
    payload = f"""<TxnData>\n    <Txn txnDt=\"{formated_txndate}\" CustCode=\"{account_code}\" credittype=\"F\" BankCode=\"A0328\" PaxName=\"{pax_name}\" TxnRefNo=\"{payment_id}\" NR1=\"Online Recharge from Portal \" NR2=\"{NR2}\" NR3=\"{NR3}\" NR4=\"{NR4}\" TxnAmount=\"{amount}\"></Txn>\n</TxnData>"""
    response = requests.request("POST", full_url, headers=headers, data=payload)
    text = response.text
    text_result = xmltodict.parse(text)
    xml_data = text_result['string']['#text']
    root = ET.fromstring(xml_data)
    status = root.find('txn').attrib.get('Status')
    if status =="True":
        record.easylink_status = True
        record.save()
    else:
        decoded_xml = html.unescape(response.text)
        ErrorLog.objects.create(module="generate_auto_trx",erros={"response":str(decoded_xml)})


class InvokeEventNotificationTransferView(APIView):
    def post(self, request):
        cancellation_reason = request.data.get("cancellation_reason")
        remarks = request.data.get("remarks")
        event = request.data.get("event")
        booking_reference_id = request.data.get("booking_id")
        booking = TransferBooking.objects.filter(display_id=booking_reference_id).first()
        if not booking:
            return Response(
                {"error": "Booking not found for the provided booking_id."},
                status=status.HTTP_200_OK,
            )
        booking_id = booking.id
        booking_date = datetime.fromtimestamp(booking.created_at).strftime("%Y-%m-%d: %H%M%S")

        pickup_details = TransferBookingLocationDetail.objects.filter(booking = booking, transfer_type= 'pickup')
        drop_details = TransferBookingLocationDetail.objects.filter(booking = booking, transfer_type= 'drop')
        pick_up = pickup_details[0].name if pickup_details else None
        drop_off = drop_details[0].name if drop_details else None
        pick_city = pickup_details[0].city_name if pickup_details else None
        drop_off_city = drop_details[0].city_name if drop_details else None
        email = [request.user.email]
        email.append(booking.user.email)
        user_email = booking.user.email
        country_name = request.user.organization.organization_country.lookup.country_name
        # country_name = "India"
        phone_number = booking.user.phone_number
        name = booking.user.first_name
        pax_count = booking.search_detail.pax_count
        if event == "Transfer_Confirmation":
            thread = threading.Thread(target=invoke, kwargs={
                                            "event":"Transfer_Confirmation",
                                            "number_list":[], 
                                            "email_list":email,
                                            "data" :{
                                            "country_name": country_name,
                                            "user_email": user_email,
                                            "booking_id": booking_id,
                                            "booking_date": booking_date,
                                            "name": name,
                                            "pax_count": pax_count,
                                            "phone_number": phone_number,
                                            "pick_up": pick_up,
                                            "drop_off": drop_off,
                                            "pick_city": pick_city,
                                            "drop_off_city": drop_off_city
                                            }
                                            })
            thread.start()
        elif event == "Transfer_Under_Process":
            thread = threading.Thread(target=invoke, kwargs={
                                            "event":"Transfer_Under_Process",
                                            "number_list":[], 
                                            "email_list":email,
                                             "data" :{
                                            "country_name": country_name,
                                            "user_email": user_email,
                                            "booking_id": booking_id,
                                            "booking_date": booking_date,
                                            "name": name,
                                            "pax_count": pax_count,
                                            "phone_number": phone_number,
                                            "pick_up": pick_up,
                                            "drop_off": drop_off,
                                            "pick_city": pick_city,
                                            "drop_off_city": drop_off_city
                                            }
                                            })
            thread.start()
        elif event == "Transfer_Cancellation_Request_Received":
            thread = threading.Thread(target=invoke, kwargs={
                                            "event":"Transfer_Cancellation_Request_Received",
                                            "number_list":[], 
                                            "email_list":email,
                                             "data" :{
                                            "country_name": country_name,
                                            "user_email": user_email,
                                            "booking_id": booking_id,
                                            "booking_date": booking_date,
                                            "name": name,
                                            "pax_count": pax_count,
                                            "phone_number": phone_number,
                                            "pick_up": pick_up,
                                            "drop_off": drop_off,
                                            "pick_city": pick_city,
                                            "drop_off_city": drop_off_city
                                            }
                                            })
            thread.start()
        return Response({"message": "Notification sent successfully."}, status=200)

class InvokeEventNotificationBusView(APIView):
    def post(self, request):
        try:
            cancellation_reason = request.data.get("cancellation_reason")
            remarks = request.data.get("remarks")
            event = request.data.get("event")
            booking_reference_id = request.data.get("booking_id")
            booking = BusBooking.objects.filter(id=booking_reference_id).first()
            if not booking:
                return Response(
                    {"error": "Booking not found for the provided booking_id."},
                    status=status.HTTP_200_OK,
                )
            booking_id = booking.id
            booking_date = datetime.fromtimestamp(booking.created_at).strftime("%Y-%m-%d: %H%M%S")
            contact = json.loads(booking.contact)

            cus_email = contact.get('email')
            cus_phone = contact.get('phone')
            email = [request.user.email]
            email.append(booking.user.email)
            if cus_email:
                email.append(cus_email)
            user_email = booking.user.email

            phone_number = cus_phone
            name = booking.user.first_name
            pax_count = booking.pax_count
            operator = booking.operator
            departure_location = booking.search_detail.origin.city_name
            destination = booking.search_detail.destination.city_name
            departure_time = booking.departure_time
            seat_numbers = list(BusBookingPaxDetail.objects.filter(booking_id = booking_id).values_list('seat_id', flat=True))
            seat_nos = ','.join(seat_numbers)

            country_name = request.user.organization.organization_country.lookup.country_name

            if event == "Bus_Confirmation":
                thread = threading.Thread(target=invoke, kwargs={
                                                "event":"Bus_Confirmation",
                                                "number_list":[], 
                                                "email_list" : email,
                                                "data" :{
                                                "country_name": country_name,
                                                "user_email": user_email,
                                                "booking_id": booking_id,
                                                "booking_date": booking_date,
                                                "name": name,
                                                "pax_count": pax_count,
                                                "phone_number": phone_number,
                                                "bus_operator":operator,
                                                "departure_location":departure_location,
                                                "destination":destination,
                                                "departure_date_time":departure_time,
                                                "seat_numbers":seat_nos
                                                }
                                                })
                thread.start()
            elif event == "Bus_Under_Process":
                thread = threading.Thread(target=invoke, kwargs={
                                                "event":"Bus_Under_Process",
                                                "number_list":[], 
                                                "email_list":email,
                                                "data" :{
                                                "country_name": country_name,
                                                "user_email": user_email,
                                                "booking_id": booking_id,
                                                "booking_date": booking_date,
                                                "name": name,
                                                "pax_count": pax_count,
                                                "phone_number": phone_number,
                                                "bus_operator":operator,
                                                "departure_location":departure_location,
                                                "destination":destination,
                                                "departure_date_time":departure_time,
                                                "seat_numbers":seat_nos
                                                }
                                                })
                thread.start()

            elif event == "Bus_Cancellation":
                thread = threading.Thread(target=invoke, kwargs={
                                                "event":"Bus_Cancellation",
                                                "number_list":[], 
                                                "email_list":email,
                                                "data" :{
                                                "country_name": country_name,
                                                "user_email": user_email,
                                                "booking_id": booking_id,
                                                "booking_date": booking_date,
                                                "name": name,
                                                "pax_count": pax_count,
                                                "phone_number": phone_number,
                                                "bus_operator":operator,
                                                "departure_location":departure_location,
                                                "destination":destination,
                                                "departure_date_time":departure_time,
                                                "seat_numbers":seat_nos
                                                }
                                                })
                thread.start()
            return Response({"message": "Notification sent successfully."}, status=200)
        except Exception as e:
            return Response({"error": str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InvokeEventNotificationHotelView(APIView):
    def post(self, request):
        try:
            cancellation_reason = request.data.get("cancellation_reason",None)
            remarks = request.data.get("remarks",None)
            event = request.data.get("event")
            booking_reference_id = request.data.get("booking_id")
            booking = HotelBooking.objects.filter(id=booking_reference_id).first()
            if not booking:
                return Response(
                    {"error": "Booking not found for the provided booking_id."},
                    status=status.HTTP_200_OK,
                )
            booking_id = booking.id
            booking_date = datetime.fromtimestamp(booking.created_at).strftime("%Y-%m-%d: %H%M%S")
            customer_details = HotelBookingCustomer.objects.filter(booking = booking).first()
            customer_email = customer_details.email
            email = [request.user.email]
            email.append(booking.created_by.email)
            if customer_email:
                email.append(customer_email)
            user_email = booking.created_by.email

            name = booking.created_by.first_name
            hotel_name = booking.hotel.hotel_code
            check_in_date = booking.check_in
            check_out_date = booking.check_out
            country_name = request.user.organization.organization_country.lookup.country_name
            confirmed = booking.status

            if event == "Hotel_Confirmation":
                thread = threading.Thread(target=invoke, kwargs={
                                                "event":"Hotel_Confirmation",
                                                "number_list":[], 
                                                "email_list" : email,
                                                "data" :{
                                                "country_name": country_name,
                                                "user_email": user_email,
                                                "booking_id": booking_id,
                                                "booking_date": booking_date,
                                                "name": name,
                                                "hotel_name": hotel_name,
                                                "check_in_date": check_in_date,
                                                "check_out_date":check_out_date,
                                                "room_type":"room_type",
                                                "confirmed":confirmed
                                                }
                                                })
                thread.start()
            elif event == "Hotel_Under_Process":
                thread = threading.Thread(target=invoke, kwargs={
                                                "event":"Hotel_Under_Process",
                                                "number_list":[], 
                                                "email_list":email,
                                                "data" :{
                                                "country_name": country_name,
                                                "user_email": user_email,
                                                "booking_id": booking_id,
                                                "booking_date": booking_date,
                                                "name": name,
                                                "hotel_name": hotel_name,
                                                "check_in_date": check_in_date,
                                                "check_out_date":check_out_date,
                                                "room_type":"room_type",
                                                "confirmed":confirmed
                                                }
                                                })
                thread.start()

            elif event == "Hotel_Cancellation_Request_Received":
                thread = threading.Thread(target=invoke, kwargs={
                                                "event":"Hotel_Cancellation_Request_Received",
                                                "number_list":[], 
                                                "email_list":email,
                                                "data" :{
                                                "country_name": country_name,
                                                "user_email": user_email,
                                                "booking_id": booking_id,
                                                "booking_date": booking_date,
                                                "name": name,
                                                "hotel_name": hotel_name,
                                                "check_in_date": check_in_date,
                                                "check_out_date":check_out_date,
                                                "room_type":"room_type",
                                                "confirmed":confirmed
                                                }
                                                })
                thread.start()
            return Response({"message": "Notification sent successfully."}, status=200)
        except Exception as e:
            return Response({"error": str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

