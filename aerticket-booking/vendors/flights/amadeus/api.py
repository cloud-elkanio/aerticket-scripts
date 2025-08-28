import requests,json
from requests.auth import HTTPBasicAuth
import xmltodict
import random
import uuid
import os
import base64
import hashlib
from datetime import datetime, timedelta,timezone
import time
from concurrent.futures import ThreadPoolExecutor
from vendors.flights import mongo_handler
from vendors.flights.utils import dictlistconverter
import concurrent.futures
ptc_mapping = {"adults": "ADT","children": "CHD","infants": "INF"}

def clean_keys(data):
    if isinstance(data, dict):
        return {clean_key(k): clean_keys(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_keys(element) for element in data]
    else:
        return data

def clean_key(key):     # Remove '@','#' and replace ':' with '_'
    key = key.replace('@', '')
    key = key.replace('#', '')
    key = key.replace(':', '_')
    return key

def convert_date(date_str):
    date_obj = datetime.strptime(date_str, "%d-%m-%Y")
    return date_obj.strftime("%d%m%y")

def generate_nonce(length=16):
    return base64.b64encode(os.urandom(length)).decode('utf-8')

def generate_password_digest(nonce, timestamp, clear_password):
    decoded_nonce = base64.b64decode(nonce)
    sha1_clear_password = hashlib.sha1(clear_password.encode()).digest()
    concatenated_string = decoded_nonce + timestamp.encode() + sha1_clear_password
    sha1_concatenated_string = hashlib.sha1(concatenated_string).digest()
    password_digest = base64.b64encode(sha1_concatenated_string).decode()
    return password_digest

def create_soap_envelope(header, body):
    envelope = f"""
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:ses="http://xml.amadeus.com/2010/06/Session_v3">
            {header}
            {body}
        </soap:Envelope>
    """
    return envelope

def create_first_soap_header(base_url,credentails,api_key): #FMPTBQ_23_2_1A
    uid = uuid.uuid4()
    nonce = generate_nonce()
    password= credentails.get("password")
    user_name= credentails.get("user_name")
    city_code = credentails.get("city_code")
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    password_digest = generate_password_digest(
        nonce, timestamp, password)  # AMADEUS100 Use your clear password

    header = f"""
    <soap:Header>
        <ses:Session TransactionStatusCode="Start" />
        <add:MessageID xmlns:add="http://www.w3.org/2005/08/addressing">{uid}</add:MessageID>
        <add:Action xmlns:add="http://www.w3.org/2005/08/addressing">http://webservices.amadeus.com/{api_key}</add:Action>
        <add:To xmlns:add="http://www.w3.org/2005/08/addressing">{base_url}</add:To>
        <link:TransactionFlowLink xmlns:link="http://wsdl.amadeus.com/2010/06/ws/Link_v1" />
            <oas:Security xmlns:oas="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
                <oas:UsernameToken xmlns:oas1="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd" oas1:Id="UsernameToken-1">
                    <oas:Username>{user_name}</oas:Username>
                    <oas:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{nonce}</oas:Nonce>
                    <oas:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{password_digest}</oas:Password>
                    <oas1:Created>{timestamp}</oas1:Created>
                </oas:UsernameToken>
            </oas:Security>
            <AMA_SecurityHostedUser xmlns="http://xml.amadeus.com/2010/06/Security_v1">
                <UserID AgentDutyCode="SU" POS_Type="1" PseudoCityCode="{city_code}" RequestorType="U" />
            </AMA_SecurityHostedUser>
    </soap:Header>
    """
    return header

def create_followup_header(base_url,session_info,api_key,TransactionStatusCode = "InSeries"):
    """
    Create the SOAP header using session information.
    """
    message_id = uuid.uuid4()
    return f"""
    <soap:Header>
        <ses:Session TransactionStatusCode="{TransactionStatusCode}">
            <ses:SessionId>{session_info["SessionId"]}</ses:SessionId>
            <ses:SequenceNumber>{session_info["SequenceNumber"]}</ses:SequenceNumber>
            <ses:SecurityToken>{session_info["SecurityToken"]}</ses:SecurityToken>
        </ses:Session>
        <add:MessageID xmlns:add="http://www.w3.org/2005/08/addressing">{message_id}</add:MessageID>
        <add:Action xmlns:add="http://www.w3.org/2005/08/addressing">http://webservices.amadeus.com/{api_key}</add:Action>
        <add:To xmlns:add="http://www.w3.org/2005/08/addressing">{base_url}</add:To>
        <link:TransactionFlowLink xmlns:link="http://wsdl.amadeus.com/2010/06/ws/Link_v1" />
    </soap:Header>
    """

def create_FMPTBQ_23_2_1A_body(journey_details, passenger_details,cabin_class=['F', 'Y']):     #Fare_MasterPricerTravelBoardSearch


    num_units_px = (
        int(passenger_details["adults"]) +
        int(passenger_details["children"])
    )
    xml_body = f"""
    <soap:Body>
        <Fare_MasterPricerTravelBoardSearch>
            <numberOfUnit>
                <unitNumberDetail>
                    <numberOfUnits>200</numberOfUnits>
                    <typeOfUnit>RC</typeOfUnit>
                </unitNumberDetail>
                <unitNumberDetail>
                    <numberOfUnits>{num_units_px}</numberOfUnits>
                    <typeOfUnit>PX</typeOfUnit>
                </unitNumberDetail>
            </numberOfUnit>
    """
    traveller_ref = 1
    infant_ref = 1
    for passenger_type, ptc in ptc_mapping.items():
        count = int(passenger_details.get(passenger_type, 0))
        if count > 0:
            xml_body += f"""
            <paxReference>
                <ptc>{ptc}</ptc>"""
                    
            for _ in range(count):
                if ptc =="INF":
                    xml_body +=f""" 
                <traveller>
                    <ref>{infant_ref}</ref>
                <infantIndicator>1</infantIndicator>"""
                    infant_ref+=1
                else:
                    xml_body +=f""" 
                <traveller>
                    <ref>{traveller_ref}</ref>"""
                xml_body +="""
                </traveller>"""
                
                traveller_ref += 1
            xml_body += """
            </paxReference>"""

    xml_body += """
            <fareOptions>
                <pricingTickInfo>
                    <pricingTicketing>
                        <priceType>RP</priceType>

                        <priceType>ET</priceType>
                        </pricingTicketing>
                </pricingTickInfo>
                <feeIdDescription />
            </fareOptions>
            """
    if cabin_class:
        cabin_xml = ''.join([f'<cabin>{c}</cabin>' for c in cabin_class])
        xml_body +=f"""
            <travelFlightInfo>
                <cabinId>
                    {cabin_xml}
                </cabinId>
            </travelFlightInfo>
            """

    for idx, journey in enumerate(journey_details):
        converted_date = convert_date(journey["travel_date"])
        xml_body += f"""
            <itinerary>
                <requestedSegmentRef>
                    <segRef>{idx + 1}</segRef>
                </requestedSegmentRef>
                <departureLocalization>
                    <departurePoint>
                        <locationId>{journey["source_city"]}</locationId>
                    </departurePoint>
                </departureLocalization>
                <arrivalLocalization>
                    <arrivalPointDetails>
                        <locationId>{journey["destination_city"]}</locationId>
                    </arrivalPointDetails>
                </arrivalLocalization>
                <timeDetails>
                    <firstDateTimeDetail>
                        <date>{converted_date}</date>
                    </firstDateTimeDetail>
                </timeDetails>
            </itinerary>
        """
    xml_body += """
        </Fare_MasterPricerTravelBoardSearch>
    </soap:Body>
    """

    return xml_body.strip()

def flight_search(session_id,base_url,credentials,passenger_details,journey_details,cabin_class):
    api_key = "FMPTBQ_23_2_1A"
    header = create_first_soap_header(base_url,credentials,api_key)
    body = create_FMPTBQ_23_2_1A_body(journey_details, passenger_details,cabin_class)
    soap_message = create_soap_envelope(header, body)
    url = base_url
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(url, data=soap_message, headers=headers)

    data_dict = xmltodict.parse(response.text)
    cleaned_data = clean_keys(data_dict)
    status =  "soap_Fault" not in cleaned_data.get("soap_Envelope").get("soap_Body")
    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
            "payload":soap_message,"api":"flight_search","url":base_url,"response":{"status":status,"data":response.text}}
    api_logs_to_mongo(log)
    return cleaned_data

