# views.py

import time
import itertools
import operator
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from math import ceil
from vendors.flights import mongo_handler
from django.core.paginator import Paginator

class UserJourneyView(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request, *args, **kwargs):
        """
        POST Body expects:
        {
            "date": "DD-MM-YYYY" ,
            "org_id":       "1234",  (optional)
            "page":         1,
            "page_size":    10
        }
        Returns paginated documents + a global summary.
        """
        start = time.time()
        mongo_client = mongo_handler.Mongo()
        data = request.data
        date_str = data.get('date')
        # --- 1) Parse inputs ---
        input_date = datetime.strptime(date_str, "%d-%m-%Y")  # returns a datetime.date

        # Construct start_of_day and end_of_day for matching
        start_of_day = datetime(input_date.year, input_date.month, input_date.day)
        end_of_day = start_of_day + timedelta(days=1)  # exclusive upper bound

        org_id = data.get("org_id")

        page      = int(data.get("page", 1))
        page_size = int(data.get("page_size", 10))
        skip_count = (page - 1) * page_size

        # --- 2) Build match_filter for the 'searches_collection' ---
        match_filter = {
            "timestamp": {
                "$gte": int(start_of_day.timestamp()),
                "$lt": int(end_of_day.timestamp())
            }
        }
        if org_id:
            match_filter["organisation_id"] = org_id
            # or if it's inside masterDoc:
            # match_filter["master.organisation_id"] = org_id

        # --- 3) First pipeline: get summary for ALL matching documents (no skip/limit) ---
        # We’ll reuse the same pipeline structure you had, minus pagination stages.
        # Then we do "summarize_docs()" on the full result set to get the global summary.
        searches_collection = mongo_client.searches

        # (3a) Build pipeline for summary (no skip/limit):
        pipeline_for_summary = [
            {"$match": match_filter},
            {
                "$group": {
                    "_id": "$session_id",
                    "masterDoc": {"$first": "$$ROOT"}
                }
            },
            {
                "$lookup": {
                    "from": "searches",
                    "localField": "_id",
                    "foreignField": "session_id",
                    "as": "allDocs"
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "session_id": "$masterDoc.session_id",
                    "timestamp": "$masterDoc.timestamp",
                    "user_info": {
                        "name":  "$masterDoc.name",
                        "email": "$masterDoc.email",
                        "phone": "$masterDoc.phone"
                    },
                    # your pipeline used "organaization" (spelled differently); adjust if needed
                    "organization_id": "$masterDoc.organaization",
                    "cabin_class": "$masterDoc.cabin_class",
                    "journey_type": "$masterDoc.journey_type",
                    "journey_details": "$masterDoc.journey_details",
                    "passenger_details": "$masterDoc.passenger_details",

                    "fare": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {"$eq": ["$$this.type", "fare"]}
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "air_pricing": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {"$eq": ["$$this.type", "air_pricing"]}
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "ssr": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {"$eq": ["$$this.type", "ssr"]}
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "hold": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {"$eq": ["$$this.type", "hold"]}
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "create_booking": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {"$eq": ["$$this.type", "create_booking"]}
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "purchase_initiated_wallet": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {
                                            "$and": [
                                                {"$eq": ["$$this.type", "purchase_initiated"]},
                                                {"$eq": ["$$this.payment_mode", "Wallet"]}
                                            ]
                                        }
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "purchase_initiated_razorpay": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {
                                            "$and": [
                                                {"$eq": ["$$this.type", "purchase_initiated"]},
                                                {"$eq": ["$$this.payment_mode", "Razorpay"]}
                                            ]
                                        }
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "book": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {"$eq": ["$$this.type", "book"]}
                                    }
                                }
                            },
                            0
                        ]
                    },
                }
            }
        ]

        results_for_summary = list(searches_collection.aggregate(pipeline_for_summary))
        if len(results_for_summary) > 0:
            summary = self.summarize_docs(results_for_summary)
        else:
            summary = {
                'session': 0, 'fare': 0, 'air_pricing': 0, 'ssr': 0, 
                'hold': 0, 'create_booking': 0, 'purchase_initiated_wallet': 0,
                'purchase_initiated_razorpay': 0, 'book': 0, 'drop_fare': 0,
                'drop_air_pricing': 0, 'drop_create_booking': 0, 'drop_purchase': 0
            }

        # --- 4) Second pipeline for paginated data ---
        # We use $facet to get:
        #    1) "data": the actual page of docs
        #    2) "metadata": the total doc count
        # so we can compute total pages.
        pipeline_for_pagination = [
            {"$match": match_filter},
            {
                "$group": {
                    "_id": "$session_id",
                    "masterDoc": {"$first": "$$ROOT"}
                }
            },
            {
                "$lookup": {
                    "from": "searches",
                    "localField": "_id",
                    "foreignField": "session_id",
                    "as": "allDocs"
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "session_id": "$masterDoc.session_id",
                    "timestamp": "$masterDoc.timestamp",
                    "user_info": {
                        "name":  "$masterDoc.name",
                        "email": "$masterDoc.email",
                        "phone": "$masterDoc.phone"
                    },
                    # same caution about "organaization" vs "organisation_id"
                    "organisation_id": "$masterDoc.organisation_id",
                    "cabin_class": "$masterDoc.cabin_class",
                    "journey_type": "$masterDoc.journey_type",
                    "journey_details": "$masterDoc.journey_details",
                    "passenger_details": "$masterDoc.passenger_details",

                    "fare": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {"$eq": ["$$this.type", "fare"]}
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "air_pricing": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {"$eq": ["$$this.type", "air_pricing"]}
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "ssr": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {"$eq": ["$$this.type", "ssr"]}
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "hold": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {"$eq": ["$$this.type", "hold"]}
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "create_booking": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {"$eq": ["$$this.type", "create_booking"]}
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "purchase_initiated_wallet": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {
                                            "$and": [
                                                {"$eq": ["$$this.type", "purchase_initiated"]},
                                                {"$eq": ["$$this.payment_mode", "Wallet"]}
                                            ]
                                        }
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "purchase_initiated_razorpay": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {
                                            "$and": [
                                                {"$eq": ["$$this.type", "purchase_initiated"]},
                                                {"$eq": ["$$this.payment_mode", "Razorpay"]}
                                            ]
                                        }
                                    }
                                }
                            },
                            0
                        ]
                    },
                    "book": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$allDocs",
                                        "cond": {"$eq": ["$$this.type", "book"]}
                                    }
                                }
                            },
                            0
                        ]
                    },
                }
            },
            {
                "$facet": {
                    "data": [
                        {"$skip": skip_count},
                        {"$limit": page_size}
                    ],
                    "metadata": [
                        {"$count": "total"}
                    ]
                }
            }
        ]

        paginated_result = list(searches_collection.aggregate(pipeline_for_pagination))
        if not paginated_result:
            # No documents match
            return Response({
                "status": True,
                "data": [],
                "summary": summary,
                "count": 0,
                "num_pages": 0,
                "current_page": page
            })

        facet_item = paginated_result[0]
        docs_page  = facet_item["data"]
        meta_page  = facet_item["metadata"]
        total_docs = meta_page[0]["total"] if meta_page else 0
        num_pages  = ceil(total_docs / page_size)

        # --- 5) Now retrieve data from flight_suppliers_collection for the sessions in this page ---
        #    Only for these session_ids to avoid big fetch of everything.
        session_ids_in_page = [doc.get("session_id") for doc in docs_page if doc.get("session_id")]
        if session_ids_in_page:
            flight_suppliers_collection = mongo_client.flight_supplier
            
            # Build pipeline:
            pipeline_flight = [
                {
                    "$match": {
                        "createdAt": {
                            "$gte": start_of_day,
                            "$lt": end_of_day
                        },
                        "session_id": {"$in": session_ids_in_page, "$ne": None}
                    }
                },
                {
                    "$group": {
                        "_id": "$session_id",
                        "flight_search": {
                            "$push": {
                                "$cond": [
                                    {"$eq": ["$api", "flight_search"]},
                                    {
                                        "vendor": "$vendor",
                                        "status": "$response.status",
                                        "info": {
                                            "$cond": [
                                                {"$eq": ["$response.status", False]},
                                                "$response.data",
                                                "$$REMOVE"
                                            ]
                                        }
                                    },
                                    "$$REMOVE"
                                ]
                            }
                        },
                        "fare_rule": {
                            "$push": {
                                "$cond": [
                                    {"$eq": ["$api", "fare_rule"]},
                                    {
                                        "vendor": "$vendor",
                                        "status": "$response.status",
                                        "info": {
                                            "$cond": [
                                                {"$eq": ["$response.status", False]},
                                                "$response.data",
                                                "$$REMOVE"
                                            ]
                                        }
                                    },
                                    "$$REMOVE"
                                ]
                            }
                        },
                        "fare_quote": {
                            "$push": {
                                "$cond": [
                                    {"$eq": ["$api", "fare_quote"]},
                                    {
                                        "vendor": "$vendor",
                                        "status": "$response.status",
                                        "info": {
                                            "$cond": [
                                                {"$eq": ["$response.status", False]},
                                                "$response.data",
                                                "$$REMOVE"
                                            ]
                                        }
                                    },
                                    "$$REMOVE"
                                ]
                            }
                        },
                        "ssr": {
                            "$push": {
                                "$cond": [
                                    {"$eq": ["$api", "ssr"]},
                                    {
                                        "vendor": "$vendor",
                                        "status": "$response.status",
                                        "info": {
                                            "$cond": [
                                                {"$eq": ["$response.status", False]},
                                                "$response.data",
                                                "$$REMOVE"
                                            ]
                                        }
                                    },
                                    "$$REMOVE"
                                ]
                            }
                        },
                        "hold": {
                            "$push": {
                                "$cond": [
                                    {"$eq": ["$api", "hold"]},
                                    {
                                        "vendor": "$vendor",
                                        "status": "$response.status",
                                        "info": {
                                            "$cond": [
                                                {"$eq": ["$response.status", False]},
                                                "$response.data",
                                                "$$REMOVE"
                                            ]
                                        }
                                    },
                                    "$$REMOVE"
                                ]
                            }
                        },
                        # Combine ticket_lcc, ticket, ticket_booking_details, ticket_book => "book"
                        "book": {
                            "$push": {
                                "$cond": [
                                    {
                                        "$in": [
                                            "$api",
                                            ["ticket_lcc", "ticket", "ticket_booking_details", "ticket_book"]
                                        ]
                                    },
                                    {
                                        "vendor": "$vendor",
                                        "status": "$response.status",
                                        "info": {
                                            "$cond": [
                                                {"$eq": ["$response.status", False]},
                                                "$response.data",
                                                "$$REMOVE"
                                            ]
                                        }
                                    },
                                    "$$REMOVE"
                                ]
                            }
                        }
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "session_id": "$_id",
                        "flight_search": 1,
                        "fare_rule": 1,
                        "fare_quote": 1,
                        "ssr": 1,
                        "hold": 1,
                        "book": 1
                    }
                }
            ]
            flight_result = list(flight_suppliers_collection.aggregate(pipeline_flight))

            # Convert flight_result into a dict keyed by session_id
            flight_dict = {d["session_id"]: d for d in flight_result}
        else:
            flight_dict = {}

        # --- 6) Merge docs_page (from searches) with flight_dict data ---
        corrected_list = []
        for doc in docs_page:
            sid = doc.get("session_id")
            # Attach "api_data" from flight_dict if session_id exists
            if sid and sid in flight_dict:
                merged = {
                    **doc,
                    "api_data": flight_dict[sid]
                }
            else:
                merged = {
                    **doc,
                    "api_data": {}
                }
            corrected_list.append(merged)

        # --- 7) Construct final response ---
        response_data = {
            "status": True,
            "results": corrected_list,  # This page of data only
            "summary": summary,      # Full summary from entire dataset
            "count": total_docs,     # total matching docs (for pagination)
            "num_pages": num_pages,
            "current_page": page,
            "execution_time":time.time()-start
        }
        return Response(response_data)


    def summarize_docs(self,docs):
        """
        Summarize docs as you originally did.
        This calculates drop rates, etc.
        """
        import time
        current_ts = int(time.time())
        fifteen_minutes_ago = current_ts - 900  # 900 seconds

        boolean_fields = [
            "fare",
            "air_pricing",
            "ssr",
            "hold",
            "create_booking",
            "purchase_initiated_wallet",
            "purchase_initiated_razorpay",
            "book"
        ]

        # Summaries for all docs
        all_summary = {
            key: sum(doc.get(key, False) for doc in docs)
            for key in boolean_fields
        }
        all_summary["session"] = sum(bool(doc.get("session_id")) for doc in docs)

        # Summaries for "old" docs (timestamp <= 15 minutes ago)
        old_docs = [
            doc for doc in docs
            if doc.get("timestamp", 0) <= fifteen_minutes_ago
        ]
        old_summary = {
            key: sum(doc.get(key, False) for doc in old_docs)
            for key in boolean_fields
        }
        old_summary["session"] = sum(bool(doc.get("session_id")) for doc in old_docs)

        drop_fare = old_summary["session"] - old_summary["fare"]
        drop_air_pricing = old_summary["fare"] - old_summary["air_pricing"]
        drop_create_booking = old_summary["air_pricing"] - old_summary["create_booking"]
        drop_purchase = (
            old_summary["create_booking"]
            - old_summary["purchase_initiated_wallet"]
            - old_summary["purchase_initiated_razorpay"]
            - old_summary["hold"]
        )

        final_summary = {
            **all_summary,
            "drop_fare": drop_fare,
            "drop_air_pricing": drop_air_pricing,
            "drop_create_booking": drop_create_booking,
            "drop_purchase": drop_purchase
        }
        
        return final_summary


