from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.authentication import BasicAuthentication
from rest_framework import status
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotFound
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
import threading
from common.permission import HasAPIAccess
from vendors.flights.flight_manager import FlightManager
from vendors.flights.abstract.abstract_flight_manager import AbstractFlightManager
from vendors.flights.utils import create_segment_keys,create_uuid,extract_data_recursive,get_fare_markup
from users.models import UserDetails,SupplierIntegration,LookupCreditCard,Organization
from common.models import (Booking,FlightBookingPaxDetails,FlightBookingItineraryDetails, FlightBookingFareDetails,   
            FlightBookingSSRDetails,LookupEasyLinkSupplier,FlightBookingJourneyDetails,FlightBookingAccess,FlightBookingUnifiedDetails)
from datetime import datetime,timezone
import concurrent.futures
import time,uuid
from pymongo import MongoClient
import re
import json,yaml
import os
import base64
from io import BytesIO
from pdf417 import encode, render_image, render_svg
from dotenv import load_dotenv
from django.db.models import F
load_dotenv() 
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .utils import get_flight_type,unique_fares

class CreateSessionView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
        tags=["Flight Search"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        data = request.data 
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)#request.user)
        data = flight_manager.create_session(data)
        return JsonResponse(data, status=201)

def deduplicate_master(out,search_query):
    unique_itineraries = [x.get('data',[]).get('itineraries',[]) for x in out]
    
    unique_itineraries = sum(unique_itineraries,[])
    
    unique_itineraries = list(set(unique_itineraries))
    
    final_unified_out = {}
    if not (search_query['journey_type'] == "Round Trip" and search_query['flight_type'] == "INT"):
        for itinerary in unique_itineraries:
            unique_segments = []
            unique_keys = []
            dup_keys = []
            for idx,ven in enumerate(out):
                if itinerary in ven['data']['itineraries'] and itinerary in ven['data']:
                    for idy,seg in enumerate(ven['data'][itinerary]):
                        keys = []
                        for s in seg.get('flightSegments',{}).get(itinerary,{}):
                            keys.append(s.get('airlineCode','')+s.get('flightNumber',''))
                        key  = "->".join(keys)
                        if key not in unique_keys:
                            unique_keys.append(key)
                            unique_segments.append({key:seg})
                        else:
                            dup_keys.append(key)
                            seg_existing = [x[key] for x in unique_segments if key in [*x]][0]
                            if seg_existing['offerFare'] > seg['offerFare']:
                                seg['segmentID'] = seg['segmentID'] + "_$#$_" + seg_existing['segmentID']
                                unique_segments.remove({key:seg_existing})
                                unique_segments.append({key:seg})
                            else:
                                unique_segments.remove({key:seg_existing})
                                seg_existing['segmentID'] = seg_existing['segmentID'] + "_$#$_" + seg['segmentID']
                                seg_existing['segmentID'] = ("_$#$_").join(list(set(seg_existing['segmentID'].split("_$#$_"))))
                                unique_segments.append({key:seg_existing})
                
                extracted_values = [list(d.values())[0] for d in unique_segments]
                final_unified_out[itinerary] = extracted_values
    else:
        unique_itinerary = unique_itineraries[0]
        itineraries = unique_itinerary.split("_R_")
    
        unique_segments = []
        unique_keys = []
        dup_keys = []
        for idx,ven in enumerate(out):
            if unique_itinerary in ven['data']:
                for idy,seg in enumerate(ven['data'][unique_itinerary]):
                    keys = []
                    for itinerary in itineraries:
                        for s in seg.get('flightSegments',{}).get(itinerary,{}):
                            keys.append(s.get('airlineCode','')+s.get('flightNumber',''))
                    key  = "->".join(keys)
                    if key not in unique_keys:
                        unique_keys.append(key)
                        unique_segments.append({key:seg})
                    else:
                        dup_keys.append(key)
                        seg_existing = [x[key] for x in unique_segments if key in [*x]][0]
                        if seg_existing['offerFare'] > seg['offerFare']:
                            seg['segmentID'] = seg['segmentID'] + "_$#$_" + seg_existing['segmentID']
                            unique_segments.remove({key:seg_existing})
                            unique_segments.append({key:seg})
                        else:
                            unique_segments.remove({key:seg_existing})
                            seg_existing['segmentID'] = seg_existing['segmentID'] + "_$#$_" + seg['segmentID']
                            seg_existing['segmentID'] = ("_$#$_").join(list(set(seg_existing['segmentID'].split("_$#$_"))))
                            unique_segments.append({key:seg_existing})
                
        extracted_values = [list(d.values())[0] for d in unique_segments]
        final_unified_out[unique_itinerary] = extracted_values
    
    return final_unified_out

class GetFlightsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
        tags=["Flight Search"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        data = request.data  
        flight_manager = FlightManager(user)
        session_id = data.get('session_id')
        start = time.time()
        validity = flight_manager.check_session_validity(session_id,True)
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"flight_search_response":{},"response_meta_data":response_meta_data,"session_id":session_id})
        master_doc = flight_manager.master_doc
        flight_type = get_flight_type(master_doc,request.user)
        vendors = flight_manager.get_vendors(journey_type = master_doc.get("journey_type"),flight_type = flight_type)
        duration = time.time()-start
        misc_data = {"duration":duration}
        if not master_doc:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"flight_search_response":{},"response_meta_data":response_meta_data,"session_id":session_id})
        search_details = {
             "flight_type":master_doc.get("flight_type"),
             "journey_type":master_doc.get("journey_type"),
             "journey_details":master_doc.get("journey_details"),
             "passenger_details":master_doc.get("passenger_details"),
             "fare_type":master_doc.get("fare_type"),
             "cabin_class":master_doc.get("cabin_class"),
             "preffered_airline":master_doc.get("preffered_airline"),
             "is_direct_flight":master_doc.get("is_direct_flight"),
                           }
        if "unified" in master_doc:
            start = time.time()
            unified_ids = list(master_doc["unified"].keys())
            is_all_vendors = len(unified_ids) == len(vendors)
            unified_responses = flight_manager.get_unified_doc(unified_ids)
            is_shown = [unified_vendor.get("is_shown") for unified_vendor in unified_responses]
            if not all(is_shown) :
                is_data_change = True
                flight_manager.update_is_showed_unified_docs(session_id,unified_ids)
            else:
                is_data_change = False
            duration = time.time() -start
            misc_data["unified"] = duration
            if len(unified_responses) == 0:
                response_meta_data = {"session_break": True,"info":"Looks like we couldn't get any flights for this search. <br> Please redo the search in other dates."}
                return JsonResponse({"flight_search_response":{},"response_meta_data":response_meta_data,"session_id":session_id})
            flight_data = list(unified_responses)
            for uni_response in unified_responses:
                for key,value in uni_response.get("data").items():
                    if key =="itineraries":
                        continue
                    else:
                        for x in value:
                            x.pop("misc",{})
            
            start = time.time()
            for x in flight_data:
                if '_id' in x:
                    del x['_id']
            duration = time.time()-start
            misc_data["id"] = duration
            start = time.time()
            unified_data =  deduplicate_master(flight_data,master_doc)
            duration = time.time()-start
            misc_data["deduplicate"] = duration
            unified_data["itineraries"] = create_segment_keys(master_doc)
            vendors = master_doc["vendors"]
            status_list = [y for x,y in vendors.items()]
            is_unified = "Unified" in status_list
            has_start_or_raw = "Start" in status_list or "Raw" in status_list
            search_metadata = {
                "error_status": not is_unified and not has_start_or_raw,
                "is_complete": is_unified and not has_start_or_raw and is_all_vendors,
                "is_data_change" :is_data_change
            } 
            response_meta_data = {"session_break":search_metadata.get("error_status")}
            if response_meta_data.get("error_status"):
                response_meta_data["info"] = "Supplier services are temporarily unavailable. Please try again later."
            return_data = unified_data | {"search_details":search_details} |{"search_metadata":search_metadata}
            return JsonResponse({"flight_search_response":return_data,"response_meta_data":response_meta_data,"session_id":session_id,"misc":misc_data})
        else:
            search_meta_data = {
            "error_status": False,
            "is_complete": False,
            "is_data_change":True
            }
            response_meta_data = {"session_break": False,"info":""}
            return JsonResponse({"flight_search_response":{"search_metadata":search_meta_data, "search_details":search_details},"session_id":session_id,"misc":misc_data,"response_meta_data":response_meta_data})

class GetFareDetails(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
        tags=["Flight Search"],  # You can group endpoints by tags in Swagger
    ) 
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data
        session_id = data.get('session_id')
        segment_id = data.get('segment_id')
        validity = flight_manager.check_session_validity(session_id)
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"fareDetails":[],"response_meta_data":response_meta_data,"session_id":session_id})
        # master_doc = flight_manager.master_doc

        def get_fare_details_for_segment(flight_manager, session_id, segment_id):
            fare_doc,status =  flight_manager.get_fare_details(session_id, segment_id)
            return {"fare":fare_doc,"status":status}

        def get_fare_details_with_threads(flight_manager, session_id, segment_ids):
            results = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []

                for segment_id in segment_ids:
                    futures.append(executor.submit(get_fare_details_for_segment, flight_manager, session_id, segment_id))

                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    results.append(result)
            return results
        segment_ids= segment_id.split("_$#$_")
        response = get_fare_details_with_threads(flight_manager, session_id, segment_ids)
        result = []
        for x in response:
            status_out = x.get("status") == "success"
            if status_out:
                fare_details = x.get("fare").get("fareDetails", {})
                result.extend(fare_details)
        response_meta_data = {"session_break":status_out}
        result = sorted(result, key = lambda x: x["offeredFare"])
        result = unique_fares(result)
        status_out = all(x.get("status") != "success" for x in response)
        if status_out:
            response_meta_data = {"session_break":status_out}
            response_meta_data["info"] = "Fare information is currently unavailable from supplier."
        else:
            response_meta_data = {"session_break":status_out,"info":""}
        return JsonResponse({'session_id': session_id,"fareDetails":result,"response_meta_data":response_meta_data},
                             status = status.HTTP_201_CREATED)
 
class AirPricing(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
        tags=["Flight Search"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data 
        session_id = data.get('session_id')

        validity = flight_manager.check_session_validity(session_id)
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"flight_air_pricing":{},"response_meta_data":response_meta_data,"session_id":session_id})
        segment = data.get('segments')
        start= time.time()
        response = flight_manager.get_updated_fare_quote(segment)
        duration = time.time()-start
        response_meta_data = {"session_break":response.get("status",False),"duration":duration}
        if response.get("status",False):
            response_meta_data["info"] = "Unable to retrieve latest fare details from suppliers."    
        return JsonResponse({"flight_air_pricing":response,"status":"success","response_meta_data":response_meta_data}, 
                            status = status.HTTP_201_CREATED)
   