def create_TIPNRQ_18_1_1A_body(passenger_dict, segments, pricingOptions):
    body_xml = '<soap:Body>\n'
    body_xml += '<Fare_InformativePricingWithoutPNR>\n'

    measurement_value = 1  # Start with measurement value 1, increment for each passenger
    infant_count= 1  # Start with measurement value 1, increment for each infants
    passenger_xml = ""
    
    for idx,(passenger_type, quantity) in enumerate(passenger_dict.items()):
        if quantity > 0:
            
            if passenger_type == "INF":
                traveller_details = "\n".join(
                    f"""
                    <travellerDetails>
                        <measurementValue>{infant_count + i}</measurementValue>
                    </travellerDetails>
                    """ for i in range(quantity)
                )
                infant_count+=quantity
            else:
                traveller_details = "\n".join(
                    f"""
                    <travellerDetails>
                        <measurementValue>{measurement_value + i}</measurementValue>
                    </travellerDetails>
                    """ for i in range(quantity)
                )
                measurement_value += quantity  # Increment measurement value for the next group
            passenger_xml += f"""
            <passengersGroup>
                <segmentRepetitionControl>
                    <segmentControlDetails>
                        <quantity>{idx+1}</quantity>
                        <numberOfUnits>{quantity}</numberOfUnits>
                    </segmentControlDetails>
                </segmentRepetitionControl>
                <travellersID>
                    {traveller_details}
                </travellersID>
                <discountPtc>
                    <valueQualifier>{passenger_type}</valueQualifier>
            """
            if passenger_type == "INF":
                passenger_xml += """
                    <fareDetails>
                        <qualifier>766</qualifier>
                    </fareDetails>
                """
            passenger_xml += """
                </discountPtc>
            </passengersGroup>
            """
           
    
    body_xml +=passenger_xml

    for segment in segments:
        body_xml += f"""
        <segmentGroup>
            <segmentInformation>
                <flightDate>
                    <departureDate>{segment["departureDate"]}</departureDate>
                </flightDate>
                <boardPointDetails>
                    <trueLocationId>{segment["trueLocationIdBoard"]}</trueLocationId>
                </boardPointDetails>
                <offpointDetails>
                    <trueLocationId>{segment["trueLocationIdOff"]}</trueLocationId>
                </offpointDetails>
                <companyDetails>
                    <marketingCompany>{segment["marketingCompany"]}</marketingCompany>
                </companyDetails>
                <flightIdentification>
                    <flightNumber>{segment["flightNumber"]}</flightNumber>
                    <bookingClass>{segment["bookingClass"]}</bookingClass>
                </flightIdentification>
                <flightTypeDetails>
                    <flightIndicator>{segment["flightIndicator"]}</flightIndicator>
                </flightTypeDetails>
                <itemNumber>{segment["itemNumber"]}</itemNumber>
            </segmentInformation>
        </segmentGroup>
        """
    
    # Generate pricing options
    for option in pricingOptions:
        pricing_option_group = f"""
        <pricingOptionGroup>
            <pricingOptionKey>
                <pricingOptionKey>{option["pricingOptionKey"]}</pricingOptionKey>
            </pricingOptionKey>
        """
        if option["pricingOptionKey"] == "VC":
            pricing_option_group += f"""
            <carrierInformation>
              <companyIdentification>
                <otherCompany>{segments[0]["marketingCompany"]}</otherCompany>
              </companyIdentification>
            </carrierInformation>"""
        # Add currency details for "FCO" options
        if option["pricingOptionKey"] == "FCO":
            pricing_option_group += f"""
            <currency>
                <firstCurrencyDetails>
                    <currencyQualifier>{option["currencyQualifier"]}</currencyQualifier>
                    <currencyIsoCode>{option["currencyIsoCode"]}</currencyIsoCode>
                </firstCurrencyDetails>
            </currency>
            """
        pricing_option_group += """
        </pricingOptionGroup>
        """
        body_xml += pricing_option_group


    # Close main tags
    body_xml += '</Fare_InformativePricingWithoutPNR>\n'
    body_xml += '</soap:Body>'

    return body_xml

def create_TIUNRQ_23_1_1A_body(passenger_dict, segments, pricingOptions): #Fare_PriceUpsellWithoutPNR
    body_xml = '<soap:Body>\n'
    body_xml += '<Fare_PriceUpsellWithoutPNR>\n'

    measurement_value = 1  
    infant_count= 1
    passenger_xml = ""
    
    for idx,(passenger_type, quantity) in enumerate(passenger_dict.items()):
        quantity = int(quantity)
        if quantity > 0:
            
            if passenger_type == "INF":
                traveller_details = "\n".join(
                    f"""
                    <travellerDetails>
                        <measurementValue>{infant_count + i}</measurementValue>
                    </travellerDetails>
                    """ for i in range(quantity)
                )
                infant_count+=quantity
            else:
                traveller_details = "\n".join(
                    f"""
                    <travellerDetails>
                        <measurementValue>{measurement_value + i}</measurementValue>
                    </travellerDetails>
                    """ for i in range(quantity)
                )
                measurement_value += quantity 
            passenger_xml += f"""
            <passengersGroup>
                <segmentRepetitionControl>
                    <segmentControlDetails>
                        <quantity>{idx+1}</quantity>
                        <numberOfUnits>{quantity}</numberOfUnits>
                    </segmentControlDetails>
                </segmentRepetitionControl>
                <travellersID>
                    {traveller_details}
                </travellersID>
                <discountPtc>
                    <valueQualifier>{passenger_type}</valueQualifier>
            """
            if passenger_type == "INF":
                passenger_xml += """
                    <fareDetails>
                        <qualifier>766</qualifier>
                    </fareDetails>
                """
            passenger_xml += """
                </discountPtc>
            </passengersGroup>
            """
           
    body_xml +=passenger_xml

    for segment in segments:
        body_xml += f"""
        <segmentGroup>
            <segmentInformation>
                <flightDate>
                    <departureDate>{segment["departureDate"]}</departureDate>
                </flightDate>
                <boardPointDetails>
                    <trueLocationId>{segment["trueLocationIdBoard"]}</trueLocationId>
                </boardPointDetails>
                <offpointDetails>
                    <trueLocationId>{segment["trueLocationIdOff"]}</trueLocationId>
                </offpointDetails>
                <companyDetails>
                    <marketingCompany>{segment["marketingCompany"]}</marketingCompany>
                </companyDetails>
                <flightIdentification>
                    <flightNumber>{segment["flightNumber"]}</flightNumber>
                    <bookingClass>{segment["bookingClass"]}</bookingClass>
                </flightIdentification>
                <flightTypeDetails>
                    <flightIndicator>{segment["flightIndicator"]}</flightIndicator>
                </flightTypeDetails>
                <itemNumber>{segment["itemNumber"]}</itemNumber>
            </segmentInformation>
        </segmentGroup>
        """
    
    for option in pricingOptions:
        
        pricing_option_group = f"""
        <pricingOptionGroup>
            <pricingOptionKey>
                <pricingOptionKey>{option["pricingOptionKey"]}</pricingOptionKey>
            </pricingOptionKey>
        """
        if option["pricingOptionKey"] == "VC":
            pricing_option_group += f"""
            <carrierInformation>
              <companyIdentification>
                <otherCompany>{segments[0]["marketingCompany"]}</otherCompany>
              </companyIdentification>
            </carrierInformation>"""
        # Add currency details for "FCO" options
        if option["pricingOptionKey"] == "FCO":
            pricing_option_group += f"""
            <currency>
                <firstCurrencyDetails>
                    <currencyQualifier>{option["currencyQualifier"]}</currencyQualifier>
                    <currencyIsoCode>{option["currencyIsoCode"]}</currencyIsoCode>
                </firstCurrencyDetails>
            </currency>
            """
        if option["pricingOptionKey"] == "CAB":
            if segment["bookingClass"] in ("M","Y"):
                pricing_option_group += f"""
                <optionDetail>
                    <criteriaDetails>
                        <attributeType>FC</attributeType>
                        <attributeDescription>M</attributeDescription>
                    </criteriaDetails>
                    <criteriaDetails>
                        <attributeType>SC</attributeType>
                        <attributeDescription>Y</attributeDescription>
                    </criteriaDetails>
                </optionDetail>
                    """
            else:
                pricing_option_group += f"""
                <optionDetail>
                    <criteriaDetails>
                        <attributeType>FC</attributeType>
                        <attributeDescription>{segment["bookingClass"]}</attributeDescription>
                    </criteriaDetails>
                </optionDetail>
                    """
        pricing_option_group += """
        </pricingOptionGroup>
        """
        body_xml += pricing_option_group

    body_xml += '</Fare_PriceUpsellWithoutPNR>\n'
    body_xml += '</soap:Body>'

    return body_xml

