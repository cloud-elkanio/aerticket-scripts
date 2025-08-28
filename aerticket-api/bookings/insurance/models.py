import uuid
import time
from django.db import models
from django.utils import timezone

from users.models import Country,UserDetails,LookupCountry
from integrations.suppliers.models import SupplierIntegration
from accounting.shared.models import PaymentDetail

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


############################ ASEGO ############################
class InsuranceAsegoVisitingCountry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # This field now links to the common Country model
    country = models.ForeignKey(Country, on_delete=models.CASCADE, db_column='Country Code')
    description = models.CharField(max_length=255, db_column='Description')
    reference = models.CharField(max_length=255, db_column='Reference')

    class Meta:
        db_table = 'insurance_asego_visiting_countries'

    def __str__(self):
        return f"{self.country} - {self.description}"


class InsuranceAsegoCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Retaining the original code as a unique field
    category_code = models.UUIDField(db_column='Category Code', default=uuid.uuid4, editable=False, unique=True)
    description = models.CharField(max_length=255, db_column='Description')

    class Meta:
        db_table = 'insurance_asego_category'

    def __str__(self):
        return str(self.category_code)


class InsuranceAsegoPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Retain the original plan_code as a unique field
    plan_code = models.UUIDField(db_column='Plan Code', default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255, db_column='Name')
    category = models.ForeignKey(InsuranceAsegoCategory, on_delete=models.CASCADE, db_column='Category Code')
    day_plan = models.BooleanField(db_column='Day Plan')
    trawelltag_option = models.BooleanField(db_column='Trawell Tag Option')
    annual_plan = models.BooleanField(db_column='Annual Plan')
    country = models.ForeignKey(InsuranceAsegoVisitingCountry, on_delete=models.CASCADE, db_column='Country Code')

    class Meta:
        db_table = 'insurance_asego_plan'

    def __str__(self):
        return self.name



