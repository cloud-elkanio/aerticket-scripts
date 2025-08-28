from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.views import APIView
from users.models import UserDetails
from .rail_manager import RailManager
from .models import RailOrganizationDetails, RailTransactions, RailLedger
from django.http import JsonResponse, HttpResponse
from vendors.rail import mongo_handler
from django.forms.models import model_to_dict
from django.db import transaction
from django.utils import timezone
from common.models import DailyCounter
from users.models import SupplierIntegration, UserDetails
from api import settings

import dateutil.parser
import time
import base64
from Crypto.Cipher import AES
import requests
import xml.etree.ElementTree as ET
from decimal import Decimal

# Create your views here.
class CheckRailOrganizationStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        manager = RailManager(user)
        if manager.auth_success:
            response_data = manager.check_rail_organization_status(user)
        else:
            return JsonResponse(
                {
                    "status":"No Suppliers",
                    "info": "No suppliers are associated with your account. Kindly contact support for assistance."},
                safe=False
            )
        
        # If `None` is returned from the manager, respond with a standard error
        if response_data is None:
            return JsonResponse(
                {"status": "Not Available",
                 "organization":None,
                 }
            )

        # Otherwise, return the data
        return JsonResponse(response_data, safe=False)

class CheckPaymentPermissionView(APIView):
    authentication_classes = []
    permission_classes = []
    def get(self, request, *args, **kwargs):
        encdata = request.GET.get('encdata')
        try:
            rail_creds = SupplierIntegration.objects.filter(integration_type ='Rail',is_active=True).first()
            iv = rail_creds.data.get('IV')
            key = rail_creds.data.get('key')
            def unpad(text):
                """
                Remove PKCS#7 padding from the text.
                """
                padding_len = ord(text[-1])
                return text[:-padding_len]
            
            def decrypt_aes_256_cbc(encdata, key, iv):
                """
                Decrypt the ciphertext which is a Base64 encoded string using AES-256 in CBC mode
                with the provided key and IV.
                Returns the decrypted plaintext string.
                """
                # Decode the Base64 encoded ciphertext to get the raw encrypted bytes
                encrypted_bytes = base64.b64decode(encdata)
                
                # Create the AES cipher object in CBC mode
                cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
                
                # Decrypt the encrypted bytes to get the padded plaintext
                padded_plaintext_bytes = cipher.decrypt(encrypted_bytes)
                
                # Convert bytes to a string
                padded_plaintext = padded_plaintext_bytes.decode('utf-8')
                
                # Remove the PKCS#7 padding
                plaintext = unpad(padded_plaintext)
                
                return plaintext

            plain_text = decrypt_aes_256_cbc(encdata, key, iv)
            def string_to_dict(s):
                # Remove newline characters (if any)
                s = s.replace("\n", "")
                # Split the string by the pipe character
                pairs = s.split("|")
                # Build the dictionary from key-value pairs
                result = {}
                for pair in pairs:
                    if "=" in pair:
                        key, value = pair.split("=", 1)
                        result[key] = value
                return result
            
            encdata_dict = string_to_dict(plain_text)
            agent_id = encdata_dict.get("ownerID")
            rail_org_detail = RailOrganizationDetails.objects.filter(agent_id=agent_id).first()
            organization = rail_org_detail.organization
            owner = UserDetails.objects.filter(
                                                            organization=organization, 
                                                            role__name__in=["agency_owner", "super_admin", "distributor_owner", "enterprise_owner"]
                                                        ).first()
            def generate_booking_display_id():
                now = timezone.now()
                today = now.date()
                with transaction.atomic():
                    counter, created = DailyCounter.objects.select_for_update().get_or_create(date=today,module="rail")
                    counter.count += 1
                    counter.save()
                    booking_number = counter.count
                formatted_booking_number = f"{booking_number:04d}"
                day_month = now.strftime("%d%m")  # DDMM format
                year_suffix = now.strftime("%y")  # Last two digits of the year
                return f"IRL{year_suffix}-{day_month}-{formatted_booking_number}"
            rail_transaction = RailTransactions.objects.create(
                                                    user=owner,
                                                    organization=organization,
                                                    display_id=generate_booking_display_id(),
                                                    status='Enquiry',
                                                    merchantCode=encdata_dict.get('merchantCode'),
                                                    reservationId=encdata_dict.get('reservationId'),
                                                    txnAmount=Decimal(encdata_dict['txnAmount']) if encdata_dict.get('txnAmount') else None,
                                                    currencyType=encdata_dict.get('currencyType'),
                                                    appCode=encdata_dict.get('appCode'),
                                                    pymtMode=encdata_dict.get('pymtMode'),
                                                    txnDate=encdata_dict.get('txnDate'),  
                                                    securityId=encdata_dict.get('securityId'),
                                                    RU=encdata_dict.get('RU'),
                                                    userID=encdata_dict.get('userID'),
                                                    ownerID=encdata_dict.get('ownerID'),
                                                    fixedCharge=Decimal(encdata_dict['fixedCharge']) if encdata_dict.get('fixedCharge') else None,
                                                    variableCharge=Decimal(encdata_dict['variableCharge']) if encdata_dict.get('variableCharge') else None,
                                                    Cgst=Decimal(encdata_dict['Cgst']) if encdata_dict.get('Cgst') else None,
                                                    Sgst=Decimal(encdata_dict['Sgst']) if encdata_dict.get('Sgst') else None,
                                                    Igst=Decimal(encdata_dict['Igst']) if encdata_dict.get('Igst') else None,
                                                    totalTxnAmount=Decimal(encdata_dict['totalTxnAmount']) if encdata_dict.get('totalTxnAmount') else None,
                                                    class_field=encdata_dict.get('Class'),
                                                    noOfPax=int(encdata_dict['noOfPax']) if encdata_dict.get('noOfPax') else None,
                                                    maxAgentFeeinclGST=Decimal(encdata_dict['maxAgentFeeinclGST']) if encdata_dict.get('maxAgentFeeinclGST') else None,
                                                    maxPGChargeinclGST=Decimal(encdata_dict['maxPGChargeinclGST']) if encdata_dict.get('maxPGChargeinclGST') else None,
                                                    ticketPrintRate=Decimal(encdata_dict['ticketPrintRate']) if encdata_dict.get('ticketPrintRate') else None,
                                                    wsUserLogin=encdata_dict.get('wsUserLogin'),
                                                    CheckSum=encdata_dict.get('CheckSum')
                                                )
            transaction_uuid = rail_transaction.id
            transaction_number = transaction_uuid.int
            base_url = organization.easy_link_billing_account.data[0].get('url')
            portal_ref_code = organization.easy_link_billing_account.data[0].get('portal_reference_code')
            if settings.DEBUG:
                # easy_link_account_code = organization.easy_link_account_code
                # url = f"{base_url}/getAvlCreditLimit/?PortalRefCode={portal_ref_code}&sAcCode={easy_link_account_code}&sRefAcCode="
                encdata_dict['status'] = True
                encdata_dict['statusDesc'] = 'Enough Balance in Wallet'
            else:
                billing_code = organization.easy_link_billing_code
                url = f"{base_url}/getAvlCreditLimit/?PortalRefCode={portal_ref_code}&sAcCode=&sRefAcCode={billing_code}"
                header = {"Content-Type":"text/plain"}
                response = requests.post(url=url, headers=header)
                xml_text = response.text
                root = ET.fromstring(xml_text)
                if "Error" not in root.text:
                    limit_root = ET.fromstring(root.text)
                    easylink_structured_data = limit_root.attrib
                    if float(easylink_structured_data.get('O',0)) > float(encdata_dict.get('ticketPrintRate')):
                        encdata_dict['status'] = True
                        encdata_dict['statusDesc'] = 'Enough Balance in Wallet'
                    else:
                        encdata_dict['status'] = False
                        encdata_dict['statusDesc'] = 'Not Enough Balance in Wallet'
                else:
                    encdata_dict['status'] = False
                    encdata_dict['statusDesc'] = 'Not Enough Balance in Wallet'

            order = [
                        "merchantCode", "reservationId", "txnAmount", "bankTxnId",
                        "status", "statusDesc", "totalTxnAmount", "chargedAmount"
                    ]
            encdata_dict['bankTxnId'] = transaction_number
            
            encdata_dict['chargedAmount'] = encdata_dict['totalTxnAmount']
            print("encdata_dict ",encdata_dict)
            def format_value(value):
                if isinstance(value, bool):
                    return str(value).lower()
                return value
            response_string = "|".join(f"{key}={format_value(encdata_dict[key])}" for key in order)
            def pad(text):
                """
                Pad text using PKCS#7 padding to ensure the length is a multiple of AES block size (16 bytes).
                """
                block_size = AES.block_size  # 16 bytes
                padding_len = block_size - (len(text) % block_size)
                padding = chr(padding_len) * padding_len
                return text + padding

            def encrypt_aes_256_cbc(plaintext, key, iv):
                """
                Encrypt the plaintext using AES-256 in CBC mode with the provided key and IV.
                Returns the encrypted data as a Base64-encoded string.
                """
                # Ensure the plaintext is padded correctly
                padded_plaintext = pad(plaintext)
                
                # Create the AES cipher object in CBC mode
                cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
                
                # Encrypt the padded plaintext
                encrypted_bytes = cipher.encrypt(padded_plaintext.encode('utf-8'))
                
                # Return the encrypted bytes as a Base64 encoded string
                return base64.b64encode(encrypted_bytes).decode('utf-8')

            encrypted_response_data = encrypt_aes_256_cbc(response_string, key, iv)
            return HttpResponse(encrypted_response_data, content_type="text/plain")
        except Exception as e:
            print(str(e))
            mongo_client = mongo_handler.Mongo()
            mongo_client.store_raw_data(str(e),'error')
            mongo_client.store_raw_data(encdata,'raw_data')