def create_FARQNQ_07_1_1A_body(ruleid,segid): #Fare_CheckRules
    body = f"""
    <soap:Body xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <Fare_CheckRules>
            <msgType>
                <messageFunctionDetails>
                    <messageFunction>712</messageFunction>
                </messageFunctionDetails>
            </msgType>
            <itemNumber>
                <itemNumberDetails>
                    <number>{ruleid}</number>
                </itemNumberDetails>
                <itemNumberDetails>
                    <number>{segid+1}</number>
                    <type>FC</type>
                </itemNumberDetails>
            </itemNumber>
            <fareRule>
                <tarifFareRule>
                    <ruleSectionId>PE</ruleSectionId>
                    <ruleSectionId>MX</ruleSectionId>
                    <ruleSectionId>SR</ruleSectionId>
                    <ruleSectionId>TR</ruleSectionId>
                    <ruleSectionId>AP</ruleSectionId>
                    <ruleSectionId>FL</ruleSectionId>
                </tarifFareRule>
            </fareRule>
        </Fare_CheckRules>
    </soap:Body>
    """
    return body


def create_fare_rules(session_id,base_url,credentials,passenger_counts,segments,pricingOptions,is_round_trip):
    api_key = "TIUNRQ_23_1_1A"
    header = create_first_soap_header(base_url, credentials, api_key)
    passenger_dict = passenger_counts
    body = create_TIUNRQ_23_1_1A_body(passenger_dict, segments, pricingOptions)
    soap_message = create_soap_envelope(header, body)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(base_url, data=soap_message, headers=headers)
    data_dict = xmltodict.parse(response.text)
    TIUNRQ_23_1_1A = clean_keys(data_dict)
    status =  "soap_Fault" not in TIUNRQ_23_1_1A.get("soap_Envelope").get("soap_Body")
    
    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
            "payload":soap_message,"api":"fare_rule","url":base_url,"response":{"status":status,"data":response.text},"misc":"TIUNRQ_23_1_1A"}
    
    
    api_logs_to_mongo(log)

    upsell = True if "applicationError" not in  TIUNRQ_23_1_1A.get("soap_Envelope",{}).get("soap_Body",{}).get("Fare_PriceUpsellWithoutPNRReply",{}).keys() else False
    #upsell = False
    if upsell:
        fare_list = TIUNRQ_23_1_1A.get('soap_Envelope', {}).get('soap_Body', {}).get('Fare_PriceUpsellWithoutPNRReply', {}).get('fareList', [])
        for x in fare_list:
            x["is_upsell"] = True
            x["fare_rule"] = []

        session_header = TIUNRQ_23_1_1A.get("soap_Envelope", {}).get("soap_Header", {}).get("awsse_Session", {})
    else:
        api_key = "TIPNRQ_18_1_1A"
        header = create_first_soap_header(base_url, credentials, api_key)

        passenger_dict = passenger_counts
        body = create_TIPNRQ_18_1_1A_body(passenger_dict, segments, pricingOptions)
        soap_message = create_soap_envelope(header, body)

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
        }

        response = requests.post(base_url, data=soap_message, headers=headers)
        data_dict = xmltodict.parse(response.text)
        TIPNRQ_18_1_1A = clean_keys(data_dict)
        status =  "soap_Fault" not in TIPNRQ_18_1_1A.get("soap_Envelope").get("soap_Body")

        log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
                "payload":soap_message,"api":"fare_rule","url":base_url,"response":{"status":status,"data":response.text}}
        api_logs_to_mongo(log)
        fare_list = TIPNRQ_18_1_1A.get('soap_Envelope', {}).get('soap_Body', {}).get('Fare_InformativePricingWithoutPNRReply',{}).get('mainGroup',{}).get("pricingGroupLevelGroup",None)
        fare_list = dictlistconverter(fare_list)
        for x in fare_list:
            x["is_upsell"] = False
            x["fare_rule"] = []
        session_header = TIPNRQ_18_1_1A.get("soap_Envelope", {}).get("soap_Header", {}).get("awsse_Session", {})


    session_info = {
        "SessionId": session_header.get("awsse_SessionId"),
        "SequenceNumber": int(session_header.get("awsse_SequenceNumber")),
        "SecurityToken": session_header.get("awsse_SecurityToken")
    }

    def process_fare_rule(idx, fare, base_url, session_info,idy):
        """Processes a single fare rule API call."""
        api_key = "FARQNQ_07_1_1A"
        session_info = {
            "SessionId": session_info["SessionId"],
            "SequenceNumber": session_info["SequenceNumber"] + idx,
            "SecurityToken": session_info["SecurityToken"]
        }

        body = create_FARQNQ_07_1_1A_body(idx,idy) 
        header = create_followup_header(base_url, session_info, api_key)
        
        soap_message = create_soap_envelope(header, body)
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
        }

        response = requests.post(base_url, data=soap_message, headers=headers)

        if response.status_code == 200:
            data_dict = xmltodict.parse(response.text)
            FARQNQ_07_1_1A = clean_keys(data_dict)
            fare_rule = FARQNQ_07_1_1A.get('soap_Envelope', {}).get('soap_Body', {}).get('Fare_CheckRulesReply', {})

            # Add the fare rule to the fare dictionary
            fare["fare_rule"].append(fare_rule)
            status =  "soap_Fault" not in FARQNQ_07_1_1A.get("soap_Envelope").get("soap_Body")

            log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
            "payload":soap_message,"api":"fare_rule","url":base_url,"response":{"status":status,"data":response.text},"misc":str(upsell)}
            api_logs_to_mongo(log)
        else:
            print(f"Error for fare index {idx}: {response.text}")

    def process_all_fare_rules(fare_list, base_url, session_info,is_round_trip):
        """Processes all fare rules using multithreading."""
        if is_round_trip:
            count = 2
        else:
            count = 1
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []

            for idx, fare in enumerate(fare_list,start=1):
                # Submit a thread for each fare rule
                for idy in range(count):
                    futures.append(
                        executor.submit(process_fare_rule, idx, fare, base_url, session_info,idy)
                    )
                    time.sleep(0.2) # for not processing a higher index before first
            

            # Wait for all threads to complete
            for future in futures:
                future.result()
    start = time.time()
    process_all_fare_rules(fare_list, base_url, session_info,is_round_trip)
    

    return fare_list


