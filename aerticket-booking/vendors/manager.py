from .hotels.hotel_manager import HotelManager
from .flights.flight_manager import FlightManager
from .transfers.transfers_manager import TransferManager

def get_manager_class(class_string):
    return eval(class_string)
