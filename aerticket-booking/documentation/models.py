from django.db import models

from common.models import SoftDeleteModel
from users.models import Organization

# Create your models here.
class OutApiDetail(SoftDeleteModel):
    status_choice = [ 
                ("Approved", "Approved"),
                ("Rejected", "Rejected"),
                ("Pending", "Pending")
                ]
    status = models.CharField(max_length=200, choices=status_choice)
    token = models.CharField(max_length= 1000, null=True, blank =True)
    exp_time_epoch = models.BigIntegerField(null=True, blank =True)
    organization =  models.ForeignKey(Organization, on_delete=models.CASCADE)

    class Meta:
        db_table = 'out_api_detail'
        ordering = ['-created_at']
        managed = False
        