def create_ITAREQ_05_2_IA_body(flight_segments,pax_count,fare_class): #Air_SellFromRecommendation
    travelProductinformation=""
    if not isinstance(fare_class,list):
        fare_class = [flight_segment['bookingClass'] for flight_segment in flight_segments]
    for idx,flight_segment in enumerate(flight_segments):

        departure_date = flight_segment.get("departureDate")  # Format: DDMMYY
        departure_airport = flight_segment['trueLocationIdBoard']
        arrival_airport = flight_segment['trueLocationIdOff']
        airline_code = flight_segment['marketingCompany']
        flight_number = flight_segment['flightNumber']
        booking_class = flight_segment['bookingClass']
        travelProductinformation+=f"""
        <itineraryDetails>
            <originDestinationDetails>
                <origin>{departure_airport}</origin>
                <destination>{arrival_airport}</destination>
            </originDestinationDetails>
            <message>
            <messageFunctionDetails>
                <messageFunction>183</messageFunction>
            </messageFunctionDetails>
            </message>
            <segmentInformation>
                <travelProductInformation>
                    <flightDate>
                        <departureDate>{departure_date}</departureDate>
                    </flightDate>
                    <boardPointDetails>
                        <trueLocationId>{departure_airport}</trueLocationId>
                    </boardPointDetails>
                    <offpointDetails>
                        <trueLocationId>{arrival_airport}</trueLocationId>
                    </offpointDetails>
                    <companyDetails>
                        <marketingCompany>{airline_code}</marketingCompany>
                    </companyDetails>
                    <flightIdentification>
                        <flightNumber>{flight_number}</flightNumber>
                        <bookingClass>{fare_class[idx]}</bookingClass>
                    </flightIdentification>
                </travelProductInformation>
                <relatedproductInformation>
                    <quantity>{pax_count}</quantity>
                    <statusCode>NN</statusCode>
                </relatedproductInformation>
            </segmentInformation>
        </itineraryDetails>
        """

    # Construct the SOAP body
    soap_body = f"""
    <soap:Body>
        <Air_SellFromRecommendation>
        <messageActionDetails>
            <messageFunctionDetails>
            <messageFunction>183</messageFunction>
            <additionalMessageFunction>M1</additionalMessageFunction>
            </messageFunctionDetails>
        </messageActionDetails>
        {travelProductinformation}
        </Air_SellFromRecommendation>
    </soap:Body>
    """
    return soap_body


def fare_quote(session_id,base_url,credentials,segments,pax_count,fare_class):
    api_key = "ITAREQ_05_2_IA"
    header = create_first_soap_header(base_url,credentials,api_key)
    
    body = create_ITAREQ_05_2_IA_body( segments,pax_count,fare_class)
    soap_message = create_soap_envelope(header, body)
    url = base_url
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(url, data=soap_message, headers=headers)
    data_dict = xmltodict.parse(response.text)
    ITAREQ_05_2_IA = clean_keys(data_dict)
    status =  "soap_Fault" not in ITAREQ_05_2_IA.get("soap_Envelope").get("soap_Body")

    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
    "payload":soap_message,"api":"fare_quote","url":base_url,"response":{"status":status,"data":response.text}}
    api_logs_to_mongo(log)
    return ITAREQ_05_2_IA

def create_SMPREQ_17_1_1A_body(segment_data,pax_type="adults"):
    body = f"""
    <soap:Body xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">

        <Air_RetrieveSeatMap>
            <travelProductIdent>
            <flightDate>
                <departureDate>{segment_data['departureDate']}</departureDate>
            </flightDate>
            <boardPointDetails>
                <trueLocationId>{segment_data['trueLocationIdBoard']}</trueLocationId>
            </boardPointDetails>
            <offpointDetails>
                <trueLocationId>{segment_data['trueLocationIdOff']}</trueLocationId>
            </offpointDetails>
            <companyDetails>
                <marketingCompany>{segment_data['marketingCompany']}</marketingCompany>
            </companyDetails>
            <flightIdentification>
                <flightNumber>{segment_data['flightNumber']}</flightNumber>
                <bookingClass>{segment_data['bookingClass']}</bookingClass>
            </flightIdentification>
            </travelProductIdent>
            <seatRequestParameters>
            <processingIndicator>FT</processingIndicator>
            </seatRequestParameters>
            """
    if pax_type =="children":
        body+="""
            <traveler>
                <travelerInformation>
                    <paxDetails>
                    <surname>ALEX</surname>
                    <quantity>1</quantity>
                </paxDetails>
                <otherPaxDetails>
                    <givenName>KENNETH MR</givenName>
                    <type>CNN</type>
                    <uniqueCustomerIdentifier>2</uniqueCustomerIdentifier>
                </otherPaxDetails>    
                </travelerInformation>
            </traveler>"""
    else:
        body+="""
            <traveler>
                <travelerInformation>
                    <paxDetails>
                    <surname>JOHN</surname>
                    <quantity>1</quantity>
                </paxDetails>
                <otherPaxDetails>
                    <givenName>KENNETH MR</givenName>
                    <type>ADT</type>
                    <uniqueCustomerIdentifier>2</uniqueCustomerIdentifier>
                </otherPaxDetails>    
                </travelerInformation>
            </traveler>"""    
    body+="""
            </Air_RetrieveSeatMap>                         
        </soap:Body>"""
    return body


def get_seatmap(session_id,base_url,credentials,segments,passenger_details):
    api_key = "SMPREQ_17_1_1A"
    url = base_url
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    def call_amadeus_api_for_segment(passenger_key, segment):
        body = create_SMPREQ_17_1_1A_body(segment, passenger_key)
        header = create_first_soap_header(base_url,credentials,api_key)

        soap_message = create_soap_envelope(header, body)
        time.sleep(0.2)
        response = requests.post(url, data=soap_message, headers=headers)
        data_dict = xmltodict.parse(response.text)
        cleaned = clean_keys(data_dict)
        status =  "soap_Fault" not in cleaned.get("soap_Envelope").get("soap_Body")

        log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
        "payload":soap_message,"api":"ssr","url":base_url,"response":{"status":status,"data":response.text},"misc":"seatmap_"+passenger_key}
        api_logs_to_mongo(log)
        
        return cleaned
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Dictionary to map each Future to a task info dictionary.
        future_to_task = {}
        for passenger_key, passenger_value in passenger_details.items():
            if int(passenger_value) != 0:
                for segment in segments:
                    future = executor.submit(call_amadeus_api_for_segment, passenger_key, segment)
                    seg_key = segment.get("trueLocationIdBoard") + "-" + segment.get("trueLocationIdOff")
                    future_to_task[future] = {"paxtype": passenger_key, "seg_key": seg_key}
         
        for future in concurrent.futures.as_completed(future_to_task):
            task_info = future_to_task[future]
            paxtype = task_info["paxtype"]
            seg_key = task_info["seg_key"]
            # try:
            result_data = future.result()
            if seg_key not in results:
                results[seg_key] = {}
            results[seg_key][paxtype] = result_data
    return results

