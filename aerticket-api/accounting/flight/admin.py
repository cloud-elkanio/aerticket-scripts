from django.contrib import admin
from .models import *

class AirlineDealsDb(admin.ModelAdmin):
    list_filter = ['source','destination','deal_type']
    ordering = ['-created_at']
    search_fields = ('sector','cabin','airline__name','deal_type')
    list_display = ['id','sector','cabin','airline','deal_type']

admin.site.register(AirlineDeals,AirlineDealsDb)
admin.site.register(FlightSupplierFilters)
admin.site.register(SupplierDealManagement)


