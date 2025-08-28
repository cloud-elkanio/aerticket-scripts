from vendors.flights import mongo_handler
import requests,json
import os
from dotenv import load_dotenv
load_dotenv() 

def flight_search(**kwargs):
    if kwargs.get("book_filters",{}).get("is_proceed") == False:
        return None
    else:
        Filtered_Airline = [{"Airline_Code":code} for code in kwargs.get("book_filters",{}).get("filtered_airlines",[])]
        session_id= kwargs.get("session_id","")
        headers = {'Content-Type': 'application/json'}
        payload = {}
        tripinfo = []
        payload["Auth_Header"] ={
                "UserId": kwargs.get("credentials",{}).get("user_id",""),
                "Password": kwargs.get("credentials",{}).get("password",""),
                "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
                "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
                "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
            }
        payload["Travel_Type"] = kwargs["search_data"].get("travel_type")
        payload["Booking_Type"] = kwargs["search_data"].get("booking_type")
        for trip_index,trip_search in enumerate(kwargs["segment_details"]):
            tripinfo.append({
                "Origin":trip_search["source_city"],
                "Destination":trip_search["destination_city"],
                "TravelDate":trip_search["travel_date"],
                "Trip_Id":trip_index
            })
        payload["TripInfo"] = tripinfo
        payload["Adult_Count"] = int(kwargs["search_data"]["passenger_details"].get("adult_Count",0))
        payload["Child_Count"] = int(kwargs["search_data"]["passenger_details"].get("child_Count",0))
        payload["Infant_Count"] = int(kwargs["search_data"]["passenger_details"].get("infant_Count",0))
        payload["Class_Of_Travel"] = int(kwargs["search_data"].get("cabin_class",0))
        payload["InventoryType"] = 0
        payload["SrCitizen_Search"] = False
        payload["StudentFare_Search"]  = False
        payload["DefenceFare_Search"] = False
        payload["Filtered_Airline"] =  [{"Airline_Code":""}] if not Filtered_Airline else Filtered_Airline
        url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_Search"
        log = {"request_type":"POST","vendor":"STT-ETrav","headers":headers,
            "payload":json.dumps(payload),"api":"flight_search","url":url,"session_id":session_id}
        try:
            response = requests.post(url = url,
                                    headers = headers, data = json.dumps(payload),timeout=30)
            log["response"] = {"status":True,"data":response.json()}
            api_logs_to_mongo(log)
            return response.json()
        except Exception as e:
            log["response"] = {"status":False,"data":str(e)}
            api_logs_to_mongo(log)
            return None       
    
def fare_rule(**kwargs):
    session_id = kwargs.get("session_id","")
    headers = {'Content-Type': 'application/json'}
    payload = {}
    payload["Auth_Header"] ={
            "UserId": kwargs.get("credentials",{}).get("user_id",""),
            "Password": kwargs.get("credentials",{}).get("password",""),
            "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
            "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
            "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
        }
    payload["Search_Key"] = kwargs["search_key"]
    payload["Flight_Key"] = kwargs["flight_key"]
    payload["Fare_Id"] = kwargs["fare_id"]

    url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_FareRule"

    log = {"request_type":"POST","vendor":"STT-ETrav","headers":headers,
        "payload":payload,"api":"fare_rule","url":url,"session_id":session_id}
    try:
        response = requests.post(url, 
                                headers = headers, json = payload)
        log["response"] = {"status":True,"data":response.json()}
        api_logs_to_mongo(log)
        return json.loads(response.text)
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return None

def fare_quote(**kwargs):
    session_id = kwargs.get("session_id","")
    headers = {"content-Type": "application/json"}
    payload = {}
    payload["Auth_Header"] ={
            "UserId": kwargs.get("credentials",{}).get("user_id",""),
            "Password": kwargs.get("credentials",{}).get("password",""),
            "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
            "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
            "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
            }
    payload["Search_Key"] = kwargs["search_key"]
    payload["Customer_Mobile"] = os.getenv('BTA_PHONE',"")
    payload["GST_Input"] = False
    payload["AirRepriceRequests"] = [{"Flight_Key":kwargs["flight_key"],"Fare_Id":kwargs["stt_fare_id"]}]
    url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_Reprice"
    log = {"request_type":"POST","vendor":"STT-ETrav","headers":headers,
            "payload":payload,"api":"fare_quote","url":url,"session_id":session_id}
    try:
        response = requests.post(url, 
                                headers=headers, data = json.dumps(payload))
        log["response"] = {"status":True,"data":response.json()}
        api_logs_to_mongo(log)
        return json.loads(response.text)
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return None