def create_TPSCGQ_17_1_1A_body(segment,passenger_dict ):
    pricingOptions = [
        {"pricingOptionKey": "FAR"},
        {"pricingOptionKey": "GRP"},
        {"pricingOptionKey": "BGR"},
        {"pricingOptionKey": "MIF"},
        {"pricingOptionKey": "SCD"}
    ]
    body_xml = '<soap:Body>\n'
    body_xml += '<Service_StandaloneCatalogue xmlns="http://xml.amadeus.com/TPSCGQ_17_1_1A">\n'
    
    # Generate passenger groups
    measurement_value = 1  # Start with measurement value 1, increment for each passenger
    passenger_xml = ""
    
    for idx, (passenger_type, quantity) in enumerate(passenger_dict.items()):
        if passenger_type =="infants":
            continue

        if quantity > 0:

            traveller_details = "\n".join(
                f"""
                <travellerDetails>
                    <measurementValue>{measurement_value + i}</measurementValue>
                </travellerDetails>
                """ for i in range(quantity)
            )
            measurement_value += quantity  # Increment measurement value for the next group
            
            passenger_xml += f"""
            <passengerInfoGroup>
                <specificTravellerDetails>
                    <travellerDetails>
                        <referenceNumber>{idx + 1}</referenceNumber>
                    </travellerDetails>
                </specificTravellerDetails>
                <fareInfo>
                    <valueQualifier>{ptc_mapping[passenger_type]}</valueQualifier>
                </fareInfo>
            </passengerInfoGroup>
            """
    
    body_xml += passenger_xml
    
    # Generate segment groups
    body_xml += f"""
    <flightInfo>
        <flightDetails>
            <flightDate>
                <departureDate>{segment["departureDate"]}</departureDate>
            </flightDate>
            <boardPointDetails>
                <trueLocationId>{segment["trueLocationIdBoard"]}</trueLocationId>
            </boardPointDetails>
            <offpointDetails>
                <trueLocationId>{segment["trueLocationIdOff"]}</trueLocationId>
            </offpointDetails>
            <companyDetails>
                <marketingCompany>{segment["marketingCompany"]}</marketingCompany>
            </companyDetails>
            <flightIdentification>
                <flightNumber>{segment["flightNumber"]}</flightNumber>
                <bookingClass>{segment["bookingClass"]}</bookingClass>
            </flightIdentification>
            <flightTypeDetails>
                <flightIndicator>{segment["flightIndicator"]}</flightIndicator>
            </flightTypeDetails>
            <itemNumber>{segment["itemNumber"]}</itemNumber>
        </flightDetails>
    </flightInfo>
    """
    
    # Generate pricing options
    for option in pricingOptions:
        pricing_option_group = f"""
        <pricingOption>
            <pricingOptionKey>
                <pricingOptionKey>{option["pricingOptionKey"]}</pricingOptionKey>
            </pricingOptionKey>
        """
        if option["pricingOptionKey"] == "VC":
            pricing_option_group += f"""
            <carrierInformation>
                <companyIdentification>
                    <otherCompany>{segment["marketingCompany"]}</otherCompany>
                </companyIdentification>
            </carrierInformation>
            """
        if option["pricingOptionKey"] == "FAR":
                pricing_option_group += f"""
                <optionDetail>
                    <criteriaDetails>
                        <attributeType>B</attributeType>
                        <attributeDescription>{segment["fareBasisCode"]}</attributeDescription>
                    </criteriaDetails>
                </optionDetail>
                """
        if option["pricingOptionKey"] == "GRP":
                pricing_option_group += f"""
                <optionDetail>
                    <criteriaDetails>
                        <attributeType>BG</attributeType>
                    </criteriaDetails>
                </optionDetail>
                """
        if option["pricingOptionKey"] == "FCO":
            pricing_option_group += f"""
            <currency>
                <firstCurrencyDetails>
                    <currencyQualifier>{option["currencyQualifier"]}</currencyQualifier>
                    <currencyIsoCode>{option["currencyIsoCode"]}</currencyIsoCode>
                </firstCurrencyDetails>
            </currency>
            """
        pricing_option_group += """
        </pricingOption>
        """
        body_xml += pricing_option_group
    
    # Close main tags
    body_xml += '</Service_StandaloneCatalogue>\n'
    body_xml += '</soap:Body>'
    
    return body_xml


def get_baggage(session_id,base_url,credentials,segments,passenger_details):
    api_key = "TPSCGQ_17_1_1A"
    url = base_url
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    def call_amadeus_api_for_segment(passenger_key, segment):
        body = create_TPSCGQ_17_1_1A_body(segment, passenger_key)
        header = create_first_soap_header(base_url,credentials,api_key)

        soap_message = create_soap_envelope(header, body)
        time.sleep(0.2)
        response = requests.post(url, data=soap_message, headers=headers)
        data_dict = xmltodict.parse(response.text)
        cleaned = clean_keys(data_dict)
        status =  "soap_Fault" not in cleaned.get("soap_Envelope").get("soap_Body")

        log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
        "payload":soap_message,"api":"ssr","url":base_url,"response":{"status":status,"data":response.text},"misc":"baggage"}
        api_logs_to_mongo(log)
        
        return cleaned
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Dictionary to map each Future to a task info dictionary.
        future_to_task = {}

        for segment in segments:
            future = executor.submit(call_amadeus_api_for_segment, passenger_details, segment)
            seg_key = segment.get("trueLocationIdBoard") + "-" + segment.get("trueLocationIdOff")
            future_to_task[future] = {"seg_key": seg_key}
         
        for future in concurrent.futures.as_completed(future_to_task):
            task_info = future_to_task[future]
            seg_key = task_info["seg_key"]
            # try:
            result_data = future.result()
            if seg_key not in results:
                results[seg_key] = {}
            results[seg_key]= result_data

    return results


