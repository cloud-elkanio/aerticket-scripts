from django.shortcuts import render
from .models import *
from rest_framework import viewsets
from .serializers import BookingSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.db.models import Q,F
from users.models import LookupAirports
from .serializers import *
import json
from django.db.models import Prefetch
from django.db.models import OuterRef, Subquery
from tools.kafka_config.config import invoke
import requests
from collections import deque
from users.models import Organization
from bs4 import BeautifulSoup
from django.db.models import Prefetch
from datetime import datetime, timedelta
from rest_framework.pagination import PageNumberPagination
from django.db.models import F, Window
from django.db.models.functions import RowNumber   
import pytz
import pandas as pd
class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    authentication_classes = [JWTAuthentication] 
    permission_classes = [IsAuthenticated] 

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        partial = True  
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

class CustomPageNumberPagination(PageNumberPagination):
    def __init__(self, page_size=15, *args, **kwargs):
        self.page_size=page_size
        return super().__init__(*args,**kwargs)
    page_size_query_param = 'page_size'
    max_page_size = 100

from django.db.models import Count

class FlightBookingQueue(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self,request):
        page_size = int(request.query_params.get('page_size', 15))
        search =  request.query_params.get('search', None)
        from_date = request.query_params.get('from_date', None)
        to_date = request.query_params.get('to_date', None)
        search_type = request.query_params.get('search_type', None)
        booking_status = request.query_params.get('booking_status', None)
        country_name = request.query_params.get('country_name', None)
        filter_condition = Q()
        if from_date and to_date and not (search and search_type in ['booking_id', 'pnr']):
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d")
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            from_date_epoch = int(from_date_obj.timestamp())
            to_date_epoch = int(to_date_obj.timestamp())
            filter_condition &= Q(booked_at__range=[from_date_epoch,to_date_epoch])
        if booking_status == "Confirmed":
            filter_condition &= Q(flightbookingitinerarydetails__status__in=["Confirmed", "Rejected","Failed-Confirmed",
                                                                             "Failed-Rejected","Cancel-Ticket-Failed"])
        elif booking_status == "failed":
            filter_condition &= (Q(flightbookingitinerarydetails__status="Ticketing-Failed")|  
                                Q(flightbookingitinerarydetails__status="Hold-Failed"))                           
        elif booking_status == "cancelled":
            filter_condition &= (Q(flightbookingitinerarydetails__status="Hold-Released")|
                                  Q(flightbookingitinerarydetails__status="Ticket-Released")
                                  )
        elif booking_status == "on-hold":
             filter_condition &= (Q(flightbookingitinerarydetails__status__in=["On-Hold","Release-Hold-Failed"])
                                  )
        elif booking_status == "all":
            all_status = FlightBookingItineraryDetails.objects.values_list('status', flat=True).distinct()
            filter_condition &= Q(flightbookingitinerarydetails__status__in = list(all_status))
        else:
            filter_condition &= Q(flightbookingitinerarydetails__status__in=["Enquiry", "Ticketing-Initiated","Hold-Initiated",
                                                                             "Hold-Unavailable"])
                                
        current_user_organization = self.get_current_organization(request.user)
        if country_name:
            filter_condition &= Q(user__organization__organization_country__lookup__country_name=country_name)    
        if search_type:
            if search_type == 'Online':
                filter_condition &= Q(flightbookingitinerarydetails__booking__source="Online")
            elif search_type == 'Offline':
                filter_condition &= Q(flightbookingitinerarydetails__booking__source="Offline")
        if search and search_type:
            if search_type == 'booking_id':
                filter_condition &= Q(display_id__icontains=search) | Q(display_id=search)

            elif search_type == 'agency_name':
                filter_condition &= (
                    Q(user__organization__organization_name__icontains=search) |
                    Q(user__organization__organization_name=search)
                )

            elif search_type == 'agency_id':
                filter_condition &= (
                    Q(user__organization__easy_link_billing_code__icontains=search) |
                    Q(user__organization__easy_link_billing_code=search)
                )
            elif search_type == 'pnr':
                filter_condition &= (
                    Q(flightbookingitinerarydetails__gds_pnr__icontains=search) |
                    Q(flightbookingitinerarydetails__gds_pnr=search) |
                    Q(flightbookingitinerarydetails__airline_pnr__icontains=search) |
                    Q(flightbookingitinerarydetails__airline_pnr=search)
                )          
            else:
                filter_condition &= (
                    Q(flightbookingjourneydetails__source__icontains=search) |
                    Q(flightbookingjourneydetails__destination__icontains=search)
                )
            
        if current_user_organization:
            filter_condition &= current_user_organization
        unique_display_ids = Booking.objects.filter(filter_condition).values('display_id').distinct()
        data = Booking.objects.filter(Q(display_id__in=Subquery(unique_display_ids))).select_related(
            'FlightBookingItineraryDetails',
            'FlightBookingJourneyDetails',
            'FlightBookingSearchDetails',
            'FlightBookingPaxDetails',
            'payment_details'
                ).prefetch_related(
                'FlightBookingJourneyDetails__flightbookingsegmentdetails_set' 
                ).order_by('display_id','-created_at').distinct('display_id').values(
                'display_id','source','user__organization__easy_link_account_code',
                'flightbookingitinerarydetails__id',
                'flightbookingitinerarydetails__hold_till',
                'flightbookingjourneydetails__source',
                'flightbookingjourneydetails__destination',
                'search_details__journey_type',
                'search_details__fare_type',
                'flightbookingjourneydetails__date',
                'user__organization__organization_country__lookup__country_name',
                'booked_at','flightbookingpaxdetails__first_name','flightbookingpaxdetails__last_name',
                'status','payment_details__payment_type','payment_details__new_published_fare','payment_details__new_offered_fare','payment_details__ssr_price',
                'user__first_name','user__last_name',
                'user__organization__easy_link_billing_code',
                'user__organization__organization_name',
                'user__organization_id',
                'user_id',
                'user__base_country__currency_symbol', 
                'id',
                 'flightbookingjourneydetails__flightbookingsegmentdetails__airline_number',
                'flightbookingjourneydetails__flightbookingsegmentdetails__airline_name',
                'flightbookingjourneydetails__flightbookingsegmentdetails__airline_code',
                'flightbookingjourneydetails__flightbookingsegmentdetails__flight_number',
                'user__first_name',
                'user__email',
                'user__phone_number',
                'modified_by',
                'modified_by__first_name',
                'modified_by__last_name',
                'search_details__passenger_details')
        data = sorted(data, key=lambda x:x['booked_at'],reverse=True)
        booked_by_data ={"name":request.user.first_name,"email":request.user.email, "phone":request.user.phone_number}
        journey_details = FlightBookingJourneyDetails.objects.select_related('itinerary','booking').values(
                'itinerary__itinerary_key', "itinerary__hold_till",
                'source','date','destination','booking__display_id'                    
            )
        for record in data:
            passenger_details = record.pop('search_details__passenger_details')
            if isinstance(passenger_details, str):
                passenger_details = ast.literal_eval(passenger_details)
            pax_count = sum(int(value) for value in passenger_details.values())
            booking_itenary_details_list =[]
            travel_dates = {}
            hold_valid_till = {}
            booking_journey_data = [journey for journey in list(journey_details)
                    if journey.get("booking__display_id") == record['display_id']
                ]
            for journey in booking_journey_data:
                booking_itenary_details_list.append(journey.get("itinerary__itinerary_key"))
                travel_dates[journey.get("source")+"-"+journey.get("destination")] = journey.get("date")
                hold_valid_till[journey.get("source")+"-"+journey.get("destination")] = journey.get("itinerary__hold_till","N/A")
            if record['booked_at']:
                timestamp = int(record['booked_at'])
                uae_tz = self.get_booking_country_time(request.user.base_country,timestamp)
                record['booked_at'] = uae_tz

            record['easy_link_account_code'] = record.pop('user__organization__easy_link_account_code')
            record['booking_itinerarydetails_id'] = record.pop('flightbookingitinerarydetails__id')
            record['agency_id'] = record.get('user__organization__easy_link_billing_code')
            if request.user.role.name in ['super_admin','admin','operations','finance','sales']:
                record['show_provider'] =True
            else:
                record['show_provider'] =False
            record['itinerary'] = self.get_itenary_data(record['id'],record['show_provider']) 
            record['details_journey_type'] = record.pop('search_details__journey_type') 
            if  record['details_journey_type'].lower() != "multi city":
                record['journeydetails_source'] = booking_itenary_details_list[0].split("_")[0] if booking_itenary_details_list else None
                record['journeydetails_destination'] = booking_itenary_details_list[0].split("_")[1] if booking_itenary_details_list else None
            else:
                record['journeydetails_source'] = booking_itenary_details_list[0].split("_")[0] if booking_itenary_details_list else None
                record['journeydetails_destination'] = booking_itenary_details_list[-1].split("_")[1] if booking_itenary_details_list else None
            record['fare_type'] = record.pop('search_details__fare_type') if record.get("search_details__fare_type") else 'Regular'
            record['journeydetails_date'] = record.pop('flightbookingjourneydetails__date')
            record['country_name'] = record.pop('user__organization__organization_country__lookup__country_name')
            record['booked_at'] = record.pop('booked_at')
            record['first_name'] = record.pop('flightbookingpaxdetails__first_name')
            record['last_name'] = record.pop('flightbookingpaxdetails__last_name')
            record['payment_type'] = "WALLET" if not record.get('payment_details__payment_type') else record.pop('payment_details__payment_type').upper()
            record['easy_link_billing_code'] = record.pop('user__organization__easy_link_billing_code',None)
            record['organization_name'] = record.pop('user__organization__organization_name')
            record['organization_id'] = record.pop('user__organization_id')
            ssr_price = record.pop('payment_details__ssr_price') if record.get('payment_details__ssr_price') else 0
            offered_fare = record.pop('payment_details__new_offered_fare') if record.get('payment_details__new_offered_fare') else 0
            published_fare = record.pop('payment_details__new_published_fare') if record.get('payment_details__new_published_fare') else 0
            record['fare_price'] = {
                "offered_fare":round(offered_fare + ssr_price,2),
                "published_fare": round(published_fare + ssr_price,2),
                "currency":record.pop('user__base_country__currency_symbol', None),
            } 
            record['airline_number'] = record.pop('flightbookingjourneydetails__flightbookingsegmentdetails__airline_number')
            record['airline_name'] = record.pop('flightbookingjourneydetails__flightbookingsegmentdetails__airline_name')
            record['airline_code'] = record.pop('flightbookingjourneydetails__flightbookingsegmentdetails__airline_code')
            record['flight_number'] = record.pop('flightbookingjourneydetails__flightbookingsegmentdetails__flight_number')
            record['itinerary_keys'] = booking_itenary_details_list
            record['travel_dates'] = travel_dates 
            record["source"] = record.pop("source")
            record["hold_valid_till"] = hold_valid_till
            record["booked_by"] ={'name':record.pop('user__first_name'),'email':record.pop('user__email'),'phone_number':record.pop('user__phone_number')}
            record["modified_by"] = record.pop("modified_by__first_name")+'-'+record.pop("modified_by__last_name")
            record['pax_count'] = pax_count

        paginator = CustomPageNumberPagination()
        paginated_queryset = paginator.paginate_queryset(data, request)
        data = {
            "results":paginated_queryset,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next_page": paginator.get_next_link(),
            "prev_page": paginator.get_previous_link(),
            "total_data":len(data),
            "page_size":page_size
        }
        return Response(data)
    
    def get_itenary_data(self,id,show_provider):
        obj = FlightBookingItineraryDetails.objects.filter(booking_id=id).order_by("modified_at")
        itinerary = {}
        for i,v in enumerate(obj):
            if v.status in ["Failed-Confirmed","Cancel-Ticket-Failed"]:
                v.status = "Confirmed"
            if v.status == "Failed-Rejected":
                v.status = "Rejected"
            if show_provider:
                itinerary[v.itinerary_key] ={"status":v.status,"airline_pnr":v.airline_pnr,"gds_pnr":v.gds_pnr,"provider":v.vendor.name,
                                             "is_soft_fail":v.soft_fail,"booking_ref_num":v.supplier_booking_id}
            else:
                itinerary[v.itinerary_key] ={"status":v.status,"airline_pnr":v.airline_pnr,"gds_pnr":v.gds_pnr,"provider":"-",
                                             "is_soft_fail":v.soft_fail,"booking_ref_num":v.supplier_booking_id}
        return itinerary
    
    def calculate_price(self,request,id):
        flight_booking = FlightBookingFareDetails.objects.filter(itinerary_id=id)
        if not flight_booking:
            return None
        flight_booking = flight_booking.first()
        if request.user.role.name == "distributor_agent":
            return (flight_booking.offered_fare - flight_booking.dist_agent_markup)+flight_booking.dist_agent_cashback
        return flight_booking.offered_fare
    
    def get_current_organization(self, user):
        filter_query = Q()
        try:
            current_role = user.role.name
        except:
            return filter_query
        assert current_role, "the current user is not  assigned to any role "
        filter_query = Q()
        if current_role == "distributor_agent":
            filter_query = Q(user_id = user.id)
        elif current_role in ["agency_owner","agency_staff","distributor_owner","distributor_staff","out_api_owner","out_api_staff","enterprise_owner","supplier"]:
            filter_query = Q(user__organization_id = user.organization_id)
        elif current_role == "sales":
            filter_query = Q(user__organization__sales_agent=user.id)|Q(user__organization_id=user.organization_id)
        return filter_query
    
    def get_booking_country_time(self, country_name,timestamp):
        time_zone_map = {
            "India": "Asia/Kolkata",
            "Canada": "America/Toronto",
            "United States of America": "America/New_York",
            "United Kingdom of Great Britain and Northern Ireland": "Europe/London",
            "United Arab Emirates": "Asia/Dubai",
        }
        tz_name = time_zone_map.get(country_name, "Asia/Kolkata")
        tz = pytz.timezone(tz_name)
        utc_datetime = datetime.fromtimestamp(timestamp, pytz.utc)
        localized_datetime = utc_datetime.astimezone(tz)
        formatted_time = localized_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        return formatted_time