def ssr(**kwargs):
    session_id = kwargs.get("session_id","")
    headers = {"content-Type": "application/json",}
    payload = {}
    payload["Auth_Header"] = {
            "UserId": kwargs.get("credentials",{}).get("user_id",""),
            "Password": kwargs.get("credentials",{}).get("password",""),
            "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
            "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
            "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
            }
    payload["Search_Key"] = kwargs["search_key"]
    payload["AirSSRRequestDetails"] = [{"Flight_Key":kwargs["flight_key"]}]
    url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_GetSSR"
    log = {"request_type":"POST","vendor":"STT-ETrav","headers":headers,
            "payload":payload,"api":"ssr","url":url,"session_id":session_id}
    try:
        response = requests.post(url,
                                headers = headers, data = json.dumps(payload))
        log["response"] = {"status":True,"data":response.json()}
        api_logs_to_mongo(log)
        return json.loads(response.text)
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return None

def seat_ssr(**kwargs):
    session_id = kwargs.get("session_id","")
    headers = {"content-Type": "application/json",}
    payload = {}
    payload["Auth_Header"] = {
            "UserId": kwargs.get("credentials",{}).get("user_id",""),
            "Password": kwargs.get("credentials",{}).get("password",""),
            "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
            "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
            "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
            }
    payload["Search_Key"] = kwargs["search_key"]
    payload["PAX_Details"] = []
    payload["Flight_Keys"] = [kwargs["flight_key"]]
    url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_GetSeatMap"
    log = {"request_type":"POST","vendor":"STT-ETrav","headers":headers,
        "payload":payload,"api":"ssr","url":url,"session_id":session_id}
    try:
        response = requests.post(url,
                                headers = headers, data = json.dumps(payload))
        log["response"] = {"status":True,"data":response.json()}
        api_logs_to_mongo(log)
        return json.loads(response.text)
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return None
   
def temp_ticket_book(**kwargs):
    session_id = kwargs.get("session_id","")
    headers = {"content-Type": "application/json"}
    payload = kwargs["payload"]
    payload["Auth_Header"] = {
            "UserId": kwargs.get("credentials",{}).get("user_id",""),
            "Password": kwargs.get("credentials",{}).get("password",""),
            "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
            "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
            "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
            }
    url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_TempBooking"
    log = {"request_type":"POST","vendor":'STT-ETrav',"headers":headers,
                "payload":payload,"api":"ticket","url":url,"session_id":session_id,"sub_type":"temp_booking"}
    try:
        response = requests.post(url,
                                headers = headers, data = json.dumps(payload))
        try:
            if response.json()["Booking_RefNo"]:
                log["response"] = {"status":True,"data":response.json()}
                api_logs_to_mongo(log)
                return {"status":True,"data":response.json()}
            else:
                log["response"] = {"status":False,"data":response.json()}
                api_logs_to_mongo(log)
                return {"status":False,"data":response.json()}
        except Exception as e:
            log["response"] = {"status":False,"data":str(e)}
            api_logs_to_mongo(log)
            return {"status":False,"data":{}}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def book_ticket_flow(**kwargs):
    session_id = kwargs.get("session_id","")
    headers = {"content-Type": "application/json"}
    payload = kwargs["payload"]
    payload["Auth_Header"] = {
            "UserId": kwargs.get("credentials",{}).get("user_id",""),
            "Password": kwargs.get("credentials",{}).get("password",""),
            "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
            "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
            "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
            }
    url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_Ticketing"
    log = {"request_type":"POST","vendor":'STT-ETrav',"headers":headers,
                "payload":payload,"api":"ticket","url":url,"session_id":session_id,"sub_type":"book_ticket"}
    try:
        if int(kwargs["ticketing_type"]) !=0:
            make_payment_response = make_payment(payload = payload,credentials = kwargs["credentials"],session_id = session_id)
        else:
            make_payment_response = True
        if make_payment_response:
            response = requests.post(url,
                                    headers = headers, data = json.dumps(payload))
            try:
                if response.json()["Response_Header"]["Error_Desc"] == "SUCCESS":
                    log["response"] = {"status":True,"data":response.json()}
                    api_logs_to_mongo(log)
                    return {"status":True,"data":response.json()}
                else:
                    log["response"] = {"status":False,"data":response.json()}
                    api_logs_to_mongo(log)
                    return {"status":False,"data":response.json()}
            except Exception as e:
                log["response"] = {"status":False,"data":str(e)}
                api_logs_to_mongo(log)
                return {"status":False,"data":{}}
        else:
            return {"status":False,"data":{}}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def make_payment(**kwargs):
    session_id = kwargs.get("session_id","")
    headers = {"content-Type": "application/json"}
    get_balance_url = kwargs["credentials"]["payment_url"]+"TradeAPIService.svc/JSONService/GetBalance"
    gat_balance_payload = {}
    gat_balance_payload["Auth_Header"] = kwargs["payload"]["Auth_Header"]
    gat_balance_payload["RefNo"] = kwargs["payload"]["Booking_RefNo"]
    log = {"request_type":"POST","vendor":'STT-ETrav',"headers":headers,
            "payload":gat_balance_payload,"api":"ticket","url":get_balance_url,"session_id":session_id}
    try:
        response = requests.post(get_balance_url,
                                    headers = headers, data = json.dumps(gat_balance_payload))
        if response.json()["Response_Header"]["Error_Desc"] == "SUCCESS":
            log["response"] = {"status":True,"data":response.json()}
            api_logs_to_mongo(log)
            make_payment_payload = {}
            make_payment_url = kwargs["credentials"]["payment_url"]+"TradeAPIService.svc/JSONService/AddPayment"
            make_payment_payload["Auth_Header"] = kwargs["payload"]["Auth_Header"]
            make_payment_payload["RefNo"] = kwargs["payload"]["Booking_RefNo"]
            make_payment_payload["TransactionType"] = 0
            make_payment_payload["ProductId"] = 1
            log = {"request_type":"POST","vendor":'STT-ETrav',"headers":headers,
                "payload":make_payment_payload,"api":"ticket","url":make_payment_url,"session_id":session_id,
                "sub_type":"add_payment"}
            response = requests.post(make_payment_url,
                                    headers = headers, data = json.dumps(make_payment_payload))
            if response.json()["Response_Header"]["Error_Desc"] == "SUCCESS":
                log["response"] = {"status":True,"data":response.json()}
                api_logs_to_mongo(log)
                return True
            else:
                log["response"] = {"status":False,"data":response.json()}
                api_logs_to_mongo(log)
                return False
        else:
            log["response"] = {"status":False,"data":response.json()}
            api_logs_to_mongo(log)
            return False
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return False
    
