from django.db import models
from tools.db.models import  SoftDeleteModel
from django.contrib.postgres.fields import ArrayField

# Create your models here.

class NotificationTemplates(SoftDeleteModel):
    NOTIFICATON_INTEGERATION_TYPE = (
        ("email","email"),
        ("sms","sms"),
        ("whatsapp","whatsapp")
    )
    name = models.CharField(max_length=200)
    integeration_type =  models.CharField(max_length=200) 
    heading = models.CharField(max_length=200) 
    body = models.TextField()
    is_active =models.BooleanField(default=True)
    recived_to = ArrayField(models.CharField(max_length=600), blank=True, default=list)
    recived_cc = ArrayField(models.CharField(max_length=600), blank=True, default=list)
    
    
    def __str__(self):
        return str(self.name)

    
    
    

        
class LookUpNotificationKeys(SoftDeleteModel):
    NOTIFICATION_TYPE = (
        ("memory","memory"),
        ("event","event")
    )
    name = models.CharField(max_length=2000, unique=True)
    type = models.CharField(choices=NOTIFICATION_TYPE, max_length=200)
    
    class Meta:
        db_table = 'lookup_notification_keys'
        verbose_name = 'lookup_notification_keys'
        verbose_name_plural = 'lookup_notification_keys'
        ordering = ['-created_at']

    def __str__(self):
        return str(self.name)