from Crypto.Cipher import AES
import base64
import xmltodict
import secrets
import string
import requests, os
from Crypto.Util.Padding import pad
import requests,json
from requests.auth import HTTPBasicAuth
from vendors.insurance import mongo_handler
import xml.etree.ElementTree as ET
from xml.dom import minidom

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

def encrypt_xml_create_policy(xml_data, sign, reference):
    print(12,xml_data)
    print(sign, reference)
    aes_key = sign.encode("ascii")[:32]
    iv = reference.encode("ascii")[:16]

    cipher = AES.new(aes_key, AES.MODE_CBC, iv)

    padded_data = pad(xml_data.encode("ascii"), AES.block_size)

    encrypted_data = cipher.encrypt(padded_data)

    return base64.b64encode(encrypted_data).decode("utf-8")

def generate_aspnet_session_id(length=24):
    # Define the allowed characters: lowercase letters and digits.
    characters = string.ascii_lowercase + string.digits
    # Generate a random session id of the specified length.
    session_id = ''.join(secrets.choice(characters) for _ in range(length))
    return session_id

def book(base_url,credentials,data,booking_id):

    # xml_data = dict_to_xml(data).strip()
    # print("xml_data",xml_data)
    xml_data = str(dict_to_xml_str(data, root_tag=None).strip())
    
    encrypted_data = encrypt_xml_create_policy(xml_data,credentials.get('sign'),credentials.get('ref'))
    url = base_url+"/CreatePolicy"

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': 'ASP.NET_SessionId='+str(generate_aspnet_session_id())
    }
    payload = {"Data": encrypted_data, "Ref": credentials.get('ref')}
    print("url",url)
    print("headers",headers)
    print("payload",payload)
    log = {"request_type":"POST","vendor":"Asego","headers":headers,
            "payload":payload,"xml_data":xml_data,"api":"book","url":url,"booking_id":booking_id}
    try:
        response = requests.post(url,headers=headers,data=payload)
        response_text = response.text 
        print("46",response_text)
        data_dict = xmltodict.parse(response.text)
        cleaned_data = clean_keys(data_dict)
        log["response"] = {"status":True,"data":response_text}
        api_logs_to_mongo(log)
        return cleaned_data
    except Exception as e:
        print(f"Error saving create policy response: {e}")
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None


def endorse(base_url,credentials,data,booking_id):
    xml_data = str(dict_to_xml_str(data, root_tag=None).strip())
    
    encrypted_data = encrypt_xml_create_policy(xml_data,credentials.get('sign'),credentials.get('ref'))
    url = base_url+"/EndorsePolicy"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': 'ASP.NET_SessionId='+str(generate_aspnet_session_id())
    }
    payload = {"Data": encrypted_data, "Ref": credentials.get('ref')}
    print("url",url)
    print("headers",headers)
    print("payload",payload)
    log = {"request_type":"POST","vendor":"Asego","headers":headers,
            "payload":payload,"xml_data":xml_data,"api":"cancel","url":url,"booking_id":booking_id}
    try:
        response = requests.post(url,headers=headers,data=payload)
        response_text = response.text 
        print("46",response_text)
        aes_key = credentials.get('sign').encode("ascii")[:32]
        iv = credentials.get('ref').encode("ascii")[:16]
        encrypted_b64 = response_text
        ciphertext = base64.b64decode(encrypted_b64)
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        plaintext_padded = cipher.decrypt(ciphertext)

        pad_len = plaintext_padded[-1]                            # last byte value is number of padding bytes
        plaintext_bytes = plaintext_padded[:-pad_len]             # slice off the padding bytes
        plaintext = plaintext_bytes.decode('utf-8', errors='ignore')  # decode to string (XML/JSON data)

        print("Decrypted response:", plaintext)
        data_dict = xmltodict.parse(plaintext)
        cleaned_data = clean_keys(data_dict)
        log["response"] = {"status":True,"data":plaintext}
        api_logs_to_mongo(log)
        return cleaned_data
    except Exception as e:
        print(f"Error saving create policy response: {e}")
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None


def cancel(base_url,credentials,data,booking_id):
    xml_data = str(dict_to_xml_str(data, root_tag=None).strip())
    
    encrypted_data = encrypt_xml_create_policy(xml_data,credentials.get('sign'),credentials.get('ref'))
    url = base_url+"/CancelCertificate"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': 'ASP.NET_SessionId='+str(generate_aspnet_session_id())
    }
    payload = {"Data": encrypted_data, "Ref": credentials.get('ref')}
    print("url",url)
    print("headers",headers)
    print("payload",payload)
    log = {"request_type":"POST","vendor":"Asego","headers":headers,
            "payload":payload,"xml_data":xml_data,"api":"cancel","url":url,"booking_id":booking_id}
    try:
        response = requests.post(url,headers=headers,data=payload)
        response_text = response.text 
        print("46",response_text)
        data_dict = xmltodict.parse(response_text)
        cleaned_data = clean_keys(data_dict)
        log["response"] = {"status":True,"data":response_text}
        api_logs_to_mongo(log)
        return cleaned_data
    except Exception as e:
        print(f"Error saving create policy response: {e}")
        log["response"] = {"status":False,"data":str("e")}
        api_logs_to_mongo(log)
        return None       
    

