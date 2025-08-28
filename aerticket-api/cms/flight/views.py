from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
from users.models import Country

class UserIP(APIView):
    authentication_classes = []
    permission_classes = []

    def get_user_ip(self, request):
        client_id = request.META.get("HTTP_X_FORWARDED_FOR", None)
        if not client_id:
            client_id = request.META.get("REMOTE_ADDR", None)
        return client_id

    def get_country_details(self, country_name):
        try:
            country = Country.objects.get(
                lookup__country_name__iexact=country_name, is_active=True
            )
            return {
                "currency_name": country.currency_name,
                "currency_code": country.currency_code,
                "country_name": country_name,
                "country_code": country.lookup.country_code,
                "country_id": country.id,
                "currency_symbol": country.currency_symbol,
                "inr_conversion_rate": str(country.inr_conversion_rate),
            }
        except Country.DoesNotExist:
            try:
                india = Country.objects.get(
                    lookup__country_name__iexact="India", is_active=True
                )
                return {
                    "currency_name": india.currency_name,
                    "currency_code": india.currency_code,
                    "currency_symbol": india.currency_symbol,
                    "inr_conversion_rate": str(india.inr_conversion_rate),
                    "country_name": india.lookup.country_name,
                    "country_code": india.lookup.country_code,
                    "country_id": india.id,
                }
            except Country.DoesNotExist:
                return {
                    "currency_name": "Indian Rupee",
                    "currency_code": "INR",
                    "currency_symbol": "₹",
                    "inr_conversion_rate": "1.0",
                    "country_name": "India",
                    "country_code": "IN",
                    "country_id": 123,
                }

    def get(self, request, *args, **kwargs):
        ip_address_list = self.get_user_ip(request)
        # ip_address = ip_address_list.split(",")[0]
        ip_address = '103.141.54.122'
        base_url = "http://api.ipstack.com/"
        ipstack_access_key = "ab5f3a703752ff9e1668bdbb22be0b8b"
        url = f"{base_url}{ip_address}?access_key={ipstack_access_key}"
        try:
            response = requests.get(url)
            response_data = response.json()
            country_name = (response_data.get("country_name") or "").strip()

            if country_name:
                country_details = self.get_country_details(country_name)
                return Response(country_details, status=status.HTTP_200_OK)
            else:
                country_details = self.get_country_details("India")
                return Response(country_details, status=status.HTTP_200_OK)

        except requests.RequestException as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# class GalleryUploadView(APIView):
#     authentication_classes = []
#     permission_classes = []
#     def get(self, request, *args, **kwargs):
#         galleries = Gallery.objects.all()
#         serializer = GallerySerializer(galleries, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)
#     def post(self, request, *args, **kwargs):
#         serializer = GallerySerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             response_data = {
#                 'message': 'Image uploaded successfully',
#                 'data': serializer.data
#             }
#             return Response(response_data, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)