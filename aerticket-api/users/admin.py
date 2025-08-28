from django.contrib import admin
from users.models import *
# Register your models here.



class LookupCountryAdmin(admin.ModelAdmin):
    list_filter = ["country_name"]
    # ordering = ['-id']
    search_fields = ('country_name','country_code')
    list_display = ['country_name','country_code']

admin.site.register(LookupCountry,LookupCountryAdmin)



##


class UserAdmin(admin.ModelAdmin):
    list_filter = ["id","username"]
    # ordering = ['-id']
    search_fields = ('phone_number','email')
    list_display = ['username','email','phone_number','is_active']

admin.site.register(UserDetails,UserAdmin)



class LookUpPermisionInline(admin.TabularInline):
    model = LookupRoles
    extra = 1

class LookupOrganizationTypesAdmin(admin.ModelAdmin):
        inlines = [LookUpPermisionInline]
        list_filter = ["id"]
        search_fields = ('name',"id")
        list_display = ['name']
        
admin.site.register(LookupOrganizationTypes,LookupOrganizationTypesAdmin)

admin.site.register(ErrorLog)











admin.site.register(LookupPermission)
        
        
from django import forms
import csv
from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from .models import LookupRoles
class CustomAdminBase(admin.ModelAdmin):

    # list_filter = ['name', ('created_at', admin.DateFieldListFilter), ('modified_at', admin.DateFieldListFilter)]

    readonly_fields = ['created_at', 'modified_at']

    # Custom method to display formatted HTML in list display
    def colored_start_date(self, obj):
        color = 'red' if obj.created_at < time.time() else 'green'
        return format_html('<span style="color: {};">{}</span>', color, obj.start_date)
    colored_start_date.short_description = 'Start Date'

    # Custom action for exporting to CSV
    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}.csv'.format(meta)
        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([getattr(obj, field) for field in field_names])

        return response

    export_as_csv.short_description = "Export Selected to CSV"
    actions = [export_as_csv]




class LookupRolesAdmin(CustomAdminBase):
        # list_filter = ["name",('created_at', admin.DateFieldListFilter), ('modified_at', admin.DateFieldListFilter)]
        ordering = ['-id']
        search_fields = ('name',"id")
        list_display = ['name','lookup_organization_type']
        
        

admin.site.register(LookupRoles,LookupRolesAdmin)




admin.site.register(Country)
admin.site.register(LookupTemplate)
admin.site.register(LookupTheme)

admin.site.register(OrganizationTheme)
admin.site.register(WhiteLabel)

admin.site.register(Permission)



# Look up integeration











# class LookUpNotificationKeysAdmin(CustomAdminBase):
#         list_filter = ["name",('created_at', admin.DateFieldListFilter), ('modified_at', admin.DateFieldListFilter)]
#         ordering = ['-id']
#         search_fields = ('name',"id")
#         list_display = ['name','integeration_type']

# admin.site.register(LookUpNotificationKeysAdmin,LookUpNotificationKeys)

class LookupAirlineAdmin(admin.ModelAdmin):
    search_fields = ['name','code']

admin.site.register(Organization)
admin.site.register(UserGroup)

admin.site.register(LookupAirports)
admin.site.register(CountryDefault)
admin.site.register(LookupAirline,LookupAirlineAdmin)
admin.site.register(CountryTax)
admin.site.register(OutApiDetail)
admin.site.register(APICriticalTransactionLog)
admin.site.register(WhiteLabelPage)
admin.site.register(FareManagement)

