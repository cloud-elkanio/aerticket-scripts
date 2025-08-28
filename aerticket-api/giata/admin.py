from django.contrib import admin

from .models import *
# Register your models here.


class GiataProviderCodeAdmin(admin.ModelAdmin):
    list_display = ('provider_name','provider_type','provider_code',)
    search_fields = ['provider_name','provider_code','provider_type']
    # list_filter = ('Date Created','Date Updated',)

class GiataPropertiesAdmin(admin.ModelAdmin):
    list_display = ('name','city_id','street','rating',)
    search_fields = ['name','city_id__city_name']
class GiataCityAdmin(admin.ModelAdmin):
    search_fields = ['city_name']

admin.site.register(GiataCountry)
admin.site.register(GiataDestination)
admin.site.register(GiataCity,GiataCityAdmin)
admin.site.register(GiataProperties,GiataPropertiesAdmin)
admin.site.register(GiataProviderCode,GiataProviderCodeAdmin)
admin.site.register(GiataPropertyImage)
admin.site.register(GiataFactsheet)
admin.site.register(GiataTexts)
class GiataErrorLogAdmin(admin.ModelAdmin):
    readonly_fields = ('time_date',)
    list_display = ('error_message', 'time_date')
admin.site.register(GiataErrorLog, GiataErrorLogAdmin)

admin.site.register(GiataChain)


# Register your models here.
