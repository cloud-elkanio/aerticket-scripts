import requests,json
from requests.auth import HTTPBasicAuth
from vendors.flights import mongo_handler
import traceback as tb

def authentication(base_url,credentials):
    client_id = credentials.get("client_id")
    username = credentials.get("username")
    password = credentials.get("password")
    end_user_ip = credentials.get("end_user_ip",credentials["end_user_ip"])
    header = {
                'Content-Type': 'application/json'    
            }
    auth_body = {
        "ClientId": client_id,
        "UserName": username,
        "Password": password, 
        "EndUserIp": end_user_ip
        }
    url = base_url+"rest/Authenticate"
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
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return None

def flight_search(baseurl,credentials,trip_type,pax,segments,fare_type,
                  session_id,book_filters):
    if book_filters.get("is_proceed") == False:
        return None
    else:
        header = {'Content-Type': 'application/json'}
        data = {
            "EndUserIp": credentials["end_user_ip"],
            "TokenId": credentials["token"],
            "AdultCount": pax['adults'],
            "ChildCount": pax['children'],
            "InfantCount": pax['infants'],
            "DirectFlight": "false",
            "OneStopFlight": "false",
            "JourneyType": trip_type,
            "PreferredAirlines": book_filters.get("filtered_airlines"),
            "Segments":segments,
            "Sources": None,
            "ResultFareType":fare_type
            }
        url = baseurl+"rest/Search"
        log = {"request_type":"POST","vendor":"TBO","headers":header,
                "payload":data,"api":"flight_search","url":url,"session_id":session_id}
        try:
            response = requests.post(url=url, headers=header, json=data,timeout=30)
            if response.status_code == 200:
                log["response"] = {"status":True,"data":response.json()}
                api_logs_to_mongo(log)
                return response.json()
            else:
                log["response"] = {"status":False,"data":response.json()}
                api_logs_to_mongo(log)
                return None
        except:
            error = tb.format_exc()
            log["response"] = {"status":False,"data":{},"error":error}
            api_logs_to_mongo(log)
            return None
   
def fare_rule(baseurl,credentials,TraceId,ResultIndex,session_id):
    headers = {"Content-Type": "application/json"}
    url =  baseurl+"rest/FareRule"

    payload = json.dumps(
        {
            "EndUserIp": credentials["end_user_ip"],
            "TokenId": credentials["token"],
            "TraceId": TraceId,
            "ResultIndex": ResultIndex
            }
        )
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":json.loads(payload),"api":"fare_rule","url":url,"session_id":session_id}
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        log["response"] = {"status":True,"data":response.json()}
        api_logs_to_mongo(log)
        return json.loads(response.text)
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return None

def fare_quote(baseurl,credentials,TraceId,ResultIndex,session_id):
    headers = {"Content-Type": "application/json"}
    url =  baseurl+"rest/FareQuote"
    payload = json.dumps(
        {
            "EndUserIp": credentials["end_user_ip"],
            "TokenId": credentials["token"],
            "TraceId": TraceId,
            "ResultIndex": ResultIndex
            }
        )
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":json.loads(payload),"api":"fare_quote","url":url,"session_id":session_id}
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        log["response"] = {"status":False,"data":response.json()}
        api_logs_to_mongo(log)
        return json.loads(response.text)
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return None

def ssr(baseurl,credentials,TraceId,ResultIndex,session_id):
    headers = {"Content-Type": "application/json"}
    url =  baseurl+"rest/SSR"
    payload = json.dumps(
        {
            "EndUserIp": credentials["end_user_ip"],
            "TokenId": credentials["token"],
            "TraceId": TraceId,
            "ResultIndex": ResultIndex
            }
                    )
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":json.loads(payload),"api":"ssr","url":url,"session_id":session_id}

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        log["response"] = {"status":True,"data":response.json()}
        api_logs_to_mongo(log)
        return json.loads(response.text)
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return {'Response':{'ResponseStatus':0}}

def hold(baseurl,credentials,TraceId,ResultIndex,Passengers,session_id):
    headers = {"Content-Type": "application/json"}
    url =  baseurl+"rest/Book"
    payload = json.dumps(
        {
            "EndUserIp": credentials["end_user_ip"],
            "TokenId": credentials["token"],
            "TraceId": TraceId,
            "ResultIndex": ResultIndex,
            "Passengers": Passengers
            }
                    )
    log = {"request_type":"POST","vendor":'TBO',"headers":headers,
                "payload":json.loads(payload),"api":"hold","url":url,"session_id":session_id}
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        json_response = json.loads(response.text)
        if json_response['Response']['ResponseStatus'] == 1:
            log["response"] = {"status":True,"data":json_response}
            api_logs_to_mongo(log)
        else:
            log["response"] = {"status":False,"data":json_response}
            api_logs_to_mongo(log)
        return log["response"]
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return log["response"]

def release_hold(baseurl,credentials,BookingId,source,session_id):
    url =  baseurl+"rest/ReleasePNRRequest"
    headers = {"Content-Type": "application/json"}
    payload = json.dumps(
        {
            "EndUserIp": credentials["end_user_ip"],
            "TokenId": credentials["token"],
            "BookingId": BookingId,
            "Source": source
            }
        )
    log = {"request_type":"POST","vendor":'TBO',"headers":headers,
               "payload":json.loads(payload),"api":"release_hold","url":url,
               "session_id":session_id}
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        json_response = json.loads(response.text)
        if json_response['Response']['ResponseStatus'] == 1:
            log["response"] = {"status":True,"data":json_response}
        else:
            log["response"] = {"status":False,"data":json_response}
        api_logs_to_mongo(log)
        return log["response"]
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return log["response"]

