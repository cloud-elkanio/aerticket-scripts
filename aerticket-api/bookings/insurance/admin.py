from django.contrib import admin
from .models import *

admin.site.register(InsuranceBookingSearchDetail)
admin.site.register(InsuranceBookingPaymentDetail)
admin.site.register(InsuranceBooking)
admin.site.register(InsuranceBookingPaxDetail)
admin.site.register(InsuranceBookingFareDetail)
admin.site.register(InsuranceAsegoPremiumChart)
admin.site.register(InsuranceAsegoPlanRider)
admin.site.register(InsuranceAsegoRiderMaster)
admin.site.register(InsuranceAsegoPlan)
admin.site.register(InsuranceAsegoCategory)
admin.site.register(InsuranceAsegoVisitingCountry)