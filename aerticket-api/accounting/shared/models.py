from django.db import models
from tools.db.models import SoftDeleteModel
from users.models import UserDetails, Organization
from bookings.flight.models import Booking
import uuid

# Create your models here.


class CreditLog(SoftDeleteModel):
    credit_type_choices = (
        ("credit_limit", "credit_limit"),
        ("available_balance", "available_balance"),
    )
    user = models.ForeignKey(
        UserDetails, on_delete=models.CASCADE, null=True, blank=True
    )
    ammount = models.DecimalField(max_digits=10, decimal_places=2)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    credit_type = models.CharField(max_length=100, choices=credit_type_choices)
    log_message = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self) -> str:
        return str(self.user)


class OrganizationFareAdjustment(SoftDeleteModel):
    module_choices = (
        ("flight", "flight"),
        ("hotel", "hotel"),
        ("holiday", "holiday"),
        ("visa", "visa"),
    )

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    cashback = models.FloatField(default=0.0)
    parting_percentage = models.FloatField(default=100.0)
    markup = models.FloatField(default=0.0)
    issued_by = models.ForeignKey(
        UserDetails, on_delete=models.CASCADE, null=True, blank=True
    )
    module = models.CharField(max_length=200, choices=module_choices, default="flight")
    cancellation_charges = models.FloatField(default=0.0)

    def __str__(self) -> str:
        return str(self.organization.organization_name)

    class Meta:
        db_table = "organization_fare_adjustment"
        ordering = ["-created_at"]


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
    cashback = models.FloatField(default=0.0)
    markup = models.FloatField(default=0.0)
    parting_percentage = models.FloatField(default=100.0)
    module = models.CharField(max_length=200, choices=module_choices, default="flight")
    cancellation_charges = models.FloatField(default=0.0)
    available_balance = models.FloatField(default=0.0)
    credit_limit = models.FloatField(default=0.0)

    class Meta:
        db_table = "distributor_agent_fare_adjustment"
        ordering = ["-created_at"]
    def __str__(self):
        return str(self.user.organization.organization_name)

class DistributorAgentFareAdjustmentLog(SoftDeleteModel):
    old_credit_limit = models.FloatField(default=0.0)
    old_available_balance = models.FloatField(default=0.0)
    new_credit_limit = models.FloatField(default=0.0)
    new_available_balance = models.FloatField(default=0.0)


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
        Booking, on_delete=models.CASCADE, null=True, blank=True,related_name="distributor_agent_transaction"
    )
    amount = models.FloatField(default=0.0)

    class Meta:
        db_table = "distributor_agent_transactions"
        ordering = ["-created_at"]


class LookupCreditCard(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, unique=True
    )
    card_type = models.CharField(max_length=50)  # No unique constraint here
    card_number = models.CharField(max_length=50, unique=True)
    internal_id = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "lookup_credit_card"
        verbose_name = "Credit Card"
        verbose_name_plural = "Credit Cards"
        ordering = ["card_type"]

    def __str__(self):
        masked_number = (
            f"XXXX XXXX XXXX {self.card_number[-4:]}"  # Mask all but the last 4 digits
        )
        return f"{self.card_type} - {masked_number}"


class LookupEasyLinkSupplier(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, unique=True
    )
    display_id = models.CharField(max_length=200)
    supplier_id = models.CharField(
        max_length=100, unique=True
    )  # Card number should remain unique

    class Meta:
        db_table = "lookup_easylink_supplier"
        verbose_name = "Easy Link Supplier"
        verbose_name_plural = "Easy Link Suppliers"
        ordering = ["display_id"]

    def __str__(self):
        return f"{self.display_id}"


class PaymentUpdates(SoftDeleteModel):
    choices = (
        ("pending", "pending"),
        ("approve", "approve"),
        ("reject", "reject"),
    )
    agency_name = models.CharField(max_length=100, null=True, blank=True)
    agency = models.ForeignKey(
        UserDetails, on_delete=models.CASCADE, null=True, blank=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    attachment_url = models.CharField(max_length=200, null=True, blank=True)
    date = models.DateField()
    remarks = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=choices, default="pending")

    class Meta:
        db_table = "payment-updates"
        ordering = ["-created_at"]


# class RechargePayment(SoftDeleteModel):
#     choices=(
#         ('unpaid','unpaid'),
#         ('paid','paid'),
#     )
#     agency = models.ForeignKey(UserDetails, on_delete=models.CASCADE, null=True, blank=True)
#     amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
#     payment_gateway = models.CharField(max_length=50, null=True, blank=True, default="razorpay")
#     payment_id_link = models.CharField(max_length=100, null=True, blank=True)
#     remarks = models.TextField(null=True, blank=True)
#     call_back = models.BooleanField(default=False)
#     status = models.CharField(max_length=20, choices=choices, default="unpaid")

#     class Meta:
#         db_table = 'recharge-payment'
#         ordering = ['-created_at']


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
        ('net_banking','net_banking')
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
