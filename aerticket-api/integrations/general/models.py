from django.db import models
from tools.db.models import  SoftDeleteModel
from django.contrib.postgres.fields import ArrayField
from users.models import Country
# Create your models here.

class LookupIntegration(SoftDeleteModel):
    name = models.CharField(max_length=600, unique=True)
    keys = ArrayField(models.CharField(max_length=600), blank=True, default=list)
    icon_url = models.CharField(max_length=600)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'lookup_integration'
        ordering = ['-created_at']

class Integration(SoftDeleteModel):

    name = models.CharField(max_length=1000)
    icon_url = models.CharField(max_length=600)
    data = models.JSONField()
    lookup_integration = models.ForeignKey(LookupIntegration, on_delete=models.CASCADE,  blank=True)
    is_active = models.BooleanField(default=True) 
    country = models.ForeignKey(Country, on_delete=models.CASCADE,  blank=True, null=True)

    def __str__(self):
        return self.name
    class Meta:
        db_table = 'integration'
        ordering = ['-created_at']