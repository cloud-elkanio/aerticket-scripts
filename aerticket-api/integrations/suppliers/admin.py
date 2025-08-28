from django.contrib import admin
from .models import *

# Register your models here.
# admin.site.register(LookupSupplierIntegration)
admin.site.register(OrganizationSupplierIntegeration)

class LookupSupplierIntegrationAdmin(admin.ModelAdmin):
    list_filter = [
         "integration_type",
        
    ]
    search_fields = (
        "name",
    )

admin.site.register(LookupSupplierIntegration, LookupSupplierIntegrationAdmin)

class SupplierIntegrationAdmin(admin.ModelAdmin):
    list_filter = [
         "integration_type",
        
    ]
    search_fields = (
        "name",
    )

admin.site.register(SupplierIntegration, SupplierIntegrationAdmin)
