from tools.integration.email_engine.main import EmailIntegerations
from tools.integration.sms_engine.main import SMSIntegerations
from integrations.notification.models import Notifications, NotificationIntegeration
from users.models import ErrorLog
from tools.integration.send_sms_general import VoicenSMS


def invoke(event, number_list:list = None, email_list:list = None,data:dict = {}):   
    notification_obj_list = Notifications.objects.filter(event__name=event)
    for notification_obj in notification_obj_list:
        if notification_obj.template.integeration_type == "email":
            email_integeration = EmailIntegerations(notification_obj, email_list, data) #  checking which email provider, inside this class
            email_integeration.send_email()

        # #( sms send directly in Login and Resend otp apis)
        # elif notification_obj.template.integeration_type == "sms":
        #         voicensms = VoicenSMS(number_list=number_list,data=data)
        #         voicensms.sms_integration()

def send_sms(number_list=[],data={}):
    voicensms = VoicenSMS(number_list=number_list,data=data)
    voicensms.sms_integration()
