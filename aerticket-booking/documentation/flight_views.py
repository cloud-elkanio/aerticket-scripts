from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated
from api.views import HealthCheckView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status

from vendors.flights.views import (
    CreateSessionView, GetFlightsView, GetFareDetails, AirPricing, FlightsSSR, CreateBooking,
    CheckHold, HoldBooking, PurchaseStatus, Purchase, Repricing, ConvertHoldtoTicket, 
    ReleaseHold, TicketStatus, CancellationCharges, CancelTicket,GetFareRule
)
from common.views import SearchAirport,CreditBalanceView, SearchAirline

from .authentication import OutApiJWTAuthentication

# Create your views here.

class OutAPIHealthCheckView(HealthCheckView):
    """
    A simple health check endpoint to verify if the service is reachable.
    Returns HTTP 200 OK if the service is up.
    """
    @swagger_auto_schema(
        operation_id="HealthCheck",
        operation_summary="Health Check",
        operation_description=(
            "Use this endpoint to verify that the service is up and running. "
            "It returns an HTTP 200 status code along with a simple JSON response."
        ),
        responses={
            200: openapi.Response(
                description="System is up and running",
                examples={
                    "application/json": {
                        "status": "ok",
                        "message": "System is healthy."
                    }
                }
            )
        },
        tags=["Health"],
    )

    def get(self, request, *args, **kwargs):
        return super().get(request,*args, **kwargs)
    
class OutAPISearchAirport(SearchAirport):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id="1_SearchAirport",
        operation_summary="1 - Search Airports",
        operation_description=(
            "Search for airports by code (exact or partial), airport name, or city. "
            "If a `search_key` is provided, the system first looks for **exact matches** by airport code (case-insensitive). If exact matches are found, those are returned first. "
            "Then it searches for **partial matches** (airport `code`, `name`, or `city` containing the `search_key`). "
            "Finally, it combines both results into one list, ordered such that exact matches appear first, followed by partial matches, limited by the `limit` parameter. "
            "If no `search_key` is provided, it simply returns the top `limit` airports."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="search_key",
                in_=openapi.IN_QUERY,
                description="Search string for code, airport name, or city (case-insensitive).",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                name="limit",
                in_=openapi.IN_QUERY,
                description="Number of records to return. Defaults to 10 if not provided or invalid.",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ],
        responses={
            200: openapi.Response(
                description="Successful retrieval of airports",
                # Option 1: Provide an example without a schema reference:
                examples={
                    "application/json": {
                    "status": True,
                    "message": "Airports retrieved successfully.",
                    "data": [
                        {
                            "name": "Chhatrapati Shivaji International Airport",
                            "code": "BOM",
                            "city": "Mumbai",
                            "country": "India",
                            "common": "BOM",
                            "latitude": 19.0901312,
                            "longitude": 72.86370318520977
                        }
                    ],
                    "errors": ""
                }
                }
                # Option 2: Provide a serializer schema:
                # schema=AirportSerializer(many=True)
            ),
            400: openapi.Response(
                description="Invalid request or error retrieving airports",
                examples={
                    "application/json": {
                        "status": False,
                        "message": "Error retrieving airports.",
                        "data": [],
                        "errors": "Error details..."
                    }
                }
            ),
        },
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Misc"],  # You can group endpoints by tags in Swagger
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class OutAPICreditBalanceView(CreditBalanceView):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="GetCreditBalance",
        operation_summary="Retrieve wallet credit balance",
        operation_description=(
            "Fetches the available credit balance and credit limit."
        ),
        responses={
            200: openapi.Response(
                description="Wallet Balance retrieved successfully",
                examples={
                    "application/json": {
                        "status": True,
                        "message": "Wallet Balance retrieved successfully.",
                        "data": {
                            "Available Balance": 5000.00,
                            "Credit Limit": 10000.00
                        },
                        "errors": ""
                    }
                }
            ),
            400: openapi.Response(
                description="Bad request (Error retrieving wallet balance)",
                examples={
                    "application/json": {
                        "status": False,
                        "message": "Error retrieving Wallet Balance. Please contact our customer support.",
                        "data": [],
                        "errors": "Detailed error message"
                    }
                }
            ),
        },
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Wallet"],  # You can group endpoints by tags in Swagger
        security=[{'Bearer': []}]
    )
    def get(self, request):
        return super().get(request)

