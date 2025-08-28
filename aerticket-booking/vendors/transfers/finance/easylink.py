import xml.etree.ElementTree as ET
import requests
from datetime import datetime
import ast
from vendors.transfers import mongo_handler
from vendors.transfers.utils import get_fare_markup
from common.models_transfers import TransferBookingSearchDetail, TransferBookingPaymentDetail, TransferBooking, \
                                    TransferBookingContactDetail, TransferBookingFareDetail, TransferBookingLocationDetail
class Manager:
    def __init__(self,booking,data):
        self.user = booking.user
        self.booking = booking
        self.base_url = data.get("url")
        self.branch_code = data.get("branch_code")
        self.portal_reference_code = data.get("portal_reference_code")
    
    def process_billing(self,creds):
        try:
            url = self.base_url+"/processEasyMiscBillImp/?sBrCode="+self.branch_code+"&PortalRefCode="+self.portal_reference_code
            # List of all keys
            empty_keys = [
                "InvoiceDate", "InvoiceRefID", "XORef", "SuppType", "CustCode",
                "CreditType", "SuppCode", "SuppCCIssue", "SuppCCNum", "BillNarration",
                "BillNote", "ServiceType", "IntDom", "ServiceNo", "PassportNo", "tktRef",
                "PaxName", "DOB", "PolicyValidFrom", "PolicyValidTill", "Nominee",
                "RelNominee", "SPName", "forCountry", "PlaceOfIssue", "PassportIssueDate",
                "PassportExpiryDate", "PolicyIssueDate", "PolicyDuration", "PolicyPlanOpted",
                "Gender", "Occupation", "Remark1", "Remark2", "Remark3", "Remark4",
                "HCheckInDate", "HCheckInTime", "HCheckOutDate", "HCheckOutTime",
                "HConfirmedBy", "HConfirmedOn", "HAddress", "HTelNo", "HBookingPlan",
                "HSpecialTC", "HRoomRentPerDay", "HRoomType", "HNoOfRooms", "HNoOfAdult",
                "HNoOfChild", "HNoOfExtra", "HComingFrom", "HComingBy", "HProceedingTo",
                "HProceedingBy", "HPkgInclusions", "HPkgExclusions", "HPaymentMode",
                "HRefNo", "HIssuedBy", "HIssuedOn", "VAppNo", "VDuration", "VisaExpDt",
                "VisaType", "VisaNo", "NewPassportNo", "PServiceType", "IMFileNo",
                "IMType", "CAirwayBillNo", "CNoWt", "Cloading", "Cdischarge", "CAirSec",
                "Amount", "TaxB", "TaxC", "TaxA", "OthChgs", "AddlAmt", "AddlTaxA",
                "AddlTaxB", "StdComm", "SrvChrgs", "MGTFee", "SrvChrgsForex", "CustStdComm",
                "CustSrvChrgs", "CustMGTFee", "PercTDS", "TDS", "CustPercTDS", "CustTDS",
                "PercGTAX", "GTAX", "CustPercGTAX", "CustGTAX", "CustPercGTAXCess",
                "CustGTAXCess"
            ]

            # Create a dictionary with default value as empty string for each key.
            invoice_data = {key: "" for key in empty_keys}
            
            def convert_to_4_decimal_string(value):
                try:
                    formatted_value = f"{float(value):.4f}"
                    return formatted_value
                except ValueError:
                    return "0.0000" 
            
            fare_details = get_fare_markup(self.user)
            # XORef = str(int(hashlib.md5(self.booking.id.encode()).hexdigest()[:8], 16) % 10**8)
            locations = TransferBookingLocationDetail.objects.filter(booking_id=self.booking.id, transfer_type__in=["pickup", "drop"])
            pickup_detail = locations.filter(transfer_type="pickup").first()
            dropoff_detail = locations.filter(transfer_type="drop").first()
            fare_detail = TransferBookingFareDetail.objects.get(booking_id=self.booking.id)
            fare_breakdown = ast.literal_eval(fare_detail.fare_breakdown)
            CustStdComm = ((fare_breakdown.get('AgentCommission',0)*fare_details.get('fare',{}).get('parting_percentage',100)/100) + \
                                fare_details.get('fare',{}).get('cashback',0))*0.82
            contact_detail = TransferBookingContactDetail.objects.get(booking_id=self.booking.id)
            update_dict = {
                "InvoiceDate": datetime.fromtimestamp(self.booking.created_at).strftime('%d/%m/%Y'),
                "InvoiceRefID": self.booking.display_id,
                "XORef":self.booking.booking_ref_no,
                "SuppType": "S",
                "SuppCode":creds.get('eazylink_supplier_code'),
                "CustCode": self.user.organization.easy_link_billing_code,
                "CreditType": "F",
                "SuppCCIssue": "N",
                "SuppCCNum":"",
                "BillNarration": "", 
                "ServiceType": "O",
                "IntDom": "D",
                "PaxName": contact_detail.first_name+' '+contact_detail.last_name,
                "Remark1": pickup_detail.name +' to '+ dropoff_detail.name,
                "Remark2": "",
                "Amount": convert_to_4_decimal_string(fare_breakdown.get('BasePrice')),
                "TaxB":convert_to_4_decimal_string(fare_breakdown.get('Tax')),
                "TaxC": convert_to_4_decimal_string(0),
                "AddlAmt": convert_to_4_decimal_string(fare_details.get('fare',{}).get('markup',0)),
                "StdComm": convert_to_4_decimal_string(fare_breakdown.get('AgentCommission')),
                "SrvChrgs": convert_to_4_decimal_string(0),
                "MGTFee": convert_to_4_decimal_string(0),
                "CustStdComm": convert_to_4_decimal_string(CustStdComm),
                "CustSrvChrgs": convert_to_4_decimal_string(0),
                "CustMGTFee": convert_to_4_decimal_string(0),
                "PercTDS": convert_to_4_decimal_string(2),
                "TDS": convert_to_4_decimal_string(fare_breakdown.get('TDS')),
                "CustPercTDS": convert_to_4_decimal_string(2),
                "CustTDS": convert_to_4_decimal_string(CustStdComm*0.02),
                "PercGTAX": convert_to_4_decimal_string(18),
                "GTAX": convert_to_4_decimal_string(fare_breakdown.get('TotalGSTAmount')),
                "CustPercGTAX": convert_to_4_decimal_string(18),
                "CustGTAX": convert_to_4_decimal_string(0*0.18),
            }
            # Update the default dictionary with the provided values.
            invoice_data.update(update_dict)

            # Create XML structure
            root = ET.Element("Invoicedata")
            # Create an Invoice element with attributes set from invoice_data.
            invoice_elem = ET.SubElement(root, "Invoice", invoice_data)

            # Convert the XML tree to a string.
            payload = ET.tostring(invoice_elem, encoding='unicode')

            headers = {}
            response = requests.request("POST", url, headers = headers, data = payload,timeout = 120)
            mongo_client = mongo_handler.Mongo()
            easy_doc = {"url":url,"payload": payload,"response": response.text,"type":"easy_link","itinerary_id":str(''),
                        "display_id":self.booking.display_id,"payload_json":'',"refund":False,"createdAt":datetime.now()}
            mongo_client.vendors.insert_one(easy_doc)

        except Exception as e:
            print("easylink exc ",str(e))