class PassengerCalender(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            page_size = int(request.query_params.get('page_size', 15))
            month = request.query_params.get('month', None)
            year = request.query_params.get('year', None)
            filter_condition = Q()
            current_user_organization = self.get_current_organization(request.user)
            try:
                if month and year:
                    month = str(month).zfill(2)  
                    year = str(year)  
                    condn = "-"+month+"-"+year
                    filter_condition = Q(flightbookingjourneydetails__date__endswith=year) & Q(flightbookingjourneydetails__date__contains='-'+month+'-')
            except ValueError:
                return Response({"error": "Invalid month or year format. Please provide numeric values."}, status=400)

            booking_ids_with_multiple_itineraries = Booking.objects.filter(
            filter_condition, current_user_organization, status="Confirmed").annotate(
            ).values('pk')  
            booking_data = Booking.objects.filter(
                pk__in=booking_ids_with_multiple_itineraries).order_by('display_id')  
            serializer = PassengerCalendarSerializer(booking_data, many=True) 
            data = {
                "status": True,
                "data": serializer.data
            }
            return Response(data)
        except Exception as e:
            return Response({"status": False,"error":str(e)})
    
    def get_current_organization(self, user):
        filter_query = Q()
        try:
            current_role = user.role.name
        except:
            return filter_query
        assert current_role, "the current user is not  assigned to any role "
        filter_query = Q()
        if current_role == "distributor_agent":
            filter_query = Q(user_id = user.id)
        elif current_role in ["agency_owner","agency_staff","distributor_owner","distributor_staff","out_api_owner","out_api_staff","enterprise_owner","supplier"]:
            filter_query = Q(user__organization_id = user.organization_id)
        elif current_role == "sales":
            filter_query = Q(user__organization__sales_agent=user.id)|Q(user__organization_id=user.organization_id)        
        return filter_query

class FlightPickUp2(APIView):
    def get(self,request):
        try:
            booking_id = request.query_params['booking_id']
        except KeyError as e:
            return Response({"message":f"key missing {e} in query params"},status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message":f"Internal server error "},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        booking_obj = Booking.objects.get(id=booking_id)
        obj = FlightBookingJourneyDetails.objects.filter(
                Q(booking_id=booking_id) & Q(booking=F('itinerary__booking'))
            ).prefetch_related(
                Prefetch('flightbookingsegmentdetails_set', queryset=FlightBookingSegmentDetails.objects.all())
            ).distinct()
        journey_details = [ ]
        for journey in obj:
            current_journey = {}
            current_journey["from"] = f"{self.get_airport_name_from_code(journey.source)} - {journey.source}"
            current_journey["to"] = f"{self.get_airport_name_from_code(journey.destination)} - {journey.destination} "
            current_journey["date"] = self.string_to_custom_format(journey.date)
            current_journey['airline_pnr']=journey.itinerary.airline_pnr if journey.itinerary.airline_pnr else "N/A"
            current_journey['gds_pnr']=journey.itinerary.gds_pnr if journey.itinerary.gds_pnr else "N/A"
            journey_details.append(current_journey)
            current_journey_segment = []
            for segment in journey.flightbookingsegmentdetails_set.all():
                current_journey_segment.append({
                    "airline_number":segment.airline_number,
                    "airline_name":segment.airline_name,
                    "airline_code":segment.airline_code,
                    "flight_number":segment.flight_number,
                    "equipment_type":segment.equipment_type,
                    "duration":f"{self.convert_to_hour(segment.duration)} {'mins' if self.convert_to_hour(segment.duration) > 60 else 'Hr'}",
                    "origin":f"{self.get_airport_name_from_code(segment.origin)} - {segment.origin}",
                    "origin_terminal":segment.origin_terminal,
                    "departure_datetime":self.epoch_to_custom_format(segment.departure_datetime),
                    "destination":f"{self.get_airport_name_from_code(segment.destination)} - {segment.destination}",
                    "destination_terminal":segment.destination_terminal,
                    "arrival_datetime":self.epoch_to_custom_format(segment.arrival_datetime)
                    
                })
                current_journey["current_segement_details"] = current_journey_segment  
        booking_details = {
            "booking_id":booking_obj.display_id,
            "booking_date":self.epoch_to_custom_format(booking_obj.booked_at)
        }
        pax_details = FlightBookingPaxDetails.objects.filter(booking_id=booking_id)
        pax_details_serializer = FlightBookingPaxDetailsSerializer(pax_details, many=True)
        fare_details_obj = FlightBookingItineraryDetails.objects.filter(Q(booking_id=booking_id)&
                            Q(booking=F('booking__flightbookingpaxdetails__booking'))
                            ).prefetch_related(
                                Prefetch("flightbookingfaredetails_set", queryset=FlightBookingFareDetails.objects.all())
                            )                          
        fare_details = []               
        for i in fare_details_obj:
            for a in i.flightbookingfaredetails_set.all():
                if a.fare_breakdown:
                    a.fare_breakdown = a.fare_breakdown.replace("'", '"')
                    fare_details.append(json.loads(a.fare_breakdown))
        data = {
            "journey_details":journey_details,
            "pax_details":pax_details_serializer.data,
            "fare_details":fare_details,
            "booking_details":booking_details
            }
        
        return Response(data)

    def string_to_custom_format(self,date_string):
        date_time = datetime.strptime(date_string, '%d-%m-%Y')
        day = date_time.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]
        return date_time.strftime(f'%b {day}{suffix} %Y')
    
    def epoch_to_custom_format(self, epoch_time):
        date_time = datetime.fromtimestamp(epoch_time)

        day = date_time.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]
        return date_time.strftime(f'%b {day}{suffix} %Y %I:%M %p')
    
    def get_airport_name_from_code(self, code:str):
        try:
            airport_name = LookupAirports.objects.get(code=code).name
        except LookupAirports.DoesNotExist:
            return code
        return airport_name

    def journey_detail_dict(self,jouney_detail_list):
        return [ { "journey_from":f"{self.get_airport_name_from_code(i.source)} ({i.source})",
                "journey_to": f"{self.get_airport_name_from_code(i.destination)} ({i.destination})",
                "journey_date":self.string_to_custom_format(i.date) }
             for i in jouney_detail_list ]

    def convert_to_hour(self,value):
        value = value/60
        return round(value,2)