class InsuranceAsegoRiderMaster(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Retain the original rider_code as a unique field
    rider_code = models.UUIDField(db_column='Rider Code', default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    amount = models.CharField(max_length=255, blank=True, null=True,db_column='Amount')
    restricted_amount = models.CharField(max_length=255, blank=True, null=True,db_column='RestrictedAmount')
    deductibles = models.CharField(max_length=255, blank=True, null=True,db_column='Deductibles')
    deductible_text = models.BooleanField(db_column='DeductibleText')
    currency = models.CharField(max_length=30, blank=True, null=True,db_column='Currency')

    class Meta:
        db_table = 'insurance_asego_rider_master'

    def __str__(self):
        return self.name if self.name else str(self.rider_code)


class InsuranceAsegoPlanRider(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(InsuranceAsegoPlan, on_delete=models.CASCADE)
    rider = models.ForeignKey(InsuranceAsegoRiderMaster, on_delete=models.CASCADE)
    trawell_assist_charges_percent = models.DecimalField(max_digits=5, decimal_places=2, db_column='Trawell Assist Charges Percent')

    class Meta:
        db_table = 'insurance_asego_plan_riders'
        unique_together = (('plan', 'rider'),)

    def __str__(self):
        return f"{self.plan} - {self.rider}"


class InsuranceAsegoPremiumChart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(InsuranceAsegoPlan, on_delete=models.CASCADE)
    age_limit = models.IntegerField(db_column='Age Limit')
    day_limit = models.IntegerField(db_column='Day Limit')
    premium = models.DecimalField(max_digits=10, decimal_places=2, db_column='Premium')

    class Meta:
        db_table = 'insurance_asego_premium_chart'
        unique_together = (('plan', 'age_limit', 'day_limit'),)

    def __str__(self):
        return f"{self.plan} - Age {self.age_limit} / Day {self.day_limit}: {self.premium}"
    

############################ ASEGO ############################


class InsuranceBookingSearchDetail(SoftDeleteModel):   
    commensing_date = models.CharField(max_length=50,null=True, blank=True)
    end_date = models.CharField(max_length=50,null=True, blank=True)
    duration = models.CharField(max_length=50,null=True, blank=True)

    class Meta: 
        db_table = 'insurance_booking_search_detail'

class InsuranceBookingPaymentDetail(SoftDeleteModel):
    payment_choices  = (
        ("wallet", "wallet"),
        ("stripe", "stripe"),
        ("razor_pay", "razor_pay"),
    )
    payment_type = models.CharField(max_length=100, choices=payment_choices)
    status = models.CharField(max_length=50, null=True, blank=True)
    timestamp = models.BigIntegerField(null=True, editable=False)
    new_published_fare = models.FloatField(null =False,default = 0)
    new_offered_fare = models.FloatField(null =False,default = 0)
    supplier_published_fare = models.FloatField(null =False,default = 0)
    supplier_offered_fare = models.FloatField(null =False,default = 0)
    payment_details = models.ForeignKey(PaymentDetail, on_delete=models.CASCADE, null=True, blank=True)
    class Meta:
        db_table = 'insurance_booking_payment_detail'

class InsuranceBooking(SoftDeleteModel):
    session_id = models.CharField(max_length=100)
    display_id = models.CharField(max_length=30)
    vendor = models.ForeignKey(SupplierIntegration, null=True, blank=True, on_delete=models.CASCADE)
    # Changed related_name to avoid conflict with flight_booking.Booking.user
    user = models.ForeignKey(UserDetails, on_delete=models.CASCADE, related_name='insurance_bookings')
    status = models.CharField(max_length=50)
    error = models.CharField(max_length=4000, null=True, blank=True)
    booked_at = models.PositiveBigIntegerField(null=True, blank=True)
    cancelled_at = models.PositiveBigIntegerField(null=True, blank=True)
    # Changed related_name to avoid conflict with flight_booking.Booking.cancelled_by
    cancelled_by = models.ForeignKey(
        UserDetails,
        on_delete=models.CASCADE,
        null=True,
        related_name='insurance_cancelled_bookings'
    )
    # Changed related_name to avoid conflict with flight_booking.Booking.modified_by
    modified_by = models.ForeignKey(
        UserDetails,
        on_delete=models.CASCADE,
        null=True,
        related_name='insurance_modified_bookings'
    )
    misc = models.JSONField(null=True, blank=True)
    search_detail = models.ForeignKey(InsuranceBookingSearchDetail, on_delete=models.CASCADE)
    insurance_payment_details = models.ForeignKey(InsuranceBookingPaymentDetail, on_delete=models.CASCADE)

    def __str__(self):
        return self.display_id

    class Meta:
        db_table = 'insurance_booking'


class InsuranceBookingPaxDetail(SoftDeleteModel):
    booking = models.ForeignKey(InsuranceBooking, on_delete= models.CASCADE)
    title = models.CharField(max_length=100,null=True, blank=True)
    first_name = models.CharField(max_length=300,null=True, blank=True)
    last_name = models.CharField(max_length=300,null=True, blank=True)
    dob = models.CharField(max_length=300,null=True, blank=True)
    gender = models.CharField(max_length=300,null=True, blank=True)
   
    misc = models.JSONField(null = True, blank = True)
    address1 = models.CharField(max_length=1000,null=True, blank=True)
    address2 = models.CharField(max_length=1000,null=True, blank=True)
    passport = models.CharField(max_length=300,null=True, blank=True)
    city = models.CharField(max_length=300,null=True, blank=True)
    district = models.CharField(max_length=300,null=True, blank=True)
    state = models.CharField(max_length=300,null=True, blank=True)
    pincode = models.CharField(max_length=300,null=True, blank=True)
    phone_code = models.CharField(max_length=30,null=True, blank=True)
    phone_number = models.CharField(max_length=300,null=True, blank=True)
    country = models.ForeignKey(LookupCountry, on_delete=models.CASCADE)
    email = models.CharField(max_length=300,null=True, blank=True)
    nominee_name = models.CharField(max_length=300,null=True, blank=True)
    relation = models.CharField(max_length=300,null=True, blank=True)
    past_illness = models.CharField(max_length=300,null=True, blank=True)
    addons = models.JSONField(null = True, blank = True)

    document = models.CharField(max_length=800,null=True, blank=True)
    policy = models.CharField(max_length=100,null=True, blank=True)
    reference = models.CharField(max_length=100,null=True, blank=True)
    claimcode = models.CharField(max_length=100,null=True, blank=True)
    status = models.CharField(max_length=100,null=True, blank=True)

    class Meta:
        db_table = 'insurance_booking_pax_detail'

class InsuranceBookingFareDetail(SoftDeleteModel):
    pax = models.ForeignKey(InsuranceBookingPaxDetail, on_delete=models.CASCADE)
    published_fare = models.FloatField(null =False,default = 0)
    offered_fare = models.FloatField(null =False,default = 0)
    organization_discount = models.FloatField(null =False,default = 0)
    dist_agent_markup = models.FloatField(null =False,default = 0)
    dist_agent_cashback = models.FloatField(null =False,default = 0)
    fare_breakdown = models.CharField(max_length=4000,null=True, blank=True)
    tax = models.FloatField(null =False,default = 0)

    class Meta:
        db_table = 'insurance_booking_fare_detail'
