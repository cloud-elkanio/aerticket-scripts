

from django.db import migrations


def add_default_values(apps, schema_editor):
    obj = apps.get_model('template', 'LookUpNotificationKeys')
    obj.objects.create(name="users_first_name", type="memory")
    obj.objects.create(name="users_last_name", type="memory")
    
class Migration(migrations.Migration):

    dependencies = [
        ('template', '0017_auto_20240906_0741'),
    ]

    operations = [
     migrations.RunPython(add_default_values)
    ]
