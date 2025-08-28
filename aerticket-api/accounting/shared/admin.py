from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(DistributorAgentFareAdjustment)
admin.site.register(LookupCreditCard)
admin.site.register(LookupEasyLinkSupplier)
admin.site.register(PaymentUpdates)
# admin.site.register(DistributorAgentTransaction)
admin.site.register(DistributorAgentFareAdjustmentLog)
admin.site.register(CreditLog)



admin.site.register(Payments)


class DistributorAgentTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "transtransaction_type", "module", "booked_user", "amount")

    def booked_user(self, obj):
        return obj.user.first_name if obj.user else None

admin.site.register(DistributorAgentTransaction, DistributorAgentTransactionAdmin)

admin.site.register(OrganizationFareAdjustment)
