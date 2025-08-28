from django.db import models
import uuid
from users.models import UserDetails,LookupCountry
from integrations.suppliers.models import SupplierIntegration
from django.db import models
from django.utils.timezone import now
from django.db import models
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
        if not self.timestamp:
            self.timestamp = now
            
        self.modified_at = now
        super(SoftDeleteModel, self).save(*args, **kwargs)

class FlightBookingSearchDetails(SoftDeleteModel):
    flight_type = models.CharField(max_length=15)
    journey_type = models.CharField(max_length=15)
    passenger_details = models.CharField(max_length=50, null=True, blank=True)
    cabin_class = models.CharField(max_length=15)
    fare_type = models.CharField(max_length=15)
    timestamp = models.BigIntegerField(null=True, editable=False)

    def __str__(self):
        return f"{self.flight_type} - {self.journey_type} - {self.cabin_class}"

    class Meta:
        db_table = 'flight_booking_search_details'
        verbose_name = 'Flight Booking Search Detail'
        ordering = ['timestamp']

class FlightBookingPaymentDetails(SoftDeleteModel):
    payment_choices = (
        ("wallet", "wallet"),
        ("stripe", "stripe"),
        ("razor_pay", "razor_pay"),
    )
    payment_type = models.CharField(max_length=50, choices=payment_choices)
    status = models.CharField(max_length=50, null=True, blank=True)
    timestamp = models.BigIntegerField(null=True, editable=False)
    new_published_fare = models.FloatField(null =False,default = 0)
    new_offered_fare = models.FloatField(null =False,default = 0)
    supplier_published_fare = models.FloatField(null =False,default = 0)
    supplier_offered_fare = models.FloatField(null =False,default = 0)
    ssr_price = models.FloatField(null =False,default = 0)
    
    def __str__(self):
        return f"{self.payment_type} - {self.status}"

    class Meta:
        db_table = 'flight_booking_payment_details'
        verbose_name = 'Flight Booking Payment Details'
        ordering = ['timestamp']

class Booking(SoftDeleteModel):
    display_id = models.CharField(max_length=50)
    session_id = models.CharField(max_length=50)
    user = models.ForeignKey(UserDetails, on_delete=models.CASCADE, related_name='bookings')
    search_details = models.ForeignKey(
        FlightBookingSearchDetails, on_delete=models.CASCADE, related_name='booking_search'
    )
    gst_details = models.CharField(max_length=500, null=True, blank=True)
    payment_details = models.ForeignKey(FlightBookingPaymentDetails, on_delete=models.CASCADE,null=True, blank=True)
    contact = models.CharField(max_length=500)
    status = models.CharField(max_length=50)
    booked_at = models.PositiveBigIntegerField()
    cancelled_at = models.PositiveBigIntegerField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        UserDetails, on_delete=models.CASCADE, null=True, blank=True, related_name='cancelled_bookings'
    )
    modified_at = models.PositiveBigIntegerField(null=True, blank=True)
    modified_by = models.ForeignKey(
        UserDetails, on_delete=models.CASCADE, null=True, blank=True, related_name='modified_bookings'
    )
    timestamp = models.BigIntegerField(null=True, editable=False)
    source = models.CharField(max_length=25,default='Online')
    is_direct_booking = models.BooleanField(default = True, null = True)

    def __str__(self):
        return f"{self.display_id} - {self.status}"

    class Meta:
        db_table = 'flight_booking'
        
        verbose_name = 'Flight Booking'
        ordering = ['timestamp']

