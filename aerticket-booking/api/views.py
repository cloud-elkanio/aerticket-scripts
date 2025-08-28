from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from users.models import UserDetails
import jwt
from api.settings import SECRET_KEY
import datetime
from django.contrib.auth.hashers import check_password
from django.db.models import Q


class HealthCheckView(APIView):
    """
    A simple health check endpoint to verify if the service is reachable.
    Returns HTTP 200 OK if the service is up.
    """
    @swagger_auto_schema(
        operation_id="HealthCheck",
        operation_summary="Health Check",
        operation_description=(
            "Use this endpoint to verify that the service is up and running. "
            "It returns an HTTP 200 status code along with a simple JSON response."
        ),
        responses={
            200: openapi.Response(
                description="System is up and running",
                examples={
                    "application/json": {
                        "status": "ok",
                        "message": "System is healthy."
                    }
                }
            )
        },
        tags=["Health"],
    )

    def get(self, request, *args, **kwargs):
        return Response(
            {"status": "ok", "message": "System is healthy."},
            status=status.HTTP_200_OK
        )

# views.py

from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render
from django.views import View
from django.db.models import Q
from django.conf import settings
from documentation.urls import schema_view

class RedocProtectedView(View):
    template_name = "login.html"  # Your login form template
    logo_url = settings.COMPANY_LOGO_URL

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            # User is already logged in -> display ReDoc
            return schema_view.with_ui('redoc', cache_timeout=0)(request, *args, **kwargs)
        else:
            # Not logged in -> Show login form
            return render(request, self.template_name, {'logo_url': self.logo_url})

    def post(self, request, *args, **kwargs):
        # Handle the login form submission
        email = request.POST.get('email')
        password = request.POST.get('password')

        user_obj = UserDetails.objects.filter(
            Q(email=email) & Q(is_active=True)
        ).first()

        if not user_obj or not check_password(password, user_obj.password):
            return render(
                request,
                self.template_name,
                {
                    'logo_url': self.logo_url,
                    'error': 'Invalid Email or Password.'
                }
            )

        if user_obj.organization.status == "pending":
            return render(
                request,
                self.template_name,
                {
                    'logo_url': self.logo_url,
                    'error': 'Your Organization is under review, please wait.'
                }
            )

        if user_obj.organization.status == "inactive":
            return render(
                request,
                self.template_name,
                {
                    'logo_url': self.logo_url,
                    'error': 'Your Organization is blocked, please contact admin.'
                }
            )

        # Log the user in (session-based)
        login(request, user_obj)
        request.session.set_expiry(86400)  # Set session expiry to 60 seconds
        return redirect('/documentation/redoc/')