import time
import traceback
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from rest_framework.request import Request
from django.contrib.auth.models import AnonymousUser
from .models import ErrorLog, ErrorLogAdvanced
import logging
import json
import re
from users.models import APICriticalTransactionLog,UserDetails,ErrorLog
from rest_framework_simplejwt.authentication import JWTAuthentication
from api import settings

logger = logging.getLogger(__name__)


def parse_user_agent(user_agent):
    """
    Parses the user agent string to extract operating system and device type.
    """
    os_name = "Unknown OS"
    device_type = "Unknown Device"

    # OS and device type parsing
    if re.search(r'windows nt', user_agent, re.IGNORECASE):
        os_name = "Windows"
    elif re.search(r'mac os x', user_agent, re.IGNORECASE):
        os_name = "Mac OS X"
    elif re.search(r'x11', user_agent, re.IGNORECASE):
        os_name = "Unix"
    elif re.search(r'android', user_agent, re.IGNORECASE):
        os_name = "Android"
    elif re.search(r'iphone|ipad|ipod', user_agent, re.IGNORECASE):
        os_name = "iOS"

    if re.search(r'iphone|ipad|ipod', user_agent, re.IGNORECASE):
        device_type = "Mobile"
    elif re.search(r'android', user_agent, re.IGNORECASE):
        device_type = "Mobile"
    elif re.search(r'tablet', user_agent, re.IGNORECASE):
        device_type = "Tablet"
    else:
        device_type = "Computer"

    return os_name, device_type




class AdvancedErrorLoggingMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        
        logger.debug(f"Exception caught: {exception}")
        error_message = str(exception)
        tb = traceback.format_exc()
        user = request.user if not isinstance(request.user, AnonymousUser) else None
        headers = dict(request.headers)

        if isinstance(request, Request):
            if request.method in ['POST', 'PUT', 'PATCH']:
                post_data = request.data
            else:
                post_data = {}
        else:
            if request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    post_data = json.loads(request.body.decode('utf-8'))
                except ValueError:
                    post_data = {}
            else:
                post_data = {}

        query_params = dict(request.GET)
        
        meta_info = {
            'REMOTE_ADDR': request.META.get('REMOTE_ADDR', 'N/A'),
            'HTTP_HOST': request.META.get('HTTP_HOST', 'N/A'),
            'LOCAL_ADDR': request.META.get('LOCAL_ADDR', 'N/A'),
        }

        # Capture User-Agent
        user_agent = request.META.get('HTTP_USER_AGENT', 'N/A')
        os_name, device_type = parse_user_agent(user_agent)
        
        
        ErrorLogAdvanced.objects.create(
            error_message=error_message,
            traceback=tb,
            path=request.path,
            method=request.method,
            user=user,
            headers=headers,
            query_params=query_params,
            post_data=post_data,
            meta_info=meta_info,
            user_agent=user_agent,
            os_name=os_name,
            device_type=device_type
        )
        
        # with open("a.json", 'w+') as file:
        #     json.dump(str(request.__dict__), file, indent=4)

        return None
    
import time
from urllib.parse import urlparse

class ErrorLogAPICriticalTransaction(MiddlewareMixin):
    def process_request(self, request):
        try:
            if request.method == "GET":
                return
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(token)
                user = jwt_auth.get_user(validated_token)
                user_obj = UserDetails.objects.filter(id=user.id).first()
            else:
                user_obj = None

            LOGGED_URLS = [
            "/update/agency/master", #agency master update
            "/supplier/integration/details", #api management get,post,patch and delete
            "/integeration/notification/update", #communication update(put), get and dlete
            "/integration/detail",  #general integration get , post,patch and delete
            "/notification/template/", #template put, get  
            "/notification/template",
            "/accounting/shared/organization/balance", #credit update get
            "/accounting/shared/update/limit/credit", #credit amount update
            "/toggle-status" ,  #change toggle of user in role assignment page  
            "/hdfc/callbackurl",

                    ]
            current_url = request.path
            if any([True for i in LOGGED_URLS if i in  current_url]):
                request_data = {} 
                if request.method == 'DELETE':
                    query_params = request.GET
                    request_data = dict(query_params)

                elif request.method in ['PUT', 'POST', 'PATCH']:
                    if request.body:
                        request_data = json.loads(request.body.decode("utf-8"))                    
                try:
                    source =  request.headers.get('Origin')
                    if source:
                        url = source
                    else:
                        if settings.DEBUG:
                            url = f'https://dev-api.b2btravelagency.com{current_url}'
                        else:
                            url = f'https://api.b2btravelagency.com{current_url}'
                    current_time = int(time.time())
                    api_log = APICriticalTransactionLog.objects.create(
                        user=user_obj,
                        # url=request.build_absolute_uri(),
                        url=url,
                        type=request.method,
                        payload=request_data,
                        created_time = current_time
                    )
                except Exception as e:
                    current_time = int(time.time())
                    error_message = f"{str(e)}: {current_time}"
                    ErrorLog.objects.create(
                        module="ErrorLogAPICriticalTransaction",
                        erros=error_message
                    )
        except Exception as e:
            print(e)
