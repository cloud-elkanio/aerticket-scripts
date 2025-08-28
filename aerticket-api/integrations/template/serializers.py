from .models import *
from rest_framework import serializers
from integrations.notification.models import Notifications


class NotificationTemplatesSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplates
        exclude = ('deleted_at','is_deleted','created_at','modified_at')
        

    
    
class LookUpNotificationKeysSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookUpNotificationKeys
        exclude = ('deleted_at','is_deleted','created_at','modified_at')
        
        


class NotificationSerializer(serializers.ModelSerializer):
    template = NotificationTemplatesSerializer()
    class Meta:
        model  = Notifications
        exclude = ('deleted_at','is_deleted','created_at','modified_at')
        
    def to_representation(self, instance):
        data = super().to_representation(instance)
        template = data.pop('template')
        data.update(template)
        data['event'] = instance.event.name
        data['event_id'] = instance.event.id
        data['recived_to'] = instance.template.recived_to
        data['recived_cc'] = instance.template.recived_cc    
        return data
    