def air_reprint(**kwargs):
    session_id = kwargs.get("session_id","")
    headers = {"content-Type": "application/json"}
    payload = kwargs["payload"]
    payload["Auth_Header"] = {
            "UserId": kwargs.get("credentials",{}).get("user_id",""),
            "Password": kwargs.get("credentials",{}).get("password",""),
            "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
            "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
            "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
            }
    url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_Reprint"
    log = {"request_type":"POST","vendor":'STT-ETrav',"headers":headers,
            "payload":payload,"api":"ticket","sub_type":"air_reprint","url":url,"session_id":session_id}
    try:
        response = requests.post(url,
                                headers = headers, data = json.dumps(payload))
        try:
            if response.json()["Response_Header"]["Error_Desc"] == "SUCCESS":
                log["response"] = {"status":True,"data":response.json()}
                api_logs_to_mongo(log)
                return {"status":True,"data":response.json()}
            else:
                log["response"] = {"status":False,"data":response.json()}
                api_logs_to_mongo(log)
                return {"status":False,"data":response.json()}
        except Exception as e:
            log["response"] = {"status":False,"data":str(e)}
            api_logs_to_mongo(log)
            return {"status":False,"data":{}}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def get_ssr_data(**kwargs):
    session_id = kwargs.get("session_id","")
    headers = {"content-Type": "application/json"}
    payload = kwargs["payload"]
    payload["Auth_Header"] = {
            "UserId": kwargs.get("credentials",{}).get("user_id",""),
            "Password": kwargs.get("credentials",{}).get("password",""),
            "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
            "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
            "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
            }
    url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_GetSSR"
    log = {"request_type":"POST","vendor":"STT-ETrav","headers":headers,
            "payload":payload,"api":"ssr","url":url,"session_id":session_id}
    try:
        response = requests.post(url,
                                headers = headers, data = json.dumps(payload))
        try:
            if response.json()["Response_Header"]["Error_Desc"] == "SUCCESS":
                log["response"] = {"status":True,"data":response.json()}
                api_logs_to_mongo(log)
                return {"status":True,"data" : response.json()}
            else:
                log["response"] = {"status":False,"data":response.json()}
                api_logs_to_mongo(log)
                return {"status":False,"data" : response.json()}
        except Exception as e:
            log["response"] = {"status":False,"data":str(e)}
            api_logs_to_mongo(log)
            return {"status":False,"data":{}}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def get_ssr_seat_data(**kwargs):
    session_id = kwargs.get("session_id","")
    headers = {"content-Type": "application/json"}
    payload = kwargs["payload"]
    payload["Auth_Header"] = {
            "UserId": kwargs.get("credentials",{}).get("user_id",""),
            "Password": kwargs.get("credentials",{}).get("password",""),
            "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
            "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
            "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
            }
    url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_GetSeatMap"
    log = {"request_type":"POST","vendor":"STT-ETrav","headers":headers,
            "payload":payload,"api":"ssr","url":url,"session_id":session_id}
    try:
        response = requests.post(url,
                                headers = headers, data = json.dumps(payload))
        try:
            if response.json()["Response_Header"]["Error_Desc"] == "SUCCESS":
                log["response"] = {"status":True,"data":response.json()}
                api_logs_to_mongo(log)
                return {"status":True,"data":response.json()}
            else:
                log["response"] = {"status":False,"data":response.json()}
                api_logs_to_mongo(log)
                return {"status":False,"data":response.json()}
        except Exception as e:
            log["response"] = {"status":False,"data":str(e)}
            api_logs_to_mongo(log)
            return {"status":False,"data":{}}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}
    