def create_PNRADD_21_1_1A_body(
    passengers: list,
    ticket_date: str,
    ticket_time: str,
    flight_segments: list
    ) -> str:

    # Create passenger XML
    passenger_xml = ""
    contact_xml = ""
    ssr_xml = ""

    for i, pax in enumerate(passengers, 1):
        passenger_xml += f"""
        <travellerInfo>
            <elementManagementPassenger>
                <reference>
                    <qualifier>PR</qualifier>
                    <number>{i}</number>
                </reference>
                <segmentName>NM</segmentName>
            </elementManagementPassenger>
            <passengerData>
                <travellerInformation>
                    <traveller>
                        <surname>{pax['surname']}</surname>
                        <quantity>1</quantity>
                    </traveller>
                    <passenger>
                        <firstName>{pax['first_name']}</firstName>
                        <type>{pax['type']}</type>
                    </passenger>
                </travellerInformation>
                """
        if pax['date_of_birth']:
            passenger_xml+=f"""
                    <dateOfBirth>
                        <dateAndTimeDetails>
                            <date>{pax['date_of_birth']}</date>
                        </dateAndTimeDetails>
                    </dateOfBirth>"""
        passenger_xml+="""
                </passengerData>
        </travellerInfo>
        """
        contact_xml += f"""
        <dataElementsIndiv>
            <elementManagementData>
                <reference>
                    <qualifier>PR</qualifier>
                    <number>{i}</number>
                </reference>
                <segmentName>AP</segmentName>
            </elementManagementData>
            <freetextData>
                <freetextDetail>
                    <subjectQualifier>3</subjectQualifier>
                    <type>6</type>
                </freetextDetail>
                <longFreetext>{pax["phone"]}</longFreetext>
            </freetextData>
        </dataElementsIndiv>
        <dataElementsIndiv>
            <elementManagementData>
                <reference>
                    <qualifier>PR</qualifier>
                    <number>{i}</number>
                </reference>
                <segmentName>AP</segmentName>
            </elementManagementData>
            <freetextData>
                <freetextDetail>
                    <subjectQualifier>3</subjectQualifier>
                    <type>P02</type>
                </freetextDetail>
                <longFreetext>{pax['email'].upper()}</longFreetext>
            </freetextData>
        </dataElementsIndiv>
        """
        ssr_elements = pax.get("ssr")
        if ssr_elements:
            count = 0
            
            for k, ssr in enumerate(ssr_elements, start=4):
                count+=1

                ssr_xml += """
                <dataElementsIndiv>
                    <elementManagementData>"""


                # Add a reference for SSRs not of type "CTC"
                if "CTC" not in ssr['type'] :
                    ssr_xml += f"""
                        <reference>
                            <qualifier>OT</qualifier>
                            <number>{k+i*5}</number>
                        </reference>"""
                if ssr["type"] != "STR":
                    ssr_xml += f"""
                            <segmentName>SSR</segmentName>
                        </elementManagementData>
                        <serviceRequest>
                            <ssr>
                                <type>{ssr['type']}</type>
                                <status>{ssr['status']}</status>
                                <quantity>1</quantity>
                                <companyId>{ssr['company_id']}</companyId>
                                <freetext>{ssr['freetext']}</freetext>
                            </ssr>
                        </serviceRequest>
                        <referenceForDataElement>
                            <reference>
                                <qualifier>PR</qualifier>
                                <number>{i}</number>
                            </reference>
                        </referenceForDataElement>
                    </dataElementsIndiv>
                    """
                else:
                    ssr_xml += f"""
                    	<segmentName>STR</segmentName>
                        </elementManagementData>
                        <seatGroup>
                            <seatRequest>
                                <special>
                                    <data>{ssr["data"]}</data>
                                </special>
                            </seatRequest>
                        </seatGroup>
                        <referenceForDataElement>
                            <reference>
                                <qualifier>PT</qualifier>
                                <number>{ssr["pax"]}</number>
                            </reference>
                            <reference>
                                <qualifier>ST</qualifier>
                                <number>{ssr["segment"]}</number>
                            </reference>
                        </referenceForDataElement>
                    </dataElementsIndiv>
                    """

    # Construct itinerary info XML using flight segment details
    for flight_segment in flight_segments:
        itinerary_info_xml = f"""
        <itineraryInfo>
            <elementManagementItinerary>
                <reference>
                    <qualifier>ST</qualifier>
                    <number>1</number>
                </reference>
                <segmentName>AIR</segmentName>
            </elementManagementItinerary>
            <travelProduct>
                <product>
                    <depDate>{flight_segment["departureDate"]}</depDate>
                    <depTime>{flight_segment['departureTime']}</depTime>
                    <arrDate>{flight_segment['arrivalDate']}</arrDate>
                    <arrTime>{flight_segment['arrivalTime']}</arrTime>
                </product>
                <boardpointDetail>
                    <cityCode>{flight_segment['trueLocationIdBoard']}</cityCode>
                </boardpointDetail>
                <offpointDetail>
                    <cityCode>{flight_segment['trueLocationIdOff']}</cityCode>
                </offpointDetail>
                <companyDetail>
                    <identification>{flight_segment['marketingCompany']}</identification>
                </companyDetail>
                <productDetails>
                    <identification>{flight_segment['flightNumber']}</identification>
                    <classOfService>{flight_segment['bookingClass']}</classOfService>
                </productDetails>
            </travelProduct>
            <relatedProduct>
                <quantity>1</quantity>
                <status>HK</status>
            </relatedProduct>
        </itineraryInfo>
        """

    # Construct full XML body
    xml_string = f"""
    <soap:Body>
        <PNR_AddMultiElements>
            <pnrActions>
                <optionCode>0</optionCode>
            </pnrActions>
            {passenger_xml}
            <dataElementsMaster>
                <marker1 />
                {contact_xml}
                <dataElementsIndiv>
                    <elementManagementData>
                        <reference>
                            <qualifier>OT</qualifier>
                            <number>13</number>
                        </reference>
                        <segmentName>TK</segmentName>
                    </elementManagementData>
                    <ticketElement>
                        <ticket>
                            <indicator>XL</indicator>
                            <date>{ticket_date}</date>
                            <time>{ticket_time}</time>
                        </ticket>
                    </ticketElement>
                </dataElementsIndiv>
                {ssr_xml}
            </dataElementsMaster>
        </PNR_AddMultiElements>
    </soap:Body>
    """
    
    return xml_string.strip()

def add_pnr_data(session_id,base_url,credentials,pax_list,ticket_date,ticket_time, segments):
    api_key = "PNRADD_21_1_1A"
    header = create_followup_header(base_url,credentials,api_key)
    body = create_PNRADD_21_1_1A_body( pax_list,ticket_date,ticket_time,segments)

    soap_message = create_soap_envelope(header, body)
    url = base_url
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(url, data=soap_message, headers=headers)
    data_dict = xmltodict.parse(response.text)
    PNRADD_21_1_1A = clean_keys(data_dict)
    status =  "soap_Fault" not in PNRADD_21_1_1A.get("soap_Envelope").get("soap_Body")

    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
    "payload":soap_message,"api":"hold","url":base_url,"response":{"status":status,"data":response.text}}
    api_logs_to_mongo(log)
    return PNRADD_21_1_1A



def create_baggage_body(segments,pax_list): #DocIssuance_IssueTicket

    xml_body = f""" <soap:Body>
        <AMA_ServiceBookPriceServiceRQ Version="1.1">"""
    tid =0
    for segment in segments:
        
        seg_key = segment.get("trueLocationIdBoard") + "-" + segment.get("trueLocationIdOff")
        for idy,pax in enumerate(pax_list,start=2):
            baggage_code = pax.get("baggage_data",{}).get(seg_key)
            if baggage_code:
                tid+=1
                rfisc = baggage_code.split('_')[0]
                Code = baggage_code.split('_')[1]
                product = f"""
                    <Product>
                        <Service TID="R{tid}" customerRefIDs="{idy}" segmentRefIDs="{segment.get('itemNumber')}">
                        <identifier RFIC="C" RFISC="{rfisc}" Code="{Code}" bookingMethod="1" />
                        <serviceProvider code="{segment.get('marketingCompany')}" />
                        </Service>
                    </Product>"""
                xml_body+=product
            
            # <Product xmlns="http://xml.amadeus.com/2010/06/ServiceBookAndPrice_v1">
            #     <Service TID="R2" customerRefIDs="2" segmentRefIDs="1 2">
            #         <identifier RFIC="C" RFISC="0C1" Code="XBAG" bookingMethod="1"/>
            #         <serviceProvider code="UK"/>
            #         <Parameters Name="WVAL" ProviderCode="UK">15</Parameters>
            #     </Service>
            # </Product>
    
    xml_body+="""
            </AMA_ServiceBookPriceServiceRQ>
        </soap:Body>
            """
    return xml_body


def add_baggage(session_id,base_url,credentials,segments,pax_list):
    api_key = "Service_BookPriceService_1.1"
    header = create_followup_header(base_url,credentials,api_key)
    body = create_baggage_body( pax_list,segments)

    soap_message = create_soap_envelope(header, body)
    url = base_url
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(url, data=soap_message, headers=headers)
    data_dict = xmltodict.parse(response.text)
    PNRADD_21_1_1A = clean_keys(data_dict)
    status =  "soap_Fault" not in PNRADD_21_1_1A.get("soap_Envelope").get("soap_Body")

    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
    "payload":soap_message,"api":"hold","url":base_url,"response":{"status":status,"data":response.text},"misc":"baggage"}
    api_logs_to_mongo(log)
    return PNRADD_21_1_1A


def create_TFOPCQ_19_2_1A_body(payment_type="Cash", reference_id=None, payment_reference=None, ref_qualifier=None):

    if payment_type.upper() == "CASH":
        mop_details = """
            <fopReference>
            </fopReference>
            <mopDescription>
                <fopSequenceNumber>
                    <sequenceDetails>
                        <number>1</number>
                    </sequenceDetails>
                </fopSequenceNumber>
                <mopDetails>
                    <fopPNRDetails>
                        <fopDetails>
                            <fopCode>CASH</fopCode>
                        </fopDetails>
                    </fopPNRDetails>
                </mopDetails>
            </mopDescription>
        """
    elif payment_type.upper() == "CREDIT" and reference_id:
        mop_details = f"""
            <fopReference>
            </fopReference>
            <mopDescription>
                <fopSequenceNumber>
                    <sequenceDetails>
                        <number>1</number>
                    </sequenceDetails>
                </fopSequenceNumber>
                <mopDetails>
                    <fopPNRDetails>
                        <fopDetails>
                            <fopCode>CC</fopCode>
                        </fopDetails>
                        <paymentRef>
                            <refDetails>
                                <refQualifier>PM</refQualifier>
                                <refNumber>{payment_reference if payment_reference else ""}</refNumber>
                            </refDetails>
                        </paymentRef>
                    </fopPNRDetails>
                </mopDetails>
            </mopDescription>
        """
    else:
        raise ValueError("Invalid payment_type or missing reference_id for Credit")
        

    body = f"""<soap:Body>
            <FOP_CreateFormOfPayment xmlns="http://webservices.amadeus.com/TFOPCQ_19_2_1A">
                <transactionContext>
                    <transactionDetails>
                        <code>FP</code>
                    </transactionDetails>
                </transactionContext>
                <fopGroup>
                    {mop_details}
                </fopGroup>
            </FOP_CreateFormOfPayment>
            </soap:Body>"""
    
    return body

