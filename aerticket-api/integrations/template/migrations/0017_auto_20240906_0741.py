from django.db import migrations


def add_default_values(apps, schema_editor):
    obj = apps.get_model('template', 'LookUpNotificationKeys')
    obj.objects.create(name="TEAM_CREATED_NOTIFICATION", type="event")
    obj.objects.create(name="user_email", type="memory")
    obj.objects.create(name="password", type="memory")
    
class Migration(migrations.Migration):

    dependencies = [
        ('template', '0016_auto_20240906_0458'),
    ]

    operations = [
     migrations.RunPython(add_default_values)
    ]