class FlightsSSR(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
        tags=["Flight Search"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data 
        session_id = data.get('session_id')
        segments = data.get('segments')
        validity = flight_manager.check_session_validity(session_id)
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"flight_ssr_response":{},"response_meta_data":response_meta_data,"session_id":session_id})
        master_doc = flight_manager.master_doc
        raw_list = master_doc.get('raw', {})
        segment_keys = create_segment_keys(master_doc)
        ssr_response = {}
        ssr_raw = {}
        segment_ids = {}
        error_dict = {}
        ssr_id = create_uuid("SSR")
        ssr_doc_mongo = flight_manager.mongo_client.fetch_all_with_sessionid(session_id = session_id, type = "ssr")
        ssr_doc_mongo = False
        if not ssr_doc_mongo:
            for index,seg in enumerate(segments):
                segment_id = seg.get("segment_id")
                target_vendor_id = segment_id.split("_$_")[0]
                vendor_uuiid = segment_id.split("_$_")[0].split("VEN-")[1]
                manager = flight_manager.get_manager_from_id(vendor_uuiid)
                if manager.name() not in ["Amadeus"]:
                    raw_ids = list(master_doc["raw"].keys())
                    raw_docs = flight_manager.get_raw_doc(raw_ids)
                    raw_docs_dict = {x["raw_id"]: x for x in raw_docs}
                    target_vendor_id = segment_id.split("_$_")[0]
                    for key, value in raw_list.items():
                        vendor_id = value.get('id')
                        if vendor_id == target_vendor_id:
                            raw_doc = raw_docs_dict[key]
                            raw_data = manager.find_segment_by_id(raw_doc,segment_id,master_doc)
                            flight_ssr_response = manager.get_ssr(segment_key = segment_keys[index],raw_data = raw_data,
                                                                raw_doc = raw_doc,session_id = session_id)
                            ssr_response.update(flight_ssr_response.get("data",{}))
                            segment_ids.update({segment_keys[index]:segment_id})
                            ssr_raw.update({segment_keys[index]:flight_ssr_response.get("raw")})
                            if flight_ssr_response.get("status") == False:
                                error_dict.update({segment_keys[index]:flight_ssr_response.get("raw")}) 
                else:

                    unified_ids = list(master_doc["unified"].keys())
                    unified_docs = flight_manager.mongo_client.fetch_all_with_sessionid(session_id = session_id, type =  "unified")
                    unified_docs_dict = {x["unified_id"]: x for x in unified_docs}
                    target_vendor_id = segment_id.split("_$_")[0]
                    master_unified_data = master_doc.get('unified', {})
                    for key, value in master_unified_data.items():
                        vendor_id = value.get('id')
                        if vendor_id == target_vendor_id:
                            unified_doc = unified_docs_dict[key]
                            unified_data = flight_manager.get_unified_data(unified_doc,segment_id)
                            itinerary_key = unified_data.get("itinerary")
                            flight_ssr_response = manager.get_ssr(segment_key = segment_keys[index],raw_data = unified_data,
                                                                raw_doc = unified_doc,session_id = session_id,passenger_details =master_doc.get("passenger_details"))
                            ssr_response.update(flight_ssr_response.get("data",{}))
                            segment_ids.update({segment_keys[index]:segment_id})
                            ssr_raw.update({segment_keys[index]:flight_ssr_response.get("raw")})
                            if flight_ssr_response.get("status") == False:
                                error_dict.update({segment_keys[index]:flight_ssr_response.get("raw")})
            ssr_doc = {
                        "raw": ssr_raw,
                        "unified":ssr_response,
                        "segments":segment_ids,
                        "ssr_id":ssr_id,
                        "createdAt":datetime.now()
                        }
            filter_query = {"session_id": session_id,"type":"ssr"}
            update_data = {"$set": ssr_doc}
            flight_manager.mongo_client.searches.update_one(filter_query, update_data, upsert = True)
        else:
           error_dict = {}
           ssr_response = ssr_doc_mongo[0].get("unified",{})
        search_details = {
             "flight_type":master_doc.get("flight_type"),
             "journey_type":master_doc.get("journey_type"),
             "journey_details":master_doc.get("journey_details"),
             "passenger_details":master_doc.get("passenger_details"),
             "fare_type":master_doc.get("fare_type"),
             "cabin_class":master_doc.get("cabin_class"),
                           }
        return_data = {'session_id': session_id,"search_details":search_details,"itineraries":segment_keys} | ssr_response
        response_meta_data = {"session_break": True,"info":error_dict} if error_dict!={} else {"session_break": False,"info":""}
        return JsonResponse({"flight_ssr_response":return_data,'session_id': session_id,"response_meta_data":response_meta_data},
                             status = status.HTTP_201_CREATED)
    
class GetFareRule(APIView):
    authentication_classes =[JWTAuthentication]
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        try:
            kwargs = request.data
            user_id = request.user.id
            user =  UserDetails.objects.filter(id=user_id ).first()
            flight_manager = FlightManager(user)
            fare_rule,mini_fare_rule = flight_manager.get_fare_rule(**kwargs)
            return JsonResponse ({"fare_rule": fare_rule,"mini_fare_rules":mini_fare_rule},status = status.HTTP_201_CREATED)
        except:
            return JsonResponse ({"fare_rule": "No Fare Rule Available","mini_fare_rules":""},status = status.HTTP_201_CREATED)

class CreateBooking(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
    tags=["Flight Search"],  # You can group endpoints by tags in Swagger
    )   
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        session_id = request.data.get('session_id')
        validity = flight_manager.check_session_validity(session_id)
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"response_meta_data":response_meta_data,"session_id":session_id})
        booking = flight_manager.create_booking(session_id,request.data)
        if booking.get("booking"):
            return JsonResponse({'session_id': session_id,"booking_id":booking["booking"].id,"display":booking["booking"].display_id,
                                "response_meta_data":{"session_break": False,"info":booking.get("info","")},"status":booking["status"]},
                                status = status.HTTP_201_CREATED)
        else:
            return JsonResponse({'session_id': session_id,
                                "response_meta_data":{"session_break": True,"info":booking.get("info","")},"status":booking["status"]},
                                status = status.HTTP_201_CREATED)

class BookingStatus(APIView):
    permission_classes = [HasAPIAccess]
    @csrf_exempt  
    def post(self, request, *args, **kwargs):
        user =  UserDetails.objects.filter(id = request.user.id).first()
        flight_manager = FlightManager(user)
        booking_id = request.data.get('booking_id')
        return_data = flight_manager.booking_status(booking_id)
        return JsonResponse(return_data, status = status.HTTP_201_CREATED)

class CheckHold(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
    tags=["Flight Search"],  # You can group endpoints by tags in Swagger
    ) 
    def post(self, request, *args, **kwargs):
        user =  UserDetails.objects.filter(id = request.user.id).first()
        flight_manager = FlightManager(user)
        session_id = request.data.get('session_id')
        booking_id = request.data.get('booking_id')

        validity = flight_manager.check_session_validity(session_id)
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"flight_search_response":{},"response_meta_data":response_meta_data,"session_id":session_id})
        response = flight_manager.check_hold(session_id,booking_id)
        response_meta_data = {"session_break":False,"info":""}
        final_response = response | {"response_meta_data":response_meta_data}
        return JsonResponse(final_response, status = status.HTTP_201_CREATED)

