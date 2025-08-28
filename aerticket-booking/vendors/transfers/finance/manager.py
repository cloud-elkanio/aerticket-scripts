import os
from vendors.transfers import mongo_handler
from .easylink import Manager as easylink

class FinanceManager:
    def __init__(self,booking):
        self.booking = booking
        self.user = booking.user
        self.bta_env = os.getenv('BTA_ENV')
        self.org = booking.user.organization
        self.mongo_client = mongo_handler.Mongo()
    
    def process_billing(self,creds):
        try:
            billing_account_name = self.org.easy_link_billing_account.lookup_integration.name
            if billing_account_name == 'easy-link  backoffice suit':
                print(16)
                manager= easylink(self.booking,self.org.easy_link_billing_account.data[0])
                manager.process_billing(creds)
        except Exception as e:
            print('manager ',str(e))
            pass