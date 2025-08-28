from django.db import models
from django.contrib.postgres.fields import ArrayField
# Create your models here.
from django.contrib.auth.models import AbstractUser

from django.contrib.auth.models import AbstractUser

from django.db import models
import uuid

from datetime import datetime, timedelta
from django.utils import timezone
import uuid
import time

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class SoftDeleteModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    is_deleted = models.BooleanField(default=False, null=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.BigIntegerField(null=True, editable=False)
    modified_at = models.BigIntegerField(null=True, editable=False)

    objects = SoftDeleteManager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        """This method won't delete, rather it will set is_deleted field to True"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def hard_delete(self, *args, **kwargs):
        """This is the actual delete method of Django"""
        super(SoftDeleteModel, self).delete(*args, **kwargs)

    def restore(self, *args, **kwargs):
        self.is_deleted = False
        self.deleted_at = None
        self.save()

    def save(self, *args, **kwargs):
        now = int(time.time())
        if not self.created_at:
            self.created_at = now
        self.modified_at = now
        super(SoftDeleteModel, self).save(*args, **kwargs)


class LookupCountry(SoftDeleteModel):
    country_name = models.CharField(max_length=200)
    country_code = models.CharField(max_length=300)
    is_active = models.BooleanField(default=True)
    calling_code = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        db_table = 'lookup_country'
        managed =False
        
        
    def __str__(self) -> str:
        return self.country_name
    
class LookupIntegration(SoftDeleteModel):
    name = models.CharField(max_length=600, unique=True)
    keys = ArrayField(models.CharField(max_length=600), blank=True, default=list)
    icon_url = models.CharField(max_length=600)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = 'lookup_integration'
        ordering = ['-created_at']

class LookupAirline(SoftDeleteModel):
    name = models.CharField(max_length=500, null = True)
    code = models.CharField(max_length=500 , null = True)
    def __str__(self):
        return str(self.name)
    class Meta:
        db_table = 'lookup_airline'
        ordering = ['-created_at']
        managed = False

class LookupAirports(SoftDeleteModel):
    name = models.CharField(max_length=300, null = True)
    code = models.CharField(max_length=300 , null = True)
    city = models.CharField(max_length=300 , null = True)
    country = models.ForeignKey(LookupCountry, on_delete=models.CASCADE, null = True)
    index = models.IntegerField(null = True)
    common = models.CharField(max_length=400 , null=True)
    latitude = models.FloatField(null = True)
    longitude = models.FloatField(null = True)
    nearest = ArrayField(models.CharField(max_length=2000), null= True)
    def __str__(self):
        return str(self.name)
    class Meta:
        db_table = 'lookup_airports'
        ordering = ['-created_at']
        managed = False
class LookupCreditCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    card_type = models.CharField(max_length=50)  # No unique constraint here
    card_number = models.CharField(max_length=50, unique=True)
    internal_id = models.CharField(max_length=50,null=True, blank=True)

    class Meta:
        db_table = 'lookup_credit_card'
        verbose_name = 'Credit Card'
        verbose_name_plural = 'Credit Cards'
        ordering = ['card_type']
        managed = False

    def __str__(self):
        masked_part = "X" * (len(self.card_number) - 4)  # Create the masked part dynamically
        grouped_masked_part = " ".join(masked_part[i:i+4] for i in range(0, len(masked_part), 4))  # Group in blocks of 4
        return f"{self.card_type} - {grouped_masked_part} {self.card_number[-4:]}"  # Append the last 4 digits



class LookupAirports(SoftDeleteModel):
    name = models.CharField(max_length=300, null = True)
    code = models.CharField(max_length=300 , null = True)
    city = models.CharField(max_length=300 , null = True)
    country = models.ForeignKey(LookupCountry, on_delete=models.CASCADE, null = True)
    index = models.IntegerField(null = True)
    common = models.CharField(max_length=400 , null=True)
    latitude = models.FloatField(null = True)
    longitude = models.FloatField(null = True)
    nearest = ArrayField(models.CharField(max_length=2000), null= True)
    timezone = models.CharField(max_length=60 , null = True)

    class Meta:
        db_table = 'lookup_airports'
        managed =False

class LookupOrganizationTypes(SoftDeleteModel):
    ORGANIZATION_CHOICES = (
        ("master","master"),
        ("agency","agency"),
        ("distributor","distributor"),
        ("enterprises","enterprises"),
        ("out_api","out_api"),
        ("supplier","supplier")
    )
    name = models.CharField(max_length=500, choices=ORGANIZATION_CHOICES)
    def __str__(self):
        return str(self.name)
    class Meta:
        db_table = 'lookup_organization_types'
        managed = False


class Country(SoftDeleteModel):
    currency_name =  models.CharField(max_length=200)
    currency_code = models.CharField(max_length=200)
    currency_symbol = models.CharField(max_length=200)
    inr_conversion_rate = models.DecimalField(default = 0.0,max_digits=100, decimal_places=4)
    is_active = models.BooleanField(default=False)
    lookup = models.ForeignKey(LookupCountry, on_delete=models.CASCADE)
    class Meta:
        managed = False

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
        managed = False

class Organization(SoftDeleteModel):
    STATUS_CHOICES = (
        ("active","active"),
        ("inactive", "inactive"),
        ("pending","pending"),
        
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    organization_name = models.CharField(max_length=2000)
    organization_type = models.ForeignKey(LookupOrganizationTypes, on_delete = models.CASCADE)
    is_iata_or_arc = models.BooleanField()
    iata_or_arc_code =models.CharField(max_length=2000, null=True, blank=True)
    address = models.TextField()
    state = models.CharField(max_length=2000, null=True, blank=True)
    organization_country = models.ForeignKey(Country, on_delete=models.DO_NOTHING,null=True, blank=True)
    organization_zipcode = models.IntegerField()
    organization_pan_number = models.CharField(max_length=2000, null=True, blank=True)
    organization_gst_number = models.CharField(max_length=2000, null=True, blank=True)
    organization_tax_number = models.CharField(max_length=2000, null=True, blank=True)
    organization_currency = models.CharField(max_length=200)
    easy_link_account_code = models.CharField(max_length=2000, null=True, blank=True)
    easy_link_account_name = models.CharField(max_length=2000, null=True, blank=True)
    easy_link_billing_account = models.ForeignKey(Integration, on_delete=models.CASCADE, blank=True, null=True)

    status = models.CharField(max_length=2000, null=True, blank=True, choices = STATUS_CHOICES, default="pending")
    support_email = models.CharField(max_length=2000, null=True, blank=True)
    support_phone = models.CharField(max_length=2000, null=True, blank=True)
    virtual_ac_no = models.CharField(max_length=2000, null=True, blank=True)
    profile_picture = models.ImageField(upload_to = 'btob/gallery', null=True, blank=True)
    easy_link_billing_code = models.CharField(max_length=2000, null=True, blank=True)

    class Meta:
        db_table = 'organization'
        managed=False

class LookupRoles(SoftDeleteModel):
    ROLE_CHOICES = (
        ("super_admin","super_admin"),
        ("admin","admin"),
        ("operations","operations"),
        ("finance","finance"),
        ("sales","sales"),
        ("agency_owner","agency_owner"),
        ("agency_staff","agency_staff"),
        ("distributor_owner","distributor_owner"),
        ("distributor_staff","distributor_staff"),
        ("distributor_agent","distributor_agent"),
        ("out_api","out_api"),
        ("enterprise_owner","enterprise_owner"),
        ("supplier","supplier")
    )
    
    name = models.CharField(max_length=500,choices=ROLE_CHOICES)
    lookup_organization_type = models.ForeignKey(LookupOrganizationTypes,on_delete=models.CASCADE)
    level=models.IntegerField(null=True)
    
    class Meta:
        db_table = 'lookup_roles'
        managed =False
    
class LookupSupplierIntegration(SoftDeleteModel):


    INTEGRATION_TYPE_CHOICES = (
        ('Flights','Flights'),
        ('Hotels','Hotels'),
        ('Rail','Rail'),
        ('Payment','Payment')
    )
    name = models.CharField(max_length=600)
    integration_type = models.CharField(max_length=500, choices= INTEGRATION_TYPE_CHOICES)
    keys = ArrayField(models.CharField(max_length=600), blank=True, default=list)
    icon_url = models.CharField(max_length=600)

    class Meta:
        db_table = 'lookup_supplier_integration'
        managed=False



class SupplierIntegration(SoftDeleteModel):
    INTEGRATION_CHOICES = (
        ('Flights','Flights'),
        ('Hotels','Hotels'),
        ('Rail','Rail'),
        ('Payment','Payment'),
        ('Transfers','Transfers')
    )

    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    name = models.CharField(max_length=600)
    data = models.JSONField()
    icon_url = models.CharField(max_length=1000)
    integration_type =  models.CharField(max_length=500,choices=INTEGRATION_CHOICES)
    lookup_supplier  = models.ForeignKey(LookupSupplierIntegration, on_delete=models.CASCADE,  blank=True)
    is_active = models.BooleanField(default=True) 
    token = models.CharField(max_length=600,null=True, blank=True)
    expired_at = models.BigIntegerField(null=True, blank=True,default=0)

    class Meta:
        db_table = 'supplier_integration'
        managed=False

    def update_token(self, new_token):
        self.token = new_token
        now = datetime.now()
        end_of_day = datetime(
            year=now.year, 
            month=now.month, 
            day=now.day, 
            hour=23, 
            minute=59, 
            second=59
        )
        self.expired_at = int(end_of_day.timestamp())
        self.save()
        

class OrganizationSupplierIntegeration(SoftDeleteModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    supplier_integeration =  models.ForeignKey(SupplierIntegration, on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=True) 
    class Meta:
        db_table = 'supplier_organization_integration'

        managed=False



class UserGroup(SoftDeleteModel):
    name = models.CharField(max_length=2000)
    role = models.ForeignKey(LookupRoles, on_delete=models.CASCADE,null=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    permission = models.ForeignKey("users.Permission", on_delete=models.CASCADE)
    is_visible= models.BooleanField(default=False)
    
    class Meta:
        db_table = 'user_group'
        ordering = ['-created_at']
        managed = False

    def __str__(self):
        return str(self.name)

#     phone_code=models.CharField(max_length=100,null=True, blank=True)
#     phone_number = models.CharField(max_length=100,null=True, blank=True)
#     is_email_verified = models.BooleanField(default=False)
#     is_phone_verified = models.BooleanField(default=False)
#     address = models.TextField(null=True, blank=True)
#     is_active = models.BooleanField(default=True)
#     is_first_time = models.BooleanField(default=True)
#     base_country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True)
#     # state = models.CharField(max_length=300,null=True, blank=True)
#     zip_code = models.CharField(max_length=100, null=True, blank=True)

#     organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
#     agency_name =  models.CharField(max_length=500, null=True, blank=True)
#     created_by = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True)
#     user_external_id = models.CharField(max_length=150, null=True, blank=True)
#     class Meta:
#         db_table = 'user_details'
#         managed=False
        
#     def __str__(self):
#         return str(self.first_name)


class UserDetails(AbstractUser, SoftDeleteModel):
    phone_code=models.CharField(max_length=100,null=True, blank=True)
    phone_number = models.CharField(max_length=100,null=True, blank=True)
    role = models.ForeignKey(LookupRoles, on_delete=models.CASCADE, null=True)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    address = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_first_time = models.BooleanField(default=True)
    base_country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True)
    # state = models.CharField(max_length=300,null=True, blank=True)
    zip_code = models.IntegerField(null=True, blank=True)
    user_group = models.ForeignKey(UserGroup,on_delete=models.CASCADE,null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True,related_name="users_details")
    agency_name =  models.CharField(max_length=500, null=True, blank=True)
    created_by = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True)
    is_client_proxy = models.BooleanField(default=False)
    user_external_id = models.CharField(max_length=150, null=True, blank=True)
    last_login_ip = models.CharField(max_length=150,null=True, blank=True)
    # markup = models.IntegerField(null=True, blank=True)
    dom_markup = models.IntegerField(null=True, blank=True)
    int_markup = models.IntegerField(null=True, blank=True)


    class Meta:
        db_table = 'user_details'
        ordering = ['-created_at']
        managed = False
        
        
    def __str__(self):
        return str(self.first_name)
    
    def save(self, *args, **kwargs):
        now = int(time.time())
        if not self.id:
            if not self.user.organization:
                self.user.user_internal_id = f"NOR-{''.join(str(now).split('.')[0])}"
            else:
                self.user_internal_id = f"{''.join([i[0].title() for i in self.organization.organization_name.split()])}-{''.join(str(now).split('.')[0])}"
        self.modified_at = now
        super(SoftDeleteModel, self).save(*args, **kwargs)
        

class CountryTax(SoftDeleteModel):
    country_id = models.ForeignKey(Country, on_delete=models.CASCADE, null = True)
    tax = models.FloatField(default= 0)
    tds = models.FloatField(default= 0)

    class Meta:
        db_table = 'country_tax'  

class OrganizationFareAdjustment(SoftDeleteModel):
    module_choices=( 
        ('flight','flight'),
        ('hotel','hotel'),
        ('holiday','holiday'),
        ('visa','visa'),

    )
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    cashback = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    parting_percentage = models.FloatField(default=100.0)
    markup = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    issued_by = models.ForeignKey(UserDetails, on_delete=models.CASCADE, null=True, blank=True)
    module = models.CharField(max_length=200, choices=module_choices, default="flight")
    cancellation_charges = models.FloatField(default=0.0)

    class Meta:
        db_table = 'organization_fare_adjustment'
        managed=False

class DistributorAgentFareAdjustment(SoftDeleteModel):

    module_choices = (
        ("flight", "flight"),
        ("hotel", "hotel"),
        ("holiday", "holiday"),
        ("visa", "visa"),
    )

    user = models.ForeignKey(
        UserDetails, on_delete=models.CASCADE, null=True, blank=True
    )
    cashback = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    markup = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    parting_percentage = models.FloatField(default=100.0)
    module = models.CharField(max_length=200, choices=module_choices, default="flight")
    cancellation_charges = models.FloatField(default=0.0)
    available_balance = models.FloatField(default=0.0)
    credit_limit = models.FloatField(default=0.0)

    class Meta:
        managed = False
        db_table = "distributor_agent_fare_adjustment"
        ordering = ["-created_at"]



class DistributorAgentTransaction(SoftDeleteModel):
    module_choices = (
        ("flight", "flight"),
        ("hotel", "hotel"),
        ("holiday", "holiday"),
        ("visa", "visa"),
    )
    transaction_type_choices = (("credit", "credit"), ("debit", "debit"))

    booking_type_choices = (
        ("new_ticketing", "new_ticketing"),
        ("cancellation", "cancellation"),
        ("online_payment", "online_payment"),
    )

    user = models.ForeignKey(
        UserDetails, on_delete=models.CASCADE, null=True, blank=True
    )
    transtransaction_type = models.CharField(
        max_length=200, choices=transaction_type_choices
    )
    module = models.CharField(max_length=200, choices=module_choices, default="flight")
    booking_type = models.CharField(
        max_length=200, choices=booking_type_choices, null=True
    )
    booking = models.ForeignKey(
        "common.Booking", on_delete=models.CASCADE, null=True, blank=True,related_name="distributor_agent_transaction"
    )
    amount = models.FloatField(default=0.0)

    class Meta:
        db_table = "distributor_agent_transactions"
        ordering = ["-created_at"]
        managed=False

class DistributorAgentFareAdjustmentLog(SoftDeleteModel):
    old_credit_limit = models.FloatField(default=0.0)
    old_available_balance = models.FloatField(default=0.0)
    new_credit_limit = models.FloatField(default=0.0)
    new_available_balance = models.FloatField(default=0.0)
    class Meta:
        managed = False

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
    
    class Meta:
        db_table = 'flight_accounting_supplierdealmanagement'
        ordering = ['-created_at']
        managed =False
    
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
    
    
    class Meta:
        db_table = 'flight_accounting_airlinedeals'
        ordering = ['-created_at']
        managed = False

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
    
    class Meta:
        db_table = 'flight_accounting_supplierdealmanagement'
        ordering = ['-created_at']
        managed = False
class Permission(SoftDeleteModel):
    name = models.CharField(max_length=200)
    # flight
    flight_create = models.BooleanField(default=False)
    flight_view = models.BooleanField(default=False)
    flight_edit = models.BooleanField(default=False)
    flight_delete = models.BooleanField(default=False)


    # hotel 
    hotel_create = models.BooleanField(default=False)
    hotel_view = models.BooleanField(default=False)
    hotel_edit = models.BooleanField(default=False)
    hotel_delete = models.BooleanField(default=False)

    # holidays
    holidays_create = models.BooleanField(default=False)
    holidays_view = models.BooleanField(default=False)
    holidays_edit = models.BooleanField(default=False)
    holidays_delete = models.BooleanField(default=False)

    #visa 
    visa_create = models.BooleanField(default=False)
    visa_view = models.BooleanField(default=False)
    visa_edit = models.BooleanField(default=False)
    visa_delete = models.BooleanField(default=False)

    #eurail
    rail_create = models.BooleanField(default=False)
    rail_view = models.BooleanField(default=False)
    rail_edit = models.BooleanField(default=False)
    rail_delete = models.BooleanField(default=False)


    #bus
    bus_create = models.BooleanField(default=False)
    bus_view = models.BooleanField(default=False)
    bus_edit = models.BooleanField(default=False)
    bus_delete = models.BooleanField(default=False)

    #cab12 
    cab_create = models.BooleanField(default=False)
    cab_view = models.BooleanField(default=False)
    cab_edit = models.BooleanField(default=False)
    cab_delete = models.BooleanField(default=False)

    #insurance
    insurance_create = models.BooleanField(default=False)
    insurance_view = models.BooleanField(default=False)
    insurance_edit = models.BooleanField(default=False)
    insurance_delete = models.BooleanField(default=False)

    #accounts
    accounts_create = models.BooleanField(default=False)
    accounts_view = models.BooleanField(default=False)
    accounts_edit = models.BooleanField(default=False)
    accounts_delete = models.BooleanField(default=False)

    #accounts -payments
    accounts_payments_create = models.BooleanField(default=False)
    accounts_payments_view = models.BooleanField(default=False)
    accounts_payments_edit = models.BooleanField(default=False)
    accounts_payments_delete = models.BooleanField(default=False)
    
    #accounts -payments -update payments 
    accounts_payments_update1space1payments_create = models.BooleanField(default=False)
    accounts_payments_update1space1payments_view = models.BooleanField(default=False)
    accounts_payments_update1space1payments_edit = models.BooleanField(default=False)
    accounts_payments_update1space1payments_delete = models.BooleanField(default=False)


    #accounts -payments -payment history 
    accounts_payments_payment1space1history_create = models.BooleanField(default=False)
    accounts_payments_payment1space1history_view = models.BooleanField(default=False)
    accounts_payments_payment1space1history_edit = models.BooleanField(default=False)
    accounts_payments_payment1space1history_delete = models.BooleanField(default=False)

    #accounts - credit notes
    accounts_credit1space1notes_create= models.BooleanField(default=False)
    accounts_credit1space1notes_view = models.BooleanField(default=False)
    accounts_credit1space1notes_edit = models.BooleanField(default=False)
    accounts_credit1space1notes_delete = models.BooleanField(default=False)

    #accounts - invoices
    accounts_invoices_create= models.BooleanField(default=False)
    accounts_invoices_view = models.BooleanField(default=False)
    accounts_invoices_edit = models.BooleanField(default=False)
    accounts_invoices_delete = models.BooleanField(default=False)

    #accounts - ledger & statement
    accounts_ledger1space1and1space1statement_create= models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_view = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_edit = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_delete = models.BooleanField(default=False)

    #accounts - ledger & statement - ledger
    accounts_ledger1space1and1space1statement_ledger_create= models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_ledger_view = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_ledger_edit = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_ledger_delete = models.BooleanField(default=False)

    #accounts - ledger & statement - statement
    accounts_ledger1space1and1space1statement_statement_create= models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_statement_view = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_statement_edit = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_statement_delete = models.BooleanField(default=False)


    #accounts - billing
    accounts_billing_create= models.BooleanField(default=False)
    accounts_billing_view = models.BooleanField(default=False)
    accounts_billing_edit = models.BooleanField(default=False)
    accounts_billing_delete = models.BooleanField(default=False)


    #accounts - credit updation
    accounts_credit1space1updation_create= models.BooleanField(default=False)
    accounts_credit1space1updation_view = models.BooleanField(default=False)
    accounts_credit1space1updation_edit = models.BooleanField(default=False)
    accounts_credit1space1updation_delete = models.BooleanField(default=False)

    #operations
    operations_create = models.BooleanField(default=False)
    operations_view = models.BooleanField(default=False)
    operations_edit = models.BooleanField(default=False)
    operations_delete = models.BooleanField(default=False)

    #operations -import & pnr
    operations_import1space1pnr_create = models.BooleanField(default=False)
    operations_import1space1pnr_view = models.BooleanField(default=False)
    operations_import1space1pnr_edit = models.BooleanField(default=False)
    operations_import1space1pnr_delete = models.BooleanField(default=False)


    #operations -visa queues
    operations_visa1space1queues_create = models.BooleanField(default=False)
    operations_visa1space1queues_view = models.BooleanField(default=False)
    operations_visa1space1queues_edit = models.BooleanField(default=False)
    operations_visa1space1queues_delete = models.BooleanField(default=False)


    #operations -holidays queues
    operations_holidays1space1queues_create = models.BooleanField(default=False)
    operations_holidays1space1queues_view = models.BooleanField(default=False)
    operations_holidays1space1queues_edit = models.BooleanField(default=False)
    operations_holidays1space1queues_delete = models.BooleanField(default=False)
    
    
    #operations -client proxy
    operations_client1space1proxy_create = models.BooleanField(default=False)
    operations_client1space1proxy_view = models.BooleanField(default=False)
    operations_client1space1proxy_edit = models.BooleanField(default=False)
    operations_client1space1proxy_delete = models.BooleanField(default=False)


    #control panel
    control1space1panel_create = models.BooleanField(default=False)
    control1space1panel_view = models.BooleanField(default=False)
    control1space1panel_edit = models.BooleanField(default=False)
    control1space1panel_delete = models.BooleanField(default=False)


    #control panel -agency master
    control1space1panel_agency1space1master_create = models.BooleanField(default=False)
    control1space1panel_agency1space1master_view = models.BooleanField(default=False)
    control1space1panel_agency1space1master_edit = models.BooleanField(default=False)
    control1space1panel_agency1space1master_delete = models.BooleanField(default=False)


    #control panel -role assignment
    control1space1panel_role1space1assignment_create = models.BooleanField(default=False)
    control1space1panel_role1space1assignment_view = models.BooleanField(default=False)
    control1space1panel_role1space1assignment_edit = models.BooleanField(default=False)
    control1space1panel_role1space1assignment_delete = models.BooleanField(default=False)


    #control panel - whitelabeling
    control1space1panel_whitelabeling_create = models.BooleanField(default=False)
    control1space1panel_whitelabeling_view = models.BooleanField(default=False)
    control1space1panel_whitelabeling_edit = models.BooleanField(default=False)
    control1space1panel_whitelabeling_delete = models.BooleanField(default=False)


    #control panel - supplier
    control1space1panel_supplier_create = models.BooleanField(default=False)
    control1space1panel_supplier_view = models.BooleanField(default=False)
    control1space1panel_supplier_edit = models.BooleanField(default=False)
    control1space1panel_supplier_delete = models.BooleanField(default=False)


    #control panel - supplier -flights fixed fares
    control1space1panel_supplier_flights1space1fixed1space1fares_create = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_create')
    control1space1panel_supplier_flights1space1fixed1space1fares_view = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_view')
    control1space1panel_supplier_flights1space1fixed1space1fares_edit = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_edit')
    control1space1panel_supplier_flights1space1fixed1space1fares_delete = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_delete')


    #control panel - supplier - hotels products
    control1space1panel_supplier_hotels1space1products_create = models.BooleanField(default=False)
    control1space1panel_supplier_hotels1space1products_view = models.BooleanField(default=False)
    control1space1panel_supplier_hotels1space1products_edit = models.BooleanField(default=False)
    control1space1panel_supplier_hotels1space1products_delete = models.BooleanField(default=False)


    #control panel - approvals
    control1space1panel_approvals_create = models.BooleanField(default=False)
    control1space1panel_approvals_view = models.BooleanField(default=False)
    control1space1panel_approvals_edit = models.BooleanField(default=False)
    control1space1panel_approvals_delete = models.BooleanField(default=False)


    #control panel - approvals -fd fares
    control1space1panel_approvals_fd1space1fares_create = models.BooleanField(default=False)
    control1space1panel_approvals_fd1space1fares_view = models.BooleanField(default=False)
    control1space1panel_approvals_fd1space1fares_edit = models.BooleanField(default=False)
    control1space1panel_approvals_fd1space1fares_delete = models.BooleanField(default=False)


    #control panel - approvals -holidays
    control1space1panel_approvals_holidays_create = models.BooleanField(default=False)
    control1space1panel_approvals_holidays_view = models.BooleanField(default=False)
    control1space1panel_approvals_holidays_edit = models.BooleanField(default=False)
    control1space1panel_approvals_holidays_delete = models.BooleanField(default=False)


    #control panel - approvals -hotels
    control1space1panel_approvals_hotels_create = models.BooleanField(default=False)
    control1space1panel_approvals_hotels_view = models.BooleanField(default=False)
    control1space1panel_approvals_hotels_edit = models.BooleanField(default=False)
    control1space1panel_approvals_hotels_delete = models.BooleanField(default=False)


    #reports 
    reports_create = models.BooleanField(default=False)
    reports_view = models.BooleanField(default=False)
    reports_edit = models.BooleanField(default=False)
    reports_delete = models.BooleanField(default=False)

    #reports -agency productivity
    reports_agency1space1productivity_create = models.BooleanField(default=False)
    reports_agency1space1productivity_view = models.BooleanField(default=False)
    reports_agency1space1productivity_edit = models.BooleanField(default=False)
    reports_agency1space1productivity_delete = models.BooleanField(default=False)


    #reports -staff productivity
    reports_staff1space1productivity_create = models.BooleanField(default=False)
    reports_staff1space1productivity_view = models.BooleanField(default=False)
    reports_staff1space1productivity_edit = models.BooleanField(default=False)
    reports_staff1space1productivity_delete = models.BooleanField(default=False)


    #admin panel  we are giving 1space1 for normal space eg: admin1space1panel--> admin panel 
    admin1space1panel_create = models.BooleanField(default=False)
    admin1space1panel_view = models.BooleanField(default=False)
    admin1space1panel_edit = models.BooleanField(default=False)
    admin1space1panel_delete = models.BooleanField(default=False)

    #admin panel -visa 
    admin1space1panel_visa_create = models.BooleanField(default=False)
    admin1space1panel_visa_view = models.BooleanField(default=False)
    admin1space1panel_visa_edit = models.BooleanField(default=False)
    admin1space1panel_visa_delete = models.BooleanField(default=False)

    # admin panel -holiday
    admin1space1panel_holiday_create = models.BooleanField(default=False)
    admin1space1panel_holiday_view = models.BooleanField(default=False)
    admin1space1panel_holiday_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_delete = models.BooleanField(default=False)


    # admin panel -holiday product
    admin1space1panel_holiday_product_create = models.BooleanField(default=False)
    admin1space1panel_holiday_product_view = models.BooleanField(default=False)
    admin1space1panel_holiday_product_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_product_delete = models.BooleanField(default=False)


    #admin panel - holiday theme
    admin1space1panel_holiday_theme_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_theme_create = models.BooleanField(default=False)
    admin1space1panel_holiday_theme_delete = models.BooleanField(default=False)
    admin1space1panel_holiday_theme_view = models.BooleanField(default=False)


    # api management

    admin1space1panel_api1space1management_create = models.BooleanField(default=False)
    admin1space1panel_api1space1management_view = models.BooleanField(default=False)
    admin1space1panel_api1space1management_edit = models.BooleanField(default=False)
    admin1space1panel_api1space1management_delete = models.BooleanField(default=False)
    

    # communication

    admin1space1panel_communication_create = models.BooleanField(default=False)
    admin1space1panel_communication_view = models.BooleanField(default=False)
    admin1space1panel_communication_edit = models.BooleanField(default=False)
    admin1space1panel_communication_delete = models.BooleanField(default=False)


    #general

    admin1space1panel_general1space1integeration_create = models.BooleanField(default=False)
    admin1space1panel_general1space1integeration_view = models.BooleanField(default=False)
    admin1space1panel_general1space1integeration_edit = models.BooleanField(default=False)
    admin1space1panel_general1space1integeration_delete = models.BooleanField(default=False)

    
    #admin panel - supplier deal manager
    admin1space1panel_supplier1space1deal1space1manager_create = models.BooleanField(default=False)
    admin1space1panel_supplier1space1deal1space1manager_view = models.BooleanField(default=False)
    admin1space1panel_supplier1space1deal1space1manager_edit = models.BooleanField(default=False)
    admin1space1panel_supplier1space1deal1space1manager_delete = models.BooleanField(default=False)


    #     #admin panel - template
    admin1space1panel_template_create = models.BooleanField(default=False)
    admin1space1panel_template_view = models.BooleanField(default=False)
    admin1space1panel_template_edit = models.BooleanField(default=False)
    admin1space1panel_template_delete = models.BooleanField(default=False)


    # admin panel -holiday favourites
    admin1space1panel_holiday_favourites_create = models.BooleanField(default=False)
    admin1space1panel_holiday_favourites_view = models.BooleanField(default=False)
    admin1space1panel_holiday_favourites_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_favourites_delete = models.BooleanField(default=False)

    # admin panel -visa favourites
    admin1space1panel_visa_favourites_create = models.BooleanField(default=False)
    admin1space1panel_visa_favourites_view = models.BooleanField(default=False)
    admin1space1panel_visa_favourites_edit = models.BooleanField(default=False)
    admin1space1panel_visa_favourites_delete = models.BooleanField(default=False)
    
    
    admin1space1panel_visa_products_create = models.BooleanField(default=False)
    admin1space1panel_visa_products_view = models.BooleanField(default=False)
    admin1space1panel_visa_products_edit = models.BooleanField(default=False)
    admin1space1panel_visa_products_delete = models.BooleanField(default=False)
    
    admin1space1panel_visa_category_create = models.BooleanField(default=False)
    admin1space1panel_visa_category_view = models.BooleanField(default=False)
    admin1space1panel_visa_category_edit = models.BooleanField(default=False)
    admin1space1panel_visa_category_delete = models.BooleanField(default=False)
    
    
    admin1space1panel_visa_type_create = models.BooleanField(default=False)
    admin1space1panel_visa_type_view = models.BooleanField(default=False)
    admin1space1panel_visa_type_edit = models.BooleanField(default=False)
    admin1space1panel_visa_type_delete = models.BooleanField(default=False)

    #flight -queues
    flight_queues_create = models.BooleanField(default=False)
    flight_queues_view = models.BooleanField(default=False)
    flight_queues_edit = models.BooleanField(default=False)
    flight_queues_delete = models.BooleanField(default=False)


    #flight -queues -failed bookings
    flight_queues_failed1space1bookings_create = models.BooleanField(default=False)
    flight_queues_failed1space1bookings_view = models.BooleanField(default=False)
    flight_queues_failed1space1bookings_edit = models.BooleanField(default=False)
    flight_queues_failed1space1bookings_delete = models.BooleanField(default=False)

    #flight -queues -hold bookings
    flight_queues_hold1space1bookings_create = models.BooleanField(default=False)
    flight_queues_hold1space1bookings_view = models.BooleanField(default=False)
    flight_queues_hold1space1bookings_edit = models.BooleanField(default=False)
    flight_queues_hold1space1bookings_delete = models.BooleanField(default=False)


    #flight -queues -passenger calendar
    flight_queues_passenger1space1calender_create = models.BooleanField(default=False)
    flight_queues_passenger1space1calender_view = models.BooleanField(default=False)
    flight_queues_passenger1space1calender_edit = models.BooleanField(default=False)
    flight_queues_passenger1space1calender_delete = models.BooleanField(default=False)


    #flight -booking history
    flight_booking1space1history_create = models.BooleanField(default=False)
    flight_booking1space1history_view = models.BooleanField(default=False)
    flight_booking1space1history_edit = models.BooleanField(default=False)
    flight_booking1space1history_delete = models.BooleanField(default=False)
    
    #flight -search
    flight_search_create = models.BooleanField(default=False)
    flight_search_view = models.BooleanField(default=False)
    flight_search_edit = models.BooleanField(default=False)
    flight_search_delete = models.BooleanField(default=False)


    #accounts -branch allocation
    accounts_branch1space1allocation_create = models.BooleanField(default=False)
    accounts_branch1space1allocation_view = models.BooleanField(default=False)
    accounts_branch1space1allocation_edit = models.BooleanField(default=False)
    accounts_branch1space1allocation_delete = models.BooleanField(default=False)

   #flight -queues -cancelled bookings
    flight_queues_cancelled1space1bookings_create = models.BooleanField(default=False)
    flight_queues_cancelled1space1bookings_view = models.BooleanField(default=False)
    flight_queues_cancelled1space1bookings_edit = models.BooleanField(default=False)
    flight_queues_cancelled1space1bookings_delete = models.BooleanField(default=False)


    #admin panel - customer deal manager
    admin1space1panel_customer1space1deal1space1manager_create = models.BooleanField(default=False)
    admin1space1panel_customer1space1deal1space1manager_view = models.BooleanField(default=False)
    admin1space1panel_customer1space1deal1space1manager_edit = models.BooleanField(default=False)
    admin1space1panel_customer1space1deal1space1manager_delete = models.BooleanField(default=False)

    #accounts -offline & ticketing
    accounts_offline1space1ticketing_create = models.BooleanField(default=False)
    accounts_offline1space1ticketing_view = models.BooleanField(default=False)
    accounts_offline1space1ticketing_edit = models.BooleanField(default=False)
    accounts_offline1space1ticketing_delete = models.BooleanField(default=False)

    #holidays -search
    holidays_search_create = models.BooleanField(default=False)
    holidays_search_view = models.BooleanField(default=False)
    holidays_search_edit = models.BooleanField(default=False)
    holidays_search_delete = models.BooleanField(default=False)

    #holidays -enquiry history
    holidays_enquiry1space1history_create = models.BooleanField(default=False)
    holidays_enquiry1space1history_view = models.BooleanField(default=False)
    holidays_enquiry1space1history_edit = models.BooleanField(default=False)
    holidays_enquiry1space1history_delete = models.BooleanField(default=False)

        #visa -search
    visa_search_create = models.BooleanField(default=False)
    visa_search_view = models.BooleanField(default=False)
    visa_search_edit = models.BooleanField(default=False)
    visa_search_delete = models.BooleanField(default=False)

    #visa -enquiry history
    visa_enquiry1space1history_create = models.BooleanField(default=False)
    visa_enquiry1space1history_view = models.BooleanField(default=False)
    visa_enquiry1space1history_edit = models.BooleanField(default=False)
    visa_enquiry1space1history_delete = models.BooleanField(default=False)

    #accounts - ledger & statement - agent statement
    accounts_ledger1space1and1space1statement_agent1space1statement_create= models.BooleanField(default=False,db_column='agent_statement_create')
    accounts_ledger1space1and1space1statement_agent1space1statement_view = models.BooleanField(default=False,db_column='agent_statement_view')
    accounts_ledger1space1and1space1statement_agent1space1statement_edit = models.BooleanField(default=False,db_column='agent_statement_edit')
    accounts_ledger1space1and1space1statement_agent1space1statement_delete = models.BooleanField(default=False,db_column='agent_statement_delete')

    #accounts - credit notes own 
    accounts_credit1space1notes_own_create= models.BooleanField(default=False)
    accounts_credit1space1notes_own_view = models.BooleanField(default=False)
    accounts_credit1space1notes_own_edit = models.BooleanField(default=False)
    accounts_credit1space1notes_own_delete = models.BooleanField(default=False)


    #accounts - credit notes agent 
    accounts_credit1space1notes_agent_create= models.BooleanField(default=False)
    accounts_credit1space1notes_agent_view = models.BooleanField(default=False)
    accounts_credit1space1notes_agent_edit = models.BooleanField(default=False)
    accounts_credit1space1notes_agent_delete = models.BooleanField(default=False)
    
    #reports -sales performance
    reports_sales1space1performance_create = models.BooleanField(default=False)
    reports_sales1space1performance_view = models.BooleanField(default=False)
    reports_sales1space1performance_edit = models.BooleanField(default=False)
    reports_sales1space1performance_delete = models.BooleanField(default=False)

    #control panel - outapi management
    control1space1panel_out1hyphen1API1space1management_create = models.BooleanField(default=False)
    control1space1panel_out1hyphen1API1space1management_view = models.BooleanField(default=False)
    control1space1panel_out1hyphen1API1space1management_edit = models.BooleanField(default=False)
    control1space1panel_out1hyphen1API1space1management_delete = models.BooleanField(default=False)
    
    #reports -user journey tracker
    reports_user1space1journey1space1tracker_create = models.BooleanField(default=False)
    reports_user1space1journey1space1tracker_view = models.BooleanField(default=False)
    reports_user1space1journey1space1tracker_edit = models.BooleanField(default=False)
    reports_user1space1journey1space1tracker_delete = models.BooleanField(default=False)

    #reports - finance team performance
    reports_finance1space1team1space1performance_create = models.BooleanField(default=False)
    reports_finance1space1team1space1performance_view = models.BooleanField(default=False)
    reports_finance1space1team1space1performance_edit = models.BooleanField(default=False)
    reports_finance1space1team1space1performance_delete = models.BooleanField(default=False)
    
    def __str__(self):
        return str(self.name)
    
    class Meta:
        ordering = ['-created_at']
        managed =False



from django.db import models

# Create your models here.


class LookupPermission(SoftDeleteModel):
    name = models.CharField(max_length=200)
    # flight
    flight_create = models.BooleanField(default=False)
    flight_view = models.BooleanField(default=False)
    flight_edit = models.BooleanField(default=False)
    flight_delete = models.BooleanField(default=False)


    # hotel 
    hotel_create = models.BooleanField(default=False)
    hotel_view = models.BooleanField(default=False)
    hotel_edit = models.BooleanField(default=False)
    hotel_delete = models.BooleanField(default=False)

    # holidays
    holidays_create = models.BooleanField(default=False)
    holidays_view = models.BooleanField(default=False)
    holidays_edit = models.BooleanField(default=False)
    holidays_delete = models.BooleanField(default=False)

    #visa 
    visa_create = models.BooleanField(default=False)
    visa_view = models.BooleanField(default=False)
    visa_edit = models.BooleanField(default=False)
    visa_delete = models.BooleanField(default=False)

    #eurail
    rail_create = models.BooleanField(default=False)
    rail_view = models.BooleanField(default=False)
    rail_edit = models.BooleanField(default=False)
    rail_delete = models.BooleanField(default=False)


    #bus
    bus_create = models.BooleanField(default=False)
    bus_view = models.BooleanField(default=False)
    bus_edit = models.BooleanField(default=False)
    bus_delete = models.BooleanField(default=False)

    #cab12 
    cab_create = models.BooleanField(default=False)
    cab_view = models.BooleanField(default=False)
    cab_edit = models.BooleanField(default=False)
    cab_delete = models.BooleanField(default=False)

    #insurance
    insurance_create = models.BooleanField(default=False)
    insurance_view = models.BooleanField(default=False)
    insurance_edit = models.BooleanField(default=False)
    insurance_delete = models.BooleanField(default=False)

    #accounts
    accounts_create = models.BooleanField(default=False)
    accounts_view = models.BooleanField(default=False)
    accounts_edit = models.BooleanField(default=False)
    accounts_delete = models.BooleanField(default=False)

    #accounts -payments
    accounts_payments_create = models.BooleanField(default=False)
    accounts_payments_view = models.BooleanField(default=False)
    accounts_payments_edit = models.BooleanField(default=False)
    accounts_payments_delete = models.BooleanField(default=False)
    
    #accounts -payments -update payments 
    accounts_payments_update1space1payments_create = models.BooleanField(default=False)
    accounts_payments_update1space1payments_view = models.BooleanField(default=False)
    accounts_payments_update1space1payments_edit = models.BooleanField(default=False)
    accounts_payments_update1space1payments_delete = models.BooleanField(default=False)


    #accounts -payments -payment history 
    accounts_payments_payment1space1history_create = models.BooleanField(default=False)
    accounts_payments_payment1space1history_view = models.BooleanField(default=False)
    accounts_payments_payment1space1history_edit = models.BooleanField(default=False)
    accounts_payments_payment1space1history_delete = models.BooleanField(default=False)

    #accounts - credit notes
    accounts_credit1space1notes_create= models.BooleanField(default=False)
    accounts_credit1space1notes_view = models.BooleanField(default=False)
    accounts_credit1space1notes_edit = models.BooleanField(default=False)
    accounts_credit1space1notes_delete = models.BooleanField(default=False)

    #accounts - invoices
    accounts_invoices_create= models.BooleanField(default=False)
    accounts_invoices_view = models.BooleanField(default=False)
    accounts_invoices_edit = models.BooleanField(default=False)
    accounts_invoices_delete = models.BooleanField(default=False)

    #accounts - ledger & statement
    accounts_ledger1space1and1space1statement_create= models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_view = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_edit = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_delete = models.BooleanField(default=False)

    #accounts - ledger & statement - ledger
    accounts_ledger1space1and1space1statement_ledger_create= models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_ledger_view = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_ledger_edit = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_ledger_delete = models.BooleanField(default=False)

    #accounts - ledger & statement - statement
    accounts_ledger1space1and1space1statement_statement_create= models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_statement_view = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_statement_edit = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_statement_delete = models.BooleanField(default=False)


    #accounts - billing
    accounts_billing_create= models.BooleanField(default=False)
    accounts_billing_view = models.BooleanField(default=False)
    accounts_billing_edit = models.BooleanField(default=False)
    accounts_billing_delete = models.BooleanField(default=False)


    #accounts - credit updation
    accounts_credit1space1updation_create= models.BooleanField(default=False)
    accounts_credit1space1updation_view = models.BooleanField(default=False)
    accounts_credit1space1updation_edit = models.BooleanField(default=False)
    accounts_credit1space1updation_delete = models.BooleanField(default=False)

    #operations
    operations_create = models.BooleanField(default=False)
    operations_view = models.BooleanField(default=False)
    operations_edit = models.BooleanField(default=False)
    operations_delete = models.BooleanField(default=False)

    #operations -import & pnr
    operations_import1space1pnr_create = models.BooleanField(default=False)
    operations_import1space1pnr_view = models.BooleanField(default=False)
    operations_import1space1pnr_edit = models.BooleanField(default=False)
    operations_import1space1pnr_delete = models.BooleanField(default=False)

    #operations -visa queues
    operations_visa1space1queues_create = models.BooleanField(default=False)
    operations_visa1space1queues_view = models.BooleanField(default=False)
    operations_visa1space1queues_edit = models.BooleanField(default=False)
    operations_visa1space1queues_delete = models.BooleanField(default=False)


    #operations -holidays queues
    operations_holidays1space1queues_create = models.BooleanField(default=False)
    operations_holidays1space1queues_view = models.BooleanField(default=False)
    operations_holidays1space1queues_edit = models.BooleanField(default=False)
    operations_holidays1space1queues_delete = models.BooleanField(default=False)
    
    
    #operations -client proxy
    operations_client1space1proxy_create = models.BooleanField(default=False)
    operations_client1space1proxy_view = models.BooleanField(default=False)
    operations_client1space1proxy_edit = models.BooleanField(default=False)
    operations_client1space1proxy_delete = models.BooleanField(default=False)


    #control panel
    control1space1panel_create = models.BooleanField(default=False)
    control1space1panel_view = models.BooleanField(default=False)
    control1space1panel_edit = models.BooleanField(default=False)
    control1space1panel_delete = models.BooleanField(default=False)


    #control panel -agency master
    control1space1panel_agency1space1master_create = models.BooleanField(default=False)
    control1space1panel_agency1space1master_view = models.BooleanField(default=False)
    control1space1panel_agency1space1master_edit = models.BooleanField(default=False)
    control1space1panel_agency1space1master_delete = models.BooleanField(default=False)


    #control panel -role assignment
    control1space1panel_role1space1assignment_create = models.BooleanField(default=False)
    control1space1panel_role1space1assignment_view = models.BooleanField(default=False)
    control1space1panel_role1space1assignment_edit = models.BooleanField(default=False)
    control1space1panel_role1space1assignment_delete = models.BooleanField(default=False)


    #control panel - whitelabeling
    control1space1panel_whitelabeling_create = models.BooleanField(default=False)
    control1space1panel_whitelabeling_view = models.BooleanField(default=False)
    control1space1panel_whitelabeling_edit = models.BooleanField(default=False)
    control1space1panel_whitelabeling_delete = models.BooleanField(default=False)


    #control panel - supplier
    control1space1panel_supplier_create = models.BooleanField(default=False)
    control1space1panel_supplier_view = models.BooleanField(default=False)
    control1space1panel_supplier_edit = models.BooleanField(default=False)
    control1space1panel_supplier_delete = models.BooleanField(default=False)


    #control panel - supplier -flights fixed fares
    control1space1panel_supplier_flights1space1fixed1space1fares_create = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_create')
    control1space1panel_supplier_flights1space1fixed1space1fares_view = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_view')
    control1space1panel_supplier_flights1space1fixed1space1fares_edit = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_edit')
    control1space1panel_supplier_flights1space1fixed1space1fares_delete = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_delete')


    #control panel - supplier - hotels products
    control1space1panel_supplier_hotels1space1products_create = models.BooleanField(default=False)
    control1space1panel_supplier_hotels1space1products_view = models.BooleanField(default=False)
    control1space1panel_supplier_hotels1space1products_edit = models.BooleanField(default=False)
    control1space1panel_supplier_hotels1space1products_delete = models.BooleanField(default=False)


    #control panel - approvals
    control1space1panel_approvals_create = models.BooleanField(default=False)
    control1space1panel_approvals_view = models.BooleanField(default=False)
    control1space1panel_approvals_edit = models.BooleanField(default=False)
    control1space1panel_approvals_delete = models.BooleanField(default=False)


    #control panel - approvals -fd fares
    control1space1panel_approvals_fd1space1fares_create = models.BooleanField(default=False)
    control1space1panel_approvals_fd1space1fares_view = models.BooleanField(default=False)
    control1space1panel_approvals_fd1space1fares_edit = models.BooleanField(default=False)
    control1space1panel_approvals_fd1space1fares_delete = models.BooleanField(default=False)


    #control panel - approvals -holidays
    control1space1panel_approvals_holidays_create = models.BooleanField(default=False)
    control1space1panel_approvals_holidays_view = models.BooleanField(default=False)
    control1space1panel_approvals_holidays_edit = models.BooleanField(default=False)
    control1space1panel_approvals_holidays_delete = models.BooleanField(default=False)


    #control panel - approvals -hotels
    control1space1panel_approvals_hotels_create = models.BooleanField(default=False)
    control1space1panel_approvals_hotels_view = models.BooleanField(default=False)
    control1space1panel_approvals_hotels_edit = models.BooleanField(default=False)
    control1space1panel_approvals_hotels_delete = models.BooleanField(default=False)


    #reports 
    reports_create = models.BooleanField(default=False)
    reports_view = models.BooleanField(default=False)
    reports_edit = models.BooleanField(default=False)
    reports_delete = models.BooleanField(default=False)

    #reports -agency productivity
    reports_agency1space1productivity_create = models.BooleanField(default=False)
    reports_agency1space1productivity_view = models.BooleanField(default=False)
    reports_agency1space1productivity_edit = models.BooleanField(default=False)
    reports_agency1space1productivity_delete = models.BooleanField(default=False)


    #reports -staff productivity
    reports_staff1space1productivity_create = models.BooleanField(default=False)
    reports_staff1space1productivity_view = models.BooleanField(default=False)
    reports_staff1space1productivity_edit = models.BooleanField(default=False)
    reports_staff1space1productivity_delete = models.BooleanField(default=False)

    #admin panel  we are giving 1space1 for normal space eg: admin1space1panel--> admin panel 
    admin1space1panel_create = models.BooleanField(default=False)
    admin1space1panel_view = models.BooleanField(default=False)
    admin1space1panel_edit = models.BooleanField(default=False)
    admin1space1panel_delete = models.BooleanField(default=False)

    #admin panel -visa 
    admin1space1panel_visa_create = models.BooleanField(default=False)
    admin1space1panel_visa_view = models.BooleanField(default=False)
    admin1space1panel_visa_edit = models.BooleanField(default=False)
    admin1space1panel_visa_delete = models.BooleanField(default=False)

    # admin panel -holiday
    admin1space1panel_holiday_create = models.BooleanField(default=False)
    admin1space1panel_holiday_view = models.BooleanField(default=False)
    admin1space1panel_holiday_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_delete = models.BooleanField(default=False)


    # admin panel -holiday product
    admin1space1panel_holiday_product_create = models.BooleanField(default=False)
    admin1space1panel_holiday_product_view = models.BooleanField(default=False)
    admin1space1panel_holiday_product_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_product_delete = models.BooleanField(default=False)


    #admin panel - holiday theme
    admin1space1panel_holiday_theme_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_theme_create = models.BooleanField(default=False)
    admin1space1panel_holiday_theme_delete = models.BooleanField(default=False)
    admin1space1panel_holiday_theme_view = models.BooleanField(default=False)


    # api management

    admin1space1panel_api1space1management_create = models.BooleanField(default=False)
    admin1space1panel_api1space1management_view = models.BooleanField(default=False)
    admin1space1panel_api1space1management_edit = models.BooleanField(default=False)
    admin1space1panel_api1space1management_delete = models.BooleanField(default=False)
    

    # communication

    admin1space1panel_communication_create = models.BooleanField(default=False)
    admin1space1panel_communication_view = models.BooleanField(default=False)
    admin1space1panel_communication_edit = models.BooleanField(default=False)
    admin1space1panel_communication_delete = models.BooleanField(default=False)


    #general

    admin1space1panel_general1space1integeration_create = models.BooleanField(default=False)
    admin1space1panel_general1space1integeration_view = models.BooleanField(default=False)
    admin1space1panel_general1space1integeration_edit = models.BooleanField(default=False)
    admin1space1panel_general1space1integeration_delete = models.BooleanField(default=False)

    
    #admin panel - supplier deal manager
    admin1space1panel_supplier1space1deal1space1manager_create = models.BooleanField(default=False)
    admin1space1panel_supplier1space1deal1space1manager_view = models.BooleanField(default=False)
    admin1space1panel_supplier1space1deal1space1manager_edit = models.BooleanField(default=False)
    admin1space1panel_supplier1space1deal1space1manager_delete = models.BooleanField(default=False)


    #     #admin panel - template
    admin1space1panel_template_create = models.BooleanField(default=False)
    admin1space1panel_template_view = models.BooleanField(default=False)
    admin1space1panel_template_edit = models.BooleanField(default=False)
    admin1space1panel_template_delete = models.BooleanField(default=False)


    # admin panel -holiday favourites
    admin1space1panel_holiday_favourites_create = models.BooleanField(default=False)
    admin1space1panel_holiday_favourites_view = models.BooleanField(default=False)
    admin1space1panel_holiday_favourites_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_favourites_delete = models.BooleanField(default=False)

    # admin panel -visa favourites
    admin1space1panel_visa_favourites_create = models.BooleanField(default=False)
    admin1space1panel_visa_favourites_view = models.BooleanField(default=False)
    admin1space1panel_visa_favourites_edit = models.BooleanField(default=False)
    admin1space1panel_visa_favourites_delete = models.BooleanField(default=False)
    
    
    admin1space1panel_visa_products_create = models.BooleanField(default=False)
    admin1space1panel_visa_products_view = models.BooleanField(default=False)
    admin1space1panel_visa_products_edit = models.BooleanField(default=False)
    admin1space1panel_visa_products_delete = models.BooleanField(default=False)
    
    admin1space1panel_visa_category_create = models.BooleanField(default=False)
    admin1space1panel_visa_category_view = models.BooleanField(default=False)
    admin1space1panel_visa_category_edit = models.BooleanField(default=False)
    admin1space1panel_visa_category_delete = models.BooleanField(default=False)
    
    
    admin1space1panel_visa_type_create = models.BooleanField(default=False)
    admin1space1panel_visa_type_view = models.BooleanField(default=False)
    admin1space1panel_visa_type_edit = models.BooleanField(default=False)
    admin1space1panel_visa_type_delete = models.BooleanField(default=False)

    #flight -queues
    flight_queues_create = models.BooleanField(default=False)
    flight_queues_view = models.BooleanField(default=False)
    flight_queues_edit = models.BooleanField(default=False)
    flight_queues_delete = models.BooleanField(default=False)


    #flight -queues -failed bookings
    flight_queues_failed1space1bookings_create = models.BooleanField(default=False)
    flight_queues_failed1space1bookings_view = models.BooleanField(default=False)
    flight_queues_failed1space1bookings_edit = models.BooleanField(default=False)
    flight_queues_failed1space1bookings_delete = models.BooleanField(default=False)

    #flight -queues -hold bookings
    flight_queues_hold1space1bookings_create = models.BooleanField(default=False)
    flight_queues_hold1space1bookings_view = models.BooleanField(default=False)
    flight_queues_hold1space1bookings_edit = models.BooleanField(default=False)
    flight_queues_hold1space1bookings_delete = models.BooleanField(default=False)


    #flight -queues -passenger calendar
    flight_queues_passenger1space1calender_create = models.BooleanField(default=False)
    flight_queues_passenger1space1calender_view = models.BooleanField(default=False)
    flight_queues_passenger1space1calender_edit = models.BooleanField(default=False)
    flight_queues_passenger1space1calender_delete = models.BooleanField(default=False)


    #flight -booking history
    flight_booking1space1history_create = models.BooleanField(default=False)
    flight_booking1space1history_view = models.BooleanField(default=False)
    flight_booking1space1history_edit = models.BooleanField(default=False)
    flight_booking1space1history_delete = models.BooleanField(default=False)
    
    #flight -search
    flight_search_create = models.BooleanField(default=False)
    flight_search_view = models.BooleanField(default=False)
    flight_search_edit = models.BooleanField(default=False)
    flight_search_delete = models.BooleanField(default=False)


    #accounts -branch allocation
    accounts_branch1space1allocation_create = models.BooleanField(default=False)
    accounts_branch1space1allocation_view = models.BooleanField(default=False)
    accounts_branch1space1allocation_edit = models.BooleanField(default=False)
    accounts_branch1space1allocation_delete = models.BooleanField(default=False)

   #flight -queues -cancelled bookings
    flight_queues_cancelled1space1bookings_create = models.BooleanField(default=False)
    flight_queues_cancelled1space1bookings_view = models.BooleanField(default=False)
    flight_queues_cancelled1space1bookings_edit = models.BooleanField(default=False)
    flight_queues_cancelled1space1bookings_delete = models.BooleanField(default=False)


    #admin panel - customer deal manager
    admin1space1panel_customer1space1deal1space1manager_create = models.BooleanField(default=False)
    admin1space1panel_customer1space1deal1space1manager_view = models.BooleanField(default=False)
    admin1space1panel_customer1space1deal1space1manager_edit = models.BooleanField(default=False)
    admin1space1panel_customer1space1deal1space1manager_delete = models.BooleanField(default=False)

    #accounts -offline & ticketing
    accounts_offline1space1ticketing_create = models.BooleanField(default=False)
    accounts_offline1space1ticketing_view = models.BooleanField(default=False)
    accounts_offline1space1ticketing_edit = models.BooleanField(default=False)
    accounts_offline1space1ticketing_delete = models .BooleanField(default=False)

    #holidays -search
    holidays_search_create = models.BooleanField(default=False)
    holidays_search_view = models.BooleanField(default=False)
    holidays_search_edit = models.BooleanField(default=False)
    holidays_search_delete = models.BooleanField(default=False)

    #holidays -enquiry history
    holidays_enquiry1space1history_create = models.BooleanField(default=False)
    holidays_enquiry1space1history_view = models.BooleanField(default=False)
    holidays_enquiry1space1history_edit = models.BooleanField(default=False)
    holidays_enquiry1space1history_delete = models.BooleanField(default=False)

        #visa -search
    visa_search_create = models.BooleanField(default=False)
    visa_search_view = models.BooleanField(default=False)
    visa_search_edit = models.BooleanField(default=False)
    visa_search_delete = models.BooleanField(default=False)

    #visa -enquiry history
    visa_enquiry1space1history_create = models.BooleanField(default=False)
    visa_enquiry1space1history_view = models.BooleanField(default=False)
    visa_enquiry1space1history_edit = models.BooleanField(default=False)
    visa_enquiry1space1history_delete = models.BooleanField(default=False)

    #accounts - ledger & statement - agent statement
    accounts_ledger1space1and1space1statement_agent1space1statement_create= models.BooleanField(default=False,db_column='agent_statement_create')
    accounts_ledger1space1and1space1statement_agent1space1statement_view = models.BooleanField(default=False,db_column='agent_statement_view')
    accounts_ledger1space1and1space1statement_agent1space1statement_edit = models.BooleanField(default=False,db_column='agent_statement_edit')
    accounts_ledger1space1and1space1statement_agent1space1statement_delete = models.BooleanField(default=False,db_column='agent_statement_delete')

    #accounts - credit notes own 
    accounts_credit1space1notes_own_create= models.BooleanField(default=False)
    accounts_credit1space1notes_own_view = models.BooleanField(default=False)
    accounts_credit1space1notes_own_edit = models.BooleanField(default=False)
    accounts_credit1space1notes_own_delete = models.BooleanField(default=False)


    #accounts - credit notes agent 
    accounts_credit1space1notes_agent_create= models.BooleanField(default=False)
    accounts_credit1space1notes_agent_view = models.BooleanField(default=False)
    accounts_credit1space1notes_agent_edit = models.BooleanField(default=False)
    accounts_credit1space1notes_agent_delete = models.BooleanField(default=False)

    #reports -sales performance
    reports_sales1space1performance_create = models.BooleanField(default=False)
    reports_sales1space1performance_view = models.BooleanField(default=False)
    reports_sales1space1performance_edit = models.BooleanField(default=False)
    reports_sales1space1performance_delete = models.BooleanField(default=False)

    #control panel - outapi management
    control1space1panel_out1hyphen1API1space1management_create = models.BooleanField(default=False)
    control1space1panel_out1hyphen1API1space1management_view = models.BooleanField(default=False)
    control1space1panel_out1hyphen1API1space1management_edit = models.BooleanField(default=False)
    control1space1panel_out1hyphen1API1space1management_delete = models.BooleanField(default=False)

    #reports -user journey tracker
    reports_user1space1journey1space1tracker_create = models.BooleanField(default=False)
    reports_user1space1journey1space1tracker_view = models.BooleanField(default=False)
    reports_user1space1journey1space1tracker_edit = models.BooleanField(default=False)
    reports_user1space1journey1space1tracker_delete = models.BooleanField(default=False)

    #reports - finance team performance
    reports_finance1space1team1space1performance_create = models.BooleanField(default=False)
    reports_finance1space1team1space1performance_view = models.BooleanField(default=False)
    reports_finance1space1team1space1performance_edit = models.BooleanField(default=False)
    reports_finance1space1team1space1performance_delete = models.BooleanField(default=False)

    def __str__(self):
        return str(self.name)

    class Meta:
        db_table = 'lookup_permission'
        ordering = ['-created_at']
        managed = False





