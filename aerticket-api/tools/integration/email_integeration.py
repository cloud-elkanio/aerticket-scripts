import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from integrations.notification.models import NotificationIntegeration
from django.db.models import Q
from users.models import Country
import os
from jinja2 import Template,Environment, FileSystemLoader




class MailEngine:
    def __init__(self):
        self.email_otp_obj = NotificationIntegeration.objects.filter(name ='smtp_go')
        self.error = None
        
    def send_otp_mail(self,obj,to_email,data):
        
        otp = data.get("otp")
        calling_code = data.get("calling_code")      
        # country = Country.objects.get(calling_code=calling_code)
        
        
        try:
            email_config = obj
        except Exception as e:
            self.error = "Error {}".format(e)
            return False
        
        smtp_server = email_config['email_server']
        smtp_port = email_config['email_port']
        smtp_username = email_config['email_username']
        smtp_password = email_config['email_password']
        sender_email = email_config['sender_email']
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
            





