import html
import xmltodict
import requests
import xml.etree.ElementTree as ET
import razorpay
from users.models import ErrorLog
from .models import Payments
import time
from datetime import datetime
from tools.easy_link.xml_restructure import XMLData
def structure_data(data, organization_obj, kwargs):
    res = {
        'organization_name': organization_obj.organization_name,
        'accode':"",
        'from_date': kwargs.get('from_date'),
        'to_date': kwargs.get('to_date'),
        'organization_address': organization_obj.address,
        'results': []
    }

    # Extract transactions
    datas = data.get('RESULT', {}).get('txn', [])
    key_value_pair = {
        "AS": "AIR TKT SALE",
        "AR": "AIR TKT REFUND",
        "AV": "AIR TKT VOID",
        "RC": "RECIEPT",
        "MS": "MISCELLANEOUS",
        "MR": "MISCELLANEOUS REFUND",
        "PY": "PAYMENT",
        "JV": "JOURNAL ENTRY",
        "CN": "CREDIT NOTE",
        "DN": "DEBIT NOTE",
        "TT": "TKT REFUND OTHER"
        
        
    }

    # Initialize results dictionary
    categorized_data = {key: {"heading": value, "data": [], "subtotal": {"Basic_OthTaxes": 0.0,"YQ_YR": 0.0,
                                                                         "SC_MF": 0.0,"GTAX_TDS": 0.0,
                                                                         "TxnFee_RoundOff": 0.0,
                                                                         "RAF_SCONREF": 0.0,
                                                                         "HCamt_AirCCAmt": 0.0,
                                                                         "NET":0.0
                                                                         }} for key, value in key_value_pair.items()}
   
    pattern = r"TXN NO\. ([A-Z0-9\-]+)"
    
    if isinstance(datas, dict):
        
        temp_dict = datas
        datas = []
        txncode = temp_dict.get('txncode')
        if not txncode :
            
            return False
        else:
            
            datas.append(temp_dict)

    for txn in datas:
        
        tx_code = txn.get('txncode', '')
        prefix = tx_code[:2]  # Extract prefix
        sm =0
        for key,value in txn.items():
            
            if key == 'accode':
                res['accode'] = value
                pass

            # if key == 'tnarr':
            #     if (match := re.search(pattern, value)):
            #         txncode1 = match.group(1)
            #         txn['txncode_1'] = txncode1
                
            if key == 'Basic':
                txn[key] = round(float(value),2)
                sm += txn[key]
            if key == 'OthTaxes':
                txn[key]=round(float(value),2)
                sm += txn[key]
            if key == 'YQ':
                txn[key]=round(float(value),2)
                sm += txn[key]
            if key == 'YR':
                txn[key]=round(float(value),2)
                sm += txn[key]
            if key == 'SC':
                txn[key]=round(float(value),2)
                sm += txn[key]
            if key == 'MF':
                txn[key]=round(float(value),2)
                sm += txn[key]
            if key == 'GTAX':
                txn[key]=round(float(value),2) 
                sm += txn[key]
            if key == 'TDS':
                txn[key]=round(float(value),2)    
                sm += txn[key]
            if key == 'TxnFee':
                txn[key]=round(float(value),2) 
                sm += txn[key]
            if key == 'RoundOff':
                txn[key]=round(float(value),2)  
                sm += txn[key]
            if key == 'RAF':
                txn[key]=round(float(value),2)
                sm += txn[key]
            if key == 'HCamt':
                txn[key]=round(float(value),2)
                sm += txn[key]
            if key == 'AirCCAmt':
                txn[key]=round(float(value),2)
                sm += txn[key]
        
        txn['NET'] = float(round(sm))
         
        
        if prefix in categorized_data:

            categorized_data[prefix]['data'].append(txn)

            # Example subtotal calculation (sum of "Basic" amounts)
            try:
                basic_oth_taxes = txn.get('Basic', 0) + txn.get('OthTaxes', 0)
                yq_yr = txn.get('YQ', 0) + txn.get('YR', 0)
                sc_mf = txn.get('SC', 0) + txn.get('MF', 0)
                gtax_tds = txn.get('GTAX', 0) + txn.get('TDS', 0)
                txnfee_roundoff = txn.get('TxnFee', 0) + txn.get('RoundOff', 0)
                raf_scref = txn.get('RAF', 0) + round(float(txn.get('SCONREF', '0').replace(',', '')))
                hcamt_airccamt = txn.get('HCamt', 0) + txn.get('AirCCAmt', 0)
                net = txn.get('NET',0)
                categorized_data[prefix]['subtotal']['Basic_OthTaxes'] +=  basic_oth_taxes
                categorized_data[prefix]['subtotal']['YQ_YR'] +=  yq_yr
                categorized_data[prefix]['subtotal']['SC_MF'] +=  sc_mf
                categorized_data[prefix]['subtotal']['GTAX_TDS'] +=  gtax_tds
                
                categorized_data[prefix]['subtotal']['TxnFee_RoundOff'] +=  txnfee_roundoff
                categorized_data[prefix]['subtotal']['RAF_SCONREF'] +=  raf_scref
                categorized_data[prefix]['subtotal']['HCamt_AirCCAmt'] +=  hcamt_airccamt
                categorized_data[prefix]['subtotal']['NET'] += net

            except ValueError:
                pass  # Handle non-numeric values gracefully

    # Add populated categories to results
    for key,value in categorized_data.items():
        # print("value------",value.get('subtotal'))
        for ky,ech_val in value.get('subtotal').items():
            # print("key----",value)
            value.get('subtotal')[ky] = round(ech_val,2)
            

    res['results'] = [value for value in categorized_data.values() if value['data']]
    length_arry = len(res['results'])
    if length_arry == 0:
        return False
    else:
        return res
            # print(res)
