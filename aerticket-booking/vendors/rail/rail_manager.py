
from .models import RailOrganizationDetails
from users.models import UserDetails
from vendors.rail import mongo_handler
import uuid
from users.models import SupplierIntegration,OrganizationSupplierIntegeration, UserDetails
from .api import authentication, login_helper
import time
import base64
from Crypto.Cipher import AES
import urllib
from datetime import datetime
import hashlib
import xml.etree.ElementTree as ET
import requests

class RailManager:
    """
    This manager class handles the application logic for 'transfers'.
    It delegates external API calls to api.py.
    """
    def __init__(self, user:UserDetails):
        self.user = user
        # self.mongo_client = mongo_handler.Mongo()
        self.creds = self.get_supplier_data()
        self.auth_success = True if self.creds !=None else False

    def create_uuid(self,suffix=""):
        if suffix == "":
            return str(uuid.uuid4())
        else:
            return suffix+"-"+str(uuid.uuid4())

    def get_supplier_data(self):
        associated_suppliers_list = OrganizationSupplierIntegeration.objects.filter(organization=self.user.organization,is_enabled=True).values_list('supplier_integeration', flat=True)
        supplier_integrations = SupplierIntegration.objects.filter(id__in=associated_suppliers_list,integration_type ='Rail',is_active=True)
        data = None
        for x in supplier_integrations:
            if x.name == "Rail - FWMSPL":
                if  x.expired_at>int(time.time()) and x.token!=None:
                    data = x.data | {"token_id":x.token,"supplier_name":x.name,"supplier_id":str(x.id)}
                else:
                    token = authentication(x.data)
                    if token == None:
                        return None
                    x.update_token(token)
                    data = x.data | {"token_id":token,"supplier_name":x.name,"supplier_id":str(x.id)}
        return data
    
    def check_rail_organization_status(self, user, *args, **kwargs):
        try:
            # Get the authenticated user's organization.
            user = user
            organization = user.organization
            
            # Try to retrieve a RailOrganizationDetails record for the user's organization.
            rail_org = RailOrganizationDetails.objects.filter(organization=organization).first()
            if rail_org:
                # Check if record qualifies for redirection.
                if (rail_org.status == "Approved" and rail_org.is_active and 
                    rail_org.agent_id and rail_org.irctc_id):
                    data = login_helper(self.creds,rail_org.agent_id)
                    if data !=None:
                        access_token = data.get('access_token')
                        base_url = self.creds['redirect_url']
                        return {
                            "status": "Success",
                            "redirect_url":f"{base_url}?encdata={access_token}"
                            }
                    else:
                        return {
                                "status": "Error",
                                }
                else:
                    return {
                                "status": "Pending",
                                }
            # Fallback: if no RailOrganizationDetails exists, return minimal Organization details.
            org_data = {
                "organization_name": organization.organization_name,
                "organization_address": organization.address,
                "organization_state": organization.state,
                "organization_country": organization.organization_country.lookup.country_name if organization.organization_country else None,
                "organization_zipcode": organization.organization_zipcode,
                "organization_pan": organization.organization_pan_number,
                "support_email": organization.support_email,
            }
            return {
                "status": "Not Available",
                "organization": org_data
                }
        except Exception as e:
            print("error",str(e))
            return None

    def populate_easylink(self,user,data):
        try:
            def convert_to_4_decimal_string(value):
                try:
                    formatted_value = f"{float(value):.4f}"
                    return formatted_value
                except ValueError:
                    return "0.0000" 
            user = user
            organization = user.organization
            billing_account_name = organization.easy_link_billing_account.lookup_integration.name
            if billing_account_name == 'easy-link  backoffice suit':
                billing_data = organization.easy_link_billing_account.data[0]
                base_url = billing_data.get("url")
                branch_code = billing_data.get("branch_code")
                portal_reference_code = billing_data.get("portal_reference_code")
                url = base_url+"/processEasyRBCBillImp/?sBrCode="+branch_code+"&PortalRefCode="+portal_reference_code
                invoice_data ={}
                invoice_data['InvoiceDate'] = datetime.now().strftime("%d/%m/%Y")
                invoice_data['InvoiceRefID'] = data.get('display_id','')
                invoice_data['XORef'] = data.get('supplierRef1','')
                invoice_data['CustCode'] = organization.easy_link_billing_code
                invoice_data['SuppCode'] = data.get('SuppCode','')
                invoice_data['credittype'] = "F"
                invoice_data['RailCode'] = "01011"
                invoice_data['SuppCCIssue'] = 'N'
                invoice_data['SuppCCNum'] = ''
                invoice_data['ServiceType'] = 'R'
                invoice_data['TktNo'] = data.get('supplierRef','')
                invoice_data['PNRNo'] = data.get('supplierRef1','')
                invoice_data['TktDt'] = datetime.now().strftime("%d/%m/%Y")
                invoice_data['tktRef'] = user.first_name + ' ' + user.last_name
                invoice_data['PaxName'] = user.first_name 
                invoice_data['Sector'] = 'Test/Test'#datetime.now().strftime("%d/%m/%Y")
                invoice_data['S1Sector'] = 'Test/Test'
                invoice_data['S1CSNo'] = '0'
                invoice_data['S1Date'] = datetime.now().strftime("%d/%m/%Y")
                invoice_data['S1Class'] = data.get('S1Class','')
                invoice_data['BasicFare'] = convert_to_4_decimal_string(data.get('item_amt',0))
                invoice_data['TatkalAmt'] = '0.0000'
                invoice_data['OthAmt'] = '0.0000'
                invoice_data['AddlOthAmt'] = '0.0000'
                invoice_data['TxnFees'] = '0.0000'
                invoice_data['StdComm'] = '0.0000'
                invoice_data['SrvChrgs'] = '0.0000'
                invoice_data['MGTFee'] = convert_to_4_decimal_string(data.get('charges',0))
                invoice_data['CustStdComm'] = '0.0000'
                invoice_data['CustSrvChrgs'] = '0.0000'
                invoice_data['CustMGTFee'] = '0.0000'
                invoice_data['PercTDS'] = '0.0000'
                invoice_data['TDS'] = '0.0000'
                invoice_data['CustGTAX'] = convert_to_4_decimal_string(float(data.get('SGST',0))+ float(data.get('CGST',0))+ float(data.get('IGST',0)))
                invoice_data['CustPercTDS'] = '0.0000'
                invoice_data['CustTDS'] = '0.0000'
                invoice_data['PercGTAX'] = convert_to_4_decimal_string('18')
                invoice_data['GTAX'] = convert_to_4_decimal_string(float(data.get('SGST',0))+ float(data.get('CGST',0))+ float(data.get('IGST',0)))
                invoice_data['CustPercGTAX'] = convert_to_4_decimal_string('18')
                invoice_data['CustPercGTAXCess'] = '0.0000'
                invoice_data['CustGTAXCess'] = '0.0000'
                # Create XML structure
                root = ET.Element("Invoicedata")
                # Create an Invoice element with attributes set from invoice_data.
                invoice_elem = ET.SubElement(root, "Invoice", invoice_data)
                # Convert the XML tree to a string.
                payload = ET.tostring(invoice_elem, encoding='unicode')

                headers = {}
                response = requests.request("POST", url, headers = headers, data = payload,timeout = 60)
        except Exception as e:
            pass