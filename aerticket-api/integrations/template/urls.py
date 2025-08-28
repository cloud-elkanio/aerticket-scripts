from django.urls import path, include

from .views import *

from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'notification/template', NotificationTemplateViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('notification/type',NotificationType.as_view()),
    path('notification/keys/', NotificationKeys.as_view()),
    path('notification/events/',NotificationEvents.as_view()),
    path('notification/variables/',NotificationVariables.as_view()),
    
]