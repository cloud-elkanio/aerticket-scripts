from django.db import models
from tools.db.models import SoftDeleteModel
from common.models import Gallery
from users.models import LookupCountry
from django.contrib.postgres.fields import ArrayField
from ckeditor.fields import RichTextField
from users.models import UserDetails 
from django.utils.text import slugify
from users.models import Country

class VisaTypeMaster(SoftDeleteModel):
    name = models.CharField(max_length= 500)
    icon_url = models.ForeignKey(Gallery , on_delete=models.CASCADE)

    def __str__(self):
        return self.name
    class Meta:
        db_table = 'visa_type_master'
        ordering = ['-created_at']
    

class VisaCategoryMaster(SoftDeleteModel):
    name = models.CharField(max_length= 500)
    icon_url = models.ForeignKey(Gallery , on_delete=models.CASCADE)

    def __str__(self):
        return self.name
    class Meta:
        db_table = 'visa_category_master'
        ordering = ['-created_at']

class VisaSKU(SoftDeleteModel):
    slug = models.SlugField(max_length= 500, unique= True)
    name = models.CharField(max_length= 500)
    type = models.ForeignKey(VisaTypeMaster, on_delete= models.CASCADE)
    category = models.ForeignKey(VisaCategoryMaster, on_delete= models.CASCADE)
    from_country = models.ForeignKey(LookupCountry, on_delete= models.CASCADE, related_name = 'visa_from_country')
    to_country = models.ForeignKey(LookupCountry, on_delete= models.CASCADE , related_name= 'visa_to_country')
    stay_duration = models.CharField(max_length= 300)
    validity = models.CharField(max_length= 500)
    entry_type = models.CharField(max_length= 300)
    processing_time = models.CharField(max_length= 300)
    info =  RichTextField()
    documents_required = models.JSONField()
    faq = models.JSONField()
    status = models.BooleanField(default=True)
    created_by = models.ForeignKey(UserDetails, on_delete= models.CASCADE, related_name='created_visa_sku')
    updated_by = models.ForeignKey(UserDetails, on_delete= models.CASCADE, related_name= 'updated_visa_sku')
    description = models.TextField(null = True, blank = True)
    #
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            base_slug = self.slug
            num = 1
            while VisaSKU.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{num}"
                num += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    class Meta:
        db_table = 'visa_sku'
        ordering = ['-created_at']
    
class VisaSKUImage(SoftDeleteModel):
    sku_id = models.ForeignKey(VisaSKU, on_delete= models.CASCADE)
    gallery_id = models.ForeignKey(Gallery, on_delete= models.CASCADE)

    def __str__(self):
        return self.sku_id.name
    class Meta:
        db_table = 'visa_sku_image'
        ordering = ['-created_at']

class VisaSKUPrice(SoftDeleteModel):
    sku_id = models.ForeignKey(VisaSKU, on_delete= models.CASCADE)
    country_id = models.ForeignKey(Country, on_delete= models.CASCADE)
    price = models.DecimalField(max_digits= 10, decimal_places=2)

    def __str__(self):
        return self.sku_id.name
    class Meta:
        db_table = 'visa_sku_price'
        ordering = ['-created_at']
    
class VisaFavourite(SoftDeleteModel):
    sku_id = models.ForeignKey(VisaSKU, on_delete= models.CASCADE)
    country_id = models.ForeignKey(Country, on_delete=models.CASCADE)

    def __str__(self):
        return self.sku_id.name
    class Meta:
        db_table = 'visa_favourite'
        ordering = ['-created_at']

class LookupVisaEnquiryStatus(SoftDeleteModel):
    name =models.CharField(max_length=5000, null=True)
    is_active = models.BooleanField(default=True)
    progression_order = models.IntegerField(default=0)  

    def __str__(self):
        return self.name
    class Meta:
        db_table = 'lookup_visa_enquiry_status'
        ordering = ['-created_at']


class VisaEnquiry(SoftDeleteModel):
    country = models.ForeignKey(LookupCountry, on_delete=models.CASCADE, null=True)
    user_id = models.ForeignKey(UserDetails, on_delete= models.CASCADE)
    visa_id = models.ForeignKey(VisaSKU, on_delete= models.CASCADE)
    name = models.CharField(max_length=500)
    gender = models.CharField(max_length=300)
    dob = models.DateField(null = True, blank = True)
    place_of_birth = models.CharField(max_length=500)
    email = models.CharField(max_length=500)
    phone_number = models.CharField(max_length=20 , null =True)
    marital_status = models.CharField(max_length=500,null = True, blank = True)
    current_address = models.CharField(max_length=600,null = True, blank = True)
    passport_number = models.CharField(max_length=500,null = True, blank = True)
    date_of_issue = models.DateField(null = True, blank = True)
    date_of_expiry = models.DateField(null = True, blank = True)
    purpose_of_visit = models.CharField(max_length=1000,null = True, blank = True)
    date_of_entry = models.DateField(null = True, blank = True)
    date_of_exit = models.DateField(null = True, blank = True) 
    visa_ref_id = models.TextField()
    pax_count = models.IntegerField(null =True)

    place_of_issue = models.CharField(max_length=600,null = True, blank = True)
    visa_type = models.CharField(max_length=500,null = True, blank = True)
    duration = models.CharField(max_length=400,null = True, blank = True)


    def __str__(self):
        return self.name
    class Meta:
        db_table = 'visa_enquiry' 
        ordering = ['-created_at']

class VisaEnquiryHistory(SoftDeleteModel):
    visa_enquiry = models.ForeignKey(VisaEnquiry, on_delete=models.CASCADE, null =True)
    status_id = models.ForeignKey(LookupVisaEnquiryStatus, on_delete=models.CASCADE)
    updated_by = models.ForeignKey(UserDetails, on_delete=models.CASCADE, null = True)


    class Meta:
        db_table = 'visa_enquiry_history' 
        ordering = ['-created_at']
