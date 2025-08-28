
from users.models import SupplierIntegration
from vendors.hotels.models import GiataCity, GiataDestination, GiataProperties
from vendors.hotels.tbo.api import get_destinations, perform_search,authentication


class Manager(object):

    def __init__(self,**kwargs):
        self.data = kwargs['data']
        self.vendor = kwargs['vendor']
        self.mongo_client = kwargs['mongo_client']
        self.supplier_instance = SupplierIntegration.objects.filter(name = 'TBO',integration_type = 'Hotels').first()
        self.base_url = self.supplier_instance.data['base_url'] if self.supplier_instance else None
        self.token = authentication(self.base_url,self.supplier_instance.data) if self.supplier_instance else None
        
    
    def name (self):
        return "TBO"
    
    def get_vendor_id(self):
        return str(self.vendor.id)

    
    def search_results(self,data):
        print("data = ",data)

        # def process_segment(seg, index):
        #     """Function to process each segment in a thread."""
        #     search_response = search(destination_id, code, token,check_in_date,
        #     check_out_date,no_of_rooms,room_pax,max_rating = 5,
        #     min_rating = 0,end_user_ip = "123.1.1.1",
        #     search_base_url="https://HotelBE.tektravels.com")
        #     flight_search_response = self.add_uuid_to_segments(
        #         flight_search_response, flight_type, journey_type
        #     )
        #     return index, flight_search_response


        # if journey_type =="Multi City" or \
        #     (journey_type =="Round Trip" and flight_type == "DOM") :
        #     def run_in_threads(segments, segment_keys):
        #         final = {}
        #         with concurrent.futures.ThreadPoolExecutor() as executor:
        #             futures = {
        #                 executor.submit(process_segment, seg, index): index
        #                 for index, seg in enumerate(segments)
        #             }
        #             for future in concurrent.futures.as_completed(futures):
        #                 index, response = future.result()
        #                 final[segment_keys[index]] = response

        #         return final

        #     final_result = run_in_threads(segments, segment_keys)
        #     return {"data":final_result,"status":"success"}

        # else:
        #     pass
        check_in_date = data['check_in_date']
        check_out_date = data['check_out_date']
        room_count = data['room_count']
        room_pax = data['room_pax']
        if data["search_type"] == "property":
            property_id = data["search_query"]
            property_instance = GiataProperties.objects.filter(id = property_id).first()
            if property_instance:
                destination_ids = [property_instance.city_id.tbo_id]
            else:
                destination_ids = []

        elif data["search_type"] == "city":
            city_id = data["search_query"]
            city_instance = GiataCity.objects.filter(id = city_id).first()
            if city_instance:
                if not city_instance.tbo_id:
                    country_code = city_instance.destination_id.country_id.country_code
                    destinations = get_destinations(country_code,self.token ,self.base_url)
                    # import pdb;pdb.set_trace()
                    return {"data":{},"status":"failure","error":"missing tbo destination id"}
                destination_ids = [city_instance.tbo_id]
                
            else:
                destination_ids = []

        elif data["search_type"] == "destination":
            city_id = data["search_query"]
            cities = GiataCity.objects.filter(destination_id__id = city_id).all()
            destination_ids = [dest.tbo_id for dest in  cities]
        # import pdb;pdb.set_trace()
        print("destination_ids",destination_ids)
        if not  destination_ids:
            print("here1")
            return {"data":{},"status":"failure","error":"missing destination id"}
        elif not self.supplier_instance:
            print("here2")
            return {"data":{},"status":"failure","error":"missing supplier integration"}
        else:
            print("here3")
            country_code = "IN"
            token = authentication(self.supplier_instance.data)
            search_base_url = self.supplier_instance.data['search_base_url']
            search_responses = []
            for destination_id in destination_ids:

                search_response = perform_search(destination_id, country_code, token,check_in_date,
                                                check_out_date,room_count,room_pax,max_rating = 5,
                                                min_rating = 0,end_user_ip = "123.1.1.1",
                                                search_base_url=search_base_url)   
                search_responses.append(search_response)
            return {"data":search_response,"status":"success"}
    
    
    def converter(self, search_response, journey_details,fare_details):
        print(search_response, journey_details,fare_details)
        print("search_response = ",search_response)
        print("journey_details = ",journey_details)
        print("fare_details = ",fare_details)
