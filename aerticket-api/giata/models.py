from django.db import models
from tools.db.models import  SoftDeleteModel
from django.contrib.postgres.fields import ArrayField
# Create your models here.

class GiataCountry(SoftDeleteModel):
    country_name = models.CharField(max_length=500)
    country_code = models.CharField(max_length=500)
    lastupdated_epoch = models.BigIntegerField(default=0)

    class Meta:
        db_table = 'giata_country'

    def __str__(self):
        return self.country_name

class GiataDestination(SoftDeleteModel):
    country_id = models.ForeignKey(GiataCountry,on_delete=models.CASCADE)
    destination_name = models.CharField(max_length=500)
    destination_id = models.CharField(max_length=500)
    lastupdated_epoch = models.BigIntegerField(default=0)

    class Meta:
        db_table = 'giata_destination'

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
    rating = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'giata_properties'
    def __str__(self):
        return self.name
class GiataProviderCode(SoftDeleteModel):
    property_id = models.ForeignKey(GiataProperties, on_delete=models.CASCADE)
    provider_name = models.CharField(max_length=500, null=True, blank=True)
    provider_type = models.CharField(max_length=500, null=True, blank=True)
    provider_code = ArrayField(models.CharField(max_length=500), null=True, blank=True)

    class Meta:
        db_table = 'giata_provider_code'
    def __str__(self):
        return self.provider_name
class GiataPropertyImage(SoftDeleteModel):
    propert_id = models.ForeignKey(GiataProperties, on_delete=models.CASCADE)
    image_type = models.CharField(max_length=400, null = True, blank = True)
    image_list = ArrayField(models.CharField(max_length=500), null=True, blank = True)
    class Meta:
        db_table = 'giata_property_image'

class GiataFactsheet(SoftDeleteModel):
    property_id = models.ForeignKey(GiataProperties, on_delete=models.CASCADE)
    last_updated =  models.CharField(max_length=100, null=True, blank=True)
    class Meta:
        db_table = 'giata_factsheet'

class GiataTexts(SoftDeleteModel):
    propert_id = models.ForeignKey(GiataProperties, on_delete=models.CASCADE)
    type = models.CharField(max_length=200,null=True, blank=True)
    title = models.CharField(max_length=500,null=True, blank=True)
    paragraph = models.TextField(null= True, blank=True)

    class Meta:
        db_table = 'giata_texts'

class GiataErrorLog(SoftDeleteModel):
    error_message = models.CharField(max_length=500, null=True, blank=True)
    time_date = models.DateTimeField(auto_now_add=True)
    traceback = models.TextField(null=True, blank=True)
    giata_id = models.CharField(max_length=100, null= True, blank=True)
    base_url = models.CharField(max_length=100, null=True, blank=True)
    variables = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'giata_error_log'
        ordering = ['-created_at']
    def __str__(self):
        return self.error_message
    

class GiataChain(SoftDeleteModel):
    property_id = models.ForeignKey(GiataProperties, on_delete=models.CASCADE)
    chain_name = models.CharField(max_length=500, null=True, blank=True)
    chain_id = models.CharField(max_length=500, null=True, blank=True)
    chain_code = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = 'giata_chain'
        