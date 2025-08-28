from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from users.models import UserDetails
from .models import *
from django.contrib.auth.hashers import check_password
from django.utils import timezone
import random
from datetime import timedelta
from django.contrib.auth import login
from rest_framework import authentication, permissions
from django.contrib.auth.models import User
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from tools.custome_jwt_token.jwt_token import get_jwt_token
from django.contrib.auth.hashers import make_password
from rest_framework import viewsets
from .serializers import *
from PyGeneratePassword import PasswordGenerate
import environ
from django.db.models import Q,Count, Max
env = environ.Env()
environ.Env.read_env
from phonenumbers import NumberParseException
import phonenumbers
from django.shortcuts import get_object_or_404

from rest_framework.pagination import PageNumberPagination
import logging
logger = logging.getLogger(__name__)
from tools.time_helper import time_converter
# Create your views here.
# This class defines an API view for retrieving integration notification types using JWT
# authentication.
class IntegrationNotifcationTypes(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self,request):
        notification_obj = LookUpIntegerationNotification.INTEGERATION_TYPE_CHOICES
        # serializer = IntegerationNotificationTypesSerializer(notification_obj,many=True)
        data = [k for k,v in notification_obj]
        return Response({"data":data},status=status.HTTP_200_OK)
    

# showing options based on the IntegrationNotifcationTypes selected

class IntegerationMethodsList(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self,request):
        selected_integeration_method = request.GET.get("integeration_methods",None)
        
        if not selected_integeration_method: #test case 1 = True
            return Response({"message":"integeration methods cannot be null"}, status=status.HTTP_400_BAD_REQUEST)
        
        obj = LookUpIntegerationNotification.objects.filter(integeration_type=selected_integeration_method).order_by('-modified_at')
        serializer = LookUpIntegerationNotificationMethodsSerializer(obj, many=True)
        
        return Response({"data":serializer.data},status=status.HTTP_200_OK)
    

    
    
    
    

class IntegerationNotificationList(APIView):
    def get(self,request):
        required_fields = ["integeration_methods", "country_id"]
        missing_fields = [fields for fields in required_fields if fields not in request.GET]
        
        if missing_fields:
            return Response({"message":f"these fields are required -> {', '.join(missing_fields)} <- in query params"})
        
        selected_integeration_method = request.GET.get("integeration_methods",None)
        country_id = request.GET.get("country_id",None)
        
        
        
        obj = NotificationIntegeration.objects.filter(Q(country_id=country_id)&Q(integeration_type__icontains=selected_integeration_method))
        serializer = NotificationIntegerationSerializer(obj,many=True)
        
        return Response({"data":serializer.data},status=status.HTTP_200_OK)
    
    
from users.permission import HasAPIAccess
class IntegerationNotificationUpdate(APIView):
    permission_classes = [HasAPIAccess]
    def get(self,request):
        integeration_id = request.GET.get('id')

        if not integeration_id:
            return Response({"message":"integeration_id is required in query params"})
        
        try:
            obj = NotificationIntegeration.objects.get(id=integeration_id)
        except NotificationIntegeration.DoesNotExist:
            return Response({"message": f"NotificationIntegration with id {integeration_id} does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        
        default_key = obj.look_up.keys
        obj_keys = obj.data
        [obj.data.update({k:""}) for k in default_key if k not in obj_keys.keys()]
        
        data = {
            "data":obj.data
        }
        
        return Response(data,status=status.HTTP_200_OK)
    
    def put(self,request):
        integeration_id = request.data.get('id')
        is_active = request.data.get('is_active')
        data = request.data.get('data')
        if not integeration_id or not data:
            return Response({"message":"id is required in query params"},status=status.HTTP_400_BAD_REQUEST)

        
        if not isinstance(request.data.get('data'), dict):
            return Response({"message":"key data is in wrong format"},status=status.HTTP_400_BAD_REQUEST)
        
        obj = NotificationIntegeration.objects.get(id=integeration_id)
        obj.data = data
        obj.is_active = is_active
        obj.save()
        return Response({"message":"data saved successfully"},status=status.HTTP_200_OK)
        
        
    def delete(self,request,id):
        integeration_id = id
        obj = NotificationIntegeration.objects.get(id=integeration_id)
        delete_obj_name = obj.name
        obj.hard_delete()
        return Response({"message":f"Integeration {delete_obj_name} is deleted successfully"},status=status.HTTP_200_OK)
        

class IntegerationNotificationcreate(APIView):
    
    def post(self,request):
        required_fields = ['country_id','data','integeration_id']
        missing_fields = [data for data in required_fields if data not in request.data ]
        
        if missing_fields:
            return Response({"message":f"these fields are required {', '.join(missing_fields)}"},status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(request.data.get('data'), dict):
            return Response({"message":"key data is in wrong format"},status=status.HTTP_400_BAD_REQUEST)
        look_obj = LookUpIntegerationNotification.objects.get(id=request.data['integeration_id'])
        if self.name_already_exist(look_obj.name, request.data['country_id'], look_obj.integeration_type):
            return Response({"message":f"{look_obj.name} Integeration already exists !"},status=status.HTTP_409_CONFLICT)
            
        try:
            NotificationIntegeration.objects.create(country_id = request.data['country_id'], 
                                                    name=look_obj.name, data=request.data['data'],
                                                    icon_url=look_obj.icon_url,
                                                    integeration_type=look_obj.integeration_type,
                                                    look_up=look_obj)
        except Exception as e:
            return Response({"message":f"{e}"},status=status.HTTP_400_BAD_REQUEST)
        
        return Response({"message":f"Integeration ss{look_obj.name} created successfully"},status=status.HTTP_200_OK)
    
    
    def name_already_exist(self,name,country_id,integration_method):
        return NotificationIntegeration.objects.filter(
            Q(name=name) & Q(country_id=country_id) & Q(integeration_type=integration_method)
            ).exists()


class IntegerationDefaultValue(APIView):
    def get(self,request):
        integeration_id = request.GET.get('integeration_id',None)
        if not integeration_id:
            return Response({"message":"key integeration_id is required in query param"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            obj = LookUpIntegerationNotification.objects.get(id=integeration_id)
        except LookUpIntegerationNotification.DoesNotExist:
            return Response({"error":"wrong integeration_id is passed"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error":f"error{e}"},status=status.HTTP_400_BAD_REQUEST)
        
        serializer = LookUpIntegerationNotificationMethodsSerializer(obj)
        return Response({"data":serializer.data},status=status.HTTP_200_OK)
    
    
from users.models import Organization
class TempMigrate(APIView):
    authentication_classes = []
    permission_classes = []
    def get(self,request):
        UserDetails.objects.create_superuser(
                username='superadmin',
                email='admin@bta.com',
                password='8665@atb'  
            )
        return Response({"message":"data"})