def clean_data(data):
    if isinstance(data, dict):
        # For dictionaries, remove '@' from all keys, handle 'tnarr', and recursively process values
        return {
            key.lstrip('@'): clean_data(value) if key.lstrip('@') != "tnarr" else value.replace("¥¿", "")
            for key, value in data.items()
        }
    elif isinstance(data, list):
        # For lists, recursively process each item
        return [clean_data(item) for item in data]
    else:
        # For other data types, return as is
        return data



        
        
        
def getanalysisreport(kwargs):

    account_type = kwargs.get('account_type')
    account_code = kwargs.get('account_code')
    format = kwargs.get('format')
    from_date = kwargs.get('from_date')
    to_date = kwargs.get('to_date')
    transaction_types = kwargs.get('transaction_types')
    merge_child = kwargs.get('merge_child')
    base_url = kwargs.get('base_url')
    branch_code = kwargs.get('branch_code')
    portal_reference_code = kwargs.get('portal_reference_code')
    if base_url != None:
        full_url = f"{base_url}/getAcAnalysisRptXML?sBrCode={branch_code}&PortalRefCode={portal_reference_code}"
    
    #-----------------end---------------------------
   
    headers = {}
    payload = f"""<Filterdata><param AcType=\"{account_type}\" AcCode=\"{account_code}\" Format=\"{format}\" FromDate=\"{from_date}\" ToDate=\"{to_date}\" TxnTypes=\"{transaction_types}\" MergeChild=\"{merge_child}\" /></Filterdata>"""
    response = requests.request("POST", full_url, headers=headers, data=payload)
    decoded_xml = html.unescape(response.text)
    root = ET.fromstring(decoded_xml)

        # Define the namespace if present in the XML
    namespace = "{http://schemas.microsoft.com/2003/10/Serialization/}"

    # Find the RESULT node
    result = root.find(f".//{namespace}RESULT")
    if result is not None and not result.attrib and not list(result):
        return False
    else:
        pass
    # Step 2: Remove the `<string>` wrapper
    start = decoded_xml.find("<RESULT>")
    end = decoded_xml.find("</RESULT>") + len("</RESULT>")
    cleaned_xml = decoded_xml[start:end]
    # Step 3: Parse XML to a dictionary
    parsed_dict = xmltodict.parse(cleaned_xml)
    # Step 4: Convert dictionary to JSON
    # self.json_result = json.dumps(parsed_dict, indent=4)
    json_result = clean_data(parsed_dict)
    
    return json_result
       


