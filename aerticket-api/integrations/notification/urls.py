from django.contrib import admin
from django.urls import path, include
from .views import *
from rest_framework.routers import DefaultRouter




urlpatterns = [
        # --------notification-------------------------------------------------------------------------------
    path('notification/types/list',IntegrationNotifcationTypes.as_view()),
    path('notification/methods/list',IntegerationMethodsList.as_view()),
    path('notification/list/',IntegerationNotificationList.as_view()),
    path('notification/create', IntegerationNotificationcreate.as_view()),
    path('notification/update', IntegerationNotificationUpdate.as_view(), name = 'admin1space1panel_communication'),
    path('notification/update/<str:id>', IntegerationNotificationUpdate.as_view(), name = 'notification/update'),
    path('notification/default/values', IntegerationDefaultValue.as_view()),
    path('temp-migrate', TempMigrate.as_view())
    # ---end----notification-----------------------------------------------------------------------------
]