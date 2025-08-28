import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from requests import Response
from integrations.notification.models import NotificationIntegeration,Notifications
from django.db.models import Q
from users.models import Country, ErrorLog
import os
from jinja2 import Template,Environment, FileSystemLoader


class SmtpEngineEmail:
    def __init__(self, notification_obj:Notifications,email_list:list,data:dict, email_provider_obj:NotificationIntegeration) -> bool:
        """_summary_
        send the email accordingly 
        Returns:
            bool: return True or False
        """
        self.notification_obj = notification_obj
        self.email_list = email_list
        self.data = data
        self.email_provider_obj = email_provider_obj

    def send_email(self):
        cc_email = self.notification_obj.template.recived_cc if self.notification_obj.template.recived_cc else []
        to_email = self.notification_obj.template.recived_to if self.notification_obj.template.recived_to else []

        cc_email = replace_placeholder_emails(cc_email,self.data)
        to_email = replace_placeholder_emails(to_email,self.data)
        content = self.notification_obj.template.body
        for replace_key, replace_value in self.data.items():
            content = content.replace(f"[[{replace_key}]]",str(replace_value)) # we are replacing   the key with actual value 
            # keep in mind we need to pass the same key to replace eg [[otp]], otp
        try:
            email_config = self.email_provider_obj.data 
        except Exception as e:
            self.error = "Error {}".format(e)
            return False
        smtp_server = email_config['smtp_server']
        smtp_port = email_config['smtp_port']
        smtp_username = email_config['smtp_username']
        smtp_password = email_config['smtp_password']
        sender_email = email_config['sender_email']
        to_emails = self.email_list + (to_email or [])
        txemails = to_emails + (cc_email or [])

        # Filter out None or invalid values
        to_emails = [email for email in to_emails if email]
        txemails = [email for email in txemails if email]
        txemails = list(set(txemails))
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ",".join(to_emails)
        msg['Subject'] = self.notification_obj.template.heading if self.notification_obj else None
        msg['Cc'] = ",".join(cc_email)

        root_dir = os.getcwd()
        jinja_file_path = f'{root_dir}/email_templates'
        env = Environment(loader=FileSystemLoader(jinja_file_path))
    
        template = env.get_template('base_template.html')
        html_content = template.render(content=content)

                                                                                                                                                                                                                                                        
        msg.attach(MIMEText(html_content, 'html'))
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, txemails, msg.as_string())  
            return True
        except Exception as e:
            ErrorLog.objects.create(module="email",erros={"email":e})
            return False

def replace_placeholder_emails(email_list, data):
    updated_emails = []
    for email in email_list:
        if '[[' in email and ']]' in email:
            key = email.replace('[[', '').replace(']]', '')
            if key in data:
                updated_emails.append(data[key])
        else:
            updated_emails.append(email)
    return updated_emails



class AwsEmailEngineMail:
    pass