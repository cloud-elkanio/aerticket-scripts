from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from .serializers import *
from django.db.models import Q
from users.models import LookupCountry, Country
from rest_framework.generics import ListAPIView, UpdateAPIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from .serializers import HolidayEnquirySerializer
from common.views import (
    CustomSearchFilter,
    DateFilter,
    HolidayEnquiryStatusFilter,
    HolidayEnquirySupplierFilter,
)
from django.db.models import Count
from decimal import Decimal
import threading
from tools.kafka_config.config import invoke

class CustomPageNumberPagination(PageNumberPagination):
    def __init__(self, page_size=10, *args, **kwargs):
        self.page_size = page_size
        return super().__init__(*args, **kwargs)

    page_size_query_param = "page_size"
    max_page_size = 100


# get whole country [from lookupcountry table]
class GetWholeCountry(APIView):
    permission_classes = []

    def get(Self, request):
        country_details = LookupCountry.objects.all()
        serializer = LookupCountrySerializer(country_details, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


from django.db.models import F

# create holiday product
# class HolidaySKUView(APIView):
#     def post(self, request):
#         request.data['created_by'] = request.user.id
#         request.data['updated_by'] = request.user.id

#         request.data['organization_id'] =request.user.organization.id if request.user.organization.id else None
#         request.data['status'] = 'Active' if request.user.organization.organization_type.name.lower() == 'master' else 'Pending'

#         sku_serializer = HolidaySKUSerializer(data = request.data)
#         if sku_serializer.is_valid():
#             sku_instances = sku_serializer.save()
#             self.create_themes(sku_instances , request.data.get('themes',[]))
#             self.create_prices(sku_instances, request.data.get('prices', []))
#             self.create_images(sku_instances, request.data.get('images', []))
#             self.create_sku_inclusions(sku_instances, request.data.get('sku_inclusions', []))
#             return Response({"message":"success"} , status= status.HTTP_200_OK)
#         return Response(sku_serializer.errors, status= status.HTTP_400_BAD_REQUEST)

#     def create_themes(self, sku_instances , themes):
#         theme_objs =([
#             HolidaySKUTheme(sku_id = sku_instances, theme_id = HolidayThemeMaster.objects.get(id = theme.get('theme_id')))
#             for theme in themes
#             ])
#         HolidaySKUTheme.objects.bulk_create(theme_objs)

#     def create_prices(self ,sku_instances , prices):
#         price_objs = ([
#             HolidaySKUPrice(
#                 sku_id = sku_instances ,

#                 country_id = Country.objects.get(id = price.get('country_id')),
#                 price = price.get('price')
#                  )
#             for price in prices
#         ])
#         HolidaySKUPrice.objects.bulk_create(price_objs)

#     def create_images(self ,sku_instances , images):
#         for image_data in images:
#             image_id = image_data.get("id")
#             gallery_instance = Gallery.objects.filter(id=image_id).first()
#             if gallery_instance:
#                 HolidaySKUImage.objects.create(sku_id=sku_instances, gallery_id=gallery_instance)
#             else:
#                 pass

#         return Response({"message":"Success"}, status=status.HTTP_201_CREATED)

#     def create_sku_inclusions(self ,sku_instances, inclusions):
#         for inclusion in inclusions:
#             HolidaySKUInclusion.objects.create(
#                 sku_id =sku_instances ,
#                 flight = inclusion.get('flight'),
#                 hotel = inclusion.get('hotel'),
#                 transfer = inclusion.get('transfer'),
#                 meals = inclusion.get('meals'),
#                 visa = inclusion.get('visa'),
#                 sight_seeing = inclusion.get('sight_seeing')
#             )
#     def get(self, request):
#         try:
#             page_size = int(request.query_params.get('page_size', 15))

#             id = request.query_params.get('id')
#             search_key = request.query_params.get('search_key')
#             if request.user.is_superuser:
#                 sku_instances = HolidaySKU.objects.all()

#             else:
#                 sku_instances = HolidaySKU.objects.filter(
#                     organization_id=request.user.organization.id
#                 )

#             if id:
#                 sku_instances = sku_instances.filter(id=id)

#             if search_key:
#                 sku_instances = sku_instances.filter(
#                     Q(name__icontains=search_key) |
#                     Q(location__icontains=search_key) |
#                     Q(country__country_name__icontains=search_key)
#                 )

#             sku_instances = sku_instances.order_by('-modified_at')

#             # Set pagination
#             paginator = CustomPageNumberPagination(page_size=page_size)
#             paginated_skus = paginator.paginate_queryset(sku_instances, request)

#             result_data = []

#             for sku_instance in paginated_skus:
#                 sku_serializer = HolidaySKUSerializerGet(sku_instance)
#                 sku_data = sku_serializer.data

#                 prices = HolidaySKUPrice.objects.filter(sku_id=sku_instance)
#                 sku_data['prices'] = [
#                     {
#                         "country_id": str(price_instance.country_id.id),
#                         "country_name":str(price_instance.country_id.lookup.country_name),
#                         "price": price_instance.price
#                     }
#                     for price_instance in prices
#                 ]

#                 # Get themes
#                 theme_instances = HolidaySKUTheme.objects.filter(sku_id=sku_instance)
#                 sku_data['themes'] = [
#                     {
#                         'id': theme.theme_id.id,
#                         'image_url': str(theme.theme_id.icon_url.url),
#                         'name': theme.theme_id.name
#                     }
#                     for theme in theme_instances
#                 ]

#                 # Get images


#                 image_instances = HolidaySKUImage.objects.filter(sku_id=sku_instance)
#                 sku_data['images'] = [
#                     {
#                         'id': str(image_instance.gallery_id.id),
#                         'image_url': image_instance.gallery_id.url.url
#                     }
#                     for image_instance in image_instances
#                 ]

#                 # Get SKU inclusions
#                 inclusion_instances = HolidaySKUInclusion.objects.filter(sku_id=sku_instance)
#                 sku_data['sku_inclusions'] = [
#                     {
#                         'flight': inclusion.flight,
#                         'hotel': inclusion.hotel,
#                         'transfer': inclusion.transfer,
#                         'meals': inclusion.meals,
#                         'visa': inclusion.visa,
#                         'sight_seeing': inclusion.sight_seeing
#                     }
#                     for inclusion in inclusion_instances
#                 ]

#                 result_data.append(sku_data)

#             return paginator.get_paginated_response(result_data)

#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def patch(self, request):
#         id = request.data.get('id')
#         if not id:
#             return Response({"message": "Provide the id of the data in parameter."}, status=status.HTTP_404_NOT_FOUND)

#         holiday_sku = HolidaySKU.objects.filter(id=id).first()
#         if not holiday_sku:
#             return Response({"message": "Object not found."}, status=status.HTTP_404_NOT_FOUND)

#         request.data['image_url'] = request.data.get('image_id')
#         serializer = HolidaySKUSerializer(instance=holiday_sku, data=request.data, partial=True)

#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#         updated_holiday_sku = serializer.save()

#         # Update themes
#         if request.data.get('themes'):
#             themes_data = request.data.get('themes', [])
#             HolidaySKUTheme.objects.filter(sku_id=updated_holiday_sku).delete()
#             themes_instances = []
#             for theme_id in themes_data:
#                 theme_instance = HolidayThemeMaster.objects.get(id=theme_id['theme_id'])
#                 themes_instances.append(HolidaySKUTheme(sku_id=updated_holiday_sku, theme_id=theme_instance))

#             # Bulk create the HolidaySKUTheme instances
#             HolidaySKUTheme.objects.bulk_create(themes_instances)


#         # Update images

#         images = request.data.get('images')
#         if images:

#             HolidaySKUImage.objects.filter(sku_id=updated_holiday_sku).delete()
#             for image in images:

#                 image_id=image['id']
#                 gallery_instance = Gallery.objects.filter(id=image_id).first()

#                 if gallery_instance:
#                     galary_instance_id=gallery_instance.id
#                     HolidaySKUImage.objects.create(sku_id=updated_holiday_sku, gallery_id=gallery_instance)

#         # Update prices
#         price_data = request.data.get('prices')
#         if price_data:
#             for price_info in price_data:
#                 country_id = price_info.get('country_id')
#                 new_price = price_info.get('price')

#                 if country_id and new_price is not None:
#                     try:
#                         country = Country.objects.get(id=country_id)
#                     except Country.DoesNotExist:
#                         return Response({"error": "Invalid country ID"}, status=status.HTTP_400_BAD_REQUEST)
#                     try:
#                         product_price_country = HolidaySKUPrice.objects.get(
#                             sku_id=updated_holiday_sku,
#                             country_id=country
#                         )
#                         product_price_country.price = new_price
#                         product_price_country.save()
#                     except HolidaySKUPrice.DoesNotExist:
#                         HolidaySKUPrice.objects.create(
#                             sku_id=updated_holiday_sku,
#                             country_id=country,
#                             price=new_price
#                         )
#                 else:
#                     return Response({"error": "Both country ID and price must be provided."}, status=status.HTTP_400_BAD_REQUEST)

#         # Update sku_inclusions
#         if request.data.get('sku_inclusions'):
#             sku_inclusions = request.data.get('sku_inclusions', [])
#             for sku_inclusion in sku_inclusions:
#                 flight = sku_inclusion.get('flight')
#                 hotel = sku_inclusion.get('hotel')
#                 transfer = sku_inclusion.get('transfer')
#                 meals = sku_inclusion.get('meals')
#                 visa = sku_inclusion.get('visa')
#                 sight_seeing = sku_inclusion.get('sight_seeing')

#                 if all(v is not None for v in [flight, hotel, transfer, meals, visa, sight_seeing]):
#                     HolidaySKUInclusion.objects.update_or_create(
#                         sku_id=updated_holiday_sku,
#                         defaults={
#                             'flight': flight,
#                             'hotel': hotel,
#                             'transfer': transfer,
#                             'meals': meals,
#                             'visa': visa,
#                             'sight_seeing': sight_seeing
#                         }
#                     )
#         return Response({"message": "Objects updated successfully"}, status=status.HTTP_200_OK)


#     def delete(self, request):
#         id=request.query_params.get('id')
#         if id is None:
#             return Response({"message":"Provide id in parameter"})
#         obj=HolidaySKU.objects.filter(id=id)
#         obj.delete()
#         return Response({"message":"deleted successfully"})

from django.db import transaction


class HolidaySKUView(APIView):
    def post(self, request):
        data = request.data.copy()
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"error": "User is not authenticated."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        data["created_by"] = request.user.id
        data["updated_by"] = request.user.id

        # Set organization_id and status
        organization = getattr(request.user, "organization", None)
        data["organization_id"] = organization.id if organization else None

        if organization and organization.organization_type:
            data["status"] = (
                "Active"
                if organization.organization_type.name.lower() == "master"
                else "Pending"
            )
        else:
            data["status"] = "Pending"

        sku_serializer = HolidaySKUSerializer(data=data)
        if sku_serializer.is_valid():
            sku_instance = sku_serializer.save()

            # Set Many-to-Many field for countries
            country_ids = data.get("country", [])
            if country_ids:
                countries = LookupCountry.objects.filter(id__in=country_ids)
                sku_instance.country.set(countries)

            # Handle related data creation
            self.create_themes(sku_instance, data.get("themes", []))
            self.create_prices(sku_instance, data.get("prices", []))
            self.create_images(sku_instance, data.get("images", []))
            self.create_sku_inclusions(sku_instance, data.get("sku_inclusions", []))

            return Response(
                {"message": "Successfully created."}, status=status.HTTP_201_CREATED
            )
        return Response(sku_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def create_themes(self, sku_instance, themes):
        theme_objs = [
            HolidaySKUTheme(
                sku_id=sku_instance,
                theme_id=HolidayThemeMaster.objects.get(id=theme.get("theme_id")),
            )
            for theme in themes
            if "theme_id" in theme
        ]
        HolidaySKUTheme.objects.bulk_create(theme_objs)

    def create_themes(self, sku_instance, themes):
        theme_objs = []
        for theme in themes:
            theme_id = theme.get("theme_id")
            if theme_id:
                try:
                    theme_obj = HolidayThemeMaster.objects.get(id=theme_id)
                    theme_objs.append(
                        HolidaySKUTheme(sku_id=sku_instance, theme_id=theme_obj)
                    )
                except HolidayThemeMaster.DoesNotExist:
                    # Handle the case where the theme does not exist
                    continue
        HolidaySKUTheme.objects.bulk_create(theme_objs)

    def create_prices(self, sku_instance, prices):
        price_objs = []
        for price in prices:
            country_id = price.get("country_id")
            price_value = price.get("price")

            if country_id and price_value:
                try:
                    country = Country.objects.get(id=country_id)
                    price_objs.append(
                        HolidaySKUPrice(
                            sku_id=sku_instance, country_id=country, price=price_value
                        )
                    )
                except Country.DoesNotExist:
                    # Log the invalid country_id for debugging if needed
                    continue

        if price_objs:
            HolidaySKUPrice.objects.bulk_create(price_objs)

    def create_images(self, sku_instance, images):
        image_objs = [
            HolidaySKUImage(
                sku_id=sku_instance, gallery_id=Gallery.objects.get(id=image.get("id"))
            )
            for image in images
            if "id" in image and Gallery.objects.filter(id=image.get("id")).exists()
        ]
        HolidaySKUImage.objects.bulk_create(image_objs)

    def create_sku_inclusions(self, sku_instance, inclusions):

        inclusion_objs = [
            HolidaySKUInclusion(
                sku_id=sku_instance,
                flight=inclusion.get("flight"),
                hotel=inclusion.get("hotel"),
                transfer=inclusion.get("transfer"),
                meals=inclusion.get("meals"),
                visa=inclusion.get("visa"),
                sight_seeing=inclusion.get("sight_seeing"),
            )
            for inclusion in inclusions
            if all(
                k in inclusion
                for k in [
                    "flight",
                    "hotel",
                    "transfer",
                    "meals",
                    "visa",
                    "sight_seeing",
                ]
            )
        ]
        HolidaySKUInclusion.objects.bulk_create(inclusion_objs)

    def get(self, request):
        try:
            page_size = int(request.query_params.get("page_size", 15))
            sku_instances = (
                HolidaySKU.objects.filter(organization_id=request.user.organization.id)
                if not request.user.is_superuser
                else HolidaySKU.objects.all()
            )

            id = request.query_params.get("id")
            search_key = request.query_params.get("search_key")
            if id:
                sku_instances = sku_instances.filter(id=id)
            if search_key:
                sku_instances = sku_instances.filter(
                    Q(name__icontains=search_key)
                    | Q(location__icontains=search_key)
                    | Q(country__country_name__icontains=search_key)
                )

            paginator = CustomPageNumberPagination(page_size=page_size)
            paginated_skus = paginator.paginate_queryset(sku_instances, request)
            serialized_data = HolidaySKUSerializerGet(paginated_skus, many=True).data
            return paginator.get_paginated_response(serialized_data)

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update_prices(self, sku_instance, prices):
        # Iterate through each price in the request
        for price in prices:
            country_id = price.get("country_id")
            price_value = price.get("price")

            if country_id and price_value:
                try:
                    country = Country.objects.get(id=country_id)

                    # Check if a price already exists for this SKU and country
                    existing_price = HolidaySKUPrice.objects.filter(
                        sku_id=sku_instance, country_id=country
                    ).first()

                    if existing_price:
                        # Update the existing price
                        existing_price.price = price_value
                        existing_price.save()  # Save the updated price
                    else:
                        # Create a new price if not found
                        HolidaySKUPrice.objects.create(
                            sku_id=sku_instance, country_id=country, price=price_value
                        )
                except Country.DoesNotExist:
                    # Skip if the country_id is invalid
                    continue

    def patch(self, request):
        id = request.data.get("id")
        if not id:
            return Response(
                {"message": "Provide the ID of the data in the request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sku_instance = HolidaySKU.objects.filter(id=id).first()
        if not sku_instance:
            return Response(
                {"message": "Object not found."}, status=status.HTTP_404_NOT_FOUND
            )
        
        user_role = request.user.role.name
        restricted_roles = [
            "agency_owner",
            "agency_staff",
            "distributor_owner",
            "distributor_staff",
            "distributor_agent",
            "out_api_owner",
            "out_api_staff"
        ]

        if user_role in restricted_roles:
            if sku_instance.status != "pending":
                return Response(
                    {"message": "You do not have permission to update this record."},
                    status=status.HTTP_403_FORBIDDEN,
                )


        serializer = HolidaySKUSerializer(
            instance=sku_instance, data=request.data, partial=True
        )
        if serializer.is_valid():
            updated_sku = serializer.save()

            # Update themes
            themes = request.data.get("themes", [])
            if themes:
                # Clear existing themes
                HolidaySKUTheme.objects.filter(sku_id=updated_sku).delete()

                # Create new themes
                self.create_themes(updated_sku, themes)

            # Update prices
            prices = request.data.get("prices", [])
            if prices:
                # Clear existing prices
                HolidaySKUPrice.objects.filter(sku_id=updated_sku).delete()
                # Create new prices
                self.create_prices(updated_sku, prices)
            # Update images
            images = request.data.get("images", [])
            if images:
                sku_instance.holidayskuimage.all().delete()
                self.create_images(sku_instance, images)

            # Update inclusions
            inclusions = request.data.get("sku_inclusions", [])
            if inclusions:
                # Delete existing inclusions
                updated_sku.holidayskuinclusion.all().delete()
                self.create_sku_inclusions(updated_sku, inclusions)

            return Response(
                {"message": "Successfully updated."}, status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        id = request.query_params.get("id")
        if not id:
            return Response(
                {"message": "Provide the id of the data in the query parameters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sku_instance = HolidaySKU.objects.filter(id=id).first()
        if not sku_instance:
            return Response(
                {"message": "Object not found."}, status=status.HTTP_404_NOT_FOUND
            )

        sku_instance.delete()
        return Response({"message": "Successfully deleted."}, status=status.HTTP_200_OK)


from tools.image_manager.image_manager import image_manager


class HolidayThemeView(APIView):
    permission_classes = []

    def post(self, request):
        image_url = request.data.get("icon_url")
        img = image_manager(image_url)
        request.data["icon_url"] = img.id
        serializer = HolidayThemeMasterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Successfully Created"}, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        theme = HolidayThemeMaster.objects.filter(status=True).order_by("-modified_at")
        serializer = HolidayThemeMasterSerializerGet(theme, many=True)
        return Response(serializer.data)

    def patch(self, request):
        id = request.data.get("id")
        if id is None:
            return Response(
                {"message": " provide the id of the data in parameter."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            themes = HolidayThemeMaster.objects.get(id=id)
        except HolidayThemeMaster.DoesNotExist:
            return Response(
                {"message": "Object not found."}, status=status.HTTP_404_NOT_FOUND
            )

        image_id = request.data.get("image_id")
        if image_id:
            try:
                gallery_instance = Gallery.objects.get(id=image_id)
                themes.icon_url = gallery_instance
            except Gallery.DoesNotExist:
                return Response(
                    {"message": "Gallery object not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        serializer = HolidayThemeMasterSerializerGet(
            instance=themes, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Objects updated successfully"}, status=status.HTTP_200_OK
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        id = request.query_params.get("id")
        if id is None:
            return Response({"message": "Provide id in parameter"})
        obj = HolidayThemeMaster.objects.filter(id=id)
        obj.delete()
        return Response({"message": "deleted successfully"})


from tools.image_manager.image_manager import image_manager


class HolidayThemeView(APIView):
    permission_classes = []

    def post(self, request):
        image_url = request.data.get("icon_url")
        img = image_manager(image_url)
        request.data["icon_url"] = img.id
        serializer = HolidayThemeMasterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Successfully Created"}, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        theme = HolidayThemeMaster.objects.filter(status=True).order_by("-modified_at")
        serializer = HolidayThemeMasterSerializerGet(theme, many=True)
        return Response(serializer.data)

    def patch(self, request):
        id = request.data.get("id")
        if id is None:
            return Response(
                {"message": " provide the id of the data in parameter."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            themes = HolidayThemeMaster.objects.get(id=id)
        except HolidayThemeMaster.DoesNotExist:
            return Response(
                {"message": "Object not found."}, status=status.HTTP_404_NOT_FOUND
            )

        image_id = request.data.get("image_id")
        if image_id:
            try:
                gallery_instance = Gallery.objects.get(id=image_id)
                themes.icon_url = gallery_instance
            except Gallery.DoesNotExist:
                return Response(
                    {"message": "Gallery object not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        serializer = HolidayThemeMasterSerializerGet(
            instance=themes, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Objects updated successfully"}, status=status.HTTP_200_OK
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        id = request.query_params.get("id")
        if id is None:
            return Response({"message": "Provide id in parameter"})
        obj = HolidayThemeMaster.objects.filter(id=id)
        obj.delete()
        return Response({"message": "deleted successfully"})


class HolidayApprovalAPI(APIView):
    # def patch(self, request):
    #     id = request.data.get("id")

    #     if not id:
    #         return Response(
    #             {"message": "Provide the id of the data in parameter."},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     holiday_sku = HolidaySKU.objects.filter(id=id).first()
    #     if not holiday_sku:
    #         return Response(
    #             {"message": "Object not found."}, status=status.HTTP_404_NOT_FOUND
    #         )
    #     previous_status = holiday_sku.status
    #     # Check if status is changing to 'Active'
    #     new_status = request.data.get("status")
    #     if new_status == "Active" and holiday_sku.status != "Active":
    #         # Retrieve prices from the request body
    #         price_data = request.data.get("prices", [])
    #         price_instances = HolidaySKUPrice.objects.filter(sku_id=holiday_sku)

    #         # Update each price instance based on price_id
    #         for price_data_item in price_data:
    #             price_id = price_data_item.get("price_id")
    #             company_markup = price_data_item.get("company_markup")

    #             if price_id and company_markup is not None:
    #                 # Find the price instance by price_id
    #                 price_instance = price_instances.filter(id=price_id).first()
    #                 if price_instance:
    #                     company_markup_decimal = Decimal(str(company_markup))

    #                     # Update company markup
    #                     price_instance.company_markup = company_markup_decimal
    #                     price_instance.save()

    #                     # Calculate the final price
    #                     final_price = price_instance.price + company_markup_decimal

    #                     # Add updated price data to the response
    #                     price_data_item["updated_price"] = final_price
    #                 else:
    #                     return Response(
    #                         {"message": f"Price with ID {price_id} not found."},
    #                         status=status.HTTP_404_NOT_FOUND,
    #                     )

    #         return Response(
    #             {"message": "Object updated successfully", "price_data": price_data},
    #             status=status.HTTP_200_OK,
    #         )

    #     # Continue with other fields if necessary
    #     serializer = HolidaySKUSerializer(
    #         instance=holiday_sku, data=request.data, partial=True
    #     )

    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response(
    #             {"message": "Object updated successfully"}, status=status.HTTP_200_OK
    #         )

    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    def patch(self, request):
        id = request.data.get("id")

        if not id:
            return Response(
                {"message": "Provide the id of the data in parameter."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        holiday_sku = HolidaySKU.objects.filter(id=id).first()
        if not holiday_sku:
            return Response(
                {"message": "Object not found."}, status=status.HTTP_404_NOT_FOUND
            )

        previous_status = holiday_sku.status
        # Check if status is changing to 'Active'
        new_status = request.data.get("status")

        # if new_status == "Active" and previous_status != "Active":
        #     # Retrieve prices from the request body
        #     price_data = request.data.get("prices", [])
        #     price_instances = HolidaySKUPrice.objects.filter(sku_id=holiday_sku)

        #     # Update each price instance based on price_id
        #     for price_data_item in price_data:
        #         price_id = price_data_item.get("price_id")
        #         company_markup = price_data_item.get("company_markup")

        #         if price_id and company_markup is not None:
        #             # Find the price instance by price_id
        #             price_instance = price_instances.filter(id=price_id).first()
        #             if price_instance:
        #                 company_markup_decimal = Decimal(str(company_markup))

        #                 # Update company markup
        #                 price_instance.company_markup = company_markup_decimal
        #                 price_instance.save()

        #                 # Calculate the final price
        #                 final_price = price_instance.price + company_markup_decimal

        #                 # Add updated price data to the response
        #                 price_data_item["updated_price"] = final_price
        #             else:
        #                 return Response(
        #                     {"message": f"Price with ID {price_id} not found."},
        #                     status=status.HTTP_404_NOT_FOUND,
        #                 )
        if new_status == "Active":
            # Retrieve prices from the request body
            price_data = request.data.get("prices", [])
            price_instances = HolidaySKUPrice.objects.filter(sku_id=holiday_sku)

            # Update each price instance based on price_id
            for price_data_item in price_data:
                price_id = price_data_item.get("price_id")
                company_markup = price_data_item.get("company_markup")

                if price_id and company_markup is not None:
                    # Find the price instance by price_id
                    price_instance = price_instances.filter(id=price_id).first()
                    if price_instance:
                        company_markup_decimal = Decimal(str(company_markup))

                        # Update company markup
                        price_instance.company_markup = company_markup_decimal
                        price_instance.save()

                        # Calculate the final price
                        final_price = price_instance.price + company_markup_decimal

                        # Add updated price data to the response
                        price_data_item["updated_price"] = final_price
                    else:
                        return Response(
                            {"message": f"Price with ID {price_id} not found."},
                            status=status.HTTP_404_NOT_FOUND,
                        )


            # Save the new status and return the response
            holiday_sku.status = new_status
            holiday_sku.save()

            return Response(
                {
                    "message": "Object updated successfully",
                    "price_data": price_data,
                },
                status=status.HTTP_200_OK,
            )

        # Handle other statuses
        serializer = HolidaySKUSerializer(
            instance=holiday_sku, data=request.data, partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Object updated successfully"}, status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            page_size = int(request.query_params.get("page_size", 15))

            id = request.query_params.get("id")
            search_key = request.query_params.get("search_key")

            sku_instances = HolidaySKU.objects.exclude(status="Active")

            if id:
                sku_instances = sku_instances.filter(id=id)

            if search_key:
                sku_instances = sku_instances.filter(
                    Q(name__icontains=search_key)
                    | Q(location__icontains=search_key)
                    | Q(country__country_name__icontains=search_key)
                )

            # Order by created_at in descending order
            sku_instances = sku_instances.order_by("-modified_at")

            # Set pagination
            paginator = CustomPageNumberPagination(page_size=page_size)

            paginated_skus = paginator.paginate_queryset(sku_instances, request)
            result_data = []

            # Iterate through each paginated SKU and build the response
            for sku_instance in paginated_skus:
                sku_serializer = HolidaySKUSerializerGet(sku_instance)
                sku_data = sku_serializer.data

                # Get all price instances related to this SKU
                prices = HolidaySKUPrice.objects.filter(sku_id=sku_instance)
                sku_data["prices"] = [
                    {   "price_id":price_instance.id,
                        "country_id": str(price_instance.country_id.id),
                        "country_name": str(
                            price_instance.country_id.lookup.country_name
                        ),
                        "price": price_instance.price,
                        "company_markup": price_instance.company_markup,
                    }
                    for price_instance in prices
                ]

                # Get themes
                theme_instances = HolidaySKUTheme.objects.filter(sku_id=sku_instance)
                sku_data["themes"] = [
                    {
                        "id": theme.theme_id.id,
                        "image_url": str(theme.theme_id.icon_url.url),
                        "name": theme.theme_id.name,
                    }
                    for theme in theme_instances
                ]

                # Get images

                image_instances = HolidaySKUImage.objects.filter(sku_id=sku_instance)
                sku_data["images"] = [
                    {
                        "id": str(image_instance.gallery_id.id),
                        "image_url": image_instance.gallery_id.url.url,
                    }
                    for image_instance in image_instances
                ]

                # Get SKU inclusions
                inclusion_instances = HolidaySKUInclusion.objects.filter(
                    sku_id=sku_instance
                )
                sku_data["sku_inclusions"] = [
                    {
                        "flight": inclusion.flight,
                        "hotel": inclusion.hotel,
                        "transfer": inclusion.transfer,
                        "meals": inclusion.meals,
                        "visa": inclusion.visa,
                        "sight_seeing": inclusion.sight_seeing,
                    }
                    for inclusion in inclusion_instances
                ]

                result_data.append(sku_data)

            return paginator.get_paginated_response(result_data)

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HolidayFavoriteView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = HolidayFavoriteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Successfully Created"}, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        page_size = int(request.query_params.get("page_size", 15))

        search_key = request.query_params.get("search_key")
        country_id = request.query_params.get("country_id")
        if not country_id:
            return Response({"message": "Provide active country_id in parameter"})

        favourite = HolidayFavourite.objects.filter(country_id=country_id)

        if search_key:
            favourite = favourite.filter(
                Q(sku_id__name__icontains=search_key)
                | Q(country_id__country_name__icontains=search_key)
            )

        favourite = favourite.order_by("-modified_at")
        paginator = CustomPageNumberPagination(page_size=page_size)
        paginated_favourites = paginator.paginate_queryset(favourite, request)

        serializer = HolidayFavoriteSerializerGet(paginated_favourites, many=True)
        return paginator.get_paginated_response(serializer.data)

    def delete(self, request):
        id = request.query_params.get("id")
        if id is None:
            return Response({"message": "Provide id in parameter"})
        obj = HolidayFavourite.objects.filter(id=id)
        obj.delete()
        return Response({"message": "deleted successfully"})

    # get all sku holiday for favourite


class SKUHolidayFavouriteGet(APIView):
    def get(self, request):
        page_size = int(request.query_params.get("page_size", 15))
        country_id = request.query_params.get("country_id")
        holiday_sku_ids = HolidayFavourite.objects.values_list("sku_id", flat=True)

        if country_id:
            price_instance = HolidaySKUPrice.objects.filter(country_id=country_id)

        price_instance_sku = price_instance.values_list("sku_id", flat=True)

        sku_instance = HolidaySKU.objects.filter(id__in=price_instance_sku).exclude(
            id__in=holiday_sku_ids
        )

        paginator = CustomPageNumberPagination(page_size=page_size)
        paginated_favourites = paginator.paginate_queryset(sku_instance, request)

        serializer = HolidaySKUSerializerGet(paginated_favourites, many=True)
        return paginator.get_paginated_response(serializer.data)


# used for create default values and suggestion for holiday web (do once)
class HolidayDefaultValues(APIView):
    def post(self, request):
        country_name = request.data.get("country_name")
        country_instance = Country.objects.get(lookup__country_name=country_name)
        country_id = country_instance.id
        request.data["country_id"] = country_id

        holiday_skus = HolidaySKUPrice.objects.filter(country_id=country_id)

        holiday_init = {"default": "", "suggestions": []}

        if holiday_skus.exists():
            default_holiday = holiday_skus[0].sku_id.name

            if holiday_skus.count() < 4:
                suggestions = [sku.sku_id.name for sku in holiday_skus]
            else:
                suggestions = [sku.sku_id.name for sku in holiday_skus[1:4]]

            holiday_init = {"default": default_holiday, "suggestions": suggestions}

        request.data["holiday"] = holiday_init
        country_default_instance = CountryDefault.objects.filter(
            country_id=country_id
        ).first()
        if country_default_instance:
            if country_default_instance.holiday:
                serializer = CountryDefaultSerializer(
                    country_default_instance, data=request.data, partial=True
                )
                if serializer.is_valid():
                    serializer.save()
                    return Response(
                        "Updated Already Existing Data in Holiday Field",
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )
            country_default_instance.holiday = holiday_init
            serializer = CountryDefaultSerializer(
                country_default_instance, data=request.data, partial=True
            )
            if serializer.is_valid():
                serializer.save()
                return Response("Updated Null Holiday Field", status=status.HTTP_200_OK)
        else:
            serializer = CountryDefaultSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    "Successfully created new record with Holiday details",
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        country_id = request.query_params.get("country_id")
        if not country_id:
            return Response(
                {"message": "country_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        default_values = CountryDefault.objects.filter(country_id=country_id)

        serializer = CountryDefaultSerializer(default_values, many=True)

        filtered_data = [data for data in serializer.data if data.get("holiday")]

        return Response(filtered_data, status=status.HTTP_200_OK)


class HolidayQueuesView(ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = HolidayEnquirySerializer
    pagination_class = CustomPageNumberPagination
    filter_backends = [
        CustomSearchFilter,
        DateFilter,
        HolidayEnquirySupplierFilter,
        HolidayEnquiryStatusFilter,
    ]
    search_fields = [
        "holiday_id__name",
        "enquiry_ref_id",
    ]

    def get_queryset(self):
        user = self.request.user


        user_role = user.role.name if user.role else None
        user_organization = user.organization
#
        if user_role in ["super_admin","operations"]:
            return HolidayEnquiry.objects.all().order_by("-created_at")
        
        if not user_organization:
            return HolidayEnquiry.objects.none()
        if user_role in [
            "agency_owner",
            "agency_staff",
            "distributor_owner",
            "distributor_staff",
            "out_api_owner",
            "out_api_staff"
        ]:
            return HolidayEnquiry.objects.filter(
                user__organization=user_organization
            ).order_by("-created_at")

        elif user_role == "distributor_agent":
            return HolidayEnquiry.objects.filter(user=user).order_by("-created_at")
        return HolidayEnquiry.objects.none()


class HolidayQueueStatusList(ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = HolidayQueueStatusSerializer
    queryset = LookUpHolidayEnquiryStatus.objects.all().order_by('progression_order')


class UpdateHolidayQueueStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = UpdateHolidayEnquiryStatusSerializer(data=request.data)
        if serializer.is_valid():
            id = serializer.validated_data["id"]
            status_id = serializer.validated_data["status_id"]

            try:
                enquiry = HolidayEnquiry.objects.get(id=id)
                user_email = [enquiry.email if enquiry.user else None]
                
                status_instance = LookUpHolidayEnquiryStatus.objects.get(id=status_id)
                status_name = status_instance.name
                enquiry.status = status_instance
                enquiry.save()
                HolidayEnquiryHistory.objects.create(
                    holiday_enquiry_id=enquiry,
                    status=status_instance,
                    updated_by=request.user,
                )
                user_obj = request.user
                currentdate =  datetime.now()
                formated_date = currentdate.strftime("%d-%m-%Y")
                print("formated_date", formated_date)
                data_dict = {
                    "country_name":user_obj.base_country.lookup.country_name, 
                    "user_name" : enquiry.name if enquiry.user else None,
                    "traveler_name": enquiry.name,
                    "destination": enquiry.holiday_id.name,
                    "booking_id" : enquiry.enquiry_ref_id,
                    "organization_name": enquiry.user.organization.organization_name
                    }
                
                if status_name :
                    event_name = '_'.join(word.capitalize()for word in status_name.split(" "))
                if event_name:
                    thread = threading.Thread(target=invoke, kwargs={
                                            "event":event_name,
                                            "number_list":[], 
                                            "email_list":user_email,
                                            "data" :data_dict
                                            })
                    thread.start()

                return Response(
                    {"message": "Enquiry status updated successfully."},
                    status=status.HTTP_200_OK,
                )


            except HolidayEnquiry.DoesNotExist:
                return Response(
                    {"error": "Enquiry not found."}, status=status.HTTP_404_NOT_FOUND
                )
            
            except LookUpHolidayEnquiryStatus.DoesNotExist:
                return Response(
                    {"error": "Status not found."}, status=status.HTTP_404_NOT_FOUND
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class HolidaySupplierListView(ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = Organization.objects.annotate(holiday_count=Count("holidaysku")).filter(
        holiday_count__gt=0
    )
    serializer_class = HolidaySupplierListSerializer


class HolidayTestScript(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response(
            {
                "data": [
                    {"id": v.id, "country_id": v.country_id}
                    for v in HolidaySKU.objects.all()
                ]
            }
        )


class HolidayTestScript2(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        data = [
            {
                "id": "2f012583-d924-4a2e-abdf-08b9201e9ec8",
                "country_id": "44499dfe-2bc0-43bd-9388-7ed365afc766",
            },
            {
                "id": "5446a4da-d53b-4912-b9c5-775beda649ee",
                "country_id": "692be641-5af0-4beb-b935-09dc4114418f",
            },
            {
                "id": "2ae9cf41-4ff7-4b97-bcbb-81ff6a0ab514",
                "country_id": "44499dfe-2bc0-43bd-9388-7ed365afc766",
            },
            {
                "id": "12b78ae6-f829-4129-bce1-8ce003cfe324",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "ee0d7b1f-b85c-4d4a-b2d1-ab9e7c68cdb0",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "e16ed22f-4e98-47c6-b991-928f2b431170",
                "country_id": "310cd1cd-74f3-46f1-bd28-be33cc69d13f",
            },
            {
                "id": "316c28b9-1f9c-461f-b39f-3b2f55624865",
                "country_id": "b9898aef-8cf1-43e8-988d-7edab1fd6624",
            },
            {
                "id": "3a8115cd-24f2-4a05-9162-2017db1ac183",
                "country_id": "c1e39a86-0759-4238-b177-5a94e0217b70",
            },
            {
                "id": "006d3c95-86e2-4dc6-9e8d-04861307bdb7",
                "country_id": "3ed8b434-9412-42b3-a7c3-bbbcf15cd452",
            },
            {
                "id": "59aee18e-1fd6-46d9-ba18-eb5f796a5e74",
                "country_id": "3ed8b434-9412-42b3-a7c3-bbbcf15cd452",
            },
            {
                "id": "67026728-ddac-45d8-9be7-9b7732063bec",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "65c04003-64dc-4694-b5aa-0fc11aae0a52",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "f3eb446a-2d79-4ed8-95ad-f77613bf0b9d",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "72590491-6105-45d1-b364-5cd5f32a4217",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "add42f56-3d04-46ad-b790-e912c4db2f03",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "2f9446ba-cf68-4fc4-bb34-2c533c153f41",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "51843288-3150-4207-9e6b-d77ef1fd3671",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "c708c367-2ab9-4576-9ae9-c922862aa68a",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "a5ed06c1-680f-41fb-be26-1f6ee4dd352a",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "30d2f282-50d1-4580-b655-0a982b6f16c2",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "cb58fe2b-0114-401e-ad5d-2658a5bbf9fe",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "9f410097-8317-4350-a5e0-41e3e7615f6b",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "154fe7e0-fa56-460c-a74a-c982341b5cd6",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "f5045f9b-c642-44b3-9c54-b203a22bbd2a",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "3a25697b-4a7c-4a8b-96ed-0b3796bdf5e6",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
            {
                "id": "d56dd143-601b-4c22-9462-2cbea64404d7",
                "country_id": "13b57be5-442d-40a3-ac7e-007f954bea32",
            },
        ]

        for i in data:
            s = LookupCountry.objects.get(id=i["country_id"])
            obj = HolidaySKU.objects.get(id=i["id"])
            obj.country.add(s)
            obj.save()
        return Response({"data": "ss"})
