import requests
from vendors.transfers import mongo_handler

def authentication(credentials):
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
    base_url = credentials.get("auth_url") +"/rest/Authenticate"
    log = {"request_type":"POST","vendor":"TBO","headers":header,
            "payload":auth_body,"api":"authenticate","url":base_url,"session_id":""}
    try:
        auth_response = requests.post(base_url, headers=header, json=auth_body)
        res = auth_response.json()
        token = res['TokenId']
        log["response"] = {"status":True,"data":res}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        token = None
    api_logs_to_mongo(log)
    return token


def fetch_country_list(token_id, client_id, end_user_ip, base_url):
    payload = {
        "TokenId": token_id,
        "ClientId": client_id,
        "EndUserIp": end_user_ip,
    }
    url = f"{base_url}/rest/CountryList"
    log = {"request_type":"POST","vendor":"TBO","headers":'',
            "payload":payload,"api":"fetch_country_list","url":url,"session_id":""}
    try:
        response = requests.post(url, json=payload)
        res = response.json()
        log["response"] = {"status":True,"data":res}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        res = None
    api_logs_to_mongo(log)
    return res

def fetch_city_data(token_id,end_user_ip, base_url,data):
    payload = {
        "TokenId": token_id,
        "CountryCode": data.get("country_code","IN"),
        "SearchType": str(data.get("search_type","1")),
        "EndUserIp": end_user_ip,
    }

    url = f"{base_url}/rest/GetDestinationSearchStaticData"
    log = {"request_type":"POST","vendor":"TBO","headers":'',
            "payload":payload,"api":"fetch_city_hotel_data","url":url,"session_id":""}
    try:
        response = requests.post(url, json=payload)
        res = response.json()
        log["response"] = {"status":True,"data":res}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        res = None
    api_logs_to_mongo(log)
    return res

def fetch_transfer_data(token_id, client_id, end_user_ip, base_url,data):
    payload = {
        "TokenId": token_id,
        "ClientId": client_id,
        "EndUserIp": end_user_ip,
        "CityId": data.get("city_code"),
        "TransferCategoryType": str(data.get("search_type","1")),
    }

    url = f"{base_url}/rest/GetTransferStaticData"
    log = {"request_type":"POST","vendor":"TBO","headers":'',
            "payload":payload,"api":"fetch_transfer_data","url":url,"session_id":""}
    try:
        response = requests.post(url, json=payload)
        res = response.json()
        log["response"] = {"status":True,"data":res}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        res = None
    api_logs_to_mongo(log)
    return res

def fetch_transfer_results_data(token_id, end_user_ip, base_url,session_id,data):
    payload = {
        "TransferTime": data['transfer_time'],
        "TransferDate": data['transfer_date'],
        "AdultCount": data['adult_count'],
        "PreferredLanguage": data['preferred_language'],
        "AlternateLanguage": data['alternate_language'],
        "PreferredCurrency": data['preferred_currency'],
        "IsBaseCurrencyRequired": False,
        "PickUpCode": data['pickup_code'],
        "PickUpPointCode": data['pickup_point_code'],
        "CityId": data['city_id'],
        "DropOffCode": data['dropoff_code'],
        "DropOffPointCode": data['dropoff_point_code'],
        "CountryCode": data['country_code'],
        "EndUserIp": end_user_ip,
        "TokenId": token_id,
    }
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    url = f"{base_url}/rest/Search"
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"fetch_transfer_results_data","url":url,"session_id":session_id}
    try:
        response = requests.post(url, json=payload,headers=headers)
        res = response.json()
        log["response"] = {"status":True,"data":res}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        res = None
    api_logs_to_mongo(log)
    return res
    
def book(token_id, end_user_ip, base_url,session_id,data):
    payload = {
        "IsVoucherBooking": True, #true = book, false =hold
        "NumOfPax": data.get("NumOfPax"),
        "PaxInfo": data.get("PaxInfo"),
        "PickUp": data.get("PickUp"),
        "DropOff": data.get("DropOff"),
        "Vehicles": data.get("Vehicles"),
        "ResultIndex": data.get("ResultIndex"),
        "TransferCode": data.get("TransferCode"),
        "VehicleIndex": [data.get("VehicleIndex")],
        "BookingMode": 5,
        "OccupiedPax": data.get("OccupiedPax"),
        "EndUserIp": end_user_ip,
        "TokenId": token_id,
        "TraceId": data.get("TraceId"),
    }
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    url = f"{base_url}/rest/Book"
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"book","url":url,"session_id":session_id}
    try:
        response = requests.post(url, json=payload,headers=headers)
        res = response.json()
        log["response"] = {"status":True,"data":res}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        res = None
    api_logs_to_mongo(log)
    return res

def get_booking_details(token_id, end_user_ip, base_url,session_id,data):
    payload = {
        "EndUserIp": end_user_ip,
        "TokenId": token_id,
    }
    booking_id = data.get("booking_id")
    TraceId = data.get('TraceId',None)
    if TraceId != None:
        payload['TraceId'] = TraceId
    elif booking_id is not None or booking_id.strip() != "":
        payload['BookingId'] = int(data.get("booking_id"))
    else:
        payload['ConfirmationNo'] = data.get("confirmation_number")
        payload['FirstName'] = data.get("f_name")
        payload['LastName'] = data.get("l_name")
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    url = f"{base_url}/rest/GetBookingDetail"
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"get_booking_details","url":url,"session_id":session_id}
    try:
        response = requests.post(url, json=payload,headers=headers)
        res = response.json()
        log["response"] = {"status":True,"data":res}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        res = None
    api_logs_to_mongo(log)
    return res



def api_logs_to_mongo(log):
    mongo_handler.Mongo().log_vendor_api(log)


