import requests,json
from requests.auth import HTTPBasicAuth
from vendors.flights import mongo_handler
from base64 import b64encode

def basic_auth(username, password):
    token = b64encode(f"{username}:{password}".encode('utf-8')).decode("ascii")
    return f'Basic {token}'

def authentication(base_url,credentials):
    username = credentials.get("username")
    password = credentials.get("password")
    scope = credentials.get("scope")
    grant_type = credentials.get("grant_type")

    payload = {}

    header = {  "Content-Type":"application/json",
              "Authorization" :  basic_auth(username, password)
          }


    url =base_url +f'oauth2/token?grant_type={grant_type}&scope={scope}'
    print("base_url",base_url)
    log = {"request_type":"POST","vendor":"Verteil","headers":header,
            "payload":payload,"api":"auth","url":url,"session_id":""}
    try:
        response = requests.post(url,data= json.dumps(payload),headers=header)
        response_dict = response.json()
        access_token = response_dict.get('access_token')
        expires_in = response_dict.get('expires_in')
        log["response"] = {"status":True,"data":response_dict}
        api_logs_to_mongo(log)
        return access_token,expires_in
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return None,None
    
def flight_search(baseurl,credentials,fare_type,pax,segments,session_id):
    access_token = credentials.get("token")
    header = {  "Content-Type":"application/json",
                "Authorization":"Bearer "+str(access_token) ,
                "service":"AirShopping"}

    data = {"Preference": {"FarePreferences": {
                              "Types": {"Type": [{"Code": fare_type}]}}
                        },
            "ResponseParameters": {"SortOrder": [{
                                    "Order": "ASCENDING ","Parameter": "PRICE"}],
                                "ShopResultPreference": "OPTIMIZED"},
            "Travelers": {"Traveler": pax},
            
            "CoreQuery": {"OriginDestinations": 
                              {"OriginDestination": segments}}}
    print("56 data",data)
    url = baseurl+"entrygate/rest/request:airShopping"
    log = {"request_type":"POST","vendor":"TBO","headers":header,
            "payload":data,"api":"flight_search","url":url,"session_id":session_id}
    try:
        response = requests.post(url=url, headers=header, json=data)
        if response.status_code == 200:
            log["response"] = {"status":True,"data":response.json()}
            api_logs_to_mongo(log)
            return response.json()
        else:
            log["response"] = {"status":False,"data":response.json()}
            api_logs_to_mongo(log)
            return None
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return None

    












































def api_logs_to_mongo(log):
    mongo_handler.Mongo().log_vendor_api(log)