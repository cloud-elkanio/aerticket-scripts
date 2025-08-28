import requests,json
from requests.auth import HTTPBasicAuth
from vendors.buses import mongo_handler

def authentication(base_url,credentials):
    client_id = credentials.get("client_id")
    username = credentials.get("username")
    password = credentials.get("password")
    end_user_ip = credentials.get("end_user_ip")
    header = {
                'Content-Type': 'application/json'    
            }

    auth_body = {
        "ClientId": client_id,
        "UserName": username,
        "Password": password, 
        "EndUserIp": end_user_ip
        }
    url = base_url+"/rest/Authenticate"
    log = {"request_type":"POST","vendor":"TBO","headers":header,
            "payload":auth_body,"api":"auth","url":url,"session_id":""}
    try:
        auth_response = requests.post(url, headers=header, json=auth_body)
        res = auth_response.json()
        token = res['TokenId']
        log["response"] = {"status":True,"data":res}
        api_logs_to_mongo(log)
        return token
    except:
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None

def get_city_list(base_url,credentials):
    payload = {
            "IpAddress": credentials.get("end_user_ip"),
            "TokenId": credentials.get('token'),
            "ClientId": credentials.get('client_id')
            }
    headers = {
                'Content-Type': 'application/json'    
            }

    url = base_url+"/rest/GetBusCityList"
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"sync","url":url,"session_id":""}
    try:
        response = requests.post(url, headers=headers, json=payload)
        res = response.json()
        log["response"] = {"status":True,"data":res}
        api_logs_to_mongo(log)
        return res
    except:
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None

def bus_search(base_url,credentials,data,session_id):
    payload = {
            "EndUserIp": credentials.get("end_user_ip"),
            "TokenId": credentials.get('token'),
            "ClientId": credentials.get('client_id'),
            "DateOfJourney":data.get('date'),#YYYY/mm/dd
            "OriginId":data.get('from'),
            "DestinationId":data.get('to'),
            "PreferredCurrency":data.get('currency')
            }
    headers = {
                'Content-Type': 'application/json'    
            }

    url = base_url+"/rest/Search"
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"search","url":url,"session_id":session_id}
    try:
        response = requests.post(url, headers=headers, json=payload)
        res = response.json()
        log["response"] = {"status":True,"data":res}
        api_logs_to_mongo(log)
        return res
    except:
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None

def seatmap(base_url,credentials,data,session_id):
    payload = {
            "EndUserIp": credentials.get("end_user_ip"),
            "TokenId": credentials.get('token'),
            "TraceId": data.get('TraceId'),
            "ResultIndex":data.get('ResultIndex')
            }
    headers = {
                'Content-Type': 'application/json'    
            }

    url = base_url+"/rest/GetBusSeatLayOut"
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"seatmap","url":url,"session_id":session_id}
    try:
        print("payload",payload)
        response = requests.post(url, headers=headers, json=payload)
        print("responser",response.text)
        res = response.json()
        log["response"] = {"status":True,"data":res}
        api_logs_to_mongo(log)
        return res
    except:
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None

def pickup_drop(base_url,credentials,data,session_id):

    payload = {
            "EndUserIp": credentials.get("end_user_ip"),
            "TokenId": credentials.get('token'),
            "TraceId": data.get('TraceId'),
            "ResultIndex":data.get('ResultIndex')
            }
    headers = {
                'Content-Type': 'application/json'    
            }

    url = base_url+"/rest/GetBoardingPointDetails"
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"pickup_drop","url":url,"session_id":session_id}
    try:
        response = requests.post(url, headers=headers, json=payload)
        res = response.json()
        log["response"] = {"status":True,"data":res}
        api_logs_to_mongo(log)
        return res
    except:
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None

def block(base_url,credentials,data,session_id):
    payload = {
            "EndUserIp": credentials.get("end_user_ip"),
            "TokenId": credentials.get('token'),
            "TraceId": data.get('TraceId'),
            "ResultIndex":data.get('ResultIndex'),
            "BoardingPointId": data.get("boarding"),
            "DroppingPointId": data.get("dropoff"),
            "Passenger":  data.get('pax_list'),
            }

    headers = {
                'Content-Type': 'application/json'    
            }

    url = base_url+"/rest/Block"
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"block","url":url,"session_id":session_id}
    try:
        response = requests.post(url, headers=headers, json=payload)
        res = response.json()
        log["response"] = {"status":True,"data":res}
        api_logs_to_mongo(log)
        return res
    except:
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None

def book(base_url,credentials,data,session_id):

    payload = {
            "EndUserIp": credentials.get("end_user_ip"),
            "TokenId": credentials.get('token'),
            "TraceId": data.get('TraceId'),
            "ResultIndex":data.get('ResultIndex'),
            "BoardingPointId": data.get("boarding"),
            "DroppingPointId": data.get("dropoff"),
            "Passenger":  data.get('pax_list'),
            }

    headers = {
                'Content-Type': 'application/json'    
            }

    url = base_url+"/rest/Book"
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"book","url":url,"session_id":session_id}
    try:
        response = requests.post(url, headers=headers, json=payload)
        res = response.json()
        log["response"] = {"status":True,"data":res}
        api_logs_to_mongo(log)
        return res
    except:
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None

def booking_detail(base_url,credentials,data,session_id):

    payload = {
            "EndUserIp": credentials.get("end_user_ip"),
            "TokenId": credentials.get('token'),
            "TraceId": data.get('TraceId'),
            "BusId":data.get('BusId'),
            "IsBaseCurrencyRequired": False,

            }
    headers = {
                'Content-Type': 'application/json'    
            }
    print("payload",payload)
    url = base_url+"/rest/GetBookingDetail"
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"cancellation","url":url,"session_id":session_id}
    try:
        response = requests.post(url, headers=headers, json=payload)
        res = response.json()
        log["response"] = {"status":True,"data":res}
        api_logs_to_mongo(log)
        return res
    except:
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None
    
def cancellation_charges(base_url,credentials,data,session_id):
    client_id = credentials.get("client_id")

    payload = {
            "EndUserIp": credentials.get("end_user_ip"),
            "TokenId": credentials.get('token'),
            "TraceId": data.get('TraceId'),
            "ClientId":client_id,
            "ChangeRequestId": [3534], # request code

            }
    headers = {
                'Content-Type': 'application/json'    
            }

    url = base_url+"/rest/GetChangeRequestStatus"
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"cancellation","url":url,"session_id":session_id}
    try:
        response = requests.post(url, headers=headers, json=payload)
        res = response.json()
        log["response"] = {"status":True,"data":res}
        api_logs_to_mongo(log)
        return res|{"payload":payload}
    except:
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None

def cancel_ticket(base_url,credentials,data,session_id):
    client_id = credentials.get("client_id")

    payload = {
            "EndUserIp": credentials.get("end_user_ip"),
            "TokenId": credentials.get('token'),
            "TraceId": None,
            "BusId": data.get('BusId'),
            "BookingMode": data.get('BookingMode'),
            "RequestType": 11,  #cancel code
            "ClientId":client_id,
            "Remarks":data.get("Remarks")
            }
    headers = {
                'Content-Type': 'application/json'    
            }

    url = base_url+"/rest/SendChangeRequest"
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"cancellation","url":url,"session_id":session_id}
    try:
        response = requests.post(url, headers=headers, json=payload)
        res = response.json()
        log["response"] = {"status":True,"data":res}
        api_logs_to_mongo(log)
        return res
    except:
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None



def api_logs_to_mongo(log):
    mongo_handler.Mongo().log_vendor_api(log)