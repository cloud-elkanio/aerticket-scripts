from vendors.manager import get_manager_class
from .models import Payments,Integration
from rest_framework.response import Response
from rest_framework import status
import razorpay
import os
from dotenv import load_dotenv

from .models import Booking
from vendors.flights import flight_manager 

from vendors.buses.models import BusBooking
from vendors.buses import bus_manager

from vendors.insurance.models import InsuranceBooking
from vendors.insurance import insurance_manager


from vendors.transfers import transfers_manager
from common.models_transfers import TransferBooking

import time
from datetime import datetime
import requests
import html
from users.models import ( DistributorAgentFareAdjustment,
                          DistributorAgentTransaction,
                          )
load_dotenv()

callback_url = os.getenv('CALLBACK_URL_RAZORPAY_BOOKING')
bta_web_url = os.getenv('WEB_URL_RAZORPAY_BOOKING')

def razorpay_payment(**kwargs):
    try:
        payment_data = {
            "agency":kwargs["user"],
            "amount":kwargs["amount"],
            "payment_types":"booking"
        }
        payment_obj = Payments.objects.create(**payment_data)
        try:
            organization_country_id = kwargs["user"].organization.organization_country_id
            organization_id = kwargs["user"].organization.id
            country_id = {"country_id":organization_country_id}
        except:
            organization_id = None
            country_id = {} 
            pass
        razorpay_data = Integration.objects.filter(name="razorpay",**country_id).first().data
        result = {}
        for item in razorpay_data:
            result.update(item)
        kwargs['api_key'] = result.get('api_key')
        kwargs['api_secret'] = result.get('api_secret')
        kwargs['callback_url'] = callback_url + result.get('booking_callback_url')
        kwargs['organization_id'] = str(organization_id)
        kwargs['payment_obj'] = payment_obj
        response = razor_pay(kwargs)
        response['payment_id'] = payment_obj.id
        return response
    except Exception as e:
        print(str(e))
        return {"short_url":None,"status":False,"error":str(e)}

def razor_pay(kwargs):
    try:
        amount = float(kwargs.get('amount' ,0))
        client = razorpay.Client(auth=(kwargs.get('api_key'), kwargs.get('api_secret')))
        callback_url ="""{0}status?confirmation=success&payment_method=razor_pay&booking_id={1}&session_id={2}&module={3}"""\
        .format(kwargs.get('callback_url'),kwargs.get('booking_id'),kwargs.get('session_id',""),kwargs.get("module"))
        if kwargs.get('payment_method'):
            response = client.payment_link.create({
            "amount": float(amount) * 100,
            "currency": "INR",
            "description": kwargs.get('description'),
            "customer": {
                "name": kwargs.get('name'),
                "email": kwargs.get('email'),
                "contact": kwargs.get('phone_number'),
            },
            "notify": {
                "sms": True,
                "email": True
            },
            "reminder_enable": True,
            "notes": {
                "organization_id": kwargs.get('organization_id'),
                "booking_id": kwargs.get('booking_id'),
                "session_id": kwargs.get('session_id'),
                "module": kwargs.get("module")
            },
            "callback_url": callback_url,
            "callback_method": "get",
            "options": {
            "checkout": {
            "method": {
                    "upi": kwargs.get('payment_method') == 'upi',         # Enable UPI
                    "netbanking": kwargs.get('payment_method') == 'net_banking',  # Enable Net Banking
                    "card": kwargs.get('payment_method') in ['credit_card','debit_card'],        # Enable Cards (optional)
                    "wallet": False      # Disable Wallets (optional)
                }
            }
        }
        }) 
        else:

            response = client.payment_link.create({
            "amount": float(amount) * 100,
            "currency": "INR",
            "description": kwargs.get('description'),
            "customer": {
                "name": kwargs.get('name'),
                "email": kwargs.get('email'),
                "contact": kwargs.get('phone_number'),
            },
            "notify": {
                "sms": True,
                "email": True
            },
            "reminder_enable": True,
            "notes": {
                "organization_id": kwargs.get('organization_id'),
                "booking_id":kwargs.get('booking_id'),
                "session_id":kwargs.get('session_id'),
                "module" : kwargs.get("module")
            },
            "callback_url": callback_url,
            "callback_method": "get"
            })
        payment_obj = kwargs.get('payment_obj')
        payment_id_link = response.get('id')
        payment_obj.payment_id_link = payment_id_link
        payment_obj.save()
        return {"short_url":response.get('short_url'),"payment_id":payment_obj.id,"status":True}
    except Exception as e:
        return {"short_url":None,"status":False,"error" :str(e)}

