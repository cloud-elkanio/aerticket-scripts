from django.db import models
from django.utils.timezone import now
from django.db import models
from django.utils import timezone
import uuid
from django.contrib.postgres.fields import ArrayField

import time

from accounting.shared.models import PaymentDetail
from integrations.suppliers.models import SupplierIntegration
from users.models import UserDetails

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
        # if not self.timestamp:
        #     self.timestamp = now
            
        self.modified_at = now
        super(SoftDeleteModel, self).save(*args, **kwargs)

class HotelDetails(SoftDeleteModel):
    hotel_code = models.CharField(max_length=100, unique=True)
    heading = models.CharField(max_length=100)
    address = models.TextField(null=True,blank=True)
    latitude = models.CharField(max_length=300, null=True,blank=True)
    longitude = models.CharField(max_length=300, null=True,blank=True)
    description = models.TextField()
    amenities = ArrayField(models.CharField(max_length=100), blank=True, default=list)  # List of amenities
    image = models.CharField(max_length=300, null=True,blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency_code = models.CharField(max_length=10,null=True,blank=True)
    star_rating = models.CharField(max_length=300, null=True,blank=True)
    review_rating = models.CharField(max_length=300, null=True,blank=True)

    def __str__(self):
        return f"HotelDetails {self.id} - {self.hotel_code} ({self.heading})"
    
    class Meta:
        db_table = 'hotel_details'

class HotelRoom(SoftDeleteModel):
    hotel = models.ForeignKey(HotelDetails, 
                              on_delete=models.SET_NULL,null = True,blank = True)
    room_code = models.CharField(max_length=300)
    name = models.CharField(max_length=300, null=True,blank=True)
    features = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency_code = models.CharField(max_length=10,null=True,blank=True)
    booking_data = models.JSONField(default=dict)

    def __str__(self):
        return f"Room Details {self.id} - {self.room_code} ({self.name})"
    
    class Meta:
        db_table = 'hotel_rooms'
class HotelBooking(SoftDeleteModel):
    """Stores user bookings with vendor, hotel, and room details."""
    STATUS_CHOICES = [
        ('enquiry','enquiry'),
        ('pending', 'pending'),
        ('confirmed', 'confirmed'),
        ('partially_confirmed', 'partially_confirmed'),
        ('failed', 'failed'),
        ('partially_cancelled', 'partially_cancelled'),
        ('cancelled', 'cancelled'),
        
    ]

    created_by = models.ForeignKey(UserDetails, on_delete=models.CASCADE)
    hotel = models.ForeignKey(HotelDetails, 
                              on_delete=models.SET_NULL,null = True,blank = True)
    payment = models.OneToOneField(PaymentDetail, on_delete=models.CASCADE,related_name="hotel_booking",null = True,blank = True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    vendor = models.ForeignKey(SupplierIntegration, on_delete=models.CASCADE)
    check_in = models.DateField()
    check_out = models.DateField()
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default='pending')
    display_id = models.CharField(max_length=250,null = True,blank = True)

    vendor_booking_reference = models.CharField(max_length=250,null = True,blank = True)
    vendor_booking_endpoint = models.CharField(max_length=250,null = True,blank = True)
    vendor_booking_payload = models.JSONField(default=dict)
    vendor_booking_response = models.JSONField(default=dict)

    def __str__(self):
        return f"Booking {self.id} - {self.hotel.hotel_code} ({self.status})"
    
    class Meta:
        db_table = 'hotel_bookings'

class HotelEasylinkBilling(models.Model):
    booking = models.ForeignKey(HotelBooking,on_delete=models.CASCADE)
    key = models.CharField(max_length=300)
    value = models.CharField(max_length=300)
    
    class Meta:
        db_table = 'hotel_easylink_data'

class HotelBookingCustomer(SoftDeleteModel):
    """Stores user booking customers."""
    TITLE_CHOICES = [
    ("Mr.", "Mr."),
    ("Ms.", "Ms."),
    ("Mrs.", "Mrs."),
    ("Dr.", "Dr.")

    
    ]
    booking = models.ForeignKey(HotelBooking, 
                              on_delete=models.SET_NULL,null = True,blank = True)
    title = models.CharField(max_length=10,  choices=TITLE_CHOICES)
    first_name = models.CharField(max_length=300,null = True,blank = True)
    last_name = models.CharField(max_length=300,null = True,blank = True)
    last_name = models.CharField(max_length=300,null = True,blank = True)
    email = models.CharField(max_length=300,null = True,blank = True)
    pan = models.CharField(max_length=300,null = True,blank = True)
    mobile_country_code = models.CharField(max_length=300,null = True,blank = True)
    mobile_no = models.CharField(max_length=300,null = True,blank = True)
    client_nationality = models.CharField(max_length=300,null = True,blank = True)
    pan_company_name = models.CharField(max_length=300,null = True,blank = True)
    # ADD MORE FIELDS BELOW AS PER THE VENDOR BOOKING REQUIREMENT

    def __str__(self):
        return f"Booking Customer {self.id}"
    
    class Meta:
        db_table = 'hotel_booking_customers'

class HotelBookedRoom(SoftDeleteModel):
    STATUS_CHOICES = [
        ('in_progress', 'in_progress'),
        ('supplier_booking_started', 'supplier_booking_started'),
        ('supplier_booking_failed', 'supplier_booking_failed'),
        ('supplier_booking_success', 'supplier_booking_success'),
        ('confirmed', 'confirmed'),

    ]
    room = models.ForeignKey(HotelRoom, 
                              on_delete=models.SET_NULL,null = True,blank = True)
    booking = models.ForeignKey(HotelBooking, on_delete=models.CASCADE)
    no_of_rooms = models.IntegerField()
    no_of_adults = models.IntegerField()
    no_of_children = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    vendor_booking_endpoint = models.CharField(max_length=250,null = True,blank = True)
    vendor_booking_payload = models.JSONField(default=dict)
    vendor_booking_response = models.JSONField(default=dict)
    booking_data = models.JSONField(default=dict)

    def __str__(self):
        return f"HotelBookedRoom {self.id} - {self.room.name if self.room else self.room} ({self.status})"
    
    class Meta:
        db_table = 'hotel_booked_rooms'

class HotelBookedRoomPax(SoftDeleteModel):
    TITLE_CHOICES = [
    ("Mr.", "Mr."),
    ("Ms.", "Ms."),
    ("Mrs.", "Mrs."),
    ("Dr.", "Dr.")
    ]
    TYPE_CHOICES = [
        ("ADULT", "ADULT"),
        ("CHILD.", "CHILD"),
    ]
    room = models.ForeignKey(HotelBookedRoom, 
                              on_delete=models.SET_NULL,null = True,blank = True)
    title = models.CharField(max_length=10,  choices=TITLE_CHOICES)
    first_name = models.CharField(max_length=300,null = True,blank = True)
    last_name = models.CharField(max_length=300,null = True,blank = True)
    email = models.CharField(max_length=300,null = True,blank = True)
    pan = models.CharField(max_length=300,null = True,blank = True)
    mobile_country_code = models.CharField(max_length=300,null = True,blank = True)
    mobile_no = models.CharField(max_length=300,null = True,blank = True)
    type = models.CharField(max_length=300,choices=TYPE_CHOICES,null = True,blank = True) # adult/child
    age = models.CharField(max_length=300,null = True,blank = True)
    
    # ADD MORE FIELDS BELOW AS PER THE VENDOR BOOKING REQUIREMENT

    def __str__(self):
        return f"HotelBookedRoomPax {self.room if self.room else self.room} - {self.status}"
    
    class Meta:
        db_table = 'hotel_booked_room_paxes'


class GrnDestination(SoftDeleteModel):
    code = models.CharField(max_length=300,unique=True)
    name = models.CharField(max_length=300)

    class Meta:
        db_table = 'grn_destinations'


class GrnCity(SoftDeleteModel):
    code = models.CharField(max_length=300,unique=True)
    name = models.CharField(max_length=300)
    destination = models.ForeignKey(GrnDestination, 
                              on_delete=models.SET_NULL,null = True,blank = True)

    class Meta:
        db_table = 'grn_cities'

class GrnHotel(SoftDeleteModel):

    code = models.CharField(max_length=300,unique=True)
    name = models.CharField(max_length=300)
    city = models.ForeignKey(GrnCity, 
                              on_delete=models.SET_NULL,null = True,blank = True)
    destination = models.ForeignKey(GrnDestination, 
                              on_delete=models.SET_NULL,null = True,blank = True)
    
    class Meta:
        db_table = 'grn_hotels'