class HoldBooking(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
    tags=["Flight Search"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        user =  UserDetails.objects.filter(id = request.user.id).first()
        flight_manager = FlightManager(user)
        session_id = request.data.get('session_id')
        booking_id = request.data.get('booking_id')
        
        validity = flight_manager.check_session_validity(session_id)
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"flight_search_response":{},"response_meta_data":response_meta_data,"session_id":session_id})
        flight_manager.hold_booking(data = request.data)
        response_meta_data = {"session_break": False,"info":""}
        return JsonResponse({"status":True,"response_meta_data":response_meta_data}, status = status.HTTP_201_CREATED)

class Purchase(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
    tags=["Flight Search"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        purchase_data = request.data
        user =  UserDetails.objects.filter(id = request.user.id).first()
        flight_manager = FlightManager(user)
        booking = Booking.objects.filter(id = purchase_data.get("booking_id")).first()
        session_id = booking.session_id
        validity = flight_manager.check_session_validity(session_id)
        flight_manager.mongo_client.searches.insert_one({"session_id":session_id,"booking_id":purchase_data.get("booking_id"),
                                                         "type":"purchase_initiated","payment_mode":purchase_data.get("payment_mode"),
                                                         "createdAt":datetime.now()})
        if not validity:
            response_meta_data = {"session_break": True,"info":"To keep things secure, your session is limited to 15 minutes. It looks like time's up! <br> Please restart to complete your booking."}
            return JsonResponse({"flight_purchase_response":{},"response_meta_data":response_meta_data,"session_id":session_id})
        if purchase_data.get("payment_mode","wallet").strip().lower() == "wallet":
            wallet_thread = threading.Thread(target = flight_manager.purchase, kwargs={'data': purchase_data,"wallet":True})
            wallet_thread.start()
            return JsonResponse({"status":True,"razorpay_url":None,"response_meta_data":{"session_break":False, "info":""}}, status = status.HTTP_201_CREATED) 
        else:
            response = flight_manager.purchase(data = purchase_data,wallet = False)
            return JsonResponse({"status":True,"razorpay_url":response.get("payment_url"),"error":response.get("error"),"response_meta_data":{"session_break":False, "info":""}}, 
                                status = status.HTTP_201_CREATED) 

class PurchaseStatus(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
    tags=["Flight Search"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        user =  UserDetails.objects.filter(id = request.user.id).first()
        flight_manager = FlightManager(user)
        response = flight_manager.purchase_response(booking_id = request.data.get('booking_id'))
        return JsonResponse(response, status = status.HTTP_201_CREATED)

class ConvertHoldtoTicket(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
        tags=["Flight Search"],  # You can group endpoints by tags in Swagger
    )
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data
        booking_id = data.get('booking_id')
        flight_manager.convert_hold_to_ticket(booking_id)
        return JsonResponse({"status":True}, status=201)

class ReleaseHold(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
        tags=["Flight Search"], 
    ) 
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data
        booking_id = data.get('booking_id')
        response = flight_manager.release_hold(booking_id)
        response["booking_id"] = booking_id
        return_data= {"response":response}
        return JsonResponse(return_data, status = status.HTTP_201_CREATED)

class TicketStatus(APIView):
    @csrf_exempt  
    def post(self, request, *args, **kwargs):
        try:
            pax_details = []
            booking_details = {}
            data_unified_dict = {"itineraries":[]}
            user_id = request.user.id
            user =  UserDetails.objects.filter(id=user_id ).first()
            data = request.data
            booking_id = data.get('booking_id')
            booking_doc = Booking.objects.prefetch_related(
                    'flightbookingjourneydetails_set',  
                    'flightbookingitinerarydetails_set',
                    'flightbookingpaxdetails_set',
                    'flightbookingunifieddetails_set',
                    'flightbookingaccess_set'
                ).get(id=booking_id)
            session_id = booking_doc.session_id
            booked_at = convert_pax_date(booking_doc.modified_at,passport=False) if booking_doc.source == "Online" \
                        else convert_pax_date(booking_doc.booked_at,passport=False)
            aws_bucket = os.getenv('AWS_STORAGE_BUCKET_NAME',"")
            profile_pic = "https://{}.s3.amazonaws.com/media/{}".format(aws_bucket,str(booking_doc.user.organization.profile_picture))
            organization_details = {"support_email":booking_doc.user.organization.support_email,"support_phone":booking_doc.user.organization.support_phone,
                                    "profile_img_url":profile_pic,"profile_address":booking_doc.user.organization.address,
                                    "profile_name":booking_doc.user.organization.organization_name}
            search_details = {
                "flight_type":booking_doc.search_details.flight_type,
                "journey_type":booking_doc.search_details.journey_type,
                "journey_details":[],
                "passenger_details":yaml.safe_load(booking_doc.search_details.passenger_details),
                "fare_type":booking_doc.search_details.fare_type,
                "cabin_class":booking_doc.search_details.cabin_class,
                            }
            itinerary_list = booking_doc.flightbookingitinerarydetails_set.all().order_by('itinerary_index')
            itinerary_data_unified = list(booking_doc.flightbookingunifieddetails_set.values('itinerary_data_unified'))
            fare_details_unified = list(booking_doc.flightbookingunifieddetails_set.values('fare_details'))
            for data_unified in itinerary_data_unified:
                for key in data_unified["itinerary_data_unified"]:
                    data_unified_dict["itineraries"].append(key)
                    full_data = data_unified["itinerary_data_unified"][key]
                    for pop_key in ['Discount', 'currency', 'offerFare',"publishFare"]:
                        full_data.pop(pop_key)
                    data_unified_dict[key] = full_data
            for itinerary in itinerary_list:
                if itinerary.status in ["Cancel-Ticket-Failed","Failed-Confirmed","Confirmed"]:
                    itinerary_status = "Confirmed"
                elif itinerary.status == "Failed-Rejected":
                    itinerary_status = "Rejected"
                elif itinerary.status in ["Ticketing-Initiated","Hold-Initiated"]:
                    itinerary_status = "In-Progress"
                else:
                    itinerary_status = itinerary.status
                booking_dict = {"booking_ref_no":itinerary.supplier_booking_id,
                                "airline_pnr":itinerary.airline_pnr if itinerary.airline_pnr else "N/A",
                                "gds_pnr":itinerary.gds_pnr if itinerary.gds_pnr else "N/A",
                                "date":convert_pax_date(itinerary.modified_at,passport=False),
                                "status":itinerary_status,
                                "is_soft_fail":itinerary.soft_fail,
                                "error":itinerary.error,
                                "itinerary_id":itinerary.id,
                                "provider":itinerary.vendor.name.upper()
                                }
                journey_detail = booking_doc.flightbookingjourneydetails_set.filter(itinerary=itinerary.id).first()
                journey_detail_dict = {"source_city":journey_detail.source,"destination_city":journey_detail.destination,
                                    "travel_date":journey_detail.date}
                search_details["journey_details"].append(journey_detail_dict)
                booking_details[itinerary.itinerary_key] = booking_dict
                data_unified_dict[itinerary.itinerary_key]["CheckIn_Baggage"] = (
                                    itinerary.default_baggage.get("checkInBag", "N/A")
                                    if itinerary.default_baggage else "N/A"
                                )
                data_unified_dict[itinerary.itinerary_key]["Cabin_Baggage"] = (
                                            (itinerary.default_baggage.get("cabinBag", "N/A")
                                            if booking_doc.source == "Online"
                                            else itinerary.default_baggage.get("cabinBag", "7 kg"))
                                            if itinerary.default_baggage else "N/A"
                                        )
            
            pax_list = booking_doc.flightbookingpaxdetails_set.all().order_by('created_at')
            fare_details_final = {}
            for pax in pax_list:
                barcode_encoded = generate_barcode(pax,data_unified_dict,booking_details)
                pax_data = {
                            "id":pax.id,
                            "type": pax.pax_type,
                            "title": pax.title if pax.title else "",
                            "firstName": pax.first_name,
                            "lastName": pax.last_name,
                            "nationality":pax.passport_issue_country_code if pax.passport_issue_country_code else "",
                            "gender": pax.gender if pax.gender else "" ,
                            "dob": convert_pax_date(pax.dob,passport = True),
                            "passport": pax.passport if pax.passport else "" ,
                            "passport_expiry":convert_pax_date(pax.passport_expiry,passport = True),
                            "passport_issue_date" : convert_pax_date(pax. passport_issue_date,passport = True),
                            "passport_issue_country_code":pax.passport_issue_country_code,
                            "address_1":pax.address_1 if pax.address_1 else "",
                            "address_2":pax.address_2 if pax.address_2 else "",
                            "barcode_encoded":barcode_encoded
                            }
            
                for itinerary in itinerary_list:
                    ssr = FlightBookingSSRDetails.objects.filter(pax = pax,itinerary = itinerary).first()
                    fare_details = next(
                                (d["fare_details"] for d in fare_details_unified if itinerary.itinerary_key in d["fare_details"]),
                                None
                            )
                    if ssr:
                        baggage_ssr = safe_json_loads(ssr.baggage_ssr) 
                        meals_ssr = safe_json_loads(ssr.meals_ssr) 
                        seats_ssr = safe_json_loads(ssr.seats_ssr) 
                        seats_ssr = {k: ({} if v == [] else v) for k, v in seats_ssr.items()}
                        meals_price = sum(float(meals_ssr[segment].get("Price", 0)) for segment in meals_ssr if isinstance(meals_ssr[segment], dict)) 
                        seats_price = sum(float(seats_ssr[segment].get("Price", 0)) for segment in seats_ssr if isinstance(seats_ssr[segment], dict))
                        baggage_price = sum(float(baggage_ssr[segment].get("Price", 0)) for segment in baggage_ssr if isinstance(baggage_ssr[segment], dict))
                        baggage_ssr["journey"] = list(baggage_ssr.keys())
                        meals_ssr["journey"] = list(meals_ssr.keys())
                        seats_ssr["journey"] = list(seats_ssr.keys())
                        pax_data[itinerary.itinerary_key] = {"baggage_ssr":baggage_ssr,
                                                            "meals_ssr":meals_ssr,
                                                            "seats_ssr":seats_ssr,
                                                            "supplier_ticket_id":ssr.supplier_ticket_id,
                                                            "supplier_pax_id":ssr.supplier_pax_id,
                                                            "supplier_ticket_number":ssr.supplier_ticket_number if ssr.supplier_ticket_number else "N/A"
                                                                }
                        pax_data[itinerary.itinerary_key]["is_cancelled"] = ssr.cancellation_status
                        pax_data[itinerary.itinerary_key]["cancellation_status"] = ssr.cancellation_status.replace("CANCELLATION","").strip().upper() if ssr.cancellation_status else "NOT REQUESTED"
                        pax_data[itinerary.itinerary_key]["cancellation_info"] = ssr.cancellation_info
                        fare_details[itinerary.itinerary_key]["seats_price"] = fare_details[itinerary.itinerary_key].get("seats_price",0) + seats_price
                        fare_details[itinerary.itinerary_key]["meals_price"] = fare_details[itinerary.itinerary_key].get("meals_price",0) + meals_price
                        fare_details[itinerary.itinerary_key]["baggage_price"] = fare_details[itinerary.itinerary_key].get("baggage_price",0) + baggage_price
                    else:
                        pax_data[itinerary.itinerary_key] = {
                                        "baggage_ssr": {},
                                        "meals_ssr":{},
                                        "seats_ssr":{},
                                        "supplier_ticket_id":'',
                                        "supplier_pax_id":'',
                                        "supplier_ticket_number":'' 
                                            }
                        pax_data[itinerary.itinerary_key]["is_cancelled"] = None
                        pax_data[itinerary.itinerary_key]["cancellation_status"] = ssr.cancellation_status.replace("CANCELLATION","").strip().upper() if ssr.cancellation_status else "NOT REQUESTED"
                        pax_data[itinerary.itinerary_key]["cancellation_info"] = ssr.cancellation_info
                        fare_details[itinerary.itinerary_key]["seats_price"] = fare_details[itinerary.itinerary_key].get("seats_price",0) + 0
                        fare_details[itinerary.itinerary_key]["meals_price"] = fare_details[itinerary.itinerary_key].get("meals_price",0) + 0
                        fare_details[itinerary.itinerary_key]["baggage_price"] = fare_details[itinerary.itinerary_key].get("baggage_price",0) + 0
                    fare_details_final[itinerary.itinerary_key] = fare_details[itinerary.itinerary_key]
                pax_details.append(pax_data)
            contact = json.loads(booking_doc.contact)
            gst_details = json.loads(booking_doc.gst_details)
            access = booking_doc.flightbookingaccess_set.order_by('created_at').first()
            access_data = {"access": {"status": False, "info": ""}}
            if access:
                expiry_time = access.expiry_time if access.expiry_time else 0
                current_time = time.time()
                if access.userid == user:
                    access_data = {
                        "access": {
                            "status": True,
                            "info": "You already have access to this booking."
                        }
                    }
                elif expiry_time > current_time:
                    duration = expiry_time - current_time
                    minutes = int(duration // 60)
                    seconds = int(duration % 60)
                    info = f"This booking is currently being accessed by user {access.userid.first_name} {access.userid.last_name}. Please try again after {minutes} minutes and {seconds} seconds."
                    access_data = {
                        "access": {
                            "status": False,
                            "info": info
                        }
                    }
                else:
                    FlightBookingAccess.objects.update_or_create(
                        bookingid=booking_doc,
                        defaults={"userid": user, "expiry_time": time.time() + 180}
                    )
                    access_data = {
                        "access": {
                            "status": True,
                            "info": "Access granted. You can now view the booking."
                        }
                    }
            else:
                FlightBookingAccess.objects.create(
                    bookingid=booking_doc,
                    userid=user,
                    expiry_time=time.time() + 180
                )
                access_data = {
                    "access": {
                        "status": True,
                        "info": "Access granted. You can now view the booking."
                    }
                }
            return_data  =  {'status':'success','session_id': session_id,"booking_id":booking_id,"booked_at":booked_at,
                            "display_id":booking_doc.display_id,
                            "search_details":search_details,"organization_details":organization_details,
                            "contact":contact,"booking_details":booking_details,"fareDetails":fare_details_final,
                            "gst_details":gst_details,"pax_details":pax_details} | data_unified_dict |access_data
            return JsonResponse(return_data, status = status.HTTP_201_CREATED,safe=True)
        except:
            return JsonResponse({"status":"failure"}, status = status.HTTP_404_NOT_FOUND,safe = True)

class Repricing(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
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
        tags=["Flight Search"],  # You can group endpoints by tags in Swagger
    )  
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data 
        booking_id = data.get('booking_id')
        itinerary_details = FlightBookingItineraryDetails.objects.filter(booking_id=booking_id)

        def get_repricing_for_segment(flight_manager,itinerary):
            reprcing=  flight_manager.repricing(itinerary)
            return {"data":reprcing,"itinerary":itinerary}
        
        def get_repricing_with_threads(flight_manager,itinerary_details):
            results = {}
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                for itinerary in itinerary_details:
                    futures.append(executor.submit(get_repricing_for_segment, flight_manager,itinerary))
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()  # Get the result from the thread
                    itinerary = result.get("itinerary")
                    results[itinerary.itinerary_key] = result.get("data")
            return results

        response = get_repricing_with_threads(flight_manager,itinerary_details)
        is_fare_change = any(values.get("is_fare_change", False) for values in response.values())
        is_hold_continue = all(values.get("is_hold_continue", False) for values in response.values())
        error = {key: values.get("error","N/A") for key, values in response.items()}
        return JsonResponse(response|{"booking_id":booking_id,"status":"success","is_fare_change":is_fare_change,
                                      "is_hold_continue":is_hold_continue,"error":error}, status=201)
    
class CancellationCharges(APIView):
    permission_classes = [HasAPIAccess]
    @csrf_exempt  
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data
        itinerary_id = data.get('itinerary_id')
        pax_ids = data.get('pax_ids')
        queryset = Booking.objects.prefetch_related(
                    "flightbookingpaxdetails_set", "flightbookingjourneydetails_set",
                ).select_related("payment_details").filter(id = data.get('booking_id')).first()
        journey_details = queryset.flightbookingjourneydetails_set.all()
        additional_charge = float(queryset.payment_details.new_published_fare) - float(queryset.payment_details.supplier_published_fare)
        pax_details = queryset.flightbookingpaxdetails_set.all()
        itinerary = FlightBookingItineraryDetails.objects.filter(id = itinerary_id).first()
        cancellation=  flight_manager.cancellation_charges(itinerary,pax_details,pax_ids,journey_details,additional_charge)
        return JsonResponse(cancellation, status=201)
    
class CancelTicket(APIView):
    permission_classes = [HasAPIAccess]
    @csrf_exempt  
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data
        pax_ids = data.get('pax_ids')
        cancel_reason = data.get("remarks","")
        itinerary_id = data.get('itinerary_id')
        itinerary = FlightBookingItineraryDetails.objects.prefetch_related(
            "flightbookingssrdetails_set","flightbookingjourneydetails_set").filter(id = itinerary_id).first()
        cancel_data = flight_manager.cancel_ticket(itinerary = itinerary,remarks = cancel_reason,pax_ids = pax_ids)
        return JsonResponse(cancel_data, status=201)

class OfficeCodes(APIView):
    @csrf_exempt  
    def get(self,request):
        vendor = request.GET['vendor']
        vendors = SupplierIntegration.objects.all()
        office_ids = []
        supplier_map = {"amadeus":"amadeus","galileo":"travelport"}
        suppplier = supplier_map.get(vendor.lower())       
        for x in vendors:
            data = x.data
            if suppplier.lower() in x.name.lower():
                city_code =  data.get("city_code")
                if city_code:
                    office_ids.append(city_code)

        return JsonResponse({"status":"success","office_ids":sorted(office_ids)}, status=201)

class CreditCards(APIView):
    @csrf_exempt  
    def get(self,request):
        credit_cards = LookupCreditCard.objects.all()
        card_list = []
        for x in credit_cards:
            data = {"id":str(x.id),"display":str(x)}
            card_list.append(data)    
        return JsonResponse({"status":"success","credit_cards":card_list}, status=201)

class AgencyList(APIView):
    @csrf_exempt  
    def get(self,request):
        organizations = Organization.objects.all()
        agency_list = []
        for x in organizations:
            data = {"id":str(x.id),"display":str(x.organization_name)}
            agency_list.append(data)    
        return JsonResponse({"status":"success","agency_list":agency_list}, status=201)
    
class SupplierList(APIView):
    @csrf_exempt  
    def get(self,request):
        suppliers = LookupEasyLinkSupplier.objects.all()
        supplier_list = []
        for x in suppliers:
            data = {"id":str(x.id),"display":str(x.display_id)}
            supplier_list.append(data)    
        return JsonResponse({"status":"success","supplier_list":supplier_list}, status=201)

class OfflineImportPNR(APIView):
    @csrf_exempt  
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data 
        response = flight_manager.offline_import_pnr(data)
        return JsonResponse(response, status=201)     

class CreateOfflineBilling(APIView):
    @csrf_exempt  
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data 
        response = flight_manager.create_offline_billing(data,user)
        return JsonResponse(response, status=201)   

class TicketingImportPNR(APIView):
    @csrf_exempt  
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data 
        response = flight_manager.ticketing_import_pnr(data)

        return JsonResponse(response, status=201)    

    
class TicketingRepricing(APIView):
    @csrf_exempt  
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data 
        response = flight_manager.ticketing_repricing(data)

        return JsonResponse(response, status=201)

class TicketingCreate(APIView):
    @csrf_exempt  
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data 
        response = flight_manager.ticketing_create(data)

        return JsonResponse(response, status=201)
    
class CreateTicketingBilling(APIView):
    @csrf_exempt  
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        flight_manager = FlightManager(user)
        data = request.data 
        response = flight_manager.create_ticketing_billing(data)

        return JsonResponse(response, status=201)   
        
class FallToFail(APIView):
    @csrf_exempt  
    def post(self, request, *args, **kwargs):
        try:
            booking_id = request.data["booking_id"]
            booking_doc = Booking.objects.filter(id = booking_id).first()
            booked_itinerary = FlightBookingItineraryDetails.objects.filter(booking=booking_doc)
            for itinerary in booked_itinerary:
                itinerary.status = "Ticketing-Failed"
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","modified_at"])
            return JsonResponse({"status":True}, status = status.HTTP_201_CREATED)
        except:
            return JsonResponse({"status":False}, status=status.HTTP_404_NOT_FOUND) 

class CheckCancellationStatus(APIView):
    def post(self, request, *args, **kwargs):
        thread = threading.Thread(target = FlightManager("EventBridge").check_cancellation_status, daemon=True)
        thread.start()  
        return JsonResponse({"status":True}, status = status.HTTP_201_CREATED)
    
class UpdateTicketStatus(APIView): 
    def post(self, request, *args, **kwargs):
        thread = threading.Thread(target = FlightManager("EventBridge").update_ticket_status, daemon=True)
        thread.start()  
        return JsonResponse({"status":True}, status = status.HTTP_201_CREATED)
        
class UpdateFailedBooking(APIView):
    permission_classes = [HasAPIAccess]
    @csrf_exempt  
    def post(self, request, *args, **kwargs):
        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        data = request.data
        booking_id = data.get('booking_id')
        status = data.get('status')
        main_key = data.get('itinerary_key')
        itinerary_data =  data.get(main_key)
        booking_doc = Booking.objects.filter(id = booking_id).first()
        itinerary = FlightBookingItineraryDetails.objects.filter(booking=booking_doc,itinerary_key = main_key).first()
        info = ""
        if status =="Rejected":
            if itinerary.status != "Confirmed":
                itinerary.status = "Failed-Rejected"
                itinerary.modified_at = int(time.time())
                booking_doc.status = 'Failed-Rejected'
                itinerary.soft_fail = False
                booking_doc.modified_by = user
                booking_doc.save()
                itinerary.save(update_fields=["status","modified_at","soft_fail"])
            else:
                info = "Itinerary is already in confirmed status"
            if info == "":
                return JsonResponse({"status":"success"}, status=201)  
            else:
                return JsonResponse({"status":"success","info":info}, status=201)
        elif status == "Confirmed":
            if itinerary.status !="Confirmed":
                itinerary.airline_pnr = data[itinerary.itinerary_key]["airline_pnr"]
                itinerary.gds_pnr = data[itinerary.itinerary_key]["gds_pnr"].replace("N/A","")
                itinerary.status = "Failed-Confirmed"
                itinerary.soft_fail = False
                itinerary.modified_at = int(time.time())
                itinerary.save(update_fields=["status","airline_pnr","gds_pnr","modified_at","soft_fail"])
                pax_list =  itinerary_data.get("pax")
                booking_doc.status = 'Failed-Confirmed'
                booking_doc.modified_by = user
                booking_doc.save()
                for x in pax_list:
                    ssr = FlightBookingSSRDetails.objects.filter(pax__id = x.get("id"),itinerary=itinerary).first()
                    ssr.supplier_ticket_number = x.get("ticket_number","").strip()
                    ssr.save(update_fields=["supplier_ticket_number"])
                easy_link_out = self.save_easy_link(user,itinerary_data,itinerary)
                total_fare = self.calculate_itinerary_fare(itinerary)
                if total_fare:
                    ab_fm = AbstractFlightManager({},"")
                    ab_fm.update_credit(total_fare = total_fare,booking = booking_doc)
            else:
                info = "The Itinerary is already in confirmed status"
            if info == "":
                return Response({"status":"success","total_fare":total_fare,
                                "easy_link_error":easy_link_out.get("easy_link_error")}, status=201)  
            else:
                return Response({"status":"success","info":info,"total_fare":total_fare,
                                "easy_link_error":easy_link_out.get("easy_link_error")}, status=201)
        
    def calculate_itinerary_fare(self,itinerary):
        try:
            fare_obj = FlightBookingFareDetails.objects.filter(itinerary = itinerary).first()
            pub_fare = fare_obj.published_fare
            ssr_list = FlightBookingSSRDetails.objects.filter(itinerary=itinerary)
            ssr_value = 0
            for ssr in ssr_list:
                baggage_ssr = safe_json_loads(ssr.baggage_ssr) 
                meals_ssr = safe_json_loads(ssr.meals_ssr) 
                seats_ssr = safe_json_loads(ssr.seats_ssr) 
                seats_ssr = {k: ({} if v == [] else v) for k, v in seats_ssr.items()}
                meals_price = sum(meals_ssr[segment].get("Price", 0) for segment in meals_ssr if isinstance(meals_ssr[segment], dict)) 
                seats_price = sum(seats_ssr[segment].get("Price", 0) for segment in seats_ssr if isinstance(seats_ssr[segment], dict))
                baggage_price = sum(baggage_ssr[segment].get("Price", 0) for segment in baggage_ssr if isinstance(baggage_ssr[segment], dict))
                ssr_price = float(meals_price) + float(seats_price) + float(baggage_price)
                ssr_value+=ssr_price
            total_fare = float(pub_fare) + float(ssr_value)
            return total_fare
        except:
            return False

    def save_easy_link(self,user,data,main_itinerary):
        try:
            flight_manager = FlightManager(user)
            manager = flight_manager.get_manager_from_id(main_itinerary.vendor.id)
            fare_details = get_fare_markup(user)
            session_id =main_itinerary.booking.session_id
            master_doc = flight_manager.get_master_doc(session_id)
            pax_list = FlightBookingPaxDetails.objects.filter(booking = main_itinerary.booking)
            pax_details = []
            for pax in pax_list:
                pax_data = {
                            "id":pax.id,
                            "type": pax.pax_type,
                            "title": pax.title,
                            "firstName": pax.first_name,
                            "lastName": pax.last_name,
                            "nationality":"IN",
                            "gender": pax.gender,
                            "dob": convert_pax_date(pax.dob,passport = True),
                            "passport": pax.passport,
                            "passport_expiry":convert_pax_date(pax.passport_expiry,passport = True),
                            "passport_issue_date" : convert_pax_date(pax. passport_issue_date,passport = True),
                            "passport_issue_country_code":pax.passport_issue_country_code,
                            "address_1":pax.address_1,
                            "address_2":pax.address_2,
                            
                            }
                itinerary =main_itinerary
                ssr = FlightBookingSSRDetails.objects.filter(pax = pax,itinerary = itinerary).first()
                if ssr:
                    baggage_ssr = safe_json_loads(ssr.baggage_ssr) 
                    meals_ssr = safe_json_loads(ssr.meals_ssr) 
                    seats_ssr = safe_json_loads(ssr.seats_ssr) 
                    seats_ssr = {k: ({} if v == [] else v) for k, v in seats_ssr.items()}
                    baggage_ssr["journey"] = list(baggage_ssr.keys())
                    meals_ssr["journey"] = list(meals_ssr.keys())
                    seats_ssr["journey"] = list(seats_ssr.keys())
                    pax_data[itinerary.itinerary_key] = {"baggage_ssr":baggage_ssr,
                                                        "meals_ssr":meals_ssr,
                                                        "seats_ssr":seats_ssr,
                                                        "supplier_ticket_id":ssr.supplier_ticket_id,
                                                        "supplier_pax_id":ssr.supplier_pax_id,
                                                        "supplier_ticket_number":ssr.supplier_ticket_number
                                                            }                    
                else:
                    pax_data[itinerary.itinerary_key] = {
                                    "baggage_ssr": {},
                                    "meals_ssr":{},
                                    "seats_ssr":{},
                                    "supplier_ticket_id":"",
                                    "supplier_pax_id":"",
                                    "supplier_ticket_number":""
                                        }

                pax_details.append(pax_data)
            segment_id = itinerary.segment_id
            data_unified_dict = {}
            target_vendor_id = segment_id.split("_$_")[0]
            unified_data = master_doc.get('unified', {})
            unified_ids = list(master_doc["unified"].keys())
            unified_docs = flight_manager.get_unified_doc(unified_ids)
            unified_docs_dict = {x["unified_id"]: x for x in unified_docs}
            for key, value in unified_data.items():
                vendor_id = value.get('id')
                if vendor_id == target_vendor_id:
                    unified_doc = unified_docs_dict[key]
                    data_unified =  flight_manager.get_unified_data(unified_doc,segment_id)
                    data_unified_dict.update(data_unified)
            manager.save_failed_finance(master_doc,data,itinerary,pax_details,fare_details,data_unified_dict)
            return {"easy_link_error":False}
        except Exception as e:
            return {"easy_link_error":str(e)}

def safe_json_loads(data):
    """Safely load JSON, returning an empty dictionary if the input is None or invalid."""
    try:
        return json.loads(data) if data else {}
    except (json.JSONDecodeError, TypeError):
        return {}
    
def convert_pax_date(date,passport):
    try:
        if not passport:
            dt = datetime.fromtimestamp(date, tz=timezone.utc)
            formatted_timestamp = dt.strftime("%d-%m-%YT%H:%M:%SZ")
            return formatted_timestamp
        else:
            dt = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ")
            formatted_timestamp = dt.strftime("%d-%m-%YT%H:%M:%S.%fZ")[:-4] + "Z"
            return formatted_timestamp
    except:
        return ""

def generate_barcode(pax,flight_details,booking_details):
    try:
        barcodes = {}
        airline_pnr = ""
        pax_string = pax.title + " "+  pax.first_name + " /  "+ pax.last_name + " / "
        for key in flight_details:
            barcode_string = ""
            flight_string = ""
            airline_string = ""
            if key != "itineraries":
                airline_pnr = booking_details.get(key,{}).get("airline_pnr","")
                flight_segment = flight_details[key]["flightSegments"]
                for fight_data in flight_segment:
                    sub_sector = flight_segment[fight_data]
                    for sub_sector_flight in sub_sector:
                        flight_string += sub_sector_flight["departure"]["airportCode"] + "-" + \
                            sub_sector_flight["departure"]["city"] + " | " + \
                            sub_sector_flight["arrival"]["airportCode"] + "-" + \
                            sub_sector_flight["arrival"]["city"] + "/"
                        airline_string += sub_sector_flight["airlineCode"] + "-" + sub_sector_flight["flightNumber"] +"|"
                barcode_string = airline_pnr + " / " + pax_string + flight_string + airline_string
                image = render_image(encode(barcode_string.strip("|")))
                buffer = BytesIO()
                image.save(buffer, format = "PNG")
                buffer.seek(0)
                barcode_key = ''.join(re.findall(r'[A-Za-z_]', key)).strip("_").replace("__","_")
                barcodes[barcode_key] = base64.b64encode(buffer.read()).decode("utf-8")
        return barcodes
    except:
        return ""

