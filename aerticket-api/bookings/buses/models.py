from django.db import models
from integrations.suppliers.models import SupplierIntegration
from django.db.models import Index
from users.models import LookupCountry, UserDetails
from tools.db.models import  SoftDeleteModel
from accounting.shared.models import PaymentDetail



class BusCity(models.Model):
    city_id = models.CharField(max_length=500, null=True, blank=True)
    city_name = models.CharField(max_length=1000, null=True, blank=True)
    supplier = models.ForeignKey(SupplierIntegration, null=True, blank=True, on_delete=models.CASCADE)
    created_at = models.FloatField(null=True, blank=True)
    country = models.ForeignKey(LookupCountry, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return str(self.city_name)

    class Meta:
        db_table = 'bus_cities'
        ordering = ['-created_at']
        indexes = [
            Index(fields=['city_name']),
        ]

class BusBookingSearchDetail(SoftDeleteModel):
    travel_date = models.CharField(max_length=50,null=True, blank=True)
    origin = models.ForeignKey(BusCity, on_delete=models.CASCADE, null=True, blank=True, related_name='pickup')
    pickup_id=models.CharField(max_length=100)
    pickup_name=models.CharField(max_length=100)
    pickup_time=models.CharField(max_length=100)
    pickup_address=models.CharField(max_length=100)
    pickup_contact=models.CharField(max_length=100)
    destination = models.ForeignKey(BusCity, on_delete=models.CASCADE, null=True, blank=True, related_name='dropoff')
    dropoff_id= models.CharField(max_length=100)
    dropoff_name= models.CharField(max_length=100)
    dropoff_time=models.CharField(max_length=100)
    dropoff_address= models.CharField(max_length=100)
    dropoff_contact= models.CharField(max_length=100)
    class Meta:
        db_table = 'bus_booking_search_detail'

class BusBookingPaymentDetail(SoftDeleteModel):
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
        db_table = 'bus_booking_payment_detail'

class BusBooking(SoftDeleteModel):
    session_id = models.CharField(max_length=100)
    display_id = models.CharField(max_length=30)
    segment_id = models.CharField(max_length=100,default = '')
    user = models.ForeignKey(UserDetails, on_delete=models.CASCADE)
    search_detail = models.ForeignKey(BusBookingSearchDetail, on_delete=models.CASCADE)
    gst_details = models.CharField(max_length=500, null=True, blank=True)
    bus_payment_details = models.ForeignKey(BusBookingPaymentDetail, on_delete=models.CASCADE)
    pax_count = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=50)
    error = models.CharField(max_length=4000,null=True, blank=True)
    # modified_by = models.ForeignKey(UserDetails, on_delete=models.CASCAD?E, related_name='modified_busbooking')
    contact = models.CharField(max_length=500)
    misc = models.JSONField(null = True, blank = True)
    booked_at = models.PositiveBigIntegerField(null = True, blank = True)
    cancelled_at = models.PositiveBigIntegerField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        UserDetails, on_delete=models.CASCADE, null=True, blank=True, related_name='cancelled_busbookings'
    )
    modified_at = models.PositiveBigIntegerField(null=True, blank=True)
    modified_by = models.ForeignKey(
        UserDetails, on_delete=models.CASCADE, null=True, blank=True, related_name='modified_busbookings'
    )
    departure_time = models.CharField(max_length=100, null=True, blank=True)
    arrival_time = models.CharField(max_length=100, null=True, blank=True)
    bus_type = models.CharField(max_length=200, null=True, blank=True)
    operator = models.CharField(max_length=200, null=True, blank=True)
    provider = models.CharField(max_length=200, null=True, blank=True)
    vendor = models.ForeignKey(SupplierIntegration, null=True, blank=True, on_delete=models.CASCADE)
    pnr = models.CharField(max_length=100, null=True, blank=True)
    invoice_number = models.CharField(max_length=100, null=True, blank=True)
    invoice_amount =  models.FloatField(default=0.0)
    ticket_number = models.CharField(max_length=100, null=True, blank=True)
    cancellation_details =  models.JSONField(null = False, blank = False, default = dict)

    def __str__(self):
        return self.display_id
    class Meta:
        db_table = 'bus_booking'

class BusBookingPaxDetail(SoftDeleteModel):
    booking = models.ForeignKey(BusBooking, on_delete= models.CASCADE)
    title = models.CharField(max_length=100,null=True, blank=True)
    first_name = models.CharField(max_length=300,null=True, blank=True)
    last_name = models.CharField(max_length=300,null=True, blank=True)
    dob = models.CharField(max_length=300,null=True, blank=True)
    seat_id = models.CharField(max_length=300,null=True, blank=True)
    seat_type = models.CharField(max_length=300,null=True, blank=True)
    pax_type = models.CharField(max_length=300,null=True, blank=True)
    gender = models.CharField(max_length=300,null=True, blank=True)
    misc = models.JSONField(null = True, blank = True)
    seat_name = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = 'bus_booking_pax_detail'

class BusBookingFareDetail(SoftDeleteModel):
    pax = models.ForeignKey(BusBookingPaxDetail, on_delete=models.CASCADE)
    published_fare = models.FloatField(null =False,default = 0)
    offered_fare = models.FloatField(null =False,default = 0)
    organization_discount = models.FloatField(null =False,default = 0)
    dist_agent_markup = models.FloatField(null =False,default = 0)
    dist_agent_cashback = models.FloatField(null =False,default = 0)
    fare_breakdown = models.CharField(max_length=4000,null=True, blank=True)
    tax = models.FloatField(null =False,default = 0)

    class Meta:
        db_table = 'bus_booking_fare_detail'
