class CustomError(Exception):
    def __init__(self, message:str = "an error occoured in application"):
        self.message = message
        return super().__init__(self.message)
    
    def __str__(self):
        return f"custom_error: {self.message}"
    



class PhoneNumberError(Exception):
    def __init__(self, phone_number, message:str = "country code is needed in phone number -->"):
        self.message = message
        self.phone_number = phone_number
        return super().__init__(self.message)
    
    def _format_message(self) -> str:
        return f"{self.message}: '{self.phone_number}'"
    



class EmailValidationError(Exception):
    def __init__(self, email, message:str = "the email you entered is not valid -->"):
        self.message = message
        self.email = email
        return super().__init__(self.message)
    
    def _format_message(self) -> str:
        return f"{self.message}: '{self.email}'"