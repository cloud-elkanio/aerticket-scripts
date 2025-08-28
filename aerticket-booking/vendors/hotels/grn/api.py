
import json

import requests


def get_headers(api_key):
    headers = {
        "api-key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    return headers

def hotel_availability(
    hotel_codes,
    check_in,
    check_out,
    selected_rooms,
    api_key,
    purpose_of_travel = 2,
    currency = "INR",
    client_nationality =  "IN",
    base_url = "https://api-sandbox.grnconnect.com/api/v3/hotels"
    
    
):
    url = f"{base_url}/availability"
    print("url = ",url)
    headers = get_headers(api_key)
    payload = json.dumps(
        {   "rooms": selected_rooms,
            "hotel_codes": hotel_codes,
            "currency": currency,
            "client_nationality": client_nationality,
            "checkout": check_out,
            "checkin": check_in,
            "purpose_of_travel": purpose_of_travel,
            "rates":"comprehensive"
        }
    )

    response = requests.request("POST", url, headers=headers, data=payload)
    # with open("grn-data.json", "w") as json_file:
    #     json.dump(response.json(), json_file, indent=4) 
    print("headers = ",headers)
    print("url = ",url)
    print("payload = ",payload)
    print("response = ",response.text)
    return json.loads(response.text)



def bundled_rates_booking(
    booking_items,
    check_in,
    check_out,
    group_code,
    city_code,
    search_id,
    hotel_code,
    headers,
    base_url,
    holder_details,
    payment_type="AT_WEB"
):
    
    """
    params: holder_details ={
        "client_nationality": client_nationality,
        "email": "info@bookotrip.com",
        "name": "James",
        "phone_number": "6614565589",
        "surname": "Patrick",
        "title": "Mr.",
        "pan_number": "AAGCB9852N",
        "pan_company_name": "BOOKOTRIP INDIA PRIVATE LIMITED",
            }

    booking_items = [{'room_reference':'xxxxx',
    "paxes":pax_list}]
    """

    url = f"{base_url}/bookings"

    payload_dict = {
            "agent_reference": "",
            "booking_comments": "Test booking",
            "booking_items": [
                {
                    "rate_key": booking_item['rate_key'],
                    "room_code": booking_item['room_code'],
                    "rooms": [
                        {
                            "paxes": [{
                                "name": j['first_name'], "surname":j['last_name'], 
                                "title":j['title'], "type":"CH" if j['type'] in ["CHILD","CH"] else "AD",
                                **({"age": j['age']} if j['type'] in ["CHILD", "CH"] else {})
                                }
                                  for j in i['paxes']],
                            "room_reference": i['room_reference'],
                        }
                   for i in booking_item['rooms']]
                }
            for booking_item in booking_items],
            "checkin": check_in,
            "checkout": check_out,
            "city_code": city_code,
            "group_code": group_code,
            "holder": holder_details,
            "hotel_code": hotel_code,
            "payment_type": payment_type,
            "search_id": search_id,
        }

    
    
    
    payload = json.dumps(
        payload_dict
    )
    response = requests.post(url, headers=headers, data=payload)
    # import pdb;pdb.set_trace()
    print(response.text)
    if response.status_code == 200:
        try:
            result = response.json()
            if "errors" in result.keys():
                return result,payload_dict,url,"failure"
            return result,payload_dict,url,"success"
        except Exception as e:
            import traceback
            return traceback.format_exc(),payload_dict,url,500
    else:
        print(f"Error:status code: {response.status_code},{response.text}")
        return response.text,payload_dict,url,500



def non_bundled_rates_booking(
    booking_items,
    check_in,
    check_out,
    group_code,
    city_code,
    search_id,
    hotel_code,
    headers,
    base_url,
    holder_details,
    payment_type="AT_WEB"
):
    """
    params: holder_details ={
        "client_nationality": client_nationality,
        "email": "info@bookotrip.com",
        "name": "James",
        "phone_number": "6614565589",
        "surname": "Patrick",
        "title": "Mr.",
        "pan_number": "AAGCB9852N",
        "pan_company_name": "BOOKOTRIP INDIA PRIVATE LIMITED",
            }

    booking_items = [{'room_reference':'xxxxx',
    "paxes":pax_list}]
    """


    url = f"{base_url}/bookings"
        
    payload = json.dumps({
    "search_id": search_id,
    "hotel_code": hotel_code,
    "city_code": city_code,
    "group_code": group_code,
    "checkout": check_out,
    "checkin": check_in,
    "booking_comments": "Test booking",
    "payment_type": payment_type,
    "agent_reference": "",
    "booking_items": [
        # {
        # "room_code": room_code,
        # "rate_key": rate_key,
        # "room_reference": room_reference,
        # "rooms": [
        #     {
        #     "paxes": selected_pax
        #     }
        # ]
        # },
        {
        "room_code": i['room_code'],
        "rate_key": i['rate_key'],
        "room_reference": i['room_reference'],
        "rooms": [
            {
            # "no_of_infants": 1,
            "paxes": [{"name": j['first_name'], "surname":j['last_name'], "title":j['title'], "type":"CH" if j['type'] == "CHILD" else "AD"} for j in i['paxes']]
            }
        ]
        }
    for i in booking_items],
    "holder": holder_details
    })
    # import pdb;pdb.set_trace()
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        try:
            return response.json()
        except ValueError:
            print("Error: Response is not valid JSON.")
    else:
        print(f"Error:status code: {response.status_code}")
        return response.text
    

def booking_cancellation(
    booking_reference,
    api_key,
    base_url="https://api-sandbox.grnconnect.com",
    comments="Cancelled by client",
    reason=13,
    
):
    """
    Sends a DELETE request to cancel a hotel booking on GRN Connect.
    (Note: GRN Connect typically uses POST for cancellations.)

    Args:
        booking_reference (str): Booking reference ID.
        api_key (str): API token for authentication.
        comments (str): Comments for cancellation.
        reason (int): Cancellation reason code.
        currency (str): Currency code.
        client_nationality (str): Nationality code.
        base_url (str): GRN Connect base API URL.

    Returns:
        dict: Response from the API or error message.
    """
    url = f"{base_url}/api/v3/hotels/bookings/{booking_reference}"
    headers = {
        "Content-Type": "application/json",
        "token": api_key
    }
    body = {
        "comments": comments,
        "reason": reason
    }

    try:
        response = requests.delete(url, json=body, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def test_bundle():
    kwargs = {'booking_items': [{'room_code': '4dhflnri4qwcpubuy7xq', 'rate_key': '4phfnmjx4ius7fstusmwehgw4ljohjxe6gzo3htz3bgrd6pkl2yar67pk5swleeqs5ffz6xtv54bqebxxcygq5m72pobjl6hsgusxq6w4gofftcrzj5d6oatei3oepck7g6sv3tfdazrk74j7g2murp44ky3ewesa34uppc47bey5wxwaewsbai7s6cgd7irblpr2wimajisapw5xkahnqrhvxhebzowb3nwxb4po2ini6okh7zxevzkmcka', 'room_reference': 'qk4srkscrircpwy', 'paxes': [{'title': 'Mr.', 'first_name': 'Jijo', 'last_name': 'Thomas', 'email': None, 'mobile_no': None, 'type': None}]}], 'check_in': '2025-10-12', 'check_out': '2025-10-20', 'group_code': 'xgirbylkwb6xtgj647fdssmex6nkls5j6c6ojv3y', 'city_code': '120919', 'search_id': '7s263wrkl3nkmxqsxusczoiuqq', 'hotel_code': '1380443', 'headers': {'api-key': 'bab29dcd81b9be82284efc966fdbdbaf', 'Accept': 'application/json', 'Content-Type': 'application/json'}, 'base_url': 'https://api-sandbox.grnconnect.com/api/v3/hotels', 'holder_details': {'title': 'Mr.', 'name': 'John', 'surname': 'Doe', 'email': 'john.doe@example.com', 'phone_number': '9876543210', 'client_nationality': 'In', 'pan_number': 'ABCDE1234F', 'pan_company_name': 'elkanio', 'fema_declaration': True}, 'payment_type': 'AT_WEB'}
    bundled_rates_booking(**kwargs)
# availability = hotel_availability(
#     [
#     "1386724",
#     "1386377",
#     "1380443",
#     "1386364"

# ],
#     "2024-12-15",
#     "2024-12-16",
#     [
#        { "adults": "2"},
#        { "adults": "2"},
#        {  "adults": "2", "children_ages": ["3" "11"] },
#        {  "adults": "1", "children_ages": ["3" "11"] }
# ],
#     purpose_of_travel = 2,
#     currency = "INR",
#     client_nationality =  "IN",
    
# )
