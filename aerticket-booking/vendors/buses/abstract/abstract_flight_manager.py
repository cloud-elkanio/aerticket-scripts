from abc import ABC, abstractmethod
from users.models import DistributorAgentFareAdjustment,DistributorAgentTransaction
class AbstractBusManager(ABC):
    def __init__(self,credentials,uuid,mongo_client):
        self.vendor_id = "VEN-"+uuid

    def name (self):
        return "Abstract"
    
