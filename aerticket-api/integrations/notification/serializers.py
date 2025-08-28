
from .models import *
from .models import *
from rest_framework import serializers
from tools.time_helper import time_converter

class LookUpIntegerationNotificationMethodsSerializer(serializers.ModelSerializer):
        class Meta:
            model = LookUpIntegerationNotification
            exclude = ('deleted_at','is_deleted','created_at','modified_at')
            
            

class NotificationIntegerationSerializer(serializers.ModelSerializer):
        class Meta:
            model = NotificationIntegeration
            exclude = ('deleted_at','is_deleted','created_at','modified_at')
            