class FlightPickUp(APIView):
    def get(self,request):
            try:
                booking_id = request.query_params['booking_id']
            except KeyError as e:
                return Response({"message":f"key missing {e} in query params"},status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"message":f"Internal server error "},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            booking_details = self.get_booking_details(booking_id)
            pax_details = self.get_pax_details(booking_id) 
            search_details = self.get_search_details(booking_id)
            itinerary_key = self.get_itinerary_key(booking_id)
            contact_details = self.get_contact_details(booking_id)
            fare_details = self.get_fare_details(booking_id)
            return_data  =self.get_data(booking_id)
            data = {

                "pax_details":pax_details,
                "search_details":search_details,
                "itinerary_key":itinerary_key,
                "contact":contact_details,
                "fareDetails":fare_details
                
            }
            itinerary_details_list = FlightBookingItineraryDetails.objects.filter(booking_id=booking_id)
            for itenary in itinerary_details_list:
                data[itenary.itinerary_key] = self.get_itenary_details(itenary.id,itenary.itinerary_key,search_details)
            return Response(return_data)
        
    def get_data(self,booking_id):
        booking = Booking.objects.filter(id=booking_id).first()
        itinerary_details = FlightBookingItineraryDetails.objects.filter(booking=booking)
        pax_details = FlightBookingPaxDetails.objects.filter(booking=booking)
        lookup_country_list = LookupCountry.objects.all()
        airports_list = LookupAirports.objects.all()        
        pax_data = []
        for pax in pax_details:
            pax_dict = {   
                        "type": pax.pax_type,
            "title": pax.title,
            "firstName": pax.first_name,
            "lastName": pax.last_name,
            "gender":pax.gender,
            "dob": pax.dob,
            "address_1": pax.address_1,
            "address_2": pax.address_2,
            "passport": pax.passport,
            "passport_issue_date": pax.passport_issue_date,
            "passport_issue_country_code": pax.passport_issue_country_code,
            "passport_expiry": pax.passport_expiry}
            for itinerary in itinerary_details:
                ssr_detail = FlightBookingSSRDetails.objects.filter(pax = pax,itinerary = itinerary).first()
                if ssr_detail:
                    pax[itinerary.itinerary_key]={
                        "baggage_ssr": json.loads(ssr_detail.baggage_ssr),
                        "meals_ssr": json.loads(ssr_detail.meals_ssr),
                        "supplier_ticket_number": ssr_detail.supplier_ticket_number,
                        "supplier_ticket_id": ssr_detail.supplier_ticket_id,
                        "supplier_pax_id": ssr_detail.supplier_pax_id,
                        "seats_ssr":json.loads(ssr_detail.seats_ssr)
                    }
            pax_data.append(pax_dict)
        itinerary_dict = {}
        for itinerary in itinerary_details:
            journeys = FlightBookingJourneyDetails.objects.filter(itinerary=itinerary)
            itinerary_dict[itinerary.itinerary_key] = {"flightSegments":{}}
            for journey in journeys:
                itinerary_dict[itinerary.itinerary_key]["flightSegments"][journey.journey_key] = []
                segment_list = FlightBookingSegmentDetails.objects.filter(journey=journey)
                for segment in segment_list:
                    segment_data ={
                            "airlineCode": segment.airline_code,
                            "airlineName": segment.airline_name,
                            "flightNumber": segment.airline_number,
                            "equipmentType": segment.equipment_type,
                            "departure": {
                                "airportCode":self.get_airport_city_from_code(segment.origin),
                                "airportName": self.get_airport_name_from_code(segment.origin),
                                "city": self.get_airport_city_from_code(segment.origin),
                                "country": self.get_airport_country_from_code(segment.origin),
                                "countryCode": self.get_country_code_from_code(segment.origin),
                                "terminal": segment.origin_terminal,
                                "departureDatetime": segment.departure_datetime
                            },
                            "arrival": {
                                "airportCode":self.get_airport_city_from_code(segment.destination),
                                "airportName": self.get_airport_name_from_code(segment.destination),
                                "city": self.get_airport_city_from_code(segment.destination),
                                "country": self.get_airport_country_from_code(segment.destination),
                                "countryCode": self.get_country_code_from_code(segment.destination),
                                "terminal": segment.destination_terminal,
                                "arrivalDatetime": segment.arrival_datetime
                            },
                            "durationInMinutes": segment.duration
                    }
                itinerary_dict[itinerary.itinerary_key]["flightSegments"][journey.journey_key].append(segment_data)
        booking_details = self.get_booking_details(booking_id)
        pax_details = self.get_pax_details(booking_id) 
        search_details = self.get_search_details(booking_id)
        itinerary_key = self.get_itinerary_key(booking_id)
        contact_details = self.get_contact_details(booking_id)
        fare_details = self.get_fare_details(booking_id)
        gst_details_and_contact = self.gst_details_and_contact(booking_id)
        return {"pax_details":pax_data,"fare_details":fare_details,
                "search_details":search_details, 
                "itinerary_key":itinerary_key,"contact":contact_details,
                }|itinerary_dict|gst_details_and_contact
        
    def gst_details_and_contact(self,booking_id):
        booking_obj = Booking.objects.get(id=booking_id)
        gst_details = json.loads(booking_obj.gst_details) if booking_obj.gst_details else None
        contact = json.loads(booking_obj.contact) if booking_obj.contact else None

        return {"gst_details": gst_details, "contact": contact}
            
    def get_fare_details(self,booking_id):
        itinerary_details = FlightBookingItineraryDetails.objects.filter(booking_id=booking_id)
        data = FlightBookingFareDetails.objects.filter(itinerary__in = itinerary_details)
        return FlightBookingFareDetailsSerializer(data, many=True).data

    def get_contact_details(self, booking_id):
        obj = Booking.objects.get(id=booking_id)
        return {
            "phoneCode":obj.user.phone_code,
            "phone":obj.user.phone_number,
            "email":obj.user.email
        }
        
    def get_booking_details(self, booking_id):
         booking_obj = Booking.objects.get(id=booking_id)
         return {
                "booking_id":booking_obj.display_id,
                "date":booking_obj.booked_at
            }
            
            
    def get_pax_details(self, booking_id):
        itinerary_details = FlightBookingItineraryDetails.objects.filter(booking_id=booking_id)
        ssr_details = FlightBookingSSRDetails.objects.filter(
            itinerary__in=itinerary_details
        ).select_related('itinerary', 'pax',)
        
        pax_details = []
        for ssr in ssr_details:
            pax_dict = FlightBookingPaxDetailsSerializer(ssr.pax).data
            baggage_ssr_list = json.loads(ssr.baggage_ssr)
            meals_ssr_list = json.loads(ssr.meals_ssr)
            seats_ssr_list = json.loads(ssr.seats_ssr)
            pax_dict[ssr.itinerary.itinerary_key] = {
                "baggage_ssr": baggage_ssr_list,
                "meals_ssr":meals_ssr_list,
                "seats_ssr":seats_ssr_list
                
            }
            pax_dict['supplier_ticket_number'] = ssr.supplier_ticket_number
            pax_dict['supplier_ticket_id'] = ssr.supplier_ticket_id
            pax_dict['supplier_pax_id'] = ssr.supplier_pax_id
            
            pax_details.append(pax_dict)

        return pax_details

    def get_search_details(self,booking_id):
        booking_obj = Booking.objects.get(id=booking_id)
        search_data = FlightBookingSearchDetailsSerializer(FlightBookingSearchDetails.objects.get(id=booking_obj.search_details_id)).data
        return search_data
        
    def get_itenary_details(self,itenary_id, key,search_details):
        journey_detail_list = FlightBookingJourneyDetails.objects.prefetch_related('flightbookingsegmentdetails_set').filter(itinerary_id=itenary_id)
        segment_list = []
        for journey in journey_detail_list:
            segments = journey.flightbookingsegmentdetails_set.all()  
            for segment in segments:
                segment_list.append({
                    "airlineCode":segment.airline_code,
                    "airlineName":segment.airline_name,
                    "flightNumber":segment.flight_number,
                    "equipmentType":segment.equipment_type,
                    "departure":{
                                 "airportCode":segment.origin,
                                 "airportName":self.get_airport_name_from_code(segment.origin),
                                 "city":self.get_airport_city_from_code(segment.origin),
                                 "country":self.get_airport_country_from_code(segment.origin),
                                 "countryCode":self.get_country_code_from_code(segment.origin),
                                 "terminal":segment.origin_terminal,
                                 "departureDatetime":self.epoch_to_custom_format(segment.departure_datetime),
                                 },
                    "arrival":{
                                 "airportCode":segment.origin,
                                 "airportName":self.get_airport_name_from_code(segment.destination),
                                 "city":self.get_airport_city_from_code(segment.destination),
                                 "country":self.get_airport_country_from_code(segment.destination),
                                 "countryCode":self.get_country_code_from_code(segment.destination),
                                 "terminal":segment.destination_terminal,
                                 "departureDatetime":self.epoch_to_custom_format(segment.arrival_datetime),
                                 },
                    "durationInMinutes":self.epoch_to_custom_format(segment.duration),
                    "stop": 0,
                    "cabinClass": search_details.get('cabin_class',None)if search_details.get('cabin_class',None) else None,
  
                })
        return {"flightSegments":{key:segment_list }} 

    def string_to_custom_format(self,date_string):
        date_time = datetime.strptime(date_string, '%d-%m-%Y')
        day = date_time.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]
        
        return date_time.strftime(f'%b {day}{suffix} %Y')
    
    def epoch_to_custom_format(self, epoch_time):
        date_time = datetime.fromtimestamp(epoch_time)
        day = date_time.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]
    
        return date_time.strftime(f'%b {day}{suffix} %Y %I:%M %p')
    
    def get_airport_name_from_code(self, code:str):
        try:
            airport_name = LookupAirports.objects.get(code=code).name
        except LookupAirports.DoesNotExist:
            return code
        return airport_name

    def get_airport_city_from_code(self, code:str):
        try:
            airport_name = LookupAirports.objects.get(code=code).city
        except LookupAirports.DoesNotExist:
            return code
        return airport_name
    
    def get_airport_country_from_code(self, code:str):
        try:
            airport_name = LookupAirports.objects.get(code=code).country.country_name
        except LookupAirports.DoesNotExist:
            return code
        return airport_name
    
    def get_country_code_from_code(self, code:str):
        try:
            airport_name = LookupAirports.objects.get(code=code).country.country_code
        except LookupAirports.DoesNotExist:
            return code
        return airport_name

    def journey_detail_dict(self,jouney_detail_list):
        return [ { "journey_from":f"{self.get_airport_name_from_code(i.source)} ({i.source})",
                "journey_to": f"{self.get_airport_name_from_code(i.destination)} ({i.destination})",
                "journey_date":self.string_to_custom_format(i.date) }
             for i in jouney_detail_list ]
    
    def convert_to_hour(self,value):
        value = value/60
        return round(value,2)
    
    def get_itinerary_key(self,booking_id):
        obj = FlightBookingItineraryDetails.objects.filter(booking_id=booking_id)
        return [i.itinerary_key for i in obj ]
    
