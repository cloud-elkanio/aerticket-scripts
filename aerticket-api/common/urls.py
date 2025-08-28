from django.urls import path
from .views import *

urlpatterns = [
    path('module-choices/', ModuleChoicesView.as_view(), name='module-choices'),
    path('upload-gallery/', GalleryUploadView.as_view(),name='upload-gallery'),
    path('gallery/', GalleryListView.as_view(), name='gallery-list'),
    path('gallery/<uuid:id>/update/', GalleryUpdateView.as_view(), name='gallery-update'),
    path('country/calling/code', CountryCallingCode.as_view()),
    path('create-razorpay-payment-link/',RazorpayPaymentLinkCreationView.as_view(),name='razorpay'),
    path('create-stripe-payment-link/',StripePaymentLinkCreationView.as_view(),name='stripe'),
    path('api/invoke',InvokeNotificationView.as_view(), name = 'api/invoke'),
    path('organization-list',GetOrganisationListView.as_view(), name = 'organisation-list'),
    path('invoke/event',InvokeEventNotificationView.as_view()),
    path('invoke/share/fare',ShareFareView.as_view()),
    path('hdfc/callbackurl',VirtualAccountTranslationAPI.as_view()),

    path('transfer/invoke/event',InvokeEventNotificationTransferView.as_view()),
    path('bus/invoke/event',InvokeEventNotificationBusView.as_view()),
    path('hotel/invoke/event',InvokeEventNotificationHotelView.as_view()),

    

# 
    

]
