from integrations.notification.models import Notifications, NotificationIntegeration
from .smtp_engine import SmtpEngine
from users.models import Country,ErrorLog
from tools.integration.send_email_general import SmtpEngineEmail,AwsEmailEngineMail

class EmailIntegerations:
    def __init__(self,notification_obj,email_list,data) -> None:
        self.email_integeration_list:list =  NotificationIntegeration.objects.filter(integeration_type = "email", is_active = True,
                                                                                     country = self.get_country(data["country_name"]))
        
        self.notification_obj = notification_obj
        self.email_list = email_list
        self.data = data
        
    def send_email(self):
        for email_provider_obj in  self.email_integeration_list:
            if email_provider_obj.name == "SMTPGo" or email_provider_obj.name == "SendGrid":
                email_server = SmtpEngineEmail(self.notification_obj,self.email_list,self.data,email_provider_obj)
                is_mail_sent = email_server.send_email()
            elif email_provider_obj.name == "Amazon SES":
                is_mail_sent = False
            if is_mail_sent:
                ErrorLog.objects.create(module="email_sent",erros={"email":"success", "to":self.email_list, "from":self.data, "body":self.data}) 
            else:
                ErrorLog.objects.create(module="email_sent_error",erros={"email":"success", "to":self.email_list, "from":self.data, "body":self.data})         
              
    def get_country(self,country_name):
        return Country.objects.get(lookup__country_name__icontains=country_name)
                