def generate_auto_trx(pay_obj):
    try:
        amount = pay_obj.amount
        easy_link_billing_obj = pay_obj.agency.organization.easy_link_billing_account
        payment_id = pay_obj.razorpay_payment_id
        pax_name = pay_obj.agency
        result = {}
        if easy_link_billing_obj:
            for item in easy_link_billing_obj.data:
                result.update(item)
        base_url = result.get('url')
        branch_code = result.get('branch_code')
        portal_reference_code = result.get('portal_reference_code')
        account_code  = pay_obj.agency.organization.easy_link_billing_code
        date = datetime.fromtimestamp(time.time())
        today_date = date.strftime("%d/%m/%Y")
        if base_url :
            full_url = f"{base_url}/GenerateAutoTxn?sBrCode={branch_code}&PortalRefCode={portal_reference_code}&sTxnType=027"
        
        headers = {}
        payload = f"""<TxnData>\n    <Txn txnDt=\"{today_date}\" CustCode=\"{account_code}\" credittype=\"F\" BankCode=\"A0344\" PaxName=\"{pax_name}\" TxnRefNo=\"{payment_id}\" NR1=\"Online Recharge from Portal\" NR2=\"\" NR3=\"\" NR4=\"\" TxnAmount=\"{amount}\"></Txn>\n</TxnData>"""
        response = requests.request("POST", full_url, headers=headers, data=payload)
        if pay_obj.agency.role.name == 'distributor_agent':
            user_id = pay_obj.agency.id
            agent = DistributorAgentFareAdjustment.objects.get(user__id=user_id)
            DistributorAgentTransaction.objects.create(
            user=agent.user,
            transtransaction_type="credit",
            amount=amount,
            booking_type = "online_payment"
            )
            agent.available_balance = float(agent.available_balance) + float(amount)
            agent.save()
    except:
        pass

def razor_webhook(webhook_data):
    payment_id_link = webhook_data["razorpay_payment_link_id"]
    pay_obj  = Payments.objects.filter(payment_id_link=payment_id_link,status="paid",call_back=True).first()
    if pay_obj:
        generate_auto_trx(pay_obj)
        
    if webhook_data.get("module") == "flight":
        booking = Booking.objects.filter(id = webhook_data["booking_id"]).first()
        flight_manager.FlightManager(booking.user).purchase(data = webhook_data)
    elif webhook_data.get("module") == "bus":
        booking = BusBooking.objects.filter(id = webhook_data["booking_id"]).first()
        bus_manager.BusManager(booking.user).purchase(data = webhook_data)
    elif webhook_data.get("module") == "transfers":
        booking = TransferBooking.objects.filter(id = webhook_data["booking_id"]).first()
        transfers_manager.TransferManager(booking.user).purchase(data = webhook_data)
    elif webhook_data.get("module") == "insurance":
        booking = InsuranceBooking.objects.filter(id = webhook_data["booking_id"]).first()
        insurance_manager.InsuranceManager(booking.user).purchase(data = webhook_data)
    else:
        payment_detail = pay_obj.payment_detail.first() if pay_obj else None
        if payment_detail:
            try:
                manager = get_manager_class(payment_detail.payment_handler)  # Get the class
                manager = manager(payment_detail.created_by)
            except:
                raise Exception(f'missing "{payment_detail.payment_handler}" class in vendors.manager') 
            try:
                manager.purchase(payment_detail.id)
            except:
                raise Exception(f'missing "purchase" function in {payment_detail.payment_handler}')
        else:
            raise Exception(f'missing "payment detail" object in {payment_detail.payment_handler}')

    

    
    