def release_hold(**kwargs):
    headers = {"content-Type": "application/json"}
    payload = kwargs["payload"]
    payload["Auth_Header"] = {
            "UserId": kwargs.get("credentials",{}).get("user_id",""),
            "Password": kwargs.get("credentials",{}).get("password",""),
            "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
            "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
            "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
            }
    url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_ReleasePNR"
    try:
        response = requests.post(url,headers = headers, data = json.dumps(payload))
        try:
            if response.json()["Response_Header"]["Error_Desc"] == "SUCCESS":
                return {"status":True,"data":response.json()}
            else:
                return {"status":False,"data":response.json()}
        except Exception as e:
            return {"status":False,"data":{}}
    except Exception as e:
        return {"status":False,"data":{}}
    
def cancel_ticket(**kwargs):
    headers = {"content-Type": "application/json"}
    payload = kwargs["payload"]
    payload["Auth_Header"] = {
            "UserId": kwargs.get("credentials",{}).get("user_id",""),
            "Password": kwargs.get("credentials",{}).get("password",""),
            "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
            "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
            "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
            }
    url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_TicketCancellation"
    try:
        response = requests.post(url,headers = headers, data = json.dumps(payload))
        try:
            if response.json()["Response_Header"]["Error_Desc"] == "SUCCESS":
                return {"status":True,"data":response.json()}
            else:
                return {"status":False,"data":response.json()}
        except Exception as e:
            return {"status":False,"data":{}}
    except Exception as e:
        return {"status":False,"data":{}}
    
def get_current_ticket_status(**kwargs):
    session_id = kwargs.get("session_id","")
    headers = {"content-Type": "application/json"}
    payload = kwargs["payload"]
    payload["Auth_Header"] = {
            "UserId": kwargs.get("credentials",{}).get("user_id",""),
            "Password": kwargs.get("credentials",{}).get("password",""),
            "IP_Address": kwargs.get("credentials",{}).get("ip_address",""),
            "Request_Id": kwargs.get("credentials",{}).get("request_id",""),
            "IMEI_Number":kwargs.get("credentials",{}).get("imei_number","")
            }
    url = kwargs["credentials"]["base_url"]+"AirAPIService.svc/JSONService/Air_Reprint"
    log = {"request_type":"POST","vendor":'STT-ETrav',"headers":headers,
            "payload":payload,"api":"current_ticket_status","url":url,"session_id":session_id}
    try:
        response = requests.post(url,
                                headers = headers, data = json.dumps(payload))
        try:
            if response.json()["Response_Header"]["Error_Desc"] == "SUCCESS":
                log["response"] = {"status":True,"data":response.json()}
                api_logs_to_mongo(log)
                return {"status":True,"data":response.json()}
            else:
                log["response"] = {"status":False,"data":response.json()}
                api_logs_to_mongo(log)
                return {"status":False,"data":response.json()}
        except Exception as e:
            log["response"] = {"status":False,"data":str(e)}
            api_logs_to_mongo(log)
            return {"status":False,"data":{}}
    except Exception as e:
        log["response"] = {"status":False,"data":str(e)}
        api_logs_to_mongo(log)
        return {"status":False,"data":{}}

def api_logs_to_mongo(log):
    mongo_handler.Mongo().log_vendor_api(log)