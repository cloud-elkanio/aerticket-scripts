from django.db import models
from tools.db.models import SoftDeleteModel
from users.models import LookupCountry, UserDetails, Country, Organization
from django.contrib.postgres.fields import ArrayField
from ckeditor.fields import RichTextField
from django.utils.text import slugify
from common.models import Gallery
import uuid
class HolidaySKU(SoftDeleteModel):
    slug = models.SlugField(max_length=500 , unique= True, null= True)
    name = models.CharField(max_length= 500)
    place = models.CharField(max_length=1000, null=True, blank=True)
    location = models.CharField(max_length= 500)
    country = models.ManyToManyField(LookupCountry)
    days = models.IntegerField()
    nights = models.IntegerField()
    inclusions = ArrayField(models.CharField(max_length= 500))
    exclusion = ArrayField(models.CharField(max_length= 500))
    itinerary = models.JSONField()
    overview = RichTextField()
    terms = RichTextField()
    created_by = models.ForeignKey(UserDetails , on_delete=models.CASCADE, related_name = 'created_holiday_sku')
    updated_by = models.ForeignKey(UserDetails , on_delete=models.CASCADE, related_name='updated_holiday_sku')
    STATUS_CHOICES = (
        ('Active', 'Active'),
        ('Pending', 'Pending'),
        ('Inactive', 'Inactive'),
        ('Rejected', 'Rejected'),
    )
    status = models.CharField(max_length= 300, choices= STATUS_CHOICES, null=True)
    organization_id = models.ForeignKey(Organization , on_delete=models.CASCADE, null=True)
    sub_heading = models.CharField(max_length=500, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            base_slug = self.slug
            num = 1
            while HolidaySKU.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{num}"
                num += 1
        super().save(*args, **kwargs)
    class Meta:
        db_table = 'holiday_sku'
        ordering = ['-created_at']


    def __str__(self):
        return self.name

class HolidayThemeMaster(SoftDeleteModel):
    name = models.CharField(max_length= 500)
    icon_url = models.ForeignKey(Gallery, on_delete=models.CASCADE)
    status = models.BooleanField(default = True)

    class Meta:
        db_table = 'holiday_theme_master'
        ordering = ['-created_at']
    def __str__(self):
        return self.name
 
class HolidaySKUTheme(SoftDeleteModel):
    sku_id = models.ForeignKey(HolidaySKU, on_delete=models.CASCADE,related_name='holidayskutheme')
    theme_id = models.ForeignKey(HolidayThemeMaster, on_delete=models.CASCADE)

    class Meta:
        db_table = 'holiday_sku_theme'
        ordering = ['-created_at']
    def __str__(self):
        return self.theme_id.name

class HolidaySKUPrice(SoftDeleteModel):
    sku_id = models.ForeignKey(HolidaySKU, on_delete=models.CASCADE,related_name="holidayskuprice")
    country_id = models.ForeignKey(Country, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    company_markup = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    class Meta:
        db_table = 'holiday_sku_price'
        ordering = ['-created_at']

class HolidaySKUImage(SoftDeleteModel):
    sku_id = models.ForeignKey(HolidaySKU, on_delete=models.CASCADE,related_name="holidayskuimage")
    gallery_id = models.ForeignKey(Gallery, on_delete = models.CASCADE)

    class Meta:
        db_table = 'holiday_sku_image'
        ordering = ['-created_at']

class HolidaySKUInclusion(SoftDeleteModel):
    sku_id = models.ForeignKey(HolidaySKU, on_delete= models.CASCADE,related_name="holidayskuinclusion")
    flight = models.BooleanField(default=False)
    hotel = models.BooleanField(default= False)
    transfer = models.BooleanField(default= False)
    meals = models.BooleanField(default =False)
    visa = models.BooleanField(default = False)
    sight_seeing = models.BooleanField(default = False)

    class Meta:
        db_table = 'holiday_sku_inclusion'
        ordering = ['-created_at']
    

# class M(SoftDeleteModel):
#     id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)



class HolidayEnquiry(SoftDeleteModel):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    holiday_id=models.ForeignKey(HolidaySKU, on_delete=models.CASCADE)
    user=models.ForeignKey(UserDetails, on_delete=models.CASCADE)
    name=models.CharField(max_length=100)
    email=models.EmailField()
    phone=models.CharField(max_length=100)
    city=models.CharField(max_length=200)
    date_of_travel=models.DateField()
    pax_count=models.IntegerField()
    enquiry_ref_id =models.TextField(null=True)
    class Meta:
        db_table = 'holiday_enquiry'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name

class LookUpHolidayEnquiryStatus(SoftDeleteModel):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    name =models.CharField(max_length=5000, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    progression_order = models.IntegerField(default=0)  

    def __str__(self):
        return self.name
    class Meta:
        db_table = 'holiday_enquiry_status'
        ordering = ['-created_at']

class HolidayEnquiryHistory(SoftDeleteModel):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    holiday_enquiry_id=models.ForeignKey(HolidayEnquiry, on_delete=models.CASCADE, null=True)
    status=models.ForeignKey(LookUpHolidayEnquiryStatus, on_delete=models.CASCADE,null=True,blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by= models.ForeignKey(UserDetails , on_delete=models.CASCADE, related_name='updated_holiday_history',null=True)
    class Meta:
        db_table = 'holiday_enquiry_history'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.holiday_enquiry_id.name

class HolidayFavourite(SoftDeleteModel):
    sku_id = models.ForeignKey(HolidaySKU, on_delete= models.CASCADE)
    country_id = models.ForeignKey(Country, on_delete=models.CASCADE, null=True , blank=True)
    class Meta:
        db_table = 'holiday_favourite'
        ordering = ['-created_at']

        