class FlightBookingItineraryDetails(SoftDeleteModel):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    itinerary_key = models.CharField(max_length=100)
    segment_id = models.CharField(max_length=100, null=True, blank=True)
    vendor = models.ForeignKey(SupplierIntegration, on_delete=models.CASCADE)
    status = models.CharField(max_length=100)
    airline_pnr = models.CharField(max_length=100, null=True, blank=True)
    gds_pnr = models.CharField(max_length=100, null=True, blank=True)
    supplier_booking_id = models.CharField(max_length=100, null=True, blank=True)
    old_itinerary = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE, related_name='new_itineraries'
    )
    invoice_id =  models.CharField(max_length=100, null=True, blank=True)
    invoice_number = models.CharField(max_length=100, null=True, blank=True)
    invoice_amount =  models.FloatField(default=0.0)
    misc = models.TextField(null=True, blank=True)
    itinerary_index = models.IntegerField(null=True, editable=False)
    timestamp = models.BigIntegerField(null=True, editable=False)
    error = models.TextField(null=True)
    hold_till = models.CharField(max_length=30, null=True, blank=True, default="N/A")
    default_baggage = models.JSONField(null=True, blank=True, default=dict)
    soft_fail = models.BooleanField(null = True,default=False)

    class Meta:
        db_table = 'flight_booking_itinerary_details'
        verbose_name = 'Flight Booking Itinerary Details'
        ordering = ['timestamp']

class FlightBookingJourneyDetails(SoftDeleteModel):
    itinerary = models.ForeignKey(FlightBookingItineraryDetails, on_delete=models.CASCADE,null=True,blank=True)
    source = models.CharField(max_length=100,null=True,blank=True)
    destination = models.CharField(max_length=100,null=True,blank=True)
    date = models.CharField(max_length=100,null=True,blank=True)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE,null=True,blank=True)
    journey_key = models.CharField(max_length=100,null=True,blank=True)
    timestamp = models.BigIntegerField(null=True, editable=False)

    class Meta:
        db_table = 'flight_booking_journey_details'
        verbose_name = 'Flight Booking Journey Details'
        ordering = ['timestamp']

