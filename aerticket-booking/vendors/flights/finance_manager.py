from users.models import LookupCreditCard,Organization
from common.models import (FlightBookingItineraryDetails,
                           FlightBookingPaxDetails,LookupEasyLinkSupplier,
                           FlightBookingSSRDetails)
from vendors.flights import utils
import requests,json
import hashlib
import os,re
import time
from django.db.models import QuerySet
from datetime import datetime
from vendors.flights import mongo_handler
from dotenv import load_dotenv
load_dotenv() 

class FinanceManager:
    def __init__(self,user):
        self.user = user
        self.bta_env = os.getenv('BTA_ENV')
        self.org = user.organization
        self.easy_link = user.organization.easy_link_billing_account
        data = self.easy_link.data[0]
        self.base_url = data.get("url")
        self.branch_code = data.get("branch_code")
        self.portal_reference_code = data.get("portal_reference_code")
        self.mongo_client = mongo_handler.Mongo()
        
    def airticket_billing(self,data_list,itinerary_id = "",display_id = ""):
        url = self.base_url+"/processEasyBillImp/?sBrCode="+self.branch_code+"&PortalRefCode="+self.portal_reference_code
        payload = """<Invoicedata>\r\n"""
        for data in data_list:
            payload+=f"""
            <Invoice XORef=\"{data['XORef']}\"\r\n
            CustCode=\"{data['CustCode']}\"\r\n
            suppcode=\"{data['suppcode']}\"\r\n
            AirCode=\"{data['AirCode']}\"\r\n
            diflg=\"{data['diflg']}\"\r\n
            PNRAir=\"{data['PNRAir']}\"\r\n
            PNRCrs=\"{data['PNRCrs']}\"\r\n
            tktRef=\"{data['tktRef']}\"\r\n
            tktNo=\"{data['tktNo'][-10:]}\"\r\n
            tktDt=\"{data['tktDt']}\"\r\n
            tkttype=\"{data['tkttype']}\"\r\n
            RCFlag=\"{data['RCFlag']}\"\r\n
            ReftktNo=\"{data['ReftktNo']}\"\r\n
            Region=\"{data['Region']}\"\r\n
            ReftktDt=\"{data['ReftktDt']}\"\r\n
            AirCCNo=\"{data['AirCCNo']}\"\r\n
            PaxName=\"{data['PaxName']}\"\r\n
            Sector=\"{data['Sector']}\"\r\n
            CRS=\"{data['CRS']}\"\r\n
            FareBasis=\"{data['FareBasis']}\"\r\n
            DealCode=\"{data['DealCode']}\"\r\n
            S1Sector=\"{data['S1Sector']}\"\r\n
            S1FltNo=\"{data['S1FltNo']} \"\r\n
            S1Date=\"{data['S1Date']}\"\r\n
            S1Class=\"{data['S1Class']}\"\r\n
            S1FltType=\"{data['S1FltType']}\"\r\n
            S2Sector=\"{data['S2Sector']}\"\r\n
            S2FltNo=\"{data['S2FltNo']}\"\r\n
            S2Date=\"{data['S2Date']}\"\r\n
            S2Class=\"{data['S2Class']}\"\r\n
            S2FltType=\"{data['S2FltType']}\"\r\n
            S3Sector=\"{data['S3Sector']}\"\r\n
            S3FltNo=\"{data['S3FltNo']}\"\r\n
            S3Date=\"{data['S3Date']}\"\r\n
            S3Class=\"{data['S3Class']}\"\r\n
            S3FltType=\"{data['S3FltType']}\"\r\n
            S4Sector=\"{data['S4Sector']}\"\r\n
            S4FltNo=\"{data['S4FltNo']}\"\r\n
            S4Date=\"{data['S4Date']}\"\r\n
            S4Class=\"{data['S4Class']}\"\r\n
            S4FltType=\"{data['S4FltType']}\"\r\n
            S5Sector=\"{data['S2FltType']}\"\r\n
            S5FltNo=\"{data['S5FltNo']}\"\r\n
            S5Date=\"{data['S5Date']}\"\r\n
            S5Class=\"{data['S5Class']}\"\r\n
            S5FltType=\"{data['S5FltType']}\"\r\n
            S6Sector=\"{data['S6Sector']}\"\r\n
            S6FltNo=\"{data['S6FltNo']}\"\r\n
            S6Date=\"{data['S6Date']}\"\r\n
            S6Class=\"{data['S6Class']}\"\r\n
            S6FltType=\"{data['S6FltType']}\"\r\n
            BasicFare=\"{data['BasicFare']}\"\r\n
            AddlAmt=\"{data['AddlAmt']}\"\r\n
            SuppAddlAmt=\"{data['SuppAddlAmt']}\"\r\n
            NC1Tax=\"{data['NC1Tax']}\"\r\n
            NC1AddlAmt=\"{data['NC1AddlAmt']}\"\r\n
            NC2Tax=\"{data['NC2Tax']}\"\r\n
            NC2AddlAmt=\"{data['NC2AddlAmt']}\"\r\n
            CTax=\"{data['CTax']}\"\r\n
            CAddlAmt=\"{data['CAddlAmt']}\"\r\n
            JNTax=\"{data['JNTax']}\"\r\n
            JNAddlAmt=\"{data['JNAddlAmt']}\"\r\n
            TxnFees=\"{data['TxnFees']}\"\r\n
            OCTax=\"{data['OCTax']}\"\r\n
            StdComm=\"{data['StdComm']}\"\r\n
            CPInc=\"{data['CPInc']}\"\r\n
            NCPInc=\"{data['NCPInc']}\"\r\n
            PLB=\"{data['PLB']}\"\r\n
            OR=\"{data['OR']}\"\r\n
            SrvChrgs=\"{data['SrvChrgs']}\"\r\n
            MGTFee=\"{data['MGTFee']}\"\r\n
            CustStdComm=\"{data['CustStdComm']}\"\r\n
            CustCPInc=\"{data['CustCPInc']}\"\r\n
            CustNCPInc=\"{data['CustNCPInc']}\"\r\n
            CustPLB=\"{data['CustPLB']}\"\r\n
            CustOR=\"{data['CustOR']}\"\r\n
            CustSrvChrgs=\"{data['CustSrvChrgs']}\"\r\n
            CustMGTFee=\"{data['CustMGTFee']}\"\r\n
            PercTDS=\"{data['PercTDS']}\"\r\n
            TDS=\"{data['TDS']}\"\r\n
            CustPercTDS=\"{data['CustPercTDS']}\"\r\n
            CustTDS=\"{data['CustTDS']}\"\r\n
            sGTAX=\"{data['sGTAX']}\"\r\n
            PercGTAX=\"{data['PercGTAX']}\"\r\n
            GTAX=\"{data['GTAX']}\"\r\n
            sCustGTAX=\"{data['sCustGTAX']}\"\r\n
            CustPercGTAX=\"{data['CustPercGTAX']}\"\r\n
            CustGTAX=\"{data['CustGTAX']}\"\r\n
            CustGTAXAdl=\"{data['CustGTAXAdl']}\"\r\n
            SCPercGTAX=\"{data['SCPercGTAX']}\"\r\n
            SCGTAX=\"{data['SCGTAX']}\"\r\n
            SCPercSrch=\"{data['SCPercSrch']}\"\r\n
            SCSrch=\"{data['SCSrch']}\"\r\n
            CustSCPercGTAX=\"{data['CustSCPercGTAX']}\"\r\n
            CustSCGTAX=\"{data['CustSCGTAX']}\"\r\n
            CustSCPercSrch=\"{data['CustSCPercSrch']}\"\r\n
            CustSCSrch=\"{data['CustSCSrch']}\"\r\n
            credittype=\"{data['credittype']}\" />"""
        payload+="""\r\n\r\n</Invoicedata>"""
        headers = {}
        response = requests.request("POST", url, headers = headers, data = payload,timeout = 120)
        easy_doc = {"url":url,"payload": payload,"response": response.text,"type":"easy_link","itinerary_id":str(itinerary_id),
                    "display_id":display_id,"payload_json":data_list,"refund":False,"createdAt":datetime.now()}
        self.mongo_client.vendors.insert_one(easy_doc)

    def airticket_refund_billing(self,data_list,itinerary_id = "",display_id = ""):
        url = self.base_url+"/processEasyBillImp_Refund/?sBrCode="+self.branch_code+"&PortalRefCode="+self.portal_reference_code
        payload = """<Invoicedata>\r\n"""
        for data in data_list:
            payload+=f"""
            <Invoice XORef=\"{data['XORef']}\"\r\n
            CustCode=\"{data['CustCode']}\"\r\n
            suppcode=\"{data['suppcode']}\"\r\n
            AirCode=\"{data['AirCode']}\"\r\n
            diflg=\"{data['diflg']}\"\r\n
            PNRAir=\"{data['PNRAir']}\"\r\n
            PNRCrs=\"{data['PNRCrs']}\"\r\n
            tktRef=\"{data['tktRef']}\"\r\n
            tktNo=\"{data['tktNo'][-10:]}\"\r\n
            tktDt=\"{data['tktDt']}\"\r\n
            tkttype=\"{data['tkttype']}\"\r\n
            RCFlag=\"{data['RCFlag']}\"\r\n
            ReftktNo=\"{data['ReftktNo']}\"\r\n
            Region=\"{data['Region']}\"\r\n
            ReftktDt=\"{data['ReftktDt']}\"\r\n
            AirCCNo=\"{data['AirCCNo']}\"\r\n
            PaxName=\"{data['PaxName']}\"\r\n
            Sector=\"{data['Sector']}\"\r\n
            CRS=\"{data['CRS']}\"\r\n
            FareBasis=\"{data['FareBasis']}\"\r\n
            DealCode=\"{data['DealCode']}\"\r\n
            S1Sector=\"{data['S1Sector']}\"\r\n
            S1FltNo=\"{data['S1FltNo']} \"\r\n
            S1Date=\"{data['S1Date']}\"\r\n
            S1Class=\"{data['S1Class']}\"\r\n
            S1FltType=\"{data['S1FltType']}\"\r\n
            S2Sector=\"{data['S2Sector']}\"\r\n
            S2FltNo=\"{data['S2FltNo']}\"\r\n
            S2Date=\"{data['S2Date']}\"\r\n
            S2Class=\"{data['S2Class']}\"\r\n
            S2FltType=\"{data['S2FltType']}\"\r\n
            S3Sector=\"{data['S3Sector']}\"\r\n
            S3FltNo=\"{data['S3FltNo']}\"\r\n
            S3Date=\"{data['S3Date']}\"\r\n
            S3Class=\"{data['S3Class']}\"\r\n
            S3FltType=\"{data['S3FltType']}\"\r\n
            S4Sector=\"{data['S4Sector']}\"\r\n
            S4FltNo=\"{data['S4FltNo']}\"\r\n
            S4Date=\"{data['S4Date']}\"\r\n
            S4Class=\"{data['S4Class']}\"\r\n
            S4FltType=\"{data['S4FltType']}\"\r\n
            S5Sector=\"{data['S2FltType']}\"\r\n
            S5FltNo=\"{data['S5FltNo']}\"\r\n
            S5Date=\"{data['S5Date']}\"\r\n
            S5Class=\"{data['S5Class']}\"\r\n
            S5FltType=\"{data['S5FltType']}\"\r\n
            S6Sector=\"{data['S6Sector']}\"\r\n
            S6FltNo=\"{data['S6FltNo']}\"\r\n
            S6Date=\"{data['S6Date']}\"\r\n
            S6Class=\"{data['S6Class']}\"\r\n
            S6FltType=\"{data['S6FltType']}\"\r\n
            BasicFare=\"{data['BasicFare']}\"\r\n
            AddlAmt=\"{data['AddlAmt']}\"\r\n
            SuppAddlAmt=\"{data['SuppAddlAmt']}\"\r\n
            NC1Tax=\"{data['NC1Tax']}\"\r\n
            NC1AddlAmt=\"{data['NC1AddlAmt']}\"\r\n
            NC2Tax=\"{data['NC2Tax']}\"\r\n
            NC2AddlAmt=\"{data['NC2AddlAmt']}\"\r\n
            CTax=\"{data['CTax']}\"\r\n
            CAddlAmt=\"{data['CAddlAmt']}\"\r\n
            JNTax=\"{data['JNTax']}\"\r\n
            JNAddlAmt=\"{data['JNAddlAmt']}\"\r\n
            TxnFees=\"{data['TxnFees']}\"\r\n
            OCTax=\"{data['OCTax']}\"\r\n
            StdComm=\"{data['StdComm']}\"\r\n
            CPInc=\"{data['CPInc']}\"\r\n
            NCPInc=\"{data['NCPInc']}\"\r\n
            PLB=\"{data['PLB']}\"\r\n
            OR=\"{data['OR']}\"\r\n
            SrvChrgs=\"{data['SrvChrgs']}\"\r\n
            MGTFee=\"{data['MGTFee']}\"\r\n
            CustStdComm=\"{data['CustStdComm']}\"\r\n
            CustCPInc=\"{data['CustCPInc']}\"\r\n
            CustNCPInc=\"{data['CustNCPInc']}\"\r\n
            CustPLB=\"{data['CustPLB']}\"\r\n
            CustOR=\"{data['CustOR']}\"\r\n
            CustSrvChrgs=\"{data['CustSrvChrgs']}\"\r\n
            CustMGTFee=\"{data['CustMGTFee']}\"\r\n
            PercTDS=\"{data['PercTDS']}\"\r\n
            TDS=\"{data['TDS']}\"\r\n
            CustPercTDS=\"{data['CustPercTDS']}\"\r\n
            CustTDS=\"{data['CustTDS']}\"\r\n
            sGTAX=\"{data['sGTAX']}\"\r\n
            PercGTAX=\"{data['PercGTAX']}\"\r\n
            GTAX=\"{data['GTAX']}\"\r\n
            sCustGTAX=\"{data['sCustGTAX']}\"\r\n
            CustPercGTAX=\"{data['CustPercGTAX']}\"\r\n
            CustGTAX=\"{data['CustGTAX']}\"\r\n
            CustGTAXAdl=\"{data['CustGTAXAdl']}\"\r\n
            SCPercGTAX=\"{data['SCPercGTAX']}\"\r\n
            SCGTAX=\"{data['SCGTAX']}\"\r\n
            SCPercSrch=\"{data['SCPercSrch']}\"\r\n
            SCSrch=\"{data['SCSrch']}\"\r\n
            CustSCPercGTAX=\"{data['CustSCPercGTAX']}\"\r\n
            CustSCGTAX=\"{data['CustSCGTAX']}\"\r\n
            CustSCPercSrch=\"{data['CustSCPercSrch']}\"\r\n
            CustSCSrch=\"{data['CustSCSrch']}\"\r\n
            RAF=\"{data['RAF']}\"\r\n
            Penalty=\"{data['Penalty']}\"\r\n
            CustRAF=\"{data['CustRAF']}\"\r\n
            CustPenalty=\"{data['CustPenalty']}\"\r\n
            CustPercGTAXRAF=\"{data['CustPercGTAXRAF']}\"\r\n
            CustGTAXRAF=\"{data['CustGTAXRAF']}\"\r\n
            CustPercGTAXpen=\"{data['CustPercGTAXpen']}\"\r\n
            CustGTAXpen=\"{data['CustGTAXpen']}\"\r\n
            SCPaid=\"{data['SCPaid']}\"\r\n
            CustSCPaid=\"{data['CustSCPaid']}\"\r\n
            CustGTAXSCP=\"{data['CustGTAXSCP']}\"\r\n
            CreditType=\"{data['credittype']}\" />"""
        payload +="""\r\n\r\n</Invoicedata>"""
        response = requests.post(url, headers = {}, data = payload,timeout = 120)
        easy_doc = {"url":url,"payload": payload,"response": response.text,"type":"easy_link","itinerary_id":str(itinerary_id),
                    "display_id":display_id,"payload_json":data_list,"refund":True,"createdAt":datetime.now()}

        self.mongo_client.vendors.insert_one(easy_doc)

    def convert_to_4_decimal_string(self,value):
        try:
            formatted_value = f"{float(value):.4f}"
            return formatted_value
        except ValueError:
            return "0.0000"  
         
    def find_ssr_cost(self,pax,pax_data:QuerySet[FlightBookingPaxDetails],ssr_data:QuerySet[FlightBookingSSRDetails]):
        FirstName = pax.get('FirstName','').lower()
        LastName = pax.get('LastName','').lower()
        pax_id = [ind_pax for ind_pax in pax_data if ind_pax.first_name.lower() == FirstName and \
                    ind_pax.last_name.lower() == LastName]
        if len(pax_id) == 0:
            return 0
        else:
            pax_id = pax_id[0]
            ind_ssr = ssr_data.filter(pax = pax_id).first()
            ssr_value = 0
            if ind_ssr.is_baggage == True:
                baggage_data = json.loads(ind_ssr.baggage_ssr)
                for key in baggage_data.keys():
                    ssr_value += baggage_data[key].get('Price',0)
            if ind_ssr.is_meals == True:
                meals_data = json.loads(ind_ssr.meals_ssr)
                for key in meals_data.keys():
                    ssr_value += (meals_data[key].get('Price',0)*meals_data[key].get('Quantity',0))
            if ind_ssr.is_seats == True:
                seats_data = json.loads(ind_ssr.seats_ssr)
                if seats_data:
                    for key in seats_data.keys():
                        if len(seats_data[key])>0:
                            ssr_value += seats_data[key].get('Price',0) 
            return ssr_value


    def book_tbo(self,ticket_response,itinerary:FlightBookingItineraryDetails,credentials,
                 payment_details,total_pax,soft_fail):
        def unify_sector_tbo(segments):
            Sector = []
            for segment in segments:
                Sector.append(segment['Origin']['Airport']['AirportCode'])
                Sector.append(segment['Destination']['Airport']['AirportCode'])
            if len(Sector) >=2:
                result = [Sector[0]]
                for i in range(1, len(Sector)):
                    if Sector[i] != Sector[i - 1]: 
                        result.append(Sector[i])
                sector_output = "/".join(result)
            else:
                sector_output = "/".join(Sector)
            return sector_output
        display_id = itinerary.booking.display_id
        supplier_id = credentials.get("supplier_id")
        if soft_fail:
            tickets = ticket_response['Response']
            tickets["PNR"] = tickets['FlightItinerary']['PNR']
        else:
            tickets = ticket_response['Response']['Response']       
        segments = tickets['FlightItinerary']['Segments']
        Sectors = unify_sector_tbo(segments)
        fare_details = utils.get_fare_markup(self.user)
        fare_adjustment,tax_condition= utils.set_fare_details(fare_details)
        search_details = itinerary.booking.search_details
        Receipt = tickets.get("FlightItinerary",{}).get("Fare",{})
        ReceiptAmt = Receipt.get("PublishedFare",0)+Receipt.get("TotalBaggageCharges",0)+ \
                        Receipt.get("TotalMealCharges",0)+Receipt.get("TotalSeatCharges",0)+ \
                            Receipt.get("TotalSpecialServiceCharges",0)
        if search_details.flight_type == "DOM":
            diflg = "D"
        else:
            diflg = "I"

        Sdata = {}
        for idx,segment in enumerate(segments):
            Sdata['S'+str(idx+1)+'Sector'] = segment['Origin']['Airport']['AirportCode']+ "/" + segment['Destination']['Airport']['AirportCode']
            Sdata['S'+str(idx+1)+'FltNo'] = segment['Airline']['AirlineCode'] + segment['Airline']['FlightNumber']
            Sdata['S'+str(idx+1)+'Date'] = datetime.fromisoformat(segment['Origin']['DepTime']).strftime('%d/%m/%Y')
            Sdata['S'+str(idx+1)+'Class'] = segment['Airline']['FareClass']
            Sdata['S'+str(idx+1)+'FltType'] = ''
        if idx+2<7:
            for i in range(idx+2,7):
                Sdata['S'+str(i)+'Sector'] = ''
                Sdata['S'+str(i)+'FltNo'] = ''
                Sdata['S'+str(i)+'Date'] = ''
                Sdata['S'+str(i)+'Class'] = ''
                Sdata['S'+str(i)+'FltType'] = ''

        final_result = []
        supplier_publish_fare = payment_details.get("supplier_published_fare")
        supplier_offer_fare = payment_details.get("supplier_offered_fare")
        # removing markup,cashback and parting percentage of agent
        new_published_fare_distributor = supplier_publish_fare + (float(fare_adjustment["markup"])-\
                        float(fare_adjustment["cashback"]))*total_pax

        new_offer_fare_distributor = supplier_publish_fare + (float(fare_adjustment["markup"])  -\
                                fare_adjustment["cashback"])*total_pax -\
                                (supplier_publish_fare - supplier_offer_fare)*(float(fare_adjustment["parting_percentage"])/100)*(1-float(tax_condition["tax"])/100)
        StdComm = (supplier_publish_fare- supplier_offer_fare)/total_pax 
        CustStdComm = (new_published_fare_distributor -new_offer_fare_distributor)/total_pax + float(fare_adjustment['cashback'])
        for pax in tickets['FlightItinerary']['Passenger']:
            NC2Tax = [tb['value'] for tb in pax['Fare'].get('TaxBreakup') or [] if tb.get('key') == 'YR']
            if len(NC2Tax)>0:
                NC2Tax = NC2Tax[0]
            else:
                NC2Tax = 0
            published_fare = pax['Fare'].get('PublishedFare')
            NC1Tax = published_fare - (pax['Fare'].get('BaseFare',0)+pax['Fare'].get('YQTax',0))- \
                sum([float(x['value']) for x in pax['Fare'].get('TaxBreakup') or [] if x['key'] in ['K3','YR']])
            NC1AddlAmt = float(fare_adjustment['markup'])
            K3 = [float(x['value']) for x in pax['Fare'].get('TaxBreakup') or [] if x['key'] == 'K3']
            if len(K3)>0:
                K3 = K3[0]
            else:
                K3 = 0
            TBOMARKUP = [float(x['value']) for x in pax['Fare']['ChargeBU'] if x['key'] == 'TBOMARKUP']
            if len(TBOMARKUP)>0:
                TBOMARKUP = TBOMARKUP[0]
            else:
                TBOMARKUP = 0
            TDS = tax_condition['tds']*StdComm /100
            CustTDS =  tax_condition['tds']*CustStdComm/100
            GTAX = tax_condition['tax']*pax['Fare'].get('ServiceFee',0)/100
            data = {
            "XORef": display_id,
            "CustCode": self.org.easy_link_billing_code,
            "suppcode": supplier_id,
            "AirCode": tickets['FlightItinerary']['AirlineCode'],
            "diflg": diflg,
            "PNRAir": tickets['PNR'],
            "PNRCrs": "",
            "tktRef": self.org.easy_link_account_name,
            "tktNo": pax.get("Ticket",{}).get("TicketNumber",tickets['PNR']),
            "tktDt": datetime.fromtimestamp(itinerary.modified_at).strftime("%d/%m/%Y"),
            "tkttype": "C",
            "BasicFare": pax['Fare']['BaseFare'],
            "AddlAmt": "0.0000",
            "SuppAddlAmt": "0.0000",
            "NC1Tax": self.convert_to_4_decimal_string(NC1Tax),
            "NC1AddlAmt": self.convert_to_4_decimal_string(NC1AddlAmt),
            "NC2Tax": self.convert_to_4_decimal_string(NC2Tax),
            "NC2AddlAmt": "0.0000",
            "CTax": self.convert_to_4_decimal_string(pax['Fare'].get('YQTax',0)),
            "CAddlAmt": "0.0000",
            "JNTax": self.convert_to_4_decimal_string(K3),
            "JNAddlAmt": "0.0000",
            "TxnFees": "0.0000",
            "OCTax": "0.0000",
            "StdComm":self.convert_to_4_decimal_string(StdComm),
            "CPInc": "0.0000",
            "NCPInc": "0.0000",
            "PLB": "0.0000",
            "OR": "0.0000",
            "SrvChrgs": self.convert_to_4_decimal_string(pax['Fare'].get('ServiceFee',0)),
            "MGTFee": self.convert_to_4_decimal_string(TBOMARKUP), 
             "CustStdComm":self.convert_to_4_decimal_string(CustStdComm),
            "CustCPInc": "0.0000",
            "CustNCPInc": "0.0000",
            "CustPLB":"0.0000",
            "CustOR": "0.0000",
            "CustSrvChrgs": self.convert_to_4_decimal_string(pax['Fare'].get('ServiceFee',0)), 
            "CustMGTFee": self.convert_to_4_decimal_string(TBOMARKUP), 
            "PercTDS": self.convert_to_4_decimal_string(tax_condition['tds']), 
            "TDS": self.convert_to_4_decimal_string(TDS), 
            "CustPercTDS": self.convert_to_4_decimal_string(tax_condition['tds']),
            "CustTDS":self.convert_to_4_decimal_string(CustTDS),
            "sGTAX": "",
            "PercGTAX": self.convert_to_4_decimal_string(tax_condition['tax']), 
            "GTAX": self.convert_to_4_decimal_string(GTAX),
            "sCustGTAX": "",
            "CustPercGTAX": self.convert_to_4_decimal_string(tax_condition['tax']),
            "CustGTAX": self.convert_to_4_decimal_string(GTAX),
            "CustGTAXAdl": "0.0000",
            "SCPercGTAX": "0.0000", 
            "SCGTAX": "0.0000",
            "SCPercSrch": "0.0000",
            "SCSrch": "0.0000",
            "CustSCPercGTAX": "0.0000",
            "CustSCGTAX": "0.0000",
            "CustSCPercSrch": "0.0000",
            "CustSCSrch": "0.0000",
            "credittype": "F",
            "RCFlag":'',
            "ReftktNo":"",
            'Region':'',
            'ReftktDt':'',
            'AirCCNo':'',
            'PaxName': (pax.get('Title',"")+" "+pax.get('FirstName',"")+" "+ pax.get('LastName',"")).replace(".","").strip(),
            'Sector':Sectors,
            "CRS":'OH',
            'FareBasis':tickets['FlightItinerary']['FareRules'][0]['FareBasisCode'],
            'DealCode':'',
            'BillNarration': '',
            'BillNote':'',
            'ReceiptAmt':ReceiptAmt
            }

            final_data = Sdata | data
            final_result.append(final_data)
        self.airticket_billing(final_result,itinerary.id,display_id)

    def book_tripjack(self,**kwargs):

        def unify_sector_tripjack(segments):
            Sector = []
            for segment in segments:
                for seg in segment:
                    Sector.append(seg['da']['code'])
                    Sector.append(seg['aa']['code'])
            if len(Sector) >=2:
                result = [Sector[0]]
                for i in range(1, len(Sector)):
                    if Sector[i] != Sector[i - 1]: 
                        result.append(Sector[i])
                sector_output = "/".join(result)
            else:
                sector_output = "/".join(Sector)
            return sector_output
        easy_link_datas = []
        search_details = kwargs["itinerary"].booking.search_details
        fare_details = utils.get_fare_markup(self.user)
        fare_adjustment,tax_condition= utils.set_fare_details(fare_details)
        diflg = "D" if search_details.flight_type == "DOM" else "I"
        booking_data = kwargs["booking_data"]
        ReceiptAmt = booking_data["itemInfos"]["AIR"]["totalPriceInfo"]["totalFareDetail"].get("fC",{}).get("TF",0)
        if len(booking_data['itemInfos']['AIR']['tripInfos']) == 1:
            segments = [booking_data['itemInfos']['AIR']['tripInfos'][0]['sI']]
        else:
            segments = [x['sI'] for x in booking_data['itemInfos']['AIR']['tripInfos']]
        Sectors = unify_sector_tripjack(segments)
        Sdata = {}
        count = 0
        payment_details = kwargs["payment_details"]
        supplier_publish_fare = payment_details.get("supplier_published_fare")
        supplier_offer_fare = payment_details.get("supplier_offered_fare")

        # removing markup,cashback and parting percentage of agent
        new_published_fare_distributor = supplier_publish_fare + (float(fare_adjustment["markup"])-\
                        float(fare_adjustment["cashback"]) )*kwargs["pax_length"]
        new_offer_fare_distributor = supplier_publish_fare + (float(fare_adjustment["markup"])  -\
                                fare_adjustment["cashback"])*kwargs["pax_length"] -\
                                (supplier_publish_fare - supplier_offer_fare)*(float(fare_adjustment["parting_percentage"])/100)*(1-float(tax_condition["tax"])/100)
        CustStdComm = (new_published_fare_distributor - new_offer_fare_distributor)/kwargs["pax_length"]
        CustStdComm = CustStdComm + CustStdComm*tax_condition['tds']/100

        for seg in segments:
            for segment in seg:
                Sdata['S'+str(count+1)+'Sector'] = segment['da']['code']+ "/" + segment['aa']['code']
                Sdata['S'+str(count+1)+'FltNo'] = segment['fD']['aI']['code'] + segment['fD']['fN']
                Sdata['S'+str(count+1)+'Date'] = datetime.fromisoformat(segment['dt']).strftime('%d/%m/%Y') 
                Sdata['S'+str(count+1)+'Class'] = "Insert FARE CLASS HERE"
                Sdata['S'+str(count+1)+'FltType'] = ''
                count +=1
        if count+1<7:
            for i in range(count+1,7):
                Sdata['S'+str(i)+'Sector'] = ''
                Sdata['S'+str(i)+'FltNo'] = ''
                Sdata['S'+str(i)+'Date'] = ''
                Sdata['S'+str(i)+'Class'] = ''
                Sdata['S'+str(i)+'FltType'] = ''
        for pax in booking_data['itemInfos']['AIR']['travellerInfos']:
            NC1Tax = 0
            NC2Tax = 0 
            YQ = 0
            K3 = 0
            ssr_cost = 0
            NC1AddlAmt = 0
            TDS = 0
            GTAX = 0
            base_fare = 0
            ncm = 0
            mf = 0
            mft = 0
            published_fare  = 0
            fare_class_index = 0
            for trip in booking_data['itemInfos']['AIR']['tripInfos']:
                for trip_sI in trip["sI"]:
                    fare_details = [x for x in trip_sI['bI']['tI'] if\
                                    (x['fN'] == pax['fN'] and x['lN'] == pax['lN'] and x['pt'] == pax['pt'])][0]
                    Sdata["S{}Class".format(fare_class_index + 1)] = fare_details.get("fd",{}).get("cB","No Fare Class")
                    fare_class_index +=1
                    if 'YR' in fare_details.get('fd',{}).get('afC',{}).get('TAF',{}):
                        NC2Tax = NC2Tax + fare_details.get('fd',{}).get('afC',{}).get('TAF',{}).get("YR",0)

                    published_fare += fare_details.get('fd',{}).get('fC',{}).get('TF',0)
                    if 'YQ' in fare_details.get('fd',{}).get('afC',{}).get('TAF',{}):
                        YQ = YQ + fare_details.get('fd',{}).get('afC',{}).get('TAF',{}).get('YQ',0)

                    if 'AGST' in fare_details.get('fd',{}).get('afC',{}).get('TAF',{}):
                        K3 = K3 + fare_details.get('fd',{}).get('afC',{}).get('TAF',{}).get('AGST',0)
                    
                    base_fare += fare_details.get('fd',{}).get('fC',{}).get('BF',0)
                    ncm += fare_details.get('fd',{}).get('fC',{}).get('NCM',0)
                    mf += fare_details.get('fd',{}).get('afC',{}).get('TAF',{}).get('MF',0)
                    mft += fare_details.get('fd',{}).get('afC',{}).get('TAF',{}).get('MFT',0)
                    ssr_cost += fare_details.get('fd',{}).get('fC',{}).get('SSRP',0)
                    
            NC1Tax = published_fare - base_fare - YQ - NC2Tax - K3 -mf -mft
            TDS = tax_condition['tds']*(ncm/100)
            GTAX = tax_condition['tax']*(mf/100)
            StdComm = ncm + ncm*tax_condition['tds']/100
            NC1AddlAmt = float(fare_adjustment['markup']) - float(fare_adjustment['cashback'])
            PNR = list(pax.get("pnrDetails",{"no":"N/A"}).values())[0]
            ticket_num_unmodified = list(pax.get("ticketNumberDetails",{"no":''}).values())[0]
            ticket_num = self.manage_ticket_number(ticket_number = ticket_num_unmodified,pnr = PNR)
            data = {
                "XORef": kwargs["display_id"],
                "CustCode": self.org.easy_link_billing_code,
                "suppcode": kwargs["supplier_id"],
                "AirCode": booking_data['itemInfos']['AIR']['tripInfos'][0]['sI'][0]['fD']['aI']['code'],
                "diflg": diflg,
                "PNRAir": PNR,
                "PNRCrs": "",
                "tktRef": self.org.easy_link_account_name,
                "tktNo": ticket_num,
                "tktDt": datetime.fromisoformat(booking_data['order']['createdOn']).strftime('%d/%m/%Y'),
                "tkttype": "C",
                "BasicFare": base_fare,
                "AddlAmt": "0.0000",
                "SuppAddlAmt": "0.0000",
                "NC1Tax": self.convert_to_4_decimal_string(NC1Tax),
                "NC1AddlAmt": self.convert_to_4_decimal_string(NC1AddlAmt),
                "NC2Tax": self.convert_to_4_decimal_string(NC2Tax),
                "NC2AddlAmt": "0.0000",
                "CTax": self.convert_to_4_decimal_string(YQ),
                "CAddlAmt": "0.0000",
                "JNTax": self.convert_to_4_decimal_string(K3),
                "JNAddlAmt": "0.0000",
                "TxnFees": "0.0000",
                "OCTax": "0.0000",
                "StdComm": self.convert_to_4_decimal_string(StdComm),
                "CPInc": "0.0000",
                "NCPInc": "0.0000",
                "PLB": "0.0000", 
                "OR": "0.0000",
                "SrvChrgs": self.convert_to_4_decimal_string(mf), 
                "MGTFee": "0.0000", 
                "CustStdComm": self.convert_to_4_decimal_string(CustStdComm),
                "CustCPInc": "0.0000",
                "CustNCPInc": "0.0000",
                "CustPLB":"0.0000",
                "CustOR": "0.0000",
                "CustSrvChrgs": "0.0000", 
                "CustMGTFee": "0.0000",
                "PercTDS": self.convert_to_4_decimal_string(tax_condition['tds']), 
                "TDS": self.convert_to_4_decimal_string(TDS), 
                "CustPercTDS": self.convert_to_4_decimal_string(tax_condition['tds']),
                "CustTDS": self.convert_to_4_decimal_string(TDS), 
                "sGTAX": "",
                "PercGTAX": self.convert_to_4_decimal_string(tax_condition['tax']), 
                "GTAX": self.convert_to_4_decimal_string(GTAX),
                "sCustGTAX": "",
                "CustPercGTAX": self.convert_to_4_decimal_string(tax_condition['tax']),
                "CustGTAX": self.convert_to_4_decimal_string(GTAX),
                "CustGTAXAdl": "0.0000",
                "SCPercGTAX": "0.0000", 
                "SCGTAX": "0.0000",
                "SCPercSrch": "0.0000",
                "SCSrch": "0.0000",
                "CustSCPercGTAX": "0.0000",
                "CustSCGTAX": "0.0000",
                "CustSCPercSrch": "0.0000",
                "CustSCSrch": "0.0000",
                "credittype": "F",
                "RCFlag":'',
                "ReftktNo":"",
                'Region':'',
                'ReftktDt':'',
                'AirCCNo':'',
                'PaxName': (pax.get('ti',"")+" "+pax.get('fN',"")+" "+ pax.get('lN',"")).replace(".","").strip(),# passenger name
                'Sector':Sectors,
                "CRS":'OH',
                'FareBasis':fare_details.get('fd',{}).get('fB',''),
                'DealCode':'',
                'BillNarration': '',
                'BillNote':'',
                'ReceiptAmt':ReceiptAmt
                }
            final_data = Sdata | data
            easy_link_datas.append(final_data)
        self.airticket_billing(easy_link_datas,kwargs["itinerary"].id,kwargs["display_id"])
        
    def book_failed_tripjack(self,fare_adjustment,tax_condition,search_details,itinerary,
                                                pax_details,booking_details,display_id,
                                                easy_link_billing_code,supplier_id,
                                                easy_link_account_name,booked_at,fare_quote,unified_booking_fare):
        def unify_sector_tripjack(segments):
            Sector = []
            for segment in segments:
                for seg in segment:
                    Sector.append(seg['da']['code'])
                    Sector.append(seg['aa']['code'])
            if len(Sector) >=2:
                result = [Sector[0]]
                for i in range(1, len(Sector)):
                    if Sector[i] != Sector[i - 1]: 
                        result.append(Sector[i])
                sector_output = "/".join(result)
            else:
                sector_output = "/".join(Sector)
            return sector_output

        def find_ssr_cost(pax, itinerary):
            ssr_cost = 0
            ssr_data = pax.get(itinerary,{})
            baggage = ssr_data.get('baggage_ssr',None)
            if baggage:
                for journey in baggage.get('journey',[]):
                    ssr_cost += baggage.get(journey,{}).get('Price',0)
            meals = ssr_data.get('meals_ssr',None)
            if meals:
                for journey in meals.get('journey',[]):
                    ssr_cost += meals.get(journey,{}).get('Price',0)
            seats = ssr_data.get('seats_ssr',None)
            if seats:
                for journey in seats.get('journey',[]):
                    ssr_cost += seats.get(journey,{}).get('Price',0)
            return ssr_cost
        itinerary_dict = itinerary
        itinerary = itinerary.itinerary_key
        fq = fare_quote
        easy_link_datas = []
        diflg = "D" if search_details.get('flight_type') == "DOM" else "I"
        ssr_price = sum([find_ssr_cost(pax, itinerary) for pax in pax_details])
        ReceiptAmt = fq["totalPriceInfo"]["totalFareDetail"].get("fC",{}).get("TF",0) + ssr_price
        if len(fq['tripInfos']) == 1:
            segments = [fq['tripInfos'][0]['sI']]
        else:
            segments = [x['sI'] for x in fq['tripInfos']]
        Sectors = unify_sector_tripjack(segments)
        Sdata = {}
        count = 0
        supplier_publish_fare = unified_booking_fare.get("supplier_publishFare")
        supplier_offer_fare = unified_booking_fare.get("supplier_offerFare")
        new_published_fare_distributor = supplier_publish_fare + (float(fare_adjustment["markup"])-\
                        float(fare_adjustment["cashback"]) )*len(pax_details)
        new_offer_fare_distributor = supplier_publish_fare + (float(fare_adjustment["markup"])  -\
                                fare_adjustment["cashback"])*len(pax_details) -\
                                (supplier_publish_fare - supplier_offer_fare)*(float(fare_adjustment["parting_percentage"])/100)*(1-float(tax_condition["tax"])/100)
        CustStdComm = (new_published_fare_distributor - new_offer_fare_distributor)/len(pax_details)
        CustStdComm = CustStdComm + CustStdComm*tax_condition['tds']/100
        for seg in segments:
            for segment in seg:
                Sdata['S'+str(count+1)+'Sector'] = segment['da']['code']+ "/" + segment['aa']['code']
                Sdata['S'+str(count+1)+'FltNo'] = segment['fD']['aI']['code'] + segment['fD']['fN']
                Sdata['S'+str(count+1)+'Date'] = datetime.fromisoformat(segment['dt']).strftime('%d/%m/%Y') 
                Sdata['S'+str(count+1)+'Class'] = utils.extract_data_recursive(fq,['tripInfos','totalPriceList','fd','ADULT','cB'],'')
                Sdata['S'+str(count+1)+'FltType'] = ''
                count +=1
        if count+1<7:
            for i in range(count+1,7):
                Sdata['S'+str(i)+'Sector'] = ''
                Sdata['S'+str(i)+'FltNo'] = ''
                Sdata['S'+str(i)+'Date'] = ''
                Sdata['S'+str(i)+'Class'] = ''
                Sdata['S'+str(i)+'FltType'] = ''

        pax_map = {'adults':"ADULT",'infant':"INFANT","child":"CHILD"}
            
        for pax in pax_details:
            NC1Tax = 0
            NC2Tax = 0 
            YQ = 0
            K3 = 0
            ssr_cost = 0
            NC1AddlAmt = 0
            TDS = 0
            GTAX = 0
            base_fare = 0
            ncm = 0
            mf = 0
            published_fare  = 0
            for trip in fq['tripInfos']:
                # for trip_sI in trip["sI"]:
                fare_details = utils.extract_data_recursive(trip,['totalPriceList','fd'],{}).get(pax_map.get(pax['type'],{}))
                if 'YR' in fare_details.get('afC',{}).get('TAF',{}):
                    NC2Tax = NC2Tax + fare_details.get('afC',{}).get('TAF',{}).get("YR",0)

                published_fare += fare_details.get('fC',{}).get('TF',0)
                if 'YQ' in fare_details.get('afC',{}).get('TAF',{}):
                    YQ = YQ + fare_details.get('afC',{}).get('TAF',{}).get('YQ',0)

                if 'AGST' in fare_details.get('afC',{}).get('TAF',{}):
                    K3 = K3 + fare_details.get('afC',{}).get('TAF',{}).get('AGST',0)
                
                base_fare += fare_details.get('fC',{}).get('BF',0)
                try:
                    ncm += fare_details.get('afC',{}).get('NCM',{}).get("OT",0)
                except:
                    ncm += fare_details.get('fC',{}).get('NCM',0)
                mf += fare_details.get('afC',{}).get('TAF',{}).get('MF',0)
            
            ssr_cost += find_ssr_cost(pax, itinerary)     
            NC1Tax = published_fare - base_fare - YQ - NC2Tax - K3 + ssr_cost
            TDS = tax_condition['tds']*(ncm/100)
            GTAX = tax_condition['tax']*(mf/100)
            NC1AddlAmt = fare_adjustment['markup'] - fare_adjustment["cashback"]
            StdComm = ncm + ncm*tax_condition['tds']/100
            PNRAir = booking_details.get('airline_pnr','')
            PNRCrs = booking_details.get('gds_pnr','')
            ticket_num = pax.get(itinerary,{}).get("supplier_ticket_number",PNRAir)
            data = {
                "XORef": display_id,
                "CustCode": easy_link_billing_code,
                "suppcode": supplier_id,
                "AirCode": fq['tripInfos'][0]['sI'][0]['fD']['aI']['code'],
                "diflg": diflg,
                "PNRAir": PNRAir,
                "PNRCrs": PNRCrs,
                "tktRef": easy_link_account_name,
                "tktNo": ticket_num,
                "tktDt": datetime.fromtimestamp(booked_at).strftime("%d/%m/%Y"),
                "tkttype": "C",
                "BasicFare": base_fare,
                "AddlAmt": "0.0000",
                "SuppAddlAmt": "0.0000",
                "NC1Tax": convert_to_4_decimal_string(NC1Tax),
                "NC1AddlAmt": convert_to_4_decimal_string(NC1AddlAmt),
                "NC2Tax": convert_to_4_decimal_string(NC2Tax),
                "NC2AddlAmt": "0.0000",
                "CTax": convert_to_4_decimal_string(YQ),
                "CAddlAmt": "0.0000",
                "JNTax": convert_to_4_decimal_string(K3),
                "JNAddlAmt": "0.0000",
                "TxnFees": "0.0000",
                "OCTax": "0.0000",
                "StdComm": convert_to_4_decimal_string(StdComm),
                "CPInc": "0.0000",
                "NCPInc": "0.0000",
                "PLB": convert_to_4_decimal_string(ncm), 
                "OR": "0.0000",
                "SrvChrgs": convert_to_4_decimal_string(mf), 
                "MGTFee": "0.0000", 
                "CustStdComm": convert_to_4_decimal_string(CustStdComm),
                "CustCPInc": "0.0000",
                "CustNCPInc": "0.0000",
                "CustPLB": convert_to_4_decimal_string(ncm),
                "CustOR": "0.0000",
                "CustSrvChrgs": convert_to_4_decimal_string(mf), 
                "CustMGTFee": "0.0000",
                "PercTDS": convert_to_4_decimal_string(tax_condition['tds']), 
                "TDS": convert_to_4_decimal_string(TDS), 
                "CustPercTDS": convert_to_4_decimal_string(tax_condition['tds']),
                "CustTDS": convert_to_4_decimal_string(TDS), 
                "sGTAX": "",
                "PercGTAX": convert_to_4_decimal_string(tax_condition['tax']), 
                "GTAX": convert_to_4_decimal_string(GTAX),
                "sCustGTAX": "",
                "CustPercGTAX": convert_to_4_decimal_string(tax_condition['tax']),
                "CustGTAX": convert_to_4_decimal_string(GTAX),
                "CustGTAXAdl": "0.0000",
                "SCPercGTAX": "0.0000", 
                "SCGTAX": "0.0000",
                "SCPercSrch": "0.0000",
                "SCSrch": "0.0000",
                "CustSCPercGTAX": "0.0000",
                "CustSCGTAX": "0.0000",
                "CustSCPercSrch": "0.0000",
                "CustSCSrch": "0.0000",
                "credittype": "F",
                "RCFlag":'',
                "ReftktNo":"",
                'Region':'',
                'ReftktDt':'',
                'AirCCNo':'',
                'PaxName': (pax.get('title',"")+" "+pax.get('firstName',"")+" "+ pax.get('lastName',"")).replace(".","").strip(),
                'Sector':Sectors,
                "CRS":'OH',
                'FareBasis':fare_details.get('fd',{}).get('fB',''),
                'DealCode':'',
                'BillNarration': '',
                'BillNote':'',
                'ReceiptAmt':ReceiptAmt
                }
            final_data = Sdata | data
            easy_link_datas.append(final_data)
        self.airticket_billing(easy_link_datas,itinerary_dict.id)


    def book_failed_tbo(self,fare_adjustment,tax_condition,search_details,itinerary,
                                                pax_details,booking_details,display_id,
                                                easy_link_billing_code,supplier_id,
                                                easy_link_account_name,booked_at,fare_quote,segments,
                                                unified_booking_fare):
        def unify_sector_tbo(segments,itinerary):
            Sector = []
            if '_R_' not in itinerary: 
                for segment in segments:
                    Sector.append(segment['departure']['airportCode'])
                    Sector.append(segment['arrival']['airportCode'])
            else:
                for segment in segments:
                    for seg in segment:
                        Sector.append(seg['departure']['airportCode'])
                        Sector.append(seg['arrival']['airportCode'])
            if len(Sector) >=2:
                result = [Sector[0]]
                for i in range(1, len(Sector)):
                    if Sector[i] != Sector[i - 1]: 
                        result.append(Sector[i])
                sector_output = "/".join(result)
            else:
                sector_output = "/".join(Sector)
            return sector_output

        def find_ssr_cost(pax, itinerary):
            ssr_cost = 0
            ssr_data = pax.get(itinerary,{})
            baggage = ssr_data.get('baggage_ssr',None)
            if baggage:
                for journey in baggage.get('journey',[]):
                    ssr_cost += baggage.get(journey,{}).get('Price',0)
            meals = ssr_data.get('meals_ssr',None)
            if meals:
                for journey in meals.get('journey',[]):
                    ssr_cost += meals.get(journey,{}).get('Price',0)
            seats = ssr_data.get('seats_ssr',None)
            if seats:
                for journey in seats.get('journey',[]):
                    ssr_cost += seats.get(journey,{}).get('Price',0)
            return ssr_cost
        itinerary_dict = itinerary
        itinerary = itinerary.itinerary_key
        fq = fare_quote
        segments = segments
        if '_R_' not in itinerary:
            f_segments = segments[itinerary]
        else:
            f_segments = []
            for it in itinerary.split('_R_'):
                f_segments.append(segments[it])

        Sectors = unify_sector_tbo(f_segments,itinerary)
        ReceiptAmt = fq.get('Response',{}).get('Results',{}).get('Fare',{}).get('PublishedFare',0)
        ReceiptAmt += sum([find_ssr_cost(pax, itinerary) for pax in pax_details])
        supplier_publish_fare = unified_booking_fare.get("supplier_publishFare")
        supplier_offer_fare = unified_booking_fare.get("supplier_offerFare")
        new_published_fare_distributor = supplier_publish_fare + (float(fare_adjustment["markup"])-\
                        float(fare_adjustment["cashback"]) )*len(pax_details)
        new_offer_fare_distributor = supplier_publish_fare + (float(fare_adjustment["markup"])  -\
                                fare_adjustment["cashback"])*len(pax_details) -\
                                (supplier_publish_fare - supplier_offer_fare)*(float(fare_adjustment["parting_percentage"])/100)*(1-float(tax_condition["tax"])/100)
        CustStdComm = (new_published_fare_distributor - new_offer_fare_distributor)/len(pax_details)
        CustStdComm = CustStdComm + CustStdComm*tax_condition['tds']/100
        StdComm = (supplier_publish_fare- supplier_offer_fare)/len(pax_details)
        StdComm = StdComm + StdComm*tax_condition['tds']/100  
        if search_details.get("flight_type") == "DOM":
            diflg = "D"
        else:
            diflg = "I"

        Sdata = {}
        if '_R_' not in itinerary: 
            for idx,segment in enumerate(segments[itinerary]):
                Sdata['S'+str(idx+1)+'Sector'] = segment['departure']['airportCode']+ "/" + segment['arrival']['airportCode']
                Sdata['S'+str(idx+1)+'FltNo'] = segment['airlineCode'] + segment['flightNumber']
                Sdata['S'+str(idx+1)+'Date'] = datetime.fromisoformat(segment['departure']['departureDatetime']).strftime('%d/%m/%Y')
                Sdata['S'+str(idx+1)+'Class'] = utils.extract_data_recursive(fq,['Response','Results','Segments','Airline','FareClass'],'')
                Sdata['S'+str(idx+1)+'FltType'] = ''
        else:
            idx = 0
            for segment in f_segments:
                for seg in segment:
                    Sdata['S'+str(idx+1)+'Sector'] = seg['departure']['airportCode']+ "/" + seg['arrival']['airportCode']
                    Sdata['S'+str(idx+1)+'FltNo'] = seg['airlineCode'] + seg['flightNumber']
                    Sdata['S'+str(idx+1)+'Date'] = datetime.fromisoformat(seg['departure']['departureDatetime']).strftime('%d/%m/%Y')
                    Sdata['S'+str(idx+1)+'Class'] = utils.extract_data_recursive(fq,['Response','Results','Segments','Airline','FareClass'],'')
                    Sdata['S'+str(idx+1)+'FltType'] = ''
                    idx +=1
        if idx+1<7:
            for i in range(idx+1,7):
                Sdata['S'+str(i)+'Sector'] = ''
                Sdata['S'+str(i)+'FltNo'] = ''
                Sdata['S'+str(i)+'Date'] = ''
                Sdata['S'+str(i)+'Class'] = ''
                Sdata['S'+str(i)+'FltType'] = ''

        final_result = []
        easy_link_datas = []
        pax_type_map = {"adults":1,"child":2,"children":2,"infants":3,"infant":3}
        for pax in pax_details:
            fare_details = [x for x in fq.get('Response',{}).get('Results',{}).get('FareBreakdown',[]) if x.get('PassengerType','1') == pax_type_map[pax['type']]][0]
            passenger_type_count = fare_details["PassengerCount"]
            if fare_details.get('TaxBreakUp',[]) == None:
                fare_details['TaxBreakUp'] = []
            NC2Tax = [tb.get('value',0) for tb in fare_details.get('TaxBreakUp',[]) if tb['key'] == 'YR']
            if len(NC2Tax)>0:
                NC2Tax = NC2Tax[0]/passenger_type_count
            else:
                NC2Tax = 0
            published_fare = (fare_details.get('BaseFare',0) + fare_details.get('Tax'))/passenger_type_count
            NC1Tax = published_fare - (fare_details.get('BaseFare',0)+fare_details.get('YQTax',0))/passenger_type_count- \
                sum([float(x['value']) for x in fare_details.get('TaxBreakUp',[]) if x['key'] in ['K3','YR']])/passenger_type_count + \
                    find_ssr_cost(pax, itinerary)
            NC1AddlAmt = fare_adjustment['markup']  - fare_adjustment['cashback']
            K3 = [float(x['value']) for x in fare_details.get('TaxBreakUp',[]) if x['key'] == 'K3']
            if len(K3)>0:
                K3 = K3[0]/passenger_type_count
            else:
                K3 = 0
            TBOMARKUP = [float(x['value']) for x in fare_details.get('ChargeBU',[]) if x['key'] == 'TBOMARKUP']
            if len(TBOMARKUP)>0:
                TBOMARKUP = TBOMARKUP[0]/passenger_type_count
            else:
                TBOMARKUP = 0
            TDS = tax_condition['tds'] * ((fare_details.get('CommissionEarned', 0) + fare_details.get('PLBEarned', 0))/passenger_type_count)/100
            GTAX = GTAX = tax_condition['tax'] * (fare_details.get('ServiceFee', 0)/passenger_type_count)/100
            PNRAir = booking_details.get('airline_pnr','')
            PNRCrs = booking_details.get('gds_pnr','')
            ticket_num = pax.get(itinerary,{}).get("supplier_ticket_number",PNRAir)
            BasicFare = fare_details.get('BaseFare',0)/passenger_type_count
            data = {
                "XORef": display_id,
                "CustCode": easy_link_billing_code,
                "suppcode": supplier_id,
                "AirCode": utils.extract_data_recursive(fq,['Response','Results','ValidatingAirline'],''),
                "diflg": diflg,
                "PNRAir": PNRAir,
                "PNRCrs": PNRCrs,
                "tktRef": easy_link_account_name,
                "tktNo": ticket_num,
                "tktDt":  datetime.fromtimestamp(booked_at).strftime("%d/%m/%Y"),
                "tkttype": "C",
                "BasicFare": convert_to_4_decimal_string(BasicFare),
                "AddlAmt": "0.0000",
                "SuppAddlAmt": "0.0000",
                "NC1Tax": convert_to_4_decimal_string(NC1Tax),
                "NC1AddlAmt": convert_to_4_decimal_string(NC1AddlAmt),
                "NC2Tax": convert_to_4_decimal_string(NC2Tax),
                "NC2AddlAmt": "0.0000",
                "CTax": convert_to_4_decimal_string(fare_details.get('YQTax',0)),
                "CAddlAmt": "0.0000",
                "JNTax": convert_to_4_decimal_string(K3),
                "JNAddlAmt": "0.0000",
                "TxnFees": "0.0000",
                "OCTax": "0.0000",
                "StdComm": convert_to_4_decimal_string(StdComm), 
                "CPInc": "0.0000",
                "NCPInc": "0.0000",
                "PLB": "0.0000",
                "OR": "0.0000",
                "SrvChrgs": convert_to_4_decimal_string(fare_details.get('ServiceFee',0)),
                "MGTFee": convert_to_4_decimal_string(TBOMARKUP), 
                "CustStdComm": convert_to_4_decimal_string(CustStdComm),
                "CustCPInc": "0.0000",
                "CustNCPInc": "0.0000",
                "CustPLB": "0.0000",
                "CustOR": "0.0000",
                "CustSrvChrgs": convert_to_4_decimal_string(fare_details.get('ServiceFee',0)), 
                "CustMGTFee": convert_to_4_decimal_string(TBOMARKUP), 
                "PercTDS": convert_to_4_decimal_string(tax_condition['tds']), 
                "TDS": convert_to_4_decimal_string(TDS), 
                "CustPercTDS": convert_to_4_decimal_string(tax_condition['tds']),
                "CustTDS": convert_to_4_decimal_string(TDS), 
                "sGTAX": "",
                "PercGTAX": convert_to_4_decimal_string(tax_condition['tax']), 
                "GTAX": convert_to_4_decimal_string(GTAX),
                "sCustGTAX": "",
                "CustPercGTAX": convert_to_4_decimal_string(tax_condition['tax']),
                "CustGTAX": convert_to_4_decimal_string(GTAX),
                "CustGTAXAdl": "0.0000",
                "SCPercGTAX": "0.0000", 
                "SCGTAX": "0.0000",
                "SCPercSrch": "0.0000",
                "SCSrch": "0.0000",
                "CustSCPercGTAX": "0.0000",
                "CustSCGTAX": "0.0000",
                "CustSCPercSrch": "0.0000",
                "CustSCSrch": "0.0000",
                "credittype": "F",
                "RCFlag":'',
                "ReftktNo":"",
                'Region':'',
                'ReftktDt':'',
                'AirCCNo':'',
                'PaxName': (pax.get('title',"")+" "+pax.get('firstName',"")+" "+ pax.get('lastName',"")).replace(".","").strip(),
                'Sector':Sectors,
                "CRS":'OH',
                'FareBasis':utils.extract_data_recursive(fq,['Response','Results','FareRules','FareBasisCode'],''),
                'DealCode':'',
                'BillNarration': '',
                'BillNote':'',
                'ReceiptAmt':ReceiptAmt
                }
            
            final_data = Sdata | data
            final_result.append(final_data)
            easy_link_datas.append(final_data)
        self.airticket_billing(easy_link_datas,itinerary_dict.id)

    def book_failed_stt_common(self,fare_adjustment,tax_condition,search_details,itinerary,
                                                pax_details,booking_details,display_id,
                                                easy_link_billing_code,supplier_id,
                                                easy_link_account_name,booked_at,fare_quote,unified_booking_fare):
        def unify_sector_stt(segments):
            Sector = []
            for segment in segments:
                for seg in segment:
                    Sector.append(seg['Origin'])
                    Sector.append(seg['Destination'])
            if len(Sector) >=2:
                result = [Sector[0]]
                for i in range(1, len(Sector)):
                    if Sector[i] != Sector[i - 1]: 
                        result.append(Sector[i])
                sector_output = "/".join(result)
            else:
                sector_output = "/".join(Sector)
            return sector_output

        def find_ssr_cost(pax, itinerary):
            ssr_cost = 0
            ssr_data = pax.get(itinerary,{})
            baggage = ssr_data.get('baggage_ssr',None)
            if baggage:
                for journey in baggage.get('journey',[]):
                    ssr_cost += baggage.get(journey,{}).get('Price',0)
            meals = ssr_data.get('meals_ssr',None)
            if meals:
                for journey in meals.get('journey',[]):
                    ssr_cost += meals.get(journey,{}).get('Price',0)
            seats = ssr_data.get('seats_ssr',None)
            if seats:
                for journey in seats.get('journey',[]):
                    ssr_cost += seats.get(journey,{}).get('Price',0)
            return ssr_cost
        itinerary_dict = itinerary
        itinerary = itinerary.itinerary_key
        fq = fare_quote
        easy_link_datas = []
        diflg = "D" if search_details.get('flight_type') == "DOM" else "I"
        ReceiptAmt = 0
        segments = [fq["AirRepriceResponses"][0]["Flight"]['Segments']]
        Sectors = unify_sector_stt(segments)
        Sdata = {}
        count = 0
        supplier_publish_fare = unified_booking_fare.get("supplier_publishFare")
        supplier_offer_fare = unified_booking_fare.get("supplier_offerFare")
        new_published_fare_distributor = supplier_publish_fare + (float(fare_adjustment["markup"])-\
                        float(fare_adjustment["cashback"]) )*len(pax_details)
        new_offer_fare_distributor = supplier_publish_fare + (float(fare_adjustment["markup"])  -\
                                fare_adjustment["cashback"])*len(pax_details) -\
                                (supplier_publish_fare - supplier_offer_fare)*(float(fare_adjustment["parting_percentage"])/100)*(1-float(tax_condition["tax"])/100)
        CustStdComm = (new_published_fare_distributor - new_offer_fare_distributor)/len(pax_details)
        CustStdComm = CustStdComm + CustStdComm*tax_condition['tds']/100
        for seg in segments:
            for segment in seg:
                Sdata['S'+str(count+1)+'Sector'] = segment['Origin']+ "/" + segment['Destination']
                Sdata['S'+str(count+1)+'FltNo'] = segment['Airline_Code'] + segment['Flight_Number']
                Sdata['S'+str(count+1)+'Date'] = datetime.strptime(segment['Departure_DateTime'], "%m/%d/%Y %H:%M").strftime("%d/%m/%Y") 
                Sdata['S'+str(count+1)+'Class'] = ""
                Sdata['S'+str(count+1)+'FltType'] = ''
                count +=1

        if count+1<7:
            for i in range(count+1,7):
                Sdata['S'+str(i)+'Sector'] = ''
                Sdata['S'+str(i)+'FltNo'] = ''
                Sdata['S'+str(i)+'Date'] = ''
                Sdata['S'+str(i)+'Class'] = ''
                Sdata['S'+str(i)+'FltType'] = ''
        for pax in pax_details:
            if "adult" in pax["type"]:
                pax_type = 0
            elif "child" in pax["type"]:
                pax_type = 1
            else:
                pax_type = 2
            NC1Tax = 0
            NC2Tax = 0 
            YQ = 0
            ssr_cost = 0
            NC1AddlAmt = 0
            TDS = 0
            GTAX = 0
            base_fare = 0
            ncm = 0
            published_fare  = 0
            TDS = 0
            GTAX = 0
            for Fare in fare_quote["AirRepriceResponses"][0]["Flight"]["Fares"]:
                fare_details = [fare for fare in Fare["FareDetails"] if fare["PAX_Type"] ==pax_type ][0]
                published_fare += fare_details.get('Total_Amount',0)
                YQ = YQ + fare_details.get('YQ_Amount',0)    
                base_fare += fare_details.get('Basic_Amount',0)
                ReceiptAmt += published_fare
                ncm += fare_details.get('Net_Commission',0)
                TDS = TDS + fare_details.get('TDS',0)
            ssr_cost += find_ssr_cost(pax, itinerary)
            NC1Tax = published_fare - base_fare - YQ 
            StdComm = ncm + ncm*tax_condition['tds']/100
            NC1AddlAmt = float(fare_adjustment['markup']) - float(fare_adjustment['cashback']) + ssr_cost
            PNRAir = booking_details.get('airline_pnr','')
            PNRCrs = booking_details.get('gds_pnr','')
            ticket_num = pax.get(itinerary,{}).get("supplier_ticket_number",PNRAir)
            data = {
                "XORef": display_id,
                "CustCode": easy_link_billing_code,
                "suppcode": supplier_id,
                "AirCode": "",
                "diflg": diflg,
                "PNRAir": PNRAir,
                "PNRCrs": PNRCrs,
                "tktRef": easy_link_account_name,
                "tktNo": ticket_num,
                "tktDt": datetime.fromtimestamp(booked_at).strftime("%d/%m/%Y"),
                "tkttype": "C",
                "BasicFare": base_fare,
                "AddlAmt": "0.0000",
                "SuppAddlAmt": "0.0000",
                "NC1Tax": self.convert_to_4_decimal_string(NC1Tax),
                "NC1AddlAmt": self.convert_to_4_decimal_string(NC1AddlAmt),
                "NC2Tax": self.convert_to_4_decimal_string(NC2Tax),
                "NC2AddlAmt": "0.0000",
                "CTax": self.convert_to_4_decimal_string(YQ),
                "CAddlAmt": "0.0000",
                "JNTax": "0.0000",
                "JNAddlAmt": "0.0000",
                "TxnFees": "0.0000",
                "OCTax": "0.0000",
                "StdComm": self.convert_to_4_decimal_string(StdComm),
                "CPInc": "0.0000",
                "NCPInc": "0.0000",
                "PLB": "0.0000", 
                "OR": "0.0000",
                "SrvChrgs": "0.0000", 
                "MGTFee": "0.0000", 
                "CustStdComm": self.convert_to_4_decimal_string(CustStdComm),
                "CustCPInc": "0.0000",
                "CustNCPInc": "0.0000",
                "CustPLB":"0.0000",
                "CustOR": "0.0000",
                "CustSrvChrgs": "0.0000", 
                "CustMGTFee": "0.0000",
                "PercTDS": self.convert_to_4_decimal_string(tax_condition['tds']), 
                "TDS": self.convert_to_4_decimal_string(TDS), 
                "CustPercTDS": self.convert_to_4_decimal_string(tax_condition['tds']),
                "CustTDS": self.convert_to_4_decimal_string(TDS), 
                "sGTAX": "",
                "PercGTAX": self.convert_to_4_decimal_string(tax_condition['tax']), 
                "GTAX": self.convert_to_4_decimal_string(GTAX),
                "sCustGTAX": "",
                "CustPercGTAX": self.convert_to_4_decimal_string(tax_condition['tax']),
                "CustGTAX": "0.0000",
                "CustGTAXAdl": "0.0000",
                "SCPercGTAX": "0.0000", 
                "SCGTAX": "0.0000",
                "SCPercSrch": "0.0000",
                "SCSrch": "0.0000",
                "CustSCPercGTAX": "0.0000",
                "CustSCGTAX": "0.0000",
                "CustSCPercSrch": "0.0000",
                "CustSCSrch": "0.0000",
                "credittype": "F",
                "RCFlag":'',
                "ReftktNo":"",
                'Region':'',
                'ReftktDt':'',
                'AirCCNo':'',
                'PaxName': (pax.get('title',"")+" "+pax.get('firstName',"")+" "+ pax.get('lastName',"")).replace(".","").strip(),
                'Sector':Sectors,
                "CRS":'OH',
                'FareBasis':"",
                'DealCode':'',
                'BillNarration': '',
                'BillNote':'',
                'ReceiptAmt':ReceiptAmt 
                }
            final_data = Sdata | data
            easy_link_datas.append(final_data)
        self.airticket_billing(easy_link_datas,itinerary_dict.id)


    def book_stt_common(self,**kwargs):

        def unify_sector_stt(segments):
            Sector = []
            for segment in segments:
                for seg in segment:
                    Sector.append(re.findall(r"\((.*?)\)", seg['Origin'])[0])
                    Sector.append(re.findall(r"\((.*?)\)", seg['Destination'])[0])
            if len(Sector) >=2:
                result = [Sector[0]]
                for i in range(1, len(Sector)):
                    if Sector[i] != Sector[i - 1]: 
                        result.append(Sector[i])
                sector_output = "/".join(result)
            else:
                sector_output = "/".join(Sector)
            return sector_output
        
        easy_link_datas = []
        search_details = kwargs["itinerary"].booking.search_details
        fare_details = utils.get_fare_markup(self.user)
        fare_adjustment,tax_condition= utils.set_fare_details(fare_details)
        diflg = "D" if search_details.flight_type == "DOM" else "I"
        booking_data = kwargs["booking_data"]
        ReceiptAmt = booking_data["AirPNRDetails"][0].get("Gross_Amount",0)
        if len(booking_data["AirPNRDetails"][0]["Flights"]) == 1:
            segments = [booking_data["AirPNRDetails"][0]["Flights"][0]["Segments"]]
        else:
            segments = [x['Segments'] for x in booking_data["AirPNRDetails"][0]["Flights"]]
        Sectors = unify_sector_stt(segments)
        Sdata = {}
        count = 0
        payment_details = kwargs["payment_details"]
        supplier_publish_fare = payment_details.get("supplier_published_fare")
        supplier_offer_fare = payment_details.get("supplier_offered_fare")
        new_published_fare_distributor = supplier_publish_fare + (float(fare_adjustment["markup"])-\
                        float(fare_adjustment["cashback"]) )*kwargs["pax_length"]
        new_offer_fare_distributor = supplier_publish_fare + (float(fare_adjustment["markup"])  -\
                                fare_adjustment["cashback"])*kwargs["pax_length"] -\
                                (supplier_publish_fare - supplier_offer_fare)*(float(fare_adjustment["parting_percentage"])/100)*(1-float(tax_condition["tax"])/100)
        CustStdComm = (new_published_fare_distributor - new_offer_fare_distributor)/kwargs["pax_length"]
        CustStdComm = CustStdComm + CustStdComm*tax_condition['tds']/100
        AirCode = booking_data["AirPNRDetails"][0]["Airline_Code"]
        for seg in segments:
            for segment in seg:
                Sdata['S'+str(count+1)+'Sector'] = re.findall(r"\((.*?)\)", segment['Origin'])[0]+ "/" + re.findall(r"\((.*?)\)", segment['Destination'])[0]
                Sdata['S'+str(count+1)+'FltNo'] = segment['Airline_Code'] + segment['Flight_Number']
                Sdata['S'+str(count+1)+'Date'] = datetime.strptime(segment['Departure_DateTime'], "%m/%d/%Y %H:%M:%S").strftime("%d/%m/%Y") 
                Sdata['S'+str(count+1)+'Class'] = ""
                Sdata['S'+str(count+1)+'FltType'] = ''
                count +=1

        if count+1<7:
            for i in range(count+1,7):
                Sdata['S'+str(i)+'Sector'] = ''
                Sdata['S'+str(i)+'FltNo'] = ''
                Sdata['S'+str(i)+'Date'] = ''
                Sdata['S'+str(i)+'Class'] = ''
                Sdata['S'+str(i)+'FltType'] = ''

        for pax in booking_data["AirPNRDetails"][0]["PAXTicketDetails"]:
            NC1Tax = 0
            NC2Tax = 0 
            YQ = 0
            ssr_cost = 0
            NC1AddlAmt = 0
            TDS = 0
            GTAX = 0
            base_fare = 0
            ncm = 0
            published_fare  = 0
            TDS = 0
            GTAX = 0
            for Fare in pax["Fares"]:
                for fare_details in Fare["FareDetails"]:
                    published_fare += fare_details.get('Total_Amount',0)
                    YQ = YQ + fare_details.get('YQ_Amount',0)    
                    base_fare += fare_details.get('Basic_Amount',0)
                    ncm += fare_details.get('Net_Commission',0)
                    for ssr in pax["SSRDetails"]:
                        ssr_cost += ssr["Total_Amount"]
                    TDS = TDS + fare_details.get('TDS',0)
            NC1Tax = published_fare - base_fare - YQ
            StdComm = ncm + ncm*tax_condition['tds']/100
            NC1AddlAmt = float(fare_adjustment['markup']) - float(fare_adjustment['cashback']) 
            PNR = booking_data["AirPNRDetails"][0]["Airline_PNR"]
            ticket_num = pax["TicketDetails"][0]["Ticket_Number"]
            data = {
                "XORef": kwargs["display_id"],
                "CustCode": self.org.easy_link_billing_code,
                "suppcode": kwargs["supplier_id"],
                "AirCode": AirCode,
                "diflg": diflg,
                "PNRAir": PNR,
                "PNRCrs": "",
                "tktRef": self.org.easy_link_account_name,
                "tktNo": ticket_num,
                "tktDt": datetime.strptime(booking_data['Booking_DateTime'], "%d/%m/%Y %H:%M:%S").strftime("%d/%m/%Y") ,
                "tkttype": "C",
                "BasicFare": base_fare,
                "AddlAmt": "0.0000",
                "SuppAddlAmt": "0.0000",
                "NC1Tax": self.convert_to_4_decimal_string(NC1Tax),
                "NC1AddlAmt": self.convert_to_4_decimal_string(NC1AddlAmt),
                "NC2Tax": self.convert_to_4_decimal_string(NC2Tax),
                "NC2AddlAmt": "0.0000",
                "CTax": self.convert_to_4_decimal_string(YQ),
                "CAddlAmt": "0.0000",
                "JNTax": "0.0000",
                "JNAddlAmt": "0.0000",
                "TxnFees": "0.0000",
                "OCTax": "0.0000",
                "StdComm": self.convert_to_4_decimal_string(StdComm),
                "CPInc": "0.0000",
                "NCPInc": "0.0000",
                "PLB": "0.0000", 
                "OR": "0.0000",
                "SrvChrgs": "0.0000", 
                "MGTFee": "0.0000", 
                "CustStdComm": self.convert_to_4_decimal_string(CustStdComm),
                "CustCPInc": "0.0000",
                "CustNCPInc": "0.0000",
                "CustPLB":"0.0000",
                "CustOR": "0.0000",
                "CustSrvChrgs": "0.0000", 
                "CustMGTFee": "0.0000",
                "PercTDS": self.convert_to_4_decimal_string(tax_condition['tds']), 
                "TDS": self.convert_to_4_decimal_string(TDS), 
                "CustPercTDS": self.convert_to_4_decimal_string(tax_condition['tds']),
                "CustTDS": self.convert_to_4_decimal_string(TDS), 
                "sGTAX": "",
                "PercGTAX": self.convert_to_4_decimal_string(tax_condition['tax']), 
                "GTAX": self.convert_to_4_decimal_string(GTAX),
                "sCustGTAX": "",
                "CustPercGTAX": self.convert_to_4_decimal_string(tax_condition['tax']),
                "CustGTAX": "0.0000",
                "CustGTAXAdl": "0.0000",
                "SCPercGTAX": "0.0000", 
                "SCGTAX": "0.0000",
                "SCPercSrch": "0.0000",
                "SCSrch": "0.0000",
                "CustSCPercGTAX": "0.0000",
                "CustSCGTAX": "0.0000",
                "CustSCPercSrch": "0.0000",
                "CustSCSrch": "0.0000",
                "credittype": "F",
                "RCFlag":'',
                "ReftktNo":"",
                'Region':'',
                'ReftktDt':'',
                'AirCCNo':'',
                'PaxName': (pax.get('ti',"")+" "+pax.get('First_Name',"")+" "+ pax.get('Last_Name',"")).replace(".","").strip(),
                'Sector':Sectors,
                "CRS":'OH',
                'FareBasis':"",
                'DealCode':'',
                'BillNarration': '',
                'BillNote':'',
                'ReceiptAmt':ReceiptAmt
                }
            final_data = Sdata | data
            easy_link_datas.append(final_data)
        self.airticket_billing(easy_link_datas,kwargs["itinerary"].id,kwargs["display_id"])

    def create_offline_billing(self,data,pnr_doc,discount_per_pax = 0,is_online = False):
        retpnr_response = pnr_doc
        create_bill_response = data
        airline_pnr = create_bill_response["airline_pnr"]
        ticketing_date = create_bill_response["ticketing_date"]
        trip_type = 'DOM'
        def unify_sector_offline(segments):
            Sector = []
            for segment in segments:
                Sector.append(segment['departure']['airportCode'])
                Sector.append(segment['arrival']['airportCode'])
            if len(Sector) >=2:
                result = [Sector[0]]
                for i in range(1, len(Sector)):
                    if Sector[i] != Sector[i - 1]:
                        result.append(Sector[i])
                sector_output = "/".join(result)
            else:
                sector_output = "/".join(Sector)
            return sector_output
        if trip_type == "DOM":
            diflg = "D"
        else:
            diflg = "I"
        segments = retpnr_response['flightSegments']
        Sectors = unify_sector_offline(segments)
        fare_details = utils.get_fare_markup(self.user)
        fare_adjustment,tax_condition= utils.set_fare_details(fare_details)
        Sdata = {}
        for idx,segment in enumerate(segments):
            Sdata['S'+str(idx+1)+'Sector'] = segment['departure']['airportCode']+ "/" + segment['arrival']['airportCode']
            Sdata['S'+str(idx+1)+'FltNo'] = segment['flightNumber']
            Sdata['S'+str(idx+1)+'Date'] = datetime.fromisoformat(segment['departure']['departureDatetime']).strftime('%d/%m/%Y')
            Sdata['S'+str(idx+1)+'Class'] = segment['cabinClass']
            Sdata['S'+str(idx+1)+'FltType'] = ''
        if idx+2<7:
            for i in range(idx+2,7):
                Sdata['S'+str(i)+'Sector'] = ''
                Sdata['S'+str(i)+'FltNo'] = ''
                Sdata['S'+str(i)+'Date'] = ''
                Sdata['S'+str(i)+'Class'] = ''
                Sdata['S'+str(i)+'FltType'] = ''
        def reduce_to_unique_number(input_string):
            # Remove "OFFLINE-" prefix
            stripped_string = input_string.replace("OFFLINE-", "")
            # Hash the stripped string using MD5 (or any hash function) and take the first 8 characters of the hex digest
            hashed = hashlib.md5(stripped_string.encode()).hexdigest()[:8]
            # Convert the hash to an integer and return as an 8-digit number
            return int(hashed, 16) % 10**8
        # Example usage
        input_string = create_bill_response['booking_id']
        AirCCNo = create_bill_response.get("fop").get("card","")
        if AirCCNo:
            AirCCNo = LookupCreditCard.objects.filter(id = AirCCNo).first().card_number
        unique_number = reduce_to_unique_number(input_string)
        final_result = []
        for pax in retpnr_response['pax_details']:
            pax_ticket_numbers = pax.get("ticketNumber","").split(",")
            for pax_duplicate,pax_tktno in enumerate(pax_ticket_numbers):
                if pax_duplicate == 0:
                    RCFlag = ""
                    fareDetails = [x for x in retpnr_response['fareDetails']['fareBreakdown'] if x['passengerType'] == pax['pax_type'] ][0]
                    NC2Tax = fareDetails['YR']
                    published_fare = fareDetails['totalFare']
                    NC1Tax = published_fare - fareDetails['baseFare'] - fareDetails['YQ'] - fareDetails['K3'] - fareDetails['YR'] # + SSR cost per pax
                    NC1AddlAmt = fare_adjustment['markup'] + float(create_bill_response['customer_end']['addamt'])
                    K3 = fareDetails['K3']
                    sup_PLB = (fareDetails['baseFare']*float(create_bill_response['supplier_end']['basic'])/100+
                            fareDetails['YQ']*float(create_bill_response['supplier_end']['yq'])/100+
                            fareDetails['YR']*float(create_bill_response['supplier_end']['yr'])/100+
                            fareDetails['baseFare']*float(create_bill_response['supplier_end']['iata'])/100)*(1-(tax_condition['tax']/100))
                    cust_PLB = (fareDetails['baseFare']*float(create_bill_response['customer_end']['basic'])/100+
                            fareDetails['YQ']*float(create_bill_response['customer_end']['yq'])/100+
                            fareDetails['YR']*float(create_bill_response['customer_end']['yr'])/100+
                            fareDetails['baseFare']*float(create_bill_response['customer_end']['iata'])/100)*(1-(tax_condition['tax']/100))
                    cust_TDS = tax_condition['tds']*cust_PLB/100 # tds * customer PLB
                    supp_TDS = tax_condition['tds']*sup_PLB/100
                    GTAX = float(create_bill_response['supplier_end']['sfee'])*tax_condition['tax']/100 # supplier service charge from new supplier deal
                else:
                    RCFlag = "C"
                    NC2Tax = published_fare = NC1Tax = NC1AddlAmt = sup_PLB = cust_PLB = cust_TDS = supp_TDS = GTAX = 0
                try:
                    supplier_code = LookupEasyLinkSupplier.objects.filter(id  = create_bill_response.get("supplier_end").get("supplier")).first().supplier_id
                except:
                    supplier_code = create_bill_response.get("supplier_end").get("supplier")
                
                if is_online:
                    CustStdComm = discount_per_pax
                    CustStdComm = CustStdComm + CustStdComm*tax_condition['tds']/100
                else:
                    CustStdComm = '0'
                
                
                Org = Organization.objects.filter(id = create_bill_response.get("supplier_end").get("agency_id")).first()
                self.easy_link = Org.easy_link_billing_account
                data = self.easy_link.data[0]
                self.base_url = data.get("url")
                self.branch_code = data.get("branch_code")
                self.portal_reference_code = data.get("portal_reference_code")               
                try:
                    tktno = pax_tktno.split('-')[1]
                    crs = "AM"
                except:
                    tktno = pax_tktno[3:]
                    crs = "GA"
                data = {
                "XORef": unique_number,
                "CustCode": Org.easy_link_billing_code,
                "suppcode": supplier_code,
                "AirCode": retpnr_response['flightSegments'][0]['airlineCode'],
                "diflg": diflg,
                "PNRAir": airline_pnr.split(",")[0].strip(),
                "PNRCrs": retpnr_response['gds_pnr'],
                "tktRef": Org.easy_link_account_name,
                "tktNo": tktno,
                "tktDt": datetime.fromisoformat(ticketing_date).strftime('%d/%m/%Y'),
                "tkttype": "C",
                "BasicFare": self.convert_to_4_decimal_string(fareDetails['baseFare']) if not RCFlag else "0.0000",
                "AddlAmt": "0.0000",
                "SuppAddlAmt": "0.0000",
                "NC1Tax": self.convert_to_4_decimal_string(NC1Tax),
                "NC1AddlAmt": self.convert_to_4_decimal_string(NC1AddlAmt),
                "NC2Tax": self.convert_to_4_decimal_string(NC2Tax),
                "NC2AddlAmt": "0.0000",
                "CTax": self.convert_to_4_decimal_string(fareDetails['YQ']) if not RCFlag else "0.0000",
                "CAddlAmt": "0.0000",
                "JNTax": self.convert_to_4_decimal_string(fareDetails['K3']) if not RCFlag else "0.0000" , # Confusion
                "JNAddlAmt": "0.0000",
                "TxnFees": "0.0000",
                "OCTax": "0.0000",
                "StdComm": '0.0000',
                "CPInc": "0.0000",
                "NCPInc": "0.0000",
                "PLB": self.convert_to_4_decimal_string(sup_PLB),
                "OR": "0.0000",
                "SrvChrgs": self.convert_to_4_decimal_string(create_bill_response['supplier_end']['sfee']), # supplier deal sheet
                "MGTFee": '0.0000',
                "CustStdComm": self.convert_to_4_decimal_string(CustStdComm),
                "CustCPInc": "0.0000",
                "CustNCPInc": "0.0000",
                "CustPLB": self.convert_to_4_decimal_string(cust_PLB),# customer PLB 246
                "CustOR": "0.0000",
                "CustSrvChrgs": self.convert_to_4_decimal_string(create_bill_response['customer_end']['sfee']),
                "CustMGTFee": '0.0000',
                "PercTDS": self.convert_to_4_decimal_string(tax_condition['tds']),
                "TDS": self.convert_to_4_decimal_string(supp_TDS), # supplier discount*tds
                "CustPercTDS": self.convert_to_4_decimal_string(tax_condition['tds']),
                "CustTDS": self.convert_to_4_decimal_string(cust_TDS), # customer discount*tds
                "sGTAX": "",
                "PercGTAX": self.convert_to_4_decimal_string(tax_condition['tax']),
                "GTAX": self.convert_to_4_decimal_string(GTAX),
                "sCustGTAX": "",
                "CustPercGTAX": self.convert_to_4_decimal_string(tax_condition['tax']),
                "CustGTAX": self.convert_to_4_decimal_string(create_bill_response['customer_end']['sfee']*(tax_condition['tax']/100)),
                "CustGTAXAdl": "0.0000",
                "SCPercGTAX": "0.0000",
                "SCGTAX": "0.0000",
                "SCPercSrch": "0.0000",
                "SCSrch": "0.0000",
                "CustSCPercGTAX": "0.0000",
                "CustSCGTAX": "0.0000",
                "CustSCPercSrch": "0.0000",
                "CustSCSrch": "0.0000",
                "credittype": "F",
                "RCFlag":RCFlag,
                "ReftktNo":"",
                'Region':'',
                'ReftktDt':'',
                'AirCCNo':AirCCNo,
                'PaxName': (pax.get('title',"")+" "+pax.get('firstName',"")+" "+ pax.get('lastName',"")).replace(".","").strip(),
                'Sector':Sectors,
                "CRS":crs,
                'FareBasis':retpnr_response['fareDetails']['fareBasis'],
                'DealCode':'',
                'BillNarration': '',
                'BillNote':'',
                'ModeofPayment': create_bill_response['fop']['type']
                }
                final_data = Sdata | data
                final_result.append(final_data)
        self.airticket_billing(final_result,"")
        return {"status":"Success"}
    
    def manage_ticket_number(self,**kwargs):
        ticket_number = kwargs["ticket_number"]
        if ticket_number == "":
            ticket_number = kwargs["pnr"]
        if self.bta_env =="DEV" and ticket_number != kwargs["pnr"]:
            ticket_number = str(time.time()).replace(".","")[-10:]
            time.sleep(1)
        if len(ticket_number)>10:
            ticket_number = ticket_number[-10:]
        return ticket_number
    
    def process_easylink_refund(self,**kwargs):
        cancellation_fee_dict = kwargs["cancellation_fee_dict"]
        payload_required = [passenger for passenger in kwargs["payload"] if passenger["PaxName"].split(" ", 1)[-1] in kwargs["pax_names"]]
        for payload_pax in payload_required:
            payload_pax["RAF"] = "{:.4f}".format(cancellation_fee_dict[payload_pax["PaxName"].split(" ", 1)[-1]]["supplier_cancellation_charge"])
            payload_pax["CustRAF"] = "{:.4f}".format(cancellation_fee_dict[payload_pax["PaxName"].split(" ", 1)[-1]]["customer_cancellation_charge"])
            payload_pax["Penalty"] = "0.0000"
            payload_pax["CustPenalty"] = "0.0000"
            payload_pax["CustPercGTAXRAF"] = "0.0000"
            payload_pax["CustGTAXRAF"] = "0.0000"
            payload_pax["CustPercGTAXpen"] = "0.0000"
            payload_pax["CustGTAXpen"] = "0.0000"
            payload_pax["SCPaid"] = "0.0000"
            payload_pax["CustSCPaid"] = "0.0000"
            payload_pax["CustGTAXSCP"] = "0.0000"
            payload_pax["ReceiptAmt"] = "{:.4f}".format(payload_pax["ReceiptAmt"])
            payload_pax["ReftktDt"] = datetime.today().strftime('%d/%m/%Y')
        self.airticket_refund_billing(payload_required,"")
        return {"status":"Success"}
   
def convert_to_4_decimal_string(value):
    try:
        formatted_value = f"{float(value):.4f}"
        return formatted_value
    except ValueError:
        return "0.0000"  