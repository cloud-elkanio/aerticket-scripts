from vendors.flights import mongo_handler
import requests,json
import traceback as tb

def flight_search(**kwargs):
    if kwargs.get("book_filters",{}).get("is_proceed") == False:
        return None
    else:
        preferredAirline = [{"code":code} for code in kwargs.get("book_filters",{}).get("filtered_airlines",[])]
        headers = {
            "apikey": kwargs.get("apikey"),
            "content-Type": "application/json",
        }
        if kwargs.get("fare_type") not in ["STUDENT","SENIOR_CITIZEN"]:
            searchModifiers ={"isDirectFlight": True, "isConnectingFlight": True}
        else:
            searchModifiers ={"isDirectFlight": True, "isConnectingFlight": True,
                            "pft":kwargs.get("fare_type")}
        if len(kwargs["segment_details"]) == 1:
            data = {
                "searchQuery": {
                    "cabinClass": kwargs["cabin_class"],
                    "paxInfo": kwargs["pax_data"],
                    "routeInfos": [
                        {
                            "fromCityOrAirport": {"code" :kwargs["segment_details"][0]["source_city"]},
                            "toCityOrAirport": {"code" :kwargs["segment_details"][0]["destination_city"]},
                            "travelDate": kwargs["segment_details"][0]["travel_date"],
                        }
                    ],

                    "preferredAirline": preferredAirline,
                    "searchModifiers": searchModifiers,
                }
            }
        else:
            data = {
                "searchQuery": {
                    "cabinClass": kwargs["cabin_class"],
                    "paxInfo": kwargs["pax_data"],
                    "routeInfos": [
                        {
                            "fromCityOrAirport": {"code" :kwargs["segment_details"][0]["source_city"]},
                            "toCityOrAirport": {"code" :kwargs["segment_details"][0]["destination_city"]},
                            "travelDate": kwargs["segment_details"][0]["travel_date"],
                        },
                                            {
                            "fromCityOrAirport": {"code" :kwargs["segment_details"][1]["source_city"]},
                            "toCityOrAirport": {"code" :kwargs["segment_details"][1]["destination_city"]},
                            "travelDate": kwargs["segment_details"][1]["travel_date"],
                        }
                    ],
                    "preferredAirline": preferredAirline,
                    "searchModifiers": searchModifiers,
                }
            }
        url = kwargs.get("baseurl")+"fms/v1/air-search-all"
        session_id = kwargs.get("session_id")
        log = {"request_type":"POST","vendor":"TripJack","headers":headers,
                "payload":data,"api":"flight_search","url":url,"session_id":session_id}
        try:
            response = requests.post(url = url, headers = headers, json = data, timeout = 30)
            if response.status_code == 200:
                log["response"] = {"status":True,"data":response.json()}
                api_logs_to_mongo(log)
                if response.json().get("searchResult",[]):
                    return response.json()
                else:
                    return None
            else:
                log["response"] = {"status":False,"data":response.json()}
                api_logs_to_mongo(log)
                return  None    
        except:
            error = tb.format_exc()
            log["response"] = {"status":False,"data":{},"error":error}
            api_logs_to_mongo(log)
            return None   
    
def fare_rule(**kwargs):
    headers = {
        "apikey": kwargs.get("apikey"),
        "content-Type": "application/json",
    }
    payload = json.dumps({
    "id": kwargs.get("fare_id"),
    "flowType": "SEARCH"
    })
    url = kwargs.get("baseurl")+"fms/v1/farerule"
    session_id = kwargs.get("session_id")
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
            "payload":json.loads(payload),"api":"fare_rule","url":url,"session_id":session_id}
    try:
        response = requests.post(url, headers=headers, data=payload)
        log["response"] = {"status":True,"data":json.loads(response.text)}
        api_logs_to_mongo(log)
        return json.loads(response.text)
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return None

def fare_quote(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    url =  kwargs.get("baseurl")+"fms/v1/review"
    payload = json.dumps(
            {
            "priceIds": [
            kwargs.get("transaction_id")           
        ]
    })
    session_id = kwargs.get("session_id")
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
            "payload":json.loads(payload),"api":"fare_quote","url":url,"session_id":session_id}
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        log["response"] = {"status":True,"data":json.loads(response.text)}
        api_logs_to_mongo(log)
        return json.loads(response.text)
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return None