class FlightBookingPaxDetails(SoftDeleteModel):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    pax_type = models.CharField(max_length=100)
    title = models.CharField(max_length=100, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    gender = models.CharField(max_length=100, null=True, blank=True)
    dob = models.CharField(max_length=100, null=True, blank=True)
    passport = models.CharField(max_length=100, null=True, blank=True)
    passport_expiry = models.CharField(max_length=100, null=True, blank=True)
    passport_issue_date = models.CharField(max_length=100, null=True, blank=True)
    # passport_issue_country_code = models.ForeignKey(
    #     LookupCountry, on_delete=models.CASCADE, null=True, blank=True
    # )
    passport_issue_country_code = models.CharField(max_length=300, null=True, blank=True)
    address_1 = models.CharField(max_length=300, null=True, blank=True)
    address_2 = models.CharField(max_length=300, null=True, blank=True)
    is_lead_pax = models.BooleanField(default=False)
    timestamp = models.BigIntegerField(null=True, editable=False)
    frequent_flyer_number = models.JSONField(null=True, blank = True, default=dict)
    class Meta:
        db_table = 'flight_booking_pax_details'
        verbose_name = 'Flight Booking Pax Details'
        ordering = ['timestamp']

class FlightBookingFareDetails(SoftDeleteModel):
    itinerary = models.ForeignKey(FlightBookingItineraryDetails, on_delete=models.CASCADE)
    published_fare = models.DecimalField(max_digits=10, decimal_places=4)
    offered_fare = models.DecimalField(max_digits=10, decimal_places=4)
    organization_discount = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    dist_agent_markup = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    dist_agent_cashback = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    
    fare_breakdown =  models.CharField(max_length=800, null=True, blank=True)
    
    timestamp = models.BigIntegerField(null=True, editable=False)

    class Meta:
        db_table = 'flight_booking_fare_details'
        verbose_name = 'Flight Booking Fare Details'
        ordering = ['timestamp']

class FlightBookingSegmentDetails(SoftDeleteModel):
    journey = models.ForeignKey(FlightBookingJourneyDetails,null=True, on_delete=models.CASCADE)
    airline_number = models.CharField(max_length=50, null=True, blank=True)
    airline_name = models.CharField(max_length=50, null=True, blank=True)
    airline_code = models.CharField(max_length=50, null=True, blank=True)
    flight_number = models.CharField(max_length=50, null=True, blank=True)
    equipment_type = models.CharField(max_length=50, null=True, blank=True)
    duration = models.PositiveIntegerField()
    origin = models.CharField(max_length=50, null=True, blank=True)
    origin_terminal = models.CharField(max_length=100, null=True, blank=True)
    departure_datetime = models.PositiveBigIntegerField()
    destination = models.CharField(max_length=50, null=True, blank=True)
    destination_terminal = models.CharField(max_length=100, null=True, blank=True)
    arrival_datetime = models.PositiveBigIntegerField()
    index = models.IntegerField()
    timestamp = models.BigIntegerField(null=True, editable=False)

    class Meta:
        db_table = 'flight_booking_segment_details'
        verbose_name = 'Flight Booking Segment Details'
        ordering = ['timestamp']

class FlightBookingSSRDetails(SoftDeleteModel):
    itinerary = models.ForeignKey(FlightBookingItineraryDetails, on_delete=models.CASCADE)
    pax = models.ForeignKey(FlightBookingPaxDetails, on_delete=models.CASCADE)
    is_baggage = models.BooleanField(default=False)
    is_meals = models.BooleanField(default=False)
    is_seats = models.BooleanField(default=False)
    baggage_ssr = models.CharField(max_length=500, null=True, blank=True)
    meals_ssr = models.CharField(max_length=500, null=True, blank=True)
    seats_ssr = models.CharField(max_length=500, null=True, blank=True)
    ssr_id = models.CharField(max_length=50, null=True, blank=True)
    supplier_pax_id = models.CharField(max_length=500, null=True, blank=True)
    supplier_ticket_id = models.CharField(max_length=500, null=True, blank=True)
    supplier_ticket_number = models.CharField(max_length=500, null=True, blank=True)
    timestamp = models.BigIntegerField(null=True, editable=False)
    cancellation_status = models.CharField(max_length=500, null=True, blank=True)
    cancellation_fee = models.JSONField(null = True, default = dict)
    cancellation_info = models.CharField(max_length=500, null=True, blank=True,default = "")

    class Meta:
        db_table = 'flight_booking_ssr_details'
        verbose_name = 'Flight Booking SSR Details'
        ordering = ['timestamp']

class EasyLinkDetails(SoftDeleteModel):
    itinerary = models.ForeignKey(FlightBookingItineraryDetails, on_delete=models.CASCADE)
    payload = models.TextField(blank=True, null=True)
    response = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'easy_link_details'

class FlightBookingAccess(SoftDeleteModel):
    bookingid = models.ForeignKey(Booking, on_delete=models.CASCADE)
    userid = models.ForeignKey(UserDetails, on_delete=models.CASCADE)
    expiry_time = models.BigIntegerField(null=True, editable=False)
    class Meta:
        db_table = 'flight_booking_access'

class FlightBookingUnifiedDetails(SoftDeleteModel):
    itinerary_data_unified = models.JSONField(null = False, blank = False, default = dict)
    itinerary = models.ForeignKey(FlightBookingItineraryDetails, on_delete = models.CASCADE,null=True,blank=True)
    booking = models.ForeignKey(Booking, on_delete = models.CASCADE,null=True,blank=True,default="")
    created_at = models.BigIntegerField(null=True, blank=True)
    fare_details = models.JSONField(null = False, blank = False, default = dict)
    fare_quote = models.JSONField(null = False, blank = False, default = dict)
    ssr_raw = models.JSONField(null = False, blank = False, default = dict)
    misc = models.JSONField(null = False, blank = False, default = dict)

    class Meta:
        db_table = 'flight_booking_unified_details'
        verbose_name = 'Flight Booking Unified Details'
        ordering = ['created_at']