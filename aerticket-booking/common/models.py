from django.db import models
import uuid
from users.models import UserDetails,Country,Integration
from users.models import SupplierIntegration
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.timezone import now
from django.utils import timezone
from model_utils import FieldTracker
from django.db.models.functions import Upper

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
        managed=False


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
        managed = False
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
    source = models.CharField(max_length=25,default='Online')

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
    is_direct_booking = models.BooleanField(default = True, null = True)

    class Meta:
        db_table = 'flight_booking'
        managed=False
        verbose_name = 'Flight Booking'


class FlightBookingItineraryDetails(SoftDeleteModel):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE,related_name="flightbookingitinerarydetails_set")
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
    tracker = FieldTracker(fields=['status', 'modified_at'])
    class Meta:
        db_table = 'flight_booking_itinerary_details'
        verbose_name = 'Flight Booking Itinerary Details'
        managed=False

class FlightBookingJourneyDetails(SoftDeleteModel):
    itinerary = models.ForeignKey(FlightBookingItineraryDetails, on_delete=models.CASCADE,null=True,blank=True)
    source = models.CharField(max_length=100,null=True,blank=True)
    destination = models.CharField(max_length=100,null=True,blank=True)
    date = models.CharField(max_length=100,null=True,blank=True)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE,null=True,blank=True,related_name= "flightbookingjourneydetails_set")
    journey_key = models.CharField(max_length=100,null=True,blank=True)
    timestamp = models.BigIntegerField(null=True, editable=False)

    class Meta:
        db_table = 'flight_booking_journey_details'
        verbose_name = 'Flight Booking Journey Details'
        managed=False

class FlightBookingPaxDetails(SoftDeleteModel):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE,related_name = "flightbookingpaxdetails_set")
    pax_type = models.CharField(max_length=100)
    title = models.CharField(max_length=100, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    gender = models.CharField(max_length=100, null=True, blank=True)
    dob = models.CharField(max_length=100, null=True, blank=True)
    passport = models.CharField(max_length=100, null=True, blank=True)
    passport_expiry = models.CharField(max_length=100, null=True, blank=True)
    passport_issue_date = models.CharField(max_length=100, null=True, blank=True)
    passport_issue_country_code = models.CharField(max_length=300, null=True, blank=True)
    address_1 = models.CharField(max_length=300, null=True, blank=True)
    address_2 = models.CharField(max_length=300, null=True, blank=True)
    is_lead_pax = models.BooleanField(default=False)
    timestamp = models.BigIntegerField(null=True, editable=False)
    frequent_flyer_number = models.JSONField(null=True, blank = True, default=dict)
    
    class Meta:
        db_table = 'flight_booking_pax_details'
        verbose_name = 'Flight Booking Pax Details'
        managed=False

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
        managed=False


class FlightBookingSegmentDetails(SoftDeleteModel):
    journey = models.ForeignKey(FlightBookingJourneyDetails,null=True, on_delete=models.CASCADE)
    airline_number = models.CharField(max_length=50, null=True, blank=True)
    airline_name = models.CharField(max_length=50, null=True, blank=True)
    airline_code = models.CharField(max_length=50, null=True, blank=True)
    flight_number = models.CharField(max_length=50, null=True, blank=True)
    equipment_type = models.CharField(max_length=50, null=True, blank=True)
    duration = models.PositiveIntegerField()
    origin = models.CharField(max_length=50, null=True, blank=True)
    origin_terminal = models.CharField(max_length=50, null=True, blank=True)
    departure_datetime = models.PositiveBigIntegerField()
    destination = models.CharField(max_length=50, null=True, blank=True)
    destination_terminal = models.CharField(max_length=50, null=True, blank=True)
    arrival_datetime = models.PositiveBigIntegerField()
    index = models.IntegerField()
    timestamp = models.BigIntegerField(null=True, editable=False)

    class Meta:
        db_table = 'flight_booking_segment_details'
        verbose_name = 'Flight Booking Segment Details'
        managed = False

class FlightBookingSSRDetails(SoftDeleteModel):
    itinerary = models.ForeignKey(FlightBookingItineraryDetails, on_delete=models.CASCADE,related_name = "flightbookingssrdetails_set")
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
        managed = False

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
        managed = False

class EasyLinkDetails(SoftDeleteModel):
    flight_booking_payment_details = models.ForeignKey(FlightBookingPaymentDetails, on_delete=models.CASCADE)
    XORef = models.CharField(max_length=50) 
    CustCode = models.CharField(max_length=50)  
    suppcode = models.CharField(max_length=50, blank=True, null=True)
    AirCode = models.CharField(max_length=50)
    diflg = models.CharField(max_length=1)
    PNRAir = models.CharField(max_length=50, blank=True, null=True)
    PNRCrs = models.CharField(max_length=50, blank=True, null=True)
    tktRef = models.CharField(max_length=50)
    tktNo = models.CharField(max_length=50)
    tktDt = models.DateField()
    tkttype = models.CharField(max_length=1)
    RCFlag = models.CharField(max_length=50, blank=True, null=True)
    ReftktNo = models.CharField(max_length=50, blank=True, null=True)
    Region = models.CharField(max_length=50, blank=True, null=True)
    ReftktDt = models.DateField(blank=True, null=True)
    AirCCNo = models.CharField(max_length=50, blank=True, null=True)
    PaxName = models.CharField(max_length=100)
    Sector = models.CharField(max_length=50)
    CRS = models.CharField(max_length=2)
    FareBasis = models.CharField(max_length=50, blank=True, null=True)
    DealCode = models.CharField(max_length=50, blank=True, null=True)

    # Sectors and Flight Information
    S1Sector = models.CharField(max_length=50) 
    S1FltNo = models.CharField(max_length=10)
    S1Date = models.DateField()
    S1Class = models.CharField(max_length=10, blank=True, null=True)
    S1FltType = models.CharField(max_length=10, blank=True, null=True)

    
    S2Sector = models.CharField(max_length=50, blank=True, null=True)
    S2FltNo = models.CharField(max_length=10, blank=True, null=True)
    S2Date = models.DateField(blank=True, null=True)
    S2Class = models.CharField(max_length=10, blank=True, null=True)
    S2FltType = models.CharField(max_length=10, blank=True, null=True)


    BasicFare = models.DecimalField(max_digits=10, decimal_places=4)
    AddlAmt = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    SuppAddlAmt = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    NC1Tax = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    NC1AddlAmt = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    


    CustStdComm = models.DecimalField(max_digits=10, decimal_places=4)
    CustCPInc = models.DecimalField(max_digits=10, decimal_places=4)
    CustNCPInc = models.DecimalField(max_digits=10, decimal_places=4)
    CustPLB = models.DecimalField(max_digits=10, decimal_places=4)
    CustOR = models.DecimalField(max_digits=10, decimal_places=4)
    CustSrvChrgs = models.DecimalField(max_digits=10, decimal_places=4)
    CustMGTFee = models.DecimalField(max_digits=10, decimal_places=4)

    PercTDS = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    TDS = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    CustPercTDS = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    CustTDS = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)

    sGTAX = models.CharField(max_length=1, blank=True, null=True)
    PercGTAX = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    GTAX = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    sCustGTAX = models.CharField(max_length=1, blank=True, null=True)
    CustPercGTAX = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    CustGTAX = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    CustGTAXAdl = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)


    CustSCPercGTAX = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    CustSCGTAX = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    CustSCPercSrch = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    CustSCSrch = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)

    credittype = models.CharField(max_length=50, blank=True, null=True)
    timestamp = models.BigIntegerField(null=True, editable=False)

    def __str__(self):
        return f"Booking {self.XORef} for {self.PaxName}"
    
    
    class Meta:
        db_table = 'easy_link_details'
        verbose_name = 'easy_link_details'
        managed=False


class LookupEasyLinkSupplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    display_id = models.CharField(max_length=200)  
    supplier_id = models.CharField(max_length=100, unique=True)  # Card number should remain unique

    class Meta:
        db_table = 'lookup_easylink_supplier'
        verbose_name = 'Easy Link Supplier'
        verbose_name_plural = 'Easy Link Suppliers'
        ordering = ['display_id']
        managed = False

    def __str__(self):
        return f"{self.display_id}"
    
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

class Payments(SoftDeleteModel):
    choices = (
        ("unpaid", "unpaid"),
        ("paid", "paid"),
    )
    payment_choices = (("recharge", "recharge"), ("booking", "booking"))
    agency = models.ForeignKey(
        UserDetails, on_delete=models.CASCADE, null=True, blank=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_types = models.CharField(
        max_length=20, choices=payment_choices, default="recharge"
    )
    payment_gateway = models.CharField(
        max_length=50, null=True, blank=True, default="razorpay"
    )
    payment_id_link = models.CharField(max_length=100, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    call_back = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=choices, default="unpaid")

    class Meta:
        managed = False 
        db_table = "payments"
        ordering = ["-created_at"]


class PaymentDetail(SoftDeleteModel):
    """Stores payment transactions linked to bookings."""
    STATUS_CHOICES = [
        ('pending', 'pending'),
        ('success', 'success'),
        ('failed', 'failed'),
    ]
    PAYMENT_METHODS = [
        ('wallet', 'wallet'),
        ('upi', 'upi'),
        ('credit_card', 'credit_card'),
        ('debit_card', 'debit_card'),
    ]
    PAYMENT_HANDLERS = [
        ('HotelManager', 'HotelManager'),
        ('FlightManager', 'FlightManager'),
        ('BusManager', 'BusManager'),
        ('TransfersManager', 'TransfersManager'),
        ('RailManager', 'RailManager')
        #ADD PAYMENT HANDLING CLASSES HERE

    ]
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey(UserDetails, on_delete=models.SET_NULL,null=True,blank=True)
    payment_method = models.CharField(max_length=100, choices=PAYMENT_METHODS,null=True,blank = True)
    payment_handler = models.CharField(max_length=100, choices=PAYMENT_HANDLERS)
    payment = models.ForeignKey(Payments,null=True,blank=True,on_delete=models.SET_NULL,related_name='payment_detail')

    order_api_endpoint = models.CharField(max_length=250,null = True,blank = True)
    order_api_payload = models.JSONField(default=dict)
    order_api_response = models.JSONField(default=dict)

    is_callback_recieved = models.BooleanField(default = False) # for preventing multiple booking api call
    callback_payload = models.JSONField(default=dict)


    def __str__(self):
        return f"PaymentDetail {self.id} - {self.status}"
    
    class Meta:
        db_table = 'payment_details'
        managed = False


class ErrorLog(SoftDeleteModel):
    module = models.TextField()
    erros = models.JSONField()
    class Meta:
        managed = False
        ordering = ['-created_at']
    def __str__(self):
        return str(self.module)
    
class FlightBookingAccess(SoftDeleteModel):
    bookingid = models.ForeignKey(Booking, on_delete=models.CASCADE,related_name = "flightbookingaccess_set")
    userid = models.ForeignKey(UserDetails, on_delete=models.CASCADE)
    expiry_time = models.BigIntegerField(null=True, editable=False)
    class Meta:
        db_table = 'flight_booking_access'

class FlightBookingUnifiedDetails(SoftDeleteModel):
    itinerary_data_unified = models.JSONField(null = False, blank = False, default = dict)
    itinerary = models.ForeignKey(FlightBookingItineraryDetails, on_delete = models.CASCADE,null=True,blank=True,
                                  related_name = "flightbookingunifieddetailsitinerary_set")
    created_at = models.BigIntegerField(null=True, blank=True)
    booking = models.ForeignKey(Booking, on_delete = models.CASCADE,null=True,blank=True,default="",
                                related_name = "flightbookingunifieddetails_set")
    fare_details = models.JSONField(null = False, blank = False, default = dict)
    fare_quote = models.JSONField(null = False, blank = False, default = dict)
    ssr_raw = models.JSONField(null = False, blank = False, default = dict)
    misc = models.JSONField(null = False, blank = False, default = dict)

    class Meta:
        managed = False
        db_table = 'flight_booking_unified_details'
        verbose_name = 'Flight Booking Unified Details'
        ordering = ['created_at']
        
class LookupCountry(SoftDeleteModel):
    country_name = models.CharField(max_length=200)
    country_code = models.CharField(max_length=300)
    is_active = models.BooleanField(default=True)
    calling_code = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        db_table = 'lookup_country'
        ordering = ['-created_at']
        managed = False
        
    def __str__(self) -> str:
        return self.country_name

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
        ordering = ['code']
        managed = False

class LookupAirline(SoftDeleteModel):
    name = models.CharField(max_length=500, null = True)
    code = models.CharField(max_length=500 , null = True)
    def __str__(self):
        return str(self.name)
    class Meta:
        db_table = 'lookup_airline'
        ordering = ['code']
        managed = False

class DailyCounter(models.Model):
    module_choices = (
        ("flight", "flight"),
        ("hotel", "hotel"),
        ("holiday", "holiday"),
        ("visa", "visa"),
        ('transfers','transfers'),
        ('bus','bus'),
        ('rail','rail'),
        ('insurance','insurance')
    )
    date = models.DateField(db_index=True)  # Add explicit index
    count = models.PositiveIntegerField(default=0)
    module = models.CharField(max_length=200, choices=module_choices, default="flight")

    class Meta:
        db_table = 'daily_counter'
        managed = False

class FareManagement(SoftDeleteModel):
    supplier_id = models.ForeignKey(SupplierIntegration,  on_delete=models.CASCADE)
    supplier_fare_name = models.CharField(max_length=500)
    brand_name = models.CharField(max_length=500)
    priority = models.IntegerField()
    class Meta:
        db_table = 'fare_management'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                Upper('supplier_fare_name'),
                'supplier_id',
                name='unique_supplier_id_fare_name')
            # ),
            # models.UniqueConstraint(
            #     Upper('brand_name'),
            #     'priority',
            #     name='unique_UniqueConstraint_priority')
        ]
    def __str__(self):
        return f"{self.brand_name} - {self.supplier_id.name} - {self.supplier_fare_name}"