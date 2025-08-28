from django.db import models
from tools.db.models import  SoftDeleteModel  # our own db models implementing soft delete
from django.contrib.postgres.fields import ArrayField
from users.models import Country,Organization

class LookupSupplierIntegration(SoftDeleteModel):


    INTEGRATION_TYPE_CHOICES = (
        ('Flights','Flights'),
        ('Hotels','Hotels'),
        ('Rail','Rail'),
        ('Payment','Payment'),
        ('Transfers','Transfers'),
        ('Bus','Bus'),
        ('Insurance','Insurance'),
    )
    name = models.CharField(max_length=600)
    integration_type = models.CharField(max_length=500, choices= INTEGRATION_TYPE_CHOICES)
    keys = ArrayField(models.CharField(max_length=600), blank=True, default=list)
    icon_url = models.CharField(max_length=600)
    def __str__(self):
        return str(self.name)
    class Meta:
        db_table = 'lookup_supplier_integration'
        ordering = ['-created_at']

class SupplierIntegration(SoftDeleteModel):
    INTEGRATION_CHOICES = (
        ('Flights','Flights'),
        ('Hotels','Hotels'),
        ('Rail','Rail'),
        ('Payment','Payment'),
        ('Transfers','Transfers'),
        ('Bus','Bus'),
        ('Insurance','Insurance'),
    )

    country = models.ForeignKey(Country, on_delete = models.CASCADE)
    name = models.CharField(max_length = 600)
    data = models.JSONField()
    icon_url = models.CharField(max_length = 1000)
    integration_type =  models.CharField(max_length = 500,choices = INTEGRATION_CHOICES)
    lookup_supplier  = models.ForeignKey(LookupSupplierIntegration, on_delete=models.CASCADE,  blank=True)
    is_active = models.BooleanField(default = True) 
    token = models.CharField(max_length = 2000,null = True, blank = True)
    expired_at = models.BigIntegerField(null=True, blank = True,default = 0)
    is_init = models.BooleanField(default = False)

    def __str__(self):
        return str(self.name)
    class Meta:
        db_table = 'supplier_integration'
        ordering = ['-created_at']
        


class OrganizationSupplierIntegeration(SoftDeleteModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    supplier_integeration =  models.ForeignKey(SupplierIntegration, on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=True) 
    def __str__(self):
        return str(self.organization.organization_name)
    class Meta:
        db_table = 'supplier_organization_integration'
        ordering = ['-created_at']