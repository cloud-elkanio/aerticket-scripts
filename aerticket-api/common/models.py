from django.db import models
from tools.db.models import SoftDeleteModel
from users.models import Organization

class Gallery(SoftDeleteModel):
    module_choices=( 
        ("flight", "flight"),
        ("hotel", "hotel"),
        ("holiday", "holiday"),
        ("visa", "visa"),
        ('transfers','transfers'),
        ('rail','rail'),
        ('bus','bus'),
        ('insurance','insurance'),

    )
    name = models.CharField(max_length=500)
    alternative_text=models.CharField(max_length=400,null=True,blank=True)
    url = models.ImageField(upload_to = 'btob/gallery')
    module = models.CharField(max_length= 400,choices=module_choices)

    class Meta:
        db_table = 'gallery_bta'
        ordering = ['-created_at']


class VirtualAccountTransaction(SoftDeleteModel):
    alert_sequence_no = models.CharField(max_length=400, unique=True)
    virtual_account = models.CharField(max_length=400,null=True,blank=True)
    account_number = models.CharField(max_length=400)
    debit_credit = models.CharField(max_length=400)
    amount = models.CharField(max_length=400)
    remitter_name = models.CharField(max_length=400,null=True,blank=True)
    remitter_account = models.CharField(max_length=400,null=True,blank=True)
    remitter_bank = models.CharField(max_length=400,null=True,blank=True)
    remitter_IFSC = models.CharField(max_length=400,null=True,blank=True)
    cheque_no = models.CharField(max_length=400,null=True,blank=True)
    user_reference_number = models.CharField(max_length=400,null=True,blank=True)
    mnemonic_code = models.CharField(max_length=400,null=True,blank=True)
    value_date = models.CharField(max_length=400,null=True,blank=True)
    transaction_description = models.CharField(max_length=400,null=True,blank=True)
    transaction_date = models.CharField(max_length=400,null=True,blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
    easylink_status = models.BooleanField(default=False)
       
    class Meta:
        db_table = 'virtual_account_transaction'

class DailyCounter(models.Model):
    module_choices = (
        ("flight", "flight"),
        ("hotel", "hotel"),
        ("holiday", "holiday"),
        ("visa", "visa"),
        ('transfers','transfers'),
        ('rail','rail'),
        ('bus','bus'),
        ('insurance','insurance'),
    )
    date = models.DateField(db_index=True)  # Add explicit index
    count = models.PositiveIntegerField(default=0)
    module = models.CharField(max_length=200, choices=module_choices, default="flight")

    class Meta:
        db_table = 'daily_counter'
    def __str__(self):
        return str(self.module)