class NotificationView(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request, *args, **kwargs):
        encdata = request.data.get('encdata')
        try:
            rail_creds = SupplierIntegration.objects.filter(integration_type ='Rail',is_active=True).first()
            iv = rail_creds.data.get('IV')
            key = rail_creds.data.get('key')
            def unpad(text):
                """
                Remove PKCS#7 padding from the text.
                """
                padding_len = ord(text[-1])
                return text[:-padding_len]
            
            def decrypt_aes_256_cbc(encdata, key, iv):
                """
                Decrypt the ciphertext which is a Base64 encoded string using AES-256 in CBC mode
                with the provided key and IV.
                Returns the decrypted plaintext string.
                """
                # Decode the Base64 encoded ciphertext to get the raw encrypted bytes
                encrypted_bytes = base64.b64decode(encdata)
                
                # Create the AES cipher object in CBC mode
                cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
                
                # Decrypt the encrypted bytes to get the padded plaintext
                padded_plaintext_bytes = cipher.decrypt(encrypted_bytes)
                
                # Convert bytes to a string
                padded_plaintext = padded_plaintext_bytes.decode('utf-8')
                
                # Remove the PKCS#7 padding
                plaintext = unpad(padded_plaintext)
                
                return plaintext

            plain_text = decrypt_aes_256_cbc(encdata, key, iv)
            def string_to_dict(s):
                # Remove newline characters (if any)
                s = s.replace("\n", "")
                # Split the string by the pipe character
                pairs = s.split("|")
                # Build the dictionary from key-value pairs
                result = {}
                for pair in pairs:
                    if "=" in pair:
                        key, value = pair.split("=", 1)
                        result[key] = value
                return result
            
            encdata_dict = string_to_dict(plain_text)
            agent_id = encdata_dict.get("ownerID")
            rail_org_detail = RailOrganizationDetails.objects.filter(agent_id=agent_id).first()
            organization = rail_org_detail.organization
            owner = UserDetails.objects.filter(
                                                            organization=organization, 
                                                            role__name__in=["agency_owner", "super_admin", "distributor_owner", "enterprise_owner"]
                                                        ).first()
            if RailLedger.objects.filter(supplierRef=encdata_dict.get("supplierRef",''),tag=encdata_dict.get("tag")).exists():
            # if False:
                response = { "message": "Webhook not processed successfully", 
                        "success": False, 
                        "transactionID": int(time.time())
                            }
            else: 
                ledger = RailLedger.objects.create(
                                                user=owner,
                                                organization=organization,
                                                time_stamp = dateutil.parser.isoparse(encdata_dict.get("TimeStamp")) if encdata_dict.get("TimeStamp") else None,
                                                previousID = encdata_dict.get("previousID"),
                                                previousBal = encdata_dict.get("previousBal"),
                                                refrerenceID = encdata_dict.get("refrerenceID"),
                                                userID = encdata_dict.get("userID"),
                                                ownerID = encdata_dict.get("ownerID"),
                                                accountID = encdata_dict.get("accountID"),
                                                itemID = encdata_dict.get("itemID"),
                                                supplierRef = encdata_dict.get("supplierRef"),
                                                description = encdata_dict.get("description"),
                                                item_amt = encdata_dict.get("item_amt"),
                                                charges = encdata_dict.get("charges"),
                                                SGST = encdata_dict.get("SGST"),
                                                CGST = encdata_dict.get("CGST"),
                                                IGST = encdata_dict.get("IGST"),
                                                commission = encdata_dict.get("commission"),
                                                TDS = encdata_dict.get("TDS"),
                                                amt_cr = encdata_dict.get("amt_cr"),
                                                amt_dr = encdata_dict.get("amt_dr"),
                                                balanceAmt = encdata_dict.get("balanceAmt"),
                                                WH_Status = encdata_dict.get("WH_Status"),
                                                supplierRef1 = encdata_dict.get("supplierRef1"),
                                                attempt = encdata_dict.get("attempt"),
                                                mongo_id = encdata_dict.get("_id"),
                                                journalID = encdata_dict.get("journalID"),
                                                version = encdata_dict.get("__v"),
                                                tag = encdata_dict.get("tag"),
                                                CheckSum = encdata_dict.get("CheckSum"),
                                                partnerTxnID = encdata_dict.get('partnerTxnID'),
                                                Last_blockBalance = encdata_dict.get('Last_blockBalance'),
                                                previous_blockBalance = encdata_dict.get("previous_blockBalance"),
                                            )
                transaction_number = ledger.id
                response = { "message": "Webhook processed successfully", 
                            "success": True, 
                            "transactionID": transaction_number
                            }
            try:
                if encdata_dict.get("tag") == 'ledger':
                    if encdata_dict.get('itemID') == 'trainTicket':
                        transaction = RailTransactions.objects.filter(reservationId=encdata_dict.get("refrerenceID")).first()
                        transaction.status = 'Purchased'
                        manager = RailManager(owner)
                        print("manager ",manager)
                        if manager.auth_success:
                            response_data = manager.populate_easylink(owner,encdata_dict|{"display_id":transaction.display_id,"SuppCode":rail_creds.data.get('eazylink_supplier_code'),
                                                                                            "S1Class":transaction.class_field})
                    elif encdata_dict.get('itemID') == 'trainRefund':
                        transaction = RailTransactions.objects.filter(reservationId=encdata_dict.get("refrerenceID")).first()
                        transaction.status = 'Cancelled'
            except Exception as e:
                print("RailTransactions error: ",str(e))
                pass
            return JsonResponse(response, status = 200 )
        except Exception as e:
            print(str(e))
            mongo_client = mongo_handler.Mongo()
            mongo_client.store_raw_data(str(e),'error')
            mongo_client.store_raw_data(encdata,'raw_data') 
            response = { "message": "Webhook not processed successfully. Error: "+str(e), 
                        "success": False, 
                        "transactionID": int(time.time())
                            }
            return JsonResponse(response, status = 200 )