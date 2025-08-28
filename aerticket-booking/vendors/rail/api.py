import requests
from vendors.rail import mongo_handler
from requests.auth import HTTPBasicAuth


def authentication(credentials):
    username = credentials.get("user_name")
    password = credentials.get("password")

    auth_body = {
        "UserName": username,
        "Password": password 
        }
    base_url = credentials.get("base_url") +"/auth/request-token"
    log = {"request_type":"POST","vendor":"Rail - FWMSPL","headers":None,
            "payload":auth_body,"api":"authenticate","url":base_url,"session_id":""}
    try:
        response = requests.post(base_url, auth=HTTPBasicAuth(username, password))
        if response.status_code == 201:
            token = response.json().get("token")
            log["response"] = {"status":True,"data":response.text}
        else:
            token = None
            log["response"] = {"status":False,"data":response.text}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        token = None
    api_logs_to_mongo(log)
    return token

def login_helper(credentials,userID):
    """
    Calls the /loginhelper endpoint with a POST request using Bearer Token authentication.
    """
    # Prepare the payload and URL
    payload = {
        "userID": userID
    }
    url = credentials.get("base_url") + "/loginhelper"
    
    # Set up headers with the Bearer Token and Content-Type as JSON
    token = credentials.get("token_id")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Log structure similar to your authentication() function
    log = {
        "request_type": "POST",
        "vendor": "Rail - FWMSPL",
        "headers": headers,
        "payload": payload,
        "api": "loginhelper",
        "url": url,
        "session_id": ""
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(response.text)
        if response.status_code in [200,201]:
            data = response.json()
            log["response"] = {"status": True, "data": response.text}
        else:
            data = None
            log["response"] = {"status": False, "data": response.text}
    except Exception as e:
        log["response"] = {"status": False, "data": str(e)}
        data = None
    
    # Log the API call
    api_logs_to_mongo(log)
    return data


def api_logs_to_mongo(log):
    mongo_handler.Mongo().log_vendor_api(log)


