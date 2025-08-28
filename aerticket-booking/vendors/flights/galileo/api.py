import requests,json
from requests.auth import HTTPBasicAuth
import xmltodict
import uuid
import os
import base64
import hashlib
from datetime import datetime, timedelta,timezone
import re

ptc_mapping = {"adults": "ADT","children": "CNN","infants": "INF"}

def clean_keys(data):
    if isinstance(data, dict):
        return {clean_key(k): clean_keys(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_keys(element) for element in data]
    else:
        return data

def clean_key(key):     # Remove '@','#' and replace ':' with '_'
    key = key.replace('@', '')
    key = key.replace('#', '')
    key = key.replace(':', '_')
    return key

def convert_date(date_str):
    date_obj = datetime.strptime(date_str, "%d-%m-%Y")
    return date_obj.strftime("%d%m%y")

def get_encoded_credentials(credentials):
    username = credentials.get("user_name")
    password = credentials.get("password")
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

    return encoded_credentials

def create_import_pnr_envelope(PseudoCityCode,TargetBranch,pnr):

    trace = uuid.uuid4()
    soap_request = f"""
                <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
                    <s:Body xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                        <UniversalRecordRetrieveReq xmlns="http://www.travelport.com/schema/universal_v42_0" TraceId="{trace}"  PseudoCityCode="{PseudoCityCode}" TargetBranch="{TargetBranch}">  
                            <BillingPointOfSaleInfo xmlns="http://www.travelport.com/schema/common_v42_0" OriginApplication="uAPI" />  
                            <ProviderReservationInfo xmlns="http://www.travelport.com/schema/universal_v42_0" ProviderCode="1G" ProviderLocatorCode="{pnr}" />
                        </UniversalRecordRetrieveReq>
                    </s:Body>
                </s:Envelope>
                """   
    return soap_request

def import_pnr_data(base_url,credentails,pnr):
    encoded_credentials = get_encoded_credentials(credentails)
    headers = {
        "Accept-Encoding": "gzip,deflate",  # Supports compressed responses
        "Content-Type": "text/xml;charset=UTF-8",  # Specifies XML content type
        "SOAPAction": "",  # SOAPAction is empty as per your requirement
        "Authorization": f"Basic {encoded_credentials}",  # Basic auth with encoded credentials
        "Content-Length": "length"  # Replace 'length' with actual payload size dynamically if needed
    }

    PseudoCityCode = credentails.get("city_code")
    TargetBranch = credentails.get("travel_branch")
    soap_message = create_import_pnr_envelope(PseudoCityCode, TargetBranch,pnr)
    content_length = len(soap_message.encode('utf-8'))
    headers["Content-Length"] = str(content_length)
    response = requests.post(base_url+"UniversalRecordService", data=soap_message, headers=headers)
    data_dict = xmltodict.parse(response.text)
    cleaned_data = clean_keys(data_dict)
    return cleaned_data