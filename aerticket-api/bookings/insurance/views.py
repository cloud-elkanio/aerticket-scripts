from django.shortcuts import render

from rest_framework.views import APIView
from django.db.models import Q
from rest_framework.response import Response
from datetime import datetime, timedelta
from .models import *
from .serializers import *
from bookings.flight.views import CustomPageNumberPagination

class InsuranceQueuesView(APIView):
    permission_classes = []
    def get(self, request):
        page_size = request.query_params.get('page_size')
        search =  request.query_params.get('search', None)
        from_date = request.query_params.get('from_date', None)
        to_date = request.query_params.get('to_date', None)
        search_type = request.query_params.get('search_type', None)
        booking_status = request.query_params.get('booking_status', None)
        country_name = request.query_params.get('country_name', None)
        filter_condition = Q()

        if booking_status == "confirmed":
            filter_condition &= Q(status = "Confirmed")
        elif booking_status == "failed":
            filter_condition &= (Q(status="Ticketing-Failed"))
        elif booking_status == "others":
            filter_condition &= Q(status__in=["Enquiry", "Ticketing-Initiated"])
        if search_type == 'booking_id' and search:
            filter_condition &= (Q(display_id = search))
        if country_name:
            filter_condition &= Q(user__organization__organization_country__lookup__country_name=country_name)
        if from_date and to_date and not (search and search_type in ['booking_id']):
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d")
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            from_date_epoch = int(from_date_obj.timestamp())
            to_date_epoch = int(to_date_obj.timestamp())
            filter_condition &=  Q(created_at__gte = from_date_epoch, created_at__lte=to_date_epoch)
        query_set = InsuranceBooking.objects.filter(filter_condition).order_by('-display_id')
        serializer = BusBookingQueueSerializer(query_set , many=True)
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