class OutAPISearchAirline(SearchAirline):
    @swagger_auto_schema(
        operation_id="2_SearchAirline",
        operation_summary="2 - Search Airlines",
        operation_description=(
            "Fetch a list of airlines filtered by a search key in the name or code field. "
            "The results are prioritized by matches in the code field and are limited by the 'limit' query parameter."
        ),
        manual_parameters=[
            openapi.Parameter(
                "search_key", openapi.IN_QUERY, 
                description="Search term to filter airlines by name or code.", 
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "limit", openapi.IN_QUERY, 
                description="Number of results to return. Defaults to 10 if not provided or invalid.", 
                type=openapi.TYPE_INTEGER
            ),
        ],
        responses={
            200: openapi.Response(
                description="Successful retrieval of airports",
                # Option 1: Provide an example without a schema reference:
                examples={
                    "application/json": {
                    "status": True,
                    "message": "Airlines retrieved successfully.",
                    "data": [
                        {"name": "IndiGo",
                        "code": "6E"}
                    ],
                    "errors": ""
                }
                }
            ),
            400: openapi.Response(
                description="Invalid request or error retrieving airlines",
                examples={
                    "application/json": {
                        "status": False,
                        "message": "Error retrieving airlines.",
                        "data": [],
                        "errors": "Error details..."
                    }
                }
            )
        },
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Misc"],  # You can group endpoints by tags in Swagger
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class OutAPICreateSessionView(CreateSessionView):
    authentication_classes = [OutApiJWTAuthentication]  # Use a different authentication
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id="01_StartFlightSearch",
        operation_summary="01 - Start Flight Search",
        operation_description=(
            "This API initiates a flight search based on the provided details. "
            "The response includes a unique session_id that must be used for subsequent API calls."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "journey_type": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["One Way", "Round Trip", "Multi City"],
                    description="Type of journey: One Way, Round Trip, or Multi City."
                ),
                "journey_details": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "source_city": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Source city code (e.g., DEL for Delhi)."
                            ),
                            "destination_city": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Destination city code (e.g., BOM for Mumbai)."
                            ),
                            "travel_date": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                format="date",
                                description="Date of travel in the format DD-MM-YYYY."
                            ),
                        },
                        required=["source_city", "destination_city", "travel_date"]
                    ),
                    description="List of journey details, including source, destination, and travel date."
                ),
                "passenger_details": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "adults": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Number of adult passengers."
                        ),
                        "children": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Number of child passengers."
                        ),
                        "infants": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Number of infant passengers."
                        ),
                    },
                    required=["adults", "children", "infants"],
                    description="Passenger details including adults, children, and infants."
                ),
                "cabin_class": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["Economy", "Business Class", "Premium Economy"],
                    description="Cabin class for the journey."
                ),
                "fare_type": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["Regular", "Student", "Senior Citizen"],
                    description="Type of fare: Regular, Student, or Senior Citizen."
                ),
                "preffered_airline": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Preferred airline codes (e.g., 6E for IndiGo)."
                    ),
                    description="List of preferred airlines."
                ),
                "is_direct_flight": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description="Specify whether the search should only include direct flights."
                ),
            },
            required=["journey_type", "journey_details", "passenger_details", "cabin_class", "fare_type", "preffered_airline", "is_direct_flight"]
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "session_id": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        format="uuid",
                        description="Unique session ID generated for subsequent API calls."
                    ),
                    "status": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        enum=["success", "failure"],
                        description="Status of the API call."
                    ),
                },
                # required=["session_id", "status"]
            ),
            400: "Bad Request - Invalid input provided."
        },
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Flight Booking"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class OutAPIGetFlightsView(GetFlightsView):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    request_schema = openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "session_id": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format="uuid",
                            description="Unique identifier for the session",
                            example="56a53b93-154e-4902-a3e7-46759b23e875"
                        ),
                    },
                    required=["session_id"]
                )
    flight_segment_schema = openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "airlineCode": openapi.Schema(type=openapi.TYPE_STRING, description="Airline code", example="AI"),
                                "airlineName": openapi.Schema(type=openapi.TYPE_STRING, description="Airline name", example="Air India"),
                                "flightNumber": openapi.Schema(type=openapi.TYPE_STRING, description="Flight number", example="9491"),
                                "equipmentType": openapi.Schema(type=openapi.TYPE_STRING, description="Aircraft type", example="320"),
                                "departure": openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        "airportCode": openapi.Schema(type=openapi.TYPE_STRING, description="Airport code", example="COK"),
                                        "airportName": openapi.Schema(type=openapi.TYPE_STRING, description="Airport name", example="Cochin Internation Arpt"),
                                        "city": openapi.Schema(type=openapi.TYPE_STRING, description="City", example="Kochi"),
                                        "country": openapi.Schema(type=openapi.TYPE_STRING, description="Country", example="India"),
                                        "countryCode": openapi.Schema(type=openapi.TYPE_STRING, description="Country code", example="IN"),
                                        "terminal": openapi.Schema(type=openapi.TYPE_STRING, description="Terminal number", example="1"),
                                        "departureDatetime": openapi.Schema(type=openapi.FORMAT_DATETIME, description="Departure time", example="2025-01-15T09:05")
                                    }
                                ),
                                "arrival": openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        "airportCode": openapi.Schema(type=openapi.TYPE_STRING, description="Airport code", example="DEL"),
                                        "airportName": openapi.Schema(type=openapi.TYPE_STRING, description="Airport name", example="Delhi Indira Gandhi Intl"),
                                        "city": openapi.Schema(type=openapi.TYPE_STRING, description="City", example="Delhi"),
                                        "country": openapi.Schema(type=openapi.TYPE_STRING, description="Country", example="India"),
                                        "countryCode": openapi.Schema(type=openapi.TYPE_STRING, description="Country code", example="IN"),
                                        "terminal": openapi.Schema(type=openapi.TYPE_STRING, description="Terminal number", example="3"),
                                        "arrivalDatetime": openapi.Schema(type=openapi.FORMAT_DATETIME, description="Arrival time", example="2025-01-15T12:20")
                                    }
                                ),
                                "durationInMinutes": openapi.Schema(type=openapi.TYPE_INTEGER, description="Duration of the flight in minutes", example=195),
                                "stop": openapi.Schema(type=openapi.TYPE_INTEGER, description="Number of stops", example=1),
                                "cabinClass": openapi.Schema(type=openapi.TYPE_STRING, description="Cabin class", example="Economy"),
                                "fareBasisCode": openapi.Schema(type=openapi.TYPE_STRING, description="Fare basis code", example="SU1YXYII"),
                                "seatsRemaining": openapi.Schema(type=openapi.TYPE_INTEGER, description="Number of seats remaining", example=4),
                                "isRefundable": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Whether the flight is refundable", example=True),
                                "isChangeAllowed": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Whether changes are allowed", example=True),
                                "stopDetails": openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        "isLayover": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Indicates if it is a layover", example=True),
                                        "stopPoint": openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "airportCode": openapi.Schema(
                                                    type=openapi.TYPE_ARRAY,
                                                    items=openapi.Items(type=openapi.TYPE_STRING),
                                                    description="List of stop points by airport code",
                                                    example=["DEL"]
                                                )
                                            }
                                        )
                                    }
                                )
                            }
                        )
    response_schema = openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "flight_search_response": openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "COK_CCU_1501": openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=flight_segment_schema
                                    ),
                                    "itineraries": openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Items(type=openapi.TYPE_STRING),
                                        description="List of itineraries",
                                        example=["COK_CCU_1501"]
                                    ),
                                    "search_details": openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "flight_type": openapi.Schema(type=openapi.TYPE_STRING, description="Flight type", example="DOM"),
                                            "journey_type": openapi.Schema(type=openapi.TYPE_STRING, description="Journey type", example="One Way"),
                                            "journey_details": openapi.Schema(
                                                type=openapi.TYPE_ARRAY,
                                                items=openapi.Schema(
                                                    type=openapi.TYPE_OBJECT,
                                                    properties={
                                                        "source_city": openapi.Schema(type=openapi.TYPE_STRING, description="Source city", example="COK"),
                                                        "destination_city": openapi.Schema(type=openapi.TYPE_STRING, description="Destination city", example="CCU"),
                                                        "travel_date": openapi.Schema(type=openapi.TYPE_STRING, description="Travel date", example="15-01-2025")
                                                    }
                                                )
                                            ),
                                            "passenger_details": openapi.Schema(
                                                type=openapi.TYPE_OBJECT,
                                                properties={
                                                    "adults": openapi.Schema(type=openapi.TYPE_STRING, description="Number of adults", example="1"),
                                                    "children": openapi.Schema(type=openapi.TYPE_STRING, description="Number of children", example="0"),
                                                    "infants": openapi.Schema(type=openapi.TYPE_STRING, description="Number of infants", example="0")
                                                }
                                            ),
                                            "fare_type": openapi.Schema(type=openapi.TYPE_STRING, description="Fare type", example=""),
                                            "cabin_class": openapi.Schema(type=openapi.TYPE_STRING, description="Cabin class", example="Economy"),
                                            "preffered_airline": openapi.Schema(
                                                type=openapi.TYPE_ARRAY,
                                                items=openapi.Items(type=openapi.TYPE_STRING),
                                                description="Preferred airlines",
                                                example=[]
                                            ),
                                            "is_direct_flight": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Is it a direct flight", example=False)
                                        }
                                    ),
                                    "search_metadata": openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "error_status": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Error status", example=False),
                                            "is_complete": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Is search complete", example=True)
                                        }
                                    )
                                }
                            ),
                            "response_meta_data": openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "session_break": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Session break indicator", example=False),
                                    'info': openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="The detailed error will be shared here. This field will be available only if session_break is True",
                            ),
                                }
                            ),
                            "session_id": openapi.Schema(type=openapi.TYPE_STRING, format="uuid", description="Session ID", example="56a53b93-154e-4902-a3e7-46759b23e875")
                        },
                    )
    response_examples = {
                        "Standard Response": {
                                    "flight_search_response": {
                                        "COK_CCU_1501": [
                                        {
                                            "flightSegments": {
                                            "COK_CCU_1501": [
                                                {
                                                "airlineCode": "AI",
                                                "airlineName": "Air India",
                                                "flightNumber": "9491",
                                                "equipmentType": "320",
                                                "departure": {
                                                    "airportCode": "COK",
                                                    "airportName": "Cochin Internation Arpt",
                                                    "city": "Kochi",
                                                    "country": "India",
                                                    "countryCode": "IN",
                                                    "terminal": "1",
                                                    "departureDatetime": "2025-01-15T09:05"
                                                },
                                                "arrival": {
                                                    "airportCode": "DEL",
                                                    "airportName": "Delhi Indira Gandhi Intl",
                                                    "city": "Delhi",
                                                    "country": "India",
                                                    "countryCode": "IN",
                                                    "terminal": "3",
                                                    "arrivalDatetime": "2025-01-15T12:20"
                                                },
                                                "durationInMinutes": 195,
                                                "stop": 1,
                                                "cabinClass": "Economy",
                                                "fareBasisCode": "SU1YXYII",
                                                "seatsRemaining": 4,
                                                "isRefundable": True,
                                                "isChangeAllowed": True
                                                },
                                                {
                                                "airlineCode": "AI",
                                                "airlineName": "Air India",
                                                "flightNumber": "463",
                                                "equipmentType": "32N",
                                                "departure": {
                                                    "airportCode": "DEL",
                                                    "airportName": "Delhi Indira Gandhi Intl",
                                                    "city": "Delhi",
                                                    "country": "India",
                                                    "countryCode": "IN",
                                                    "terminal": "3",
                                                    "departureDatetime": "2025-01-15T18:10"
                                                },
                                                "arrival": {
                                                    "airportCode": "CCU",
                                                    "airportName": "Netaji Subhas Chandra Bose Intl",
                                                    "city": "Kolkata",
                                                    "country": "India",
                                                    "countryCode": "IN",
                                                    "terminal": "N/A",
                                                    "arrivalDatetime": "2025-01-15T20:25"
                                                },
                                                "durationInMinutes": 135,
                                                "stop": 1,
                                                "cabinClass": "Economy",
                                                "fareBasisCode": "SU1YXYII",
                                                "seatsRemaining": 4,
                                                "isRefundable": True,
                                                "isChangeAllowed": True,
                                                "stopDetails": {
                                                    "isLayover": True,
                                                    "stopPoint": {
                                                    "airportCode": [
                                                        "DEL"
                                                    ]
                                                    }
                                                }
                                                }
                                            ]
                                            },
                                            "segmentID": "VEN-041bacdb-7c53-4a45-931d-0225e8b73367_$_SEG-cf6dac05-be56-493f-abfa-68ac8a193a85",
                                            "offerFare": 13668.0,
                                            "Discount": 0.0,
                                            "publishFare": 13668.0,
                                            "currency": "INR"
                                        }
                                        ],
                                        "itineraries": [
                                        "COK_CCU_1501"
                                        ],
                                        "search_details": {
                                        "flight_type": "DOM",
                                        "journey_type": "One Way",
                                        "journey_details": [
                                            {
                                            "source_city": "COK",
                                            "destination_city": "CCU",
                                            "travel_date": "15-01-2025"
                                            }
                                        ],
                                        "passenger_details": {
                                            "adults": "1",
                                            "children": "0",
                                            "infants": "0"
                                        },
                                        "fare_type": "",
                                        "cabin_class": "Economy",
                                        "preffered_airline": [],
                                        "is_direct_flight": False
                                        },
                                        "search_metadata": {
                                        "error_status": False,
                                        "is_complete": True
                                        }
                                    },
                                    "response_meta_data": {
                                        "session_break": False
                                    },
                                    "session_id": "56a53b93-154e-4902-a3e7-46759b23e875"
                                    },
                    "Round Trip International Response": {
                                    "flight_search_response": {
                                        "DXB_LHR_1501_R_LHR_DXB_2201": [
                                        {
                                            "flightSegments": {
                                            "DXB_LHR_1501": [
                                                {
                                                "airlineCode": "AF",
                                                "airlineName": "Air France",
                                                "flightNumber": "659",
                                                "equipmentType": "77W",
                                                "departure": {
                                                    "airportCode": "DXB",
                                                    "airportName": "Dubai Intl Arpt",
                                                    "city": "Dubai",
                                                    "country": "United Arab Emirates",
                                                    "countryCode": "AE",
                                                    "terminal": "1",
                                                    "departureDatetime": "2025-01-15T11:00"
                                                },
                                                "arrival": {
                                                    "airportCode": "CDG",
                                                    "airportName": "Charles De Gaulle Intl Arpt",
                                                    "city": "Paris",
                                                    "country": "France",
                                                    "countryCode": "FR",
                                                    "terminal": "2E",
                                                    "arrivalDatetime": "2025-01-15T15:35"
                                                },
                                                "durationInMinutes": 455,
                                                "stop": 1,
                                                "cabinClass": "Economy",
                                                "fareBasisCode": "RGS0PBLA",
                                                "seatsRemaining": 9,
                                                "isRefundable": False,
                                                "isChangeAllowed": True
                                                },
                                                {
                                                "airlineCode": "AF",
                                                "airlineName": "Air France",
                                                "flightNumber": "1380",
                                                "equipmentType": "223",
                                                "departure": {
                                                    "airportCode": "CDG",
                                                    "airportName": "Charles De Gaulle Intl Arpt",
                                                    "city": "Paris",
                                                    "country": "France",
                                                    "countryCode": "FR",
                                                    "terminal": "2E",
                                                    "departureDatetime": "2025-01-15T21:00"
                                                },
                                                "arrival": {
                                                    "airportCode": "LHR",
                                                    "airportName": "Heathrow",
                                                    "city": "London",
                                                    "country": "United Kingdom",
                                                    "countryCode": "GB",
                                                    "terminal": "4",
                                                    "arrivalDatetime": "2025-01-15T21:25"
                                                },
                                                "durationInMinutes": 85,
                                                "stop": 1,
                                                "cabinClass": "Economy",
                                                "fareBasisCode": "RGS0PBLA",
                                                "seatsRemaining": 9,
                                                "isRefundable": False,
                                                "isChangeAllowed": True,
                                                "stopDetails": {
                                                    "isLayover": True,
                                                    "stopPoint": {
                                                    "airportCode": [
                                                        "CDG"
                                                    ]
                                                    }
                                                }
                                                }
                                            ],
                                            "LHR_DXB_2201": [
                                                {
                                                "airlineCode": "AF",
                                                "airlineName": "Air France",
                                                "flightNumber": "1681",
                                                "equipmentType": "223",
                                                "departure": {
                                                    "airportCode": "LHR",
                                                    "airportName": "Heathrow",
                                                    "city": "London",
                                                    "country": "United Kingdom",
                                                    "countryCode": "GB",
                                                    "terminal": "4",
                                                    "departureDatetime": "2025-01-22T09:00"
                                                },
                                                "arrival": {
                                                    "airportCode": "CDG",
                                                    "airportName": "Charles De Gaulle Intl Arpt",
                                                    "city": "Paris",
                                                    "country": "France",
                                                    "countryCode": "FR",
                                                    "terminal": "2E",
                                                    "arrivalDatetime": "2025-01-22T11:25"
                                                },
                                                "durationInMinutes": 85,
                                                "stop": 1,
                                                "cabinClass": "Economy",
                                                "fareBasisCode": "RGS0PBLA",
                                                "seatsRemaining": 9,
                                                "isRefundable": False,
                                                "isChangeAllowed": True
                                                },
                                                {
                                                "airlineCode": "AF",
                                                "airlineName": "Air France",
                                                "flightNumber": "662",
                                                "equipmentType": "77W",
                                                "departure": {
                                                    "airportCode": "CDG",
                                                    "airportName": "Charles De Gaulle Intl Arpt",
                                                    "city": "Paris",
                                                    "country": "France",
                                                    "countryCode": "FR",
                                                    "terminal": "2E",
                                                    "departureDatetime": "2025-01-22T13:35"
                                                },
                                                "arrival": {
                                                    "airportCode": "DXB",
                                                    "airportName": "Dubai Intl Arpt",
                                                    "city": "Dubai",
                                                    "country": "United Arab Emirates",
                                                    "countryCode": "AE",
                                                    "terminal": "1",
                                                    "arrivalDatetime": "2025-01-22T23:20"
                                                },
                                                "durationInMinutes": 405,
                                                "stop": 1,
                                                "cabinClass": "Economy",
                                                "fareBasisCode": "RGS0PBLA",
                                                "seatsRemaining": 9,
                                                "isRefundable": False,
                                                "isChangeAllowed": True,
                                                "stopDetails": {
                                                    "isLayover": True,
                                                    "stopPoint": {
                                                    "airportCode": [
                                                        "CDG"
                                                    ]
                                                    }
                                                }
                                                }
                                            ]
                                            },
                                            "segmentID": "VEN-041bacdb-7c53-4a45-931d-0225e8b73367_$_SEG-bb08b1fb-d97e-4361-b7a6-1ba2ec865d19",
                                            "offerFare": 90088.0,
                                            "Discount": 0.0,
                                            "publishFare": 90088.0,
                                            "currency": "INR"
                                        }
                                        ],
                                        "itineraries": [
                                        "DXB_LHR_1501_R_LHR_DXB_2201"
                                        ],
                                        "search_details": {
                                        "flight_type": "INT",
                                        "journey_type": "Round Trip",
                                        "journey_details": [
                                            {
                                            "source_city": "DXB",
                                            "destination_city": "LHR",
                                            "travel_date": "15-01-2025"
                                            },
                                            {
                                            "source_city": "LHR",
                                            "destination_city": "DXB",
                                            "travel_date": "22-01-2025"
                                            }
                                        ],
                                        "passenger_details": {
                                            "adults": 1,
                                            "children": 1,
                                            "infants": 1
                                        },
                                        "fare_type": "",
                                        "cabin_class": "Economy",
                                        "preffered_airline": [],
                                        "is_direct_flight": False
                                        },
                                        "search_metadata": {
                                        "error_status": False,
                                        "is_complete": True
                                        }
                                    },
                                    "response_meta_data": {
                                        "session_break": False
                                    },
                                    "session_id": "619d1617-d472-46c4-b41d-4d0290624fdb"
                                    }
                    }
    response_with_examples = openapi.Response(
                                description="A successful response with multiple examples. Change  'RESPONSE SCHEMA' from 'application/json' to view sample responses",
                                schema=response_schema,
                                examples=response_examples
                            )
    @swagger_auto_schema(
        operation_id="02_GetFlightSearchData",
        operation_summary="02 - Get Flight Search Data",
        operation_description=(
            "This endpoint allows users to search for flights based on their journey details and preferences. "
            "Pass a valid `session_id` in the request body to retrieve relevant flight search details. Continue "
            "calling this API until the `flight_search_response.search_metadata.is_complete` field in the response "
            "is `True`, ensuring that `flight_search_response.search_metadata.error_status` is `False` to confirm "
            "that no errors occurred during the search process. "
            "\n\nIf the session has expired, the `response_meta_data.session_break` field will be `True`. In such "
            "cases, you must redo the search with a new session and proceed accordingly. "
            "\n\nThe response includes two primary data structures: one specific to roundtrip international flights "
            "and another used for all other cases. Detailed information about available flights, including segments, "
            "durations, fares, and metadata, is provided for supported domestic and international journeys. "
            "Preferences like cabin class, direct flights, and preferred airlines can be specified in the search."
            ),
        request_body=request_schema,
        responses={200: response_with_examples},
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Flight Booking"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class OutAPIGetFareDetails(GetFareDetails):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="03_GetFareDetails",
        operation_summary="03 - Get Fare Details",
        operation_description=("Retrieve detailed fare information for a specific flight segment."
                               "This includes baggage allowance, fare breakdown, and rules."
                               "\n\nIf the session has expired, the `response_meta_data.session_break` field will be `True`. In such "
                                "cases, you must redo the search with a new session and proceed accordingly."),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'segment_id': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Unique identifier for the flight segment Can be found at segmentID in flight search details.",
                ),
                'session_id': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Unique identifier for the search session.",
                ),
            },
            required=['segment_id', 'session_id'],
            example={
                "segment_id": "VEN-041bacdb-7c53-4a45-931d-0225e8b73367_$_SEG-adf9c9ca-c097-4163-b66d-09cd3cc851f1",
                "session_id": "e5e65144-d057-43b7-9e25-72a054fedfe6",
            },
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'session_id': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Unique identifier for the search session.",
                    ),
                    'fareDetails': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'baggage': openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        'checkInBag': openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            description="Allowed check-in baggage weight. Example: '15 Kg'.",
                                        ),
                                        'cabinBag': openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            description="Allowed cabin baggage weight. Example: '7 Kg'.",
                                        ),
                                    },
                                ),
                                'fare_id': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Unique identifier for the fare. Example: 'FARE-5928c957-fa18-43ce-913d-fc707e203a74'.",
                                ),
                                'segment_id': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Identifier for the segment tied to the fare. Example: 'VEN-041bacdb-7c53-4a45-931d-0225e8b73367_$_SEG-adf9c9ca-c097-4163-b66d-09cd3cc851f1'.",
                                ),
                                'publishedFare': openapi.Schema(
                                    type=openapi.TYPE_NUMBER,
                                    format=openapi.FORMAT_FLOAT,
                                    description="Original published fare before discounts. Example: 3267.0.",
                                ),
                                'offeredFare': openapi.Schema(
                                    type=openapi.TYPE_NUMBER,
                                    format=openapi.FORMAT_FLOAT,
                                    description="Offered fare after applying discounts. Example: 3267.0.",
                                ),
                                'Discount': openapi.Schema(
                                    type=openapi.TYPE_NUMBER,
                                    format=openapi.FORMAT_FLOAT,
                                    description="Discount applied on the published fare. Example: 0.0.",
                                ),
                                'vendor_id': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Unique identifier for the vendor. Example: 'VEN-041bacdb-7c53-4a45-931d-0225e8b73367'.",
                                ),
                                'transaction_id': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Unique identifier for the transaction. Example: '4-2115714270_9DELBOMSG169~22086336692545787'.",
                                ),
                                'fareType': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Type of fare offered (e.g., 'SALE').",
                                ),
                                'uiName': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Name displayed in the UI for this fare type. Example: 'SALE'.",
                                ),
                                'fare_rule': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="HTML content of the fare rules including cancellation and date-change policies.",
                                ),
                                'currency': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Currency for the fare. Example: 'INR'.",
                                ),
                                'colour': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Color code associated with the fare type. Example: 'RED'.",
                                ),
                                'fareBreakdown': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'passengerType': openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                enum=["adults", "children", "infants"],
                                                description="Type of passenger (e.g., 'adults').",
                                            ),
                                            'baseFare': openapi.Schema(
                                                type=openapi.TYPE_NUMBER,
                                                format=openapi.FORMAT_FLOAT,
                                                description="Base fare for the passenger. Example: 1999.0.",
                                            ),
                                            'tax': openapi.Schema(
                                                type=openapi.TYPE_NUMBER,
                                                format=openapi.FORMAT_FLOAT,
                                                description="Tax applied to the fare. Example: 1268.0.",
                                            ),
                                        },
                                    ),
                                ),
                                'isRefundable': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(
                                        type=openapi.TYPE_BOOLEAN,
                                        description="Indicates whether the fare is refundable.",
                                    ),
                                ),
                            },
                        ),
                    ),
                    'response_meta_data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'session_break': openapi.Schema(
                                type=openapi.TYPE_BOOLEAN,
                                description="Indicates whether the session is broken. Example: True.",
                            ),
                            'info': openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="The detailed error will be shared here. This field will be available only if session_break is True",
                            ),
                        },
                    ),
                },
            ),
            400: "Bad Request - Invalid input data",
            500: "Internal Server Error",
        },
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Flight Booking"],  # You can group endpoints by tags in Swagger
    ) 
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class OutAPIAirPricing(AirPricing):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    flight_segment_schema = openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            additional_properties=openapi.Schema(  # Allows dynamic keys like DEL_BOM_1501
                                type=openapi.TYPE_ARRAY,  # Each key maps to a list of flight segments
                                items=openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        "airlineCode": openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            description="Code of the airline operating the flight.",
                                            example="SG"
                                        ),
                                        "airlineName": openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            description="Name of the airline operating the flight.",
                                            example="SpiceJet"
                                        ),
                                        "flightNumber": openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            description="Flight number assigned to the segment.",
                                            example="385"
                                        ),
                                        "equipmentType": openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            description="Aircraft type used for the flight.",
                                            example="737"
                                        ),
                                        "departure": openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "airportCode": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="IATA code of the departure airport.",
                                                    example="DEL"
                                                ),
                                                "airportName": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Name of the departure airport.",
                                                    example="Indira Gandhi Airport"
                                                ),
                                                "city": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="City of the departure airport.",
                                                    example="Delhi"
                                                ),
                                                "country": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Country of the departure airport.",
                                                    example="India"
                                                ),
                                                "countryCode": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="ISO country code of the departure airport.",
                                                    example="IN"
                                                ),
                                                "terminal": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Terminal number for departure.",
                                                    example="1D"
                                                ),
                                                "departureDatetime": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    format=openapi.FORMAT_DATETIME,
                                                    description="Scheduled date and time of departure.",
                                                    example="2025-01-15T05:25:00"
                                                )
                                            }
                                        ),
                                        "arrival": openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "airportCode": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="IATA code of the arrival airport.",
                                                    example="BOM"
                                                ),
                                                "airportName": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Name of the arrival airport.",
                                                    example="Chhatrapati Shivaji International Airport"
                                                ),
                                                "city": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="City of the arrival airport.",
                                                    example="Mumbai"
                                                ),
                                                "country": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Country of the arrival airport.",
                                                    example="India"
                                                ),
                                                "countryCode": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="ISO country code of the arrival airport.",
                                                    example="IN"
                                                ),
                                                "terminal": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Terminal number for arrival.",
                                                    example="1"
                                                ),
                                                "arrivalDatetime": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    format=openapi.FORMAT_DATETIME,
                                                    description="Scheduled date and time of arrival.",
                                                    example="2025-01-15T07:40:00"
                                                )
                                            }
                                        ),
                                        "durationInMinutes": openapi.Schema(
                                            type=openapi.TYPE_INTEGER,
                                            description="Duration of the flight segment in minutes.",
                                            example=135
                                        ),
                                        "stop": openapi.Schema(
                                            type=openapi.TYPE_INTEGER,
                                            description="Number of stops in the flight segment.",
                                            example=0
                                        ),
                                        "cabinClass": openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            description="Class of service for the flight segment.",
                                            example="Economy"
                                        ),
                                        "fareBasisCode": openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            description="Code representing the fare basis.",
                                            example="USAF"
                                        ),
                                        "seatsRemaining": openapi.Schema(
                                            type=openapi.TYPE_INTEGER,
                                            description="Number of seats remaining for the flight segment.",
                                            example=None
                                        ),
                                        "isRefundable": openapi.Schema(
                                            type=openapi.TYPE_BOOLEAN,
                                            description="Indicates whether the flight segment is refundable.",
                                            example=True
                                        ),
                                        "isChangeAllowed": openapi.Schema(
                                            type=openapi.TYPE_BOOLEAN,
                                            description="Indicates whether changes are allowed for the flight segment.",
                                            example=True
                                        )
                                    }
                                ),
                                description="List of flight segments for the itinerary."
                            ),
                            description="Dictionary of flight segments organized by itinerary keys like DEL_BOM_1501. Each key maps to a list of flight segments for that itinerary."
                        )

    fare_details_schema = openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        additional_properties=openapi.Schema(  # Allow dynamic keys for itineraries
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "fare_id": openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Unique identifier for the fare.",
                                    example="FARE-7d3c4229-fd00-4c85-9cf3-f3ac0430507b"
                                ),
                                "publishedFare": openapi.Schema(
                                    type=openapi.TYPE_NUMBER,
                                    format=openapi.FORMAT_FLOAT,
                                    description="Original fare price as published.",
                                    example=10935.6
                                ),
                                "offeredFare": openapi.Schema(
                                    type=openapi.TYPE_NUMBER,
                                    format=openapi.FORMAT_FLOAT,
                                    description="Discounted fare offered to the customer.",
                                    example=10746.38
                                ),
                                "Discount": openapi.Schema(
                                    type=openapi.TYPE_NUMBER,
                                    format=openapi.FORMAT_FLOAT,
                                    description="Discount amount applied to the published fare.",
                                    example=155.1604
                                ),
                                "vendor_id": openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Unique internal vendor ID",
                                    example="UUID"
                                ),
                                "transaction_id": openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Unique internal transaction ID",
                                    example="UUID"
                                ),
                                'fareType': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Type of fare offered (e.g., 'SALE').",
                                ),
                                "currency": openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Currency code for the fares.",
                                    example="INR"
                                ),
                                'colour': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Color code associated with the fare type. Example: 'RED'.",
                                ),
                                "fare_rule": openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="HTML-formatted string describing fare rules.",
                                    example="<h1>DEL - BOM</h1><br>The FareBasisCode is: USAF<br/>Changes and cancellations are permitted as per applicable rules and charges"
                                ),
                                "fareBreakdown": openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "passengerType": openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                description="Type of passenger (e.g., adults, children, infants).",
                                                example="adults"
                                            ),
                                            "baseFare": openapi.Schema(
                                                type=openapi.TYPE_NUMBER,
                                                format=openapi.FORMAT_FLOAT,
                                                description="Base fare price for the passenger type.",
                                                example=2800.0
                                            ),
                                            "tax": openapi.Schema(
                                                type=openapi.TYPE_NUMBER,
                                                format=openapi.FORMAT_FLOAT,
                                                description="Tax applied to the base fare.",
                                                example=1308.0
                                            ),
                                        },
                                    ),
                                    description="Breakdown of fares for each passenger type."
                                ),
                                "isRefundable": openapi.Schema(
                                    type=openapi.TYPE_BOOLEAN,
                                    description="Indicates whether the fare is refundable.",
                                    example=True
                                ),
                            },
                        ),
                        description="Details of fares for each itinerary. The keys represent dynamic itinerary identifiers such as DEL_BOM_1501."
                    )

    response_schema = openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "flight_air_pricing": openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "session_id": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Session ID of the current pricing session."
                            ),
                            "itineraries": openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="Identifiers for itineraries included in the response (e.g., DEL_BOM_1501)."
                                ),
                                description="List of itinerary identifiers for looping through flight details."
                            ),
                            'fareDetails': fare_details_schema,
                            "search_details": openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "flight_type": openapi.Schema(type=openapi.TYPE_STRING, description="Flight type", example="DOM"),
                                            "journey_type": openapi.Schema(type=openapi.TYPE_STRING, description="Journey type", example="One Way"),
                                            "journey_details": openapi.Schema(
                                                type=openapi.TYPE_ARRAY,
                                                items=openapi.Schema(
                                                    type=openapi.TYPE_OBJECT,
                                                    properties={
                                                        "source_city": openapi.Schema(type=openapi.TYPE_STRING, description="Source city", example="COK"),
                                                        "destination_city": openapi.Schema(type=openapi.TYPE_STRING, description="Destination city", example="CCU"),
                                                        "travel_date": openapi.Schema(type=openapi.TYPE_STRING, description="Travel date", example="15-01-2025")
                                                    }
                                                )
                                            ),
                                            "passenger_details": openapi.Schema(
                                                type=openapi.TYPE_OBJECT,
                                                properties={
                                                    "adults": openapi.Schema(type=openapi.TYPE_STRING, description="Number of adults", example="1"),
                                                    "children": openapi.Schema(type=openapi.TYPE_STRING, description="Number of children", example="0"),
                                                    "infants": openapi.Schema(type=openapi.TYPE_STRING, description="Number of infants", example="0")
                                                }
                                            ),
                                            "fare_type": openapi.Schema(type=openapi.TYPE_STRING, description="Fare type", example=""),
                                            "cabin_class": openapi.Schema(type=openapi.TYPE_STRING, description="Cabin class", example="Economy"),
                                        }
                                    ),
                            'gst_details':openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "name": openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                description="Name of the GST-registered entity.",
                                                example="BTA"
                                            ),
                                            "number": openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                description="GST identification number of the entity.",
                                                example="03AAGCB9897B1ZK"
                                            ),
                                            "email": openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                format=openapi.FORMAT_EMAIL,
                                                description="Email address associated with the GST registration.",
                                                example="amjad@tripbrandstechnology.com"
                                            ),
                                            "phone_code": openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                description="Country or region phone code (if applicable).",
                                                example="+91"
                                            ),
                                            "phone_number": openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                description="Phone number associated with the GST registration.",
                                                example="9447508305"
                                            ),
                                            "address": openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                description="Physical address of the GST-registered entity.",
                                                example="5D, B2B Travel Agency, Chakolas Heights, Seaport - Airport Rd, near Infopark South Gate, Chittethukara, Kakkanad, Kerala 682037"
                                            ),
                                            "support_email": openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                format=openapi.FORMAT_EMAIL,
                                                description="Support email address for GST-related queries.",
                                                example="hanees.uk@tripbrandsgroup.com"
                                            ),
                                            "support_phone": openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                description="Support phone number for GST-related queries.",
                                                example="7290066347"
                                            ),
                                        },
                                        description="Details of the GST-registered entity, including contact information and address."
                                    ),
                            "itinerary_key": openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "flightSegments": openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=flight_segment_schema,
                                        description="List of flight segments for the itinerary."
                                    ),
                                    "default_baggage": openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "checkInBag": openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                description="Check-in baggage allowance."
                                            ),
                                            "cabinBag": openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                description="Cabin baggage allowance."
                                            ),
                                        },
                                        description="Baggage information for the itinerary."
                                    ),
                                    "publishFare": openapi.Schema(
                                    type=openapi.TYPE_NUMBER,
                                    format=openapi.FORMAT_FLOAT,
                                    description="Original fare price as published.",
                                    example=10935.6
                                    ),
                                    "offerFare": openapi.Schema(
                                        type=openapi.TYPE_NUMBER,
                                        format=openapi.FORMAT_FLOAT,
                                        description="Discounted fare offered to the customer.",
                                        example=10746.38
                                    ),
                                    "Discount": openapi.Schema(
                                        type=openapi.TYPE_NUMBER,
                                        format=openapi.FORMAT_FLOAT,
                                        description="Discount amount applied to the published fare.",
                                        example=155.1604
                                    ),
                                    "segmentID": openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        description="Unique internal segment ID",
                                        example="UUID"
                                    ),
                                    "currency": openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        description="Currency code for the fares.",
                                        example="INR"
                                    ),
                                },
                                description="Flight details specific to the itinerary."
                            ),
                            "IsPriceChanged": openapi.Schema(
                                type=openapi.TYPE_BOOLEAN,
                                description="Indicates if the fare price has changed since the last check."
                            ),
                            "isDOB": openapi.Schema(
                                type=openapi.TYPE_BOOLEAN,
                                description="Indicates if the passenger's date of birth is required."
                            ),
                            "isGST": openapi.Schema(
                                type=openapi.TYPE_BOOLEAN,
                                description="Indicates if GST details are required."
                            ),
                            "isPassport": openapi.Schema(
                                type=openapi.TYPE_BOOLEAN,
                                description="Indicates if passport details are required."
                            ),
                        },
                        description="Pricing and fare metadata for the session and itineraries."
                    ),
                    "status": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Status of the API response (e.g., success)."
                    ),
                    'response_meta_data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'session_break': openapi.Schema(
                                type=openapi.TYPE_BOOLEAN,
                                description="Indicates whether the session is broken. Example: True.",
                            ),
                            'info': openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="The detailed error will be shared here. This field will be available only if session_break is True",
                            ),
                        },
                    ),
                },
                description="Response payload with flight pricing, segment details, and fare breakdown."
            )
    response_examples = {
                        "Standard Response": {
                                            "flight_air_pricing": {
                                                "session_id": "849ef51d-40cd-4918-a54c-7550799fa94a",
                                                "fareDetails": {
                                                    "DEL_BOM_1501": {
                                                        "fare_id": "FARE-7d3c4229-fd00-4c85-9cf3-f3ac0430507b",
                                                        "publishedFare": 10935.6,
                                                        "offeredFare": 10746.38,
                                                        "Discount": 155.16040000000098,
                                                        "vendor_id": "",
                                                        "transaction_id": "OB12[TBO]CnqIo1yreIHCmMUdXm9fs2bnDISHQNoHfiXKsRyb/1z6G8xC6xKBTc5KGJWWrzCqlp3gyyA4LiYB8V5WWff0C2r4y4iNSyAvURwMLETtFAR1Ex/f/IO3RekrGiXZVU5T65UoOvYqjQf/CGwa/xTOIYKWQUn/89ezAxCiI5J0kzu+fVVIyaSjDA7k+qvktVWVJQ7LBASfzMQUaSDbEoa1U+Iu5DLYmkFh5NU6I+8Dma7gJQK0fZNnLQJP4F/6AMyLXI09vJq1RmumWZ1/sqk0Ef2Tzscxz6UW44cy60O4S3Ij3HGMBLDv+XYAr6kxqldyNIRGQotiUqkUs2ZV/Ww7qSEekytve5UcF4lY+02s5L/UC7YdY240XuxRnzg2+OcG2/mfhY3Bb70Fr85DdPkoCMEkd1VpI3jwk5WOARR4q84WVlEgeCKnEo8OJDMs0FrYc4239jbNyK+iDD1dx0Gw849yHkuYscvQodPRlJJv7B42MjgD0SEBKXpLlvrePm7oVH1ImprOz8BIm3xL+MZyDxgNnuv7/d1VU25byLa3oW6CbaqnYfcVDFgxIEV4sDQrjGZ4eu9iSsUb7ZmUzJG9CCdYHiFjeDwnsa81btZgg/dxn/pG47PvZJUijEdMfg9FE6hDo6Ie183XrQsuUNpIRv0CFZSa+sI9quGz+jvcgPU=",
                                                        "fareType": "RegularFare",
                                                        "fare_rule": "<h1>DEL - BOM</h1><br>The FareBasisCode is: USAF<br/>Changes and cancellations are permitted as per applicable rules and charges<br/><ul><li>APART FROM AIRLINE CHARGES,GST+RAF+ APPLICABLE CHARGES IF ANY, WILL BE CHARGED<br/></li><li>MENTIONED FEE ARE INDICATIVE PER PAX AND PER SECTOR<br/></li><li>FOR DOMESTIC BOOKINGS, PASSENGERS ARE REQUIRED TO SUBMIT THE CANCELLATION OR REISSUE REQUEST AT LEAST 2 HOURS BEFORE THE AIRLINES CANCELLATION AND REISSUE POLICY<br/></li><li>FOR INTERNATIONAL BOOKINGS, PASSENGERS ARE REQUIRED TO SUBMIT THE CANCELLATION OR REISSUE REQUEST AT LEAST 4 HOURS BEFORE THE AIRLINES CANCELLATION AND REISSUE POLICY<br/></li></ul>",
                                                        "currency": "INR",
                                                        "colour": "Peach",
                                                        "fareBreakdown": [
                                                            {
                                                                "passengerType": "adults",
                                                                "baseFare": 2800.0,
                                                                "tax": 1308.0
                                                            },
                                                            {
                                                                "passengerType": "children",
                                                                "baseFare": 2800.0,
                                                                "tax": 1308.0
                                                            },
                                                            {
                                                                "passengerType": "infants",
                                                                "baseFare": 1666.0,
                                                                "tax": 1030.0
                                                            }
                                                        ],
                                                        "isRefundable": True
                                                    }
                                                },
                                                "search_details": {
                                                    "flight_type": "DOM",
                                                    "journey_type": "One Way",
                                                    "journey_details": [
                                                        {
                                                            "source_city": "DEL",
                                                            "destination_city": "BOM",
                                                            "travel_date": "15-01-2025"
                                                        }
                                                    ],
                                                    "passenger_details": {
                                                        "adults": 1,
                                                        "children": 1,
                                                        "infants": 1
                                                    },
                                                    "fare_type": "",
                                                    "cabin_class": "Economy"
                                                },
                                                "gst_details": {
                                                    "name": "BTA",
                                                    "number": "qq",
                                                    "email": "admin@bta.com",
                                                    "phone_code": None,
                                                    "phone_number": "6282957556",
                                                    "address": "5D, B2B Travel Agency, Chakolas Heights, Seaport - Airport Rd, near Infopark South Gate, Chittethukara, Kakkanad, Kerala 682037",
                                                    "support_email": "spad1@gmail.com7",
                                                    "support_phone": "56774433217"
                                                },
                                                "IsPriceChanged": True,
                                                "isDOB": True,
                                                "isGST": True,
                                                "isPassport": False,
                                                "itineraries": [
                                                    "DEL_BOM_1501"
                                                ],
                                                "DEL_BOM_1501": {
                                                    "flightSegments": {
                                                        "DEL_BOM_1501": [
                                                            {
                                                                "airlineCode": "SG",
                                                                "airlineName": "SpiceJet",
                                                                "flightNumber": "385",
                                                                "equipmentType": "737",
                                                                "departure": {
                                                                    "airportCode": "DEL",
                                                                    "airportName": "Indira Gandhi Airport",
                                                                    "city": "Delhi",
                                                                    "country": "India",
                                                                    "countryCode": "IN",
                                                                    "terminal": "1D",
                                                                    "departureDatetime": "2025-01-15T05:25:00"
                                                                },
                                                                "arrival": {
                                                                    "airportCode": "BOM",
                                                                    "airportName": "Chhatrapati Shivaji International Airport",
                                                                    "city": "Mumbai",
                                                                    "country": "India",
                                                                    "countryCode": "IN",
                                                                    "terminal": "1",
                                                                    "arrivalDatetime": "2025-01-15T07:40:00"
                                                                },
                                                                "durationInMinutes": 135,
                                                                "stop": 0,
                                                                "cabinClass": "Economy",
                                                                "fareBasisCode": "USAF",
                                                                "seatsRemaining": None,
                                                                "isRefundable": True,
                                                                "isChangeAllowed": True
                                                            }
                                                        ]
                                                    },
                                                    "segmentID": "VEN-d955334e-37f5-48dd-ba1f-4c81b2337c28_$_SEG-bcb58964-5192-4d01-8e46-b40641744d5e",
                                                    "publishFare": 10935.6,
                                                    "offerFare": 10746.38,
                                                    "Discount": 155.16040000000098,
                                                    "currency": "INR",
                                                    "default_baggage": {
                                                        "checkInBag": "15 KG",
                                                        "cabinBag": "7 KG"
                                                    }
                                                }
                                            },
                                            "status": "success",
                                            "response_meta_data": {
                                                "session_break": False
                                                                }
                                        }
    }
    response_with_examples = openapi.Response(
                                description="A successful response with multiple examples. Change  'RESPONSE SCHEMA' from 'application/json' to view sample responses",
                                schema=response_schema,
                                examples=response_examples
                            )
    @swagger_auto_schema(
        operation_id="04_GetUpdatedPricing",
        operation_summary="04 - Get Updated Pricing",
        operation_description="Retrieve updated flight pricing details, including fare breakdown, journey details, GST information, and other fare-related metadata.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "session_id": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="A unique identifier for the user session."
                ),
                "segments": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "segment_id": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Unique identifier for the flight segment."
                            ),
                            "fare_id": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Unique identifier for the fare associated with the segment."
                            ),
                        },
                    ),
                    description="Array of flight segments for which pricing is being checked."
                ),
            },
            required=["session_id", "segments"],
            description="Payload containing session and segment information for flight pricing checks."
        ),
        responses={
            200: response_with_examples,
        },
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Flight Booking"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class OutAPIFlightsSSR(FlightsSSR):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    response_schema = openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "flight_ssr_response": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "session_id": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Session ID echo."
                    ),
                    "search_details": openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "flight_type": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Domestic (DOM) or International (INT)"
                            ),
                            "journey_type": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="One Way or Round Trip."
                            ),
                            "journey_details": openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        "source_city": openapi.Schema(type=openapi.TYPE_STRING),
                                        "destination_city": openapi.Schema(type=openapi.TYPE_STRING),
                                        "travel_date": openapi.Schema(type=openapi.TYPE_STRING),
                                    }
                                ),
                                description="List of journey segments with source, destination, and travel date."
                            ),
                            "passenger_details": openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "adults": openapi.Schema(type=openapi.TYPE_INTEGER),
                                    "children": openapi.Schema(type=openapi.TYPE_INTEGER),
                                    "infants": openapi.Schema(type=openapi.TYPE_INTEGER),
                                }
                            ),
                            "fare_type": openapi.Schema(type=openapi.TYPE_STRING),
                            "cabin_class": openapi.Schema(type=openapi.TYPE_STRING),
                        }
                    ),
                    "itineraries": openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_STRING),
                        description="List of itinerary keys used as references below."
                    ),
                },
                # Use additionalProperties to handle dynamic itinerary keys, e.g. 'DEL_BOM_1501'
                additionalProperties=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "is_baggage": openapi.Schema(
                                type=openapi.TYPE_BOOLEAN,
                                description="Indicates if baggage SSRs are available."
                            ),
                            "baggage_ssr": openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "adults": openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "Code": openapi.Schema(type=openapi.TYPE_STRING),
                                                "Weight": openapi.Schema(type=openapi.TYPE_INTEGER),
                                                "Unit": openapi.Schema(type=openapi.TYPE_STRING),
                                                "Price": openapi.Schema(type=openapi.TYPE_NUMBER),
                                                "Description": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Description of baggage, or numeric as string."
                                                ),
                                            }
                                        )
                                    ),
                                    "children": openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "Code": openapi.Schema(type=openapi.TYPE_STRING),
                                                "Weight": openapi.Schema(type=openapi.TYPE_INTEGER),
                                                "Unit": openapi.Schema(type=openapi.TYPE_STRING),
                                                "Price": openapi.Schema(type=openapi.TYPE_NUMBER),
                                                "Description": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Description of baggage, or numeric as string."
                                                ),
                                            }
                                        )
                                    ),
                                }
                            ),
                            "Currency": openapi.Schema(type=openapi.TYPE_STRING),
                            "journey_segment": openapi.Schema(type=openapi.TYPE_STRING),
                            "is_meals": openapi.Schema(
                                type=openapi.TYPE_BOOLEAN,
                                description="Indicates if meal SSRs are available."
                            ),
                            "meals_ssr": openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "adults": openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "Code": openapi.Schema(type=openapi.TYPE_STRING),
                                                "Description": openapi.Schema(type=openapi.TYPE_STRING),
                                                "Quantity": openapi.Schema(type=openapi.TYPE_INTEGER),
                                                "Price": openapi.Schema(type=openapi.TYPE_NUMBER),
                                            }
                                        )
                                    ),
                                    "children": openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "Code": openapi.Schema(type=openapi.TYPE_STRING),
                                                "Description": openapi.Schema(type=openapi.TYPE_STRING),
                                                "Quantity": openapi.Schema(type=openapi.TYPE_INTEGER),
                                                "Price": openapi.Schema(type=openapi.TYPE_NUMBER),
                                            }
                                        )
                                    ),
                                }
                            ),
                            "is_seats": openapi.Schema(
                                type=openapi.TYPE_BOOLEAN,
                                description="Indicates if seat selection is available."
                            ),
                            "seats_ssr": openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "adults": openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "seatmap": openapi.Schema(
                                                type=openapi.TYPE_ARRAY,
                                                items=openapi.Schema(
                                                    type=openapi.TYPE_OBJECT,
                                                    properties={
                                                        "row": openapi.Schema(
                                                            type=openapi.TYPE_INTEGER,
                                                            description="Row number."
                                                        ),
                                                        "seats": openapi.Schema(
                                                            type=openapi.TYPE_ARRAY,
                                                            items=openapi.Schema(
                                                                type=openapi.TYPE_OBJECT,
                                                                properties={
                                                                    "Code": openapi.Schema(type=openapi.TYPE_STRING),
                                                                    "isBooked": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                                                                    "Price": openapi.Schema(
                                                                        type=openapi.TYPE_NUMBER,
                                                                        x_nullable=True,
                                                                        description="Price (can be null if no fee)."
                                                                    ),
                                                                    "seatType": openapi.Schema(
                                                                        type=openapi.TYPE_INTEGER,
                                                                        x_nullable=True,
                                                                        description="Seat type code (can be null)."
                                                                    ),
                                                                    "info": openapi.Schema(type=openapi.TYPE_STRING),
                                                                }
                                                            )
                                                        )
                                                    }
                                                )
                                            ),
                                            "CraftType": openapi.Schema(type=openapi.TYPE_STRING),
                                            "seat_data": openapi.Schema(
                                                type=openapi.TYPE_OBJECT,
                                                properties={
                                                    "row": openapi.Schema(type=openapi.TYPE_INTEGER),
                                                    "column": openapi.Schema(type=openapi.TYPE_INTEGER),
                                                }
                                            ),
                                        }
                                    ),
                                    "children": openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "seatmap": openapi.Schema(
                                                type=openapi.TYPE_ARRAY,
                                                items=openapi.Schema(
                                                    type=openapi.TYPE_OBJECT,
                                                    properties={
                                                        "row": openapi.Schema(type=openapi.TYPE_INTEGER),
                                                        "seats": openapi.Schema(
                                                            type=openapi.TYPE_ARRAY,
                                                            items=openapi.Schema(
                                                                type=openapi.TYPE_OBJECT,
                                                                properties={
                                                                    "Code": openapi.Schema(type=openapi.TYPE_STRING),
                                                                    "isBooked": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                                                                    "Price": openapi.Schema(
                                                                        type=openapi.TYPE_NUMBER,
                                                                        x_nullable=True
                                                                    ),
                                                                    "seatType": openapi.Schema(
                                                                        type=openapi.TYPE_INTEGER,
                                                                        x_nullable=True
                                                                    ),
                                                                    "info": openapi.Schema(type=openapi.TYPE_STRING),
                                                                }
                                                            )
                                                        )
                                                    }
                                                )
                                            ),
                                            "CraftType": openapi.Schema(type=openapi.TYPE_STRING),
                                            "seat_data": openapi.Schema(
                                                type=openapi.TYPE_OBJECT,
                                                properties={
                                                    "row": openapi.Schema(type=openapi.TYPE_INTEGER),
                                                    "column": openapi.Schema(type=openapi.TYPE_INTEGER),
                                                }
                                            ),
                                        }
                                    ),
                                }
                            ),
                        }
                    )
                )
            ),
            "session_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Echo of the session ID."
            ),
        },
        example={
            "flight_ssr_response": {
                "session_id": "6501f7a6-928c-4d58-ae9e-3cec81195a22",
                "search_details": {
                    "flight_type": "DOM",
                    "journey_type": "One Way",
                    "journey_details": [
                        {
                            "source_city": "DEL",
                            "destination_city": "BOM",
                            "travel_date": "15-01-2025"
                        }
                    ],
                    "passenger_details": {
                        "adults": 1,
                        "children": 1,
                        "infants": 1
                    },
                    "fare_type": "",
                    "cabin_class": "Economy"
                },
                "itineraries": [
                    "DEL_BOM_1501"
                ],
                # Dynamic itinerary property
                "DEL_BOM_1501": [
                    {
                        "is_baggage": True,
                        "baggage_ssr": {
                            "adults": [
                                {
                                    "Code": "NoBaggage",
                                    "Weight": 0,
                                    "Unit": "Kg",
                                    "Price": 0,
                                    "Description": "2"
                                }
                            ],
                            "children": [
                                {
                                    "Code": "NoBaggage",
                                    "Weight": 0,
                                    "Unit": "Kg",
                                    "Price": 0,
                                    "Description": "2"
                                }
                            ]
                        },
                        "Currency": "INR",
                        "journey_segment": "DEL-BOM",
                        "is_meals": True,
                        "meals_ssr": {
                            "adults": [
                                {
                                    "Code": "NoMeal",
                                    "Description": "",
                                    "Quantity": 0,
                                    "Price": 0
                                }
                            ],
                            "children": [
                                {
                                    "Code": "NoMeal",
                                    "Description": "",
                                    "Quantity": 0,
                                    "Price": 0
                                }
                            ]
                        },
                        "is_seats": True,
                        "seats_ssr": {
                            "adults": {
                                "seatmap": [
                                    {
                                        "row": 4,
                                        "seats": [
                                            {
                                                "Code": "4A",
                                                "isBooked": True,
                                                "Price": 1620,
                                                "seatType": 1,
                                                "info": "Window Seat"
                                            }
                                        ]
                                    }
                                ],
                                "CraftType": "A321-220",
                                "seat_data": {
                                    "row": 38,
                                    "column": 7
                                }
                            },
                            "children": {
                                "seatmap": [
                                    {
                                        "row": 4,
                                        "seats": [
                                            {
                                                "Code": "4A",
                                                "isBooked": True,
                                                "Price": 1620,
                                                "seatType": 1,
                                                "info": "Window Seat"
                                            }
                                        ]
                                    }
                                ],
                                "CraftType": "A321-220",
                                "seat_data": {
                                    "row": 38,
                                    "column": 7
                                }
                            }
                        }
                    }
                ]
            },
            "session_id": "6501f7a6-928c-4d58-ae9e-3cec81195a22"
        }
    )
    response_with_examples = openapi.Response(
                                description="A successful response with multiple examples. Change  'RESPONSE SCHEMA' from 'application/json' to view sample responses",
                                schema=response_schema,
                            )
    @swagger_auto_schema(
        operation_id="05_GetSSRDetails",
        operation_summary="05 - Get SSR Details",
        operation_description="Retrieve SSR (baggage, meals, seats) information for the specified flight segments.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["session_id", "segments"],
            properties={
                "session_id": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Unique session identifier."
                ),
                "segments": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    description="List of segments for which SSR data is requested.",
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        required=["segment_id", "fare_id"],
                        properties={
                            "segment_id": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Unique identifier of the flight segment."
                            ),
                            "fare_id": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Fare identifier for the chosen fare."
                            ),
                        }
                    )
                )
            }
        ),
        responses={
            200: response_with_examples,
        },
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Flight Booking"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    
class OutAPICreateBooking(CreateBooking):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="06_CreateBooking",
        operation_summary="06 - Create Booking",
        operation_description="Create a new flight booking given the passenger details, segments, itineraries, and contact information.",
        request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["session_id", "segments", "itineraries", "pax_details", "contact"],
        properties={
            "session_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Unique session identifier from the frontend context"
            ),
            "segments": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                description="List of segments to book",
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    required=["segment_id", "fare_id"],
                    properties={
                        "segment_id": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Segment identifier"
                        ),
                        "fare_id": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Fare identifier for the given segment"
                        ),
                    },
                ),
            ),
            "itineraries": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                description="List of itinerary identifiers",
                items=openapi.Schema(type=openapi.TYPE_STRING),
            ),
            "pax_details": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                description="List of passenger details (adults, child, infants, etc.)",
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "type": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Passenger type (e.g. 'adults', 'child', 'infants')"
                        ),
                        "title": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Title (Mr, Mrs, Ms, etc.)"
                        ),
                        "firstName": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Passenger's first name"
                        ),
                        "lastName": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Passenger's last name"
                        ),
                        "gender": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Gender of the passenger (Male / Female / Other)"
                        ),
                        "dob": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Date of birth (if applicable; format may vary)"
                        ),
                        "passport": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Passport number (if required)"
                        ),
                        "passport_issue_date": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Passport issue date"
                        ),
                        "passport_expiry": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Passport expiry date"
                        ),
                        "passport_issue_country_code": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="ISO country code of passport issuing country"
                        ),
                        # This example shows only "COK_CCU_1501" sub-structure for seats_ssr, baggage_ssr, etc.
                        # In practice, your field names may be dynamically generated based on itinerary segments.
                        "COK_CCU_1501": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            description="Keyed by flight segment code. Each flight segment has seats, baggage, meals data.",
                            properties={
                                "COK-BLR": openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        "seats_ssr": openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "Code": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Seat code"
                                                ),
                                                "isBooked": openapi.Schema(
                                                    type=openapi.TYPE_BOOLEAN,
                                                    description="Whether the seat has been booked"
                                                ),
                                                "Price": openapi.Schema(
                                                    type=openapi.TYPE_NUMBER,
                                                    description="Price of the seat"
                                                ),
                                                "seatType": openapi.Schema(
                                                    type=openapi.TYPE_INTEGER,
                                                    description="Type of seat (e.g., window, aisle, middle)"
                                                ),
                                                "info": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Additional info about seat"
                                                ),
                                                "selected": openapi.Schema(
                                                    type=openapi.TYPE_BOOLEAN,
                                                    description="Whether this seat is selected"
                                                ),
                                            }
                                        ),
                                        "baggage_ssr": openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "Code": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Baggage code (e.g. 'NoBaggage', 'Bag15KG')"
                                                ),
                                                "Weight": openapi.Schema(
                                                    type=openapi.TYPE_NUMBER,
                                                    description="Weight allowance for baggage"
                                                ),
                                                "Unit": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Weight unit, typically 'Kg'"
                                                ),
                                                "Price": openapi.Schema(
                                                    type=openapi.TYPE_NUMBER,
                                                    description="Price for baggage SSR"
                                                ),
                                            }
                                        ),
                                        "meals_ssr": openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "Code": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Meal code"
                                                ),
                                                "Description": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    description="Meal description"
                                                ),
                                                "Quantity": openapi.Schema(
                                                    type=openapi.TYPE_INTEGER,
                                                    description="Number of meals"
                                                ),
                                                "Price": openapi.Schema(
                                                    type=openapi.TYPE_NUMBER,
                                                    description="Price of the meal"
                                                ),
                                            }
                                        ),
                                    },
                                ),
                            },
                        ),
                    },
                ),
            ),
            "contact": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                required=["phoneCode", "phone", "email"],
                properties={
                    "phoneCode": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="International calling code for the contact number (e.g. '+91')"
                    ),
                    "phone": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Contact phone number"
                    ),
                    "email": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Contact email address"
                    ),
                },
            ),
            "gstDetails": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description="GST details if applicable (can be null)",
                properties={
                    "phoneCode": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Country calling code for GST contact (e.g. '+91')"
                    ),
                    "phone": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="GST contact phone number"
                    ),
                    "email": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="GST contact email address"
                    ),
                    "gstNumber": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="GST registration number"
                    ),
                    "name": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Registered name of the GST entity"
                    ),
                    "address": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Registered address of the GST entity"
                    ),
                },
                nullable=True
            ),
        },
        example={
            "session_id": "d7c4c9f0-e50e-46f8-87f5-942af05e792f",
            "segments": [
                {
                    "segment_id": "VEN-d955334e-37f5-48dd-ba1f-4c81b2337c28_$_SEG-fbbbe8bb-76c0-4fd0-ab69-31fd6ce33684",
                    "fare_id": "FARE-0a87660e-fb56-4727-899e-00299afe0ea8"
                }
            ],
            "itineraries": [
                "COK_CCU_1501"
            ],
            "pax_details": [
                {
                    "type": "adults",
                    "title": "Mr",
                    "firstName": "Amjad",
                    "lastName": "Naushad",
                    "gender": "Male",
                    "dob": "",
                    "passport": "",
                    "passport_issue_date": "",
                    "passport_expiry": "",
                    "passport_issue_country_code": "",
                    "COK_CCU_1501": {
                        "COK-BLR": {
                            "seats_ssr": {
                                "Code": "3E",
                                "isBooked": False,
                                "Price": 650,
                                "seatType": 3,
                                "info": "Middle Seat",
                                "selected": True
                            },
                            "baggage_ssr": {
                                "Code": "NoBaggage",
                                "Weight": 0,
                                "Unit": "Kg",
                                "Price": 0
                            },
                            "meals_ssr": {
                                "Code": "TCSW",
                                "Description": "Tomato Cucumber Cheese Lettuce Sandwich Combo",
                                "Quantity": 1,
                                "Price": 400
                            }
                        }
                    }
                },
                {
                    "type": "child",
                    "title": "",
                    "firstName": "Arjun",
                    "lastName": "Mecheril",
                    "gender": "Male",
                    "dob": "",
                    "passport": "",
                    "passport_issue_date": "",
                    "passport_expiry": "",
                    "passport_issue_country_code": "",
                    "COK_CCU_1501": {
                        "COK-BLR": {
                            "seats_ssr": {
                                "Code": "3F",
                                "isBooked": False,
                                "Price": 650,
                                "seatType": 1,
                                "info": "Window Seat",
                                "selected": True
                            },
                            "baggage_ssr": {
                                "Code": "NoBaggage",
                                "Weight": 0,
                                "Unit": "Kg",
                                "Price": 0
                            },
                            "meals_ssr": {
                                "Code": "NoMeal",
                                "Description": "",
                                "Quantity": 0,
                                "Price": 0
                            }
                        }
                    }
                },
                {
                    "type": "infant",
                    "title": "",
                    "firstName": "Jijo",
                    "lastName": "Thomas",
                    "gender": "Male",
                    "dob": "",
                    "passport": "",
                    "passport_issue_date": "",
                    "passport_expiry": "",
                    "passport_issue_country_code": ""
                }
            ],
            "contact": {
                "phoneCode": "+91",
                "phone": "9447508305",
                "email": "amjad@elkanio.com"
            },
            "gstDetails": None
        }
    ),
    responses={
        status.HTTP_200_OK: openapi.Response(
            description="Successfully created the booking",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "session_id": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Session ID used for the booking"
                    ),
                    "booking_id": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Booking ID representing the newly created booking"
                    ),
                    "display": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Booking display string"
                    ),
                },
            ),
            examples={
                "application/json": {
                    "session_id": "d7c4c9f0-e50e-46f8-87f5-942af05e792f",
                    "booking_id": "e6c33ba0-37bb-4ecd-a3a7-78e82626b434",
                    "display": "BTA25-0201-0001"
                }
            },
        ),
        status.HTTP_400_BAD_REQUEST: openapi.Response(
            description="Bad Request - Validation errors or missing fields",
        ),
        status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response(
            description="Internal server error"
        ),
    },
    deprecated=False,  # Set True if you consider this endpoint deprecated
    tags=["Flight Booking"],  # You can group endpoints by tags in Swagger
    )   
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class OutAPICheckHold(CheckHold):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="07_CheckHold",
        operation_summary="07 - Check Hold",
    operation_description=(
                            "- `is_hold` indicates if the hold can be applied (true/false)."
                            "- `is_hold_ssr` indicates if the hold can include any special service requests (true/false)."
                            ),
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["session_id", "booking_id"],
        properties={
            "session_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Unique session identifier from the frontend or booking context"
            ),
            "booking_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Identifier for the booking to check hold availability"
            ),
        },
        example={
            "session_id": "d7c4c9f0-e50e-46f8-87f5-942af05e792f",
            "booking_id": "cd7800d2-a952-4dcd-9db0-f131ea4aa6a6"
        }
    ),
    responses={
        status.HTTP_200_OK: openapi.Response(
            description="Hold information returned successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "is_hold": openapi.Schema(
                        type=openapi.TYPE_BOOLEAN,
                        description="Indicates if a hold can be applied to this booking"
                    ),
                    "is_hold_ssr": openapi.Schema(
                        type=openapi.TYPE_BOOLEAN,
                        description="Indicates if special service requests (SSR) can be included in the hold"
                    ),
                },
            ),
            examples={
                "application/json": {
                    "is_hold": True,
                    "is_hold_ssr": False
                }
            },
        ),
        status.HTTP_400_BAD_REQUEST: openapi.Response(
            description="Bad Request - Validation errors or missing fields",
        ),
        status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response(
            description="Internal server error",
        ),
    },
    deprecated=False,  # Set True if you consider this endpoint deprecated
    tags=["Flight Booking"],  # You can group endpoints by tags in Swagger
    ) 
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class OutAPIHoldBooking(HoldBooking):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="08_HoldBooking",
        operation_summary="08 - Hold Booking",
    operation_description="""
    This endpoint is used to hold the booking. You must provide the following fields:

    - **session_id**: The unique session identifier.
    - **booking_id**: The unique booking identifier.
    - **amount**: The total amount to be held for the booking.

    **Important**: The response only indicates that the hold request was successfully **received**. 
    The `status` field in the response does not confirm a successful hold. 
    You **must continuously call** the `/purchase-status` endpoint to check the hold status of the booking.
    """,
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["session_id", "booking_id", "amount"],
        properties={
            "session_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="A unique ID to identify the current session",
                example="64557400-3223-49bd-adba-426186f50a5f"
            ),
            "booking_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="A unique ID to identify the specific booking",
                example="18600969-e49c-4a35-b1f0-41c6c85c84b3"
            ),
            "amount": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="The amount to be held for this booking (in decimal format as a string)",
                example="3267.00"
            ),
        }
    ),
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "status": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description="""
                    **true** if the request has been successfully received.
                    This does **not** mean the booking is confirmed.
                    You need to check the booking status via `/purchase-status`.
                    """,
                    example=True
                )
            },
            description="The request has been received. Check booking status with the `/purchase-status` endpoint."
        ),
        400: "Bad Request (Invalid data or missing fields)",
        500: "Internal Server Error",
    },
    deprecated=False,  # Set True if you consider this endpoint deprecated
    tags=["Flight Booking"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class OutAPIPurchaseStatus(PurchaseStatus):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="09_GetPurchaseStatus",
        operation_summary="09 - Get Purchase Status",
    operation_description="""
    **Repeatedly call** this endpoint to check the status of a previously held booking.

    **Request Body**:
    - **session_id**: The unique identifier for the user session.
    - **booking_id**: The unique identifier for the booking.

    **Response**:
    - **status**: The status of the booking (e.g., "success", "In-Progress", "failed", etc.).
    - **info**: A message describing the status or outcome.
    - **display_id**: A reference ID (e.g., a booking or transaction reference).

    Continue calling same API until the status is not "In-Progress"
    """,
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["session_id", "booking_id"],
        properties={
            "session_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="A unique ID to identify the current session",
                example="c85882ff-aa66-49d4-8a48-e672cf60d7fa"
            ),
            "booking_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="A unique ID to identify the booking",
                example="e0032c58-1fa5-4ab4-92dc-2f537ba69861"
            ),
        }
    ),
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "status": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Status of the booking (e.g., 'success', 'In-Progress', 'failed')",
                    example="success"
                ),
                "info": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="An informational message about the booking status",
                    example="Ticket Booked Successfully!"
                ),
                "display_id": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="A display or reference ID for the booked ticket",
                    example="BTA25-0201-0005"
                ),
            },
            description="Status response for the booking."
        ),
        400: "Bad Request (Invalid data or missing fields)",
        500: "Internal Server Error",
    },
    deprecated=False,  # Set True if you consider this endpoint deprecated
    tags=["Flight Booking"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class OutAPIPurchase(Purchase):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="10_PurchaseTicket",
        operation_summary="10 - Purchase Ticket",
    operation_description=(
        "This endpoint processes a purchase request. The response status indicates "
        "the request is received. Please call `purchase-status` to get the updated "
        "booking status and details."
    ),
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'session_id': openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Unique session ID for the purchase request"
            ),
            'amount': openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Total amount to be charged (e.g., '3267.00')"
            ),
            'booking_id': openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Unique booking identifier"
            ),
            'payment_mode': openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Mode of payment (e.g., 'Wallet')"
            ),
        },
        required=['session_id', 'amount', 'booking_id', 'payment_mode']
    ),
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'status': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description="Status of the request (always true if received)"
                ),
                'razorpay_url': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    nullable=True,
                    description="Razorpay redirect URL if applicable; null otherwise"
                ),
            },
            example={
                "status": True,
                "razorpay_url": None
            }
        )
    },
    deprecated=False,  # Set True if you consider this endpoint deprecated
    tags=["Flight Booking"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class OutAPIRepricing(Repricing):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="11_RepriceHoldTickets",
        operation_summary="11 - Reprice Hold Tickets",
        operation_description="""
        This endpoint is used to reprice a booking during the hold-to-ticket conversion process.
        The client needs to send a booking ID in the request payload.
        The response provides details on whether there has been a fare change,
        the old and new fare amounts, and whether the hold conversion can proceed.
        """,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'booking_id': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Unique identifier of the booking to reprice."
                )
            },
            required=['booking_id'],
            example={"booking_id": "e0032c58-1fa5-4ab4-92dc-2f537ba69861"}
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'DEL_BOM_0301': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'is_fare_change': openapi.Schema(
                                type=openapi.TYPE_BOOLEAN,
                                description="Indicates if there has been a fare change."
                            ),
                            'new_fare': openapi.Schema(
                                type=openapi.TYPE_NUMBER,
                                format=openapi.FORMAT_FLOAT,
                                description="The new fare amount after repricing."
                            ),
                            'old_fare': openapi.Schema(
                                type=openapi.TYPE_NUMBER,
                                format=openapi.FORMAT_FLOAT,
                                description="The old fare amount before repricing."
                            ),
                            'is_hold_continue': openapi.Schema(
                                type=openapi.TYPE_BOOLEAN,
                                description="Indicates if the hold conversion process can continue."
                            )
                        },
                        description="Details specific to the route or segment being repriced."
                    ),
                    'booking_id': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Unique identifier of the booking."
                    ),
                    'status': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="The status of the repricing operation (e.g., success or failure)."
                    ),
                    'is_fare_change': openapi.Schema(
                        type=openapi.TYPE_BOOLEAN,
                        description="Indicates if there has been any fare change across all routes/segments."
                    ),
                    'is_hold_continue': openapi.Schema(
                        type=openapi.TYPE_BOOLEAN,
                        description="Indicates if the hold conversion process can proceed."
                    ),
                    'error': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        additional_properties=openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Error messages or codes for specific routes/segments, if applicable."
                        ),
                        description="Error details for each route/segment."
                    )
                },
                example={
                    "DEL_BOM_0301": {
                        "is_fare_change": False,
                        "new_fare": 3267.0,
                        "old_fare": 3267.0,
                        "is_hold_continue": True
                    },
                    "booking_id": "e0032c58-1fa5-4ab4-92dc-2f537ba69861",
                    "status": "success",
                    "is_fare_change": False,
                    "is_hold_continue": True,
                    "error": {
                        "DEL_BOM_0301": "N/A"
                    }
                }
            ),
            400: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'detail': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Details of the error in case of an invalid request."
                    )
                },
                example={"detail": "Invalid booking ID."}
            )
        },
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Flight Booking"],  # You can group endpoints by tags in Swagger
    )  
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class OutAPIConvertHoldtoTicket(ConvertHoldtoTicket):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="12_ConvertHoldToTicket",
        operation_summary="12 - Convert Hold To Ticket",
        operation_description="""
        This API initiates the conversion of a hold booking to a ticket. 
        The client sends the booking ID in the request payload, and the response indicates whether the request has been accepted.
        
        Once the request is accepted (`status: true`), the client is required to poll the `purchase-status` API to get the conversion status.
        """,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'booking_id': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Unique identifier of the booking to convert from hold to ticket."
                )
            },
            required=['booking_id'],
            example={"booking_id": "e0032c58-1fa5-4ab4-92dc-2f537ba69861"}
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'status': openapi.Schema(
                        type=openapi.TYPE_BOOLEAN,
                        description="Indicates if the hold-to-ticket conversion request has been accepted."
                    )
                },
                example={"status": True}
            ),
            400: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'detail': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Error message for invalid request."
                    )
                },
                example={"detail": "Invalid booking ID."}
            )
        },
        deprecated=False,  # Set True if you consider this endpoint deprecated
        tags=["Flight Booking"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class OutAPIReleaseHold(ReleaseHold):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="13_ReleaseHold",
        operation_summary="13 - Release Hold",
        operation_description="""
        This API releases the hold on a booking. The client sends the `booking_id` in the request payload.
        The response provides details about the status of the release operation, including specific segment details if applicable.

        If the api response in `flight_hold_release_response.status` is `In-Progress`, poll the same api until you get a success or failure.
        """,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'booking_id': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Unique identifier of the booking whose hold is to be released."
                )
            },
            required=['booking_id'],
            example={"booking_id": "42b34f53-94e6-4e6c-9294-7096e425078b"}
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'response': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'session_id': openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Session ID for the release operation."
                            ),
                            'status': openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Indicates the overall status of the release operation (e.g., success or failure)."
                            ),
                            'flight_hold_release_response': openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'status': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        description="Status of the hold release operation (e.g., Success or Failure)."
                                    ),
                                    'info': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        description="Additional information about the hold release status."
                                    ),
                                    'itineraries': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(
                                            type=openapi.TYPE_STRING
                                        ),
                                        description="List of itineraries related to the booking."
                                    ),
                                    'DEL_BOM_2301': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'status': openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                description="Status of the specific itinerary segment."
                                            )
                                        },
                                        description="Status details for the specific itinerary."
                                    )
                                }
                            ),
                            'booking_id': openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Unique identifier of the booking."
                            )
                        }
                    )
                },
                example={
                    "response": {
                        "session_id": "6f1aa3be-cc39-41cd-91d6-fc8b10a5ee72",
                        "status": "success",
                        "flight_hold_release_response": {
                            "status": "Failure",
                            "info": "Release Hold Not Possible",
                            "itineraries": [
                                "DEL_BOM_2301"
                            ],
                            "DEL_BOM_2301": {
                                "status": "Hold-Failed"
                            }
                        },
                        "booking_id": "42b34f53-94e6-4e6c-9294-7096e425078b"
                    }
                }
            ),
            400: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'detail': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Error message for invalid request."
                    )
                },
                example={"detail": "Invalid booking ID."}
            )
        },
        deprecated=False,  
        tags=["Flight Booking"], 
    ) 
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class OutAPITicketStatus(TicketStatus):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    domestic_response_example = {
        "session_id": "43504b22-b73c-41b5-8afb-611e3a7f6b83",
        "booking_id": "8f3b57f4-dedf-4e62-b892-efb02cb61d03",
        "booked_at": "03-03-2025T16:58:48Z",
        "display_id": "FLT25-0303-0257",
        "search_details": {
            "flight_type": "DOM",
            "journey_type": "One Way",
            "journey_details": [
                {
                    "source_city": "VNS",
                    "destination_city": "BOM",
                    "travel_date": "15-05-2025"
                }
            ],
            "passenger_details": {
                "adults": 1,
                "children": 0,
                "infants": 0
            },
            "fare_type": "Regular",
            "cabin_class": "Economy"
        },
        "organization_details": {
            "support_email": "abc@gmail.com",
            "support_phone": "9876543210",
            "profile_img_url": "image_url",
            "profile_address": "Address of Client.",
            "profile_name": "Cust Cap"
        },
        "contact": {
            "phone": "9876543210",
            "email": "custcap@gmail.com"
        },
        "booking_details": {
            "VNS_BOM_1505": {
                "BookingId": "76337038",
                "airline_pnr": "K4JKWM",
                "gds_pnr": "K4JKWM",
                "date": "03-03-2025T16:58:48Z",
                "status": "Confirmed",
                "error": "",
                "itinerary_id": "f758972d-565f-449a-86ad-0e5dfa3ae0ca"
            }
        },
        "fareDetails": {
            "VNS_BOM_1505": {
                "colour": "Peach",
                "fare_id": "FARE-97adceeb-082e-436e-b489-678bcd28b47c",
                "Discount": 33.95,
                "currency": "INR",
                "fareType": "RegularFare",
                "fare_rule": "",
                "vendor_id": "",
                "offeredFare": 6867.05,
                "isRefundable": True,
                "fareBreakdown": [
                    {
                        "tax": 1177.0,
                        "baseFare": 5724.0,
                        "passengerType": "adults"
                    }
                ],
                "publishedFare": 6901.0,
                "transaction_id": "OB14[TBO]/2Nn3NqGUswrQU37rKkiz1JFr9AXp9IJJHvDn3JwYpXDE+..."
            }
        },
        "gst_details": None,
        "pax_details": [
            {
                "id": "8df5778b-08b7-4024-9344-4d28e1dae748",
                "type": "adults",
                "title": "Mr",
                "firstName": "Amjad",
                "lastName": "Naushad",
                "nationality": "IN",
                "gender": "Male",
                "dob": "",
                "passport": "",
                "passport_expiry": "",
                "passport_issue_date": "",
                "passport_issue_country_code": "IN",
                "address_1": "",
                "address_2": "",
                "barcode_encoded": {
                    "VNS_BOM": "iVBORw0KGgoAAAANSUhEUgAAAikAAACCCAIAAAAMtc9NAAAEwklEQVR4n..."
                }
            }
        ],
        "itineraries": [
            "VNS_BOM_1505"
        ],
        "VNS_BOM_1505": {
            "Discount": 34.64,
            "currency": "INR",
            "offerFare": 6866.36,
            "segmentID": "VEN-d955334e-37f5-48dd-ba1f-4c81b2337c28_$_SEG-423d5b90-88ef-4418-add7-2daf36b77822",
            "publishFare": 6901.0,
            "flightSegments": {
                "VNS_BOM_1505": [
                    {
                        "stop": 0,
                        "arrival": {
                            "city": "Mumbai",
                            "country": "India",
                            "terminal": "2",
                            "airportCode": "BOM",
                            "airportName": "Chhatrapati Shivaji Maharaj International Airport",
                            "countryCode": "IN",
                            "arrivalDatetime": "2025-05-15T18:30:00"
                        },
                        "departure": {
                            "city": "Varanasi",
                            "country": "India",
                            "terminal": "",
                            "airportCode": "VNS",
                            "airportName": "Varanasi",
                            "countryCode": "IN",
                            "departureDatetime": "2025-05-15T16:15:00"
                        },
                        "cabinClass": "Economy",
                        "airlineCode": "IX",
                        "airlineName": "Air India Express",
                        "flightNumber": "2547",
                        "isRefundable": True,
                        "equipmentType": "7M8",
                        "fareBasisCode": "ONSA000",
                        "seatsRemaining": 6,
                        "isChangeAllowed": True,
                        "durationInMinutes": 135
                    }
                ]
            },
            "CheckIn_Baggage": "15KG",
            "Cabin_Baggage": "7 KG"
        },
        "access": {
            "status": True,
            "info": "Access granted. You can now view the booking."
        }
    }

    # International Round Trip Response Example
    international_response_example = {
        "session_id": "83d8b917-ff04-42cf-b2c5-a01d0bb0135b",
        "booking_id": "675665da-0355-4d99-a930-15a04607af41",
        "booked_at": "02-03-2025T14:56:54Z",
        "display_id": "FLT25-0203-0135",
        "search_details": {
            "flight_type": "INT",
            "journey_type": "Round Trip",
            "journey_details": [
                {
                    "source_city": "DEL",
                    "destination_city": "SIN",
                    "travel_date": "05-03-2025"
                }
            ],
            "passenger_details": {
                "adults": 2,
                "children": 0,
                "infants": 0
            },
            "fare_type": "Regular",
            "cabin_class": "Premium Economy"
        },
        "organization_details": {
            "support_email": "custcap@gmail.com",
            "support_phone": "9876543210",
            "profile_img_url": "image url",
            "profile_address": "Cust Cap Address",
            "profile_name": "CUST CAP"
        },
        "contact": {
            "phone": "9876543210",
            "email": "custcap@gmail.com"
        },
        "booking_details": {
            "DEL_SIN_0503_R_SIN_DEL_1503": {
                "BookingId": "76310580",
                "airline_pnr": "QAWS3D",
                "gds_pnr": "QAWS3D",
                "date": "02-03-2025T14:56:54Z",
                "status": "Confirmed",
                "error": "",
                "itinerary_id": "6fb93a2a-3fce-4ee4-b6cb-86d90c0ca262"
            }
        },
        "fareDetails": {
            "DEL_SIN_0503_R_SIN_DEL_1503": {
                "colour": "Peach",
                "fare_id": "FARE-5ff5fcbe-448c-45c9-90bc-09c01bbf8292",
                "Discount": 1643.88,
                "currency": "INR",
                "fareType": "RegularFare",
                "fare_rule": "",
                "vendor_id": "",
                "offeredFare": 90736.12,
                "isRefundable": False,
                "fareBreakdown": [
                    {
                        "tax": 14860.0,
                        "baseFare": 31330.0,
                        "passengerType": "adults"
                    }
                ],
                "publishedFare": 92380.0,
                "transaction_id": "OB800[TBO]ac4QNaOOXpd70mdkqmPQyiveBonpoXrm7b3s20l8/..."
            }
        },
        "gst_details": None,
        "pax_details": [
            {
                "id": "d4672382-be02-49f0-824a-990d441bfdf1",
                "type": "adults",
                "title": "Mr",
                "firstName": "Amjad",
                "lastName": "Naushad",
                "nationality": "IN",
                "gender": "Male",
                "dob": "25-11-1996T00:00:00.000Z",
                "passport": "CDTFVYGBHN",
                "passport_expiry": "02-02-2026T00:00:00.000Z",
                "passport_issue_date": "03-02-2016T00:00:00.000Z",
                "passport_issue_country_code": "IN",
                "address_1": "",
                "address_2": "",
                "barcode_encoded": {
                    "DEL_SIN_R_SIN_DEL": "iVBORw0KGgoAAAANSUhEUgAAAikAAACmCAIAAACQiIhtAAAGQUlEQV..."
                }
            },
            {
                "id": "b9676f29-1f6b-4f92-b8f0-95c4a60691cd",
                "type": "adults",
                "title": "Ms",
                "firstName": "SINI",
                "lastName": "AMJAD",
                "nationality": "IN",
                "gender": "Female",
                "dob": "16-04-1996T00:00:00.000Z",
                "passport": "DSFG4567FGH",
                "passport_expiry": "16-09-2031T00:00:00.000Z",
                "passport_issue_date": "17-09-2021T00:00:00.000Z",
                "passport_issue_country_code": "IN",
                "address_1": "",
                "address_2": "",
                "barcode_encoded": {
                    "DEL_SIN_R_SIN_DEL": "iVBORw0KGgoAAAANSUhEUgAAAikAAACmCAIAAACQiIhtAAAGRklEQV..."
                }
            }
        ],
        "itineraries": [
            "DEL_SIN_0503_R_SIN_DEL_1503"
        ],
        "DEL_SIN_0503_R_SIN_DEL_1503": {
            "Discount": 1677.42,
            "currency": "INR",
            "offerFare": 90702.58,
            "segmentID": "VEN-d955334e-37f5-48dd-ba1f-4c81b2337c28_$_SEG-8ae9b521-e9ec-4c36-867f-fa5ebcfe0631",
            "publishFare": 92380.0,
            "flightSegments": {
                "DEL_SIN_0503": [
                    {
                        "stop": 0,
                        "arrival": {
                            "city": "Singapore",
                            "country": "Singapore",
                            "terminal": "2",
                            "airportCode": "SIN",
                            "airportName": "Changi",
                            "countryCode": "SG",
                            "arrivalDatetime": "2025-03-06T07:00:00"
                        },
                        "departure": {
                            "city": "Delhi",
                            "country": "India",
                            "terminal": "3",
                            "airportCode": "DEL",
                            "airportName": "Indira Gandhi Airport",
                            "countryCode": "IN",
                            "departureDatetime": "2025-03-05T22:55:00"
                        },
                        "cabinClass": "Economy",
                        "airlineCode": "AI",
                        "airlineName": "Air India",
                        "flightNumber": "2380",
                        "isRefundable": True,
                        "equipmentType": "789",
                        "fareBasisCode": "QL2YXSDY",
                        "seatsRemaining": 9,
                        "isChangeAllowed": True,
                        "durationInMinutes": 335
                    }
                ],
                "SIN_DEL_1503": [
                    {
                        "stop": 0,
                        "arrival": {
                            "city": "Delhi",
                            "country": "India",
                            "terminal": "3",
                            "airportCode": "DEL",
                            "airportName": "Indira Gandhi Airport",
                            "countryCode": "IN",
                            "arrivalDatetime": "2025-03-16T03:00:00"
                        },
                        "departure": {
                            "city": "Singapore",
                            "country": "Singapore",
                            "terminal": "2",
                            "airportCode": "SIN",
                            "airportName": "Changi",
                            "countryCode": "SG",
                            "departureDatetime": "2025-03-15T23:00:00"
                        },
                        "cabinClass": "Economy",
                        "airlineCode": "AI",
                        "airlineName": "Air India",
                        "flightNumber": "2383",
                        "isRefundable": True,
                        "equipmentType": "321",
                        "fareBasisCode": "QL2YXSDY",
                        "seatsRemaining": 4,
                        "isChangeAllowed": True,
                        "durationInMinutes": 390
                    }
                ]
            },
            "CheckIn_Baggage": "25 KG",
            "Cabin_Baggage": "Included"
        },
        "access": {
            "status": True,
            "info": "Access granted. You can now view the booking."
        }
    }

    response_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "session_id": openapi.Schema(
            type=openapi.TYPE_STRING,
            format="uuid",
            example="43504b22-b73c-41b5-8afb-611e3a7f6b83"
        ),
        "booking_id": openapi.Schema(
            type=openapi.TYPE_STRING,
            format="uuid",
            example="8f3b57f4-dedf-4e62-b892-efb02cb61d03"
        ),
        "booked_at": openapi.Schema(
            type=openapi.TYPE_STRING,
            example="03-03-2025T16:58:48Z"
        ),
        "display_id": openapi.Schema(
            type=openapi.TYPE_STRING,
            example="FLT25-0303-0257"
        ),
        "search_details": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "flight_type": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="DOM"  # Use "INT" for international
                ),
                "journey_type": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="One Way"  # Or "Round Trip"
                ),
                "journey_details": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "source_city": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                example="VNS"
                            ),
                            "destination_city": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                example="BOM"
                            ),
                            "travel_date": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                example="15-05-2025"
                            ),
                        }
                    )
                ),
                "passenger_details": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "adults": openapi.Schema(
                            type=openapi.TYPE_INTEGER,
                            example=1
                        ),
                        "children": openapi.Schema(
                            type=openapi.TYPE_INTEGER,
                            example=0
                        ),
                        "infants": openapi.Schema(
                            type=openapi.TYPE_INTEGER,
                            example=0
                        ),
                    }
                ),
                "fare_type": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="Regular"
                ),
                "cabin_class": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="Economy"
                ),
            }
        ),
        "organization_details": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "support_email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="email",
                    example="amjad@xyz.com"
                ),
                "support_phone": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="9447508305"
                ),
                "profile_img_url": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="url",
                    example="image url"
                ),
                "profile_address": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="Thrive Space"
                ),
                "profile_name": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="COMPANY NAME"
                ),
            }
        ),
        "contact": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "phone": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="976543210"
                ),
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="email",
                    example="abc@gmail.com"
                ),
            }
        ),
        "booking_details": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            additionalProperties=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "BookingId": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="76337038"
                    ),
                    "airline_pnr": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="K4JKWM"
                    ),
                    "gds_pnr": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="K4JKWM"
                    ),
                    "date": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="03-03-2025T16:58:48Z"
                    ),
                    "status": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="Confirmed"
                    ),
                    "error": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example=""
                    ),
                    "itinerary_id": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="f758972d-565f-449a-86ad-0e5dfa3ae0ca"
                    ),
                }
            )
        ),
        "fareDetails": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            additionalProperties=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "colour": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="Peach"
                    ),
                    "fare_id": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="FARE-97adceeb-082e-436e-b489-678bcd28b47c"
                    ),
                    "Discount": openapi.Schema(
                        type=openapi.TYPE_NUMBER,
                        example=33.95
                    ),
                    "currency": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="INR"
                    ),
                    "fareType": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="RegularFare"
                    ),
                    "fare_rule": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example=""
                    ),
                    "vendor_id": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example=""
                    ),
                    "offeredFare": openapi.Schema(
                        type=openapi.TYPE_NUMBER,
                        example=6867.05
                    ),
                    "isRefundable": openapi.Schema(
                        type=openapi.TYPE_BOOLEAN,
                        example=True
                    ),
                    "fareBreakdown": openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "tax": openapi.Schema(
                                    type=openapi.TYPE_NUMBER,
                                    example=1177.0
                                ),
                                "baseFare": openapi.Schema(
                                    type=openapi.TYPE_NUMBER,
                                    example=5724.0
                                ),
                                "passengerType": openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    example="adults"
                                ),
                            }
                        )
                    ),
                    "publishedFare": openapi.Schema(
                        type=openapi.TYPE_NUMBER,
                        example=6901.0
                    ),
                    "transaction_id": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="OB14[TBO]/2Nn3NqGUswrQU37rKkiz1JFr9AXp9IJJHvDn3JwYpXDE+..."
                    ),
                    "supplier_offerFare": openapi.Schema(
                        type=openapi.TYPE_NUMBER,
                        example=6867.05
                    ),
                    "supplier_publishFare": openapi.Schema(
                        type=openapi.TYPE_NUMBER,
                        example=6901
                    ),
                    "seats_price": openapi.Schema(
                        type=openapi.TYPE_NUMBER,
                        example=0
                    ),
                    "meals_price": openapi.Schema(
                        type=openapi.TYPE_NUMBER,
                        example=0
                    ),
                    "baggage_price": openapi.Schema(
                        type=openapi.TYPE_NUMBER,
                        example=0
                    ),
                }
            )
        ),
        "gst_details": openapi.Schema(
            type=openapi.TYPE_STRING,
            nullable=True,
            example=None
        ),
        "pax_details": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "id": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="8df5778b-08b7-4024-9344-4d28e1dae748"
                        ),
                        "type": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="adults"
                        ),
                        "title": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="Mr"
                        ),
                        "firstName": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="Amjad"
                        ),
                        "lastName": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="Naushad"
                        ),
                        "nationality": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="IN"
                        ),
                        "gender": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="Male"
                        ),
                        "dob": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example=""
                        ),
                        "passport": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example=""
                        ),
                        "passport_expiry": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example=""
                        ),
                        "passport_issue_date": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example=""
                        ),
                        "passport_issue_country_code": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="IN"
                        ),
                        "address_1": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example=""
                        ),
                        "address_2": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example=""
                        ),
                        "barcode_encoded": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            additionalProperties=openapi.Schema(
                                type=openapi.TYPE_STRING,
                                example="iVBORw0KGgoAAAANSUhEUgAAAikAAACCCAIAAAAMtc9NAAAEwklEQV..."
                            )
                        ),
                    }
                )
            ),
            "itineraries": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_STRING,
                    example="VNS_BOM_1505"  # Or "DEL_SIN_0503_R_SIN_DEL_1503" for international
                )
            ),
            # To capture the dynamic flight segment details (keyed by itinerary ID), we add a dedicated property.
            "flight_segments_by_itinerary": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                additionalProperties=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "Discount": openapi.Schema(
                            type=openapi.TYPE_NUMBER,
                            example=34.64
                        ),
                        "currency": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="INR"
                        ),
                        "offerFare": openapi.Schema(
                            type=openapi.TYPE_NUMBER,
                            example=6866.36
                        ),
                        "segmentID": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="VEN-d955334e-37f5-48dd-ba1f-4c81b2337c28_$_SEG-423d5b90-88ef-4418-add7-2daf36b77822"
                        ),
                        "publishFare": openapi.Schema(
                            type=openapi.TYPE_NUMBER,
                            example=6901.0
                        ),
                        "flightSegments": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            additionalProperties=openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        "stop": openapi.Schema(
                                            type=openapi.TYPE_INTEGER,
                                            example=0
                                        ),
                                        "arrival": openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "city": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="Mumbai"
                                                ),
                                                "country": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="India"
                                                ),
                                                "terminal": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="2"
                                                ),
                                                "airportCode": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="BOM"
                                                ),
                                                "airportName": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="Chhatrapati Shivaji Maharaj International Airport"
                                                ),
                                                "countryCode": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="IN"
                                                ),
                                                "arrivalDatetime": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="2025-05-15T18:30:00"
                                                ),
                                            }
                                        ),
                                        "departure": openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                "city": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="Varanasi"
                                                ),
                                                "country": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="India"
                                                ),
                                                "terminal": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example=""
                                                ),
                                                "airportCode": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="VNS"
                                                ),
                                                "airportName": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="Varanasi"
                                                ),
                                                "countryCode": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="IN"
                                                ),
                                                "departureDatetime": openapi.Schema(
                                                    type=openapi.TYPE_STRING,
                                                    example="2025-05-15T16:15:00"
                                                ),
                                            }
                                        ),
                                        "cabinClass": openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            example="Economy"
                                        ),
                                        "airlineCode": openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            example="IX"
                                        ),
                                        "airlineName": openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            example="Air India Express"
                                        ),
                                        "flightNumber": openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            example="2547"
                                        ),
                                        "isRefundable": openapi.Schema(
                                            type=openapi.TYPE_BOOLEAN,
                                            example=True
                                        ),
                                        "equipmentType": openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            example="7M8"
                                        ),
                                        "fareBasisCode": openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            example="ONSA000"
                                        ),
                                        "seatsRemaining": openapi.Schema(
                                            type=openapi.TYPE_INTEGER,
                                            example=6
                                        ),
                                        "isChangeAllowed": openapi.Schema(
                                            type=openapi.TYPE_BOOLEAN,
                                            example=True
                                        ),
                                        "durationInMinutes": openapi.Schema(
                                            type=openapi.TYPE_INTEGER,
                                            example=135
                                        ),
                                    }
                                )
                            )
                        ),
                        "CheckIn_Baggage": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="15KG"
                        ),
                        "Cabin_Baggage": openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="7 KG"
                        ),
                    }
                )
            ),
            "access": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "status": openapi.Schema(
                        type=openapi.TYPE_BOOLEAN,
                        example=True
                    ),
                    "info": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        example="Access granted. You can now view the booking."
                    ),
                }
            ),
        }
    )

    @swagger_auto_schema(
        operation_id="14_TicketStatus",
        operation_summary="14 - Ticket Status",
        operation_description="""
                This endpoint retrieves comprehensive booking details using a unique booking identifier. When a client sends a request with a booking_id (formatted as a UUID), the API responds with an extensive summary of the booking, including session, itinerary, fare, and passenger information.

                Key features of the API include:

                - Booking Overview:
                Returns a unique session identifier, booking ID, and booking timestamp along with a display identifier.

                - Search Details:
                Provides information about the flight search, such as:

                    - Flight Type: Domestic (DOM) or International (INT).
                    - Journey Type: One Way or Round Trip.
                    - Journey Details: Contains source and destination cities and travel dates.
                    - Passenger Details: Includes the count of adults, children, and infants.
                    - Fare Type & Cabin Class: Specifies the fare category and the travel class.
                
                - Organization Details:
                Lists the contact and profile details of the booking organization, such as support email, phone number, profile image URL, address, and organization name.

                - Booking & Fare Details:
                Details like booking reference numbers, airline and GDS PNRs, status, error messages (if any), and a breakdown of fare information. The fare details include:

                    - Discounts, offered and published fares.
                    - Fare breakdown for individual passengers.
                    - Transaction IDs and fare-specific identifiers.
                
                - Passenger Details:
                Contains an array of passenger records with personal and travel document information (e.g., passport details).

                - Itineraries & Flight Segments:
                Lists itinerary identifiers and provides dynamic flight segment information for each itinerary. Flight segments include:

                    - Detailed arrival and departure information (cities, airports, terminals, and times).
                    - Flight specifics such as airline details, flight numbers, equipment types, refundable status, and travel duration.
                    - Baggage allowances (check-in and cabin).

                This API is versatile and supports both domestic one-way and international round-trip bookings, with the response structure adapting to the booking type.
                """,
        request_body = openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    required=['booking_id'],
                                    properties={
                                        'booking_id': openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            format='uuid',
                                            example="8f3b57f4-dedf-4e62-b892-efb02cb61d03"
                                        )
                                    }
                                ),
        responses={
            200: openapi.Response(
                description="Booking details response (see examples for domestic one-way and international round-trip)",
                examples={
                    "domestic_one_way": domestic_response_example,
                    "international_round_trip": international_response_example,
                },
                schema=response_schema
            )
        },
        deprecated=False,  
        tags=["Flight Booking"], 
    ) 
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    

