from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from users.models import UserDetails
from bookings.flight.models import Booking,FlightBookingItineraryDetails,FlightBookingSegmentDetails
from django.db.models import Sum, Count, Case, When, IntegerField, Value
from datetime import datetime, timedelta
import time
import calendar
from uuid import UUID
from django.db.models.functions import Concat
from django.db import models  
from django.core.exceptions import PermissionDenied
from accounting.shared.models import Payments
from rest_framework import status
from collections import defaultdict


class BillingStaffPerformanceApi(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    

    def get(self, request, *args, **kwargs):
        module = self.request.query_params.get('module', None)
        from_date = self.request.query_params.get('from_date', None)
        to_date = self.request.query_params.get('to_date', None)
        agency_id = self.request.query_params.get('agency_id', None)  
        staff_performance = []

        from_timestamp = None
        to_timestamp = None
        try:
            if from_date:
                from_date = datetime.strptime(from_date, "%Y-%m-%d")
                from_timestamp = int(time.mktime(from_date.timetuple()))
            if to_date:
                to_date = datetime.strptime(to_date, "%Y-%m-%d")
                to_date += timedelta(days=1)
                to_timestamp = int(time.mktime(to_date.timetuple()))
        except ValueError:
            return Response(
                {
                    "status": False,
                    "message": "Invalid date format. Use YYYY-MM-DD.",
                    "data": [],
                    "errors": {"details": "Date parsing error."}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        finance_users = UserDetails.objects.filter(role__name='finance')
        if agency_id:
            try:
                agency_uuid = UUID(agency_id)  # Ensure the agency ID is a valid UUID
                finance_users = finance_users.filter(organization__id=agency_uuid)  # Filter by agency UUID
            except ValueError:
                return Response(
                    {
                        "status": False,
                        "message": "Invalid agency ID format. Ensure the agency ID is a valid UUID.",
                        "data": [],
                        "errors": {"details": "Invalid agency ID format."}
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if module == "flight":
            for user in finance_users:
                user_bookings = Booking.objects.filter(
                    modified_by=user,
                    source='Offline'
                )
                if from_timestamp:
                    user_bookings = user_bookings.filter(modified_at__gte=from_timestamp)
                if to_timestamp:
                    user_bookings = user_bookings.filter(modified_at__lt=to_timestamp)

                booking_count = user_bookings.count()

                new_published_fare_sum = user_bookings.aggregate(
                    total_new_published_fare=Sum('payment_details__new_published_fare')
                )['total_new_published_fare'] or 0

                new_offered_fare_sum = user_bookings.aggregate(
                    total_new_offered_fare=Sum('payment_details__new_offered_fare')
                )['total_new_offered_fare'] or 0

                supplier_offered_fare_sum = user_bookings.aggregate(
                    total_supplier_offered_fare=Sum('payment_details__supplier_offered_fare')
                )['total_supplier_offered_fare'] or 0

                supplier_published_fare_sum = user_bookings.aggregate(
                    total_supplier_published_fare=Sum('payment_details__supplier_published_fare')
                )['total_supplier_published_fare'] or 0

                staff_performance.append({
                    "billing_staff_name": f"{user.first_name} {user.last_name}",
                    "booking_count": booking_count,
                    "new_published_fare": new_published_fare_sum,
                    "new_offered_fare": new_offered_fare_sum,
                    "supplier_offered_fare": supplier_offered_fare_sum,
                    "supplier_published_fare": supplier_published_fare_sum,
                })

            return Response(
                {
                    "status": True,
                    "message": "Staff performance retrieved successfully.",
                    "data": staff_performance,
                    "errors": None
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {
                    "status": False,
                    "message": "Module missing or invalid module.",
                    "data": [],
                    "errors": {"details": "Invalid module provided."}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

def check_user_role(user):
    allowed_roles = {"finance", "admin", "super_admin"}    
    if not user.role or user.role.name not in allowed_roles:
        raise PermissionDenied("You are not allowed to perform this process.")

class AirlineVsSupplierPerformanceApi(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            check_user_role(request.user)
        except PermissionDenied as e:
            return Response(
                {
                    "status": False,
                    "message": str(e),
                    "data": [],
                    "errors": {"details": str(e)},
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        module = self.request.query_params.get('module', None)
        airline_code = self.request.query_params.get('airline_code', None)
        from_date = self.request.query_params.get('from_date', None)
        to_date = self.request.query_params.get('to_date', None)

        try:
            # Parse date filters
            from_timestamp = int(time.mktime(datetime.strptime(from_date, "%Y-%m-%d").timetuple())) if from_date else None
            to_date_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1) if to_date else None
            to_timestamp = int(time.mktime(to_date_dt.timetuple())) if to_date_dt else None
        except ValueError:
            return Response(
                {
                    "status": False,
                    "message": "Invalid date format. Use YYYY-MM-DD.",
                    "data": [],
                    "errors": {"details": "Date parsing error."}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if module == "flight":
            try:
                # Start with all the data, then filter based on parameters
                performance_data = FlightBookingItineraryDetails.objects.filter(booking__source="Offline")

                if from_timestamp:
                    performance_data = performance_data.filter(booking__booked_at__gte=from_timestamp)

                if to_timestamp:
                    performance_data = performance_data.filter(booking__booked_at__lte=to_timestamp)

                if airline_code:
                    performance_data = performance_data.filter(
                        flightbookingjourneydetails__flightbookingsegmentdetails__airline_code__icontains=airline_code
                    )

                # Annotate the required data
                performance_data = performance_data.values('vendor__name').annotate(
                    total_bookings=Count('booking__id', distinct=True),  # Count distinct bookings
                    cash_bookings=Count(
                        Case(
                            When(booking__payment_details__payment_type='wallet', then=Value(1)),
                            output_field=IntegerField()
                        )
                    ),
                    credit_card_bookings=Count(
                        Case(
                            When(booking__payment_details__payment_type__icontains='Credit Card - ', then=Value(1)),
                            output_field=IntegerField()
                        )
                    ),
                    total_new_published_fare=Sum('booking__payment_details__new_published_fare'),
                    total_new_offered_fare=Sum('booking__payment_details__new_offered_fare'),
                    total_supplier_offered_fare=Sum('booking__payment_details__supplier_offered_fare'),
                    total_supplier_published_fare=Sum('booking__payment_details__supplier_published_fare'),
                )

                # Replace None with 0 for fare fields
                structured_data = []
                for entry in performance_data:
                    structured_data.append({
                        "vendor_name": entry.get('vendor__name'),
                        "total_bookings": entry.get('total_bookings', 0),
                        "cash_bookings": entry.get('cash_bookings', 0),
                        "credit_card_bookings": entry.get('credit_card_bookings', 0),
                        "total_new_published_fare": entry.get('total_new_published_fare') or 0,
                        "total_new_offered_fare": entry.get('total_new_offered_fare') or 0,
                        "total_supplier_offered_fare": entry.get('total_supplier_offered_fare') or 0,
                        "total_supplier_published_fare": entry.get('total_supplier_published_fare') or 0,
                    })

                return Response(
                    {
                        "status": True,
                        "message": "Supplier performance data fetched successfully.",
                        "data": structured_data,
                        "errors": None,
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                return Response(
                    {
                        "status": False,
                        "message": f"An error occurred while fetching data: {str(e)}",
                        "data": [],
                        "errors": {"details": str(e)},
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        else:
            return Response(
                {
                    "status": False,
                    "message": "Invalid module. Only 'flight' module is supported.",
                    "data": [],
                    "errors": {"details": "Invalid module provided."},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

class SupplierVsAirlinePerformanceApi(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Extract query parameters
        module = request.query_params.get('module', None)
        supplier_id = request.query_params.get('supplier_id', None)
        from_date = request.query_params.get('from_date', None)
        to_date = request.query_params.get('to_date', None)

        try:
            # Parse date filters
            from_timestamp = int(time.mktime(datetime.strptime(from_date, "%Y-%m-%d").timetuple())) if from_date else None
            to_date_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1) if to_date else None
            to_timestamp = int(time.mktime(to_date_dt.timetuple())) if to_date_dt else None
        except ValueError:
            return Response(
                {
                    "status": False,
                    "message": "Invalid date format. Use YYYY-MM-DD.",
                    "data": [],
                    "errors": {"details": "Date parsing error."}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if module == "flight":
            try:
                segment_data = FlightBookingSegmentDetails.objects.filter(
                    journey__itinerary__booking__source="Offline"
                )
                if supplier_id:
                    segment_data = segment_data.filter(
                        journey__itinerary__vendor__id=supplier_id
                    )

                if from_timestamp:
                    segment_data = segment_data.filter(
                        journey__itinerary__booking__booked_at__gte=from_timestamp
                    )
                if to_timestamp:
                    segment_data = segment_data.filter(
                        journey__itinerary__booking__booked_at__lte=to_timestamp
                    )

                segment_data = segment_data.values(
                    'journey__itinerary__vendor__name',  
                    'airline_code',  
                    'airline_name'  
                ).annotate(
                    total_bookings=Count('journey__itinerary__booking', distinct=True),
                    cash_bookings=Count(
                        Case(
                            When(
                                journey__itinerary__booking__payment_details__payment_type='wallet',
                                then=Value(1)
                            ),
                            output_field=IntegerField()
                        )
                    ),
                    card_bookings=Count(
                        Case(
                            When(
                                journey__itinerary__booking__payment_details__payment_type__icontains='Credit Card - ',
                                then=Value(1)
                            ),
                            output_field=IntegerField()
                        )
                    ),
                    total_new_published_fare=Sum(
                        'journey__itinerary__booking__payment_details__new_published_fare'
                    ),
                    total_new_offered_fare=Sum(
                        'journey__itinerary__booking__payment_details__new_offered_fare'
                    ),
                    total_supplier_offered_fare=Sum(
                        'journey__itinerary__booking__payment_details__supplier_offered_fare'
                    ),
                    total_supplier_published_fare=Sum(
                        'journey__itinerary__booking__payment_details__supplier_published_fare'
                    ),
                )

                # Structure the data
                structured_data = []
                for entry in segment_data:
                    structured_data.append({
                        "supplier_name": entry.get('journey__itinerary__vendor__name'),
                        "airline_code": entry.get('airline_code'),
                        "airline_name": entry.get('airline_name'),
                        # "total_bookings": entry.get('total_bookings', 0),
                        "cash_bookings": entry.get('cash_bookings', 0),
                        "card_bookings": entry.get('card_bookings', 0),
                        "total_new_published_fare": entry.get('total_new_published_fare') or 0,
                        "total_new_offered_fare": entry.get('total_new_offered_fare') or 0,
                        "total_supplier_offered_fare": entry.get('total_supplier_offered_fare') or 0,
                        "total_supplier_published_fare": entry.get('total_supplier_published_fare') or 0,
                    })

                return Response(
                    {
                        "status": True,
                        "message": "Supplier vs Airline performance data fetched successfully.",
                        "data": structured_data,
                        "errors": None,
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                return Response(
                    {
                        "status": False,
                        "message": f"An error occurred while fetching data: {str(e)}",
                        "data": [],
                        "errors": {"details": str(e)},
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        else:
            return Response(
                {
                    "status": False,
                    "message": "Invalid module. Only 'flight' module is supported.",
                    "data": [],
                    "errors": {"details": "Invalid module provided."},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

def payment_type_chart(kwargs):
    year = kwargs.get("year")
    month = kwargs.get("month")
    filters = {}

    yr, mth = int(year), int(month)
    num_days = calendar.monthrange(yr, mth)[1]
    date_list = [
        (datetime(yr, mth, day)).strftime("%Y-%m-%d") for day in range(1, num_days + 1)
    ]
    formatted_dates = [datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b-%Y") for date in date_list]

    # Dictionary to hold aggregated data per date
    aggregated_data = defaultdict(lambda: {
        "date": None,
        "recharge_success_count": 0,
        "recharge_failure_count": 0,
        "booking_success_count": 0,
        "booking_failure_count": 0
    })

    for date in date_list:
        date_timestart = datetime.strptime(date, "%Y-%m-%d")
        date_timestart_epoch = int(date_timestart.timestamp())
        date_timeend = (
            datetime.strptime(date, "%Y-%m-%d")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        date_timeend_epoch = int(date_timeend.timestamp())

        filters["created_at__range"] = [date_timestart_epoch, date_timeend_epoch]

        # Process data for each payment type
        for payment_type in ['recharge', 'booking']:
            filters["payment_types"] = payment_type
            payments = Payments.objects.filter(**filters)

            success_count = payments.filter(status='paid').count()
            failure_count = payments.filter(status='unpaid').count()

            # Update aggregated data for the current date
            if payment_type == 'recharge':
                aggregated_data[date]["recharge_success_count"] += success_count
                aggregated_data[date]["recharge_failure_count"] += failure_count
            elif payment_type == 'booking':
                aggregated_data[date]["booking_success_count"] += success_count
                aggregated_data[date]["booking_failure_count"] += failure_count
            
            aggregated_data[date]["date"] = date

    # Convert aggregated data to a list
    final_list = list(aggregated_data.values())

    data = {
        "date_list": formatted_dates,
        "data_list": final_list
    }
    return data

class PaymentGatewayStackedChart(APIView):
    permission_classes =  [IsAuthenticated,]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        module = request.query_params.get("module", None)
        month = request.query_params.get("month", None)
        year = request.query_params.get("year", None)

        if not module:
            return Response(
                {
                    "status": False,
                    "message": "Module parameter is required.",
                    "data": [],
                    "errors": {"details": "Invalid or missing module."}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not month or not year:
            return Response(
                {
                    "status": False,
                    "message": "Month and year parameters are required.",
                    "data": [],
                    "errors": {"details": "Invalid or missing date parameters."}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        kwargs = {
            "module":module,
            "month": month,
            "year": year,
        }
        payment_chart_results = payment_type_chart(kwargs)

        return Response(
            {
                "status": True,
                "message": f"{module} data retrieved successfully.",
                "data": payment_chart_results,
                "errors": None
            },
            status=status.HTTP_200_OK,
        )