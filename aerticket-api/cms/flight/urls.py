from .views import *
from django.urls import path

urlpatterns = [
    path("api/user-ip/", UserIP.as_view(), name="user-ip"),
    # path("upload/", GalleryUploadView.as_view(), name="gallery-upload"),
]
