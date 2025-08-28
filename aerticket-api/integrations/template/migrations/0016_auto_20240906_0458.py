from django.db import migrations


def add_default_values(apps, schema_editor):
    obj = apps.get_model('template', 'LookUpNotificationKeys')
    if not obj.objects.filter(name="customer_email"):
        obj.objects.create(name="customer_email", type="memory")
    if not obj.objects.filter(name="otp"):
        obj.objects.create(name="otp", type="memory")

class Migration(migrations.Migration):

    dependencies = [
        ('template', '0015_auto_20240810_1038'),
    ]

    operations = [
     migrations.RunPython(add_default_values)
    ]