def ssr(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    url =  kwargs.get("baseurl")+"fms/v1/review"
    payload = json.dumps(
            {
            "priceIds": [
            kwargs.get("transaction_id")           
        ]
    })
    session_id = kwargs.get("session_id")
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
            "payload":json.loads(payload),"api":"ssr","url":url,"session_id":session_id}
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        log["response"] = {"status":True,"data":json.loads(response.text)}
        api_logs_to_mongo(log)
        return json.loads(response.text)
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return None

def seat_ssr(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    url =  kwargs.get("baseurl")+"fms/v1/seat"
    payload = json.dumps(
            {"bookingId": kwargs.get("booking_id")})
    session_id = kwargs.get("session_id")
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
            "payload":json.loads(payload),"api":"ssr","url":url,"session_id":session_id}
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        log["response"] = {"status":True,"data":json.loads(response.text)}
        api_logs_to_mongo(log)
        return json.loads(response.text)
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return None

def hold(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    url = kwargs.get("baseurl") + "oms/v1/air/book"
    payload = kwargs.get("payload")
    session_id = kwargs.get("session_id")
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
            "payload":payload,"api":"hold","url":url,"session_id":session_id}
    try:
        response = requests.post(url, headers = headers, data = json.dumps(payload))
        if response.json()["status"]["success"] == True:
            log["response"] = {"status":True,"data":response.json()}
            api_logs_to_mongo(log)
            return {"status":True,"data":response.json()}
        else:
            log["response"] = {"status":False,"data":response.json()}
            api_logs_to_mongo(log)
            return {"status":False,"data":response.json()}
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def ticket_book_api(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    url = kwargs.get("baseurl") +"oms/v1/air/book"
    payload = kwargs.get("payload")
    session_id = kwargs.get("session_id")
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
            "payload":payload,"api":"ticket","url":url,"session_id":session_id}
    try:
        book_response = requests.post(url, headers = headers, data = json.dumps(payload))
        if book_response.json()["status"]["success"] == True:
            response =  {"status":True,"data":book_response.json()}
        else:
            response = {"status":False,"data":book_response.json()}
        log["response"] = response
        api_logs_to_mongo(log)
        return response
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def ticket_booking_details_api(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    url = kwargs.get("baseurl") +"oms/v1/booking-details"
    payload = {"bookingId":kwargs.get("booking_id"),"requirePaxPricing" :True}
    session_id = kwargs.get("session_id")
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
            "payload":payload,"api":"ticket_booking_details","url":url,"session_id":session_id}
    try:
        book_response = requests.post(url, headers = headers, data = json.dumps(payload),timeout=30)
        if book_response.json()["status"]["success"] == True:
            response =  {"status":True,"data":book_response.json()}
        else:
            response = {"status":False,"data":book_response.json()}
        log["response"] = response
        api_logs_to_mongo(log)
        return response
    except (requests.exceptions.Timeout, SystemExit):
        log["response"] = {"status":False,"data":{},"error":"Response timeout/SystemExit"}
        api_logs_to_mongo(log)
        return {"status":False,"data":{},"status_code":504}
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def conform_holded_fare(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    session_id = kwargs.get("session_id","")
    url = kwargs.get("baseurl") + "oms/v1/air/fare-validate"
    payload = {"bookingId":kwargs.get("booking_id")}
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
        "payload":payload,"api":"conform_holded_fare","url":url,"session_id":session_id}
    try:
        response = requests.post(url, headers = headers, data = json.dumps(payload))
        if response.json()["status"]["success"] == True:
            response = {"status":True,"data":response.json()}
        else:
            response = {"status":False,"data":response.json()}
        log["response"] = response
        api_logs_to_mongo(log)
        return response       
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def conform_holded_book(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    session_id = kwargs.get("session_id","")
    url = kwargs.get("baseurl") +"oms/v1/air/confirm-book"
    payload = {"bookingId":kwargs.get("booking_id"),"paymentInfos":[{"amount":kwargs.get("price")}]}
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
        "payload":payload,"api":"conform_holded_book","url":url,"session_id":session_id}
    try:
        response = requests.post(url, headers = headers, data = json.dumps(payload))
        if response.json()["status"]["success"] == True:
            response = {"status":True,"data":response.json()}
        else:
            response = {"status":False,"data":response.json()}
        log["response"] = response
        api_logs_to_mongo(log)
        return response  
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def release_hold(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    url = kwargs.get("baseurl") + "oms/v1/air/unhold"
    payload = {"bookingId":kwargs.get("booking_id"),"pnrs":[kwargs.get("pnrs")]}
    session_id = kwargs.get("session_id","")
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
        "payload":payload,"api":"release_hold","url":url,"session_id":session_id}
    try:
        response = requests.post(url, headers = headers, data = json.dumps(payload))
        if response.json()["status"]["success"] == True:
            response = {"status":True,"data":response.json()}
        else:
            response =  {"status":False,"data":response.json()}
        log["response"] = response
        api_logs_to_mongo(log)
        return response  
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def get_cancellation_charges(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    url = kwargs.get("baseurl") + "oms/v1/air/amendment/amendment-charges"
    session_id = kwargs.get("session_id","")
    if not kwargs["is_full_trip"]:
        payload = {"bookingId":kwargs.get("booking_id"),"type":"CANCELLATION","remarks":"checking paxwise cancellation charges",
                    "trips":kwargs.get("trips",[])}
    else:
        payload = {"bookingId":kwargs.get("booking_id"),"type":"CANCELLATION","remarks":"checking cancellation charges"}
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
        "payload":payload,"api":"get_cancellation_charges","url":url,"session_id":session_id}
    try:
        cancellation_charges = requests.post(url, headers = headers, data = json.dumps(payload))
        if cancellation_charges.json()["status"]["success"] == True:
            response =  {"status":True,"data":cancellation_charges.json()}
        else:
            response = {"status":False,"data":cancellation_charges.json()}
        log["response"] = response
        api_logs_to_mongo(log)
        return response  
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def cancel_ticket(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    url = kwargs.get("baseurl") + "oms/v1/air/amendment/submit-amendment"
    session_id = kwargs.get("session_id","")
    if not kwargs["is_full_trip"]:
        payload = {"bookingId":kwargs.get("booking_id"),"type":"CANCELLATION","remarks":kwargs.get("remarks","Other reason"),
                    "trips":kwargs.get("trips",[])}
    else:
        payload = {"bookingId":kwargs.get("booking_id"),"type":"CANCELLATION","remarks":kwargs.get("remarks","Other reason")}
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
        "payload":payload,"api":"cancel_ticket","url":url,"session_id":session_id}
    try:
        cancellation_response = requests.post(url, headers = headers, data = json.dumps(payload))
        if cancellation_response.json()["status"]["success"] == True:
            response = {"status":True,"data":cancellation_response.json()}
        else:
            response = {"status":False,"data":cancellation_response.json()}
        log["response"] = response
        api_logs_to_mongo(log)
        return response  
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def check_cancellation_status(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    url = kwargs.get("baseurl") + "oms/v1/air/amendment/amendment-details"
    payload = {"amendmentId":kwargs.get("amendmentId")}
    session_id = kwargs.get("session_id","")
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
        "payload":payload,"api":"check_cancellation_status","url":url,"session_id":session_id}
    try:
        cancellation_status_response = requests.post(url, headers = headers, data = json.dumps(payload))
        if cancellation_status_response.json()["status"]["success"] == True:
            response =  {"status":True,"data":cancellation_status_response.json()}
        else:
            response = {"status":False,"data":cancellation_status_response.json()}
        log["response"] = response
        api_logs_to_mongo(log)
        return response  
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}