def dict_to_etree(data, tag=None):
    """
    Recursively converts a dictionary (with special handling for keys starting with '@' for attributes
    and '#text' for element text) into an ElementTree Element.
    If no tag is provided, a dummy root 'root' element is created.
    """
    if tag is None:
        # No tag provided; create a dummy root element and attach all top-level items as children.
        root = ET.Element("root")
        if isinstance(data, dict):
            for key, value in data.items():
                child = dict_to_etree(value, tag=key)
                root.append(child)
        elif isinstance(data, list):
            # If data is a list, each item becomes a child with a default tag 'item'
            for item in data:
                child = dict_to_etree(item, tag="item")
                root.append(child)
        else:
            root.text = str(data)
        return root
    else:
        # Create an element with the specified tag.
        elem = ET.Element(tag)
        
        if isinstance(data, dict):
            # Process attributes: keys starting with '@' are treated as attributes.
            for key, value in data.items():
                if key.startswith("@"):
                    elem.set(key[1:], str(value))
            # Set the element's text if provided via '#text'
            if "#text" in data:
                elem.text = str(data["#text"])
            # Process all other keys as child elements.
            for key, value in data.items():
                if key.startswith("@") or key == "#text":
                    continue
                # If the value is a list, create multiple child elements with the same tag.
                if isinstance(value, list):
                    for item in value:
                        child = dict_to_etree(item, tag=key)
                        elem.append(child)
                else:
                    child = dict_to_etree(value, tag=key)
                    elem.append(child)
        elif isinstance(data, list):
            # If data is a list when a tag is provided, create multiple child elements.
            for item in data:
                child = dict_to_etree(item, tag=tag)
                elem.append(child)
        else:
            # For simple types, assign data to the element's text.
            elem.text = str(data)
        return elem

def dict_to_xml_str(data, root_tag=None, indent="  "):
    """
    Converts a dictionary to a pretty-printed XML string without an XML declaration.
    If a root_tag is provided it is used; otherwise, if the dictionary has a single key,
    that key is used as the root element.
    """
    # If no root tag provided and data is a dict with one top-level key, use that key.
    if root_tag is None and isinstance(data, dict) and len(data) == 1:
         root_tag = next(iter(data))
         data = data[root_tag]
    
    root = dict_to_etree(data, tag=root_tag)
    rough_string = ET.tostring(root, "utf-8")
    reparsed = minidom.parseString(rough_string)
    # Use documentElement's toprettyxml to avoid the XML declaration.
    xml_without_decl = reparsed.documentElement.toprettyxml(indent=indent)
    # Remove any extra blank lines.
    xml_lines = [line for line in xml_without_decl.split('\n') if line.strip()]
    return "\n".join(xml_lines)


def dict_to_xml(data, tag=None, indent=""):
    xml_str = ""
    indent = ""
    # If a tag is provided, create an opening tag.
    if tag is not None:
        if isinstance(data, dict):
            attrs = ""
            inner_text = ""
            children_str = ""
            for key, value in data.items():
                if key.startswith("@"):  # Process attributes.
                    attrs += f' {key[1:]}="{value}"'
                elif key == "#text":      # Process inner text.
                    inner_text = str(value)
                else:
                    if isinstance(value, list):
                        for item in value:
                            children_str += dict_to_xml(item, tag=key, indent=indent + "    ")
                    else:
                        children_str += dict_to_xml(value, tag=key, indent=indent + "    ")
            # If there are child elements, add a newline for readability.
            if children_str:
                xml_str += f"{indent}<{tag}{attrs}>\n{inner_text}{children_str}{indent}</{tag}>\n"
            else:
                xml_str += f"{indent}<{tag}{attrs}>{inner_text}</{tag}>\n"
        elif isinstance(data, list):
            # When data is a list, iterate over all items using the same tag.
            for item in data:
                xml_str += dict_to_xml(item, tag=tag, indent=indent)
        else:
            # For simple types, just output the text.
            xml_str += f"{indent}<{tag}>{data}</{tag}>\n"
    else:
        # If no tag is provided at the root, assume a dict or list.
        if isinstance(data, dict):
            for key, value in data.items():
                xml_str += dict_to_xml(value, tag=key, indent=indent)
        elif isinstance(data, list):
            for item in data:
                xml_str += dict_to_xml(item, tag=None, indent=indent)
        else:
            xml_str += f"{indent}{data}\n"
    
    return xml_str




def api_logs_to_mongo(log):
    mongo_handler.Mongo().log_vendor_api(log)