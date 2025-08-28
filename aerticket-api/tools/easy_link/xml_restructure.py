import xml.etree.ElementTree as ET
import html
from html import unescape

class XMLData:
    def __init__(self) -> None:
        self.response = None # call this to get full response from api provider
        self.status = None # call this for api status
        self.api_status_code = None # call this to know api providers status code
        self.status_code = None # this is  custom status code to handle errors in our code 200 = 'success' 400 = 'failure'
        self.error = None # this will show error message  from api if there is  else None
        self.message = None # this will show the message of api 
        self.data = {}
        

    @classmethod
    def create_customer_response(cls,xml_response):
        
        instance = cls()
        instance.api_status_code = xml_response.status_code
        xml_response= xml_response.text
        root = ET.fromstring(xml_response)
        inner_xml = root.text
        instance.response = inner_xml
        inner_root = ET.fromstring(inner_xml)
        cust_element = inner_root.find('cust')
        if cust_element is not None and cust_element.get('Status') == 'False':
            instance.status =cust_element.get('Status')
            instance.error = cust_element.get('Desc')
            instance.status_code = 400 
        else:
            instance.status_code = 200 
            instance.status =cust_element.get('Status')
            account_code = cust_element.get("AcCode")
            account_name = cust_element.get("AcName")
            instance.data.update({"account_code":account_code, "account_name":account_name})
        return instance
    
    @classmethod
    def update_limit_response(cls,xml_response):
        instance = cls()
        instance.api_status_code = xml_response.status_code
        xml_response= xml_response.text
        root = ET.fromstring(xml_response)
        inner_xml = root.text
        instance.response = inner_xml
        inner_root = ET.fromstring(inner_xml)
        instance.error = inner_xml
        if "Error" in  inner_root.text or "False" in inner_root.text:
            instance.status_code = 400
            instance.error = inner_root.text
        else:
            instance.status_code = 200
            instance.message = inner_root.text
            instance.data.update({"status":True})
        return instance
    


    @classmethod
    def get_credit_limit_response(cls, xml_response):
        instance = cls()
        instance.api_status_code = xml_response.status_code
        xml_text = xml_response.text
        instance.response = xml_text
        root = ET.fromstring(xml_text)
        if "Error" in  root.text:
            instance.status_code = 400
            instance.error = root.text
        else:
            instance.status_code = 200
            instance.message = root.text
            limit_root = ET.fromstring(root.text)
            instance.data.update(limit_root.attrib)
        return instance
    
    @classmethod
    def set_temporary_credit_limit_response(cls,xml_response):
            instance = cls()
            instance.api_status_code = xml_response.status_code
            xml_response= xml_response.text
            root = ET.fromstring(xml_response)
            inner_xml = root.text
            instance.response = inner_xml
            inner_root = ET.fromstring(inner_xml)
            if "Error" in  inner_root.text:
                instance.status_code = 400
                instance.error = inner_root.text
            else:
                instance.status_code = 200
                instance.message = inner_root.text
                instance.data.update({"status":True})
            return instance
    
    @classmethod
    def remove_temporary_credit_limit_response(cls,xml_response):
            instance = cls()
            instance.api_status_code = xml_response.status_code
            xml_response= xml_response.text
            root = ET.fromstring(xml_response)
            inner_xml = root.text
            instance.response = inner_xml
            inner_root = ET.fromstring(inner_xml)
            if "Error" in  inner_root.text:
                instance.status_code = 400
                instance.error = inner_root.text
            else:
                instance.status_code = 200
                instance.message = inner_root.text
                instance.data.update({"status":True})
            return instance
    
    @classmethod
    def get_ledger_accounts_response(cls,xml_response):
            instance = cls()
            instance.api_status_code = xml_response.status_code
            xml_response= xml_response.text
            root = ET.fromstring(xml_response)
            inner_xml = root.text
            
            instance.response = inner_xml

            inner_root = ET.fromstring(inner_xml)

            error_element = inner_root.find('err')
            if error_element is not None:
                instance.status_code = 400
                instance.error = inner_xml
            else:
                instance.status_code = 200
                unescaped_xml = unescape(xml_response)

                # Step 2: Extract the XML inside the <string> tag
                start_tag = "<RESULT>"
                end_tag = "</RESULT>"
                start = unescaped_xml.find(start_tag)
                end = unescaped_xml.find(end_tag) + len(end_tag)
                xml_content = unescaped_xml[start:end]

                # Step 3: Parse the XML content
                root = ET.fromstring(xml_content)

                # Step 4: Convert XML to dictionary
                result_dict = {"RESULT": []}
                for txn in root:
                    txn_dict = txn.attrib
                    result_dict["RESULT"].append(txn_dict)

                # Output the dictionary
                instance.data.update(result_dict)
                instance.data.update({"status":"true"})
            return instance
    

    @classmethod

    def get_account_detail_response(cls,xml_response):
            instance = cls()
            instance.api_status_code = xml_response.status_code
            xml_response= xml_response.text

            if "Error" in xml_response:
               
                instance.status_code = 400
                instance.error = xml_response
            else:
       
                root = ET.fromstring(xml_response)
                inner_xml = root.text
                
                instance.response = inner_xml

                inner_root = ET.fromstring(inner_xml)

                error_element = inner_root.find('err')
                instance.status_code = 200
                unescaped_xml = unescape(xml_response)

                # Step 2: Extract the XML inside the <string> tag
                start_tag = "<RESULT>"
                end_tag = "</RESULT>"
                start = unescaped_xml.find(start_tag)
                end = unescaped_xml.find(end_tag) + len(end_tag)
                xml_content = unescaped_xml[start:end]

                # Step 3: Parse the XML content
                root = ET.fromstring(xml_content)

                # Step 4: Convert XML to dictionary
                result_dict = {"RESULT": []}
                for txn in root:
                    txn_dict = txn.attrib
                    result_dict["RESULT"].append(txn_dict)

                # Output the dictionary
                instance.data.update(result_dict)
                instance.data.update({"status":"true"})
            return instance
    
    @classmethod
    def get_analysis_response(cls,xml_response):
            instance = cls()
            instance.api_status_code = xml_response.status_code
            xml_response= xml_response.text

            if "Error" in xml_response:
               
                instance.status_code = 400
                instance.error = xml_response
            else:
       
                root = ET.fromstring(xml_response)
                inner_xml = root.text
                
                instance.response = inner_xml

                inner_root = ET.fromstring(inner_xml)

                error_element = inner_root.find('err')
                instance.status_code = 200
                unescaped_xml = unescape(xml_response)

                # Step 2: Extract the XML inside the <string> tag
                start_tag = "<RESULT>"
                end_tag = "</RESULT>"
                start = unescaped_xml.find(start_tag)
                end = unescaped_xml.find(end_tag) + len(end_tag)
                xml_content = unescaped_xml[start:end]

                # Step 3: Parse the XML content
                root = ET.fromstring(xml_content)

                # Step 4: Convert XML to dictionary
                result_dict = {"RESULT": []}
                for txn in root:
                    txn_dict = txn.attrib
                    result_dict["RESULT"].append(txn_dict)

                # Output the dictionary
                instance.data.update(result_dict)
                instance.data.update({"status":"true"})
            return instance