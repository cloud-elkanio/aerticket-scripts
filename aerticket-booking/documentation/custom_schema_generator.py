from drf_yasg.generators import OpenAPISchemaGenerator
from django.conf import settings

class CustomOpenAPISchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, *args, **kwargs):
        schema = super().get_schema(*args, **kwargs)
        schema["tags"] = [
            {"name": "Authentication", "description": "Endpoints for getting new Auth Token from Refresh Tokens"},
            {"name": "Health", "description": "Endpoint to check system health."},
            {"name": "Wallet", "description": "Endpoint to get the current Wallet details."},
            {"name": "Misc", "description": "Endpoints for flight-related functionalities."},
            {
                "name": "Flight Booking",
                "description": """
                    The Flight Booking API enables you to perform a wide range of operations related to flight bookings, fare management, and ticketing. This API is designed to streamline your travel booking experience and provide seamless integration for various flight-related functionalities.

                    ### Key Features:

                    1. **Search Flights**:
                    - Search for flights based on criteria such as:
                        - One-way
                        - Round trip
                        - International travel

                    2. **Get Fare Details**:
                    - Retrieve detailed fare breakdown for selected flights.

                    3. **Get Fare Rules**:
                    - Access fare rules, including cancellation and refund policies.

                    4. **Book Special Service Requests (SSR)**:
                    - Add extra services to your booking:
                        - Seat selection
                        - Meal preferences
                        - Additional baggage

                    5. **Hold Tickets**:
                    - Reserve tickets without immediate payment.

                    6. **Purchase Tickets**:
                    - Complete the booking by purchasing held tickets.

                    7. **Convert Hold to Ticket**:
                    - Finalize held bookings by converting them into confirmed tickets.

                    8. **Cancel Held Tickets**:
                    - Cancel tickets that are currently on hold.

                    This API simplifies the flight booking process by offering a comprehensive suite of features, ensuring a smooth and efficient integration with your travel application or system.

                    ---

                    ### Example Use Cases:
                    - A customer searching for round-trip flights from New York to London.
                    - Retrieving the rules for a refundable ticket.
                    - Booking a flight with additional baggage and preferred seating.
                    - Holding a ticket for later purchase.
                    - Converting a held ticket into a confirmed booking.

                    Refer to the endpoints below to explore the full capabilities of the Flight Search API.

                    ---

                    ### Enhancements

                    ![Flight Search Workflow Diagram](/static/images/flight_search.png)


                    ![Hold-Ticket Workflow Diagram](/static/images/Hold-Ticket_Workflow.png)
                    

                """
            },
        ]
         # Sort paths based on `operationId`
        sorted_paths = sorted(
            schema["paths"].items(),
            key=lambda item: (
                item[1].get("get", {}).get("operationId") or
                item[1].get("post", {}).get("operationId") or
                ""
            )
        )
        # Reassign the sorted paths to the schema
        schema["paths"] = dict(sorted_paths)
        if settings.FORCE_SCRIPT_NAME:
            schema.basePath = settings.FORCE_SCRIPT_NAME.rstrip('/')
        return schema
