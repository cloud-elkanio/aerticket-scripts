# from django.shortcuts import render
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from users.models import LookupCountry, Country, Organization
from common.models import Gallery
from .serializers import *
import pytz
from pms.holiday_app.views import CustomPageNumberPagination
from tools.kafka_config.config import invoke
import threading

from datetime import datetime
class VisaCategoryView(APIView):
    def post(self, request):
        image_id=request.data.get('icon_id')
        image_url=request.data.get('icon_url')
        gallery_instance = Gallery.objects.filter(id=image_id).first()
        request.data['icon_url'] = gallery_instance.id
        serializer=VisaCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message":"Successfully Created"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        category=VisaCategoryMaster.objects.all().order_by('-modified_at')
        serializer=VisaCategorySerializerGet(category, many=True)
        return Response(serializer.data)
    
    def patch(self, request):
        id=request.data.get('id')
        if id is None:
            return Response({"message": " provide the id of the data in parameter."}, status=status.HTTP_404_NOT_FOUND)
        try:
            categories = VisaCategoryMaster.objects.get(id=id)
        except VisaCategoryMaster.DoesNotExist:
            return Response({"message": "Object not found."}, status=status.HTTP_404_NOT_FOUND)
                
        image_id=request.data.get('icon_id')
        gallery_instance = Gallery.objects.filter(id=image_id).first()

        if gallery_instance:
            galary_instance_id=gallery_instance.id
            request.data['icon_url']=galary_instance_id

        serializer = VisaCategorySerializer(instance=categories, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Objects updated successfully"}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def delete(self, request):
        id=request.query_params.get('id')
        if id is None:
            return Response({"message":"Provide id in parameter"})
        obj=VisaCategoryMaster.objects.filter(id=id)
        obj.delete()
        return Response({"message":"deleted successfully"})

class VisaTypeMasterView(APIView):
    def post(self, request):
        image_id=request.data.get('icon_id')
        image_url=request.data.get('icon_url')
        gallery_instance = Gallery.objects.filter(id=image_id).first()
        request.data['icon_url'] = gallery_instance.id
        serializer=VisaTypeMasterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message":"Successfully Created"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        types=VisaTypeMaster.objects.all().order_by('-modified_at')
        serializer=VisaTypeMasterSerializerGet(types, many=True)
        return Response(serializer.data)

    def patch(self, request):
        id=request.data.get('id')
        if id is None:
            return Response({"message": " provide the id of the data in parameter."}, status=status.HTTP_404_NOT_FOUND)
        try:
            types = VisaTypeMaster.objects.get(id=id)
        except VisaTypeMaster.DoesNotExist:
            return Response({"message": "Object not found."}, status=status.HTTP_404_NOT_FOUND)
                
        image_id=request.data.get('icon_id')
        gallery_instance = Gallery.objects.filter(id=image_id).first()
        if gallery_instance:
            galary_instance_id=gallery_instance.id
            request.data['icon_url']=galary_instance_id

        serializer = VisaTypeMasterSerializer(instance=types, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Objects updated successfully"}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def delete(self, request):
        id=request.query_params.get('id')
        if id is None:
            return Response({"message":"Provide id in parameter"})
        obj=VisaTypeMaster.objects.filter(id=id)
        obj.delete()
        return Response({"message":"deleted successfully"})


class VisaSKUDetailView(APIView):
    pagination_class = CustomPageNumberPagination

    def post(self, request):
        visa_data = request.data     
        prices = request.data.get('prices')
        from_country_instance = LookupCountry.objects.get(id=visa_data['from_country'])
        to_country_instance = LookupCountry.objects.get(id=visa_data['to_country'])
        user_instance = UserDetails.objects.get(id=request.user.id)
        images = request.data.get('images')
        
        # Create VisaDetail instance directly using create()
        visa_instance = VisaSKU.objects.create(
            name=visa_data['name'],
            type_id=visa_data['type'],
            category_id=visa_data['category'],
            from_country=from_country_instance,
            to_country=to_country_instance,
            stay_duration=visa_data['stay_duration'],
            validity=visa_data['validity'],
            entry_type=visa_data['entry_type'],
            processing_time=visa_data['processing_time'],
            info=visa_data['info'],
            documents_required=visa_data['documents_required'],
            faq= visa_data['faq'],
            description=visa_data['description'],
            created_by = user_instance,
            updated_by = user_instance
                            )

        for price_data in prices:
            country_instance = Country.objects.get(id=price_data['country_id'])
            VisaSKUPrice.objects.create(
                sku_id=visa_instance,
                country_id=country_instance,
                price=price_data['price']
                )
            
        for image in images:
            image_instance = Gallery.objects.get(id=image['id'])
            VisaSKUImage.objects.create(
                sku_id=visa_instance,
                gallery_id=image_instance
                )
            
        return Response({"message": "Visa detail created successfully"}, status=status.HTTP_201_CREATED)

    def get(self, request):
        try:
            page_size = int(request.query_params.get('page_size', 15))  

            id = request.query_params.get('id')
            search_key = request.query_params.get('search_key')

            from_country = request.query_params.get('from_country')
            to_country = request.query_params.get('to_country')

            if not from_country or not to_country:
                return Response({'error': 'Both from_country and to_country  parameters are required'}, status=status.HTTP_400_BAD_REQUEST)
            result_data = []

            visa_price_instances = VisaSKUPrice.objects.filter(sku_id__from_country=from_country, sku_id__to_country=to_country, sku_id__status=True).order_by('sku_id__name','-modified_at').distinct('sku_id__name')
#----------------------------------------------------------------
            if id:
                visa_price_instances = visa_price_instances.filter(sku_id__id=id)

            if search_key:
                visa_price_instances = visa_price_instances.filter(
                    Q(sku_id__name__icontains=search_key)
                )

#----------------------------------------------------------------

            for visa_price_instance in visa_price_instances:
                visa_serializer = VisaSKUSerializer(visa_price_instance.sku_id)
                visa_data = visa_serializer.data
#price get
                price_details = []
                price_instances = VisaSKUPrice.objects.filter(sku_id=visa_data['id']).order_by('-modified_at')

                for price_instance in price_instances:
                    price_serializer = VisaSKUPriceSerializer(price_instance)
                    price_data = price_serializer.data
                    price_details.append({
                        'country_id': price_data['country_id'],
                        'price': price_data['price']
                    })

                visa_data['price_details'] = price_details


                # Get images
                image_instances = VisaSKUImage.objects.filter(sku_id=visa_data['id'])
                visa_data['images'] = [
                    {
                        'id': str(image_instance.gallery_id.id),
                        'url': image_instance.gallery_id.url.url
                    }
                    for image_instance in image_instances
                ]
                result_data.append(visa_data)

            paginator = CustomPageNumberPagination(page_size = page_size)
            paginated_obj = paginator.paginate_queryset(result_data, request)
            
            data = {
            'count': paginator.page.paginator.count,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
            'results': paginated_obj
            }

            return Response({'data': data}, status=status.HTTP_200_OK)
        except VisaSKUPrice.DoesNotExist:
            return Response({'error': 'No visa prices found for the provided countries'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def patch(self, request):
        id = request.data.get('id')
        if id is None:
            return Response({"message": "Provide the id of the data in parameter."}, status=status.HTTP_404_NOT_FOUND)
        try:
            visa_detail = VisaSKU.objects.get(id=id)
        except VisaSKU.DoesNotExist:
            return Response({"message": "Visa detail not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer_visa_detail = VisaSKUSerializer(instance=visa_detail, data=request.data, partial=True)
        if not serializer_visa_detail.is_valid():
            return Response(serializer_visa_detail.errors, status=status.HTTP_400_BAD_REQUEST)

        updated_visa_detail = serializer_visa_detail.save()

        VisaSKUPrice.objects.filter(sku_id=updated_visa_detail).delete()

        price_data = request.data.get('prices')
        if price_data:
            for price_info in price_data:
                country_id = price_info.get('country_id')
                price = price_info.get('price')
                new_price_detail = VisaSKUPrice.objects.create(
                    sku_id=updated_visa_detail,
                    country_id=Country.objects.get(id = country_id),
                    price=price
                )
        # Update images

        images = request.data.get('images')
        if images:

            VisaSKUImage.objects.filter(sku_id=updated_visa_detail).delete()
            for image in images:

                image_id=image['id']
                gallery_instance = Gallery.objects.filter(id=image_id).first()

                if gallery_instance:
                    galary_instance_id=gallery_instance.id
                    VisaSKUImage.objects.create(sku_id=updated_visa_detail, gallery_id=gallery_instance)

        return Response({"message": "Objects updated successfully"}, status=status.HTTP_200_OK)

    def delete(self, request):
        id=request.query_params.get('id')
        if id is None:
            return Response({"message":"Provide id in parameter"})
        obj=VisaSKU.objects.filter(id=id)
        obj.delete()
        return Response({"message":"deleted successfully"})
    

class SearchFromToCountryView(APIView):
    def get(self, request):
        search_key = request.query_params.get('search_key')
        is_from = request.query_params.get('is_from', 'False') == 'True'
        from_country = request.query_params.get('from_country', None)

        if search_key and search_key != 'null':
            if is_from:
                visa_instances = VisaSKU.objects.filter(
                    from_country__country_name__icontains=search_key
                ).values(
                    'from_country__country_name', 'from_country__id'
                ).order_by('from_country__country_name', 'from_country__id').distinct('from_country__country_name')
                formatted = [
                    {'country_id': item['from_country__id'], 'country_name': item['from_country__country_name']}
                    for item in visa_instances
                ]
            else:
                visa_instances = VisaSKU.objects.filter(
                    to_country__country_name__icontains=search_key
                ).values(
                    'to_country__country_name', 'to_country__id'
                ).order_by('to_country__country_name', 'to_country__id').distinct('to_country__country_name')
                formatted = [
                    {'country_id': item['to_country__id'], 'country_name': item['to_country__country_name']}
                    for item in visa_instances
                ]
        else:
            if is_from:
                visa_instances = VisaSKU.objects.values(
                    'from_country__country_name', 'from_country__id'
                ).order_by('from_country__country_name', 'from_country__id').distinct('from_country__country_name')
                formatted = [
                    {'country_id': item['from_country__id'], 'country_name': item['from_country__country_name']}
                    for item in visa_instances
                ]
            else:
                if from_country:
                    visa_instances = VisaSKU.objects.filter(
                        from_country__country_name__icontains=from_country
                    ).values(
                        'to_country__country_name', 'to_country__id'
                    ).order_by('to_country__country_name', 'to_country__id').distinct('to_country__country_name')
                else:
                    visa_instances = VisaSKU.objects.values(
                        'to_country__country_name', 'to_country__id'
                    ).order_by('to_country__country_name', 'to_country__id').distinct('to_country__country_name')
                
                formatted = [
                    {'country_id': item['to_country__id'], 'country_name': item['to_country__country_name']}
                    for item in visa_instances
                ]
        return Response(formatted, status=status.HTTP_200_OK)
    
class VisaChangeStatusView(APIView):
    def post(self, request):
        try:
            visa_id=request.data.get("visa_id")
            active = request.data.get('status')
            visa_instance = VisaSKU.objects.get(id=visa_id)
            if visa_instance:
                visa_instance.status = active
                visa_instance.save()
                if active:
                    return Response({'detail': 'Visa activated successfully'}, status=status.HTTP_200_OK)
                else:
                    return Response({'detail': 'Visa deactivated successfully'}, status=status.HTTP_200_OK)
        except VisaSKU.DoesNotExist:
            return Response({'detail': 'Visa not found'}, status=status.HTTP_404_NOT_FOUND)


class VisaDefaultValues(APIView):

    def post(self, request):

        country_name = request.data.get('country_name')
        country_instance = Country.objects.get(lookup__country_name=country_name)
        country_id = country_instance.id
        request.data['country_id'] = country_id

        visa_skus = VisaSKUPrice.objects.filter(country_id=country_id) 
        if not visa_skus.exists():
            return Response("No Visa Found Under this Country ")
        visa_init = {"default": {"from_country": None, "to_country": None}, "suggestions": []}
        default_visa = visa_skus.first()
        visa_init['default'] = {
            "from_country": {
                "id": str(default_visa.sku_id.from_country.id),
                "name": default_visa.sku_id.from_country.country_name,
            },
            "to_country": {
                "id": str(default_visa.sku_id.to_country.id),
                "name": default_visa.sku_id.to_country.country_name,
            },
        }
        suggestion_list = []
        for visa_sku in visa_skus[1:4]:
            suggestion_list.append({
                "from_country": {
                    "id": str(visa_sku.sku_id.from_country.id),
                    "name": visa_sku.sku_id.from_country.country_name,
                },
                "to_country": {
                    "id": str(visa_sku.sku_id.to_country.id),
                    "name": visa_sku.sku_id.to_country.country_name,
                },
            })

        visa_init['suggestions'] = suggestion_list
        request.data['visa'] = visa_init
        country_default_instance = CountryDefault.objects.filter(country_id=country_id).first()
        if country_default_instance:
            if country_default_instance.visa:
                serializer = VisaDefaultSerializer(country_default_instance, data= request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response("Updated Already Existing Data in Visa Field", status=status.HTTP_200_OK)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            country_default_instance.visa = visa_init
            serializer = VisaDefaultSerializer(country_default_instance, data= request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response("Updated Null Visa Field", status=status.HTTP_200_OK)            
        else:
            serializer = VisaDefaultSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response("Successfully created new record with visa details", status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def get(self, request):
        country_id = request.user.organization.organization_country
        if not country_id:
            return Response({"message": "country_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        default_values = CountryDefault.objects.filter(country_id=country_id)
    
        # default_values = CountryDefault.objects.all()

        serializer = VisaDefaultSerializer(default_values, many=True)

        filtered_data = [data for data in serializer.data if data.get('visa')]

        return Response(filtered_data, status=status.HTTP_200_OK)
    

#get all sku visa for favourite    
class visaSKUHolidayFavouriteGet(APIView):
    def get(self, request):
        page_size = int(request.query_params.get('page_size', 15))  
        country_id = request.query_params.get('country_id')
        visa_sku_ids = VisaFavourite.objects.values_list('sku_id', flat=True)

        if country_id:
            price_instance = VisaSKUPrice.objects.filter(country_id= country_id)

        price_instance_sku = price_instance.values_list('sku_id', flat=True)

        sku_instance = VisaSKU.objects.filter(id__in = price_instance_sku).exclude(id__in = visa_sku_ids)

        paginator = CustomPageNumberPagination(page_size=page_size)
        paginated_favourites = paginator.paginate_queryset(sku_instance, request)

        serializer = VisaSKUSerializer(paginated_favourites, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    
class VisaFavoriteView(APIView):
    permission_classes = []
    def post(self, request):
        serializer=VisaFavoriteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message":"Successfully Created"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    def get(self, request):
        page_size = int(request.query_params.get('page_size', 15))  

        search_key = request.query_params.get('search_key')
        country_id = request.query_params.get('country_id')
        if not country_id:
            return Response({"message":"Provide active country_id in parameter"})

        favourite = VisaFavourite.objects.filter(country_id=country_id)

        if search_key:
            favourite = favourite.filter(
                Q(sku_id__name__icontains=search_key) | 
                Q(country_id__lookup__country_name__icontains=search_key)
            )

        favourite = favourite.order_by('-modified_at')
        paginator = CustomPageNumberPagination(page_size=page_size)
        paginated_favourites = paginator.paginate_queryset(favourite, request)

        serializer = VisaFavoriteSerializerGet(paginated_favourites, many=True)
        return paginator.get_paginated_response(serializer.data)
#

    def delete(self, request):
        id=request.query_params.get('id')
        if id is None:
            return Response({"message":"Provide id in parameter"})
        obj=VisaFavourite.objects.filter(id=id)
        obj.delete()
        return Response({"message":"deleted successfully"})
    
from django.utils import timezone
import time

class VisaQueueGet(APIView):
    def get(self, request):
        # Extract query parameters
        page_size = int(request.query_params.get('page_size', 15))
        status_name = request.query_params.get('status')
        date = request.query_params.get('date')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        ref_id = request.query_params.get('visa_ref_id')
        # Initialize filters
        filters = Q()

        # Apply filters based on query parameters
        if status_name:
            filters &= Q(visaenquiryhistory__status_id__name=status_name)
        if ref_id:
            filters &= Q(visa_ref_id=ref_id)
        if start_date and end_date:
            # Parse the start and end dates
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            # Get the start of the day for `start_date`
            start_datetime = datetime.combine(start_date, datetime.min.time())
            start_of_day = start_datetime.timestamp()

            # Get the end of the day for `end_date`
            end_datetime = datetime.combine(end_date, datetime.max.time())
            end_of_day = end_datetime.timestamp()

            # Filter records based on `created_at` timestamp
            filters &= Q(created_at__gte=start_of_day, created_at__lte=end_of_day)

        # Role-based filtering
        user = request.user
        if user.role.name in ["super_admin","operations"]:
            # Superuser sees all records
            enquiry_instance = VisaEnquiry.objects.filter(filters)
        elif user.role.name in ["agency_owner", "agency_staff", "distributor_owner", "distributor_staff", "out_api_owner", "out_api_staff"]:
            # Filter based on the user's organization
            enquiry_instance = VisaEnquiry.objects.filter(filters, user_id__organization=user.organization)
        elif user.role.name == "distributor_agent":
            # Distributor agent sees only their created records
            enquiry_instance = VisaEnquiry.objects.filter(filters, user_id=user)
        else:
            # Default: no access
            enquiry_instance = VisaEnquiry.objects.none()

        # Pagination
        paginator = CustomPageNumberPagination(page_size=page_size)
        paginated_enquiries = paginator.paginate_queryset(enquiry_instance, request)
        serializer = VisaEnquirySerializerGet(paginated_enquiries, many=True)

        return paginator.get_paginated_response(serializer.data)
    
#visa queue status update

    def patch(self, request):
        visa_enquiry_id = request.data.get('id')
        event_name = request.data.get('event_name','')
        if visa_enquiry_id is None:
            return Response({"message": "Provide id in parameter"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            visa_enquiry_instance = VisaEnquiry.objects.get(id=visa_enquiry_id)
            user_email = [visa_enquiry_instance.email]

        except VisaEnquiry.DoesNotExist:
            return Response({"message": "VisaEnquiry with this id does not exist."}, status=status.HTTP_404_NOT_FOUND)

        # Retrieve status_id safely
        status_id = request.data.get('status_id')
        updated_by = request.user

        if not status_id:
            return Response({"message": "status_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Fetch the new status by ID
            new_status = LookupVisaEnquiryStatus.objects.get(id=status_id)
            print("status name", new_status.name)
            status_name = new_status.name
            
        except LookupVisaEnquiryStatus.DoesNotExist:
            return Response({"message": "Invalid status_id."}, status=status.HTTP_400_BAD_REQUEST)

        # Create a new VisaEnquiryHistory instance
        visa_enquiry_history_instance = VisaEnquiryHistory.objects.create(
            visa_enquiry=visa_enquiry_instance,
            status_id=new_status,
            updated_by=updated_by,
        )

        # Serialize the created instance and return success response
        serializer = VisaEnquiryHistorySerializer(visa_enquiry_history_instance)
        user_obj = request.user
        currentdate =  datetime.now()
        formated_date = currentdate.strftime("%d-%m-%Y")

        data_dict = {
            "country_name":user_obj.base_country.lookup.country_name, 
            "applicant_name": visa_enquiry_instance.name,
            "country": visa_enquiry_instance.country.country_name,
            "name": visa_enquiry_instance.visa_id.name,
            "ref_id" : visa_enquiry_instance.visa_ref_id,
            "organization_name": visa_enquiry_instance.user_id.organization.organization_name,
            "visa_type": visa_enquiry_instance.visa_type,
            "approval_date":formated_date,
            "visa_validity": visa_enquiry_instance.date_of_expiry
            }
        
        if status_name:
            event_name = '_'.join(word.capitalize()for word in status_name.split(" "))

        if event_name:
            thread = threading.Thread(target=invoke, kwargs={
                                    "event":event_name,
                                    "number_list":[], 
                                    "email_list":user_email if user_email else None,
                                    "data" :data_dict
                                    })
            thread.start()
        return Response({"message": "Queue updated successfully"}, status=status.HTTP_201_CREATED)


class VisaEnquiryStatusGet(APIView):
    def get(self, request):
        status_instance = LookupVisaEnquiryStatus.objects.all().order_by('progression_order')
        serializer = VisaEnquiryStatusSerializer(status_instance, many=True)
        return Response(serializer.data)
    
class GetSupplierListForVisEnquiry(APIView):
    def get(self, request):
        supplier_instance = Organization.objects.all().values('id','organization_name')
        supplier_list = list(supplier_instance)
        return Response(supplier_list)
    
class SingleVisaUsingSlug(APIView):
    def get(self, request, slug):
        try:
            visa_instance = VisaSKU.objects.get(slug=slug)
            serializer = VisaSKUSlugSerializer(visa_instance)
            return Response(serializer.data)
        except VisaSKU.DoesNotExist:
            return Response({"message": "VisaSKU with this slug does not exist."}, status=status.HTTP_404_NOT_FOUND)


# from accounting.shared.models import LookupEasyLinkSupplier

# class Upload_data_to_eazylink_supplier_table(APIView):
#     authentication_classes = []
#     permission_classes = []

#     def post(self, request):
#         s_data = request.data
#         if not isinstance(s_data, list):
#             return Response(
#                 {"message": "Invalid data format. Expected a list of supplier data."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         for index, item in enumerate(s_data):
#             code = item.get('code')
#             name = item.get('name')

#             try:
#                 LookupEasyLinkSupplier.objects.update_or_create(
#                     supplier_id=code,
#                     display_id=name
#                 )
#             except Exception as e:
#                 return Response(str(e))

#         return Response({"message": "All suppliers uploaded successfully."}, status=status.HTTP_201_CREATED)
