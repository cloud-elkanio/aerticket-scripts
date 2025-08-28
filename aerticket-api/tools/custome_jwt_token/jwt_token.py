from rest_framework_simplejwt.tokens import RefreshToken

def get_jwt_token(user):
    refresh = RefreshToken.for_user(user)
    return {
    'access_token':str(refresh.access_token),
    'refresh_token' : str(refresh)
    }

     