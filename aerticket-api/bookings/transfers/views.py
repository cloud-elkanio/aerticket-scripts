from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from .models import *
from rest_framework.response import Response
from .serializers import *
from bookings.flight.views import CustomPageNumberPagination
from datetime import datetime, timedelta
import json

class TransfersBookingQueue(APIView):
    def get(self,request):
        page_size = int(request.query_params.get('page_size', 15))
        search =  request.query_params.get('search', None)
        from_date = request.query_params.get('from_date', None)
        to_date = request.query_params.get('to_date', None)
        search_type = request.query_params.get('search_type', None)
        booking_status = request.query_params.get('booking_status', None)
        country_name = request.query_params.get('country_name', None)
        filter_condition = Q()

        if booking_status == "confirmed":
            filter_condition &= Q(status="Confirmed")
        elif booking_status == "failed":
            filter_condition &= (Q(status="Failed"))
        elif booking_status == "others":
            filter_condition &= Q(status__in=["Enquiry", "In-Progress"])
        elif booking_status == "cancelled":
            filter_condition &= Q(status__in=["Cancelled", "Cancellation-Requested"])
        if search_type and search:
            filter_condition &= (Q(display_id = search))
        if country_name:
            filter_condition &= Q(user_id__organization__organization_country__lookup__country_name=country_name)
        if from_date and to_date and not (search and search_type in ['booking_id']):
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d")
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            from_date_epoch = int(from_date_obj.timestamp())
            to_date_epoch = int(to_date_obj.timestamp())
            filter_condition &=  Q(created_at__gte = from_date_epoch, created_at__lte=to_date_epoch)

        query_set = TransferBooking.objects.filter(filter_condition).order_by('-display_id')
        serializer = TransfersBookingQueueSerializer(query_set , many=True)
        paginator = CustomPageNumberPagination()
        paginated_queryset = paginator.paginate_queryset(serializer.data, request)
        data = {
             "results": paginated_queryset,
             "total_pages": paginator.page.paginator.num_pages,
             "current_page": paginator.page.number,
             "next_page":paginator.get_next_link(),
             "prev_page":paginator.get_previous_link(),
             "total_data":len(serializer.data),
             "page_size":page_size
        }
        return Response(data)

