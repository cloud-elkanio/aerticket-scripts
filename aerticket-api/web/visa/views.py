from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pms.visa_app.models import *
from .serializers import *
from pms.visa_app.views import CustomPageNumberPagination
from pms.visa_app.models import VisaEnquiry
from tools.kafka_config.config import invoke
import threading

class WebVisaCategoryView(APIView):
    def get(self, request):
        category=VisaCategoryMaster.objects.all()
        serializer=VisaCategorySerializerGet(category, many=True)
        return Response(serializer.data)
    

class WebVisaSKUDetailView(APIView):
   def get(self, request):
        try:
            page_size = int(request.query_params.get('page_size', 15))  

            from_country = request.query_params.get('from_country')
            to_country = request.query_params.get('to_country')
            category = request.query_params.get('category')
            country = request.user.organization.organization_country

            if not from_country or not to_country or not category:
                return Response({'error': 'Both from_country and to_country and category  parameters are required'}, status=status.HTTP_400_BAD_REQUEST)
            result_data = []

            visa_price_instances = VisaSKUPrice.objects.filter(sku_id__from_country=from_country, sku_id__to_country=to_country, sku_id__category=category, sku_id__status=True, country_id = country).order_by('sku_id__name','-modified_at').distinct('sku_id__name')


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
                        'price': price_data['price'],
                        'currency_symbol': price_data['currency_symbol']
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
        
#get single visa
class SingleVisaDetailView(APIView):
    def get(self, request,from_country,to_country,category,entry_type,country_id):
        country_id = country_id


        if not from_country and not to_country and not category and not entry_type:
            return Response({"message": "Please provide a from_country to_country category entry_type ."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            visa_obj = VisaSKU.objects.filter(from_country__country_name=from_country,to_country__country_name=to_country,category__name=category,entry_type=entry_type).first()
            visa_price = VisaSKUPrice.objects.filter(sku_id = visa_obj.id,country_id=country_id)

        except VisaSKU.DoesNotExist:
            return Response({"message": "Visa not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = SingleVisaDetailSerializer(visa_obj)
        serializer_data = serializer.data
        serializer_data['price_details'] = [
            {
                'country_id': price.country_id.id,  # Use the ID of the country
                'price': price.price
            } 
            for price in visa_price
        ]        
        return Response(serializer_data, status=status.HTTP_200_OK)   

#get single visa using slug
class SingleVisaDetailViewUsingSlug(APIView):
    def get(self, request,slug):
        country_id = request.user.organization.organization_country.id

        if not slug and not country_id:
            return Response({"message": "Please provide a slug  and country_id ."}, status=status.HTTP_400_BAD_REQUEST)
        
        visa_price_instances = VisaSKUPrice.objects.filter(sku_id__slug=slug)


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
                    'price': price_data['price'],
                    'currency_symbol': price_data['currency_symbol']
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

        return Response(visa_data, status=status.HTTP_200_OK)
 
class VisaEnquiryView(APIView):
    def post(self, request):
        request.data['user_id'] = request.user.id
        status_name = 'New application'
        status_instance, created = LookupVisaEnquiryStatus.objects.get_or_create(name=status_name)
        status_obj = status_instance.id
        try:
            country = LookupCountry.objects.get(id=request.data.get('country'))
            country_name = country.country_name   
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        count = VisaEnquiry.objects.all().count()+1
        count = '{:04d}'.format(count)
        request.data['visa_ref_id'] = f"BTA_VISA-{count}"
        updated_by = request.user
        serializer = VisaEnquirySerializer(data=request.data)

        if serializer.is_valid():
            visa_obj = serializer.save()
            VisaEnquiryHistory.objects.create(visa_enquiry = visa_obj, status_id = status_instance , updated_by = updated_by)
            #---------------START-----------------------------------------------------------------------------------------------------
            data_list = {
                        "agent_name":request.user.first_name, 
                        "country":country_name,
                        "full_name":request.data['name'],
                        "gender": request.data['gender'],
                        "dob": request.data['dob'],
                        "place_of_birth":request.data['place_of_birth'],
                        "email":request.data['email'], 
                        "phone_number":request.data['phone_number'], 
                        "marital_status":request.data['marital_status'],
                        "current_address": request.data['current_address'],
                        "passport_number": request.data['passport_number'],
                        "date_of_issue":request.data['date_of_issue'],
                        "date_of_expiry":request.data['date_of_expiry'], 
                        "place_of_issue":request.data['place_of_issue'],
                        "visa_type": request.data['visa_type'],
                        "purpose_of_visit": request.data['purpose_of_visit'],
                        "duration":request.data['duration'],
                        "date_of_entry":request.data['date_of_entry'], 
                        "date_of_exit":request.data['date_of_exit'], 
                        "country_name":request.user.base_country.lookup.country_name
                        }
            
            email_data = [request.data['email']]
           
            thread = threading.Thread(target=invoke, kwargs={
                        "event":"Visa_Enquiry", 
                        "email_list":email_data,
                        "data" :data_list
                        })
            thread.start()
            # invoke(event='Visa_Enquiry',email_list=email_data, data = data_list)

            #---------------END-----------------------------------------------------------------------------------------------------

            return Response({"message":"Created Successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status= status.HTTP_400_BAD_REQUEST)
    
class WebVisaFavoriteView(APIView):
    def get(self, request):
        country_id = request.query_params.get('country_id')
        if not country_id:
            return Response({"message":"Provide active country_id in parameter"})

        favourite = VisaFavourite.objects.filter(country_id=country_id).order_by('-modified_at')[:6]

        serializer = VisaFavoriteSerializerGet(favourite, many=True)
        return Response(serializer.data)
    
class MyDashboardContent(APIView):   
    def get(self, request):
        user_id=request.user.id
        enquiry_instance=VisaEnquiry.objects.filter(user_id=user_id).order_by('-created_at')
        serializer = VisaEnquirySerializer(enquiry_instance, many=True)
        return Response({"total_count":len(enquiry_instance),"data":serializer.data})

class CategoryBasedOnCountry(APIView):
    def get(self, request):
        from_country = request.query_params.get('from_country')
        to_country = request.query_params.get('to_country')
        if not from_country or not to_country:
            return Response({"message":"Both from_country and to_country are required"})
        category_instance = VisaSKU.objects.filter(from_country = from_country, to_country = to_country).values_list('category__name', 'category__id','category__icon_url__url').distinct()
        if not category_instance:
            return Response({'error': 'No visa categories found for the given countries'}, status=status.HTTP_404_NOT_FOUND)
        formated_category = [{'id':category_id ,'category_name':category_name, 'category_url':category_url} for category_name, category_id, category_url in category_instance]
        return Response(formated_category)