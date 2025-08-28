from django.http import JsonResponse
from common.permission import HasAPIAccess
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.shortcuts import render, redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from common.models import PaymentDetail, Payments, LookupAirports, LookupAirline
from common.serializers import AirportSerializer, LookupAirlineSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import status

from vendors.manager import get_manager_class
from .razor_pay import razor_webhook, razorpay_payment
from django.shortcuts import get_object_or_404
from rest_framework import  status
import os
import threading
from django.db.models import Q
import requests
import xml.etree.ElementTree as ET
import json
from dotenv import load_dotenv
import importlib



load_dotenv()
callback_url = os.getenv('CALLBACK_URL_RAZORPAY_BOOKING')
bta_web_url = os.getenv('WEB_URL_RAZORPAY_BOOKING')

class RazorCallbackApi(APIView):
    permission_classes = []
    authentication_classes = []
    def get(self, request):
        try:
            callback_status = request.query_params.get('confirmation')
            module = request.query_params.get("module")
            if callback_status == "success":
                kwargs = {"razorpay_payment_id" : request.query_params.get('razorpay_payment_id'),
                "razorpay_payment_link_id" : request.query_params.get('razorpay_payment_link_id'),
                "razorpay_payment_link_status" : request.query_params.get('razorpay_payment_link_status'),
                "status":callback_status
                }
                payment_obj = Payments.objects.filter(payment_id_link=kwargs.get('razorpay_payment_link_id'),call_back=False,status="unpaid").first()
                if payment_obj:
                    payment_obj.status = "paid"
                    payment_obj.call_back = True
                    payment_obj.razorpay_payment_id = kwargs.get("razorpay_payment_id")
                    payment_obj.save()
                    data = {"booking_id":request.query_params.get("booking_id"),
                                "session_id":request.query_params.get("session_id"),
                                "from_razorpay":True,
                                "razorpay_payment_link_id":kwargs.get('razorpay_payment_link_id'),
                                "module":module}
                    thread = threading.Thread(target = razor_webhook, args=(data,))
                    thread.start()
                return redirect(f"{bta_web_url}{module}/payment-success")
            else:
                return redirect(f"{bta_web_url}{module}/payment-failure")       
        except:
            return Response({"status":False})

