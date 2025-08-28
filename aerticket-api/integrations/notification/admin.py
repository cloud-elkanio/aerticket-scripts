from django.contrib import admin
from users.admin import CustomAdminBase
from . models import *

class LookUpIntegerationNotificationAdmin(CustomAdminBase):
        # list_filter = ["name",('created_at', admin.DateFieldListFilter), ('modified_at', admin.DateFieldListFilter)]
        ordering = ['-id']
        search_fields = ('name',"id")
        list_display = ['name','integeration_type']

admin.site.register(LookUpIntegerationNotification,LookUpIntegerationNotificationAdmin)

class NotificationIntegerationAdmin(CustomAdminBase):
        # list_filter = ["name",('created_at', admin.DateFieldListFilter), ('modified_at', admin.DateFieldListFilter)]
        ordering = ['-id']
        search_fields = ('name',"id")
        list_display = ['name','integeration_type']

admin.site.register(NotificationIntegeration,NotificationIntegerationAdmin)






admin.site.register(Notifications)