def add_form_of_payment(session_id,base_url,credentials):
    api_key = "TFOPCQ_19_2_1A"
    header = create_followup_header(base_url,credentials,api_key)
    
    body = create_TFOPCQ_19_2_1A_body(payment_type="Cash", reference_id=None, payment_reference=None, ref_qualifier=None)

    soap_message = create_soap_envelope(header, body)
    url = base_url
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(url, data=soap_message, headers=headers)
    data_dict = xmltodict.parse(response.text)
    TFOPCQ_19_2_1A = clean_keys(data_dict)
    status =  "soap_Fault" not in TFOPCQ_19_2_1A.get("soap_Envelope").get("soap_Body")

    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
    "payload":soap_message,"api":"hold","url":base_url,"response":{"status":status,"data":response.text},"misc":"FOP"}
    api_logs_to_mongo(log)
    return TFOPCQ_19_2_1A


def create_TPCBRQ_18_1_1A_body_for_upsell(other_company, currency_iso_code, fare_class, is_round_trip=False):
    references = """
                    <referenceDetails>
                        <type>S</type>
                        <value>1</value>
                    </referenceDetails>"""
    if is_round_trip:
        references+="""
                    <referenceDetails>
                        <type>S</type>
                        <value>2</value>
                    </referenceDetails>"""
    body = f"""
    <soap:Body>
        <Fare_PricePNRWithBookingClass>
            <pricingOptionGroup>
                <pricingOptionKey>
                    <pricingOptionKey>VC</pricingOptionKey>
                </pricingOptionKey>    
                <carrierInformation>
                    <companyIdentification>  
                        <otherCompany>{other_company}</otherCompany>
                    </companyIdentification>
                </carrierInformation>
            </pricingOptionGroup>
            <pricingOptionGroup>
                <pricingOptionKey>
                    <pricingOptionKey>FCO</pricingOptionKey>
                </pricingOptionKey>
                <currency>
                    <firstCurrencyDetails>
                        <currencyQualifier>FCO</currencyQualifier>
                        <currencyIsoCode>{currency_iso_code}</currencyIsoCode>
                    </firstCurrencyDetails>
                </currency>
            </pricingOptionGroup>
            """
    
    if fare_class:
        fare_class = fare_class.split("_")
        if fare_class[0] !="":
            body += f"""
            <pricingOptionGroup>
                <pricingOptionKey>
                    <pricingOptionKey>PFF</pricingOptionKey>
                </pricingOptionKey>
                <optionDetail>
                    <criteriaDetails>
                        <attributeType>FF</attributeType>
                        <attributeDescription>{fare_class[0]}</attributeDescription>
                    </criteriaDetails>
                </optionDetail>
                <paxSegTstReference>
                    {references}
                </paxSegTstReference>
            </pricingOptionGroup>
        """
    body+="""
        </Fare_PricePNRWithBookingClass>
    </soap:Body>"""
    return body



def add_upsell(session_id,base_url,credentials,fare_class,validating_carrier,currency_iso_code,is_round_trip):
    api_key = "TPCBRQ_18_1_1A"
    header = create_followup_header(base_url,credentials,api_key)
    
    body = create_TPCBRQ_18_1_1A_body_for_upsell(validating_carrier, currency_iso_code, fare_class, is_round_trip)

    soap_message = create_soap_envelope(header, body)
    url = base_url
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(url, data=soap_message, headers=headers)
    data_dict = xmltodict.parse(response.text)
    TPCBRQ_18_1_1A = clean_keys(data_dict)
    status =  "soap_Fault" not in TPCBRQ_18_1_1A.get("soap_Envelope").get("soap_Body")

    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
    "payload":soap_message,"api":"hold","url":base_url,"misc":"upsell","response":{"status":status,"data":response.text}}
    api_logs_to_mongo(log)
    return TPCBRQ_18_1_1A






def create_TPCBRQ_18_1_1A_body(other_company, currency_iso_code,reference_list= None): #Fare_PricePNRWithBookingClass
    if reference_list:
        soap_body = ""
        for reference  in reference_list:
            soap_body += f"""
                    <pricingOptionGroup>
                        <pricingOptionKey>
                        <pricingOptionKey>SEL</pricingOptionKey>
                        </pricingOptionKey>
                        <paxSegTstReference>
                        <referenceDetails>
                            <type>{reference[0]["qualifier"][0]}</type>
                            <value>{reference[0]["number"]}</value>
                        </referenceDetails>
                        <referenceDetails>
                            <type>{reference[1]["qualifier"][0]}</type>
                            <value>{reference[1]["number"]}</value>
                        </referenceDetails>
                        </paxSegTstReference>
                    </pricingOptionGroup>
                    """
    else:
        soap_body = ""
    soap_body = ""

    body = f"""<soap:Body>
        <Fare_PricePNRWithBookingClass>
            {soap_body}
            <pricingOptionGroup>
            <pricingOptionKey>
              <pricingOptionKey>RP</pricingOptionKey>
            </pricingOptionKey>
          </pricingOptionGroup>
            <pricingOptionGroup>
            <pricingOptionKey>
              <pricingOptionKey>RU</pricingOptionKey>
            </pricingOptionKey>
          </pricingOptionGroup>
          """
    if other_company:
        body+=f"""
            <pricingOptionGroup>
                <pricingOptionKey>
                <pricingOptionKey>VC</pricingOptionKey>
                </pricingOptionKey>
                <carrierInformation>
                <companyIdentification>  
                    <otherCompany>{other_company}</otherCompany>
                </companyIdentification>
                </carrierInformation>
            </pricingOptionGroup>
                    """
    body+=f"""
          <pricingOptionGroup>
            <pricingOptionKey>
              <pricingOptionKey>FCO</pricingOptionKey>
            </pricingOptionKey>
            <currency>
              <firstCurrencyDetails>
                <currencyQualifier>FCO</currencyQualifier>
                <currencyIsoCode>{currency_iso_code}</currencyIsoCode>
              </firstCurrencyDetails>
            </currency>
          </pricingOptionGroup>
          <pricingOptionGroup>
            <pricingOptionKey>
              <pricingOptionKey>RLO</pricingOptionKey>
            </pricingOptionKey>
          </pricingOptionGroup>
        </Fare_PricePNRWithBookingClass>
      </soap:Body>"""

    return body

def repricing_with_pnr(session_id,base_url,credentails,data):
    api_key = "TPCBRQ_18_1_1A"
    other_company = data.get("other_company")
    currency_iso_code = data.get("currency_iso_code")
    header = create_followup_header(base_url,credentails,api_key)
    body = create_TPCBRQ_18_1_1A_body(other_company,currency_iso_code,data.get("reference"))
    soap_message = create_soap_envelope(header, body)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(base_url, data=soap_message, headers=headers)

    data_dict = xmltodict.parse(response.text)
    cleaned_data = clean_keys(data_dict)
    status =  "soap_Fault" not in cleaned_data.get("soap_Envelope").get("soap_Body")

    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
    "payload":soap_message,"api":"hold","url":base_url,"misc":"repricing","response":{"status":status,"data":response.text}}
    api_logs_to_mongo(log)
    return cleaned_data

