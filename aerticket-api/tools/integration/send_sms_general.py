import requests
import json
from integrations.notification.models import NotificationIntegeration
from users.models import Country
from datetime import datetime
class VoicenSMS:
    def __init__(self, data,number_list):
        self.sms_integeration_list =  NotificationIntegeration.objects.filter(integeration_type = "sms", is_active = True,
                                                                                     country = self.get_country(data["country_name"])).first()
        self.number_list = number_list
        self.data = data

    def sms_integration(self):
        try:
            url = self.sms_integeration_list.data['url']
            headers = {'Content-Type': 'application/json'}
            message = self.sms_integeration_list.data['message']
            for replace_key, replace_value in self.data.items():
                message = message.replace(f"[[{replace_key}]]",str(replace_value)) # we are replacing   the key with actual value 

            payload = json.dumps({
                        "filetype":2,
                        "msisdn":self.number_list,
                        "language":0,
                        "credittype":7,
                        "senderid":self.sms_integeration_list.data['senderid'],
                        "templateid":0,
                        "message":message,
                        "ukey":self.sms_integeration_list.data['ukey'],
                        "isschd":False,
                        "schddate":datetime.today().strftime(('%Y-%m-%d %H:%S:%M')),
                        "isrefno":False
                        })    
            response = requests.request("POST", url, headers=headers, data=payload)
        except:
             pass

    def get_country(self,country_name):
        return Country.objects.get(lookup__country_name__icontains=country_name)







