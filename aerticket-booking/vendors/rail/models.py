from django.db import models
from users.models import UserDetails, Organization
import uuid
import time
from django.utils import timezone
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
        if not self.timestamp:
            self.timestamp = now
            
        self.modified_at = now
        super(SoftDeleteModel, self).save(*args, **kwargs)

class RailOrganizationDetails(SoftDeleteModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    agency_name = models.CharField(max_length=50)
    email = models.CharField(max_length=50)
    pan = models.CharField(max_length=15)
    dob = models.CharField(max_length=15)
    address = models.CharField(max_length=500)
    landmark = models.CharField(max_length=500)
    country = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    city = models.CharField(max_length=50)
    pincode = models.IntegerField(null=False, blank=False)
    created_by = models.ForeignKey(UserDetails, on_delete= models.CASCADE, related_name='created_request')
    updated_by = models.ForeignKey(UserDetails, on_delete= models.CASCADE, related_name= 'modified_request')
    agent_id = models.CharField(max_length=50,null=True, blank=True)
    irctc_id = models.CharField(max_length=50,null=True, blank=True)
    is_active = models.BooleanField(default=False)
    status = models.CharField(max_length=50,default='Pending')
    timestamp = models.BigIntegerField(null=True, editable=False)

    def __str__(self):
        return f"{self.agency_name} - {self.status}"

    class Meta:
        db_table = 'rail_organization_details'
        verbose_name = 'Rail Organization Detail'
        ordering = ['timestamp']
        managed = False

class RailTransactions(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_id = models.CharField(max_length=50,blank=True,null=True)
    # Foreign keys for user and organization mappings. Ensure these models exist.
    user = models.ForeignKey(UserDetails, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    
    # Status field with a default value.
    status = models.CharField(max_length=20, default='Enquiry')
    
    # Fields from the provided dictionary
    merchantCode = models.CharField(max_length=50,null=True, blank=True)
    reservationId = models.CharField(max_length=50,null=True, blank=True)
    txnAmount = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    currencyType = models.CharField(max_length=10,null=True, blank=True)
    appCode = models.CharField(max_length=10,null=True, blank=True)
    pymtMode = models.CharField(max_length=20,null=True, blank=True)
    txnDate = models.CharField(max_length=8,null=True, blank=True)  # Could also use DateField with proper formatting
    securityId = models.CharField(max_length=50,null=True, blank=True)
    RU = models.URLField(null=True, blank=True)
    userID = models.CharField(max_length=50,null=True, blank=True)
    ownerID = models.CharField(max_length=50,null=True, blank=True)
    fixedCharge = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    variableCharge = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    Cgst = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    Sgst = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    Igst = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    totalTxnAmount = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    # Renaming "Class" to "class_field" to avoid using the reserved keyword "class"
    class_field = models.CharField(max_length=10,null=True, blank=True)
    noOfPax = models.PositiveIntegerField(null=True, blank=True)
    maxAgentFeeinclGST = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    maxPGChargeinclGST = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    ticketPrintRate = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    wsUserLogin = models.CharField(max_length=50,null=True, blank=True)
    CheckSum = models.CharField(max_length=100,null=True, blank=True)
    
    def __str__(self):
        return f"Transaction {self.reservationId} ({self.status})"
    
    class Meta:
        db_table = 'rail_transactions'
        verbose_name = 'Rail Transaction Detail'
        managed = False


class RailLedger(models.Model):
    # Django automatically creates an incremental 'id' field.
    user = models.ForeignKey(UserDetails, on_delete=models.CASCADE, blank=True, null=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, blank=True, null=True)
    time_stamp = models.DateTimeField(db_column='TimeStamp', blank=True, null=True)
    previousID = models.CharField(max_length=255, db_column='previousID', blank=True, null=True)
    previousBal = models.CharField(max_length=255, db_column='previousBal', blank=True, null=True)
    refrerenceID = models.CharField(max_length=255, db_column='refrerenceID', blank=True, null=True)
    userID = models.CharField(max_length=255, db_column='userID', blank=True, null=True)
    ownerID = models.CharField(max_length=255, db_column='ownerID', blank=True, null=True)
    accountID = models.CharField(max_length=255, db_column='accountID', blank=True, null=True)
    itemID = models.CharField(max_length=255, db_column='itemID', blank=True, null=True)
    supplierRef = models.CharField(max_length=255, db_column='supplierRef', blank=True, null=True)
    description = models.TextField(db_column='description', blank=True, null=True)
    item_amt = models.CharField(max_length=255, db_column='item_amt', blank=True, null=True)
    charges = models.CharField(max_length=255, db_column='charges', blank=True, null=True)
    SGST = models.CharField(max_length=255, db_column='SGST', blank=True, null=True)
    CGST = models.CharField(max_length=255, db_column='CGST', blank=True, null=True)
    IGST = models.CharField(max_length=255, db_column='IGST', blank=True, null=True)
    commission = models.CharField(max_length=255, db_column='commission', blank=True, null=True)
    TDS = models.CharField(max_length=255, db_column='TDS', blank=True, null=True)
    amt_cr = models.CharField(max_length=255, db_column='amt_cr', blank=True, null=True)
    amt_dr = models.CharField(max_length=255, db_column='amt_dr', blank=True, null=True)
    balanceAmt = models.CharField(max_length=255, db_column='balanceAmt', blank=True, null=True)
    WH_Status = models.CharField(max_length=255, db_column='WH_Status', blank=True, null=True)
    supplierRef1 = models.CharField(max_length=255, db_column='supplierRef1', blank=True, null=True)
    attempt = models.CharField(max_length=255, db_column='attempt', blank=True, null=True)
    mongo_id = models.CharField(max_length=255, db_column='_id', blank=True, null=True)
    journalID = models.CharField(max_length=255, db_column='journalID', blank=True, null=True)
    version = models.CharField(max_length=255, db_column='__v', blank=True, null=True)
    tag = models.CharField(max_length=255, db_column='tag', blank=True, null=True)
    CheckSum = models.CharField(max_length=255, db_column='CheckSum', blank=True, null=True)
    partnerTxnID = models.CharField(max_length=255, db_column='partnerTxnID', blank=True, null=True)
    Last_blockBalance = models.CharField(max_length=255, db_column='Last_blockBalance', blank=True, null=True)
    previous_blockBalance = models.CharField(max_length=255, db_column='previous_blockBalance', blank=True, null=True)

    class Meta:
        db_table = 'rail_ledger'
        verbose_name = 'Rail Ledger'
        managed= False

    def __str__(self):
        return f"Ledger {self.id}"