def generate_auto_trx(kwargs):
    pay_obj = kwargs.get('pay_obj')
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
        # ______________________________end__________________________________________________


    account_code  = pay_obj.agency.organization.easy_link_billing_code
    date = datetime.fromtimestamp(time.time())
    today_date = date.strftime("%d/%m/%Y")
    # today_date= "04/12/2024"
    if base_url :
        full_url = f"{base_url}/GenerateAutoTxn?sBrCode={branch_code}&PortalRefCode={portal_reference_code}&sTxnType=027"
    
    #-----------------end---------------------------
    headers = {}
    payload = f"""<TxnData>\n    <Txn txnDt=\"{today_date}\" CustCode=\"{account_code}\" credittype=\"F\" BankCode=\"A0344\" PaxName=\"{pax_name}\" TxnRefNo=\"{payment_id}\" NR1=\"Online Recharge from Portal \" NR2=\"\" NR3=\"\" NR4=\"\" TxnAmount=\"{amount}\"></Txn>\n</TxnData>"""
    response = requests.request("POST", full_url, headers=headers, data=payload)
    decoded_xml = html.unescape(response.text)
    ErrorLog.objects.create(module="generate_auto_trx",erros={"response":str(decoded_xml)})

def razor_webhook(kwargs):
    
    payment_id_link = kwargs.get('razorpay_payment_link_id')
    pay_obj  = Payments.objects.filter(payment_id_link=payment_id_link,status="paid",call_back=True).first()
    if pay_obj:
        kwargs['pay_obj'] = pay_obj
        generate_auto_trx(kwargs)
    ErrorLog.objects.create(module="call_razor_webhook",erros={"pay_obj":str(pay_obj)})
    
    
  
    pass


def razor_pay(kwargs):
    
    amount = kwargs.get('amount')
    description = kwargs.get('description')
    billing_code = kwargs.get('billing_code')
    account_code = kwargs.get('account_code')
    user = kwargs.get('user')
    organization_name = kwargs.get('organization_name')
    name = kwargs.get('name')
    email = kwargs.get('email')
    phone_number = kwargs.get('phone_number')
    organization_id = kwargs.get('organization_id')
    callback_url = kwargs.get('callback_url')
    api_key = kwargs.get('api_key')
    # sms = kwargs.get('sms',False)
    # email = kwargs.get('email',True)
    api_secret = kwargs.get('api_secret')
    client = razorpay.Client(auth=(f"{api_key}", f"{api_secret}"))
    response = client.payment_link.create({
    "amount": int(amount) * 100,
    "currency": "INR",
    "description": description,
    "customer": {
        "name": name,
        "email": email,
        "contact": phone_number,
    },
    "notify": {
        "sms": True,
        "email": True
    },
    "reminder_enable": True,
    "notes": {
        "organization_id": organization_id,
        "billing_code" : billing_code,
        "paid_by" : user,
        "organization_name" : organization_name,
        "account_code": account_code
    },
    "callback_url": f'{callback_url}status?confirmation=success&payment_method=razor_pay',
    "callback_method": "get"
    })
    payment_obj = kwargs.get('payment_obj')
    
    payment_id_link = response.get('id')
    payment_obj.payment_id_link = payment_id_link
    payment_obj.save()
    response = {"short_url":response.get('short_url')}
    return response


