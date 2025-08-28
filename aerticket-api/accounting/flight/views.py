from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
import requests
from tools.easy_link.xml_restructure import XMLData
from integrations.general.models import Integration
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from users.models import Organization
from rest_framework import generics
from rest_framework.generics import RetrieveAPIView,ListAPIView,UpdateAPIView
from .models import *
from .serializers import *
from django.db.models import Q,Count, Max
from rest_framework.pagination import PageNumberPagination
from rest_framework import viewsets
from datetime import datetime
import pytz
from users.models import Country,LookupAirline
# Create your views here.


class AllAirLines(generics.ListCreateAPIView):
    queryset = LookupAirline.objects.all()
    serializer_class = LookUpAirlineSerializersList
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        search = self.request.query_params.get('search', None)
        queryset = super().get_queryset() 
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
        return queryset
    
    

class AllSupplierIntegrations(generics.ListCreateAPIView):
    queryset = SupplierIntegration.objects.all()
    serializer_class = SupplierIntegrationSerializers
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):        
        search = self.request.query_params.get('search', None)
        queryset = self.queryset.all()
        if search:
            queryset = queryset.filter(Q(name__icontains=search))
        return queryset
    
    

class AllCountryViewSet(generics.ListCreateAPIView):
    queryset = Country.objects.all()
    serializer_class = CountrySerializers
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
class CustomPageNumberPagination(PageNumberPagination):
    def __init__(self, page_size=15, *args, **kwargs):
        self.page_size=page_size
        return super().__init__(*args,**kwargs)
    page_size_query_param = 'page_size'
    max_page_size = 100


class DealManagement(viewsets.ModelViewSet):
    permission_classes=[IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    queryset = AirlineDeals.objects.all()
    serializer_class = AirlineDealsSerializers

    def list(self, request, *args, **kwargs):
            search_key = request.query_params.get('search_key', None)
            page_size = request.query_params.get('page_size', 15)

            queryset = AirlineDeals.objects.all()
            if search_key:
                queryset = AirlineDeals.objects.filter(
                        Q(airline__name__icontains=search_key) | 
                        Q(source__icontains=search_key) |
                        Q(destination__icontains=search_key) | 
                        Q(supplier__name__icontains=search_key)
                    )
            total_data = len(queryset)
            paginator = CustomPageNumberPagination(page_size=page_size)
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            serializer = AirlineDealsSerializers(paginated_queryset, many=True)
            data = {
                    "results": serializer.data,
                    "total_pages": paginator.page.paginator.num_pages,
                    "current_page": paginator.page.number,
                    "next_page": paginator.get_next_link(),
                    "prev_page": paginator.get_previous_link(),
                    "total_data":total_data,
                    "page_size":page_size
                }
            return Response(data)

    def create(self, request, *args, **kwargs):
        data = request.data
        data['modified_by'] = request.user.id
        data['valid_till'] = self.convert_to_timestamp(data.get('valid_till'))
        # if data.get('yq_after_valid_date',None):
        #     data['yq_after_valid_date'] = self.convert_to_timestamp(data.get('yq_after_valid_date'))
            
        # if data.get('yr_after_valid_date',None):
        #     data['yr_after_valid_date'] = self.convert_to_timestamp(data.get('yr_after_valid_date'))
            
        return super(DealManagement, self).create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        data = request.data
        data['modified_by'] = request.user.id
        data['valid_till'] = self.convert_to_timestamp(data.get('valid_till'))
        
        # if data.get('yq_after_valid_date',None):
        #     data['yq_after_valid_date'] = self.convert_to_timestamp(data.get('yq_after_valid_date'))
            
        # if data.get('yr_after_valid_date',None):
        #     data['yr_after_valid_date'] = self.convert_to_timestamp(data.get('yr_after_valid_date'))
        return super(DealManagement, self).update(request, *args, **kwargs)

    def convert_to_timestamp(self, date_str):
        if date_str:
            if isinstance(date_str, int):
                return date_str  
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000) 
            except ValueError:
                raise serializers.ValidationError(f"Invalid date format: {date_str}")
        return None
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.hard_delete()

        
        return Response({"message": "Deal deleted successfully!"}, status=status.HTTP_204_NO_CONTENT)

