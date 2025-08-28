from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from integrations.suppliers.models import OrganizationSupplierIntegeration, SupplierIntegration
from .models import *
from django.contrib.auth.hashers import check_password
from django.utils import timezone
import random
from datetime import timedelta
from django.contrib.auth import login
from rest_framework import authentication, permissions
from django.contrib.auth.models import User
from .models import *
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db.models import F, Q
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken , AccessToken
from tools.custome_jwt_token.jwt_token import get_jwt_token
from django.contrib.auth.hashers import make_password
from rest_framework import viewsets
from users.serializers import *
from .serializers import *
from PyGeneratePassword import PasswordGenerate
import environ
from django.db.models import Q, Count, Max
from rest_framework.generics import RetrieveAPIView,ListAPIView,UpdateAPIView
from common.views import CustomPageNumberPagination,CustomSearchFilter,DateFilter
from rest_framework import filters
from tools.easy_link.helper import *
from tools.easy_link.xml_restructure import XMLData
from tools.easy_link.errors import *
from accounting.shared.models import OrganizationFareAdjustment
from accounting.shared.models import  CreditLog
from accounting.shared.services import get_accounting_software_credentials,get_credit_limit
from django.http import HttpRequest
from datetime import datetime
from tools.integration.send_sms_general import VoicenSMS

from .services import jwt_encode, jwt_decode, get_local_ip, get_model_fields, get_user_permision,getorganizationtheme
##
env = environ.Env()
environ.Env.read_env
from phonenumbers import NumberParseException
import phonenumbers
from django.shortcuts import get_object_or_404
from api.settings import WEB_URL
from rest_framework.pagination import PageNumberPagination
import logging

logger = logging.getLogger(__name__)
from tools.time_helper import time_converter
from tools.kafka_config.config import invoke,send_sms
from bs4 import BeautifulSoup
import csv
from integrations.general.models import Integration
from geopy.distance import geodesic
import secrets
import string
import random
import base64
import requests
import threading
import pandas as pd
from io import StringIO
import re
import os
from api import settings
import boto3
import math
from io import BytesIO
from django.forms.models import model_to_dict
from .permission import HasAPIAccess
from urllib.parse import urlparse
from django.db.utils import IntegrityError    
from collections import defaultdict
from uuid import UUID

def generate_otp(user_obj):
    code = random.randint(100000, 999999)
    expiration_time = timezone.now() + timedelta(minutes=3)
    error_count = 0
    user_obj.is_active = True
    user_obj.save()
    otp_obj, created = OtpDetails.objects.update_or_create(
        user=user_obj,
        defaults={
            "code": code,
            "expiration_time": expiration_time,
            "error_count": error_count,
        },
    )
    return code

# class CustomPageNumberPagination(PageNumberPagination):
#     def __init__(self, page_size=15, *args, **kwargs):
#         self.page_size=page_size
#         return super().__init__(*args,**kwargs)
#     page_size_query_param = 'page_size'
#     max_page_size = 100

