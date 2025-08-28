from django.db import models
from users.models import UserDetails
from django.utils import timezone
import time
import uuid
from common.models import PaymentDetail

# Create your models here.

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


class TransferBookingSearchDetail(SoftDeleteModel):
    transfer_time = models.CharField(max_length=10,null=True, blank=True)
    transfer_date = models.CharField(max_length=15,null=True, blank=True)
    pax_count = models.IntegerField(null=True, blank=True)
    preferred_language = models.IntegerField(null=True, blank=True)
    alternate_language = models.IntegerField(null=True, blank=True)
    pickup_type = models.CharField(max_length=20,null=True, blank=True)
    pickup_point_code = models.CharField(max_length=25,null=True, blank=True)
    city_id = models.IntegerField(null=True, blank=True)
    dropoff_type = models.CharField(max_length=20,null=True, blank=True)
    dropoff_point_code = models.CharField(max_length=25,null=True, blank=True)
    country_code = models.CharField(max_length=5,null=True, blank=True)
    preferred_currency =  models.CharField(max_length=10,null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'transfer_booking_search_detail'

class TransferBookingPaymentDetail(SoftDeleteModel):
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
    payment = models.ForeignKey(PaymentDetail,null=True,blank=True,on_delete=models.CASCADE)

    class Meta:
        managed = False
        db_table = 'transfer_booking_payment_detail'

class TransferBooking(SoftDeleteModel):
    display_id = models.CharField(max_length=20)
    session_id = models.CharField(max_length=100)
    segment_id = models.CharField(max_length=100,default = '')
    user = models.ForeignKey(UserDetails, on_delete=models.CASCADE)
    search_detail = models.ForeignKey(TransferBookingSearchDetail, on_delete=models.CASCADE)
    payment_detail = models.ForeignKey(TransferBookingPaymentDetail, on_delete=models.CASCADE)
    pax_count = models.IntegerField(null=True, blank=True)
    pax_data = models.CharField(max_length=500,null=True, blank=True)
    confirmation_number = models.CharField(max_length=50,null=True, blank=True)
    booking_ref_no = models.CharField(max_length=100)
    booking_id = models.CharField(max_length=50,null=True, blank=True)
    transfer_id = models.CharField(max_length=50,null=True, blank=True)
    status = models.CharField(max_length=50)
    error = models.CharField(max_length=4000,null=True, blank=True)
    modified_by = models.ForeignKey(UserDetails, on_delete=models.CASCADE, related_name='modified_transferbooking')
    max_passengers = models.CharField(max_length=50,null=True)
    category = models.CharField(max_length=100,null=True)
    max_bags = models.CharField(max_length=20,null=True)
    url = models.CharField(max_length=100,null=True)
    booking_remarks = models.CharField(max_length=4000,null=True)

    def __str__(self):
        return self.display_id

    class Meta:
        managed = False
        db_table = 'transfer_booking'


class TransferBookingContactDetail(SoftDeleteModel):
    booking = models.ForeignKey(TransferBooking, on_delete= models.CASCADE)
    pax_id = models.IntegerField(null=True, blank=True)
    title = models.CharField(max_length=100,null=True, blank=True)
    first_name = models.CharField(max_length=300,null=True, blank=True)
    last_name = models.CharField(max_length=300,null=True, blank=True)
    pan = models.CharField(max_length=500,null=True, blank=True)
    contact_number = models.CharField(max_length=300,null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    email = models.CharField(max_length=100,null=True, blank=True)
    country_code = models.CharField(max_length=10,null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'transfer_booking_contact_detail'

class TransferBookingFareDetail(SoftDeleteModel):
    booking = models.ForeignKey(TransferBooking, on_delete=models.CASCADE)
    published_fare = models.FloatField(null =False,default = 0)
    offered_fare = models.FloatField(null =False,default = 0)
    organization_discount = models.FloatField(null =False,default = 0)
    dist_agent_markup = models.FloatField(null =False,default = 0)
    dist_agent_cashback = models.FloatField(null =False,default = 0)
    fare_breakdown = models.CharField(max_length=4000,null=True, blank=True)
    tax = models.FloatField(null =False,default = 0)
    cancellation_details = models.CharField(max_length=4000,null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'transfer_booking_fare_detail'

class TransferBookingLocationDetail(SoftDeleteModel):
    booking = models.ForeignKey(TransferBooking, on_delete=models.CASCADE)
    type = models.CharField(max_length=50,null=True, blank=True)
    name = models.CharField(max_length=300,null=True, blank=True)
    date = models.CharField(max_length=20,null=True, blank=True)
    time = models.CharField(max_length=10,null=True, blank=True)
    code = models.CharField(max_length=50,null=True, blank=True)
    city_name = models.CharField(max_length=50,null=True, blank=True)
    country = models.CharField(max_length=5,null=True, blank=True)
    AddressLine1 = models.CharField(max_length=400,null=True, blank=True)
    AddressLine2 = models.CharField(max_length=400,null=True, blank=True)
    details = models.CharField(max_length=4000,null=True, blank=True)
    ZipCode = models.CharField(max_length=10,null=True, blank=True)
    transfer_choices = (
        ("pickup", "pickup"),
        ("drop", "drop"),
    )
    transfer_type = models.CharField(max_length=50, choices=transfer_choices)
    
    class Meta:
        managed = False
        db_table = 'transfer_booking_location_detail'