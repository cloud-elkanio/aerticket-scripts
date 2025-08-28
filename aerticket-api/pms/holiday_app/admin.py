from django.contrib import admin
from .models import *
from users.admin import CustomAdminBase
from django.utils.html import format_html

# Register your models here.
admin.site.register(HolidayThemeMaster)
admin.site.register(HolidaySKUImage)
admin.site.register(HolidaySKUInclusion)
admin.site.register(LookUpHolidayEnquiryStatus)
admin.site.register(HolidayEnquiry)
admin.site.register(HolidayEnquiryHistory)





class HolidaySKUAdmin(CustomAdminBase):
        list_filter = ["name","days",('created_at', admin.DateFieldListFilter), ('modified_at', admin.DateFieldListFilter)]
        ordering = ['-id']
        search_fields = ('name',"location")
        list_display = ['name','location',"days","nights","place","organization_id",'get_countries']
        def get_countries(self, obj):
        # Get all associated country names as a comma-separated string
            return ", ".join([country.country_name for country in obj.country.all()])

        get_countries.short_description = "Associated Countries"
admin.site.register(HolidaySKU,HolidaySKUAdmin)

class HolidaySKUPriceAdmin(CustomAdminBase):
    ordering = ['-id']
    list_display = ['sku_id', 'get_country_name', 'price']

    def get_country_name(self, obj):
        return obj.country_id.lookup.country_name  
    get_country_name.short_description = 'Country Name'

admin.site.register(HolidaySKUPrice, HolidaySKUPriceAdmin)

admin.site.register(HolidayFavourite)


class HolidaySKUThemeAdmin(admin.ModelAdmin):
    ordering = ['-created_at']
    search_fields = ('sku_id__name', 'theme_id__name')  
    list_display = ['holiday_name', 'theme_name']

    def holiday_name(self, obj):
        return obj.sku_id.name 

    def theme_name(self, obj):
        return obj.theme_id.name  

    holiday_name.short_description = "Holiday Name"
    theme_name.short_description = "Theme Name"

admin.site.register(HolidaySKUTheme, HolidaySKUThemeAdmin)