def get_current_ticket_status(**kwargs):
    headers = {
        "apikey": kwargs.get("api_key"),
        "content-Type": "application/json",
    }
    url = kwargs.get("baseurl") +"oms/v1/booking-details"
    payload = {"bookingId":kwargs.get("booking_id"),"requirePaxPricing" :True}
    session_id = kwargs.get("session_id")
    log = {"request_type":"POST","vendor":"TripJack","headers":headers,
            "payload":payload,"api":"get_current_ticket_status","url":url,"session_id":session_id}
    try:
        book_response = requests.post(url, headers = headers, data = json.dumps(payload),timeout=30)
        if book_response.json()["status"]["success"] == True:
            response =  {"status":True,"data":book_response.json()}
        else:
            response = {"status":False,"data":book_response.json()}
        log["response"] = response
        api_logs_to_mongo(log)
        return response
    except (requests.exceptions.Timeout, SystemExit):
        log["response"] = {"status":False,"data":{},"error":"Response timeout/SystemExit"}
        api_logs_to_mongo(log)
        return {"status":False,"data":{},"status_code":504}
    except:
        error = tb.format_exc()
        log["response"] = {"status":False,"data":{},"error":error}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def api_logs_to_mongo(log):
    mongo_handler.Mongo().log_vendor_api(log)