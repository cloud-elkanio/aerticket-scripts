from datetime import datetime
import uuid
import time
from users.models import UserDetails,OrganizationFareAdjustment,CountryTax,\
    DistributorAgentFareAdjustment
from common.models import Booking
from django.db.models import Count, Q,F, ExpressionWrapper, fields
from collections import defaultdict
from common.utils import *

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
    fare_obj = OrganizationFareAdjustment.objects.filter(organization = user.organization,module = 'insurance').first()
    fare = {
            "markup":fare_obj.markup if fare_obj else 0,
            "cashback":fare_obj.cashback if fare_obj else 0,
            "parting_percentage":fare_obj.parting_percentage if fare_obj else 100,
            "cancellation_charges":fare_obj.cancellation_charges if fare_obj else 0,
            }
    if user.role.name == "distributor_agent":
        dafa_obj = DistributorAgentFareAdjustment.objects.filter(user = user,module = 'insurance').first()
        dafa = {"distributor_markup":dafa_obj.markup if dafa_obj else 0 ,
            "distributor_cashback":dafa_obj.cashback if dafa_obj else 0,
            "distributor_parting_percentage":dafa_obj.parting_percentage if dafa_obj else 100,
            "distributor_cancellation_charges":dafa_obj.cancellation_charges if dafa_obj else 0}
    else:
        dafa = {"distributor_markup":0,
            "distributor_cashback":0,
            "distributor_parting_percentage":100,
            "distributor_cancellation_charges" :0}
    fare = fare | dafa
    tax_obj = CountryTax.objects.filter(country_id = user.organization.organization_country).first()
    tax = {"tax":tax_obj.tax if tax_obj else 18,"tds":tax_obj.tds if tax_obj else 2}
    return  {"fare":fare,"tax":tax,"user":user}

def fare_calculation(fare_detatils,supplier_published_fare,supplier_offered_fare):
    fare_adjustment = fare_detatils['fare']
    tax_condition = fare_detatils['tax']
    new_published_fare = supplier_published_fare + ((float(fare_adjustment["markup"]))+(float(fare_adjustment["distributor_markup"]))-\
                            float(fare_adjustment["cashback"]) - float(fare_adjustment["distributor_cashback"]))
    new_offered_fare = supplier_published_fare + (float(fare_adjustment["markup"]) + float(fare_adjustment["distributor_markup"]) -\
        float(fare_adjustment["cashback"])-float(fare_adjustment["distributor_cashback"])) -\
        (supplier_published_fare-supplier_offered_fare)*(float(fare_adjustment["parting_percentage"])/100)*(float(fare_adjustment["distributor_parting_percentage"])/100)*(1-float(tax_condition["tax"])/100)
    discount = new_published_fare - new_offered_fare
    return {"offered_fare":round(new_offered_fare,2),"discount":round(discount,2),
            "published_fare":round(new_published_fare,2),"supplier_published_fare":supplier_published_fare,
            "supplier_offered_fare":supplier_offered_fare}
