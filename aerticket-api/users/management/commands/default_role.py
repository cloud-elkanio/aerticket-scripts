from django.core.management.base import BaseCommand
import os
from django.contrib.auth.models import Permission,Group
from tools.roles_and_permision.roles import agency ,test

class Command(BaseCommand):
    help = 'Description of your custom command'

    def handle(self, *args, **options):
        self.implement_default_roles()
        # self.stdout.write(f'This is my custom command!')
    
        

        
    
    def implement_default_roles(self):
        agency_permisison = agency.agency_permissions
        
        
        group_list = [agency_permisison] # what names are addeed inhere you should add below also
        group_name_list_str = ['agency_permisison']
        
        for li in group_list:
            group_name_create = group_name_list_str.pop(0)
            for group in li:
                for app_name , group_name_list in group.items():
                    for group_names in group_name_list:
                        for model_name, permision_list in group_names.items():
                            for permision in permision_list:
                                p = Permission.objects.get(content_type__app_label=app_name.lower(),content_type__model=model_name.lower(),codename=f'{permision.lower()}_{model_name.lower()}')
                                current_group_name  = group_name_create.split('_')[0].lower()
                                group_obj, created = Group.objects.get_or_create(name=current_group_name)
                                if not group_obj.permissions.filter(id=p.id).exists():
                                        group_obj.permissions.add(p)
                                















    def role_finder(self):
        folder_path = 'tools/roles_and_permision/roles'
        files = os.listdir(folder_path)
        for file in files:
            roles = file.split('.')[0]
