import requests
from vendors.buses import mongo_handler
import json

def api_logs_to_mongo(log):
    mongo_handler.Mongo().log_vendor_api(log)
def get_city_list(**kwargs):


    base_url = kwargs['base_url']
    url = f"{base_url}Bus_CityList"

    payload = {
      "Auth_Header": {
        "UserId": kwargs['username'],
        "Password": kwargs['password'],
        "Request_Id": str(kwargs['request_id']),
        "IP_Address": kwargs['ip_address'],
        "IMEI_Number": kwargs['IMEI_number']
      }
    }

    log = {"request_type": "POST", "vendor": "flyshop", "headers": '',
           "payload": payload, "api": "get-city-list", "url": url, "session_id": ""}

    try:
        headers = {
            'Content-Type':'application/json'
        }

        response = requests.request("POST", url, headers=headers, json=payload)

        res = response.json()

        log["response"] = {"status":True,"data":res}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        res = None

    api_logs_to_mongo(log)

    return res



def BusSearch(**kwargs):


    base_url = kwargs['base_url']
    url = f"{base_url}Bus_Search"

    payload = {
      "Auth_Header": {
        "UserId": kwargs['username'],
        "Password": kwargs['password'],
        "Request_Id": str(kwargs['request_id']),
        "IP_Address": kwargs['ip_address'],
        "IMEI_Number": kwargs['IMEI_number']
      },
        "From_City": kwargs['from_city'],
        "To_City": kwargs['to_city'],
        "TravelDate": kwargs['travel_date']
    }

    log = {"request_type": "POST", "vendor": "flyshop", "headers": '',
           "payload": payload, "api": "get-bus-list", "url": url, "session_id": ""}

    try:
        headers = {
            'Content-Type':'application/json'
        }

        response = requests.request("POST", url, headers=headers, json=payload)

        res = response.json()

        log["response"] = {"status":True,"data":res}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        res = None

    api_logs_to_mongo(log)

    return res

