from django.contrib import admin
from users.admin import CustomAdminBase
from . models import *

# Register your models here.
class LookUpNotificationKeysAdmin(CustomAdminBase):
        # list_filter = ["name",('created_at', admin.DateFieldListFilter), ('modified_at', admin.DateFieldListFilter)]
        ordering = ['-id']
        search_fields = ('name',"id")
        list_display = ['name']
admin.site.register(LookUpNotificationKeys,LookUpNotificationKeysAdmin)



class NotificationTemplatesAdmin(CustomAdminBase):
        # list_filter = ["name",('created_at', admin.DateFieldListFilter), ('modified_at', admin.DateFieldListFilter)]
        ordering = ['-id']
        search_fields = ('name',"id")
        list_display = ['name']
admin.site.register(NotificationTemplates,NotificationTemplatesAdmin)