class FlightCancellationView(FlightPickUp):
    def post(self,request):
        try:
            itinerary_key = request.data['itinerary_key']
            cancellation_reason=request.data['cancellation_reason']
        except KeyError as e:
            return Response({"message":f"key {e} is required in payload "},status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message":f"Unknown error {e}"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        flight_segments = self.flight_segments(itinerary_key)
        pax_detail = self.pax_details(itinerary_key)
        booking_reference_id = Booking.objects.get(id=FlightBookingJourneyDetails.objects.filter(itinerary_id=itinerary_key).first().booking_id).display_id
        request_date = self.epoch_to_custom_format(time.time())
        cancellation_reason = cancellation_reason
        country_name = request.user.organization.organization_country.lookup.country_name
        invoke(event='FLIGHT_CANCELLATION_REQUEST',number_list=[], email_list=[],data = {"request_date":request_date, 
                                                           "booking_reference":booking_reference_id,"passenger_list":pax_detail,
                                                           "cancellation_reason":cancellation_reason,"flight_segments":flight_segments,
                                                           "country_name":country_name,"user_email":request.user.email
                                                           })

        return Response({"message":"success"})

    def pax_details(self,itinerary_id):
         booking_id = FlightBookingJourneyDetails.objects.filter(itinerary_id=itinerary_id).first().booking_id
         pax_details = FlightBookingPaxDetails.objects.filter(booking_id=booking_id)
         
         return "".join(
                        f"""<tr>
                        <td>{i+1}</td>
                        <td>{v.first_name} {v.last_name}</td>
                        <td>{v.pax_type}</td>
                        </tr>"""

             for i,v in enumerate(pax_details)
         )
        
    def flight_segments(self,itinerary_id):
        """ converts the flight segments with html code"""
        segments = FlightBookingSegmentDetails.objects.filter(journey__in =
                                                              Subquery(
                                                                  FlightBookingJourneyDetails.objects.filter(itinerary_id=itinerary_id).values('id')
                                                              ))
        
        return "".join(
       
            f"""
                <div class="segment-title">Flight Segment {i+1}:</div>
                <table class="details" width="100%" cellspacing="0" cellpadding="0">
                <tbody>
                    <tr>
                    <td><strong>From:</strong></td>
                    <td>{self.get_airport_name_from_code(v.origin)} - ({v.origin})</td>
                    </tr>
                    <tr>
                    <td><strong>To:</strong></td>
                    <td>{self.get_airport_name_from_code(v.destination)} - ({v.destination})</td>
                    </tr>
                    <tr>
                    <td><strong>Flight Number:</strong></td>
                    <td>{v.airline_number}</td>
                    </tr>
                    <tr>
                    <td><strong>Departure Date:</strong></td>
                    <td>{self.epoch_to_custom_format(v.departure_datetime)}</td>
                    </tr>
                </tbody>
                </table>
                        """  for i ,v in enumerate(segments))

class FlightBookingFailed(FlightCancellationView):
    def post(self,request):
        
        try:
            itinerary_key = request.data['itinerary_key']
            error_message = request.data['error_message']
        except KeyError as e:
            return Response({"message":f"key {e} is required in payload "},status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message":f"Unknown error {e}"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        error_message = error_message
        flight_segments = self.flight_segments(itinerary_key)
        pax_detail = self.pax_details(itinerary_key)
        booking_id = FlightBookingJourneyDetails.objects.filter(itinerary_id=itinerary_key).first().booking_id
        details = FlightBookingPaxDetails.objects.filter(booking_id=booking_id).first()
        soup = BeautifulSoup(flight_segments, 'html.parser')

        from_location = [row.find_next_sibling('td').text for row in soup.find_all('td', text="From:")][0]
        to_location = [row.find_next_sibling('td').text for row in soup.find_all('td', text="To:")][0]
        booking_reference_id = Booking.objects.get( id=FlightBookingJourneyDetails.objects.filter(itinerary_id=itinerary_key).first().booking_id).display_id
        request_date =self.epoch_to_custom_format(time.time())
        country_name = request.user.organization.organization_country.lookup.country_name
        # invoke(event='Flight_Booking_Failed',number_list=[], email_list=[request.user.email], data ={"agent_name":request.user.organization.organization_name, 
        #                                                    "booking_reference":booking_reference_id,"passenger_name":details.first_name, 
        #                                                    "travel_date":request_date,
        #                                                    "error_message":error_message,"origin":from_location,"destination":to_location,
        #                                                    "user_email":request.user.email,"country_name":country_name})
        return Response({"message":"success"})
        
class FlightBookingModification(FlightCancellationView):
    def post(self,request):
        
        try:
            itinerary_key = request.data['itinerary_key']
            error_message = request.data['error_message']
        except KeyError as e:
            return Response({"message":f"key {e} is required in payload "},status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message":f"Unknown error {e}"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        error_message = error_message
        flight_segments = self.flight_segments(itinerary_key)
        pax_detail = self.pax_details(itinerary_key)
        booking_reference_id = Booking.objects.get( id=FlightBookingJourneyDetails.objects.filter(itinerary_id=itinerary_key).first().booking_id).display_id
        request_date =self.epoch_to_custom_format(time.time())
        country_name = request.user.organization.organization_country.lookup.country_name
        email = request.user.email
        invoke(event='FLIGHT_BOOKING_MODIFICATION',number_list=[], email_list=[email], data = {"request_date":request_date, 
                                                           "booking_reference":booking_reference_id,"passenger_list":pax_detail,
                                                           "error_message":error_message,"flight_segments":flight_segments,
                                                           "user_email":request.user.email,"country_name":country_name})
        return Response({"message":"success"})

class FlightBookingConfirmation(FlightCancellationView):
    def post(self,request):
        try:
            booking_id = request.data['booking_id']
        except KeyError as e:
            return Response({"message":""})
        itinerary_details = FlightBookingItineraryDetails.objects.filter(booking=booking_id)
        passenger_list = FlightBookingPaxDetails.objects.filter(
                    booking_id=booking_id
            ).prefetch_related(
                Prefetch(
                    'flightbookingssrdetails_set',
                    queryset=FlightBookingSSRDetails.objects.filter(itinerary__in=itinerary_details),
                    to_attr='ssr_details'
                )
            ) 
        passenger_details = f"""
                                <tr>
                                <td style="background-color:#f5f5f5;border-bottom:1px #e5e5e5 solid; font-size:16px; padding:12px; font-weight:600;">
                                Passenger Details {len(passenger_list)}
                                </td>
                                </tr>
                                <tr>
                                    <td>
                                        <table width="750" border="0" cellspacing="0" cellpadding="0">
                                            <tr>
                                                <td width="20"
                                                    style="border-bottom:1px #e5e5e5 solid; border-right:1px #e5e5e5 solid; font-weight:bold; padding:5px;">
                                                    No.</td>
                                                <td width="330"
                                                    style="border-bottom:1px #e5e5e5 solid; border-right:1px #e5e5e5 solid; font-weight:bold; padding:5px;">
                                                    Sr. Name, DOB, Passport, & FF</td>
                                                <td width="200"
                                                    style="border-bottom:1px #e5e5e5 solid; border-right:1px #e5e5e5 solid;  font-weight:bold; padding:5px;">
                                                    Ticket No</td>
                                                <td width="200"
                                                    style="border-bottom:1px #e5e5e5 solid;  font-weight:bold; padding:5px;">
                                                    Meal, Baggage, Seat & Other
                                                    Preference</td>
                                            </tr>
                            """
        for passenger in passenger_list:
            passenger_details+=self.passenger_block()
            pass
            
        passenger_details+="""
                        </table></td>
                        </tr>
         """
        itinerary_details = FlightBookingItineraryDetails.objects.filter(booking=booking_id).prefetch_related(
            Prefetch(
                'flightbookingjourneydetails_set', 
                queryset=FlightBookingJourneyDetails.objects.all().prefetch_related(
                    Prefetch(
                        'flightbookingsegmentdetails_set',
                        queryset=FlightBookingSegmentDetails.objects.all()
                    )
                ),
                to_attr='journeys'
            )
        )
        flight_segment = ""
        for itinerary in itinerary_details:
            
            for journey in itinerary.journeys:
                flight_segment += self.html_block_2_origin_destination(from_origin = journey.source,
                                                                       to_destination = journey.destination,
                                                                       epoc_time = journey.timestamp ,
                                                                       gds_pnr=itinerary.gds_pnr,
                                                                       airline_pnr = itinerary.airline_pnr)
                for segment in journey.flightbookingsegmentdetails_set.all():
                    flight_segment += self.html_block_3_segment_details(airline_name=segment.airline_name,airline_code=segment.airline_code,origin=segment.origin,
                                                                       timestamp=segment.timestamp,departure_datetime=segment.departure_datetime,
                                                                        arrival_datetime=segment.arrival_datetime,destination=segment.destination,duration=segment.duration)

        return Response({"message":"success"})

    def html_block_2_origin_destination(self,from_origin,to_destination,epoc_time,gds_pnr,airline_pnr):
        
                            return f"""
                             <tr>
                             <td>
                             <table width="730" border="0" cellspacing="0" cellpadding="0">
                             <tr>
                             <td width="460">
                             <div
                            style="background-color:#f5f5f5;border:1px #e5e5e5 solid; font-size:16px; font-weight:bold; height:20px; padding:18px;">
                            {self.get_airport_name_from_code(from_origin)}-({from_origin}) → {self.get_airport_name_from_code(to_destination)}-({to_destination}) on {self.epoch_to_custom_format(epoc_time)}</div>
                                                            </td>
                                                            <td width="15">&nbsp;</td>
                                                            <td width="255">
                                                                <div
                                                                    style="background-color:#f5f5f5; font-size:12px; font-weight:bold;">
                                                                    <table width="100%" border="0" cellspacing="0"
                                                                        cellpadding="0"
                                                                        style="border:1px #e5e5e5 solid; ">
                                                                        <tr>
                                                                            <td
                                                                                style="padding:5px; border-bottom:1px #e5e5e5 solid;">
                                                                                Airline PNR</td>
                                                                            <td
                                                                                style="border-left:1px #e5e5e5 solid; padding:5px; border-bottom:1px #e5e5e5 solid;">
                                                                                GDS PNR</td>
                                                                        </tr>
                                                                        <tr>
                                                                            <td style="padding:5px; ">{gds_pnr if gds_pnr else "--"}</td>
                                                                            <td
                                                                                style="border-left:1px #e5e5e5 solid; padding:5px;">
                                                                                {airline_pnr if airline_pnr else "--"}</td>
                                                                        </tr>
                                                                    </table>
                                                                </div>

                                                            </td>
                                                        </tr>
                                                    </table>


                                                </td>
                                            </tr>
                                            <tr>
                                                <td height="8"></td>
                                            </tr>
        """
    
    def html_block_3_segment_details(self,airline_name,airline_code,origin,timestamp,departure_datetime,
                                     arrival_datetime,destination,duration):
        return f"""
                <tr>
                <td>

                <table width="730" border="0" cellspacing="0" cellpadding="0"style="border:1px #e5e5e5 solid;">
                <tr>
                <td width="100"style="border-right:1px #e5e5e5 solid; padding:5px;">
                <table width="100%" border="0" cellspacing="0"
                cellpadding="0">
                <tr>
                <td><img src="{self.get_airline_logo(airline_name)}"></td>
                <td><strong>{airline_name}</strong><br> {airline_code}</td>
                </tr>
                </table>

                </td>
                <td width="190"
                style="border-right:1px #e5e5e5 solid;padding:5px;">
                <p style="margin:0px;">{self.epoch_to_custom_format(departure_datetime)}</p>
                <p style="margin:0px;">{self.get_airport_city_from_code(origin)}, {self.get_country_code_from_code(origin)}</p>
                <p style="margin:0px;">{self.get_airport_name_from_code(origin)}</p>
                </td>
                <td width="150" style="border-right:1px #e5e5e5 solid;"align="center">

                <img src="https://b2bta-production.s3.ap-south-1.amazonaws.com/assets/images/flight/duration.svg" width="100"style="margin-top:10px;">
                </td>
                <td width="145" style="border-right:1px #e5e5e5 solid; padding:5px;">
                <p style="margin:0px;">{self.epoch_to_custom_format(arrival_datetime)}</p>
                <p style="margin:0px;">{self.get_airport_city_from_code(destination)}, {self.get_country_code_from_code(destination)}</p>
                <p style="margin:0px;">{self.get_airport_name_from_code(destination)}</p>
                </td>
                <td width="145" style="padding:5px;">
                <p style="margin:0px;">{ str(round(int(duration) / 60, 2)).split(".")[0] + "hr " + str(round(int(duration) / 60, 2)).split(".")[1] + "min"}</p>
                </p>
                </td>
                </tr>
                </table>

                </td>
                </tr>
                """
                
    def get_airline_logo(self,airline_name):
        url = f"https://logo.clearbit.com/{airline_name.lower().replace(' ', '')}.com"
        response = requests.get(url)
        if response.status_code == 200:
            return url
        return "https://www.google.com/url?sa=i&url=https%3A%2F%2Fwww.istockphoto.com%2Fillustrations%2Fflight-logo&psig=AOvVaw3zOlkHcvzqtLw2snV3bakO&ust=1730545624073000&source=images&cd=vfe&opi=89978449&ved=0CBEQjRxqFwoTCND-vfv-uokDFQAAAAAdAAAAABAS"
    
    def passenger_block(self,title,first_name,last_name,
                        gender,passport):
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


class FetchPaxDetails(APIView):
    def get(self, request):
        try:
            search_key = request.query_params.get("name")
            pax_type = request.query_params.get("type")

            if search_key and pax_type:
                query_sets = FlightBookingPaxDetails.objects.filter(Q(first_name__icontains=search_key) & Q(pax_type__icontains = pax_type))
                serializer = FetchPaxDetailsSerializer(query_sets, many=True)
                data = pd.DataFrame(serializer.data)
            if data.empty:
                final_data = []
            else:
                data.fillna("", inplace=True)
                def merge_rows(group):
                    return group.apply(lambda col: ", ".join(map(str, col[col != ""].unique())), axis=0)
                grouped_data = data.groupby(["first_name", "last_name", "passport", "gender","passport_expiry",
                                             "passport_issue_date","passport_issue_country_code","dob"], dropna=False).apply(merge_rows).reset_index(drop=True)
                final_data = grouped_data.to_dict(orient="records")
            return Response(final_data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
