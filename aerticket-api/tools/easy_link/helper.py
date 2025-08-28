import re

def is_number_valid(number:str)-> bool:
    """ used to check if phone number contains country code"""
    if number.startswith("+") :
        return True
    elif number == None or number == "":
        return True
    

def is_email_valid(email:str)-> bool: 
    
    """ check if email is valid"""
    EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    return bool(EMAIL_REGEX.match(email)) or email is None