class OutAPICancellationCharges(CancellationCharges):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="15_CancellationCharges",
        operation_summary="15 - Cancellation Charges",
        operation_description="""
        This API get the cancellation charge against the itinerary. 
        """,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'booking_id': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Unique identifier for the booking"
                ),
                'itinerary_id': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Unique identifier for the itinerary"
                ),
                'pax_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="List of passenger IDs"
                ),
            },
            required=['booking_id', 'itinerary_id', 'pax_ids']
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'status': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Operation status"
                    ),
                    'cancellation_charge': openapi.Schema(
                        type=openapi.TYPE_NUMBER,
                        format="float",
                        description="Calculated cancellation charge"
                    ),
                    'currency': openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Currency symbol"
                    ),
                }
            )
        },
        deprecated=False,  
        tags=["Flight Booking"], 
    ) 
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class OutAPICancelTicket(CancelTicket):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_id="16_CancelTicket",
        operation_summary="16 - Cancel Ticket",
        operation_description="""
        Cancel passenger-wise ticket based on the provided booking details and passenger IDs.
        If the status is apart from `CANCELLATION REJECTED`, please call `14 - Ticket Status` API to get the latest status.
        """,
        request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "booking_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                format="uuid",
                description="Unique booking identifier"
            ),
            "itinerary_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                format="uuid",
                description="Unique itinerary identifier"
            ),
            "remarks": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Remarks for the cancellation"
            ),
            "pax_ids": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="uuid",
                    description="Passenger ID"
                ),
                description="List of passenger IDs to cancel"
            )
        },
        required=["booking_id", "itinerary_id", "remarks", "pax_ids"]
        ),
        responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "status": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Operation status",
                    default="success"
                ),
                "info": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Additional information about the cancellation in case of status = `Failure`"
                )
            }
        ),
        400: "Bad Request"
        },
        deprecated=False,  
        tags=["Flight Booking"], 
    ) 
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    
class OutAPIGetFareRule(GetFareRule):
    authentication_classes = [OutApiJWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)