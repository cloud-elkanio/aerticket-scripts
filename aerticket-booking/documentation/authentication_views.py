
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import authenticate
import jwt
from django.conf import settings
from datetime import datetime, timedelta
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from documentation.models import OutApiDetail
from users.models import UserDetails
from rest_framework import serializers, status

class OutApiTokenObtainView(APIView):
    """
    Generates JWT access and refresh tokens using the custom secret key.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user:
            # Generate Access Token
            access_payload = {
                "user_id": str(user.id),
                "exp": datetime.utcnow() + settings.OUT_API_JWT["ACCESS_TOKEN_LIFETIME"],
                "iat": datetime.utcnow(),
                "token_type": "access"
            }
            access_token = jwt.encode(
                access_payload,
                settings.OUT_API_JWT["SIGNING_KEY"],
                algorithm=settings.OUT_API_JWT["ALGORITHM"],
            )

            # Generate Refresh Token (Longer expiry)
            refresh_expiry = datetime.utcnow() + settings.OUT_API_JWT["REFRESH_TOKEN_LIFETIME"]
            refresh_payload = {
                "user_id": str(user.id),
                "exp": datetime.utcnow() + settings.OUT_API_JWT["REFRESH_TOKEN_LIFETIME"],
                "iat": datetime.utcnow(),
                "token_type": "refresh"
            }
            refresh_token = jwt.encode(
                refresh_payload,
                settings.OUT_API_JWT["SIGNING_KEY"],
                algorithm=settings.OUT_API_JWT["ALGORITHM"],
            )
            user = UserDetails.objects.filter(id = request.user.id).first()
            org_id = user.organization
            
            exp_time = refresh_expiry.timestamp()
            OutApiDetail.objects.update_or_create(
                    organization = org_id,
                    defaults={
                    "token" : str(refresh_token),
                    "exp_time_epoch" : exp_time
                    }
                )
            return Response({
                "access": access_token,
                "refresh": refresh_token,
                "expiry":exp_time
            })

        return Response({"error": "Invalid credentials"}, status=400)

# Request serializer
class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        help_text="Refresh token to obtain a new access token."
    )

# Successful response serializer
class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField(
        help_text="JWT access token generated from the refresh token."
    )
    expires_at = serializers.CharField(
        help_text="Timestamp (as a string) when the access token will expire."
    )

# Error response serializer
class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField(
        help_text="Error message describing what went wrong."
    )


class RefreshTokenView(APIView):
    """
    Refreshes the access token using the custom refresh token.
    """
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_id="GenerateAccessToken",
        operation_summary="Generate Access Token",
        operation_description="Obtain a new access token by providing a valid refresh token.",
        request_body=RefreshTokenSerializer,
        responses={
            200: TokenResponseSerializer,
            400: ErrorResponseSerializer,
        },
        security=[],
        tags=["Authentication"],
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response({"error": "Refresh token is required"}, status=400)

        try:
            # Decode Refresh Token
            decoded_refresh = jwt.decode(
                refresh_token,
                settings.OUT_API_JWT["SIGNING_KEY"],
                algorithms=[settings.OUT_API_JWT["ALGORITHM"]],
            )
            # Validate Token Type
            if decoded_refresh.get("token_type") != "refresh":
                return Response({"error": "Invalid token type"}, status=401)

            user_id = decoded_refresh.get("user_id")
            
            expires_at = datetime.utcnow() + settings.OUT_API_JWT["ACCESS_TOKEN_LIFETIME"]
            # Generate New Access Token
            new_access_token = jwt.encode(
                {
                    "user_id": str(user_id),
                    "exp": expires_at,
                    "iat": datetime.utcnow(),
                    "token_type": "access"
                },
                settings.OUT_API_JWT["SIGNING_KEY"],
                algorithm=settings.OUT_API_JWT["ALGORITHM"],
            )

            return Response({"access": new_access_token,"expires_at":str(expires_at.timestamp())})

        except jwt.ExpiredSignatureError:
            return Response({"error": "Refresh token has expired"}, status=401)
        except jwt.InvalidTokenError:
            return Response({"error": "Invalid refresh token"}, status=401)


