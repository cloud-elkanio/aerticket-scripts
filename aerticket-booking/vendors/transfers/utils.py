from users.models import UserDetails,OrganizationFareAdjustment,CountryTax,\
    DistributorAgentFareAdjustment

def get_fare_markup(user:UserDetails):
    fare_obj = OrganizationFareAdjustment.objects.filter(organization = user.organization,module = 'flight').first()
    fare = {
            "markup":fare_obj.markup if fare_obj else 0,
            "cashback":fare_obj.cashback if fare_obj else 0,
            "parting_percentage":fare_obj.parting_percentage if fare_obj else 100,
            "cancellation_charges":fare_obj.cancellation_charges if fare_obj else 0,
            }
    if user.role.name == "distributor_agent":
        dafa_obj = DistributorAgentFareAdjustment.objects.filter(user = user,module = 'flight').first()
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