def create_TAUTCQ_04_1_1A_body(fareList): #Ticket_CreateTSTFromPricing
    body = """
            <soap:Body>
            <Ticket_CreateTSTFromPricing>"""
    for x in fareList:
        ref = x.get("fareReference")
        body += f""" 
                  <psaList>
                      <itemReference>
                        <referenceType>{ref['referenceType']}</referenceType>
                        <uniqueReference>{ref['uniqueReference']}</uniqueReference>
                      </itemReference>
                  </psaList>"""
    body+="""</Ticket_CreateTSTFromPricing>
                </soap:Body>"""
    return body

def create_ticket(session_id,base_url,credentails,fareList):
    api_key = "TAUTCQ_04_1_1A"
    header = create_followup_header(base_url,credentails,api_key)
    body = create_TAUTCQ_04_1_1A_body(fareList)
    soap_message = create_soap_envelope(header, body)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(base_url, data=soap_message, headers=headers)


    data_dict = xmltodict.parse(response.text)
    cleaned_data = clean_keys(data_dict)
    status =  "soap_Fault" not in cleaned_data.get("soap_Envelope").get("soap_Body")

    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
    "payload":soap_message,"api":"hold","url":base_url,"misc":"create_ticket","response":{"status":status,"data":response.text}}
    api_logs_to_mongo(log)
    return cleaned_data

def create_PNRADD_21_1_1A_permission(comment): #PNR_AddMultiElements
    soap_body = f"""
    <soap:Body>
    <PNR_AddMultiElements>
        <pnrActions>
            <optionCode>20</optionCode>
        </pnrActions>
        <dataElementsMaster>
            <marker1/>
            <dataElementsIndiv>
                <elementManagementData>
                    <segmentName>ES</segmentName>
                </elementManagementData>
                <pnrSecurity>
                    <security>
                        <identification>DEL3C2XO</identification>
                        <accessMode>B</accessMode>
                    </security>
                    <indicator>P</indicator>
                </pnrSecurity>
            </dataElementsIndiv>
        </dataElementsMaster>
    </PNR_AddMultiElements>
    </soap:Body>
    """

    return soap_body

def add_permission(base_url,credentails,comment):
    api_key = "PNRADD_21_1_1A"

    header = create_followup_header(base_url,credentails,api_key)
    body = create_PNRADD_21_1_1A_permission(comment)
    soap_message = create_soap_envelope(header, body)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(base_url, data=soap_message, headers=headers)


    data_dict = xmltodict.parse(response.text)
    cleaned_data = clean_keys(data_dict)
    status =  "soap_Fault" not in cleaned_data.get("soap_Envelope").get("soap_Body")

    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
    "payload":soap_message,"api":"hold","url":base_url,"misc":"permission","response":{"status":status,"data":response.text}}
    api_logs_to_mongo(log)
    return cleaned_data


def create_PNRADD_21_1_1A_closing_body(comment): #PNR_AddMultiElements
    soap_body = f"""
    <soap:Body>
    <PNR_AddMultiElements>
      <pnrActions>
        <optionCode>11</optionCode>
      </pnrActions>
      <dataElementsMaster>
        <marker1 />
        <dataElementsIndiv>
          <elementManagementData>
            <segmentName>RF</segmentName>
          </elementManagementData>
          <freetextData>
            <freetextDetail>
              <subjectQualifier>3</subjectQualifier>
              <type>P22</type>
            </freetextDetail>
            <longFreetext>{comment}</longFreetext>
          </freetextData>
        </dataElementsIndiv>
      </dataElementsMaster>
    </PNR_AddMultiElements>
    </soap:Body>
    """

    return soap_body

def close_PNR(session_id,base_url,credentails,comment):
    api_key = "PNRADD_21_1_1A"

    header = create_followup_header(base_url,credentails,api_key)
    body = create_PNRADD_21_1_1A_closing_body(comment)
    soap_message = create_soap_envelope(header, body)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(base_url, data=soap_message, headers=headers)


    data_dict = xmltodict.parse(response.text)
    cleaned_data = clean_keys(data_dict)
    status =  "soap_Fault" not in cleaned_data.get("soap_Envelope").get("soap_Body")

    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
    "payload":soap_message,"api":"hold","url":base_url,"misc":"close","response":{"status":status,"data":response.text}}
    api_logs_to_mongo(log)
    return cleaned_data

def create_TTKTIQ_15_1_1A_body(indicator="ET"): #DocIssuance_IssueTicket
    body = f"""
          <soap:Body>
            <DocIssuance_IssueTicket>
              <optionGroup>
                <switches>
                  <statusDetails>
                    <indicator>{indicator}</indicator>
                  </statusDetails>
                </switches>
              </optionGroup>
            </DocIssuance_IssueTicket>
          </soap:Body>
            
            """
    return body

def issue_Ticket(session_id,base_url,credentails,indicator):
    api_key = "TTKTIQ_15_1_1A"

    header = create_followup_header(base_url,credentails,api_key)
    body = create_TTKTIQ_15_1_1A_body(indicator)
    soap_message = create_soap_envelope(header, body)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(base_url, data=soap_message, headers=headers)


    data_dict = xmltodict.parse(response.text)
    cleaned_data = clean_keys(data_dict)
    status =  "soap_Fault" not in cleaned_data.get("soap_Envelope").get("soap_Body")

    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
    "payload":soap_message,"api":"ticket","url":base_url,"misc":"issue","response":{"status":status,"data":response.text}}
    api_logs_to_mongo(log)
    return cleaned_data

def create_PNRRET_21_1_1A_body(PNR): #PNR_Retrieve
    body = f"""
            <soap:Body>
          <PNR_Retrieve>
            <retrievalFacts>
              <retrieve>
                <type>2</type>
              </retrieve>
              <reservationOrProfileIdentifier>
                <reservation>
                  <controlNumber>{PNR}</controlNumber>
                </reservation>
              </reservationOrProfileIdentifier>
            </retrievalFacts>
          </PNR_Retrieve>
        </soap:Body>
            
            """
    return body

def import_pnr_data(session_id,base_url,credentails,PNR,first_time =True):
    api_key = "PNRRET_21_1_1A"
    if first_time:
        header = create_first_soap_header(base_url,credentails,api_key)
    else:
        header = create_followup_header(base_url,credentails,api_key)

    body = create_PNRRET_21_1_1A_body(PNR)
    soap_message = create_soap_envelope(header, body)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(base_url, data=soap_message, headers=headers)


    data_dict = xmltodict.parse(response.text)
    cleaned_data = clean_keys(data_dict)
    status =  "soap_Fault" not in cleaned_data.get("soap_Envelope").get("soap_Body")

    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
    "payload":soap_message,"api":"ticket","url":base_url,"misc":"import","response":{"status":status,"data":response.text}}
    api_logs_to_mongo(log)
    return cleaned_data,soap_message

def create_VLSSOQ_04_1_1A_body(): #Security_SignOut
    return """
    <soap:Body>
        <Security_SignOut />
    </soap:Body>"""

def signout(session_id,base_url,credentails):
    api_key = "VLSSOQ_04_1_1A"
    header = create_followup_header(base_url,credentails,api_key)
    body = create_VLSSOQ_04_1_1A_body()
    soap_message = create_soap_envelope(header, body)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"http://webservices.amadeus.com/{api_key}"
    }
    response = requests.post(base_url, data=soap_message, headers=headers)


    data_dict = xmltodict.parse(response.text)
    cleaned_data = clean_keys(data_dict)
    status =  "soap_Fault" not in cleaned_data.get("soap_Envelope").get("soap_Body")

    log = {"request_type":"POST","vendor":"Amadeus","headers":headers,"session_id":session_id,
    "payload":soap_message,"api":"hold","url":base_url,"misc":"signout","response":{"status":status,"data":response.text}}
    api_logs_to_mongo(log)
    return cleaned_data

def api_logs_to_mongo(log):
    mongo_handler.Mongo().log_vendor_api(log)
