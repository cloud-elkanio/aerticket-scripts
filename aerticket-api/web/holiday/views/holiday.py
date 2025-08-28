from pms.holiday_app.models import (
    HolidaySKU,
    HolidaySKUPrice,
    HolidaySKUTheme,
    HolidaySKUImage,
    HolidayThemeMaster,
    HolidaySKUInclusion,
    LookUpHolidayEnquiryStatus,
    HolidayEnquiry,
    HolidayEnquiryHistory
   
    )
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from users.models import Country
from rest_framework_simplejwt.authentication import JWTAuthentication
from ..serializers import *
from django.db.models import Max,Prefetch
from rest_framework.permissions import AllowAny
from decimal import Decimal

import numpy as np
from scipy.stats import norm
from django.db.models import Q
from ..models import *

from django.db.models import Q
from functools import reduce
from operator import or_
from rest_framework.views import APIView

from django.db.models import Max, Min
from urllib.parse import unquote
from django.db.models.functions import Cast
from django.db.models import IntegerField
from api.settings import MEDIA_URL as aws_url
from datetime import datetime
from tools.kafka_config.config import invoke
import threading

# class HolidaySKUPredictView(APIView):
#     def get_queryset(self):
#         # Return all Active SKUs by default
#         return HolidaySKU.objects.filter(status="Active")

#     def filter_queryset(self, query):
#         # Filter products based on the search query
#         return self.get_queryset().filter(
#             Q(name__icontains=query) |
#             Q(place__icontains=query) |
#             Q(location__icontains=query) |
#             Q(country__country_name__icontains=query)
#         )
#     def filter_themes(self, query):
#         # Filter themes based on the query and return matching SKUs
#         theme_matches = HolidaySKUTheme.objects.filter(
#             Q(theme_id__name__icontains=query) |
#             Q(sku_id__country__country_name__icontains=query) |
#             Q(sku_id__place__icontains=query)
#         ).values_list('sku_id', flat=True)
#         return self.get_queryset().filter(id__in=theme_matches)

#     def list(self, request, *args, **kwargs):
#         query = self.request.query_params.get('search', '').strip()
#         if not query:
#             return Response({"error": "No search query provided."}, status=400)

#         # Query SKUs directly based on search query
#         holiday_skus = self.filter_queryset(query)

#         # Search for themes matching the query
#         themes = HolidaySKUTheme.objects.filter(
#             Q(theme_id__name__icontains=query) |
#             Q(sku_id__country__country_name__icontains=query) |
#             Q(sku_id__place__icontains=query)
#         ).values('theme_id__name', 'theme_id').distinct()[:2]

#         # Get SKUs linked to themes
#         theme_skus = HolidaySKUTheme.objects.filter(
#             theme_id__in=themes.values_list('theme_id', flat=True)
#         ).values_list('sku_id', flat=True)
        
#         # Fetch active SKUs based on themes
#         theme_products = self.get_queryset().filter(id__in=theme_skus)

#         # Combine SKUs from direct query and theme-based query
#         products = holiday_skus | theme_products
#         products = products.distinct()[:2]  # Ensure unique and limit to top 2 products

#         # Collect top 2 unique places and countries
#         places = (
#             products.values_list('place', flat=True).distinct()[:2]
#         )
#         countries = (
#             products.values_list('country__country_name', flat=True).distinct()[:2]
#         )

#         # Prepare the response
#         search_results = {
#             'places': [{'place': place} for place in places if place],  # Non-null places
#             'countries': [{'country_name': country} for country in countries if country],  # Unique countries
#             'themes': list(themes),  # Top 2 themes
#             'products': HolidaySKUSerializer(products, many=True).data,  # Top 2 products
#         }

#         return Response(search_results)

#     def get(self, request, *args, **kwargs):
#         # Handle GET request by calling the list method
#         return self.list(request, *args, **kwargs)





    # def get_queryset(self):
    #     query = self.request.query_params.get('search', '')
    #     if not query:
    #         return HolidaySKU.objects.none()  
        
    #     return HolidaySKU.objects.filter(
    #         Q(name__icontains=query) |
    #         Q(place__icontains=query) |
    #         Q(location__icontains=query) |
    #         Q(country__country_name__icontains=query),  
    #         status="Active"
    #     )
        # return HolidaySKU.objects.filter(name__icontains=query,status="Active")
from collections import OrderedDict

