import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.models import User

from users.models import UserDetails

class OutApiJWTAuthentication(BaseAuthentication):
    """
    Custom JWT authentication using a different secret key.
    """

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return None  # No authentication provided

        token = auth_header.split(" ")[1]  # Extract the token

        try:
            decoded_data = jwt.decode(
                token,
                settings.OUT_API_JWT["SIGNING_KEY"],  # Use custom secret key
                algorithms=[settings.OUT_API_JWT["ALGORITHM"]],
            )
            user_id = decoded_data.get("user_id")
            if decoded_data.get("token_type") != "access":
                raise AuthenticationFailed("Invalid token")

            user = UserDetails.objects.filter(id=user_id).first()
            if not user:
                raise AuthenticationFailed("User not found")

            return (user, None)

        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token has expired")
        except jwt.InvalidTokenError:
            raise AuthenticationFailed("Invalid token")
