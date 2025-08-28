from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from tools.db.models import  SoftDeleteModel  # our own db models implementing soft delete
from django.utils import timezone
import time
from django.contrib.postgres.fields import ArrayField
from users.models import Country, Organization
from integrations.template.models import LookUpNotificationKeys,NotificationTemplates
# Create your models here.
class LookUpIntegerationNotification(SoftDeleteModel):
    
    INTEGERATION_TYPE_CHOICES = (("email","email"),
                                 ("sms","sms"),
                                 ("whatsapp","whatsapp"))
    name = models.CharField(max_length=2000)
    integeration_type = models.CharField(max_length=200, choices=INTEGERATION_TYPE_CHOICES)
    keys = ArrayField(models.CharField(max_length=600), blank=True, default=list)
    icon_url = models.CharField(max_length=600)
    
    
    class Meta:
        db_table = 'lookup_integeration_notification'
        ordering = ['-created_at']
    

class NotificationIntegeration(SoftDeleteModel):
    INTEGERATION_TYPE_CHOICES = (("email","email"),
                                 ("sms","sms"),
                                 ("whatsapp","whatsapp"))
    country = models.ForeignKey(Country,on_delete=models.CASCADE,related_name='notification_country')
    name = models.CharField(max_length=200)
    data = models.JSONField()
    icon_url = models.CharField(max_length=600)
    integeration_type = models.CharField(max_length=200, choices=INTEGERATION_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    look_up = models.ForeignKey(LookUpIntegerationNotification, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'notification_integeration'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{str(self.id)}-----{self.name}"
        
        

class Notifications(SoftDeleteModel):
    # name = models.CharField
    event = models.ForeignKey(LookUpNotificationKeys, on_delete=models.CASCADE, null=True)
    template = models.ForeignKey(NotificationTemplates, on_delete = models.CASCADE,null=True)
    organization = models.ForeignKey(Organization, on_delete = models.CASCADE,null=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self):
        return str(self.event.name)