class SearchAirport(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]

    @swagger_auto_schema(
        operation_id="1_SearchAirport",
        operation_summary="1 - Search Airports",
        operation_description=(
            "Search for airports by code (exact or partial), airport name, or city. "
            "If a `search_key` is provided, the system first looks for **exact matches** by airport code (case-insensitive). If exact matches are found, those are returned first. "
            "Then it searches for **partial matches** (airport `code`, `name`, or `city` containing the `search_key`). "
            "Finally, it combines both results into one list, ordered such that exact matches appear first, followed by partial matches, limited by the `limit` parameter. "
            "If no `search_key` is provided, it simply returns the top `limit` airports."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="search_key",
                in_=openapi.IN_QUERY,
                description="Search string for code, airport name, or city (case-insensitive).",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                name="limit",
                in_=openapi.IN_QUERY,
                description="Number of records to return. Defaults to 10 if not provided or invalid.",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ],
        responses={
            200: openapi.Response(
                description="Successful retrieval of airports",
                # Option 1: Provide an example without a schema reference:
                examples={
                    "application/json": {
                    "status": True,
                    "message": "Airports retrieved successfully.",
                    "data": [
                        {
                            "name": "Chhatrapati Shivaji International Airport",
                            "code": "BOM",
                            "city": "Mumbai",
                            "country": "India",
                            "common": "BOM",
                            "latitude": 19.0901312,
                            "longitude": 72.86370318520977
                        }
                    ],
                    "errors": ""
                }
                }
                # Option 2: Provide a serializer schema:
                # schema=AirportSerializer(many=True)
            ),
            400: openapi.Response(
                description="Invalid request or error retrieving airports",
                examples={
                    "application/json": {
                        "status": False,
                        "message": "Error retrieving airports.",
                        "data": [],
                        "errors": "Error details..."
                    }
                }
            ),
        },
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Misc"],  # You can group endpoints by tags in Swagger
    )
    def get(self, request, *args, **kwargs):
        try:
            search_key = request.query_params.get("search_key", "")
            limit_str = request.query_params.get("limit", 10)

            # Attempt to parse limit from the query parameter
            try:
                limit = int(limit_str)
            except ValueError:
                limit = 10
                pass  # If invalid, we'll just treat it as "limit = 10"

            # Get all airports
            queryset = LookupAirports.objects.all()

            # If user provided a search_key, try exact match first
            if len(search_key) > 0:
                exact_match_qs = queryset.filter(code__iexact=search_key)

                # Partial match (excluding exact-match rows)
                partial_match_qs = queryset.exclude(pk__in=exact_match_qs).filter(
                    Q(code__icontains=search_key) |
                    Q(name__icontains=search_key) |
                    Q(city__icontains=search_key)
                )

                # Combine in Python so that exact matches appear first
                combined_results = list(exact_match_qs) + list(partial_match_qs)
                # If limit is provided, slice the queryset
                if len(combined_results)>limit:
                    combined_results = combined_results[:limit]
            else:
                combined_results = queryset[:limit]
            serializer = AirportSerializer(combined_results, many=True)

            response_data = {
                "status": True,
                "message": "Airports retrieved successfully.",
                "data": serializer.data,
                "errors": ""
            }

            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            # In case of any error, return a standardized error response
            response_data = {
                "status": False,
                "message": "Error retrieving airports.",
                "data": [],
                "errors": str(e)
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
    @swagger_auto_schema(auto_schema=None) 
    def post(self, request, *args, **kwargs):
        return self.method_not_allowed()
    @swagger_auto_schema(auto_schema=None) 
    def put(self, request, *args, **kwargs):
        return self.method_not_allowed()
    @swagger_auto_schema(auto_schema=None) 
    def patch(self, request, *args, **kwargs):
        return self.method_not_allowed()
    @swagger_auto_schema(auto_schema=None) 
    def delete(self, request, *args, **kwargs):
        return self.method_not_allowed()

    def method_not_allowed(self):
        response_data = {
            "status": False,
            "message": "Only GET method is allowed for this endpoint.",
            "data": [],
            "errors": "MethodNotAllowed"
        }
        return Response(response_data, status=status.HTTP_405_METHOD_NOT_ALLOWED)

class CreditBalanceView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="GetCreditBalance",
        operation_summary="Retrieve wallet credit balance",
        operation_description=(
            "Fetches the available credit balance and credit limit."
        ),
        responses={
            200: openapi.Response(
                description="Wallet Balance retrieved successfully",
                examples={
                    "application/json": {
                        "status": True,
                        "message": "Wallet Balance retrieved successfully.",
                        "data": {
                            "Available Balance": 5000.00,
                            "Credit Limit": 10000.00
                        },
                        "errors": ""
                    }
                }
            ),
            400: openapi.Response(
                description="Bad request (Error retrieving wallet balance)",
                examples={
                    "application/json": {
                        "status": False,
                        "message": "Error retrieving Wallet Balance. Please contact our customer support.",
                        "data": [],
                        "errors": "Detailed error message"
                    }
                }
            ),
        },
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Wallet"],  # You can group endpoints by tags in Swagger
        security=[{'Bearer': []}]
    )
    def get(self, request):
        try:
            org_obj = request.user.organization
            billing_account_obj = org_obj.easy_link_billing_account.data[0]
            base_url = billing_account_obj['url']
            s_account_code = org_obj.easy_link_account_code
            portal_reference_code = billing_account_obj['portal_reference_code']
            url = f"{base_url}/getAvlCreditLimit/?PortalRefCode={portal_reference_code}&sAcCode={s_account_code}&sRefAcCode="
            header = {"Content-Type":"text/plain"}
            response = requests.post(url=url, headers=header)
            xml_response = response.text
            # Extract the inner XML from the string
            inner_xml = xml_response.split("&lt;")[1].split("&gt;")[0]
            inner_xml = f"<{inner_xml}>"  

            # Parse the XML
            root = ET.fromstring(inner_xml)

            # Convert XML attributes to a dictionary
            result = {root.tag: root.attrib}

            limit_data = result['Limit']
            # Fields for Available Limit
            available_limit_fields = ["L", "F", "V", "I", "O", "H"]

            # Fields for Credit Limit
            credit_limit_fields = ["LC", "FC", "VC", "IC", "OC", "HC"]

            # Calculate Available Limit and Credit Limit
            available_limit = sum(float(limit_data[field]) for field in available_limit_fields)
            credit_limit = sum(float(limit_data[field]) for field in credit_limit_fields)

            # Return results as a dictionary
            data =  {
                "Available Balance": available_limit,
                "Credit Limit": credit_limit
            }

            response_data = {
                "status": True,
                "message": "Wallet Balance retrieved successfully.",
                "data": data,
                "errors": ""
            }

            return Response(response_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            response_data = {
                "status": False,
                "message": "Error retrieving Wallet Balance. Please contact our customer support.",
                "data": [],
                "errors": str(e)
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

class SearchAirline(APIView):
    @swagger_auto_schema(
        operation_id="2_SearchAirline",
        operation_summary="2 - Search Airlines",
        operation_description=(
            "Fetch a list of airlines filtered by a search key in the name or code field. "
            "The results are prioritized by matches in the code field and are limited by the 'limit' query parameter."
        ),
        manual_parameters=[
            openapi.Parameter(
                "search_key", openapi.IN_QUERY, 
                description="Search term to filter airlines by name or code.", 
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "limit", openapi.IN_QUERY, 
                description="Number of results to return. Defaults to 10 if not provided or invalid.", 
                type=openapi.TYPE_INTEGER
            ),
        ],
        responses={
            200: openapi.Response(
                description="Successful retrieval of airports",
                # Option 1: Provide an example without a schema reference:
                examples={
                    "application/json": {
                    "status": True,
                    "message": "Airlines retrieved successfully.",
                    "data": [
                        {"name": "IndiGo",
                        "code": "6E"}
                    ],
                    "errors": ""
                }
                }
            ),
            400: openapi.Response(
                description="Invalid request or error retrieving airlines",
                examples={
                    "application/json": {
                        "status": False,
                        "message": "Error retrieving airlines.",
                        "data": [],
                        "errors": "Error details..."
                    }
                }
            )
        },
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Misc"],  # You can group endpoints by tags in Swagger
    )
    def get(self, request, *args, **kwargs):
        try:
            # Get query parameters
            search_key = request.query_params.get("search_key", "")
            limit_str = request.query_params.get("limit", 10)

            # Convert limit to an integer and handle invalid values
            try:
                limit = int(limit_str)
            except ValueError:
                limit = 10  # Default value

            # Filter airlines by search key in name or code (case-insensitive)
            airlines = LookupAirline.objects.exclude(name__in=["name", ""])

            if len(search_key) > 0:
                airlines = airlines.filter(
                    Q(name__icontains=search_key) | Q(code__icontains=search_key)
                )

            # Order by code and name
            airlines = airlines.order_by('code', 'name')
            # Apply limit
            if len(airlines)>limit:
                airlines = airlines[:limit]

            # Serialize data
            serializer = LookupAirlineSerializer(airlines, many=True)
            response_data = {
                "status": True,
                "message": "Successfully retrieved airlines.",
                "data": serializer.data,
                "errors": ""
            }
            # Return response
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            # Standardized error response
            response_data = {
                "status": False,
                "message": "Error retrieving airlines.",
                "data": [],
                "errors": str(e)
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

class PaymentView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        
        payment_id = request.data['payment_id']
        payment_method = request.data['payment_method']
        payment_detail = get_object_or_404(PaymentDetail, id=payment_id)

        if not payment_detail and not payment_detail.created_by != request.user:
            return JsonResponse({"error":'invalid payment id for user'}, status=400)

        booking_amount = payment_detail.amount

        manager = get_manager_class(payment_detail.payment_handler)  # Get the class
        manager = manager(request.user) 

        try:
            payment_module = manager.module_name
        except:
            raise Exception(f'missing module_name attribute in {payment_detail.payment_handler}')
        
        razor_response = razorpay_payment(user = payment_detail.created_by,
                                          booking_id = str(payment_detail.id),
                                          amount = booking_amount,
                                          module = payment_module,
                                          payment_method = payment_method)                                            
        payment_status = True if razor_response.get("status") else False

        payment_detail.payment_method = payment_method
        payment_detail.payment_id = razor_response.get('payment_id')
        payment_detail.save()

        try:
            manager.initiate_payment(payment_id)
        except:
            raise Exception(f'missing initiate_payment function in {payment_detail.payment_handler}')
        if payment_method == 'wallet':

            if payment_detail:
                try:
                    manager = get_manager_class(payment_detail.payment_handler)  # Get the class
                    manager = manager(payment_detail.created_by)
                except:
                    raise Exception(f'missing "{payment_detail.payment_handler}" class in vendors.manager') 
                try:
                    manager.purchase(payment_detail.id)
                except:
                    raise Exception(f'missing "purchase" function in {payment_detail.payment_handler}')
            else:
                raise Exception(f'missing "payment detail" object in {payment_detail.payment_handler}')
            razor_response = {"short_url":f"{bta_web_url}{manager.module_name}/payment-success","payment_id":payment_detail.id,"status":True}
            return JsonResponse({"payment_status":payment_status,"checkout_details":razor_response,"show_purchase_success":True}, status=200)
        
        return JsonResponse({"payment_status":payment_status,"checkout_details":razor_response,"show_purchase_success":False}, status=200)