class SupplierDealManagementView(viewsets.ModelViewSet):
    permission_classes=[IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    queryset = SupplierDealManagement.objects.all()
    serializer_class = SupplierDealManagementSerializers

    def list(self, request, *args, **kwargs):
            search_key = request.query_params.get('search_key', None)
            page_size = request.query_params.get('page_size', 15)

            queryset = SupplierDealManagement.objects.all().order_by('-created_at')
            if search_key:
                queryset = SupplierDealManagement.objects.filter(
                        Q(airline__name__icontains=search_key) | 
                        Q(source__icontains=search_key) |
                        Q(destination__icontains=search_key) | 
                        Q(supplier__name__icontains=search_key)
                    )
            total_data = len(queryset)
            paginator = CustomPageNumberPagination(page_size=page_size)
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            serializer = SupplierDealManagementSerializers(paginated_queryset, many=True)
            data = {
                    "results": serializer.data,
                    "total_pages": paginator.page.paginator.num_pages,
                    "current_page": paginator.page.number,
                    "next_page": paginator.get_next_link(),
                    "prev_page": paginator.get_previous_link(),
                    "total_data":total_data,
                    "page_size":page_size
                }
            return Response(data)

    def create(self, request, *args, **kwargs):
        data = request.data
        data['modified_by'] = request.user.id
        data['valid_till'] = self.convert_to_timestamp(data.get('valid_till'))
        # if data.get('yq_after_valid_date',None):
        #     data['yq_after_valid_date'] = self.convert_to_timestamp(data.get('yq_after_valid_date'))
            
        # if data.get('yr_after_valid_date',None):
        #     data['yr_after_valid_date'] = self.convert_to_timestamp(data.get('yr_after_valid_date'))
            
        return super(SupplierDealManagementView, self).create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        data = request.data
        data['modified_by'] = request.user.id
        data['valid_till'] = self.convert_to_timestamp(data.get('valid_till'))
        
        # if data.get('yq_after_valid_date',None):
        #     data['yq_after_valid_date'] = self.convert_to_timestamp(data.get('yq_after_valid_date'))
            
        # if data.get('yr_after_valid_date',None):
        #     data['yr_after_valid_date'] = self.convert_to_timestamp(data.get('yr_after_valid_date'))
        return super(SupplierDealManagementView, self).update(request, *args, **kwargs)
    
    def convert_to_timestamp(self, date_str):
        if date_str:
            if isinstance(date_str, int):
                return date_str  
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000) 
            except ValueError:
                raise serializers.ValidationError(f"Invalid date format: {date_str}")
        return None
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.hard_delete()

        
        return Response({"message": "Deal deleted successfully!"}, status=status.HTTP_204_NO_CONTENT)

class FlightSupplierFiltersView(APIView):
    
    def get(self, request):
        try:
            supplier_id = request.query_params.get('supplier_id', None)
            page_size = request.query_params.get('page_size', 15)
            if supplier_id:
                queryset = FlightSupplierFilters.objects.filter(supplier=supplier_id).order_by("created_at")
                total_data = len(queryset)
                paginator = CustomPageNumberPagination(page_size=page_size)
                paginated_queryset = paginator.paginate_queryset(queryset, request)

            else:
                queryset = FlightSupplierFilters.objects.all()
                total_data = len(queryset)
                paginator = CustomPageNumberPagination(page_size=page_size)
                paginated_queryset = paginator.paginate_queryset(queryset, request)
            serializer = FlightSupplierFiltersSerializerGet(paginated_queryset, many=True)
            data = {
                    "results": serializer.data,
                    "total_pages": paginator.page.paginator.num_pages,
                    "current_page": paginator.page.number,
                    "next_page": paginator.get_next_link(),
                    "prev_page": paginator.get_previous_link(),
                    "total_data":total_data,
                    "page_size":page_size
                }
            return Response(data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def post(self, request):
        serializer = FlightSupplierFiltersSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response("Data Created Successfully", status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request):
        filter_id = request.data.get("id")
        filter_obj = FlightSupplierFilters.objects.filter(id = filter_id)
        filter_obj.delete()
        return Response({"message": "Data Deleted Successfully"}, status=status.HTTP_201_CREATED)

    def patch(self, request):
        try:
            id = request.data.get('id')
            instance = FlightSupplierFilters.objects.get(id=id)
        except FlightSupplierFilters.DoesNotExist:
            return Response({"error": "Not Found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = FlightSupplierFiltersSerializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response("Updated Successfully", status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
