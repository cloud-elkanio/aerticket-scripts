from rest_framework.permissions import BasePermission

from users.models import Permission,LookupPermission


# class HasAPIAccess(BasePermission):
#     def has_permission(self, request, view):
#         if not request.user.is_authenticated:
#             return False
#         url_name = request.resolver_match.view_name
#         if '_$_' in url_name:
#             """ CASE when incorret methods are used in views 
#             put url name in the format : {permission_column_name}_$_{method_name}
#             """
#             method_name = url_name.split('_$_')[1]
#             url_name = url_name.split('_$_')[0]
#         else:
#             method_name = str(request.method)
#             url_name = url_name

#         method_mapping = {
#             "POST":"_create",
#             "GET":"_view",
#             "PUT":"_edit",
#             "DELETE":"_delete"
#         }
#         permission_column =  url_name + str(method_mapping[method_name])
#         user_group = request.user.user_group
#         print("user_group = ",user_group)
#         # import pdb;pdb.set_trace()
#         permission_instance = user_group.permission if user_group else None
#         if not permission_instance:
#             permission_instance = LookupPermission.objects.filter(name__iexact = request.user.role.name.replace("_"," ")).first()  
#         if not permission_instance:
#             return False
#         has_access = permission_instance.__dict__[permission_column]
#         print(permission_column,has_access)
#         return has_access

class HasAPIAccess(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        url_name = request.resolver_match.view_name
        if '_$_' in url_name:
            """ CASE when incorret methods are used in views 
            put url name in the format : {permission_column_name}_$_{method_name}
            """
            method_name = url_name.split('_$_')[1]
            url_name = url_name.split('_$_')[0]
        elif any(item in url_name for item in ['-list','-create','-update','-detail']):
            method_name = str(request.method)
            url_name = url_name.replace('-list','').replace('-create','').replace('-update','').replace('-detail','')
        else:
            method_name = str(request.method)
            url_name = url_name
        method_mapping = {
            "POST":"_create",
            "GET":"_view",
            "PUT":"_edit",
            "DELETE":"_delete",
            "PATCH":"_edit",
        }
        permission_column =  url_name + str(method_mapping[method_name])
        user_group = request.user.user_group
        permission_instance = user_group.permission if user_group else None
        if not permission_instance:
            role_name_data = 'distributer owner' if request.user.role.name.replace("_", " ") == 'distributor owner' else request.user.role.name.replace("_", " ")
            permission_instance = LookupPermission.objects.filter(name__iexact = role_name_data).first()  
        if not permission_instance:
            return False
        has_access = permission_instance.__dict__[permission_column]
        return has_access
    