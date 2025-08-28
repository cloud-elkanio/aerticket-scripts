import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from integrations.notification.models import NotificationIntegeration,Notifications
from django.db.models import Q
from users.models import Country
import os
from jinja2 import Template,Environment, FileSystemLoader








class VoiceEnEngine:
    def __init__(self,notification_obj:Notifications ,phone_number_list:list ,data:dict,sms_provider_obj:NotificationIntegeration) -> bool:
        """_summary_
        send the email accordingly 
        Returns:
            bool: return True or False
        """
        self.notification_obj = notification_obj
        self.email_list = phone_number_list
        self.data = data
        self.email_provider_obj = sms_provider_obj
    
    
    def sent_mail(self):
        
    
        otp = self.data.get("otp")
        # calling_code = self.data.get("calling_code")  
        
        
        try:
            sms_config = self.email_provider_obj.data
        except Exception as e:
            self.error = "Error {}".format(e)
            return False
        
        smtp_server = sms_config['email_server']
        msg = MIMEMultipart()
        msg['From'] = sender_email
        
        
        
        msg['To'] = to_email
        msg['Subject'] = "Verify Your Account with This OTP"
        
        root_dir = os.getcwd()
        jinja_file_path = f'{root_dir}/templates/customer_confirmation_ticket'
        env = Environment(loader=FileSystemLoader(jinja_file_path))
      
        template = env.get_template('Payment-Confirmation.html')
        html_content = template.render(otp=otp)

                                                                                                                                                                                                                                                        
        msg.attach(MIMEText(html_content, 'html'))

        msg.attach(MIMEText(html_content, 'html'))
      
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_username, smtp_password)
        
            server.sendmail(sender_email, to_email, msg.as_string())
            return True
        
        except Exception as e:
            self.error = str(e)
            return False
        