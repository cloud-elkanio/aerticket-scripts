import threading
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from datetime import datetime, timedelta

from tools.kafka_config.config import invoke
from .models import *
from .serializers import *
from bookings.flight.views import CustomPageNumberPagination
from rest_framework import status
import pandas as pd

class HotelQueuesView(APIView):
    authentication_classes = []
    permission_classes = []
    def get(self, request):
        try:
            page_size = int(request.query_params.get('page_size', 15))
            search =  request.query_params.get('search', None)
            from_date = request.query_params.get('from_date', None)
            to_date = request.query_params.get('to_date', None)
            search_type = request.query_params.get('search_type', None)
            booking_status = request.query_params.get('booking_status', None)
            country_name = request.query_params.get('country_name', None)
            filter_condition = Q()
            if booking_status:
                filter_condition &= Q(status = booking_status)
            if search and search_type:
                filter_condition &= (Q(display_id = search))

            if from_date and to_date and not (search and search_type in ['booking_id', 'pnr']):
                from_date_obj = datetime.strptime(from_date, "%Y-%m-%d")
                to_date_obj = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
                from_date_epoch = int(from_date_obj.timestamp())
                to_date_epoch = int(to_date_obj.timestamp())
                filter_condition &= Q(created_at__range=[from_date_epoch,to_date_epoch])

            query_set = HotelBooking.objects.filter(filter_condition)
            serializer = HotelBookingSerializer(query_set , many=True)
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
            return Response({"data":data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)

def send_mail(content):
    thread = threading.Thread(target=invoke, kwargs={
                                                "event":"Hotel_Confirmation",
                                                "number_list":[], 
                                                "email_list" : ['jijo.thomas@elkanio.com'],
                                                "data" :{
                                                "country_name": 'India',
                                                "user_email": 'user_email',
                                                "booking_id": 'booking_id',
                                                "booking_date": 'booking_date',
                                                "name": content,
                                                "hotel_name": 'hotel_name',
                                                "check_in_date": 'check_in_date',
                                                "check_out_date":'check_out_date',
                                                "room_type":"room_type",
                                                "confirmed":'confirmed'
                                                }
                                                })
    thread.start()

def sync_grn():
    print("grn sync started...")
    try:
        send_mail('grn sync started')
        GrnHotel.objects.all().delete()
        GrnDestination.objects.all().delete()
        GrnCity.objects.all().delete()
        print("started reading hotels...")
        send_mail('started reading hotels...')
        # hotel_df = pd.read_csv("https://cdn.grnconnect.com/static-assets/static-data/latest/hotel_master.tsv.bz2" ,sep="\t", compression="bz2")
        hotel_df = pd.read_csv("hotel_master (3).tsv.bz2" ,sep="\t", compression="bz2")
        send_mail("hotels completed....")
        city_df = pd.read_csv("https://cdn.grnconnect.com/static-assets/static-data/new-codes/city_master.tsv.bz2",sep="\t", compression="bz2")
        send_mail("cities completed....")
        destination_df = pd.read_csv("https://cdn.grnconnect.com/static-assets/static-data/new-codes/location_master.tsv.bz2",sep="\t", compression="bz2")
        send_mail("destinations completed....")
        location_map = pd.read_csv("https://cdn.grnconnect.com/static-assets/static-data/new-codes/hotel_location_city_map.tsv.bz2",sep="\t", compression="bz2")
        # hotel_df['Hotel Code'] = hotel_df.apply(lambda row: row['Hotel Code'].replace('H!',''), axis=1)
        # city_df['City Code'] = city_df.apply(lambda row: row['City Code'].replace('C!',''), axis=1)
        # destination_df['Destination Code'] = destination_df.apply(lambda row: row['Destination Code'].replace('D!',''), axis=1)
        # city_df['Destination Code'] = city_df.apply(lambda row: row['Destination Code'].replace('D!',''), axis=1)
        # hotel_df['Destination Code'] = hotel_df.apply(lambda row: row['Destination Code'].replace('D!',''), axis=1)
        # hotel_df['City Code'] = hotel_df.apply(lambda row: row['City Code'].replace('C!',''), axis=1)
        send_mail("datas fetched....")

        # Convert DataFrame to model instances
        destinations = [
            GrnDestination(code=row['Location Code'], name=row['Location Name'])
            for _, row in destination_df.iterrows()
        ]

        # Bulk insert
        GrnDestination.objects.bulk_create(destinations, ignore_conflicts=True)

        destination_objects = {dest.code:dest for dest in GrnDestination.objects.all()}

        destination_dict = {str(row['City Code']):destination_objects.get(str(row['Location Code'])) for _, row in location_map.iterrows()}
        send_mail("destinations inserted")

        # Convert DataFrame to model instances
        # import pdb;pdb.set_trace()
        cities = [
            GrnCity(
                code=row['City Code'],
                name=row['City Name'],
                destination=destination_dict.get(str(row['City Code']))  # Link to FK
            )
            for _, row in city_df.iterrows()
        ]

        # Bulk insert
        GrnCity.objects.bulk_create(cities, ignore_conflicts=True)

        # city_dict = {row[]: row[] for _, row in location_map.iterrows()}
        send_mail("cities inserted")

        city_objects = {city.code:city for city in GrnCity.objects.all()}

        hotel_destination_map = {str(row['Hotel Code']):destination_objects.get(str(row['Location Code']))
                             for _, row in location_map.iterrows()}

        # Convert DataFrame to model instances
        hotels = [
            GrnHotel(
                code=row['Hotel Code'],
                name=row['Hotel Name'],
                city=city_objects.get(str(row['City Code'])),  # Link to FK
                destination=hotel_destination_map.get(str(row['Hotel Code']))  # Link to FK
            )
            for _, row in hotel_df.iterrows()
        ]

        # Bulk insert
        # GrnHotel.objects.bulk_create(hotels, ignore_conflicts=True)
        GrnHotel.objects.bulk_create(hotels, ignore_conflicts=True,batch_size =100)
        send_mail("hotels inserted")
        send_mail('grn sync completed')
    except Exception as e:
        import traceback
        send_mail(str(e))
        send_mail(traceback.format_exc())

class GrnSyncView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        print("here")
        import threading
        task_thread = threading.Thread(target=sync_grn)
        task_thread.start()
        print("here 2")
        return Response({"success":True }, status=status.HTTP_200_OK)
            