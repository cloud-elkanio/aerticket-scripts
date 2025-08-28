from integrations.notification.models import Notifications, NotificationIntegeration
from .voice_en_sms import VoiceEnEngine
from users.models import Country


class SMSIntegerations:
    def __init__(self,notification_obj,number_list,data) -> None:
        self.sms_integeration_list:list =  NotificationIntegeration.objects.filter(integeration_type = "sms", is_active = True,
                                                                                     country = self.get_country(data["country_name"]))
        
        self.notification_obj = notification_obj
        self.number_list = number_list
        self.data = data
        
    def send_sms(self):
        for email_provider_obj in  self.sms_integeration_list:
            if email_provider_obj.name == "smtp_go":
                email_server = SmtpEngine(self.notification_obj,self.email_list,self.data,email_provider_obj)
            elif email_provider_obj.name == "Amazon SES":
                email_server = AwsEmailEngine(self.notification_obj,self.email_list,self.data,email_provider_obj)
                email_server.sent_mail()
                
                
    def get_country(self,country_name):
        return Country.objects.get(lookup__country_name__icontains=country_name)