def get_ledger_report(kwargs):

    account_type = kwargs.get('account_type')
    account_code = kwargs.get('account_code')
    from_date = kwargs.get('from_date')
    to_date = kwargs.get('to_date')
    base_url = kwargs.get('base_url')
    branch_code = kwargs.get('branch_code')
    portal_reference_code = kwargs.get('portal_reference_code')
    if base_url != None:
        full_url = f"{base_url}/getLedgerRptXML/?sBrCode={branch_code}&PortalRefCode={portal_reference_code}"
    


    account_type = "CC"
    payload = f"<Filterdata>\r\n<param AcType=\"{account_type}\" AcCode=\"{account_code}\" Format=\"AAB\" FromDate=\"{from_date}\" ToDate=\"{to_date}\" />\r\n</Filterdata>"
    headers = {
        'Content-Type': 'text/plain',
    }
    response = requests.request("POST", full_url, headers=headers, data=payload)
    # decoded_xml = html.unescape(response.text)
    # print("response-----",decoded_xml)
    # root = ET.fromstring(decoded_xml)

    #     # Define the namespace if present in the XML
    # namespace = "{http://schemas.microsoft.com/2003/10/Serialization/}"

    # # Find the RESULT node
    # result = root.find(f".//{namespace}RESULT")
    # if result is not None and not result.attrib and not list(result):
    #     return False
    # else:
    #     pass
    # # Step 2: Remove the `<string>` wrapper
    # start = decoded_xml.find("<RESULT>")
    # end = decoded_xml.find("</RESULT>") + len("</RESULT>")
    # cleaned_xml = decoded_xml[start:end]
    # # Step 3: Parse XML to a dictionary
    # parsed_dict = xmltodict.parse(cleaned_xml)
    # # Step 4: Convert dictionary to JSON
    # # self.json_result = json.dumps(parsed_dict, indent=4)
    # json_result = clean_data(parsed_dict)
    
    return response


def get_credit_limit(base_url,
                            portal_ref_code,
                            billing_code
                            
                            ):
        url = f"{base_url}/getAvlCreditLimit/?PortalRefCode={portal_ref_code}&sAcCode=&sRefAcCode={billing_code}"
        header = {"Content-Type":"text/plain"}
        response = requests.post(url=url, headers=header)

        return XMLData.get_credit_limit_response(response)

   
def get_accounting_software_credentials(organization_obj):
    # getting objects 
        try:

            # _____________________________start___________________________________________________
            obj = organization_obj.easy_link_billing_account
            # ______________________________end__________________________________________________


            # obj = Integration.objects.get(name = "easy-link  backoffice suit",country_id=country_id)
        # except Integration.DoesNotExist:
        #     raise Exception("easy-link  backoffice suit is not configured in  the  portal ")
        # except Integration.DoesNotExist:
        #     raise Exception("easy-link  backoffice suit is not configured in  the  portal ")

        except Exception as e:
            raise Exception(str(e))
        
        # getting credentials 
        try:
            data = obj.data[0]
            url = data["url"]
            branch_code = data["branch_code"]
            portal_reference_code = data["portal_reference_code"]
        except KeyError as e:
            raise Exception(f"{obj.name} is not configured correctly missing keys {e} ")
        except Exception as e:
            raise Exception(str(e))
        
        return url,branch_code,portal_reference_code
    

    
def update_credit_limit(
        s_br_code,
        portal_ref_code,
        s_acc_code,
        s_cred_limit,
        s_credit_type,
        base_url
        ):

    url = f"{base_url}/UpdateCreditLimit/?sBrCode={s_br_code}&PortalRefCode={portal_ref_code}&sAcCode={s_acc_code}&sRefAcCode=&sCreditLimit={s_cred_limit}&sCreditType={s_credit_type}"

    header = {"Content-Type":"text/plain"}
    response = requests.post(url=url, headers=header)
    try : 
        ErrorLog.objects.create(module="update_credit_limit_in easylink",erros={"response":str(response),"all_params":str(url)})
    except:
        pass
    return XMLData.update_limit_response(response)
