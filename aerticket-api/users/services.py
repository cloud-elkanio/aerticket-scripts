import jwt
from api.settings import SECRET_KEY
import datetime
from rest_framework import status
import socket
from .models import UserDetails, LookupRoles, LookupPermission,OrganizationTheme
from django.forms.models import model_to_dict
secret_key = SECRET_KEY
algorithms = "HS256"

def jwt_decode(token):
    
    try:
        decoded_payload = jwt.decode(token, secret_key, algorithms=algorithms)
        return decoded_payload
    except jwt.ExpiredSignatureError:
        return {"message":"token_has_expired","status":status.HTTP_504_GATEWAY_TIMEOUT}
    except jwt.InvalidTokenError:
        return ({"message":"invalid_token","status":status.HTTP_404_NOT_FOUND})
    pass

def jwt_encode(kwargs):
    payload = kwargs
    sec = kwargs.get("sec")
    payload["exp"] = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=sec)
    token = jwt.encode(payload, secret_key, algorithm=algorithms)
    return token

def get_local_ip():
    try:
        # Create a socket and connect to a public server to determine the local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  
            local_ip = s.getsockname()[0]
        return local_ip
    except Exception as e:
        return f"Error fetching local IPv4: {e}"

def structure_permision(permision_dict):
        formated_list = [f'{key}_{str(item).lower()}' for key,item in permision_dict.items()]
        default_dict = {}
        nested_dict = default_dict
        for i in formated_list:
            
            #  we are giving a space eg "control panel"  we need space in between these word our current code doesn't satify
            # that's why we are giving this if condiditon
            # if you want to have space you need to give this key word "1space1"
            # don't forget to change in models we need to update in 2 models lookup and permisison
            
            if "1space1" in i:
                i = ' '.join(i.split('1space1'))
            
            #--------- end space condition ----------
            if "1hyphen1" in i:
                i = '-'.join(i.split('1hyphen1'))

            counter_split = i.split("_")
            splited = i.split("_", len(counter_split) - 2)
            counter = len(splited) - 1
            for letters in splited:
                try:
                    nested_dict = nested_dict[letters]
                except:
                    if counter == 0:
                        perm = letters.split("_")
                        bool_dict = {}
                        for i in range(0, int(len(perm) / 2)):
                            current = perm[i]
                            bool_value = eval(str(perm[i+1]).title())
                            
                            bool_dict[current] = bool_value
                            perm = perm[2:]
                        nested_dict.update(bool_dict)
                        pass
                    else:
                        nested_dict[letters] = {}
                        nested_dict = nested_dict[letters]
                counter -= 1
            nested_dict = default_dict
        return default_dict

def get_model_fields(model):
        fields = model._meta.get_fields()
        remove_fields = [
            "id",
            "is_deleted",
            "deleted_at",
            "created_at",
            "modified_at",
            "deleted_at",
            "name",
        ]
        field_names = [
            field.name
            for field in fields
            if not field.many_to_one and not field.one_to_many
        ]
        return [field for field in field_names if field not in remove_fields]
    
def get_user_permision(user_id, is_super_user):
        user = UserDetails.objects.get(id=user_id)
        # getting all the fieldss of the lookupmodels
        field_names = get_model_fields(LookupPermission)
        # geting the default permision set on lookupmodal
        if is_super_user:
            field_values = {field: True for field in field_names}
        
        else:
            role_id = user.role.id            
            user_role = LookupRoles.objects.filter(id=role_id).first()
            default_permission = user_role.lookup_permission
            if user.user_group:
                default_permission = user.user_group.permission
            # showing all the fields from lookup permision weather it true or false

            field_values = {
                field: getattr(default_permission, field) for field in field_names
            }
        # filtering all the true fields because we just need to show only the permision for the roles
        true_fields_values = {key: values for key, values in field_values.items()}

        # structuring permision for front-end

        strucured_permision = structure_permision(true_fields_values)
        return strucured_permision

def getorganizationtheme(user_obj):
    try:
        theme_obj = OrganizationTheme.objects.filter(organization_id = user_obj).first()
        if theme_obj:
            theme_dict =  model_to_dict(theme_obj, fields=["customer_journey_button_first_color", 
                                                    "customer_journey_button_second_color",
                                                        "general_button_first_color", "general_button_second_color",
                                                        "background_color","nav_bar_text_color",
                                                        "nav_bar_drop_down_color","nav_bar_bg_color",
                                                        "nav_bar_selected_text_color","nav_bar_selected_bg_color",
                                                        "loader_color","customer_journey_text_color",
                                                        "general_button_text_color","template_id"])
            theme_dict['template_name'] = theme_obj.template_id.name
            theme_dict['profile_picture'] = theme_obj.organization_id.profile_picture.url if theme_obj.organization_id.profile_picture else None
            return theme_dict
    except:
        return {}


