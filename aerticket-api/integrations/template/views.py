from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
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
from integrations.notification.models import Notifications
from rest_framework.pagination import PageNumberPagination
import logging
logger = logging.getLogger(__name__)
from tools.time_helper import time_converter



class NotificationType(APIView):
    def get(self,request):
        data = getattr(NotificationTemplates, "NOTIFICATON_INTEGERATION_TYPE")
        data = [v for k,v in data]
        return Response({"data":data},status=status.HTTP_200_OK)
    
    
class NotificationTemplateViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = []
    queryset = Notifications.objects.all()
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
      
        if self.request.method=="GET":

            template_type = self.request.GET.get('template_type')
            search_query = self.request.GET.get('search_query',None)
            return Notifications.objects.filter(Q(template__integeration_type=template_type) & (Q(template__name__icontains=search_query)| Q(template__name__icontains=search_query)))
        else:
            return super().get_queryset()
        
        
    def create(self, request, *args, **kwargs):
        events = request.data.get('event_id')
        integeration_type = request.data.get('event_id')
        organization_id = request.user.organization_id
        if not events:
            return Response({"message":"event id is required in payload"},status=status.HTTP_409_CONFLICT)
        
        if not organization_id:
            return Response({"message":"organization id is required in payload"},status=status.HTTP_409_CONFLICT)
        
        notification_instance = Notifications.objects.filter(Q(event_id = events) & Q(template__is_active = True) & Q(is_deleted=False) & Q(template__integeration_type=integeration_type) & Q(organization_id=organization_id))
  
        if notification_instance.exists():
            return Response({"message":f"the event -> {notification_instance.first().event.name} <- is already assigned. the name of the event is -> {notification_instance.first().template.name} <- please delete or deactivate to add new."},status=status.HTTP_409_CONFLICT)
        
        serializer = NotificationTemplatesSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            data = serializer.save()
            Notifications.objects.create(event_id=events,template_id=str(data.id),organization_id= organization_id)
     
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    

    
    
    
    def update(self, request, *args, **kwargs):
        partial = True if request.method == "PATCH" else False
        instance = NotificationTemplates.objects.get(id=kwargs['pk'])
        serializer = NotificationTemplatesSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({"message":"successfully updated"}, status=status.HTTP_200_OK)

    def perform_update(self, serializer):
        serializer.save()

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    
    
    def destroy(self, request, *args, **kwargs):
        instance = Notifications.objects.get(template__id=kwargs['pk'])
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

        
        
    


class NotificationKeys(APIView):
    def get(self,request):
        obj = LookUpNotificationKeys.objects.filter(type="memory")
        serializer = LookUpNotificationKeysSerializer(obj, many=True)
        return Response({"data":serializer.data}, status=status.HTTP_200_OK)
    
    
    
class NotificationEvents(APIView):
    def get(self,request):
        obj = LookUpNotificationKeys.objects.filter(type="event")
        serializer = LookUpNotificationKeysSerializer(obj, many=True)
        return Response({"data":serializer.data}, status=status.HTTP_200_OK)
    
    

class NotificationVariables(APIView):
    def get(self,request):
        obj = LookUpNotificationKeys.objects.filter(type="memory")
        serializer = LookUpNotificationKeysSerializer(obj, many=True)
        return Response({"data":serializer.data}, status=status.HTTP_200_OK)
    
    

