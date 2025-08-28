
import requests
from requests.auth import HTTPBasicAuth

def flight_search(base_url,credentials,trip_type,origin,destination,cabin_class,depart_date,arrival_date,pax):

    company_code=  credentials.get("company_code")
    website_name=  credentials.get("website_name")
    username=  credentials.get("username")
    password=  credentials.get("password")
    header = {"Content-Type": "application/json"}
    pax = { "adults": 1, "children": 1, "infants": 0 }
    data = {
        "TripType": trip_type,
        "Origin": origin,
        "Destination": destination,
        "AirlineCode": "",
        "DepartDate": depart_date,
        "ArrivalDate": arrival_date,
        "Class": cabin_class,
        "IsFlexibleDate": False,
        "IsDirectFlight": False,
        "NoOfAdultPax": pax.get("adults",1),
        "NoOfInfantPax": pax.get("infants",0),
        "NoOfChildPax": pax.get("children",0),
        "NoOfYouthPax": "0",
        "CompanyCode": company_code,
        "WebsiteName": website_name,
        "ApplicationAccessMode": "TEST",
    }
    url = f"{base_url}flightsearch"
    response = requests.post(
        url=url,
        headers=header,
        json=data,
        auth=HTTPBasicAuth(username, password),
    )
    if response.status_code == 200:
        return response.json()
    else:
        return None

def pricing_availability_search(base_url,credentials,trip_type,key,token,supp,OptionKeyList):
    company_code=  credentials.get("company_code")
    website_name=  credentials.get("website_name")
    username=  credentials.get("username")
    password=  credentials.get("password")
    account_code=  credentials.get("account_code")
    header = {"Content-Type": "application/json"}
    data = {
        "Key": key,
        "TripType": trip_type,
        "AccountCode": account_code,
        "InboundKey": "ingal",
        "OutBoundKey": "outgal",
        "CompanyCode": company_code,
        "WebsiteName": website_name,
        "ApplicationAccessMode": "TEST",
        "token": token,
        "supp": supp,
        "IsFlexibleDate": False,
        "OptionKeyList": OptionKeyList,
        "NoOfAdultPax": "1",
        "NoOfChildPax": "0",
        "NoOfYouthPax": "0",
    }
    url = f"{base_url}flightprice"
    response = requests.post(
        url=url,
        headers=header,
        json=data,
        auth=HTTPBasicAuth(username, password),
    )
    if response.status_code == 200:
        return response.json()
    else:
        return None

def purchase_api(base_url,credentials,search_details,booking_detail,extracted_data):
    header = {
        "Content-Type": "application/json",
    }
    if len(extracted_data) == 4:
        air_solution, journey, option_info,token = extracted_data
    key = air_solution.get('key',"")
    supp = air_solution.get('supp')
    if search_details['journey_type'] == "One Way":
        TripType = "OW"
    elif search_details['journey_type'] == "Round Trip":
        TripType = "RT"
    pax_list = []
    for pax in booking_detail['pax_details']:
        pax_dict = {
            "Title": pax["title"],
            "FirstName": pax["firstName"],
            "MiddelName": "",  # Assuming no middle name provided in the current.json
            "LastName": pax["lastName"],
            "PaxType": "ADT" if pax["type"] == "adults" else "CHD",  # ADT for adults, CHD for children
            "Gender": "M" if pax["gender"] == "Male" else "F",
            "PaxDOB": pax["dob"].replace("-", "/"),  # Adjust date format if needed
            "IsLeadName": False,  # By default, not the lead name (set first pax as lead below)
        }
        pax_list.append(pax_dict)
    # Mark the first passenger as the lead name
    if pax_list:
        pax_list[0]["IsLeadName"] = True
    try:
        CountryDialingCode = booking_detail.get("contact").get("phoneCode").replace("+", "")
    except:
        CountryDialingCode = "'"
    data = {
        "Key": key,
        "TripType": TripType,
        "AccountCode": credentials["account_code"],
        "CompanyCode": credentials["company_code"],
        "WebsiteName": credentials["website_name"],
        "ApplicationAccessMode": "TEST",
        "token": token,
        "supp":supp,
        "IsFlexible": False,
        "Pax": pax_list,
        "AddressInfo": {
            "City": {
                "CityCode": None,
                "AreaCode": None,
                "CityName": "Hounslow",
                "BillingCityName": None,
            },
            "Country": {
                "CountryCode": "GB",
                "CountryName": "London",
                "BillingCountryName": None,
            },
            "Street": {
                "HouseNo": "Brightsun Travel (Uk) Ltd",
                "PostalCode": "tw3 1ua",
                "Address1": "14 Hanworth Road,, Greater London",
                "Address2": "",
                "Address3": "",
                "AddressType": None,
                "BillingHouseNo": None,
                "BillingAddress1": None,
                "BillingAddress2": None,
                "BillingZipcode": None,
            },
        },
        "Email": booking_detail["contact"]["email"],
        "ContactNo": str(booking_detail["contact"]["phone"]),
        "CountryDialingCode": CountryDialingCode,
    }
    url = f"{base_url}flightpnr"
    response = requests.post(
        url=url,
        headers=header,
        json=data,
        auth=HTTPBasicAuth(credentials["username"], credentials["password"]),
    )