class Initialize(APIView):
    """
    A class-based view that handles user initialization requests.
    This view provides an endpoint to retrieve the user's IP address and the 
    default calling code. It uses no authentication or permission classes.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request:HttpRequest) -> Response:
        """
        Handle GET requests to retrieve user information.

        This method fetches the user's IP address and returns it alongside 
        a default calling code.

        Args:
            request (Request): The HTTP request object.

        Returns:
            Response: A JSON response containing the user's IP address 
                      and a default calling code.
        """
        ip_address = self.get_user_ip(request)
        return Response({"calling_code": ["+"], "ip_address": ip_address})

    def get_user_ip(self, request:HttpRequest) -> str:
        """
        Retrieve the user's IP address from the request.

        This method checks if the request contains the user's IP address in 
        the `HTTP_X_FORWARDED_FOR` header (used when the request is proxied). 
        If not found, it falls back to `REMOTE_ADDR`.

        Args:
            request (Request): The HTTP request object.

        Returns:
            str: The user's IP address.
        """
        
        client_id = request.META.get("HTTP_X_FORWARDED_FOR", None)
        if not client_id:
            client_id = request.META.get("REMOTE_ADDR", None)
        return client_id


class Login(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        unique_id = request.data.get('unique_id')
        login_type = request.data.get('type')
        if login_type == 'email':
            unique_id = unique_id.strip().lower()

        password = request.data.get('password')
        country_name = request.data.get('country_name',None)
        if (country_name is None or country_name==''):
            return Response({"message":"please enter country name"},status=status.HTTP_400_BAD_REQUEST) 
        if not unique_id or not password:
            return Response(
                {"message": "email and password missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            if login_type == 'email':
                print("email",unique_id)
                user_obj = UserDetails.objects.filter(
                    (Q(email=unique_id)) &
                    Q(is_active=True)
                )

            elif login_type == 'phone':
                print("phone")
                user_obj = UserDetails.objects.filter(
                    (Q(phone_number=unique_id)) &
                    Q(is_active=True)
                )
            elif login_type == 'agency_id':
                print("agency_id")
                user_obj = UserDetails.objects.filter(
                Q(organization__easy_link_billing_code=unique_id) &
                Q(is_active=True) & 
                Q(role__name__in=['distributor_owner', 'agency_owner','super_admin','out_api_owner'])
                )
            if not user_obj or not check_password(password, user_obj.first().password):
                return Response(
                    {"message": "Invalid Email Or Password"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            else:
                user_obj = user_obj.first()
                if user_obj.organization.status == "pending":
                    return Response({"error_code":1, "message":"Your Organization is under review please wait..."},status=status.HTTP_410_GONE)
                if user_obj.organization.status == "inactive":
                    return Response({"error_code":1, "message":"Your Organization is Blocked please contact admin."},status=status.HTTP_410_GONE)

            # server_ip = get_local_ip()
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                # In case of multiple proxies, take the first IP (real client IP)
                server_ip = x_forwarded_for.split(',')[0].strip()
            else:
                # Fallback to REMOTE_ADDR if X-Forwarded-For is not set
                server_ip = request.META.get('REMOTE_ADDR')
            ErrorLog.objects.create(
                module="local---ip", erros={"local_ip": str(server_ip)}
            )
            if (not user_obj.last_login_ip) or (user_obj.last_login_ip != server_ip) :
                # user_obj.last_login_ip = server_ip
                # user_obj.save()
                pass
                
            else:
                kwargs = {
                    "user": str(user_obj.id),
                    "sec" : 86400
                }
                token = jwt_encode(kwargs)

                return Response({"otp_required":False,"token":token},status=status.HTTP_200_OK)

            otp = generate_otp(user_obj)
            # voicensms = VoicenSMS(number_list=[user_obj.phone_number],data={"country_name":country_name,"otp":otp})
            # voicensms.sms_integration
            sms_thread = threading.Thread(target=send_sms,  kwargs={ "number_list": [user_obj.phone_number],
                                             "data": {"country_name": country_name, "otp": otp}
                                            })
            sms_thread.start()
            thread = threading.Thread(target=invoke, kwargs={
                                                        "event":"SEND_LOGIN_OTP",
                                                        "number_list": [] if not user_obj.phone_code else [f"{user_obj.phone_code}{user_obj.phone_number}"],
                                                        "email_list": [user_obj.email],
                                                        "data": {
                                                            "otp": otp,
                                                            "country_name": country_name,
                                                            "customer_email": user_obj.email
                                                        }})
            thread.start()
            is_first_time = user_obj.is_first_time
            user_name = user_obj.first_name + user_obj.last_name
            data = {"message": "OTP sent successfully",
                             "otp_required":True,
                             "is_first_time":is_first_time,
                             'user_name':user_name,
                             }
            if settings.DEBUG:
                data['otp']= otp
                return Response(data, status=status.HTTP_200_OK)
            return Response(data, status=status.HTTP_200_OK)
        except  Exception as e:
            print("Exception ",str(e))
            return Response(
                {"message": "User not found"}, status=status.HTTP_409_CONFLICT
            )

class Pagination(PageNumberPagination):
    def __init__(self, page_size=25, *args, **kwargs):
        self.page_size = page_size  # You can adjust the page size here
        self.page_size_query_param = "page_size"
        self.max_page_size = 100
        return super().__init__(*args, **kwargs)


class OtpVerify(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            unique_id = request.data.get("unique_id")
            login_type = request.data.get('type')
            if login_type == 'email':
                unique_id = unique_id.strip().lower()

            user_otp = request.data.get("otp")
        except Exception as e:
            return Response({"key {} missing in body".format(e)})
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # In case of multiple proxies, take the first IP (real client IP)
            server_ip = x_forwarded_for.split(',')[0].strip()
        else:
            # Fallback to REMOTE_ADDR if X-Forwarded-For is not set
            server_ip = request.META.get('REMOTE_ADDR')
        # server_ip = get_local_ip()
        otp = OtpDetails.objects.filter(
            (Q(user__email=unique_id) | Q(user__phone_number=unique_id) | Q(user__organization__easy_link_billing_code=unique_id))
            & Q(code=user_otp)
        ).first()
        if otp and not otp.expiration_time <= timezone.now():
            token = get_jwt_token(otp.user)
            user_permissions = self.get_user_permision(
                otp.user.id, otp.user.is_superuser
            )
            if (not otp.user.last_login_ip) or (otp.user.last_login_ip != server_ip) :
                otp.user.last_login_ip = server_ip
                otp.user.save()
            theme = getorganizationtheme(otp.user.organization)
            return Response(
                {
                    "message": "OTP verification successful",
                    "access_token": token["access_token"],
                    "refresh_token": token["refresh_token"],
                    "permissions": user_permissions,
                    "User_Name": otp.user.first_name,
                    # "show_proxy": self.show_proxy(otp.user),
                    "show_proxy":otp.user.is_client_proxy,
                    "user_role":otp.user.role.name,
                    "theme":theme,
                    "organization":{
                        "organization_name":otp.user.organization.organization_name,
                        "phone_number":otp.user.organization.support_phone,
                        "email":otp.user.organization.support_email
                    }
                },
                status=status.HTTP_200_OK,
            )
        else:
            otp_objs = OtpDetails.objects.filter(
                Q(user__email=unique_id) | Q(user__phone_number=unique_id)
            ).first()
            if otp_objs.user.is_active:
                otp_objs.error_count += 1
                otp_objs.save()
                if otp_objs.error_count == env.int("MAX_ERROR_COUNT", default=5):  
                    try:
                        otp_objs.user.is_active = False
                        otp_objs.user.save()

                        user_ticket_creation(otp_objs.user, status_key="Limit_Reached")

                        return Response(
                            {"message": "User Limit Expired, Please login again"}
                        )
                    except Exception as e:
                        print("Error occurred while deactivating user:", e)
            else:
                return Response({"message": "User Limit Expired, Please login again"})
        return Response(
            {"message": "Invalid OTP or OTP expired"},
            status=status.HTTP_400_BAD_REQUEST,
        )
        
        
        
        
        
        
        
    def show_proxy(self, user):
        return user.role.name in ["super_admin","admin","operations","finance","sales"]

    def get_user_permision(self, user_id, is_super_user):
        user = UserDetails.objects.get(id=user_id)
        # getting all the fieldss of the lookupmodels
        field_names = self.get_model_fields(LookupPermission)
        # geting the default permision set on lookupmodal
        if is_super_user:
            field_values = {field: True for field in field_names}
        
        else:
            role_id = user.role.id
            user_role = LookupRoles.objects.filter(id=role_id).first()
            default_permission = user_role.lookup_permission
            if user.user_group:
                default_permission = user.user_group.permission
            # showing all the fields from lookup permision weather it true or false

            field_values = {
                field: getattr(default_permission, field) for field in field_names
            }
        # filtering all the true fields because we just need to show only the permision for the roles
        true_fields_values = {key: values for key, values in field_values.items()}

        # structuring permision for front-end

        strucured_permision = self.structure_permision(true_fields_values)
        return strucured_permision

    def get_model_fields(self, model):
        fields = model._meta.get_fields()
        remove_fields = [
            "id",
            "is_deleted",
            "deleted_at",
            "created_at",
            "modified_at",
            "deleted_at",
            "name",
        ]
        field_names = [
            field.name
            for field in fields
            if not field.many_to_one and not field.one_to_many
        ]
        return [field for field in field_names if field not in remove_fields]
    
    def structure_permision(self,permision_dict):
        formated_list = [f'{key}_{str(item).lower()}' for key,item in permision_dict.items()]
        default_dict = {}
        nested_dict = default_dict
        for i in formated_list:
            
            #  we are giving a space eg "control panel"  we need space in between these word our current code doesn't satify
            # that's why we are giving this if condiditon
            # if you want to have space you need to give this key word "1space1"
            # don't forget to change in models we need to update in 2 models lookup and permisison
            
            if "1space1" in i:
                i = ' '.join(i.split('1space1'))
            
            #--------- end space condition ----------
                        
            if "1hyphen1" in i:
                i = '-'.join(i.split('1hyphen1'))

            
            counter_split = i.split("_")
            splited = i.split("_", len(counter_split) - 2)
            counter = len(splited) - 1
            for letters in splited:
                try:
                    nested_dict = nested_dict[letters]
                except:
                    if counter == 0:
                        perm = letters.split("_")
                        bool_dict = {}
                        for i in range(0, int(len(perm) / 2)):
                            current = perm[i]
                            bool_value = eval(str(perm[i+1]).title())
                            
                            bool_dict[current] = bool_value
                            perm = perm[2:]
                        nested_dict.update(bool_dict)
                        pass
                    else:
                        nested_dict[letters] = {}
                        nested_dict = nested_dict[letters]
                counter -= 1
            nested_dict = default_dict
        return default_dict
    

class WithoutOtpVerify(APIView):
    
    permission_classes = [AllowAny]

    def post(self, request):
        
        token = request.data.get('token')
        decoded_data = jwt_decode(token)
        user_id = decoded_data.get('user')
        
        if not user_id:
            return Response({"message":decoded_data.get("message")},status=decoded_data.get('status'))
       
        print("1")
        user_det = UserDetails.objects.filter(id=user_id).first()
        
        token = get_jwt_token(user_det)
        user_permissions = get_user_permision(
            user_det.id, user_det.is_superuser
        )
        proxy = None
        if user_det.role.name in ["super_admin","admin","operations","finance","sales"]:
            proxy = user_det.role.name
        theme = getorganizationtheme(user_det.organization)
        print("theme", theme)
        return Response(
            {
                "message": "Verification successful",
                "access_token": token["access_token"],
                "refresh_token": token["refresh_token"],
                "permissions": user_permissions,
                "User_Name": user_det.first_name,
                "show_proxy": proxy,
                "user_role":user_det.role.name,
                "theme":theme,
                "organization":{
                    "organization_name":user_det.organization.organization_name,
                    "phone_number":user_det.organization.support_phone,
                    "email":user_det.organization.support_email
                }
            },
            status=status.HTTP_200_OK,
        )
        
        
        
        
        
        
        
#

    



class FirstTimeUpdatePassword(APIView):
    permission_classes = []

    def post(self, request):
        user = request.user
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")
        if not new_password and not confirm_password:
            return Response(
                {"message": "new password and confirm password missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_password != confirm_password:
            return Response(
                {"message": "new password and confirm password does not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.password = make_password(new_password)
        user.is_first_time = False
        user.save()
        return Response(
            {"message": "Password Updated Successfully"}, status=status.HTTP_200_OK
        )
    

class UpdatePassword(APIView):
    # permission_classes = [IsAuthenticated]
    permission_classes = [AllowAny]
    def post(self, request):
        # user = request.user
        
        token = request.data.get('token')
        user_data  = jwt_decode(token)
        user_id = user_data.get('user_id')
        if not user_id:
            return Response({"message":user_data.get("message")},status=user_data.get('status'))
        user = UserDetails.objects.filter(id=user_id).first()
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")
        if not new_password and not confirm_password:
            return Response(
                {"message": "new password and confirm password missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_password != confirm_password:
            return Response(
                {"message": "new password and confirm password does not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.password = make_password(new_password)
        user.is_first_time = False
        user.save()
        return Response(
            {"message": "Password Updated Successfully"}, status=status.HTTP_200_OK
        )


def passwordgenerator(length=10):
    required_chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(string.punctuation),
    ]
    selection_list = string.ascii_letters + string.digits + string.punctuation
    password = required_chars + [
        secrets.choice(selection_list) for _ in range(length - 4)
    ]
    random.shuffle(password)
    pwd = "".join(password)
    return pwd
class Registration(APIView):
    permission_classes = []
    authentication_classes = []
    def post(self, request):
        random_password = passwordgenerator()
        organization_type = request.data['product_name']
        is_iata_or_arc = request.data.get('is_iata_or_arc')
        iata_or_arc_code = request.data.get('iata_or_arc_code'," ")
        company_name = request.data['company_name']
        owner_first_name = request.data['owner_first_name']
        owner_last_name = request.data['owner_last_name']
        tax_id = request.data.get('tax_id')
        gst_or_vat_number = request.data.get('gst_or_vat_number')
        is_gst_or_pan_verified = request.data['is_gst_or_pan_verified']
        company_address = request.data['company_address']
        phone = request.data['phone']
        email = request.data['email'].strip().lower()
        country = request.data['country_id']
        state = request.data['state']
        pin_or_zip = request.data['pin_or_zip']
        country = self.get_country(country)
        is_error = self.check_data_exists(request) # to check if data already exists in database
        if is_error:
            return Response({"error_code":1, "error":str(is_error), "message":str(is_error), "data":None}, status=status.HTTP_409_CONFLICT)
        
        # status = "active" if is_gst_or_pan_verified and (gst_or_vat_number or tax_id) else "pending" 
        # print("status",status)
        company_detail = {
            "organization_name":company_name,
            "organization_type": self.get_organization_type(organization_type.lower()),
            "is_iata_or_arc":is_iata_or_arc,
            "iata_or_arc_code":iata_or_arc_code,
            "address":company_address,
            "state":state,
            "organization_country":country.id,
            'organization_currency':country.currency_symbol,
            "organization_tax_number":tax_id,
            "organization_zipcode":pin_or_zip,
            "organization_gst_number":gst_or_vat_number,
            "status": "active" if is_gst_or_pan_verified else "pending"

        }

        personal_details = {
            "first_name":owner_first_name,
            "last_name":owner_last_name,
            "email":email,
            "phone_number":phone
        }
        
         
        email = personal_details["email"]
        agency_name = company_detail["organization_name"]
        organization_type = company_detail['organization_type']
        if not organization_type:
            return Response(
                {"message": "organization_type is missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user_role = set_role_for_user(organization_type)
        if not user_role:
            return Response({"message": "No user role found"})


        organization_type_obj = LookupOrganizationTypes.objects.get(
            name__icontains=user_role.lookup_organization_type.name
        )
        company_detail["organization_type"] = organization_type_obj.id
        whitelabel_obj = WhiteLabel.objects.filter(is_default=True).first()
        company_detail['whitelabel'] = whitelabel_obj.id if whitelabel_obj else None

        # get easylink name COK from lookupintegration
        country_name = country.lookup.country_name
        if country_name == 'India':
            easy_link_billing = Integration.objects.filter(Q(lookup_integration__name__icontains='easy-link backoffice suit') & Q(name__icontains='COK')).first()
            first_data = Integration.objects.filter(Q(lookup_integration__name__icontains='easy-link backoffice suit')).first()
            company_detail["easy_link_billing_account"] = easy_link_billing.id if easy_link_billing else first_data.id

        else:
            easy_link_billing = Integration.objects.filter(Q(lookup_integration__name__icontains='easy-link backoffice suit') & Q(country__lookup__country_name__icontains=country_name)).first()
            company_detail["easy_link_billing_account"] = easy_link_billing.id if easy_link_billing else None
        url = easy_link_billing.data[0]['url']
        branch_code =  easy_link_billing.data[0]['branch_code'] 
        portal_reference_code = easy_link_billing.data[0]['portal_reference_code'] 
        # ----------------------end---------------------------------------------------

        #-------------------------start company id generation----------------------------------
        company_id = self.create_company_id(agency_name)
        company_detail['easy_link_billing_code'] = company_id
        #-------------------------end company id generation----------------------------------
        try:
            country_name = company_detail['organization_country']
        except KeyError:
            raise KeyError("The key 'organization_country' was not found in companydetails")
        company_serializer = CompanySerializer(data = company_detail)
        if not company_serializer.is_valid():
            return Response(
                company_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
        company = company_serializer.save() 
        # -----------START - registeration for accouting software - START---------------------------------------# 
        # geting branch code
        branch_code_generated =  self.get_branch_code(state)
        created_organization = Organization.objects.get(id=company.id)

        #create a outapi instance 
        OutApiDetail.objects.create(organization=company, status="Pending")
        generated_password=make_password(random_password)
        personal_details.update(
            {
                "organization": company.id,
                "role": user_role.id,
                "password": generated_password,
                "username": email,
                "first_name": agency_name,
                "base_country":country.id
            }
        )
        register_serializer = RegisterSerializer(data=personal_details)
        if not register_serializer.is_valid():
            company.delete()
            return Response(
                register_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
        user_obj = register_serializer.save()
        ticket_id = user_ticket_creation(user_obj, status_key="Register")
        organization_id = company.id
        self.create_organization_theme(organization_id)
        # --------------------------------START ---------------------------------------------------
        # not create user group if role in ['superadmin', 'agency_owner', 'distributor_owner']
        if user_obj.role.name.lower() not in ['super_admin', 'agency_owner', 'distributor_owner', 'out_api_owner']:
            permission_created = self.create_permission(user_obj)
        # --------------------------------end ---------------------------------------------------

        data_dict = {
                    "user_email":email, 
                    "country_name":user_obj.base_country.lookup.country_name, 
                    "password":random_password,
                    "users_first_name": user_obj.first_name,
                    "users_last_name": user_obj.last_name,
                    "organization_name":company.organization_name 
                    }
                
        self.invoke_registrations(is_gst_or_pan_verified,request.data['product_name'],email,data_dict)

        if is_gst_or_pan_verified:
            try:
                self.create_is_init_supplier(company)
            except Exception as e:
                return Response({"error":str(e)})
            # creating an account in the  accounting software    
            easylink_account_request = self.register_accounting_software(
                        url = url,
                        sbr_code = branch_code,
                        portal_code = portal_reference_code,
                        account_code = "NEWID",
                        ref_ac_code = company_id,
                        acc_type="CC",
                        ac_name=company.organization_name,
                        contact_person = owner_first_name + owner_last_name,
                        address_1 = company_address,
                        address_2 = "",
                        address_3 = "",
                        city = "",
                        pin_code = pin_or_zip,
                        state = state,
                        country = country.lookup.country_name,
                        phone_number1 = phone,
                        phone_number2 = "",
                        phone_number3 = "",
                        fax = "",
                        mobile1 = phone,
                        mobile2 = "",
                        email1 = email,
                        email2 = "",
                        credit_limit = "1",
                        opening_balance = "0",
                        openiong_balance_type = "C",
                        family= "999",
                        category = "TRAVEL AND TOURS" ,
                        sales_man = "",
                        collection_list = "TEST",
                        pan = "",
                        gst_no = gst_or_vat_number if gst_or_vat_number else "",
            )
            if easylink_account_request.status_code == 200:
                data = easylink_account_request.data
                account_code = data['account_code']
                account_name = data['account_name']
                created_organization.easy_link_account_code = account_code
                created_organization.easy_link_account_name = account_name
                created_organization.save()
                CreditLog.objects.create(user=None, ammount=1, organization_id=created_organization.id,credit_type="credit_limit",log_message="Auto Approved by system")
            else:
                created_organization.status = 'pending'
                created_organization.save()
                return Response(
                        {"error_code": 1, "error": "Failed to create Easylink Customer", "message": "Failed to create Easylink Customer", "data": None},
                        status=status.HTTP_409_CONFLICT,
                        )

        # ----------- END - registeration for accouting software - END---------------------------------------# 

        return Response({"message":"Register Successfully","generated_password":random_password}, status=status.HTTP_201_CREATED)
    
    def invoke_registrations(self,is_gst_or_pan_verified,org_type,email,data_dict):

            if is_gst_or_pan_verified:
                if org_type in "distributor":
                    thread = threading.Thread(target=invoke, kwargs={
                                "event":"Distributor_Registration",
                                "number_list":[], 
                                "email_list":[email],
                                "data" :data_dict
                                })
                    thread.start()

                elif org_type in "agency":
                    thread = threading.Thread(target=invoke, kwargs={
                                "event":"Agent_Registration",
                                "number_list":[], 
                                "email_list":[email],
                                "data" :data_dict
                                })
                    thread.start()
                elif org_type in "out_api":
                    thread = threading.Thread(target=invoke, kwargs={
                                "event":"API_Registration",
                                "number_list":[], 
                                "email_list":[email],
                                "data" :data_dict
                                })
                    thread.start()

                else:
                    thread = threading.Thread(target=invoke, kwargs={
                                "event":"NEW_REGISTRATION",
                                "number_list":[], 
                                "email_list":[email],
                                "data" :data_dict
                                })
                    thread.start()

            else:
                thread = threading.Thread(target=invoke, kwargs={
                                "event":"UNCONFIRMED_REGISTRATION",
                                "number_list":[], 
                                "email_list":[email],
                                "data" :data_dict
                                })
                thread.start()

    
    def get_branch_code(self, state):
        state_branch_map = {
            "Jammu & Kashmir": "Punjab", "Himachal Pradesh": "Punjab", "Punjab": "Punjab", "Chandigarh": "Punjab",
            "Uttarakhand": "Delhi", "Haryana": "Delhi", "Delhi": "Delhi", "Rajasthan": "Delhi", "Uttar Pradesh": "Delhi",
            "Bihar": "West Bengal", "Sikkim": "West Bengal", "Arunachal Pradesh": "West Bengal", "Nagaland": "West Bengal", 
            "Manipur": "West Bengal", "Mizoram": "West Bengal", "Tripura": "West Bengal", "Meghalaya": "West Bengal", 
            "Assam": "West Bengal", "West Bengal": "West Bengal", "Jharkhand": "West Bengal", "Orissa": "West Bengal", 
            "Chhattisgarh": "West Bengal",
            "Madhya Pradesh": "Maharashtra", "Gujarat": "Maharashtra", "Daman & Diu": "Maharashtra", 
            "Dadra & Nagar Haveli": "Maharashtra", "Maharashtra": "Maharashtra", "Andhra Pradesh": "Maharashtra", 
            "Karnataka": "Maharashtra", "Goa": "Maharashtra",
            "Lakshadweep": "cochin", "Kerala": "cochin", "Tamil Nadu": "cochin", "Puducherry": "cochin", 
            "Andaman & Nicobar Islands": "cochin", "Telengana": "cochin"
        }

        return state_branch_map.get(state.title(), "cochin")
        
        
        
        
    

    def check_data_exists(self,request):
        company_name = request.data['company_name']
        tax_id = request.data.get('tax_id')
        gst_or_vat_number = request.data.get('gst_or_vat_number')
        
        obj = Organization.objects.all()
        print("obj",obj)
        
        is_company_name_exists = obj.filter(organization_name=company_name)
        print("is_company_name_exists",is_company_name_exists)
        if is_company_name_exists:
            return "company name already exists"
        
        if tax_id:
            is_tax_id_exists = obj.filter(iata_or_arc_code=tax_id)
            if is_tax_id_exists:
                return "tax id already exists"
        
        # is_gst_or_vat_numberobj_exists = obj.exclude(organization_gst_number__isnull=True,organization_tax_number__isnull=True).filter(organization_gst_number=gst_or_vat_number)
        is_gst_or_vat_numberobj_exists = False
        if gst_or_vat_number:
            is_gst_or_vat_numberobj_exists = obj.exclude(
                organization_gst_number__isnull=True,
                organization_tax_number__isnull=True
            ).filter(
                organization_gst_number=gst_or_vat_number
            ).exists()
        print("22")
        if is_gst_or_vat_numberobj_exists:
            return "GST or VAT number already exists"
        
        return None
        



    def register_accounting_software(self, url,
                    sbr_code,
                    portal_code,
                    account_code,
                    ref_ac_code,
                    acc_type,
                    ac_name,
                    contact_person,
                    address_1,
                    address_2,
                    address_3,
                    city,
                    pin_code,
                    state,
                    country,
                    phone_number1,
                    phone_number2,
                    phone_number3,
                    fax,
                    mobile1,
                    mobile2,
                    email1,
                    email2,
                    credit_limit,
                    opening_balance,
                    openiong_balance_type,
                    family,category,
                    sales_man,
                    collection_list,pan,
                    gst_no,
                    ):
    

                

                
            credit_limit = int(credit_limit)
            if not isinstance(credit_limit, int):
                raise Exception("Credit limit must be an integer")
            if credit_limit < 1:
                raise Exception("Credit limit cannot be less than 1")

            url = f"{url}/processEasyMasterImp/?sBrCode={sbr_code[:-3]}&PortalRefCode={portal_code}"
            header = {"Content-Type":"text/plain"}
            data = f"""
            <Accountdata>
                <Account 
                    AcCode="{account_code}" 
                    RefAcCode="{ref_ac_code}"
                    AcType="{acc_type}"
                    AcName="{ac_name}" 
                    Contact_Person="{contact_person}"
                    AddLine1="{address_1}"
                    AddLine2="{address_2}"
                    AddLine3="{address_3}"
                    City="{city}"
                    Pincode="{pin_code}"
                    State="{state}"
                    Country="{country}"
                    Phone1="{phone_number1}"
                    Phone2="{phone_number2}"
                    Phone3="{phone_number3}"
                    Fax="{fax}"
                    Mobile1="{mobile1}"
                    Mobile2="{mobile2}"
                    Email1="{email1}"
                    Email2="{email2}"
                    CreditLimit="{credit_limit}"
                    OPBal="{opening_balance}"
                    OPBalType="{openiong_balance_type}"
                    Family="{family}"
                    Category="{category}"
                    Salesman="{sales_man}"
                    Collection_List="{collection_list}"
                    PAN="{pan}"
                    GSTNo="{gst_no}"
                    CreditLimit_L="1" 
                    CreditLimit_F="1"
                    CreditLimit_V="1" 
                    CreditLimit_H="1"
                    CreditLimit_I="1"
                />
            </Accountdata>
            """

            response = requests.post(url=url, data=data, headers=header)
            return XMLData.create_customer_response(response)
    



    def get_accounting_software_credentials(self,country_id):
        # getting objects 
        try:
            obj = Integration.objects.get(name = "easy-link backoffice suit",country_id=country_id)
            # getting credentials 
            data = obj.data[0]
            url = data["url"]
            branch_code = data["branch_code"]
            portal_reference_code = data["portal_reference_code"]
            return url,branch_code,portal_reference_code
        except Exception as e:
            print(107)
            raise Exception(str(e))
        
    def get_country(self, id):
        try:
            obj = Country.objects.get(id = id)
        except Exception as e:
            raise Exception(f"Error: {e} ")
        
        return obj
    def get_organization_type(self, name):
        try:
            obj = LookupOrganizationTypes.objects.get(name=name)
        except Exception as e:
            raise Exception(f"Error: {e} ")
        return obj
        


    def create_permission(self, user_obj):
        if not isinstance(user_obj, UserDetails):
            raise TypeError(f" {user_obj} is not an instance for UserDetials Model")
        organization_type = user_obj.organization.organization_type.name
        role = (
            LookupRoles.objects.filter(name__icontains=organization_type, level=1)
            .order_by("-created_at")
            .first()
        )
        # getting all the fieldss of the lookupmodels
        field_names = self.get_model_fields(LookupPermission)

        # geting the default permision set on lookupmodal
        default_permission = role.lookup_permission

        # showing if it's true or false
        field_values = {
            field: getattr(default_permission, field) for field in field_names
        }

        custom_permission = self.create_custom_permission(field_values)
        custom_group = self.create_custom_group(custom_permission, user_obj)
        return True

    def get_model_fields(self, model):
        fields = model._meta.get_fields()
        remove_fields = [
            "id",
            "is_deleted",
            "deleted_at",
            "created_at",
            "modified_at",
            "deleted_at",
        ]
        field_names = [
            field.name
            for field in fields
            if not field.many_to_one and not field.one_to_many
        ]

        return [field for field in field_names if field not in remove_fields]

    def create_custom_permission(self, field_values):
        custom_permision = Permission.objects.create(**field_values)
        return custom_permision
    
    def create_custom_group(self, custom_perission,user_obj):
        user_group = UserGroup.objects.create(name="custom Group",organization=user_obj.organization,permission=custom_perission)
        user_obj.user_group = user_group
        user_obj.save()

    def create_organization_theme(self, organization_id):
        try:
            lookup_template_obj = LookupTemplate.objects.filter(is_default=True).first()
            if not lookup_template_obj:
                return Response(
                    "Default LookupTemplate not found.",
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            lookup_theme_obj = LookupTheme.objects.filter(
                template=lookup_template_obj
            ).first()
            if not lookup_theme_obj:
                return Response(
                    "LookupTheme not found for the default LookupTemplate.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            field_names = [
                field.name
                for field in OrganizationTheme._meta.get_fields()
                if field.name not in ["id", "organization_id", "template_id"]
            ]

            field_values = {
                field: getattr(lookup_theme_obj, field, None) for field in field_names
            }

            organization = get_object_or_404(Organization, id=organization_id)

            organization_theme, created = OrganizationTheme.objects.update_or_create(
                organization_id=organization,
                template_id=lookup_template_obj,
                defaults=field_values,
                )
        except Exception as e:
            print(str(e))

    def create_company_id(self,org_name):
        random_letters = self.generate_random_number()
        while random_letters == 'AG':
            random_letters = self.generate_random_number()            
        existing_easy_link_billing_codes =Organization.objects.filter(easy_link_billing_code__startswith=random_letters).values_list('easy_link_billing_code', flat=True)
        existing_easy_link_billing_numbers = set(code.split('-')[1] for code in existing_easy_link_billing_codes if '-' in code)
        while True:
            formatted_number = random.randint(143256, 985674)
            if formatted_number not in existing_easy_link_billing_numbers:
                new_code = f"{random_letters}-{formatted_number}"
                return new_code
            
    def generate_random_number(self):
        random_letters = ''.join(random.choices(string.ascii_uppercase, k=2))
        return random_letters
            
    def after_easylink_registered(self,easylink_account_request,company):
        created_organization = Organization.objects.get(id=company.id)
        # handling the edge cases 
        if str(easylink_account_request.api_status_code) != str(200):
            created_organization.delete()
            return Response({"error_code":1, "error":f"couldn't register error_code: ESL01 eserror:{easylink_account_request.error}","message":f"unknown error", "data":None}, status=status.HTTP_409_CONFLICT)
        else:
            if str(easylink_account_request.status_code) == str(400):
                #1 : when the account name already exists .
                if easylink_account_request.error == "A/C Name Already Exists.":
                    created_organization.delete()
                    
                    return Response({"error_code":1, "error":f"couldn't register error_code: ESL02 eserror:{easylink_account_request.error}","message":f"Company Name already exists.", "data":None}, status=status.HTTP_409_CONFLICT)
                #2 : when reference account already exists.
                elif easylink_account_request.error == "Ref A/c Code Already Exists!":
                    created_organization.delete()
                    return Response({"error_code":1, "error":f"couldn't register error_code: ESL03 eserror:{easylink_account_request.error}","message":f"account code already exists.", "data":None}, status=status.HTTP_409_CONFLICT)
                #3 for unknown error
                else:
                    created_organization.delete()
                    return Response({"error_code":1, "error":f"couldn't register error_code: ESL04 eserror:{easylink_account_request.error}","message":f"unknown error.", "data":None}, status=status.HTTP_409_CONFLICT)
            else:
                data = easylink_account_request.data
                account_code = data['account_code']
                account_name = data['account_name']
                created_organization.easy_link_account_code = account_code
                created_organization.easy_link_account_name = account_name
                created_organization.save()
                        
    def create_is_init_supplier(self, organization):
        supplier_objs = SupplierIntegration.objects.filter(is_init=True)
        if supplier_objs.exists():
            try:
                for supplier_obj in supplier_objs:
                    OrganizationSupplierIntegeration.objects.create(organization= organization, supplier_integeration=supplier_obj)
            except Exception as e:
                return str(e)
        else:
            return 'No supplier with init status True'

# class Registration(APIView):
#     permission_classes = []

#     def post(self, request):
#         random_password = passwordgenerator()
#         organization_type = request.data['organization_type']
#         isiata_or_arc = request.data['isiata_or_arc']
#         iata_or_arc_code = request.data['isiata_or_arc']
#         company_name = request.data['company_name']
#         owner_first_name = request.data['company_name']



#         companydetails = request.data.get("company_details")
#         personal_details = request.data.get("personal_details")
#         email = personal_details["email"]
#         agency_name = personal_details["agency_name"]
#         organization_name = organization_type

#         if not organization_name:
#             return Response(
#                 {"message": "organization_type is missing"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#         user_role = set_role_for_user(organization_name)

#         if not user_role:
#             return Response({"message": "No user role found"})
#         if not companydetails and not personal_details and not user_role:
#             return Response(
#                 {"message": "Invalid Data"}, status=status.HTTP_400_BAD_REQUEST
#             )

#         organization_type_obj = LookupOrganizationTypes.objects.get(
#             name__icontains=user_role.lookup_organization_type.name
#         )
#         companydetails["organization_type"] = organization_type_obj.id
#         whitelabel_obj = WhiteLabel.objects.first()
#         companydetails['whitelabel'] = whitelabel_obj.id
        
#         # modified by karthik  needed country name for invoke function do not remove it 
#         try:
#             country_name = companydetails['organization_country']
#         except KeyError:
#             raise KeyError("The key 'organization_country' was not found in companydetails")
#         company_serializer = CompanySerializer(data = companydetails)
        
#         #-------end modified by karthik------------

#         if not company_serializer.is_valid():
#             return Response(
#                 company_serializer.errors, status=status.HTTP_400_BAD_REQUEST
#             )
#         company = company_serializer.save()
#         personal_details.update(
#             {
#                 "organization": company.id,
#                 "role": user_role.id,
#                 "password": make_password(random_password),
#                 "username": email,
#                 "first_name": agency_name,
#             }
#         )
#         register_serializer = RegisterSerializer(data=personal_details)
#         if not register_serializer.is_valid():
#             return Response(
#                 register_serializer.errors, status=status.HTTP_400_BAD_REQUEST
#             )
#         user_obj = register_serializer.save()

#         ticket_id = user_ticket_creation(user_obj, status_key="Register")

#         organization_id = company.id
#         self.create_organization_theme(organization_id)

#         permission_created = self.create_permission(user_obj)
#         if not permission_created:
#             return Response({"message":"Permission not created error creating contact admin"}, status=status.HTTP_400_BAD_REQUEST)
        
#         invoke(event='GENERATE_FIRST_TIME_LOGIN_PASSWORD',number_list = [] if not user_obj.phone_code else [f"{user_obj.phone_code}{user_obj.phone_number}"],email_list=[user_obj.email], data = {"one_time_password":random_password, "country_name":country_name,"customer_email":user_obj.email})
#         return Response({"message":"Register Successfully"}, status=status.HTTP_201_CREATED)

#     def create_permission(self, user_obj):
#         if not isinstance(user_obj, UserDetails):
#             raise TypeError(f" {user_obj} is not an instance for UserDetials Model")
#         organization_type = user_obj.organization.organization_type.name
#         role = (
#             LookupRoles.objects.filter(name__icontains=organization_type, level=1)
#             .order_by("-created_at")
#             .first()
#         )

#         # getting all the fieldss of the lookupmodels
#         field_names = self.get_model_fields(LookupPermission)

#         # geting the default permision set on lookupmodal
#         default_permission = role.lookup_permission

#         # showing if it's true or false
#         field_values = {
#             field: getattr(default_permission, field) for field in field_names
#         }

#         custom_permission = self.create_custom_permission(field_values)
#         custom_group = self.create_custom_group(custom_permission, user_obj)
#         return True

#     def get_model_fields(self, model):
#         fields = model._meta.get_fields()
#         remove_fields = [
#             "id",
#             "is_deleted",
#             "deleted_at",
#             "created_at",
#             "modified_at",
#             "deleted_at",
#         ]
#         field_names = [
#             field.name
#             for field in fields
#             if not field.many_to_one and not field.one_to_many
#         ]

#         return [field for field in field_names if field not in remove_fields]

#     def create_custom_permission(self, field_values):
#         custom_permision = Permission.objects.create(**field_values)
#         return custom_permision
    
#     def create_custom_group(self, custom_perission,user_obj):
#         user_group = UserGroup.objects.create(name="custom Group",organization=user_obj.organization,permission=custom_perission)
#         user_obj.user_group = user_group
#         user_obj.save()

#     def create_organization_theme(self, organization_id):
#         try:
#             lookup_template_obj = LookupTemplate.objects.filter(is_default=True).first()
#             if not lookup_template_obj:
#                 return Response(
#                     "Default LookupTemplate not found.",
#                     status=status.HTTP_404_NOT_FOUND,
#                 )

#             lookup_theme_obj = LookupTheme.objects.filter(
#                 template=lookup_template_obj
#             ).first()
#             if not lookup_theme_obj:
#                 return Response(
#                     "LookupTheme not found for the default LookupTemplate.",
#                     status=status.HTTP_404_NOT_FOUND,
#                 )

#             field_names = [
#                 field.name
#                 for field in OrganizationTheme._meta.get_fields()
#                 if field.name not in ["id", "organization_id", "template_id"]
#             ]

#             field_values = {
#                 field: getattr(lookup_theme_obj, field, None) for field in field_names
#             }

#             organization = get_object_or_404(Organization, id=organization_id)

#             organization_theme, created = OrganizationTheme.objects.update_or_create(
#                 organization_id=organization,
#                 template_id=lookup_template_obj,
#                 defaults=field_values,
#             )
#         except Exception as e:

class UserDetailsView(RetrieveAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes=[]
    queryset = UserDetails.objects.all()
    serializer_class = UserDetailSerializer
    lookup_field = 'id'

def user_ticket_creation(user_obj, status_key):
    try:
        ticket_type = "Open"
        existing_status_keys = dict(Tickets.TICKET_STATUS_CHOICES)

        if status_key not in existing_status_keys:
            return Response("Invalid status provided", status=400)
        status_value = existing_status_keys[status_key]

        ticket = Tickets.objects.create(
            ticket_type=ticket_type, status=status_value, user=user_obj
        )
        return ticket.id
    except Exception as e:
        return Response("Error occure while creating the ticket : {e}")


def set_role_for_user(role_type, level=1):
    matching_roles = LookupRoles.objects.get(name__icontains=role_type, level=level)
    return matching_roles


# def create_user_group(user_role):
#     lookup_permissions = user_role.lookup_permission
#     return lookup_permissions

# class Test(APIView):
#     authentication_classes = []
#     permission_classes = []
#     def get(self,request):
#         permissions = request.user.get_all_permissions()
#         for permission in permissions:

#         content_type = ContentType.objects.get_for_model(TestModel)
#         return Response({'s':'s'})


class CountryDetailGet(APIView):
    permission_classes = []
    authentication_classes = []
    def get(self, request):
        country_details = Country.objects.filter(lookup__is_active =True)
        serializer = CountrySerializer(country_details, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)



class GetUser(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = request.data["username"]

        user = UserDetails.objects.filter(username=username)
        if user.exists():
            token = get_jwt_token(user.first())
            return Response(
                {
                    "message": "OTP verification successful",
                    "access_token": token["access_token"],
                    "refresh_token": token["refresh_token"],
                },
                status=status.HTTP_200_OK,
            )
        return Response({"s": "s"})


class UserExistCheck(APIView):
    authentication_classes = []
    permission_classes = []
    """
    A class view that  provides if the user already exists in databse
    or not.
    """
    def get(self, request:HttpRequest)-> Response:
        """
        Handle GET requests to retrieve if user exists in database or not.
        This method  check if the user already  exists with email or phone numnber 
        Args:
            request (Request): The HTTP request object.

        Returns:
            Response: A JSON response containing the user exists or not.
        """
        
        email = request.GET.get("email")
        if email :
            email = email.strip().lower()
        phone_number = request.GET.get("phone_number")
        user_dict = self.user_exist(email, phone_number)
        if user_dict["user"]:
            medium = "email" if user_dict["email"] else "phone number"
            return Response(
                {
                    "message": f"the user with this {medium}:{user_dict['user'].email if user_dict['email'] else user_dict['user'].phone_number} already exists under organization {user_dict['user'].organization}"
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response({"message": "new User Detected"}, status=status.HTTP_200_OK)
    
    

    def user_exist(self, email:str=None, phone_number:int=None) -> dict:
        """
        this method checks if the  user exists. if the user exists it return 
        a dict containing details and platform on which it exists.
        Args:
            email: a string .
            phone_number: numbers.

        Returns:
            A dict containing user object and the medium if they exists
        """
        email = UserDetails.objects.filter(email=email)
        phone_number = UserDetails.objects.filter(phone_number=phone_number).exclude(
            Q(phone_number__isnull=True) | Q(phone_number="")
        )
        details = {"email": email.exists(), "phone_number": phone_number.exists()}
        if email.exists():
            user = email.first()
        elif phone_number.exists():
            user = phone_number.first()
        else:
            user = False
        details.update({"user": user})
        return details
    
    
from accounting.shared.models import DistributorAgentFareAdjustment
from accounting.shared.views import OrganizationCreditBalanceView



# This Python class is used to create, list, deactivate, and delete team members with authentication
# and validation checks.

class TeamCreate(OrganizationCreditBalanceView):
    permission_classes = [HasAPIAccess]
    """
    this class is used to create and list team members. this class requires authentication
    """
    authentication_classes = [JWTAuthentication]

    def get(self,request:HttpRequest) -> Response:
        """
        this method retrives all the team members of the  current
        loged in user  and return all them as  response.
        
        Args:
            request: a HTTP request object.
        Returns:
            HTTP response.
        """
        search=request.query_params.get("search",None)
        page_size=request.query_params.get("page_size",15)
        filter =  Q(organization=request.user.organization) & Q(is_deleted=False)
        if search:
            filter &=(Q(first_name__icontains=search)|Q(last_name__icontains=search)|Q(email__icontains=search)|Q(phone_number__icontains=search))
        teams = UserDetails.objects.filter(filter).exclude(id=request.user.id)
        paginator = CustomPageNumberPagination(page_size=page_size)
        paginated_queryset = paginator.paginate_queryset(teams, request)
        serializer = UserList(paginated_queryset, many=True)
        data = {
            "data": serializer.data,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next_page": paginator.get_next_link(),
            "prev_page": paginator.get_previous_link(),
            "total_data":teams.count(),
            "page_size":page_size
        }

        return Response({"data": data})



   
    # ------------- start post---------------------------------------
    def post(self, request) -> Response:
        
        """
        this method creates  team members 
        
        Args:
            request: A HTTP request object.
        Returns:
            A dict containing user object and the medium if they exists.
        """
        required_fields = [
            "email",
            "phone_number",
            "country",
            "name",
            "role_id",
            "group_id",
        ]
        missing_fields = [
            field for field in required_fields if field not in request.data
        ]

        if missing_fields:
            return Response(
                {"message": f"Missing fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not self.validate_phonenumber(request.data["phone_number"]):
            return Response(
                {
                    "message": f"Phone Number: {request.data['phone_number']} is not valid."
                },
                status=status.HTTP_409_CONFLICT,
            )
        email = request.data["email"].strip().lower()
        phone_number = request.data["phone_number"]
        user_dict = self.user_exist(email, phone_number)

        # checking if phone number is valid for country
        country_obj = Country.objects.get(id=request.data["country"])
        is_phone_number_valid = self.validate_phone_number(
            country_obj.lookup.country_code, phone_number
        )
        if not is_phone_number_valid:
            return Response(
                {
                    "message": f"please enter the correct phone number for the country {country_obj.lookup.country_name}"
                },
                status=status.HTTP_409_CONFLICT,
            )

        if user_dict["user"]:
            medium = "email" if user_dict["email"] else "phone number"
            return Response(
                {
                    "message": f"the user with this {medium}:{user_dict['user'].email if user_dict['email'] else user_dict['user'].phone_number} already exists under organization {user_dict['user'].organization}"
                },
                status=status.HTTP_409_CONFLICT,
            )
        random_password = passwordgenerator()
        user = UserDetails.objects.create(
            phone_number=phone_number,
            email=email,
            first_name=request.data["name"],
            user_group_id=request.data["group_id"],
            role_id=request.data["role_id"],
            organization=request.user.organization,
            base_country=country_obj,
            # phone_code=country_obj.lookup.calling_code,
            phone_code=request.data.get("calling_code","+91"),
            password = make_password(random_password)
        )
        
        if user.role.name == "distributor_agent":
            
            requested_wallet_amount = request.data.get("wallet_amount",None)
            if not requested_wallet_amount:
                user.hard_delete()
                return Response({"message":"wallet ammount not passed distributor agent should have  wallet ammount"}, status=status.HTTP_409_CONFLICT)
            if not self.is_wallet_ammount_applicable(
                                                    requested_wallet_amount=requested_wallet_amount,
                                                    organization_obj = request.user.organization,
                                                    easy_link_billing_code=request.user.organization.easy_link_billing_code
                                                    ): # checks if the  amount less than organization wallet amount 
                return Response({"message":"requested amount is  higher than your wallet balance"},status=status.HTTP_409_CONFLICT)
            DistributorAgentFareAdjustment.objects.create(user = user,available_balance=requested_wallet_amount)
        # invoke(event='TEAM_CREATED_NOTIFICATION',email_list=[email], data = {"user_email":user.email, "country_name":user.base_country.lookup.country_name, "password":random_password,"users_first_name": user.first_name, "users_last_name": user.last_name })

        #---------------START-----------------------------------------------------------------------------------------------------
        data_list = {
                    "agent_name":user.first_name, 
                     "username":email, 
                     "temporary_password":random_password,
                     "login_url": "lOGIN url",
                    "distributor_name": request.user.organization.organization_name,
                    "country_name":request.user.base_country.lookup.country_name
                       }

        email_data = [user.email,request.user.email]
        if request.user.organization.organization_type.name=='master':
            data_list = {
                        "organization_name":request.user.organization.organization_name,
                        'users_first_name':user.first_name,
                        'users_last_name':user.last_name,
                        'password':random_password,
                        "country_name":request.user.base_country.lookup.country_name
                        }
            thread = threading.Thread(target=invoke, kwargs={
                        "event":"BTA_Team_Creation", 
                        "email_list":email_data,
                        "data" :data_list
                        })
            thread.start()
            
            # invoke(event='BTA_Team_Creation',email_list=email_data, data = data_list)
        else:
            thread = threading.Thread(target=invoke, kwargs={
                        "event":"Registration_email_from_Distributor_to_Agent", 
                        "email_list":email_data,
                        "data" :data_list
                        })
            thread.start()
            # invoke(event='Registration_email_from_Distributor_to_Agent',email_list=email_data, data = data_list)



        #---------------END-----------------------------------------------------------------------------------------------------

        
        return Response(
            {"message": f"user {request.data['name']} created succefully ! "},
            status=status.HTTP_200_OK,
        )
        
    def is_wallet_ammount_applicable(self,requested_wallet_amount,organization_obj,easy_link_billing_code):
        """ return true if organization wallet amount is less than request amount  """
        # url,  branch_code,  portal_reference_code = self.get_accounting_software_credentials(country_id) # getting the easy link details for checkinh the organization's wallet
        url,  branch_code,  portal_reference_code =get_accounting_software_credentials(organization_obj)
        response = get_credit_limit(base_url=url, portal_ref_code=portal_reference_code,billing_code=easy_link_billing_code)
        credit_data = response.data
        try:
            credit_data['F']
        except KeyError as e:
            raise Exception ("esy link account error")
        return float(requested_wallet_amount) < float(credit_data['F']), credit_data['F']

# 
        
        
        
    def validate_phonenumber(self, phone_number):
        return str(phone_number).isnumeric()

    def user_exist(self, email=None, phone_number=None):
        email = UserDetails.objects.filter(email=email)
        phone_number = UserDetails.objects.filter(phone_number=phone_number).exclude(
            Q(phone_number__isnull=True) | Q(phone_number="")
     # The above Python code is creating a dictionary called `details` that contains information about
     # the existence of an email and a phone number. It then checks if an email exists, and if so,
     # assigns the first email to the variable `user`. If an email does not exist but a phone number
     # does, it assigns the first phone number to `user`. If neither email nor phone number exists, it
     # sets `user` to False. Finally, it updates the `details` dictionary with the `user` information
     # and returns the updated dictionary.
        )
        details = {"email": email.exists(), "phone_number": phone_number.exists()}
        if email.exists():
            user = email.first()
        elif phone_number.exists():
            user = phone_number.first()
        else:
            user = False
        details.update({"user": user})
        return details

    def validate_phone_number(self, country_code, phone_number):
        try:

            parsed_number = phonenumbers.parse(phone_number, country_code)

            if not phonenumbers.is_possible_number(parsed_number):
                return False

            if not phonenumbers.is_valid_number(parsed_number):
                return False

            if self.is_repeated_digits(phone_number):
                return False

            return True
        except NumberParseException:
            return False

    def is_repeated_digits(self, phone_number):
        """Check if the phone number consists of repeated digits."""
        if len(set(phone_number)) == 1:
            return True
        return False

    # ------------- end post---------------------------------------

    def patch(self, request):
        id = request.data.get("id")
        if not id:
            return Response(
                {"message": "id is required in payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user = UserDetails.objects.get(id=id)
        except UserDetails.DoesNotExist:
            return Response(
                {"message": "user doesn't exist"}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response({"message": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)

        message = None
        if user.is_active:
            user.is_active = False
            message = "deactivated"
        else:
            user.is_active = True
            message = "activated"
        user.save()
        return Response(
            {"message": f"user successfully {message}.", "flag": user.is_active},
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        id = request.GET.get("id")
        if not id:
            return Response(
                {"message": "id is required in payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = UserDetails.objects.get(id=id)
        user.delete()
        return Response(
            {"message": f"user successfully deleted"}, status=status.HTTP_200_OK
        )


class ToggleUserStatusView(APIView):
    permission_classes = [HasAPIAccess]
    def post(self, request):
        id = request.data.get("id")
        if not id:
            return Response(
                {"message": "id is required in payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            user = UserDetails.objects.get(id=id)
        except UserDetails.DoesNotExist:
            return Response(
                {"message": "User doesn't exist"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": f"An error occurred: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.is_active:
            user.is_active = False
            message = "deactivated"
        else:
            user.is_active = True
            message = "activated"
        
        user.save()
        
        return Response(
            {
                "message": f"User successfully {message}.",
                "flag": user.is_active,
            },
            status=status.HTTP_200_OK,
        )
class RoleSuggest(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = []
    def get(self,request):
        user_role = request.user.role

        organization_type = user_role.lookup_organization_type.name

        level = user_role.level

        # we are getting the  roles which is below the role level of the current user's role
        if int(level) == 0:
            organization_roles = LookupRoles.objects.filter(
                lookup_organization_type__name=organization_type
            ).exclude(name = 'super_admin')
        else:
            organization_roles = LookupRoles.objects.filter(
                lookup_organization_type__name=organization_type
            ).exclude(level__lte=level)

        if organization_roles:
            data = [
                {"id": role_name.id, "role_name": role_name.name.replace("_", " ").title()}
                for role_name in organization_roles
            ]
        else:
            data = [organization_type, "error in rolesuggest"]
        return Response({"data": data})


class ShowPermissions(APIView):
    def get(self, request):
        try:
            group_id = request.GET.get('group_id')
            role_id = request.GET["role_id"]
        except Exception as e:
            return Response({"message": f"{e} key missing "})
        if group_id:
            user_role = UserGroup.objects.filter(role_id=role_id, id=group_id).first().rolec
        else:
            user_role = LookupRoles.objects.filter(id=role_id).first()

        # getting all the fieldss of the lookupmodels
        field_names = self.get_model_fields(LookupPermission)

        # geting the default permision set on lookupmodal
        default_permission = user_role.lookup_permission

        # showing all the fields from lookup permision weather it true or false
        field_values = {
            field: getattr(default_permission, field) for field in field_names
        }

        # filtering all the true fields because we just need to show only the permision for the roles
        true_fields_values = {
            key: values for key, values in field_values.items() if values
        }

        # structuring permision for front-end

        strucured_permision = self.structure_permision(true_fields_values)
        return Response({"data": strucured_permision}, status=status.HTTP_200_OK)

    def get_model_fields(self, model):
        fields = model._meta.get_fields()
        remove_fields = [
            "id",
            "is_deleted",
            "deleted_at",
            "created_at",
            "modified_at",
            "deleted_at",
            "name",
        ]
        field_names = [
            field.name
            for field in fields
            if not field.many_to_one and not field.one_to_many
        ]
        return [field for field in field_names if field not in remove_fields]
    
    def structure_permision(self,permision_dict):
        formated_list = [f'{key}_{str(item).lower()}' for key,item in permision_dict.items()]
        default_dict = {}
        nested_dict = default_dict
        for i in formated_list:
            
            #  we are giving a space eg "control panel"  we need space in between these word our current code doesn't satify
            # that's why we are giving this if condiditon
            # if you want to have space you need to give this key word "1space1"
            # don't forget to change in models we need to update in 2 models lookup and permisison
            
            if "1space1" in i:
                i = ' '.join(i.split('1space1'))
            
            #--------- end space condition ----------
            
            counter_split = i.split("_")
            splited = i.split("_", len(counter_split) - 2)
            counter = len(splited) - 1
            for letters in splited:
                try:
                    nested_dict = nested_dict[letters]
                except:
                    if counter == 0:
                        perm = letters.split("_")
                        bool_dict = {}
                        for i in range(0, int(len(perm) / 2)):
                            current = perm[i]
                            bool_value = eval(str(perm[i+1]).title())

                            bool_dict[current] = bool_value
                            perm = perm[2:]
                        
                        nested_dict["permissions"].update(bool_dict)
                        pass
                    else:
                        nested_dict[letters] = {}
                        if counter == 1:
                            nested_dict = nested_dict[letters]
                            nested_dict["permissions"] = {}
                        else:
                            nested_dict = nested_dict[letters]
                counter -= 1
            nested_dict = default_dict
        return default_dict


# The `CreateGroupPermission` class defines a POST method to create a group with specified permissions
# and role within an organization, restructuring permission data before storing it in the database.
class CreateGroupPermission(ShowPermissions):
    permission_classes = [HasAPIAccess]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            permission_dict = request.data["permission"]
            group_name = request.data["group_name"]
            role_id = request.data["role_id"]
        except Exception as e:

            return Response({"message": f"{e} key missing in payload"})

        # if UserGroup.objects.filter(
        #     name=group_name, organization=request.user.organization
        # ):
        #     return Response(
        #         {"message": "a group with this name already exists"},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        users_organization = request.user.organization
        permissons_restructuring = self.convert_to_key_value(permission_dict)
        permissons_restructuring["name"] = group_name
        permission_obj = Permission.objects.create(**permissons_restructuring)
        user_group = UserGroup.objects.create(
            name=group_name, organization=users_organization, permission=permission_obj,
            role_id = role_id
        )
        return Response(
            {"message": f"Group {group_name} created successfully !"},
            status=status.HTTP_200_OK,
        )

    def convert_to_key_value(self, data, parent_key=""):
        items = []
        for k, v in data.items():
            #  we are restructuin to desired strucuture in database condition 
            # eg: from front ent we will recive "control panel"
            # we are structring it from 'control panel' to 'control1space1panel' ----->   in databse
            if ' 'in k:
                k = k.replace(' ', '1space1')
            if k == "permissions":
               new_key = f"{parent_key}" if parent_key else k
            else:
                new_key = f"{parent_key}_{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.convert_to_key_value(v, new_key).items())
            else:
                items.append((new_key, eval(str(v).title())))
        return dict(items)


# The `UpdateGroupPermission` class in Python retrieves group and role information, checks for missing
# group ID, fetches user role and default permissions, and displays all fields and their values from
# the lookup permission model.
class UpdateTeamMember(ShowPermissions):
    permission_classes = [HasAPIAccess]
    def get(self,request):
        """
        The function retrieves user group information based on provided parameters and checks for missing
        group ID before fetching role permissions.
        
        :param request: The code snippet you provided is a Django view that handles a GET request. It
        retrieves the 'user_id', 'group_id', and 'role_id' from the request parameters. If 'group_id' is
        missing, it returns a 400 Bad Request response. It then tries to fetch a User
        :return: The code snippet is returning a dictionary `field_values` that contains the field names
        of the `LookupPermission` model as keys and their corresponding values from the
        `default_permission` object. The values are retrieved using `getattr(default_permission, field)`
        for each field in `field_names`.
        """
        user_id = request.GET.get('user_id',None)
        group_id = request.GET.get('group_id',None)
        role_id = request.GET.get('role_id',None)
        if not group_id:
            return Response(
                {"message": "group_id is missing in query Params"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            group_obj = UserGroup.objects.get(id=group_id)
        except Exception as e:
            return Response({"message":f"{e}"},status=status.HTTP_400_BAD_REQUEST)
        user_role = LookupRoles.objects.filter(id=role_id).first()
        # getting all the fieldss of the lookupmodels
        field_names = self.get_model_fields(LookupPermission)

        # geting the default permision set on lookupmodal
        default_permission = user_role.lookup_permission

        # showing all the fields from lookup permision weather it true or false
        field_values = {field: getattr(default_permission, field) for field in field_names}

        # filtering all the true fields because we just need to show only the permision for the roles 
        true_fields_values = {key:values for key,values in field_values.items() if values}        
        group_permission = group_obj.permission
        group_field_values = {field: getattr(group_permission, field) for field in true_fields_values}
        group_true_fields_values = {key:values for key,values in group_field_values.items() if values}
        strucured_permision = self.structure_permision(group_field_values)
        user_details = UserDetails.objects.filter(id=user_id)
        if not user_details:
            return Response({"message":"wrong user id is passed"})        
        user_details = user_details.first()
        
        details = {
            "name" : user_details.first_name,
            "phone":user_details.phone_number,
            "country_id":user_details.base_country.id,
            "country_name":user_details.base_country.lookup.country_name,
            "group_id":user_details.user_group.id,
            "group_name":user_details.user_group.name,
            "role":{"role_id":user_details.role.id,
                    "name":user_details.role.name},
            
            "email":user_details.email,
        }
        data = {
            "user_details":details,
            "permission":strucured_permision
        }
        return Response({"data":data},status=status.HTTP_200_OK)
    
    
    def post(self,request):
        try:
            user_id = request.data['user_id']
        except Exception as e:
            return Response({"message":f"{e} key missing in payload"})

        try:
            user_obj = UserDetails.objects.get(id=user_id)
        except UserDetails.DoesNotExist:
            return Response({"error":"user id not found"},status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Internal server error {e}"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        user_obj.base_country_id = request.data['country']
        user_obj.email = request.data['email']
        user_obj.user_group_id = request.data['group_id']
        user_obj.first_name = request.data['name']
        user_obj.phone_number = request.data['phone_number']
        user_obj.save()

        return Response({"message":f"Team Member Details updated successfully !"},status=status.HTTP_200_OK)
    
    def structure_permision(self,permision_dict):
        formated_list = [f'{key}_{str(item).lower()}' for key,item in permision_dict.items()]
        default_dict = {}
        nested_dict = default_dict
        for i in formated_list:
            
            #  we are giving a space eg "control panel"  we need space in between these word our current code doesn't satify
            # that's why we are giving this if condiditon
            # if you want to have space you need to give this key word "1space1"
            # don't forget to change in models we need to update in 2 models lookup and permisison
            
            if "1space1" in i:
                i = ' '.join(i.split('1space1'))
            
            #--------- end space condition ----------
            
            counter_split = i.split("_")
            splited = i.split("_", len(counter_split) - 2)
            counter = len(splited) - 1
            for letters in splited:
                try:
                    nested_dict = nested_dict[letters]
                except:
                    if counter == 0:
                        perm = letters.split("_")
                        bool_dict = {}
                        for i in range(0, int(len(perm) / 2)):
                            current = perm[i]
                            bool_value = eval(str(perm[i+1]).title())

                            bool_dict[current] = bool_value
                            perm = perm[2:]
                        
                        nested_dict["permissions"].update(bool_dict)
                        pass
                    else:
                        nested_dict[letters] = {}
                        if counter == 1:
                            nested_dict = nested_dict[letters]
                            nested_dict["permissions"] = {}
                        else:
                            nested_dict = nested_dict[letters]
                counter -= 1
            nested_dict = default_dict
        return default_dict


# This class retrieves a list of user groups based on the role ID provided in the request.
class GroupNames(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        """
        This Python function retrieves a list of user groups based on a specified role ID and returns the
        serialized data in a response.
        
        :param request: The `request` parameter in the `get` method is an object that contains information
        about the incoming HTTP request, such as the request method, headers, and query parameters. In this
        specific code snippet, the `request` object is used to extract the value of the `role_id` query
        parameter
        :return: A response containing a list of user groups filtered by the organization ID of the
        requesting user and the specified role ID. The data is serialized using ListGroupSerializer and
        returned with a status code of 200 (OK).
        """
        role_id = request.GET['role_id']
        group_list = UserGroup.objects.filter(
            organization_id=request.user.organization.id, role_id=role_id
        )
        group_serializer = ListGroupSerializer(group_list, many=True).data
        return Response({"data": group_serializer}, status=status.HTTP_200_OK)
    

class OperationsLists(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
   
        
        group_list = UserGroup.objects.filter(
            role__name="operations"
        )
        group_serializer = ListGroupSerializer(group_list, many=True).data
        return Response({"data": group_serializer}, status=status.HTTP_200_OK)
    
    
    
    # def get(self, request):
    #     group_list = UserGroup.objects.filter(
    #         organization_id=request.user.organization.id
    #     )
    #     group_serializer = ListGroupSerializer(group_list, many=True).data
    #     return Response({"data": group_serializer}, status=status.HTTP_200_OK)



class TicketView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(Self, request):
        ticket_instance = Tickets.objects.all()
        serializer = TicketSerializer(ticket_instance, many=True)
        return Response(serializer.data)

    def patch(self, request):
        ticket_id = request.data.get("id")
        if not ticket_id:
            return Response(
                {"message": "id is required in payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ticket_instance = Tickets.objects.get(id=ticket_id)

        request.data["modified_by"] = request.user.id

        serializer = TicketSerializer(ticket_instance, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Updated Successfully"}, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LookupCountryCreate(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        file_data = request.FILES.get("countries")
        decoded_file = file_data.read().decode("utf-8").splitlines()

        csv_data = csv.reader(decoded_file)

        for row in csv_data:
            name = row[0]
            code = row[1]
            LookupCountry.objects.update_or_create(country_name=name, country_code=code)
        return Response(
            {"message": "Country data created successfully"}, status=status.HTTP_200_OK
        )

    def get(self, request):
        search_key = request.query_params.get('search_key', '')

        if search_key:
            country_details = LookupCountry.objects.filter(
                country_name__icontains=search_key
            )
        else:
            country_details = LookupCountry.objects.all()
        serializer = LookupCountrySerializer(country_details, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
        # country_details = LookupCountry.objects.all()
        # serializer = LookupCountrySerializer(country_details, many=True)
        # return Response(serializer.data, status=status.HTTP_200_OK)





class LookupAirportDealManagement(APIView):
    authentication_classes = []
    permission_classes = []
    
    def get(self, request):
        search_key = request.query_params.get("search_key", None)
        if search_key:
            airports = LookupAirports.objects.filter(Q(name__icontains=search_key)|Q(code__icontains=search_key))
        else:
            airports = LookupAirports.objects.all()[:50]
        serializer = LookupAirportsSerializer(airports, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



class LookupAirportCreate(APIView):
    authentication_classes = []
    permission_classes = []
    # def post(self, request):
    #     airport_csv = request.FILES.get("airport_data")
    #     df = pd.read_csv(airport_csv)
    #     df.reset_index(drop=True,inplace=True)
    #     # file_url = file_upload(airport_csv)
    #     if len(df)>0:
            
    #         thread = threading.Thread(target=self.import_airport, args=(df,))
    #         thread.start()
    #         return Response(
    #             {"message": "Airport data created successfully"}, status=status.HTTP_200_OK
    #         )
    #     else:
    #         return Response(
    #             {"message": "Error message"}, status=status.HTTP_204_NO_CONTENT
    #         )
            


    # def import_airport(self, df):
    #     airports = LookupAirports.objects.all()
    #     serializer = LookupAirportsSerializer(airports, many=True)
    #     existing_airports_data = serializer.data
    #     existing_df = pd.DataFrame(existing_airports_data)
    #     existing_codes = existing_df['code'].unique().tolist()
    #     pending_df  = df[~df['Code'].isin(existing_codes)]
    #     pending_df.reset_index(drop=True,inplace=True)
    #     if len(pending_df)>0:
    #         for index, airport in pending_df.iterrows():
    #             name = airport.get("AirportName",'')
    #             code = airport.get("Code",'')
    #             city = airport.get("City",'')
    #             country_code = airport.get("CountryCode") if airport.get("CountryCode") else " "
    #             common = airport.get("Code",'')
    #             latitude = airport.get('latitude',None)
    #             longitude = airport.get('longitude',None)

    #             if country_code:
    #                 try:
    #                     country_id = LookupCountry.objects.get(country_code=country_code)
    #                 except:
    #                     country_id = None
    #             LookupAirports.objects.create(
    #                 name=name,
    #                 code=code,
    #                 city=city,
    #                 country=country_id,
    #                 common = common,
    #                 latitude = latitude,
    #                 longitude = longitude

    #             )

        
    def get(self, request):
        airports = LookupAirports.objects.all()[:10] 
        serializer = LookupAirportsSerializer(airports, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class Airport_Location(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        file_data = request.FILES.get("location")
        decoded_file = file_data.read().decode("utf-8").splitlines()
        decoded_file = decoded_file[1:]
        csv_data = csv.reader(decoded_file)
        thread = threading.Thread(target=self.import_location, args=(csv_data,))
        thread.start()
        return Response(
            {"message": "Airport location updated successfully"},
            status=status.HTTP_200_OK,
        )

    def import_location(self, csv_data):
        for row in csv_data:
            iata = row[2]
            latitude = row[5]
            longitude = row[6]
            airport_obj = LookupAirports.objects.filter(Q(code__icontains=iata)).first()
            if airport_obj:
                airport_obj.latitude = latitude
                airport_obj.longitude = longitude
                airport_obj.save()


class NearestAirports1(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        airport_obj = LookupAirports.objects.all()
        threshold_distance = 60
        for airport1 in airport_obj:
            for airport2 in airport_obj:
                if airport1.name != airport2.name:
                    airport_point1 = (airport1["latitude"], airport1["longitude"])
                    airport_point2 = (airport2["latitude"], airport2["longitude"])

                    distance = geodesic(airport_point1, airport_point2).kilometers
                    if distance <= threshold_distance:
                        airportobj1 = LookupAirports.objects.filter(name=airport1.name)
                        airportobj1.update(nearest=airport2.name)
                        airportobj2 = LookupAirports.objects.filter(name=airport1.name)
                        airportobj2.update(nearest=airport2.name)
                        break
                    else:
                        classification = "far"
        return Response({"message": "Successfully"}, status=status.HTTP_200_OK)


class NearestAirports(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        airport_obj = LookupAirports.objects.all()
        threshold_distance = 60
        thread = threading.Thread(
            target=self.get_nearest_airport,
            args=(
                airport_obj,
                threshold_distance,
            ),
        )
        thread.start()

        return Response({"message": "Nearest airports updated successfully"})

    def get_nearest_airport(self, airport_obj, threshold_distance):
        for airport1 in airport_obj:
            nearest_airports = set(airport1.nearest or [])
            checked_airports = nearest_airports.copy()

            for airport2 in airport_obj:
                if airport1.id != airport2.id and airport2.code not in checked_airports:
                    airport_point1 = (airport1.latitude, airport1.longitude)
                    airport_point2 = (airport2.latitude, airport2.longitude)

                    # Ensure that both airport_point1 and airport_point2 have valid latitude and longitude values

                    if all(v is not None for v in airport_point1) and all(
                        v is not None for v in airport_point2
                    ):
                        distance = geodesic(airport_point1, airport_point2).kilometers

                        if distance <= threshold_distance:
                            nearest_airports.add(airport2.code)
                            checked_airports.add(airport2.code)
                            # Also add airport1 to the nearest of airport2 to keep consistency
                            if not airport2.nearest:
                                airport2.nearest = []
                            if airport1.code not in airport2.nearest:
                                airport2.nearest.append(airport1.code)
                                airport2.save()

            if nearest_airports:
                airport1.nearest = list(nearest_airports)
                airport1.save()


class SearchAirport(APIView):
    authentication_classes = []
    permission_classes = []
    def get(self, request):
        search = request.query_params.get("search_key")
        queryset = LookupAirports.objects.all()
        if search:
            code_match = queryset.filter(code__iexact=search)
            
            if code_match.exists():
                queryset = code_match
            else:
                queryset = queryset.filter(
                    Q(code__icontains=search) | 
                    Q(name__icontains=search) | 
                    Q(city__icontains=search)
                )

        serializer = AirportSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

    # def get(self, request):
    #     search = request.query_params.get("search_key")
    #     queryset = LookupAirports.objects.all()
    #     if search:
    #         queryset = queryset.filter(Q(code__icontains=search) | Q(name__icontains=search) | Q(city__icontains=search) )

    #     serializer = AirportSerializer(queryset, many=True)
        
    #     return Response(serializer.data, status=status.HTTP_200_OK)


class VerifyGSTIN(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        username = "k-e2754771-cc1b-4516-8ba4-03d20ecbd399"
        password = "s-61f70c59-39f8-4507-a399-61357f376718"
        gst_number = request.query_params.get("gst_number")
        if not gst_number:
            return Response(
                {"message": "GST number required"},
                status=status.HTTP_409_CONFLICT,
            )

        if len(gst_number) < 15:
            return Response(
                {"message": "GST number not correct"},
                status=status.HTTP_409_CONFLICT,
            )

        auth_string = f"{username}:{password}"
        encoded_bytes = base64.b64encode(auth_string.encode("utf-8"))
        encoded_string = encoded_bytes.decode("utf-8")
        auth_header = f"Basic {encoded_string}"

        url = "https://api.atlaskyc.com/v2/prod/verify/gstin"
        headers = {"Authorization": auth_header}
        params = {"gst_number": gst_number}

        response = requests.post(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            if "error" in data:
                return Response(
                    {"message": data["error"]}, status=status.HTTP_400_BAD_REQUEST
                )
            else:
                org_name = data.get("data", {}).get(
                    "business_legal_name", "Not Available"
                )
                address_parts = [
                    data.get("data", {}).get("business_address_primary_building", ""),
                    data.get("data", {}).get("business_address_primary_floor", ""),
                    data.get("data", {}).get("business_address_primary_street1", ""),
                    data.get("data", {}).get("business_address_primary_number", ""),
                    data.get("data", {}).get("business_address_primary_location", ""),
                    data.get("data", {}).get("business_address_primary_state", ""),
                    data.get("data", {}).get("business_address_primary_pincode", ""),
                ]
                company_address = ", ".join(filter(None, address_parts))
                zipcode = data.get("data", {}).get(
                    "business_address_primary_pincode", "Not Available"
                )

                return Response(
                    {
                        "status": "success",
                        "organization_name": org_name,
                        "company_address": company_address,
                        "organization_zipcode": zipcode,
                    }
                )
        else:
            return Response(
                {
                    "message": f"Failed to retrieve data, Status Code: {response.status_code}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        

class VerifyPAN(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        username = "k-e2754771-cc1b-4516-8ba4-03d20ecbd399"
        password = "s-61f70c59-39f8-4507-a399-61357f376718"
        pan_number = request.query_params.get("pan_number")

        if not pan_number:
            return Response(
                {"message": "PAN number required"},
                status=status.HTTP_409_CONFLICT,
            )

        if len(pan_number) != 10:
            return Response(
                {"message": "PAN number is not correct"},
                status=status.HTTP_409_CONFLICT,
            )

        auth_string = f"{username}:{password}"
        encoded_bytes = base64.b64encode(auth_string.encode("utf-8"))
        encoded_string = encoded_bytes.decode("utf-8")
        auth_header = f"Basic {encoded_string}"

        url = f"https://api.atlaskyc.com/v2/prod/verify/pan"
        headers = {"Authorization": auth_header}
        params = {"pan_number": pan_number}  # Use params for GET request

        response = requests.post(url, headers=headers, params=params)
        data = response.json()
        pan_data = data.get("data", {})
        if pan_data is None:
            return Response(
                {"message": "No data found for the provided PAN number"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pan_status = pan_data.get("pan_status", "Not Available")

        if response.status_code == 200:
            if "error" in data:
                return Response(
                    {"message": data["error"]}, status=status.HTTP_400_BAD_REQUEST
                )
            elif pan_status == "VALID":
                pan_number = pan_data.get("pan_number", "Not Available")
                last_name = pan_data.get("last_name", "Not Available")
                first_name = pan_data.get("first_name", "Not Available")
                middle_name = pan_data.get("middle_name", "")

                return Response(
                    {
                        "status": "success",
                        "pan_number": pan_number,
                        "last_name": last_name,
                        "first_name": first_name,
                        "middle_name": middle_name,
                    }
                )
        else:
            return Response(
                {
                    "message": f"Failed to retrieve data, Status Code: {response.status_code}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
from django.db.models import Q

#create values from only backend
class CountryDefaultCreateView(APIView):
    def post(self, request):
        country_name = request.data.get('country_name')
        country_instance = Country.objects.get(lookup__country_name=country_name)
        country_id = country_instance.id
        request.data['country_id'] = country_instance.id
        
        flights = request.data.get('flights', {})
        popular_from_codes = [code for code in flights.get('suggestions', [{}])[0].get('popular_from', [{}])[0].get('code', [])]
        popular_to_codes = [code for code in flights.get('suggestions', [{}])[1].get('popular_to', [{}])[0].get('code', [])]

        default_from_code = flights.get('default', {}).get('from')
        default_to_code = flights.get('default', {}).get('to')

        default_from_airport = LookupAirports.objects.filter(code=default_from_code).first()
        default_to_airport = LookupAirports.objects.filter(code=default_to_code).first()

        default_from_airport_data = {}
        if default_from_airport:
            default_from_airport_data = {
                "id": str(default_from_airport.id),
                "code": default_from_airport.code,
                "name": default_from_airport.name,
                "city": default_from_airport.city,
                "index": default_from_airport.index
            }

        default_to_airport_data = {}
        if default_to_airport:
            default_to_airport_data = {
                "id": str(default_to_airport.id), 
                "code": default_to_airport.code,
                "name": default_to_airport.name,
                "city": default_to_airport.city,
                "index": default_to_airport.index
            }

        flights['default'] = {
            "from": default_from_airport_data,
            "to": default_to_airport_data
        }

        popular_from_airports = LookupAirports.objects.filter(code__in=popular_from_codes)
        popular_to_airports = LookupAirports.objects.filter(code__in=popular_to_codes)

        popular_from_data = [
            {
                "id": str(airport.id),
                "code": airport.code,
                "name": airport.name,
                "city": airport.city,
                "index": airport.index
            }
            for airport in popular_from_airports
        ]
        popular_to_data = [
            {
                "id": str(airport.id),
                "code": airport.code,
                "name": airport.name,
                "city": airport.city,
                "index": airport.index            }
            for airport in popular_to_airports
        ]

        flights['suggestions'][0]['popular_from'] = popular_from_data
        flights['suggestions'][1]['popular_to'] = popular_to_data

        request.data['flights'] = flights
        # request.data['default'] = default_from_airport_data
        country_default_instance = CountryDefault.objects.filter(country_id=country_id).first()
        if country_default_instance:
            if country_default_instance.flights:
                serializer = CountryDefaultSerializer(country_default_instance, data= request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response("Updated Already Existing Data in flights Field", status=status.HTTP_200_OK)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            country_default_instance.flights = flights
            serializer = CountryDefaultSerializer(country_default_instance, data= request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response("Updated Null flights Field", status=status.HTTP_200_OK)            
        else:
            serializer = CountryDefaultSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response("Successfully created new record with flights details", status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        country_id=request.query_params.get("country_id")
        if not country_id:
            return Response({"message":"country_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        default_values=CountryDefault.objects.filter(country_id=country_id, flights__isnull = False).order_by('-modified_at')
        serializer  = CountryDefaultSerializer(default_values, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
from django.db.models import Prefetch

class OrganizationListView(ListAPIView):
    permission_classes=[HasAPIAccess]
    authentication_classes = [JWTAuthentication]
    queryset=Organization.objects.all()
    serializer_class=OrganizationSerializer
    pagination_class=CustomPageNumberPagination
    filter_backends=[CustomSearchFilter,DateFilter]
    search_fields=[
        "organization_name",
        "organization_type__name",
        "organization_country__lookup__country_name",
        "easy_link_billing_code"
    ]
 
    

# This class represents a detail view for an Organization model with authentication and permission
# settings specified.
class OrganizationDetailView(RetrieveAPIView):
    permission_classes=[IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    queryset=Organization.objects.all()
    serializer_class=OrganizationDetailsSerializer
    lookup_field = 'id' 


# This class is an API view for updating the status of an organization with authentication and
# permission settings.
class OrganizationStatusUpdateView(UpdateAPIView):
    permission_classes=[IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    queryset = Organization.objects.all()
    serializer_class = OrganizationStatusUpdateSerializer
    allowed_methods = ("PATCH",)   
    lookup_field = 'id' 
    partial = True
    
    def patch(self, request, *args, **kwargs):
        organization = Organization.objects.get(id=kwargs['id'])
        users = organization.users_details.filter(role__level=1).first()
        status = request.data.get("status")

        if organization.status == "pending" and status=="active":
            # OrganizationFareAdjustment.objects.create(organization=organization)
            # invoke(event='UPON_APPROVAL_ORGANIZATION',email_list=[user.email for user in UserDetails.objects.filter(organization=organization,role__level=1) ], data = { })
            sales_team_mail = organization.sales_agent.email if organization.sales_agent else None
            org_mail = users.email if users else None
            email = [request.user.email]
            if org_mail:
                email.append(org_mail)
            if sales_team_mail:
                email.append(sales_team_mail)
            activation_date = datetime.fromtimestamp(organization.modified_at).strftime('%d-%m-%Y')
            data_list ={"country_name":request.user.base_country.lookup.country_name,
                        "agent_name":organization.organization_name,
                          "username":users.email if users else None, 
                          "activation_date":activation_date}
            
            thread = threading.Thread(target=invoke, kwargs={
                        "event":"Agency_Activation", 
                        "email_list":email,
                        "data" :data_list})
            thread.start()

            # invoke(event='Agency_Activation',email_list=email, data = data_list)
        return super(OrganizationStatusUpdateView,self).patch(request, *args, **kwargs)
    

 
from rest_framework.exceptions import ValidationError
    
class TeamMemebersOrganization(ListAPIView):
    permission_classes=[IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    serializer_class=UserDetailSerializer
    pagination_class=CustomPageNumberPagination
    filter_backends=[CustomSearchFilter]
    search_fields=[
        "email",
        "first_name",
        "phone_number"
    ]
    
    def get_queryset(self):

        organization_id = self.request.query_params.get('organization_id', None)
        if not organization_id:
            raise ValidationError("organization_id query parameter is required.")

        queryset =  UserDetails.objects.filter(organization_id=organization_id)
        return queryset
        


# This class activates a proxy for a user by generating access and refresh tokens and creating a
# ProxyLog object.
class ActivateProxy(APIView):
    def get(self,request):
        user_id = self.request.query_params.get('user_id',None)
        if not user_id:
            return Response({"status":False, "message":"key user_id is missing in query params"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user_obj = UserDetails.objects.get(id=user_id)
        except UserDetails.DoesNotExist:
            return Response({"status":False, "message":"the user_id you passed is invalid and not the users's id"}, status=status.HTTP_400_BAD_REQUEST)
        
        token = get_jwt_token(user_obj)
        proxy_access_token = token["access_token"]
        proxy_refresh_token = token["refresh_token"]
        proxy_obj = ProxyLog.objects.create(operation_team_user=request.user, proxy_user_id = user_id)
        return Response({"proxy_access_token":proxy_access_token, "proxy_refresh_token":proxy_refresh_token,"username": user_obj.first_name + user_obj.last_name,
            "user_role": user_obj.role.name,"valid_till":proxy_obj.valid_till, "proxy_id":proxy_obj.id}, status=status.HTTP_200_OK)
        
    
    
    
    
    
    
    
import subprocess
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required



def file_upload(file):
    file_extension = file.name.split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"  # Generate a unique filename
    s3 = boto3.client('s3',
                        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                        region_name=settings.AWS_S3_REGION_NAME
                        )
    try:
        s3.upload_fileobj(file, settings.AWS_STORAGE_BUCKET_NAME, unique_filename, ExtraArgs={'ACL': 'public-read'})
        file_url = f'https://{settings.AWS_S3_CUSTOM_DOMAIN}/temp/{unique_filename}'
        return file_url
    except Exception as e:
        return str(e)
    
class LookupAirlineCreate(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        airline = request.FILES.get('airline_csv')
        if airline:
            csv_data = airline.read().decode('utf-8')

            split_csv = csv.reader(csv_data.splitlines(), delimiter='^')

            for row in split_csv:
                LookupAirline.objects.create(
                    name=row[2],
                    code=row[0]
                )

            return JsonResponse({'status': 'success', 'message': 'LookupAirline created successfully'}, status=200)
        else:
            return JsonResponse({'status': 'error', 'message': 'No file found in the request'}, status=400)
    
    def patch(self, request):
        airline = request.FILES.get('airline_csv')
        if not airline:
            return JsonResponse({'status': 'error', 'message': 'No file found in the request'}, status=400)

        csv_data = airline.read().decode('utf-8')
        split_csv = csv.reader(csv_data.splitlines(), delimiter='^')

        created_count = 0
        updated_count = 0

        for row in split_csv:
            code, name = row[0], row[2]

            airline_obj, created = LookupAirline.objects.update_or_create(
                code=code,
                defaults={'name': name}
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        return JsonResponse({
            'status': 'success',
            'message': 'LookupAirline data processed successfully',
            'created': created_count,
            'updated': updated_count
        }, status=200)

          
    def get(self, request):
        search_key = request.GET.get('search', '')  

        airlines = LookupAirline.objects.exclude(name__in=["name", ""])

        if search_key:
            airlines = airlines.filter(
                Q(name__icontains=search_key) | Q(code__icontains=search_key)
            )

        airlines = airlines.order_by('code', 'name')
        serializer = LookupAirlineSerializer(airlines, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    



class ClientProxy(APIView):
    def get(self,request):
        return Response({'status': 'success', 'message': f'success', 'data':{"proxy_status":request.user.is_client_proxy}}, status=status.HTTP_200_OK)
    
    def post(self,request):
        try:
            proxy_status = request.data['status']
        except KeyError as e :
            return Response({'status': 'error', 'message': f'key "{status}"  required in payload data:{"status":True}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'status': 'error', 'message': f'Internal Server Error "{e}"  '}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        user = request.user
        user.is_client_proxy = proxy_status
        user.save()
        return Response({'status': 'success', 'message': f"Proxy enabled" if proxy_status else "proxy disabled"}, status=status.HTTP_200_OK)            
    
    
    
    
    
    
class GetUserPermissions(APIView):
    permission_classes=[IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    def get(self,request):
        user = request.user
        permission = self.get_user_permision(user.id, user.is_superuser)
        return Response({"data":permission})
    
    def get_user_permision(self, user_id, is_super_user):
        user = UserDetails.objects.get(id=user_id)
        # getting all the fieldss of the lookupmodels
        field_names = self.get_model_fields(LookupPermission)
        # geting the default permision set on lookupmodal
        if is_super_user:
            field_values = {field: True for field in field_names}
        else:
            role_id = user.role.id
            user_role = LookupRoles.objects.filter(id=role_id).first()
            default_permission = user_role.lookup_permission
            # showing all the fields from lookup permision weather it true or false

            field_values = {
                field: getattr(default_permission, field) for field in field_names
            }
        # filtering all the true fields because we just need to show only the permision for the roles
        true_fields_values = {key: values for key, values in field_values.items()}

        # structuring permision for front-end

        strucured_permision = self.structure_permision(true_fields_values)
        return strucured_permision

    def get_model_fields(self, model):
        fields = model._meta.get_fields()
        remove_fields = [
            "id",
            "is_deleted",
            "deleted_at",
            "created_at",
            "modified_at",
            "deleted_at",
            "name",
        ]
        field_names = [
            field.name
            for field in fields
            if not field.many_to_one and not field.one_to_many
        ]
        return [field for field in field_names if field not in remove_fields]
    
    def structure_permision(self,permision_dict):
        formated_list = [f'{key}_{str(item).lower()}' for key,item in permision_dict.items()]
        default_dict = {}
        nested_dict = default_dict
        for i in formated_list:
            
            #  we are giving a space eg "control panel"  we need space in between these word our current code doesn't satify
            # that's why we are giving this if condiditon
            # if you want to have space you need to give this key word "1space1"
            # don't forget to change in models we need to update in 2 models lookup and permisison
            
            if "1space1" in i:
                i = ' '.join(i.split('1space1'))
            
            #--------- end space condition ----------
            
            counter_split = i.split("_")
            splited = i.split("_", len(counter_split) - 2)
            counter = len(splited) - 1
            for letters in splited:
                try:
                    nested_dict = nested_dict[letters]
                except:
                    if counter == 0:
                        perm = letters.split("_")
                        bool_dict = {}
                        for i in range(0, int(len(perm) / 2)):
                            current = perm[i]
                            bool_value = eval(str(perm[i+1]).title())
                            
                            bool_dict[current] = bool_value
                            perm = perm[2:]
                        nested_dict.update(bool_dict)
                        pass
                    else:
                        nested_dict[letters] = {}
                        nested_dict = nested_dict[letters]
                counter -= 1
            nested_dict = default_dict
        return default_dict

class OrganizationProfile(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self,request):
        roles = ["agency_owner","distributor_owner", "out_api_owner"]
        has_perm = request.user.role.name in roles
        serializer = OrganizationProfileSectionSerializer(request.user.organization,context={'request': request}).data
        data = dict(
                    organization_details=serializer,
                    has_perm = has_perm
               )
        return Response({"message":"success", "data":data})
    
    
    def patch(self,request):
        try:
            id = request.data['id']
            user_id = request.data['user_id']
            organization_name = request.data['organization_name']
            organization_currency = request.data['organization_currency']
            state = request.data['state']
            organization_country = request.data['organization_country']
            organization_gst_number = request.data['organization_gst_number']
            organization_zipcode = request.data['organization_zipcode']
            address = request.data['address']
            organization_tax_number = request.data['organization_tax_number']
            profile_picture = request.FILES.get('profile_picture',None)
            first_name = request.data['first_name']
            last_name = request.data['last_name']
            email = request.data['email']
            phone = request.data['phone']
            support_email=request.data['support_email']
            support_phone=request.data['support_phone']
            dom_markup=request.data['dom_markup']
            int_markup=request.data['int_markup']


            # virtual_ac_no=request.data['virtual_ac_no']
        except Exception as e:
            return Response({"message":f"key missing {e}"})
        organization = Organization.objects.get(id=id)

        organization.organization_name=organization_name
        organization.organization_currency=organization_currency
        organization.state=state
        organization.organization_country=Country.objects.filter(lookup__country_name__iexact=organization_country).first()
        organization.organization_gst_number=organization_gst_number
        organization.organization_zipcode=organization_zipcode
        organization.address=address
        organization.organization_tax_number=organization_tax_number
        if profile_picture:
            organization.profile_picture=profile_picture
        organization.support_email=support_email
        organization.support_phone=support_phone
        # organization.virtual_ac_no=virtual_ac_no
        organization.save()
        user = UserDetails.objects.get(id=user_id)

        user.first_name=first_name
        user.last_name=last_name
        user.email=email
        user.phone_number=phone
        user.dom_markup = dom_markup
        user.int_markup = int_markup
        user.save()
        
        serializer = OrganizationProfileSectionSerializer(organization,context={'request': request}).data
        data = dict(
                    organization_details=serializer,
               )
        return Response({"message":"success", "data":data})
    
    
    
   
class InternalidGenerate(APIView):
    permission_classes=[]
    authentication_classes = []
    
    def get(self,request):
        now = time.time()
        user = UserDetails.objects.all()
        for user in  user:
            if not user.organization:
                 user.user_external_id = f"NOR-{''.join(str(now).split('.')[0])}"
            else:
                user.user_external_id = f"{''.join([i[0] for i in user.organization.organization_name.split()])}-{''.join(str(now).split('.')[0])}"
            user.save()
        return Response({"message":"kaaa"})


class UpdateLinkForOrganization(APIView):
    permission_classes = []
    authentication_classes = []
    def post(self, request):
        easy_link_billing = Integration.objects.filter(Q(lookup_integration__name__icontains='easy-link backoffice suit') & Q(name__icontains='COK')).first()
        if easy_link_billing:
            easy_link_billing_uuid = easy_link_billing.id
            Organization.objects.filter(
                Q(easy_link_billing_account__isnull=True)
            ).update(easy_link_billing_account=easy_link_billing_uuid)
            return Response({"message": "updated"})
        else:
            return Response({"message": "No easy link billing account found."}, status=404)

class EasyLinkBranchAllocationDropDown(APIView):
    def get(self, request):
        integrations = Integration.objects.filter(
            Q(lookup_integration__name__icontains='easy-link'),
            organization__organization_country_id=F('country_id')
        ).values('id', 'name').order_by('name').distinct('name')
        
        data = [{"id": item['id'], "name": item['name']} for item in integrations]
        return Response({"data": data})
          

class BranchAllocationView(APIView):
    def get(self,request):
        s_key = request.query_params.get('search_key', None)
        page_size=request.query_params.get("page_size",15)
        if s_key:
           org_inst = Organization.objects.filter(Q(organization_name__icontains=s_key)) 
        else:
            org_inst = Organization.objects.all().order_by('-modified_at')
        if org_inst.exists():
            paginator = CustomPageNumberPagination(page_size=page_size)
            paginated_queryset = paginator.paginate_queryset(org_inst, request)
            serializer = UpdateBranchAllocationSerializer(paginated_queryset, many=True)
            total_data = org_inst.count()

            data = {
                "total_pages": paginator.page.paginator.num_pages,
                "current_page": paginator.page.number,
                "next_page": paginator.get_next_link(),
                "prev_page": paginator.get_previous_link(),
                "total_data":total_data,
                "page_size":page_size,
                "data": serializer.data
            }
            return Response(data)
        else:
            return Response({"message": "No organization found"}, status=404)
        
    def patch(self,request):
        id = request.data.get('id')
        organization_instance = Organization.objects.filter(id = id).first()
        billing_account_id = request.data.get('easy_link')
        if organization_instance:
            integration_instance = Integration.objects.filter(id= billing_account_id).first()
            if integration_instance:
                organization_instance.easy_link_billing_account = integration_instance
                organization_instance.save()
                return Response({"message": "Branch allocation updated successfully"}, status=200)
            else:
                return Response({"message": "integration instance not found"}, status=404)
        else:
            return Response({"message": "Organization not found"}, status=404)
        
class UpdateAlreadyExisting_Finanace_And_Operation(APIView):
    def patch(self, request):
        organization_id = request.user.organization.id
        organization_instance = UserDetails.objects.filter(Q(organization__id = organization_id) & Q(role__name = 'operations'))
        if organization_instance.exists():
            role_instance = LookupRoles.objects.filter(Q(name = 'operations')).first()
            if role_instance:
                operation_lookup_permission = role_instance.lookup_permission
                permission_fields = [
                    field.name
                    for field in Permission._meta.get_fields()
                    if isinstance(field, models.BooleanField)
                ]
                updated_users = []
                for user in organization_instance:
                    user_permission = user.user_group.permission
                    for field in permission_fields:
                        if getattr(user_permission, field) != getattr(operation_lookup_permission, field):
                            setattr(user_permission, field, getattr(operation_lookup_permission, field))
                    user_permission.save()
                    updated_users.append(user.id)
                return Response(
                    {"message": "Permissions updated successfully", "updated_users": updated_users},
                    status=200,
                )
        return Response({"message": "No operations users found to update permissions"}, status=404)
    
class AgencyMasterListAPI(APIView):
    def get(self, request):
        org_id = request.query_params.get('id', None)
        if org_id:
            agency_instance = Organization.objects.filter(id=org_id)
        else:
            return Response("Provide organization ID")
        serializer = AgencyMasterListSerializer(agency_instance, many=True)
        return Response(serializer.data)
# 
class GetSalesAgentList(APIView):
    def get(self, request):
        sales_agent_instance = UserDetails.objects.filter(Q(organization__organization_name__icontains='BTA') & Q(role__name__icontains='sale')
                                                          ).values('id','first_name')
        data = [{"id": item['id'],"name": item['first_name']} for item in sales_agent_instance]
        return Response({"data":data})
    

class UpdateAgencyMaster(APIView):
    permission_classes = [HasAPIAccess]
    def post(self, request):
        success, message, errors = self.update_agency_master(request.data)
        d = {"message": message} if success else errors if errors else {"message": message}
        return Response(d,status=200 if success else 400 if errors else 404)
        
    def update_agency_master(self, data):
        id = data.get('id')
        organization_instance = Organization.objects.filter(id=id).first()
        if not organization_instance:
            return False, "Organization not found", None
        serializer = AgencyMasterUpdateSerializer(organization_instance, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return True, "Agency updated successfully", None
        else:
            return False, "Validation failed", serializer.errors


#--------------------------------------------------------------

# class CreateOrganizationAPI(APIView):
#     authentication_classes = []
#     permission_classes = []
#     def post(self, request):
#         # df = pd.read_excel(r'D:\BTA_Folder\New_Organization_Data\TEST AGENCY.xlsx')
#         file = .get('excel_path')
#         if not file:
#             return Response({"error": "Excel file is required."}, status=400)
#         try:
#             df = pd.read_excel(file)
#         except Exception as e:
#             return Response({"error": f"Failed to read Excel file: {str(e)}"}, status=400)

#         thread = threading.Thread(target=self.process_new_users, kwargs={
#                                                         "df":df})
#         thread.start()
#         # invoke(event='SEND_LOGIN_OTP',number_list = [] if not user_obj.phone_code else [f"{user_obj.phone_code}{user_obj.phone_number}"],email_list=[user_obj.email], data = {"otp":otp, "country_name":country_name,"customer_email":user_obj.email})
#         return Response({"message": "Process Started"}, status=201)


#     def process_new_users(self,**kwargs):
#         df = kwargs.get("df")
#         df= df.fillna("")
#         start = time.time()
#         seg = time.time()
#         count = 0 
#         for _, row in df.iterrows():
#             if count%100==0:
#                 seg = time.time()
#             count+=1
#             org_type_name = LookupOrganizationTypes.objects.get(name='agency')
#             lookup_country = LookupCountry.objects.get(country_name='India')
#             country_obj = Country.objects.get(lookup=lookup_country)  

#             # --------------------------start-----------------------------------------------
#             easy_link_billing = Integration.objects.filter(Q(lookup_integration__name__icontains='easy-link  backoffice suit') & Q(name__icontains=row.get('Branch Id'))).first()

#             first_data = Integration.objects.filter(Q(lookup_integration__name__icontains='easy-link  backoffice suit')).first()
#             # ----------------------end---------------------------------------------------
#             sales_agent_name = row.get('Sales Agent')  # Extract 'Sales Agent' value from the row
#             sales_Agent_id = UserDetails.objects.filter(Q(first_name__icontains=sales_agent_name)).first()
#             zipcode = row.get("Pincode")
#             zipcode = zipcode if zipcode else ""
#             org_instance = Organization.objects.create(organization_name = row.get('AgencyName',''),
#                                                         organization_type= org_type_name if org_type_name else None,
#                                                         is_iata_or_arc= False,
#                                                         iata_or_arc_code=None,
#                                                         address=row.get('Address',""),
#                                                         state=row.get('State',""),
#                                                         organization_country=country_obj,
#                                                         whitelabel=None,
#                                                         organization_zipcode=zipcode,
#                                                         organization_pan_number=row.get("PanNumber_Or_TaxNumber",""),
#                                                         organization_gst_number=None,
#                                                         organization_tax_number=row.get("PanNumber_Or_TaxNumber",""),
#                                                         organization_currency=country_obj.currency_symbol,
#                                                         easy_link_account_code=row.get("Customer_code",""),
#                                                         easy_link_account_name=row.get("AgencyName",""),
#                                                         easy_link_billing_account= easy_link_billing if easy_link_billing else first_data,
#                                                         status = 'active',
#                                                         easy_link_billing_code=row.get("Int. Ref. Code",""),
#                                                         sales_agent=sales_Agent_id if sales_Agent_id else None)

#             role_inst = LookupRoles.objects.get(name = 'agency_owner')
#             new_password = str(row.get("Customer_code")) + '@BTA'
#             new_password = str(row.get("Int. Ref. Code")) + '@BTA'

#             UserDetails.objects.create(first_name = row.get("F_Name"),
#                                         last_name  =row.get("L_Name"),
#                                         email = row.get("vcEmail"),
#                                         phone_code=None,
#                                     phone_number=None,
#                                    role= role_inst,
#                                    address= row.get('Address',""),
#                                    zip_code=zipcode,
#                                    organization=org_instance,
#                                    agency_name=row.get("AgencyName"),
#                                    password = make_password(new_password),
#                                    base_country= country_obj
#                                    )
        # return Response("User and Org created successfully")

#         end = time.time()





class UserValidateTokenGenerateView(APIView):
    permission_classes = []
    authentication_classes = []
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'message': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
    
        user = UserDetails.objects.filter(email=email).first()
        
        if not user:
            
            return Response({'message': 'User not found'}, status=status.HTTP_200_OK)
        else:
            
            kwargs = {
                "user_id" : str(user.id),
                "user" : str(user),
                "sec"  : 86400
            }
            token = jwt_encode(kwargs)
            reset_url  = f"{WEB_URL}account/reset-password?token={token}"
            # email = "vishnu.ts@elkanio.com"
            thread = threading.Thread(target=invoke, kwargs={
                        "event":"RESET_PASSWORD_LINK", 
                        "email_list":[email],
                        "data" :{"reset_url":reset_url,
                                "to_email":email,
                                "country_name":user.organization.organization_country.lookup.country_name}
                        })
            thread.start()

            # invoke(event='RESET_PASSWORD_LINK',email_list=[email], data = {"reset_url":reset_url,"to_email":email,"country_name":user.organization.organization_country.lookup.country_name})
            return Response({'message': 'Password reset link sent successfully'}, status=status.HTTP_200_OK)
        

class ValidateTokenView(APIView):
    permission_classes = []
    authentication_classes = []
    def post(self, request):
        token = request.data.get('token')
        user_data  = jwt_decode(token)
        user_id = user_data.get('user_id')
        if not user_id:
            return Response({"message":user_data.get("message"),"is_valid":False},status=user_data.get('status'))
        else:
            return Response({"message":"success","is_valid":True},status=status.HTTP_200_OK)
        
class ResendOtpView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        unique_id = request.data.get('unique_id')
        password = request.data.get('password')
        country_name = request.data.get('country_name',None)
        
        if (country_name is None or country_name==''):
            return Response({"message":"please enter country name"},status=status.HTTP_400_BAD_REQUEST) 
        if not unique_id or not password:
            return Response(
                {"message": "email and password missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user_obj = UserDetails.objects.filter(
                (Q(email=unique_id) | Q(phone_number=unique_id)) &
                Q(is_active=True)
            ).first()
            
            if not user_obj:
                return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            otp = generate_otp(user_obj)
            # voicensms = VoicenSMS(number_list=[user_obj.phone_number],data={"country_name":country_name,"otp":otp})
            # voicensms.sms_integration()
            sms_thread = threading.Thread(target=send_sms,  kwargs={ "number_list": [user_obj.phone_number],
                                             "data": {"country_name": country_name, "otp": otp}
                                            })
            sms_thread.start()
            thread = threading.Thread(target=invoke, kwargs={
                                                        "event":"SEND_LOGIN_OTP",
                                                        "number_list": [] if not user_obj.phone_code else [f"{user_obj.phone_code}{user_obj.phone_number}"],
                                                        "email_list": [user_obj.email],
                                                        "data": {
                                                            "otp": otp,
                                                            "country_name": country_name,
                                                            "customer_email": user_obj.email
                                                        }})
            thread.start()
            return Response({"message": "OTP resent successfully","otp": otp}, status=status.HTTP_200_OK)
        except UserDetails.DoesNotExist:
            return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

class GetMarkupView(APIView):
    def get(self, request):
        module = request.query_params.get("module", None)
        if module == 'flight':
            user_markup_instance = UserDetails.objects.filter(id=request.user.id).values('id','first_name','dom_markup','int_markup')
            data = [{"id": item['id'],"name": item['first_name'],"dom_markup":item['dom_markup'], "int_markup":item['int_markup']} for item in user_markup_instance]
            return Response(data)
        else:
            return Response([])


class CreateExcelTemplateForTeamCreate(APIView):

    def get(self, request):
        df = pd.DataFrame(columns= ['First Name', 'Last Name', 'Phone', 'Email', 'Wallet Amount','Group' ])
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        file_path = self.file_upload(buffer)
        return Response(file_path)

    def file_upload(self,file):
        unique_filename = f"{uuid.uuid4()}.xlsx"
        s3 = boto3.client('s3',
                            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                            region_name=settings.AWS_S3_REGION_NAME
                            )
        try:
            s3.upload_fileobj(file, settings.AWS_STORAGE_BUCKET_NAME, unique_filename, ExtraArgs={'ACL': 'public-read'})
            file_url = f'https://{settings.AWS_S3_CUSTOM_DOMAIN}/temp/{unique_filename}'
            return file_url
        except Exception as e:
            return str(e)

    def post(self, request):
        excel_file = request.FILES.get("excel_data")
        if not excel_file:
            return Response({"error": "No file uploaded"}, status=400)

        try:
            df = pd.read_excel(excel_file)
            results = []
            count= 0
            for index, row in df.iterrows():
                try:
                    role_name = 'distributor_agent'
                    role_obj = LookupRoles.objects.filter(name=role_name).first()
                    user_group_name = row.iloc[5]
                    user_group_obj = None
                    if user_group_name:
                        user_group_obj = UserGroup.objects.filter(name=user_group_name).first()
                    name = row.iloc[0] + ' ' + row.iloc[1]
                    country = request.user.base_country

                    data = {
                        "name": name,
                        "phone_number": row.iloc[2],
                        "email": row.iloc[3],
                        "country": country.id,
                        "role_id": role_obj.id if role_obj else None,
                        "group_id": user_group_obj.id if user_group_obj else None,
                        "wallet_amount": row.iloc[4],
                        "organization_obj": request.user.organization,
                        "easy_link_billing_code": request.user.organization.easy_link_billing_code,
                        "distributor_name": request.user.organization.organization_name,
                        "email_data": [row.iloc[3], request.user.email],
                        "org_type_name": request.user.organization.organization_type.name,
                        "country_name": request.user.base_country.lookup.country_name
                    }
                    team_create_response = self.create_team(**data)
                    if team_create_response.get('error_status'):
                        count = count + 1
                        results.append({"status": "success", "message": f"Number of created teams : {count}"})
                    else:
                        results.append({"row": index + 1, "status": "error", "message": team_create_response})

                except Exception as e:
                    results.append({"row": index + 1, "message": str(e)})
            if any(result['status'] == 'error' for result in results):
                return Response({"status":"error", "results": results})
            else:
                return Response({"status":"success", "results": results})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def create_team(self,**kwargs):
        err_status =False
        if not self.validate_phonenumber(kwargs.get("phone_number")):
            return {"message": f"Phone Number: {kwargs.get('phone_number')} is not valid.", "error_status" : err_status}
        
        data_email = kwargs.get('email')
        email = data_email.strip().lower()
        phone_number = kwargs.get("phone_number")
        user_dict = self.user_exist(email, phone_number)
        country_id = kwargs.get("country")

        country_obj = Country.objects.get(id=country_id)
        is_phone_number_valid = self.validate_phone_number(
            country_obj.lookup.country_code, phone_number
        )
        if not is_phone_number_valid:
            return {"message":f"please enter the correct phone number for the country {country_obj.lookup.country_name}", "error_status" : err_status}

        if user_dict["user"]:
            medium = "email" if user_dict["email"] else "phone number"
            return {"message":f"the user with this {medium}:{user_dict['user'].email if user_dict['email'] else user_dict['user'].phone_number} already exists under organization {user_dict['user'].organization}","error_status" : err_status}
            

        random_password = passwordgenerator()
        try:
            user = UserDetails.objects.create(
                phone_number=phone_number,
                email=email,
                first_name=kwargs.get("name"),
                user_group_id=kwargs.get("group_id"),
                role_id=kwargs.get("role_id"),
                organization=kwargs.get('organization_obj'),
                base_country=country_obj,
                phone_code=country_obj.lookup.calling_code,
                password = make_password(random_password)
            )
            err_status= True
        except Exception as e:
            return str(e)
        requested_wallet_amount = kwargs.get("wallet_amount",None)

        if not requested_wallet_amount or (isinstance(requested_wallet_amount, float) and math.isnan(requested_wallet_amount)):
            err_status= False
            user.hard_delete()
            return  {"message":"wallet ammount not passed distributor agent should have  wallet ammount","error_status" : err_status}
        if not self.is_wallet_ammount_applicable(
                                                requested_wallet_amount=requested_wallet_amount,
                                                organization_obj = kwargs.get('organization_obj'),
                                                easy_link_billing_code = kwargs.get('easy_link_billing_code')
                                                ):
            err_status= False
            return {"message": "requested amount is  higher than your wallet balance","error_status" : err_status}
        DistributorAgentFareAdjustment.objects.create(user = user,available_balance=requested_wallet_amount)        
    
        #---------------START-----------------------------------------------------------------------------------------------------
        data_list = {
                    "agent_name":user.first_name, 
                     "username":email, 
                     "temporary_password":random_password,
                     "login_url": "lOGIN url",
                    "distributor_name":kwargs.get('distributor_name'),
                    "country_name": kwargs.get('country_name')
                       }

        email_data = kwargs.get('email_data')
        org_type = kwargs.get('org_type_name')
        if org_type == 'master':
            data_list = {
                        "organization_name":kwargs.get('distributor_name'),
                        'users_first_name':user.first_name,
                        'users_last_name':user.last_name,
                        'password':random_password,
                        "country_name": kwargs.get('country_name')
                        }
            thread = threading.Thread(target=invoke, kwargs={
                        "event":"BTA_Team_Creation", 
                        "email_list":email_data,
                        "data" :data_list
                        })
            thread.start()
        else:
            thread = threading.Thread(target=invoke, kwargs={
                        "event":"Registration_email_from_Distributor_to_Agent", 
                        "email_list":email_data,
                        "data" :data_list
                        })
            thread.start()
        #---------------END-----------------------------------------------------------------------------------------------------
        return {"message": "created succefully","error_status" : err_status}


    def is_wallet_ammount_applicable(self,requested_wallet_amount,organization_obj,easy_link_billing_code):
        url,  branch_code,  portal_reference_code =get_accounting_software_credentials(organization_obj)
        response = get_credit_limit(base_url=url, portal_ref_code=portal_reference_code,billing_code=easy_link_billing_code)
        credit_data = response.data
        try:
            credit_data['F']
        except KeyError as e:
            raise Exception ("esy link account error")
        return float(requested_wallet_amount) < float(credit_data['F']), credit_data['F']

    def validate_phonenumber(self, phone_number):
        return str(phone_number).isnumeric()

    def user_exist(self, email=None, phone_number=None):
        email = UserDetails.objects.filter(email=email)
        phone_number = UserDetails.objects.filter(phone_number=phone_number).exclude(
            Q(phone_number__isnull=True) | Q(phone_number="")
        )
        details = {"email": email.exists(), "phone_number": phone_number.exists()}
        if email.exists():
            user = email.first()
        elif phone_number.exists():
            user = phone_number.first()
        else:
            user = False
        details.update({"user": user})
        return details

    def validate_phone_number(self, country_code, phone_number):
        try:
            phone_number = str(phone_number)
            parsed_number = phonenumbers.parse(phone_number, country_code)
            if not phonenumbers.is_possible_number(parsed_number):
                return False
            if not phonenumbers.is_valid_number(parsed_number):
                return False
            if self.is_repeated_digits(phone_number):
                return False
            return True
        except NumberParseException:
            return False

    def is_repeated_digits(self, phone_number):
        if len(set(phone_number)) == 1:
            return True
        return False

    # ------------- end post---------------------------------------


class ListOutApiView(APIView):
    permission_classes = [HasAPIAccess]
    def get(self, request):
        org_id = request.query_params.get('id', None)
        search_key = request.query_params.get('search')
        try:
            if search_key and org_id:
                filter_query = OutApiDetail.objects.filter(
                                            Q(status__icontains = search_key) &
                                            Q(organization__icontains = org_id)
                                                            )
                serializer = OutApiDetailGetSerializer(filter_query, many=True)
                data = serializer.data
            else:
                outapi_ins  = OutApiDetail.objects.filter(Q(status__icontains = search_key))
                serializer = OutApiDetailGetSerializer(outapi_ins, many=True)
                data = serializer.data
            return Response(data)
        except Exception as e:
            return Response(str(e))
        
class OutApiStatusChange(APIView):
    permission_classes =[HasAPIAccess]
    def patch(self, request):
        try:
            status = request.data.get('status')
            outapi_id = request.data.get('id')
            org_obj = None
            if outapi_id:
                outapi_obj = OutApiDetail.objects.filter(id=outapi_id).first()
                if outapi_obj:
                    org_obj = outapi_obj.organization
            if not org_obj:
                org_obj = request.user.organization

            out_api_obj , created = OutApiDetail.objects.update_or_create(
                organization = org_obj,
                defaults= {
                    "status" :status
                }
            )
            if created:
                print("created")
            else:
                print("updated")
            return Response("successfully status changed")
        except Exception as e:
            return Response(str(e))


class CreateAccesToken(APIView):
    def get(self, request):
        try:
            user_id = request.query_params.get('id')
            if user_id:
                access_token = AccessToken()
                access_token["user_id"] = user_id 
            else:
                user = request.user
                access_token = AccessToken.for_user(user)
            access_token.set_exp(lifetime=timedelta(days=365))
            payload = access_token.payload
            if payload:
                exp_time = payload['exp']
                user_id = payload['user_id']
                user_instance = UserDetails.objects.filter(id = user_id).first()
                org_id = user_instance.organization
                outapiobj , created = OutApiDetail.objects.update_or_create(
                    organization = org_id,
                    defaults={
                    "token" : str(access_token),
                    "exp_time_epoch" : exp_time
                    }
                )
            return Response({'access_token': str(access_token),"expiry":exp_time})
        except Exception as e:
            return Response(str(e))

class ListAccesToken(APIView):
    def get(self, request):
        org_id = request.user.organization
        org_inst = OutApiDetail.objects.filter(organization= org_id).first()
        if org_inst:
            data = {"token":org_inst.token, "expiry":org_inst.exp_time_epoch, "status":org_inst.status} 
            return Response(data, status=status.HTTP_200_OK)
        data = {"token":None, "expiry":None, "status":None} 
        return Response(data, status = status.HTTP_204_NO_CONTENT)


class Testgetuserusingorg(APIView):
    def get(self, request):
        org_id = request.query_params.get('id')
        update_email = request.query_params.get('email')
        if update_email:
            UserDetails.objects.update(
                email = update_email
            )

        if not org_id:
            return Response("need org id")
        user_ins = UserDetails.objects.filter(organization = org_id).first()
        if not user_ins:
            return Response("No User Exist")

        return Response({"id":user_ins.id, "name":user_ins.first_name,"email":user_ins.email})

class ThemeView(APIView):
    def get(self, request):
        org_id = request.user.organization.id
        if not org_id:                      
            return Response("No Organization Exist")
        org_theme_ins = OrganizationTheme.objects.filter(organization_id = org_id).first()
        if not org_theme_ins:
            lookup_theme_ins = LookupTheme.objects.all().first()
        if org_theme_ins:
            serializer = ThemeGetSerializer(org_theme_ins)
            return Response(serializer.data)
        else:
            if lookup_theme_ins:
                serializer = LookupThemeSerializer(lookup_theme_ins,context={"org_id": org_id})
                return Response(serializer.data)
        return Response("No Theme found for the Organization")

    def patch(self, request):
        organization_id = request.data.get('organization_id')
        if not organization_id:
            return Response("Need organization id")
        org_theme_obj = OrganizationTheme.objects.filter(organization_id=organization_id).first()
        if not org_theme_obj:
            data = request.data.copy()
            data['organization_id'] = request.user.organization.id
            serializer = ThemeSerializer(data=data)
        else:
            serializer = ThemeSerializer(org_theme_obj, data=request.data, partial=True)

        if serializer.is_valid():
            updated_theme_obj = serializer.save()
            profile_picture = request.FILES.get('profile_picture', None)
            if profile_picture:
                organization = org_theme_obj.organization_id if org_theme_obj else request.user.organization
                organization.profile_picture = profile_picture
                organization.save()
            return Response("Theme Updated Successfully", status=status.HTTP_200_OK)    
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GetThemeTemplate(APIView):
    def get(self, request):
        template_obj = LookupTemplate.objects.all()
        if template_obj:
            serializer = ThemeTemplateSerializer(template_obj, many=True)
            return Response(serializer.data)
        else:
            return Response('No Template Found')
class UserGroupPermissionListAndUpdate(APIView):
    permission_classes = [HasAPIAccess]
    def post(self,request):
        try:
            permission_dict = request.data['permission']
            group_id = request.data['group_id']
        except Exception as e:
            return Response({"message":f"{e} key missing in payload"})
        group = UserGroup.objects.get(id=group_id)
        permissons_restructuring = self.convert_to_key_value(permission_dict)
        if group.permission:
            Permission.objects.filter(id=group.permission.id).update(**permissons_restructuring)
            permission_obj = group.permission
        else:
            permission_obj = Permission.objects.create(**permissons_restructuring)
            group.permission = permission_obj
        group.name = group.name
        group.permission = permission_obj
        group.save()
        return Response({"message":f"Group {group.name} updated successfully !"},status=status.HTTP_200_OK)
    
    def convert_to_key_value(self, data, parent_key=""):
        items = []
        for k, v in data.items():
            if ' 'in k:
                k = k.replace(' ', '1space1')
            if k == "permissions":
               new_key = f"{parent_key}" if parent_key else k
            else:
                new_key = f"{parent_key}_{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.convert_to_key_value(v, new_key).items())
            else:
                items.append((new_key, eval(str(v).title())))
        return dict(items)
    
    def get(self,request):
        group_id = request.GET.get('group_id',None)
        role_id = request.GET.get('role_id',None)
        if not group_id:
            return Response(
                {"message": "group_id is missing in query Params"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            group_obj = UserGroup.objects.get(id=group_id)
        except Exception as e:
            return Response({"message":f"{e}"},status=status.HTTP_400_BAD_REQUEST)

        user_role = LookupRoles.objects.filter(id=role_id).first()
        field_names = self.get_model_fields(LookupPermission)
        default_permission = user_role.lookup_permission
        field_values = {field: getattr(default_permission, field) for field in field_names}

        true_fields_values = {key:values for key,values in field_values.items() if values}        
        group_permission = group_obj.permission
        group_field_values = {field: getattr(group_permission, field) for field in true_fields_values}
        strucured_permision = self.structure_permision(group_field_values)
        data = {
            "permission":strucured_permision
        }
        return Response({"data":data},status=status.HTTP_200_OK)
    def get_model_fields(self, model):
        fields = model._meta.get_fields()
        remove_fields = [
            "id",
            "is_deleted",
            "deleted_at",
            "created_at",
            "modified_at",
            "deleted_at",
            "name",
        ]
        field_names = [
            field.name
            for field in fields
            if not field.many_to_one and not field.one_to_many
        ]
        return [field for field in field_names if field not in remove_fields]
    
    def structure_permision(self,permision_dict):
        formated_list = [f'{key}_{str(item).lower()}' for key,item in permision_dict.items()]
        default_dict = {}
        nested_dict = default_dict
        for i in formated_list:
            if "1space1" in i:
                i = ' '.join(i.split('1space1'))
            
            counter_split = i.split("_")
            splited = i.split("_", len(counter_split) - 2)
            counter = len(splited) - 1
            for letters in splited:
                try:
                    nested_dict = nested_dict[letters]
                except:
                    if counter == 0:
                        perm = letters.split("_")
                        bool_dict = {}
                        for i in range(0, int(len(perm) / 2)):
                            current = perm[i]
                            bool_value = eval(str(perm[i+1]).title())

                            bool_dict[current] = bool_value
                            perm = perm[2:]
                        
                        nested_dict["permissions"].update(bool_dict)
                        pass
                    else:
                        nested_dict[letters] = {}
                        if counter == 1:
                            nested_dict = nested_dict[letters]
                            nested_dict["permissions"] = {}
                        else:
                            nested_dict = nested_dict[letters]
                counter -= 1
            nested_dict = default_dict
        return default_dict
class UserGroupListUnderOrganization(APIView):
    def get(self, request):
        search_key = request.query_params.get("search")
        page_size = request.query_params.get('page_size',10)
        organization_id = request.user.organization
        user_group_objs = UserGroup.objects.filter(organization = organization_id.id)
        if search_key:
            user_group_objs = UserGroup.objects.filter(Q(name__icontains = search_key))
        if not user_group_objs:
            return Response("No usergroups exist under this organization")
        paginator = CustomPageNumberPagination(page_size= page_size)
        paginator_queryset = paginator.paginate_queryset(user_group_objs, request)
        serializer = UserGroupUnderOrganizationlistSerializer(paginator_queryset, many=True)
        data = {"data": serializer.data,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next_page": paginator.get_next_link(),
            "prev_page": paginator.get_previous_link(),
            "total_data":user_group_objs.count(),
            "page_size":page_size}
        return Response(data)

class UserGroupIsActiveChangeAPI(APIView):
    def patch(self, request):
        try:
            status_param = request.data.get("status")
            user_group_id = request.data.get("id")
            if status_param is None or user_group_id is None:
                return Response({"error": "status and id are required"}, status=status.HTTP_400_BAD_REQUEST)
            user_group_obj = UserGroup.objects.filter(id=user_group_id).first()
            if not user_group_obj:
                return Response({"error": "No UserGroup Exists"}, status=status.HTTP_404_NOT_FOUND)
            user_group_obj.is_visible = status_param
            user_group_obj.save()
            return Response({"message": "Successfully changed status"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetWhiteLabelStatus(APIView):
    def get(self, request):
        try:
            org_id = request.user.organization_id
            org_inst = Organization.objects.filter(id=org_id).first()
            if org_inst:
                return Response({'id':org_inst.id , 'status':org_inst.is_white_label})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class WhiteLabelPagesView(APIView):
    def post(self, request):
        try:
            org_id = request.user.organization_id
            request.data['organization'] = org_id
            #whitelabel_inst = None
            org_inst = Organization.objects.filter(id=org_id).first()
            request.data['whitelabel'] = org_inst.whitelabel.id if org_inst else WhiteLabel.objects.filter(is_default=True).first()
            serializer = WhiteLabelPageSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    serializer.save()
                    return Response("created successfully", status=status.HTTP_201_CREATED)
                except IntegrityError:
                    return Response({"error":"Duplicate entry: A page with this slug already exists for the given whitelabel"}, status=status.HTTP_400_BAD_REQUEST)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:
            org_id = request.user.organization_id
            current_whitelabel = request.user.organization.whitelabel
            org_inst = Organization.objects.filter(organization_type__name='master').first()
            white_label_pages = WhiteLabelPage.objects.filter(organization_id=org_id) if org_id else WhiteLabelPage.objects.none()

            if not white_label_pages.exists() and org_inst:  # Ensure org_inst is not None
                white_label_pages = WhiteLabelPage.objects.filter(organization_id=org_inst.id, slug_url='/')
                for pages in white_label_pages:
                    WhiteLabelPage.objects.create(
                        slug_url = pages.slug_url,
                        heading = pages.heading,
                        html_content = pages.html_content,
                        css_style = pages.css_style,
                        js_code = pages.js_code,
                        page_content = pages.page_content,
                        organization = request.user.organization if request.user.organization else None,
                        whitelabel = current_whitelabel
                    )
            serializer = WhiteLabelPageSerializer(white_label_pages, many=True)
            return Response({'data': serializer.data})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    def patch(self, request):
        try:
            page_id = request.data.get("id")
            if page_id is None:
                return Response({"error": "id is required"}, status=status.HTTP_400_BAD_REQUEST)
            white_label_page = WhiteLabelPage.objects.filter(id=page_id).first()
            if not white_label_page:
                return Response({"error": "No WhiteLabelPage Exists"}, status=status.HTTP_404_NOT_FOUND)
            request.data['organization'] = request.user.organization_id
            serializer = WhiteLabelPageSerializer(white_label_page, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response('Updated Successfully', status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    def delete(self, request,id):
        instance =  WhiteLabelPage.objects.filter(id = id).first()
        if instance:
            instance.hard_delete()
            return Response("deleted successfully",status=status.HTTP_200_OK)
        return Response("No data found", status = status.HTTP_404_NOT_FOUND)

class ChangeOrgWhiteLabelStatus(APIView):
    def patch(self, request):
        status_name = request.data.get('status')
        organization_id = request.data.get('id', None)
        if not status_name:
            return Response("Missing Status Key",status=status.HTTP_404_NOT_FOUND)
        if not organization_id:
            organization_id = request.user.organization_id
        organization_obj = Organization.objects.filter(id=organization_id).first()
        if not organization_obj:
            return Response("No Organization Exists", status=status.HTTP_404_NOT_FOUND)
        organization_obj.is_white_label =  status_name
        organization_obj.save()
        return Response("Successfully Changed White Label Status", status=status.HTTP_200_OK)
    def get(self, request):
        org_id = request.query_params.get('id', None)
        search_key = request.query_params.get('search_key') 
        status = request.query_params.get('search','pending')
        try:
            if search_key and status:
                filter_query = Organization.objects.filter(
                                    Q(organization_name__icontains = search_key) &
                                    Q(is_white_label__icontains =  status)
                                                            )
                serializer = OrgWhiteLabelGetSerializer(filter_query, many=True)
                data = serializer.data
            else:
                whitelabel_ins  = Organization.objects.filter(Q(is_white_label__icontains =  status))
                serializer = OrgWhiteLabelGetSerializer(whitelabel_ins, many=True)
                data = serializer.data
            return Response(data)
        except Exception as e:
            return Response(str(e))
        
class HostView(APIView):
    def post(self, request):
        try:
            host_name = request.data.get('host')
            id = request.data.get('id')
            org_id = request.user.organization_id
            if not host_name:
                return Response('Host Field Missing', status= status.HTTP_400_BAD_REQUEST)
            existing_whitelabel = WhiteLabel.objects.filter(id=id).first()
            if existing_whitelabel and existing_whitelabel.is_default:
                whitelabel_ins = WhiteLabel.objects.create(host=host_name)
            else:
                whitelabel_ins, created = WhiteLabel.objects.update_or_create(
                    id=id,
                    defaults={"host": host_name}
                )
            org_whitelabel_updated = Organization.objects.filter(id = org_id).update(whitelabel = whitelabel_ins.id)
            whitelabelpage_inst = WhiteLabelPage.objects.filter(organization_id = org_id).update(whitelabel = whitelabel_ins.id)
            if org_whitelabel_updated:
                return Response({'message': 'Host updated successfully'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Organization not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(str(e), status= status.HTTP_404_NOT_FOUND)
        
    def get(self, request):
        org_id = request.user.organization_id
        if org_id:
            whitelabel_inst = Organization.objects.filter(id = org_id).first()
        if whitelabel_inst:
            data = {"id": whitelabel_inst.whitelabel.id,
                    "host":whitelabel_inst.whitelabel.host}
            return Response(data)
        return Response({})

class CMSContentView(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try:
            path = request.data.get('path') # example -> /
            source =  request.headers.get('Origin') #host name
            parsed_url = urlparse(source)
            domain = parsed_url.netloc
            # ErrorLog.objects.create(module = 'CMSContentView',erros ={"domain":domain})
            if not path:
                return Response("Missing path")
            cms_content =  WhiteLabelPage.objects.filter(Q(whitelabel__host = domain) & Q(slug_url = path))
            if not cms_content:
                super_admin_ins = UserDetails.objects.filter(is_superuser=True).first()                                                                                                                              
                cms_content =  WhiteLabelPage.objects.filter(whitelabel__host = super_admin_ins.organization.whitelabel, slug_url = path)
            serializer = CMSContentViewSerializer(cms_content, many=True)
            if serializer.data:
                return Response({"static":True, "html":serializer.data[0].get("page_content") if serializer.data else None}, status = status.HTTP_200_OK)
            else:
                return Response({"static":False}, status = status.HTTP_200_OK)
        except Exception as e:
            return Response(str(e), status= status.HTTP_404_NOT_FOUND)
class FareManagementView(APIView):
    def get(self, request):
        page = request.query_params.get('page')
        page_size = request.query_params.get('page_size')
        fares = FareManagement.objects.all().order_by('priority','-created_at')
        serializer = FareManagementGetSerializer(fares, many=True)
        grouped_data = defaultdict(list)
        for item in serializer.data:
            brand_name = item["brand_name"]
            grouped_data[brand_name].extend(item["combinations"])
        result = [{"brand_name": brand, "combinations": combos} for brand, combos in grouped_data.items()]
        paginator = CustomPageNumberPagination(page_size=page_size)
        paginated_queryset = paginator.paginate_queryset(result, request)
        return Response(
            {
                "data": paginated_queryset,
                "total_pages": paginator.page.paginator.num_pages,
                "current_page": paginator.page.number,
                "next_page": paginator.get_next_link(),
                "prev_page": paginator.get_previous_link(),
                "total_data": len(result),
                "page_size": page_size
            },
            status=status.HTTP_200_OK
        )

    def post(self, request):
        try:
            combinations = request.data.get('combinations', [])
            deleted= request.data.get('deleted', None)
            if deleted:
                FareManagement.objects.filter(id__in=deleted).delete()
            if not combinations:
                return Response({"error": "combinations are required"}, status=status.HTTP_400_BAD_REQUEST)
            brand_name = request.data.get('brand_name')
            combinations = request.data.get('combinations', [])
            duplicate = False
            if not brand_name or not combinations:
                return Response({"error": "brand_name and combinations are required"}, status=status.HTTP_400_BAD_REQUEST)
            created_fares = []
            supplier_ids = {combo['supplier'] for combo in combinations}
            suppliers = {s.id: s for s in SupplierIntegration.objects.filter(id__in=supplier_ids)}
            for combo in combinations:
                combo_id= combo['id'] if 'id' in combo else None
                supplier_instance = suppliers.get(UUID(combo['supplier']))
                if not supplier_instance:
                    return Response({"error": f"Supplier {combo['supplier']} not found"}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    if not combo_id:
                        last_priority = FareManagement.objects.filter(brand_name=brand_name).aggregate(Max('priority'))['priority__max']
                        new_priority = (last_priority or 0) + 1
                        fare = FareManagement.objects.create(
                            supplier_id=supplier_instance,
                            supplier_fare_name=combo['name'],
                            brand_name=brand_name,
                            priority=new_priority
                        )
                        created_fares.append({
                            "id": fare.id,
                            "brand_name": fare.brand_name,
                            "supplier": str(fare.supplier_id.id),
                            "supplier_fare_name": fare.supplier_fare_name,
                            "priority": fare.priority
                        })
                    else:
                        fare = FareManagement.objects.get(
                            id=combo_id 
                        )
                        fare.supplier_id=supplier_instance
                        fare.supplier_fare_name=combo['name']
                        fare.brand_name = brand_name
                        fare.priority = combo['position']
                        fare.save()
                except Exception as e:
                    duplicate = True
            if duplicate:
                return Response({"duplicate":duplicate,
                                "data":created_fares if created_fares else None}, status=status.HTTP_201_CREATED)
            return Response({"duplicate":duplicate}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request,brand_name):
        if not brand_name:
            return Response("brand_name is required", status=status.HTTP_400_BAD_REQUEST)
        fare_counts,_ = FareManagement.objects.filter(brand_name=brand_name).delete()
        return Response("Fare deleted successfully" if fare_counts else "No records found", status=status.HTTP_200_OK)

        