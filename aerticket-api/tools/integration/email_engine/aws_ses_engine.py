import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from integrations.notification.models import NotificationIntegeration, Notifications
from django.db.models import Q
from users.models import Country, ErrorLog
import os
from jinja2 import Template, Environment, FileSystemLoader


class AwsEmailEngine:
    def __init__(
        self,
        notification_obj: Notifications,
        email_list: list,
        data: dict,
        email_provider_obj: NotificationIntegeration,
    ) -> bool:
        """_summary_
        send the email accordingly
        Returns:
            bool: return True or False
        """
        self.notification_obj = notification_obj
        self.email_list = email_list
        self.data = data
        self.email_provider_obj = email_provider_obj

    def sent_mail(self):
        self.email_list.extend(self.notification_obj.template.recived_cc)
        self.email_list.extend(self.notification_obj.template.recived_to)

        content = self.notification_obj.template.body

        for replace_key, replace_value in self.data.items():
            content = content.replace(
                f"[[{replace_key}]]", str(replace_value)
            )  # we are replacing   the key with actual value
            # keep in mind we need to pass the same key to replace eg [[otp]], otp

        try:
            email_config = self.email_provider_obj.data
        except Exception as e:
            self.error = "Error {}".format(e)
            return False

        smtp_server = email_config["smtp_server"]
        smtp_port = email_config["smtp_port"]
        smtp_username = email_config["smtp_username"]
        smtp_password = email_config["smtp_password"]
        sender_email = email_config["sender_email"]

        # emails_with_pattern = [email for email in self.email_list if '[[' in email and ']]' in email]
        # if emails_with_pattern:
        while self.email_list:
            i = 0
            to_email = self.email_list.pop()
            if str(to_email).startswith(
                "[["
            ):  # if there is [[customer_email]] then we will replace it with actualcustomers
                try:
                    to_email = self.data[to_email[2:-2]]
                    if (
                        to_email in self.email_list
                    ):  # if email list already has the  the email we are sending then this wil not work
                        # eg k@gmail.com in  [k@gmail.com]  then this will not work to avoid sending multiple mails we are eliminating this
                        i = i + 1
                        continue
                except:
                    continue

            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = to_email

            msg["Subject"] = self.notification_obj.template.heading
            root_dir = os.getcwd()
            jinja_file_path = f"{root_dir}/email_templates"
            env = Environment(loader=FileSystemLoader(jinja_file_path))

            template = env.get_template("base_template.html")
            html_content = template.render(content=content)

            msg.attach(MIMEText(html_content, "html"))

            try:
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(smtp_username, smtp_password)
               
                server.sendmail(sender_email, to_email, msg.as_string())
                return True
            except Exception as e:
                return False
                ErrorLog.objects.create(module="email", erros={"email": e})
