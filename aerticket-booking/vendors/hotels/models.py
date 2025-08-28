from django.db import models
from django.contrib.postgres.fields import ArrayField

from common.models import PaymentDetail, Payments, SoftDeleteModel
from users.models import SupplierIntegration, UserDetails
import uuid
from django.utils import timezone
import time

# Create your models here.

class GiataCountry(SoftDeleteModel):
    country_name = models.CharField(max_length=500)
    country_code = models.CharField(max_length=500)
    lastupdated_epoch = models.BigIntegerField(default=0)

    class Meta:
        db_table = 'giata_country'
        managed = False

    def __str__(self):
        return self.country_name

class GiataDestination(SoftDeleteModel):
    country_id = models.ForeignKey(GiataCountry,on_delete=models.CASCADE)
    destination_name = models.CharField(max_length=500)
    destination_id = models.CharField(max_length=500)
    lastupdated_epoch = models.BigIntegerField(default=0)

    class Meta:
        db_table = 'giata_destination'
        managed = False

    def __str__(self):
        return self.destination_name
class GiataCity(SoftDeleteModel):
    destination_id = models.ForeignKey(GiataDestination,on_delete=models.CASCADE)
    city_name = models.CharField(max_length=500)
    city_id = models.CharField(max_length=500)
    tbo_id = models.CharField(max_length=500,null=True, blank = True)
    lastupdated_epoch = models.BigIntegerField(default=0)

    class Meta:
        db_table = 'giata_city'
        managed = False

    def __str__(self):
        return self.city_name
    
class GiataProperties(SoftDeleteModel):
    city_id = models.ForeignKey(GiataCity,on_delete=models.CASCADE)
    giata_id = models.CharField(max_length=300)
    last_updated = models.CharField(max_length=100, null=True, blank=True)  # ISO format "YYYY-MM-DDTHH:MM:SS"
    name = models.CharField(max_length=500)
    street = models.CharField(max_length=500, null=True, blank=True)
    address = ArrayField(models.CharField(max_length=1000),null=True, blank=True)
    postal_code = models.CharField(max_length=300, null=True, blank=True)
    po_box = models.CharField(max_length=300, null=True, blank=True)
    phone = ArrayField(models.CharField(max_length=200), null=True, blank=True)
    email = ArrayField(models.CharField(max_length=200), null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'giata_properties'
        managed = False
        
    def __str__(self):
        return self.name

class GiataProviderCode(SoftDeleteModel):
    property_id = models.ForeignKey(GiataProperties, on_delete=models.CASCADE)
    provider_name = models.CharField(max_length=500, null=True, blank=True)
    provider_type = models.CharField(max_length=500, null=True, blank=True)
    provider_code = ArrayField(models.CharField(max_length=500), null=True, blank=True)

    class Meta:
        db_table = 'giata_provider_code'
        managed =False
        
    def __str__(self):
        return self.provider_name

# class VendorCity(SoftDeleteModel):
#     vendor = models.ForeignKey(SupplierIntegration, on_delete=models.CASCADE)
#     city_name = models.CharField(max_length=500)
#     vendor_city_code = models.CharField(max_length=500)
#     giata_city_code = 

    
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

class HotelDetails(SoftDeleteModel):
    hotel_code = models.CharField(max_length=100, unique=True)
    heading = models.CharField(max_length=100)
    address = models.TextField(null=True,blank=True)
    latitude = models.CharField(max_length=300, null=True,blank=True)
    longitude = models.CharField(max_length=300, null=True,blank=True)
    latitude = models.CharField(max_length=300, null=True,blank=True)
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
        managed = False

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
        managed = False

class HotelBooking(SoftDeleteModel):
    """Stores user bookings with vendor, hotel, and room details."""
    STATUS_CHOICES = [
        ('enquiry','enquiry'),
        ('pending', 'pending'),
        ('confirmed', 'confirmed'),
        ('partially_confirmed', 'partially_confirmed'),
        ('failed', 'failed'),
        ('partially_cancelled', 'partially_cancelled'),
        ('rejected', 'rejected'),
        ('cancelled', 'cancelled'),
        
    ]

    created_by = models.ForeignKey(UserDetails, on_delete=models.CASCADE)
    hotel = models.ForeignKey(HotelDetails, 
                              on_delete=models.SET_NULL,null = True,blank = True)
    payment = models.OneToOneField(PaymentDetail, on_delete=models.CASCADE,related_name="hotel_booking")
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
        return f"Booking {self.id} - {self.hotel.heading if self.hotel else ''} ({self.status})"
    
    class Meta:
        db_table = 'hotel_bookings'
        managed = False

class HotelEasylinkBilling(models.Model):
    booking = models.ForeignKey(HotelBooking,on_delete=models.CASCADE)
    key = models.CharField(max_length=300)
    value = models.CharField(max_length=300)
    
    class Meta:
        db_table = 'hotel_easylink_data'
        managed = False


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
    email = models.CharField(max_length=300,null = True,blank = True)
    pan = models.CharField(max_length=300,null = True,blank = True)
    mobile_country_code = models.CharField(max_length=300,null = True,blank = True)
    mobile_no = models.CharField(max_length=300,null = True,blank = True)
    client_nationality = models.CharField(max_length=300,null = True,blank = True)
    pan_company_name = models.CharField(max_length=300,null = True,blank = True)
    # ADD MORE FIELDS BELOW AS PER THE VENDOR BOOKING REQUIREMENT

    def __str__(self):
        return f"Booking Customer {self.id} - {self.hotel.hotel_name} ({self.status})"
    
    class Meta:
        db_table = 'hotel_booking_customers'
        managed = False

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
        managed = False

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
        managed = False



class GrnDestination(SoftDeleteModel):
    code = models.CharField(max_length=300,unique=True)
    name = models.CharField(max_length=300)

    class Meta:
        db_table = 'grn_destinations'
        managed = False


class GrnCity(SoftDeleteModel):
    code = models.CharField(max_length=300,unique=True)
    name = models.CharField(max_length=300)
    destination = models.ForeignKey(GrnDestination, 
                              on_delete=models.SET_NULL,null = True,blank = True)

    class Meta:
        db_table = 'grn_cities'
        managed = False

class GrnHotel(SoftDeleteModel):

    code = models.CharField(max_length=300,unique=True)
    name = models.CharField(max_length=300)
    city = models.ForeignKey(GrnCity, 
                              on_delete=models.SET_NULL,null = True,blank = True)
    destination = models.ForeignKey(GrnDestination, 
                              on_delete=models.SET_NULL,null = True,blank = True)

    class Meta:
        db_table = 'grn_hotels'
        managed = False