def cancellation_charges(baseurl,credentials,BookingId,session_id):
    url =  baseurl+"rest/GetCancellationCharges"
    headers = {"Content-Type": "application/json"}

    payload = {
            "EndUserIp": credentials["end_user_ip"],
            "TokenId": credentials["token"],
            "BookingId": BookingId,
            "RequestType": "2",
            "BookingMode": "5",
            }
    log = {"request_type":"POST","vendor":'TBO',"headers":headers,
               "payload":payload,"api":"cancellation_charges","url":url,
               "session_id":session_id}
    try:
        response = requests.request("POST", url, headers = headers, data = json.dumps(payload))
        json_response = json.loads(response.text)
        if json_response['Response']['ResponseStatus'] == 1:
            log["response"] = {"status":True,"data":json_response}
        else:
            log["response"] = {"status":False,"data":json_response}
        api_logs_to_mongo(log)
        return log["response"]
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return log["response"]

def cancel_ticket(baseurl,credentials,BookingId,TicketId,Sectors,is_full_trip,session_id):
    url =  baseurl+"rest/SendChangeRequest"
    headers = {"Content-Type": "application/json"}
    payload = {
            "EndUserIp": credentials["end_user_ip"],
            "TokenId": credentials["token"],
            "BookingId": BookingId,
            "RequestType": "1",
            "CancellationType": "3",
            "Remarks": "Customer wants to cancel the booking."
            }
    if not is_full_trip:
        payload["Sectors"] = Sectors
        payload["TicketId"] = TicketId
        payload["RequestType"] = 2
    log = {"request_type":"POST","vendor":'TBO',"headers":headers,
               "payload":payload,"api":"cancel_ticket","url":url,
               "session_id":session_id}
    try:
        response = requests.request("POST", url, headers = headers, data = json.dumps(payload))
        json_response = json.loads(response.text)
        if json_response['Response']['ResponseStatus'] == 1:
            log["response"] = {"status":True,"data":json_response}
        else:
            log["response"] = {"status":False,"data":json_response}
        api_logs_to_mongo(log)
        return log["response"]
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return log["response"]

def check_cancellation_status(baseurl,credentials,ChangeRequestId,session_id):
    url =  baseurl+"rest/GetChangeRequestStatus"
    headers = {"Content-Type": "application/json"}
    payload = {
            "EndUserIp": credentials["end_user_ip"],
            "TokenId": credentials["token"],
            "ChangeRequestId": ChangeRequestId,
            }
    log = {"request_type":"POST","vendor":'TBO',"headers":headers,
               "payload":payload,"api":"check_cancellation_status","url":url,
               "session_id":session_id}
    try:
        response = requests.request("POST", url, headers = headers, data = json.dumps(payload))
        json_response = json.loads(response.text)
        if json_response['Response']['ResponseStatus'] == 1:
            log["response"] = {"status":True,"data":json_response}
        else:
            log["response"] = {"status":False,"data":json_response}
        api_logs_to_mongo(log)
        return log["response"]
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return log["response"]

def ticket_lcc(baseurl,credentials,TraceId,ResultIndex,Passengers,session_id):
    headers = {"Content-Type": "application/json"}
    url =  baseurl+"rest/Ticket"

    payload = {"PreferredCurrency": "INR",
            "ResultIndex": ResultIndex,
            "AgentReferenceNo": "sonam1234567890",
            "Passengers":Passengers,
            "EndUserIp": credentials["end_user_ip"],
            "TokenId": credentials["token"],
            "TraceId": TraceId
            }
    log = {"request_type":"POST","vendor":'TBO',"headers":headers,
                "payload":payload,"api":"ticket_lcc","url":url,"session_id":session_id}
    try:
        response = requests.request("POST", url, headers=headers, data = json.dumps(payload))
        json_response = json.loads(response.text)
        if json_response['Response']['ResponseStatus'] == 1:
            log["response"] = {"status":True,"data":json_response}
        else:
            log["response"] = {"status":False,"data":json_response}
        api_logs_to_mongo(log)
        return log["response"]
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return log["response"]

def ticket(baseurl,credentials,TraceId,ResultIndex,pnr,bookingId,session_id): #Passengers its alist
    headers = {"Content-Type": "application/json"}
    url =  baseurl+"rest/Ticket"
    payload = {
            "EndUserIp": credentials["end_user_ip"],
            "TokenId": credentials["token"],
            "TraceId": TraceId,
            "PNR": pnr,
            "BookingId": bookingId
            }
    log = {"request_type":"POST","vendor":'TBO',"headers":headers,
               "payload":payload,"api":"ticket","url":url,"session_id":session_id}
    try:
        response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
        json_response = json.loads(response.text)
        if json_response['Response']['ResponseStatus'] == 1:
            log["response"] = {"status":True,"data":json_response}
        else:
            log["response"] = {"status":False,"data":json_response}
        api_logs_to_mongo(log)
        return log["response"]
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return log["response"]
    
def get_current_ticket_status(baseurl,credentials,TraceId,session_id):
    headers = {"Content-Type": "application/json"}
    url =  baseurl+"rest/GetBookingDetails"

    payload = {"EndUserIp": credentials["end_user_ip"],"TokenId": credentials["token"],"TraceId": TraceId}
    log = {"request_type":"POST","vendor":"TBO","headers":headers,
            "payload":payload,"api":"get_current_ticket_status","url":url,"session_id":session_id}
    try:
        response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
        log["response"] = {"status":True,"data":response.json()}
        api_logs_to_mongo(log)
        return log["response"]
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return log["response"]

def api_logs_to_mongo(log):
    mongo_handler.Mongo().log_vendor_api(log)