class UserJourneyDetailsView(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request, *args, **kwargs):
        """
        POST Body expects:
        {
            "date": "DD-MM-YYYY" ,
            "org_id":       "1234",  (optional)
            "page":         1,
            "page_size":    10
        }
        Returns paginated documents + a global summary.
        """
        start = time.time()
        mongo_client = mongo_handler.Mongo()
        data = request.data
        date_str = data.get('date')
        org_id = data.get('org_id',None)
        page      = int(data.get('page', 1))
        page_size = int(data.get('page_size', 10))
        input_date = datetime.strptime(date_str, '%d-%m-%Y')  # returns a datetime.date

        # Construct start_of_day and end_of_day for matching
        start_of_day = datetime(input_date.year, input_date.month, input_date.day)
        end_of_day = start_of_day + timedelta(days=1)  # exclusive upper bound

        # Build the match filter
        match_filter = {
            "timestamp": {
                "$gte": int(start_of_day.timestamp()),
                "$lt": int(end_of_day.timestamp())
            }
        }

        if org_id:
            match_filter["master.organaization"] = org_id
            # or if organisation_id is only inside masterDoc:
            # match_filter["master.organisation_id"] = org_id
        # Build the pipeline
        pipeline = [
                {"$match": match_filter},
                {
                    "$group": {
                        "_id": "$session_id",
                        "masterDoc": {"$first": "$$ROOT"}
                    }
                },
                {
                    "$lookup": {
                        "from": "searches",
                        "localField": "_id",
                        "foreignField": "session_id",
                        "as": "allDocs"
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "session_id": "$masterDoc.session_id",
                        "timestamp": "$masterDoc.timestamp",
                        "user_info": {"name":"$masterDoc.name","email":"$masterDoc.email","phone":"$masterDoc.phone"},
                        "organisation_id": "$masterDoc.organaization",
                        "cabin_class": "$masterDoc.cabin_class",
                        "journey_type": "$masterDoc.journey_type",
                        "journey_details": "$masterDoc.journey_details",
                        "passenger_details": "$masterDoc.passenger_details",
                        "flight_type": "$masterDoc.flight_type",
                        "fare_type":"$masterDoc.fare_type",
                        "search": {
                            "$gt": [
                                {
                                    "$size": {
                                        "$filter": {
                                            "input": "$allDocs",
                                            "cond": {"$eq": ["$$this.type", "master"]}
                                        }
                                    }
                                },
                                0
                            ]
                        },
                        "fare": {
                            "$gt": [
                                {
                                    "$size": {
                                        "$filter": {
                                            "input": "$allDocs",
                                            "cond": {"$eq": ["$$this.type", "fare"]}
                                        }
                                    }
                                },
                                0
                            ]
                        },
                        "air_pricing": {
                            "$gt": [
                                {
                                    "$size": {
                                        "$filter": {
                                            "input": "$allDocs",
                                            "cond": {"$eq": ["$$this.type", "air_pricing"]}
                                        }
                                    }
                                },
                                0
                            ]
                        },
                        "ssr": {
                            "$gt": [
                                {
                                    "$size": {
                                        "$filter": {
                                            "input": "$allDocs",
                                            "cond": {"$eq": ["$$this.type", "ssr"]}
                                        }
                                    }
                                },
                                0
                            ]
                        },
                        "hold": {
                            "$gt": [
                                {
                                    "$size": {
                                        "$filter": {
                                            "input": "$allDocs",
                                            "cond": {"$eq": ["$$this.type", "hold"]}
                                        }
                                    }
                                },
                                0
                            ]
                        },
                        "create_booking": {
                            "$gt": [
                                {
                                    "$size": {
                                        "$filter": {
                                            "input": "$allDocs",
                                            "cond": {"$eq": ["$$this.type", "create_booking"]}
                                        }
                                    }
                                },
                                0
                            ]
                        },
                        "purchase_initiated_wallet": {
                            "$gt": [
                                {
                                    "$size": {
                                        "$filter": {
                                            "input": "$allDocs",
                                            "cond": {
                                                "$and": [
                                                    {"$eq": ["$$this.type", "purchase_initiated"]},
                                                    {"$eq": ["$$this.payment_mode", "Wallet"]}
                                                ]
                                            }
                                        }
                                    }
                                },
                                0
                            ]
                        },
                        # purchase_initiated_razorpay => doc with type == "purchase_initiated" and payment_mode == "Razorpay"
                        "purchase_initiated_razorpay": {
                            "$gt": [
                                {
                                    "$size": {
                                        "$filter": {
                                            "input": "$allDocs",
                                            "cond": {
                                                "$and": [
                                                    {"$eq": ["$$this.type", "purchase_initiated"]},
                                                    {"$eq": ["$$this.payment_mode", "Razorpay"]}
                                                ]
                                            }
                                        }
                                    }
                                },
                                0
                            ]
                        },
                        "book": {
                            "$gt": [
                                {
                                    "$size": {
                                        "$filter": {
                                            "input": "$allDocs",
                                            "cond": {"$eq": ["$$this.type", "book"]}
                                        }
                                    }
                                },
                                0
                            ]
                        },
                    }
                }
            ]

        # Execute the aggregation
        results = list(mongo_client.searches.aggregate(pipeline))
        def summarize_docs(docs):
            current_ts = int(time.time())
            fifteen_minutes_ago = current_ts - 900  # 900 seconds = 15 minutes

            boolean_fields = [
                "fare",
                "air_pricing",
                "ssr",
                "hold",
                "create_booking",
                "purchase_initiated_wallet",
                "purchase_initiated_razorpay",
                "book"
            ]


            all_summary = {
                key: sum(doc.get(key, False) for doc in docs)
                for key in boolean_fields
            }
            all_summary["session"] = sum(bool(doc.get("session_id")) for doc in docs)


            old_docs = [
                doc for doc in docs
                if doc.get("timestamp", 0) <= fifteen_minutes_ago
            ]
            old_summary = {
                key: sum(doc.get(key, False) for doc in old_docs)
                for key in boolean_fields
            }
            old_summary["session"] = sum(bool(doc.get("session_id")) for doc in old_docs)


            drop_fare = old_summary["session"] - old_summary["fare"]
            drop_air_pricing = old_summary["fare"] - old_summary["air_pricing"]
            drop_create_booking = old_summary["air_pricing"]  - old_summary["create_booking"]
            drop_purchase = (
                old_summary["create_booking"]
                - old_summary["purchase_initiated_wallet"]
                - old_summary["purchase_initiated_razorpay"]
                
            )

            final_summary = {
                **all_summary,  # Expand all_summary keys
                "drop_fare": drop_fare,
                "drop_air_pricing": drop_air_pricing,
                "drop_create_booking": drop_create_booking,
                "drop_purchase": drop_purchase
            }

            return final_summary



        if len(results)>0:
            summary = summarize_docs(results)
        else:
            summary = {'session': 0,
            'fare': 0,
            'air_pricing': 0,
            'ssr': 0,
            'hold': 0,
            'create_booking': 0,
            'purchase_initiated_wallet': 0,
            'purchase_initiated_razorpay': 0,
            'book': 0,
            'drop_fare': 0,
            'drop_air_pricing': 0,
            'drop_create_booking': 0,
            'drop_purchase': 0}

        pipeline = [
            {
                # Match documents by createdAt range and ensure session_id is NOT null
                "$match": {
                    "createdAt": {
                        "$gte": start_of_day,
                        "$lt": end_of_day
                    },
                    "session_id": { "$ne": None }
                }
            },
            {
                "$group": {
                    # Group by session_id only
                    "_id": "$session_id",
                    
                    "flight_search": {
                        "$push": {
                            "$cond": [
                                { "$eq": [ "$api", "flight_search" ] },
                                {
                                    "vendor": "$vendor",
                                    "status": "$response.status",
                                    "info": {
                                        "$cond": [
                                            { "$eq": [ "$response.status", False ] },
                                            "$response.data",
                                            "$$REMOVE"
                                        ]
                                    }
                                },
                                "$$REMOVE"
                            ]
                        }
                    },
                    "fare_rule": {
                        "$push": {
                            "$cond": [
                                { "$eq": [ "$api", "fare_rule" ] },
                                {
                                    "vendor": "$vendor",
                                    "status": "$response.status",
                                    "info": {
                                        "$cond": [
                                            { "$eq": [ "$response.status", False ] },
                                            "$response.data",
                                            "$$REMOVE"
                                        ]
                                    }
                                },
                                "$$REMOVE"
                            ]
                        }
                    },
                    "fare_quote": {
                        "$push": {
                            "$cond": [
                                { "$eq": [ "$api", "fare_quote" ] },
                                {
                                    "vendor": "$vendor",
                                    "status": "$response.status",
                                    "info": {
                                        "$cond": [
                                            { "$eq": [ "$response.status", False ] },
                                            "$response.data",
                                            "$$REMOVE"
                                        ]
                                    }
                                },
                                "$$REMOVE"
                            ]
                        }
                    },
                    "ssr": {
                        "$push": {
                            "$cond": [
                                { "$eq": [ "$api", "ssr" ] },
                                {
                                    "vendor": "$vendor",
                                    "status": "$response.status",
                                    "info": {
                                        "$cond": [
                                            { "$eq": [ "$response.status", False ] },
                                            "$response.data",
                                            "$$REMOVE"
                                        ]
                                    }
                                },
                                "$$REMOVE"
                            ]
                        }
                    },
                    "hold": {
                        "$push": {
                            "$cond": [
                                { "$eq": [ "$api", "hold" ] },
                                {
                                    "vendor": "$vendor",
                                    "status": "$response.status",
                                    "info": {
                                        "$cond": [
                                            { "$eq": [ "$response.status", False ] },
                                            "$response.data",
                                            "$$REMOVE"
                                        ]
                                    }
                                },
                                "$$REMOVE"
                            ]
                        }
                    },
                    
                    # Combine ticket_lcc, ticket, ticket_booking_details, ticket_book under the same key 'book'
                    "book": {
                        "$push": {
                            "$cond": [
                                { 
                                    "$in": [ 
                                        "$api", 
                                        [ "ticket_lcc", "ticket", "ticket_booking_details", "ticket_book" ] 
                                    ] 
                                },
                                {
                                    "vendor": "$vendor",
                                    "status": "$response.status",
                                    "info": {
                                        "$cond": [
                                            { "$eq": [ "$response.status", False ] },
                                            "$response.data",
                                            "$$REMOVE"
                                        ]
                                    }
                                },
                                "$$REMOVE"
                            ]
                        }
                    }
                }
            },
            {
                "$project": {
                    # Rename _id to session_id and keep only relevant fields
                    "_id": 0,
                    "session_id": "$_id",
                    "flight_search": 1,
                    "fare_rule": 1,
                    "fare_quote": 1,
                    "ssr": 1,
                    "hold": 1,
                    "book": 1  # 'book' now includes everything from ticket_lcc/ticket/ticket_booking_details/ticket_book
                }
            }
        ]

        result = list(mongo_client.flight_supplier.aggregate(pipeline))


        def group_by_key_groupby(records, main_key):
            # Sort records by the main_key for groupby to work properly
            sorted_records = sorted(records, key=operator.itemgetter(main_key))
            
            # groupby returns (group_value, group_iterator)
            # We construct a dict comprehension for the final result
            result = {
                key: [
                    {k: v for k, v in rec.items() if k != main_key} 
                    for rec in group
                ]
                for key, group in itertools.groupby(sorted_records, key=operator.itemgetter(main_key))
            }
            return result

        result_dict = group_by_key_groupby(result, "session_id")
        keys = result_dict.keys()

        corrected_list = [
            x | {"api_data": result_dict[x['session_id']][0]}
            if x.get('session_id') in keys
            else x | {"api_data": {}}
            for x in results
        ]

        # response_data = {
        #     "status": True,
        #     "data": corrected_list,
        #     "summary":summary
        # }
        paginator = Paginator(corrected_list, page_size)
        current_page = paginator.get_page(page)

        # 6. Construct the response
        final_response_data = {
            "count": paginator.count,
            "num_pages": paginator.num_pages,
            "current_page": current_page.number,
            "results": list(current_page.object_list),
            "summary":summary,
            "exec_time":time.time()-start
        }
        return Response(final_response_data)
