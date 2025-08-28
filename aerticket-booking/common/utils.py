
import uuid

from users.models import UserDetails,OrganizationFareAdjustment,CountryTax,\
    DistributorAgentFareAdjustment

def create_uuid(suffix=""):
    if suffix == "":
        return str(uuid.uuid4())
    else:
        return suffix+"-"+str(uuid.uuid4())

def set_fare_details(fare_details):
    default_fare = {
        "markup": 0,
        "cashback": 0,
        "parting_percentage": 100,
        "distributor_markup": 0,
        "distributor_cashback": 0,
        "distributor_parting_percentage":100
    }
    default_tax = {
        "tax": 18,
        "tds": 2
    }   
    fare_adjustment = fare_details.get("fare", {})
    for key, value in default_fare.items():
        fare_adjustment.setdefault(key, value)
    tax_condition = fare_details.get("tax", {})
    for key, value in default_tax.items():
        tax_condition.setdefault(key, value)
    return fare_adjustment,tax_condition

def get_fare_markup(user:UserDetails):
    fare_obj = OrganizationFareAdjustment.objects.filter(organization = user.organization).first()
    fare = {
            "markup":fare_obj.markup if fare_obj else 0,
            "cashback":fare_obj.cashback if fare_obj else 0,
            "parting_percentage":fare_obj.parting_percentage if fare_obj else 100
            }
    if user.role.name == "distributor_agent":
        dafa_obj = DistributorAgentFareAdjustment.objects.filter(user = user).first()
        dafa = {"distributor_markup":dafa_obj.markup if dafa_obj else 0 ,
            "distributor_cashback":dafa_obj.cashback if dafa_obj else 0,
            "distributor_parting_percentage":dafa_obj.parting_percentage if dafa_obj else 100}
    else:
        dafa = {"distributor_markup":0,
            "distributor_cashback":0,
            "distributor_parting_percentage":100}
    fare = fare | dafa
    tax_obj = CountryTax.objects.filter(country_id = user.organization.organization_country).first()
    tax = {"tax":tax_obj.tax if tax_obj else 18,"tds":tax_obj.tds if tax_obj else 2}
    return  {"fare":fare,"tax":tax}

def extract_data_recursive(data, keys, default_response):
    for key in keys:
        while isinstance(data, list):
            if data:
                data = data[0]
            else:
                return default_response
        if isinstance(data, dict):
            if key in data:
                data = data[key]
            else:
                return default_response
        else:
            return default_response
    while isinstance(data, list) and data:
        data = data[0]
    return data if data is not None else default_response

def extract_data_recursive(data, keys, default_response):
    for key in keys:
        while isinstance(data, list):
            if data:
                data = data[0]
            else:
                return default_response
        if isinstance(data, dict):
            if key in data:
                data = data[key]
            else:
                return default_response
        else:
            return default_response
    while isinstance(data, list) and data:
        data = data[0]
    return data if data is not None else default_response

def dictlistconverter(dictorlist):
    data = dictorlist if isinstance(dictorlist,list) else [dictorlist]
    return data

def calculate_fare(price,fare_details):
    """
    Include fare adjustment calculations here
    """
    # fare_details = {'fare': {'markup': 0, 'cashback': 0, 'parting_percentage': 100, 
    #             'distributor_markup': 0, 'distributor_cashback': 0, 
    #             'distributor_parting_percentage': 100}, 'tax': {'tax': 18, 'tds': 2}}
    markup = fare_details['fare']['markup']
    distributor_markup = fare_details['fare']['distributor_markup']
    distributor_cashback = fare_details['fare']['distributor_markup']
    cashback = fare_details['fare']['cashback']
    print(price,markup,distributor_markup,cashback,distributor_cashback)
    # import pdb;pdb.set_trace()
    price = price + markup + distributor_markup - cashback - distributor_cashback
    return price