class HolidaySKUPredictView(APIView):
    authentication_classes = []
    permission_classes = []
    def get_queryset(self):
        # Return all Active SKUs by default
        return HolidaySKU.objects.filter(status="Active")

    def filter_queryset(self, query):
        # Filter products based on the search query
        return self.get_queryset().filter(
            Q(name__icontains=query) |
            Q(place__icontains=query) |
            Q(location__icontains=query) |
            Q(country__country_name__icontains=query)|
            Q(holidayskutheme__theme_id__name__icontains=query)
        )

    
    def list(self, request, *args, **kwargs):
        query = self.request.query_params.get('search', '').strip()
        if not query:
            return Response({"error": "No search query provided."}, status=400)

        holiday_skus = self.filter_queryset(query)
        if not holiday_skus.exists():
            return Response([])

        # Fetch themes related to the holiday_skus
        theme_skus = HolidaySKUTheme.objects.filter(
            sku_id__in=holiday_skus.values_list('id', flat=True)
        ).values_list('theme_id', flat=True)
        themes = HolidayThemeMaster.objects.filter(
            id__in=theme_skus
        ).distinct().values('id', 'name')
       
        theme_products = HolidaySKU.objects.filter(
            id__in=HolidaySKUTheme.objects.filter(theme_id__in=[theme['id'] for theme in themes]).values_list('sku_id', flat=True),
            status="Active"
        )
        print(theme_products)
        places = list(
            set(holiday_skus.filter(place__icontains=query).values_list('place', flat=True)) |
            set(theme_products.filter(place__icontains=query).values_list('place', flat=True))
        )

        countries = list(
            set(
                country
                for sku in holiday_skus
                for country in sku.country.filter(country_name__icontains=query).values_list('country_name', flat=True)
            ) | set(
                country
                for sku in theme_products
                for country in sku.country.filter(country_name__icontains=query).values_list('country_name', flat=True)
            )
        )

        # Fetch matching products based on query
        matching_products = holiday_skus.filter(
            Q(name__icontains=query) |
            Q(place__icontains=query) |
            Q(location__icontains=query) |
            Q(country__country_name__icontains=query)
        )

        # Limit results to top 2 for places, countries, themes, and products
        if len(places) > 2:
            places = places[:2]
        if len(countries) > 2:
            countries = countries[:2]
        if len(themes) > 2:
            matching_themes =themes[:2]
        if matching_products.count() > 2:
            matching_products = matching_products[:2]

        # Prepare the response data
        response_data = []

        # Add places to the response
        if places:
            response_data.extend([{'type': 'place', 'name': place} for place in places])

        # Add countries to the response
        if countries:
            response_data.extend([{'type': 'country', 'name': country} for country in countries])

        # Add themes to the response
        if matching_themes:
            response_data.extend([{'type': 'theme', 'id': theme['id'], 'name': theme['name']} for theme in matching_themes])

        # Add unique products to the response
        if matching_products:
            # Use an OrderedDict to remove duplicate products
            unique_products = OrderedDict()
            for product in matching_products:
                unique_products[product.id] = {
                    'type': 'product',
                    'id': product.id,
                    'name': product.name,
                    'location': product.location,
                    'countries': [country.country_name for country in product.country.all()],
                    'slug': product.slug,
                    'place': product.place,
                }
            response_data.extend(unique_products.values())

        return Response(response_data)
    def get(self, request, *args, **kwargs):
        # Handle GET request by calling the list method
        return self.list(request, *args, **kwargs)

