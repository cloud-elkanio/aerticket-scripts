from datetime import datetime
import requests
import json
import re

def authentication(base_url,credentials):
    url = f"{base_url}/SharedData.svc/rest/Authenticate"
    payload = json.dumps({
        "ClientId": credentials['client_id'],
        "UserName": credentials['username'],
        "Password": credentials['password'],
        "EndUserIp": credentials['end_user_ip']
        })
    headers = {
      'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    # import pdb;pdb.set_trace()
    res_json = response.json()
    
    token = res_json['TokenId']
    # country_list(token)
    
    return token

def country_list(token,base_url):
    url = f"{base_url}/SharedServices/SharedData.svc/rest/CountryList"
    payload = json.dumps({
      "TokenId": token,
      "ClientId": "ApiIntegrationNew",
      "EndUserIp": "192.168.10.130"
    })
    headers = {
      'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    res_json = response.json()
    # print("country_list_res_json---->",res_json)
    # Get Full Country CODE
    string = res_json['CountryList']
    codes = re.findall(r'<Code>(.*?)<\/Code>', string)
    code= 'IN'
    # destination(code, token)
    return codes 


def get_destinations(code ,token,base_url):
    #url = f"{base_url}/StaticData.svc/rest/GetDestinationSearchStaticData"
    url = "http://api.tbotechnology.in/TBOHolidays_HotelAPI/CityList"
    payload = json.dumps({
      "EndUserIp": "192.168.10.26",
      "TokenId": token,
      "CountryCode": code,
      "SearchType": "1"
    })
    headers = {
      'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    data = response.json()
    # import pdb;pdb.set_trace()
    destination_id = data['Destinations'][0]['DestinationId']
    return data['Destinations']

    # perform_search(destination_id, code, token)


def perform_search(destination_id, code, token,check_in_date,
check_out_date,no_of_rooms,room_pax,max_rating = 5,
min_rating = 0,end_user_ip = "123.1.1.1",
search_base_url="https://HotelBE.tektravels.com"):

    url = f"{search_base_url}/hotelservice.svc/rest/GetHotelResult/"
    check_in_date = datetime.strptime(check_in_date, "%d/%m/%Y")
    check_out_date = datetime.strptime(check_in_date, "%d/%m/%Y")
    days_difference = (check_out_date - check_in_date).days
    room_pax = [{
           "NoOfAdults": pax["adults_count"],
           "NoOfChild":pax["child_count"],
           "ChildAge": None
        } for pax in room_pax]
    payload = json.dumps({
      "CheckInDate":check_in_date, #"25/01/2025",
      "NoOfNights":str(days_difference), #"1",
      "CountryCode": code,
      "CityId": destination_id,
      "ResultCount": None,
      "PreferredCurrency": "INR",
      "GuestNationality": "IN",
      "NoOfRooms": str(no_of_rooms),#"1",
      "RoomGuests": room_pax,
      # "RoomGuests": [
      #   {
      #     "NoOfAdults": 1,
      #     "NoOfChild": 0,
      #     "ChildAge": None 
      #   }
      # ],
      "MaxRating": max_rating,#5,
      "MinRating": min_rating,#0,
      "ReviewScore": None,
      "IsNearBySearchAllowed": False,
      "EndUserIp": end_user_ip,
      "TokenId": token
    })
    headers = {
      'Content-Type': 'application/json'
    }
    
    response = requests.request("POST", url, headers=headers, data=payload)
    
    search_data = response.json()
    return search_data

    # hotelcode = search_data['HotelSearchResult']['HotelResults'][0]['HotelCode']
    # hotel_index = search_data['HotelSearchResult']['HotelResults'][0]['ResultIndex']
    # hotel_name = search_data['HotelSearchResult']['HotelResults'][0]['HotelName']

    # trace_id = search_data['HotelSearchResult']['TraceId']
    # # print("hotelcode",hotelcode,"trace_id",trace_id , "token",token, "hotel_index",hotel_index, "hotel_name",hotel_name)
    # info(hotelcode,trace_id , token,hotel_index,hotel_name)

    
def info(hotelcode,trace_id, token,hotel_index,hotel_name,
         search_base_url = "https://HotelBE.tektravels.com",
         end_user_ip = "123.1.1.1"):

    # print("info",hotelcode,trace_id, token)

    url = f"{search_base_url}/hotelservice.svc/rest//GetHotelInfo"
    
    payload = json.dumps({
      "ResultIndex": hotel_index,
      "HotelCode": hotelcode,
      "EndUserIp": end_user_ip,
      "TokenId": token,
      "TraceId": trace_id
    })
    headers = {
      'Content-Type': 'application/json'
    }
    
    response = requests.request("POST", url, headers=headers, data=payload)
    
    rooms(hotelcode,trace_id, token,hotel_index,hotel_name)

def rooms(hotelcode,trace_id, token,hotel_index,
          hotel_name,search_base_url = "https://HotelBE.tektravels.com",
          end_user_ip = "123.1.1.1"):
    print("info completed")

    # print("rooms",hotelcode,trace_id, token)
    url = f"{search_base_url}/hotelservice.svc/rest/GetHotelRoom"
    room_index_value = 1
    payload = json.dumps({
      "ResultIndex": hotel_index,
      "HotelCode": hotelcode,
      "EndUserIp": end_user_ip,
      "TokenId": token,
      "TraceId": trace_id
    })
    headers = {
      'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    rooms_data = response.json()
    # print("rooms_data",rooms_data)
    print("rooms_res_json---->",rooms_data)
    

    room_res_for_book={
    'trace_id' : trace_id,
    'token' :token,
    'hotelcode':hotelcode,
    'hotel_index':hotel_index,
    'hotel_name':hotel_name,
    
    'roomindex': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['RoomIndex'],
    'roomtypecode': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['RoomTypeCode'],
    'roomtypename': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['RoomTypeName'],
    'rateplancode': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['RatePlanCode'],
    'currencycode': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['CurrencyCode'],
    'roomprice': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['RoomPrice'],
    'tax': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['Tax'],
    'extraguestcharge': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['ExtraGuestCharge'],
    'childcharge': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['ChildCharge'],
    'othercharges': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['OtherCharges'],
    'discount': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['Discount'],
    'publishedprice': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['PublishedPrice'],
    'publishedpriceroundedoff': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['PublishedPriceRoundedOff'],
    'offeredprice': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['OfferedPrice'],
    'offeredpriceroundedoff': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['OfferedPriceRoundedOff'],
    'agentcommission': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['AgentCommission'],
    'agentmarkup': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['AgentMarkUp'],
    'servicetax': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['ServiceTax'],
    'tds': rooms_data['GetHotelRoomResult']['HotelRoomsDetails'][room_index_value]['Price']['TDS']
    }
    blockroom(**room_res_for_book)


def blockroom(**kwargs):
    print("rooms completed")
    url = "https://HotelBE.tektravels.com/hotelservice.svc/rest/blockRoom"
    payload = json.dumps({
      "ResultIndex": kwargs.get('hotel_index'),
      "HotelCode": kwargs.get('hotelcode'),
      "HotelName": kwargs.get('hotel_name'),
      "GuestNationality": "IN",
      "NoOfRooms": "1",
      "IsVoucherBooking": "false",
      "HotelRoomsDetails": [
        {
          "RoomIndex": kwargs.get('roomindex'),
          "RoomTypeCode": kwargs.get('roomtypecode') ,
          "RoomTypeName": kwargs.get('roomtypename') ,
          "RatePlanCode": kwargs.get('rateplancode')  ,
          "BedTypeCode": None,
          "SmokingPreference": 0,
          "Supplements": None,
          "Price": {
            "CurrencyCode": kwargs.get('currencycode') ,
            "RoomPrice": kwargs.get('roomprice') ,
            "Tax": kwargs.get('tax') ,
            "ExtraGuestCharge": kwargs.get('extraguestcharge') ,
            "ChildCharge": kwargs.get('childcharge') ,
            "OtherCharges": kwargs.get('othercharges') ,
            "Discount": kwargs.get('discount') ,
            "PublishedPrice": kwargs.get('publishedprice') ,
            "PublishedPriceRoundedOff": kwargs.get('publishedpriceroundedoff') ,
            "OfferedPrice": kwargs.get('offeredprice') ,
            "OfferedPriceRoundedOff": kwargs.get('offeredpriceroundedoff') ,
            "AgentCommission": kwargs.get('agentcommission') ,
            "AgentMarkUp": kwargs.get('agentmarkup'),
            "TDS": kwargs.get('tds'),
            "ServiceTax": kwargs.get('servicetax')
          }}],
      "EndUserIp": "123.1.1.1",
      "TokenId":kwargs.get('token'),
      "TraceId": kwargs.get('trace_id')
    })
    headers = {
      'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    print("blockroommmm",response.text)
    book(**kwargs)


def book(**kwargs):
    print("bookkkk======",kwargs)
    print("rooms completed", "hotel_name",kwargs.get('hotel_name'))
    
    url = "https://HotelBE.tektravels.com/hotelservice.svc/rest/book"
    
    payload = json.dumps({
      "ResultIndex": kwargs.get('hotel_index'),
      "HotelCode": kwargs.get('hotelcode'),
      "HotelName": kwargs.get('hotel_name'),
      "GuestNationality": "IN",
      "NoOfRooms": "1",
      "IsVoucherBooking": "false",
      "HotelRoomsDetails": [
        {
          "RoomIndex": kwargs.get('roomindex'),
          "RoomTypeCode": kwargs.get('roomtypecode') ,
          "RoomTypeName": kwargs.get('roomtypename') ,
          "RatePlanCode": kwargs.get('rateplancode')  ,
          "BedTypeCode": None,
          "SmokingPreference": 0,
          "Supplements": None,
          "Price": {
            "CurrencyCode": kwargs.get('currencycode') ,
            "RoomPrice": kwargs.get('roomprice') ,
            "Tax": kwargs.get('tax') ,
            "ExtraGuestCharge": kwargs.get('extraguestcharge') ,
            "ChildCharge": kwargs.get('childcharge') ,
            "OtherCharges": kwargs.get('othercharges') ,
            "Discount": kwargs.get('discount') ,
            "PublishedPrice": kwargs.get('publishedprice') ,
            "PublishedPriceRoundedOff": kwargs.get('publishedpriceroundedoff') ,
            "OfferedPrice": kwargs.get('offeredprice') ,
            "OfferedPriceRoundedOff": kwargs.get('offeredpriceroundedoff') ,
            "AgentCommission": kwargs.get('agentcommission') ,
            "AgentMarkUp": kwargs.get('agentmarkup'),
            "TDS": kwargs.get('tds'),
            "ServiceTax": kwargs.get('servicetax')
          },
          "HotelPassenger": [
            {
              "Title": "mr",
              "FirstName": "Jeemol",
              "LastName": "CR",
              "Email": "jeemol.cr@elkanio.com",
              "PaxType": 1,
              "LeadPassenger": True,
              "Age": 25
            }
          ]
        }
      ],
      "EndUserIp": "123.1.1.1",
      "TokenId":kwargs.get('token'),
      "TraceId": kwargs.get('trace_id')
    })    
    headers = {
      'Content-Type': 'application/json'
    }
    
    response = requests.request("POST", url, headers=headers, data=payload)
    
    print("bookking response*********************",response.text)

    print("book completed")





# credentials = {
#     "ClientId": "ApiIntegrationNew",
#     "UserName": "b2btravel",
#     "Password": "travel@1234567",
#     "EndUserIp": "192.168.11.120"
#     }

# authentication(credentials)



