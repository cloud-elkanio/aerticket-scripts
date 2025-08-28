from abc import ABC, abstractmethod
JOURNEY_TYPES = ['One Way', 'Round Trip', 'Multi City']
from users.models import DistributorAgentFareAdjustment,DistributorAgentTransaction
from common.models import FlightSupplierFilters

class AbstractFlightManager(ABC):
    def __init__(self,data,uuid):
        self.vendor_id = "VEN-"+uuid

    def name (self,data="null"):
        return "Abstract"
    def search_flights (self, journey_details):
        pass
    def converter(self, search_response, journey_details,fare_details):
        pass
    def get_journey_types(self):
        return JOURNEY_TYPES
    def support_journey_type(self,journey_type):
        if journey_type in self.get_journey_types():
            return True
        else:
            return False 
    def find_segment_by_id(self,data, segment_id,journey_details):
        pass
    
    def get_fare_details(self,search_details,raw_data,fare_details,raw_doc = None):
        pass

    def get_updated_fare_details(self,index,search_details,raw_data,raw_doc,currentfare,fare_details):
        pass

    def get_ssr(self,**kwargs):
        pass
    
    def check_hold(self,**kwargs):
        pass

    def hold_booking(self,**kwargs):
        pass
    def purchase(self,**kwargs):
        pass

    def convert_hold_to_ticket(self,**kwargs):
        pass

    def cancellation_charges(self,**kwargs):
        pass

    def cancel_ticket(self,**kwargs):
        pass

    def get_repricing(self,**kwargs):
        pass

    def release_hold(self,**kwargs):
        pass
    def check(self,**kwargs):
        pass
    def update_credit(self,**kwargs):
        total_fare = kwargs.get("total_fare",0)
        booking = kwargs.get("booking")
        if booking.user.role.name == "distributor_agent":
            try:
                agent = DistributorAgentFareAdjustment.objects.get(user=booking.user)
                markup = agent.markup if agent.markup else 0
                cashback = agent.cashback if agent.cashback else 0
                final_fare = float(total_fare) + float(markup) - float(cashback)
                old_available_balance = agent.available_balance if agent.available_balance else 0
                new_available_balance = old_available_balance - final_fare
                DistributorAgentTransaction.objects.create(user=agent.user,transtransaction_type='debit',
                                                        booking_type ='new_ticketing', amount=total_fare,
                                                        booking = booking
                                                        )
                agent.available_balance =new_available_balance
                agent.save()
            except:
                pass

    def booking_filters(self,kwargs):
        try:
            journey_type = kwargs.get("journey_type","").upper()
            flight_type = kwargs.get("flight_type","").upper()
            fare_type = kwargs.get("fare_type","").upper()
            supplier_deals = FlightSupplierFilters.objects.filter(supplier_id = kwargs["supplier_id"].split("VEN-")[-1]).order_by("created_at")
            filter_result = {"is_proceed":True,"filtered_airlines":[],"is_lcc":True,"is_gds":True}
            for supplier_deal in supplier_deals:
                if flight_type == "DOM":
                    if not supplier_deal.dom:
                        filter_result["is_proceed"] = False
                    else:
                        filter_result["is_proceed"] = True
                elif flight_type == "INT":
                    if journey_type == "ROUND TRIP":
                        if not supplier_deal.round_int:
                            filter_result["is_proceed"] = False
                        else:
                            filter_result["is_proceed"] = True
                    elif journey_type == "ONE WAY":
                        if not supplier_deal.int:
                            filter_result["is_proceed"] = False
                        else:
                            filter_result["is_proceed"] = True
                if filter_result["is_proceed"]:
                    if fare_type == "REGULAR":
                        if not supplier_deal.regular_fare:
                            filter_result["is_proceed"] = False
                    elif fare_type == "STUDENT":
                        if not supplier_deal.student_fare:
                            filter_result["is_proceed"] = False
                    elif fare_type == "SENIOR CITIZEN":
                        if not supplier_deal.senior_citizen_fare:
                            filter_result["is_proceed"] = False  
                    if filter_result["is_proceed"]:
                        break
                filter_result["is_lcc"] = supplier_deal.lcc
                filter_result["is_gds"] = supplier_deal.gds
                filter_result["filtered_airlines"] = supplier_deal.airline
            return filter_result
        except:
            return {"is_proceed":True,"filtered_airlines":[],"is_lcc":True,"is_gds":True}