class SingleHolidaySKUView(APIView):  
    authentication_classes=[JWTAuthentication]
    permission_classes=[IsAuthenticated]
    def get(self, request, slug):
        try:
            slug = slug
            user=request.user
            country_id = user.base_country.id if hasattr(user, 'base_country') and user.base_country else None
            country_id = country_id

            if not slug and not country_id:
                return Response({'error': 'slug and country_id parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
            product_price_instances = HolidaySKUPrice.objects.filter(sku_id__slug=slug,country_id=country_id)

            result_data = []
            for product_price_instance in product_price_instances:
                product_serializer = HolidaySkuGetSerializer(product_price_instance.sku_id)
                product_data = product_serializer.data
                
                price_serializer = HolidaySKUPriceSerializer(product_price_instance)
                base_price = Decimal(price_serializer.data.get('price', '0') or '0')
                company_markup = Decimal(price_serializer.data.get('company_markup', '0') or '0')
                if user.organization == product_price_instance.sku_id.organization_id:
                    product_data['price'] = base_price 
                else:
                    product_data['price'] = base_price + company_markup

                theme_instances = HolidaySKUTheme.objects.filter(sku_id=product_price_instance.sku_id)
             
                theme_serializer = HolidayThemeSerializer(theme_instances, many=True)
               
                theme_data = theme_serializer.data
          
                image_instances = HolidaySKUImage.objects.filter(sku_id=product_price_instance.sku_id)
                image_data = []
              
                for image_instance in image_instances:
                    image_url = aws_url+str(image_instance.gallery_id.url)
                    # image_url = image_urls.split("/media", 1)[-1]
                 
                    image_data.append({'id': str(image_instance.id), 'image_url': image_url})
                product_data['images'] = image_data
       
                theme_names = [{ 'id': theme['id'], 'image_url':f"{aws_url}{str(HolidayThemeMaster.objects.get(id=theme['theme_id']).icon_url.url)}", 'name':HolidayThemeMaster.objects.get(id=theme['theme_id']).name} for theme in theme_data]

                # theme_names = [{'id': theme['id'], 'image_url':f"{aws_url}{str(Theme.objects.get(id=theme['theme']).image_url.image_url)}"} for theme in theme_data]
                product_data['themes'] = theme_names

                # Add SKU inclusions
                inclusions = HolidaySKUInclusion.objects.filter(sku_id=product_price_instance.sku_id).first()
                product_data['sku_inclusions'] = {
                    'flight': inclusions.flight if inclusions else False,
                    'hotel': inclusions.hotel if inclusions else False,
                    'transfer': inclusions.transfer if inclusions else False,
                    'meals': inclusions.meals if inclusions else False,
                    'visa': inclusions.visa if inclusions else False,
                    'sight_seeing': inclusions.sight_seeing if inclusions else False
                }

                result_data.append(product_data)
            return Response({'products': result_data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HolidayEnquiryView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes=[IsAuthenticated]

    def post(self, request):
        user = request.user

        if user.base_country is None:
            return Response({"message": "User does not have a base country set."}, status=status.HTTP_400_BAD_REQUEST)

        country_code = user.base_country.lookup.country_code
        try:
            country_obj = Country.objects.get(lookup__country_code=country_code)  # Corrected lookup query
            c_id = country_obj.id
        except Country.DoesNotExist:
            return Response({"message": "Country not found."}, status=status.HTTP_404_NOT_FOUND)

        name = request.data.get('name')
        travel_date_str = request.data.get('date_of_travel')

        if travel_date_str is None:
            return Response({"message": "Date of travel is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            travel_date_obj = datetime.strptime(travel_date_str, "%d/%m/%Y")
        except ValueError:
            return Response({"message": "Invalid date format. Please use DD/MM/YYYY."}, status=status.HTTP_400_BAD_REQUEST)

        formatted_date_str = travel_date_obj.strftime("%Y-%m-%d")
        request.data['date_of_travel'] = formatted_date_str

        date_of_travel = request.data.get('date_of_travel')
        package_id = request.data.get('holiday_id')

        try:
            package_instance = HolidaySKU.objects.get(id=package_id)
        except HolidaySKU.DoesNotExist:
            return Response({"message": "Holiday package not found."}, status=status.HTTP_404_NOT_FOUND)

        package_name = package_instance.name
        try:
            package_price_instance = HolidaySKUPrice.objects.filter(sku_id=package_id, country_id=c_id)
            package_price = package_price_instance
        except HolidaySKUPrice.DoesNotExist:
            return Response({"message": "Package price not found for the selected country."}, status=status.HTTP_404_NOT_FOUND)

        status_name = "Enquiry received"
        status_instance, created = LookUpHolidayEnquiryStatus.objects.get_or_create(name=status_name)
        request.data['status'] = status_instance.id
        request.data['user'] = user.id  

        serializer = HolidayEnquirySerializerCreate(data=request.data, context={'request': request})
        if serializer.is_valid():
            enquiry = serializer.save()
            count = HolidayEnquiry.objects.all().count() + 1
            count = '{:04d}'.format(count)
            reference_id = f"BTA-HOLIDAY-{count}"
            enquiry.enquiry_ref_id = reference_id
            enquiry.save()

            HolidayEnquiryHistory.objects.create(
                holiday_enquiry_id=enquiry,
                status=status_instance,
                updated_by=request.user
            )
            #---------------START-----------------------------------------------------------------------------------------------------
            holiday_obj = HolidaySKU.objects.get(id = request.data.get('holiday_id'))
            holiday_name = holiday_obj.name
            data_list = {
                        "agent_name":request.user.first_name, 
                        "reference_id":reference_id,
                        "name":request.data['name'],
                        "holiday_name": holiday_name,
                        "email": request.data['email'],
                        "phone":request.data['phone'],
                        "date_of_travel":request.data['date_of_travel'], 
                        "travellers":request.data['pax_count'], 
                        "country_name":request.user.base_country.lookup.country_name
                        }
            
            email_data = [request.data['email']]
            thread = threading.Thread(target=invoke, kwargs={
                        "event":"Holiday_Enquiry", 
                        "email_list":email_data,
                        "data" :data_list
                        })
            thread.start()

            # invoke(event='Holiday_Enquiry',email_list=email_data, data = data_list)

            #---------------END-----------------------------------------------------------------------------------------------------


            return Response({"message": "Successfully saved", "status": True}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def find_country(self, country_id):
        try:
            country = Country.objects.get(country_code=country_id)
            return country.lookup.country_name
        except Country.DoesNotExist:
            try:
                country = Country.objects.get(lookup__calling_code=country_id)
                return country.lookup.country_name
            except Country.DoesNotExist:
                return None
        except Exception as e:
            return str(e)

class SearchHolidayView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def get_filtered_queryset(self, request, filters, country_id):
        """Build the filtered queryset."""
       
        queryset = HolidaySKU.objects.filter(
        holidayskuprice__country_id_id=country_id,
        status="Active"
    ).prefetch_related(
        Prefetch(
            'holidayskutheme',
            queryset=HolidaySKUTheme.objects.select_related('theme_id')
        ),
        Prefetch(
            'holidayskuimage',
            queryset=HolidaySKUImage.objects.select_related('gallery_id')
        )
    ).distinct()

        search_term = request.query_params.get('search_term')
        search_type = request.query_params.get('type')

        if search_term:
            # Filter based on search type
            if search_type == 'place':
                place_name_filters = Q()
                places = [unquote(p).strip() for p in search_term.split(",")]
                for p in places:
                    place_name_filters |= Q(place__icontains=p) | Q(name__icontains=p)
                queryset = queryset.filter(place_name_filters)
                
            elif search_type == 'country':
                country_filters = Q(country__country_name__icontains=search_term)  # Corrected filter for country name
                queryset = queryset.filter(country_filters)
                
            elif search_type == 'theme':
                theme_filters = Q(holidayskutheme__theme_id__name__icontains=search_term)
                queryset = queryset.filter(theme_filters)
            else:
                # General search term (search across all fields like name, place, theme, etc.)
                general_filters = Q(name__icontains=search_term) | Q(place__icontains=search_term) | Q(country__country_name__icontains=search_term) |Q(holidayskutheme__theme_id__name__icontains=search_term)
                queryset = queryset.filter(general_filters)

        # Filter by name
        if name := filters.get('name'):
            queryset = queryset.filter(name__icontains=name)

        # Filter by price range
       
        start_price_range = filters.get('start_price_range', None)
        end_price_range = filters.get('end_price_range', None)

        if start_price_range and start_price_range != 'null':
            start_price_range = float(start_price_range) if start_price_range != 'inf' else 0
            queryset = queryset.filter(Q(holidayskuprice__country_id_id=country_id) & Q(holidayskuprice__price__gte=start_price_range))

        if end_price_range and end_price_range != 'null':
            max_price = HolidaySKUPrice.objects.aggregate(max_price=Max('price')).get('max_price')
            end_price_range = float(end_price_range) if end_price_range != 'inf' else max_price
            queryset = queryset.filter(Q(holidayskuprice__country_id_id=country_id) & Q(holidayskuprice__price__lte=end_price_range))

        # Filter by place
      
        place = filters.get('place', None)
        if place and place != 'null':
            places = [unquote(p).strip() for p in place.split(",")]
            # place_name_filters = [Q(place__icontains=p) | Q(name__icontains=p) for p in places]
            place_name_filters = Q()
            for p in places:
                place_name_filters |= Q(place__icontains=p) | Q(name__icontains=p)


            if place_name_filters:
            #  queryset = queryset.filter(reduce(or_, place_name_filters))
                queryset = queryset.filter(place_name_filters)
        # Filter by theme
        if theme := filters.get('theme'):
            themes = [t.strip() for t in theme.split(",")]
            theme_filters = [Q(holidayskutheme__theme_id__name__icontains=t) for t in themes]
            queryset = queryset.filter(reduce(Q.__or__, theme_filters))

        # Filter by duration
        if start_duration_range := filters.get('start_duration_range'):
            queryset = queryset.annotate(nights_int=Cast('nights', IntegerField())).filter(nights_int__gte=int(start_duration_range))
        if end_duration_range := filters.get('end_duration_range'):
            queryset = queryset.annotate(days_int=Cast('days', IntegerField())).filter(days_int__lte=int(end_duration_range))

        return queryset

    def get_price_range_distribution(self, total_price_list):
        """Calculate price range distribution."""
        ranges = 5
        std, mean = np.std(total_price_list), np.mean(total_price_list)
        thresholds = [norm.ppf(i / ranges, mean, std) if std != 0 else mean for i in range(ranges + 1)]
        return np.array([round(thresholds[i], 2) for i in range(ranges + 1)])

    def post(self, request, *args, **kwargs):
        filters = request.data.get('filters', {})
        user = request.user
        country_id = getattr(user.base_country, 'id', None)
        
        if not country_id:
            return Response({"error": "User's base country is not set."}, status=400)

        queryset = self.get_filtered_queryset(request, filters, country_id)
        result_data = []

        for sku in queryset:
            sku_data = HolidaySkuGetSerializer(sku).data
            country_instance = sku.country.first()  
            if country_instance:
                sku_data['country_name'] = country_instance.country_name  
            else:
                sku_data['country_name'] = None

            sku_price_instance = HolidaySKUPrice.objects.filter(sku_id=sku.id, country_id=country_id).first()
            if sku_price_instance:
                if user.organization == sku.organization_id:
                    sku_data['price'] = sku_price_instance.price  # Base price
                else:
                    sku_data['price'] = sku_price_instance.price + (sku_price_instance.company_markup or 0)

                # Themes
                theme_instances = HolidaySKUTheme.objects.filter(sku_id=sku.id)
                sku_data['themes'] = [{
                    'id': theme.theme_id.id,
                    'name': theme.theme_id.name,
                    'image_url': f"{aws_url}{theme.theme_id.icon_url.url}"
                } for theme in theme_instances]

                # Images
                image_instances = HolidaySKUImage.objects.filter(sku_id=sku.id)
                sku_data['images'] = [{
                    'id': img.id,
                    'image_url': f"{aws_url}{img.gallery_id.url}"
                } for img in image_instances]

                # Inclusions
                inclusions = HolidaySKUInclusion.objects.filter(sku_id=sku.id).first()
                sku_data['sku_inclusions'] = inclusions and {
                    'flight': inclusions.flight,
                    'hotel': inclusions.hotel,
                    'transfer': inclusions.transfer,
                    'meals': inclusions.meals,
                    'visa': inclusions.visa,
                    'sight_seeing': inclusions.sight_seeing
                } or {}

            result_data.append(sku_data)

        # Price Range
        prices = [sku['price'] for sku in result_data if 'price' in sku]
        price_range = [min(prices, default=None), max(prices, default=None)]

        if result_data:
    # Only calculate ranges if there is data
            duration_range = [
                min(sku['nights'] for sku in result_data),
                max(sku['days'] for sku in result_data)
            ]
        else:
            duration_range = [None, None] 

        # Unique Places and Themes
        places = {place for sku in result_data for place in (sku.get('place') or '').split(',')}

        themes = {theme['name'] for sku in result_data for theme in sku.get('themes', [])}

        # Price Distribution
        total_price_list = [float(price) for price in prices]
        if total_price_list:
            price_ranges = self.get_price_range_distribution(total_price_list)
            counts, _ = np.histogram(total_price_list, bins=price_ranges)
            formatted_price_range = [{"range": [f"{round(start, -3)} - {round(end, -3)}"], "count": count}
                                     for (start, end), count in zip(zip(price_ranges[:-1], price_ranges[1:]), counts)]
        else:
            formatted_price_range = []

        return Response({
            'holiday_sku': result_data,
            'price_range': price_range,
            'duration_range': duration_range,
            'place_range': list(places),
            'themes_range': list(themes),
            'formatted_price_range': formatted_price_range
        })
