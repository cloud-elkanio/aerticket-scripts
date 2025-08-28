from django.db import models
from tools.db.models import  SoftDeleteModel
from integrations.suppliers.models import SupplierIntegration
# Create your models here.
from django.contrib.postgres.fields import ArrayField
from users.models import UserDetails, LookupAirline

# class LookUpAirline(SoftDeleteModel):
#     name = models.CharField(max_length=2000,null=True,blank=True)
#     code = models.CharField(max_length=2000,null=True,blank=True)
#     logo =  models.TextField()
    
    
    # class Meta:
    #     db_table = 'lookup_airline'
        
    
    # def __str__(self) -> str:
    #     return str(f"airport name {self.name} code:{self.code}")


class AirlineDeals(SoftDeleteModel):
    deal_type_choice = (
        ("DOM","DOM"),
        ("INT","INT")
    )
    airline = models.ForeignKey(LookupAirline,on_delete=models.CASCADE, null=True)
    supplier = models.ForeignKey(SupplierIntegration, on_delete=models.CASCADE) #unique
    source = ArrayField(
        models.CharField(max_length=200),  
        null=True,
        blank=True
    )
    destination = ArrayField(
        models.CharField(max_length=200), 
        null=True,
        blank=True
    )
    sector=models.BooleanField()
    cabin = models.TextField(null = True,blank=True) #  unique
    class_included = models.TextField(null=True,blank=True) # coma seperated value
    class_excluded = models.TextField(null=True,blank=True)
    deal_type = models.CharField(max_length=2000,choices=deal_type_choice) # unique
    iata_commission = models.FloatField(default=0.0,blank=True, null=True)
    basic = models.FloatField(default=0.0, null=True,blank=True)
    basic_yq = models.FloatField(default=0.0,null=True,blank=True)
    basic_yr =models.FloatField(default=0.0,null=True,blank=True)
    valid_till = models.BigIntegerField(null=True) #should alwas be a future date
    country_applicability=models.BooleanField(null=True,blank=True)
    source_country_code=ArrayField(
        models.CharField(max_length=200), 
        null=True,
        blank=True
    )
    destination_country_code=ArrayField(
        models.CharField(max_length=200), 
        null=True,
        blank=True
    )
    # rules = models.TextField()
    soto = models.BooleanField()
    basic_after_valid_date = models.FloatField(null=True,blank=True)
    yq_after_valid_date = models.FloatField(null=True,blank=True)
    yr_after_valid_date = models.FloatField(null=True,blank=True)
    discount_percentage = models.FloatField(default=0.0)
    code_sharing=models.BooleanField(null=True,blank=True)
    status = models.BooleanField(default=True)
    modified_by = models.ForeignKey(UserDetails,on_delete=models.CASCADE)
    
    
    class meta:
        db_table = 'airline_deals'
        ordering = ['-created_at']

class SupplierDealManagement(SoftDeleteModel):
    deal_type_choice = (
        ("DOM","DOM"),
        ("INT","INT")
    )
    airline = models.ForeignKey(LookupAirline,on_delete=models.CASCADE, null=True)
    supplier = models.ForeignKey(SupplierIntegration, on_delete=models.CASCADE) #unique
    source = ArrayField(
        models.CharField(max_length=200),  
        null=True,
        blank=True
    )
    destination = ArrayField(
        models.CharField(max_length=200), 
        null=True,
        blank=True
    )
    sector=models.BooleanField()
    cabin = models.TextField() #  unique
    class_included = models.TextField(null=True,blank=True) # coma seperated value
    class_excluded = models.TextField(null=True,blank=True)
    deal_type = models.CharField(max_length=2000,choices=deal_type_choice) # unique
    iata_commission = models.FloatField(default=0.0,blank=True, null=True)
    basic = models.FloatField(default=0.0, null=True,blank=True)
    basic_yq = models.FloatField(default=0.0,null=True,blank=True)
    basic_yr =models.FloatField(default=0.0,null=True,blank=True)
    valid_till = models.BigIntegerField(null=True) #should alwas be a future date
    country_applicability=models.BooleanField(null=True,blank=True)
    source_country_code=ArrayField(
        models.CharField(max_length=200), 
        null=True,
        blank=True
    )
    destination_country_code=ArrayField(
        models.CharField(max_length=200), 
        null=True,
        blank=True
    )
    # rules = models.TextField()
    soto = models.BooleanField()
    basic_after_valid_date = models.FloatField(null=True,blank=True)
    yq_after_valid_date = models.FloatField(null=True,blank=True)
    yr_after_valid_date = models.FloatField(null=True,blank=True)
    discount_percentage = models.FloatField(default=0.0)
    code_sharing=models.BooleanField(null=True,blank=True)
    status = models.BooleanField(default=True)
    modified_by = models.ForeignKey(UserDetails,on_delete=models.CASCADE)
    gst_inclusive = models.BooleanField()
    service_charge = models.FloatField(default=0.0,null=True,blank=True)
    
    class meta:
        db_table = 'supplier_deal_management'
        ordering = ['-created_at']
    
    
    # def save(self, *args, **kwargs):
    #     now = int(time.time())
    #     if not self.created_at:
    #         self.created_at = now
    #     self.modified_at = now
    #     super(SoftDeleteModel, self).save(*args, **kwargs)
    
    
class FlightSupplierAvailability(SoftDeleteModel):
    supplier = models.ForeignKey(SupplierIntegration, on_delete=models.CASCADE)
    heading = models.CharField(max_length=600, null=True, blank=True)
    sector_from = ArrayField(models.CharField(max_length=200),null=True,blank=True)
    sector_to =  ArrayField(models.CharField(max_length=200),null=True,blank=True)
    country_from =   ArrayField(models.CharField(max_length=200),null=True,blank=True)
    country_to =  ArrayField(models.CharField(max_length=200),null=True,blank=True)
    airline =  ArrayField(models.CharField(max_length=200),null=True,blank=True)
    dom = models.BooleanField()
    int = models.BooleanField()
    round_int = models.BooleanField()
    lcc = models.BooleanField()
    class meta:
        db_table = 'flight_supplier_availability'
        ordering = ['-created_at']

class FlightSupplierFilters(SoftDeleteModel):
    supplier = models.ForeignKey(SupplierIntegration, on_delete=models.CASCADE)
    heading = models.CharField(max_length=600, null=True, blank=True)
    sector_from = ArrayField(models.CharField(max_length=200),null=True,blank=True)
    sector_to =  ArrayField(models.CharField(max_length=200),null=True,blank=True)
    country_from =   ArrayField(models.CharField(max_length=200),null=True,blank=True)
    country_to =  ArrayField(models.CharField(max_length=200),null=True,blank=True)
    airline =  ArrayField(models.CharField(max_length=200),null=True,blank=True)
    dom = models.BooleanField(default = True)
    int = models.BooleanField(default = True)
    round_int = models.BooleanField(default = True)
    lcc = models.BooleanField(default = True)
    gds = models.BooleanField(default = True)
    regular_fare = models.BooleanField(default = True)
    student_fare = models.BooleanField(default = True)
    senior_citizen_fare = models.BooleanField(default = True)
    class Meta:
        db_table = 'flight_supplier_filters'
        ordering = ['-created_at']
