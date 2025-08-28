import requests
import html
import xml.etree.ElementTree as ET
from datetime import datetime
import xmltodict
import calendar
import pandas as pd
from datetime import datetime, timedelta
from users.models import Organization, UserDetails, ErrorLog
from accounting.shared.services import clean_data
from bookings.flight.models import Booking, FlightBookingItineraryDetails,FlightBookingPaxDetails
from django.db.models import Count, Q, F, Sum, Subquery,OuterRef



def total_confirmed_booking(**kwargs):

    filters = {}
    from_date = kwargs.get("from_date")
    to_date = kwargs.get("to_date")
    sales_agent_id = kwargs.get("sales_agent_id")
    if from_date and to_date:
        from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
        to_date_obj = (
            datetime.strptime(to_date, "%d/%m/%Y")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        from_date_epoch = int(from_date_obj.timestamp())
        to_date_epoch = int(to_date_obj.timestamp())
        filters["booked_at__range"] = [from_date_epoch, to_date_epoch]

    organization_id = kwargs.get("organization_id")
    if organization_id:
        filters["user__organization_id"] = organization_id

    if sales_agent_id:
        filters["user__organization__sales_agent_id"] = sales_agent_id

    bookings = Booking.objects.filter(**filters).annotate(
        total_itineraries=Count("flightbookingitinerarydetails"),
        confirmed_itineraries=Count(
            "flightbookingitinerarydetails",
            filter=Q(flightbookingitinerarydetails__status="Confirmed"),
        ),
    )

    total_booking_confirmed_count = bookings.filter(
        total_itineraries__gt=0,  
        total_itineraries=F("confirmed_itineraries"),
    ).count()
    total_confirmed_pax_count = bookings.filter(
        total_itineraries__gt=0,  
        total_itineraries=F("confirmed_itineraries"),
    ).aggregate(count=Count("flightbookingpaxdetails"))["count"]
    print("total_confirmed_pax_count-----",total_confirmed_pax_count)
    total_online_booking_confirmed_count = bookings.filter(
        total_itineraries__gt=0,  
        total_itineraries=F("confirmed_itineraries"),
        source="Online",
    ).count()
    online_paxcount = bookings.filter(
        total_itineraries__gt=0,  
        total_itineraries=F("confirmed_itineraries"),
        source="Online",
    ).aggregate(count=Count("flightbookingpaxdetails"))["count"]
    print("online_paxcount-----",online_paxcount)
    total_offline_booking_confirmed_count = bookings.filter(
        total_itineraries__gt=0,  
        total_itineraries=F("confirmed_itineraries"),
        source="Offline",
    ).count()
    offline_paxcount = bookings.filter(
        total_itineraries__gt=0,  
        total_itineraries=F("confirmed_itineraries"),
        source="Offline",
    ).aggregate(count=Count("flightbookingpaxdetails"))["count"]
    print("offline_paxcount-----",offline_paxcount)
    results = {
        "total_confirmed_bookings": total_booking_confirmed_count,
        "total_pax_count": total_confirmed_pax_count,
        "total_online_booking_confirmed_count": total_online_booking_confirmed_count,
        "total_online_pax": online_paxcount,
        "total_offline_booking_confirmed_count": total_offline_booking_confirmed_count,
        "total_offline_pax": offline_paxcount
    }
    return results


def total_amount_confirmed_booking(**kwargs):

    filters = {}
    from_date = kwargs.get("from_date")
    to_date = kwargs.get("to_date")
    organization_id = kwargs.get("organization_id")
    sales_agent_id = kwargs.get('sales_agent_id')

    if from_date and to_date:
        from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
        to_date_obj = (
            datetime.strptime(to_date, "%d/%m/%Y")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        from_date_epoch = int(from_date_obj.timestamp())
        to_date_epoch = int(to_date_obj.timestamp())
        filters["booked_at__range"] = [from_date_epoch, to_date_epoch]

    if organization_id:
        filters["user__organization_id"] = organization_id

    if sales_agent_id :
        filters["user__organization__sales_agent_id"] = sales_agent_id

    bookings = Booking.objects.filter(**filters)

    bookings = bookings.annotate(
        total_itineraries=Count("flightbookingitinerarydetails"),
        confirmed_itineraries=Count(
            "flightbookingitinerarydetails",
            filter=Q(flightbookingitinerarydetails__status="Confirmed"),
        ),
    )

    total_amount_confirmed = bookings.filter(
        total_itineraries__gt=0, total_itineraries=F("confirmed_itineraries")
    ).annotate(total_sum=Sum("payment_details__new_published_fare"))

    total_amount_confirmed_online = bookings.filter(
        total_itineraries__gt=0,
        total_itineraries=F("confirmed_itineraries"),
        source="Online",
    ).annotate(total_sum=Sum("payment_details__new_published_fare"))

    total_amount_confirmed_offline = bookings.filter(
        total_itineraries__gt=0,
        total_itineraries=F("confirmed_itineraries"),
        source="Offline",
    ).annotate(total_sum=Sum("payment_details__new_published_fare"))

    total_amount_confirmed = (
        total_amount_confirmed.aggregate(total=Sum("total_sum"))["total"] or 0
    )
    total_amount_confirmed_online = (
        total_amount_confirmed_online.aggregate(total=Sum("total_sum"))["total"] or 0
    )
    total_amount_confirmed_offline = (
        total_amount_confirmed_offline.aggregate(total=Sum("total_sum"))["total"] or 0
    )

    results = {
        "total_amount_confirmed": round(total_amount_confirmed),
        "total_amount_confirmed_online": round(total_amount_confirmed_online),
        "total_amount_confirmed_offline": round(total_amount_confirmed_offline),
    }
    return results


# def total_bookings(**kwargs):

#     filters = {}
#     from_date = kwargs.get("from_date")
#     to_date = kwargs.get("to_date")
#     sales_agent_id = kwargs.get('sales_agent_id')
#     if from_date and to_date:
#         from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
#         to_date_obj = (
#             datetime.strptime(to_date, "%d/%m/%Y")
#             + timedelta(days=1)
#             - timedelta(seconds=1)
#         )
#         from_date_epoch = int(from_date_obj.timestamp())
#         to_date_epoch = int(to_date_obj.timestamp())
#         filters["booked_at__range"] = [from_date_epoch, to_date_epoch]

#     organization_id = kwargs.get("organization_id")
#     if organization_id:
#         filters["user__organization_id"] = organization_id
#     if sales_agent_id:
#         filters["user__organization__sales_agent_id"] = sales_agent_id

#     bookings = Booking.objects.filter(**filters)
#     # total -booking
#     total_bookings = bookings.count()
#     # total-confirmed
#     bookings_confirmed = bookings.annotate(
#         total_itineraries=Count("flightbookingitinerarydetails"),
#         confirmed_itineraries=Count(
#             "flightbookingitinerarydetails",
#             filter=Q(flightbookingitinerarydetails__status="Confirmed"),
#         ),
#     )
    

#     total_booking_confirmed = bookings_confirmed.filter(
#         total_itineraries__gt=0,  # Ensure there are itineraries
#         total_itineraries=F("confirmed_itineraries"),
#     )
#     total_booking_confirmed_count = total_booking_confirmed.count()
#     # total - enquiry
#     bookings_enquiry = bookings.annotate(
#         total_itineraries=Count("flightbookingitinerarydetails"),
#         enquiry_itineraries=Count(
#             "flightbookingitinerarydetails",
#             filter=Q(flightbookingitinerarydetails__status="Enquiry"),
#         ),
#     )

#     total_booking_enquiry = bookings_enquiry.filter(
#         total_itineraries__gt=0,  # Ensure there are itineraries
#         total_itineraries=F("enquiry_itineraries"),
#     )

#     total_booking_enquiry_count = total_booking_enquiry.count()

    

#     # total - hold

#     bookings_hold = bookings.annotate(
#         total_itineraries=Count("flightbookingitinerarydetails"),
#         hold_itineraries=Count(
#             "flightbookingitinerarydetails",
#             filter=Q(flightbookingitinerarydetails__status="On-Hold"),
#         ),
#     )

#     total_booking_hold_count = bookings_hold.filter(
#         total_itineraries__gt=0,  # Ensure there are itineraries
#         total_itineraries=F("hold_itineraries"),
#     ).count()
    
#     # total-failed
#     bookings_failed = list(
#         set(
#             bookings.filter(
#                 flightbookingitinerarydetails__status__in=[
#                     "Ticketing-Failed",
#                     "Hold-Failed",
#                 ]
#             ).values_list("id", flat=True)
#         )
#     )

#     results = {
#         "total_bookings": total_bookings,
#         "total_booking_confirmed_count": total_booking_confirmed_count,
#         "total_booking_enquiry_count": total_booking_enquiry_count,
#         "total_booking_hold_count": total_booking_hold_count,
#         "bookings_failed": len(bookings_failed),
#     }
#     return results


def total_bookings(**kwargs):

    filters = {}
    from_date = kwargs.get("from_date")
    to_date = kwargs.get("to_date")
    sales_agent_id = kwargs.get('sales_agent_id')
    if from_date and to_date:
        from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
        to_date_obj = (
            datetime.strptime(to_date, "%d/%m/%Y")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        from_date_epoch = int(from_date_obj.timestamp())
        to_date_epoch = int(to_date_obj.timestamp())
        filters["booked_at__range"] = [from_date_epoch, to_date_epoch]

    organization_id = kwargs.get("organization_id")
    if organization_id:
        filters["user__organization_id"] = organization_id
    if sales_agent_id:
        filters["user__organization__sales_agent_id"] = sales_agent_id

    bookings = Booking.objects.filter(**filters)
    # total -booking
    total_bookings = bookings.count()

    # total-confirmed
    bookings_confirmed = bookings.annotate(
        total_itineraries=Count("flightbookingitinerarydetails"),
        confirmed_itineraries=Count(
            "flightbookingitinerarydetails",
            filter=Q(flightbookingitinerarydetails__status="Confirmed"),
        ),
    )
    total_booking_confirmed = bookings_confirmed.filter(
        total_itineraries__gt=0,  # Ensure there are itineraries
        total_itineraries=F("confirmed_itineraries"),
    )
    total_booking_confirmed_count = total_booking_confirmed.count()
    #------end----------

    #total-hold-released
    bookings_hold_released = bookings.annotate(
        total_itineraries=Count("flightbookingitinerarydetails"),
        hold_released_itineraries=Count(
            "flightbookingitinerarydetails",
            filter=Q(flightbookingitinerarydetails__status="Hold-Released"),
        ),
    )
    total_booking_hold_released= bookings_hold_released.filter(
        total_itineraries__gt=0,  # Ensure there are itineraries
        total_itineraries=F("hold_released_itineraries"),
    )
    total_booking_hold_released_count = total_booking_hold_released.count()
    #-----------------------
    # total failed 

    bookings_failed = list(
        set(
            bookings.filter(
                flightbookingitinerarydetails__status__in=[
                    "Ticketing-Failed",
                    "Hold-Failed",
                    "Rejected"
                ]
            ).values_list("id", flat=True)
        )
    )
    print("bookings_failed-----ids",bookings_failed)
    #--------------------------------------
    # total - hold
    bookings_on_hold = list(
        set(
            bookings.filter(
                flightbookingitinerarydetails__status__in=[
                    "On-Hold"
                ]
            ).exclude(id__in=bookings_failed).values_list("id", flat=True)
        )
    )
    
    #-----------------------------------------------------
    # total - enquiry
    bookings_enquiry = bookings.annotate(
        total_itineraries=Count("flightbookingitinerarydetails"),
        enquiry_itineraries=Count(
            "flightbookingitinerarydetails",
            filter=Q(flightbookingitinerarydetails__status="Enquiry"),
        ),
    )

    total_booking_enquiry = bookings_enquiry.filter(
        total_itineraries__gt=0,  # Ensure there are itineraries
        total_itineraries=F("enquiry_itineraries"),
    )

    total_booking_enquiry_count = total_booking_enquiry.count()
    bookings_to_enquiry = list(
        set(
            bookings.filter(
                flightbookingitinerarydetails__status__in=[
                    "Cancel-Ticket-Failed",
                    "Ticket-Released",
                    "Release-Hold-Failed",
                    "Ticketing-Initiated",
                    "Release-Hold-Initiated",
                    "Cancel-Ticket-Initiated",
                    "Hold-Initiated",
                    "Hold-Unavailable"
                ]
            ).exclude(id__in=bookings_failed).values_list("id", flat=True)
        )
    )

    print()
    total_booking_enquiry_count += len(bookings_to_enquiry)
    
    
    

    results = {
        "total_bookings": total_bookings,
        "total_booking_confirmed_count": total_booking_confirmed_count,
        "total_booking_hold_released_count" : total_booking_hold_released_count,
        "total_booking_enquiry_count": total_booking_enquiry_count,
        "total_booking_hold_count": len(bookings_on_hold),
        "bookings_failed": len(bookings_failed),
    }
    return results


def flight_commission(**kwargs):

    organization_id = kwargs.get("organization_id")
    from_date = kwargs.get("from_date")
    to_date = kwargs.get("to_date")

    organization_obj = Organization.objects.filter(id=organization_id).first()
    # _____________________________start___________________________________________________
    easy_link_billing_obj = organization_obj.easy_link_billing_account
    result = {}
    if easy_link_billing_obj:
        for item in easy_link_billing_obj.data:
            result.update(item)
    base_url = result.get("url")
    branch_code = result.get("branch_code")
    portal_reference_code = result.get("portal_reference_code")
    account_code = organization_obj.easy_link_billing_code

    if base_url != None:
        full_url = f"{base_url}/getAcAnalysisRptXML?sBrCode={branch_code}&PortalRefCode={portal_reference_code}"

    # -----------------end---------------------------

    headers = {}
    payload = f"""<Filterdata><param AcType=\"CC\" AcCode=\"{account_code}\" Format=\"AAB\" FromDate=\"{from_date}\" ToDate=\"{to_date}\" TxnTypes=\"019\" MergeChild=\"Y\" /></Filterdata>"""
    response = requests.request("POST", full_url, headers=headers, data=payload)
    decoded_xml = html.unescape(response.text)
    root = ET.fromstring(decoded_xml)

    # Define the namespace if present in the XML
    namespace = "{http://schemas.microsoft.com/2003/10/Serialization/}"

    # Find the RESULT node
    result = root.find(f".//{namespace}RESULT")
    if result is not None and not result.attrib and not list(result):
        final_result = {"total_commission_amount": 0}
        return final_result
    else:
        pass
    # Step 2: Remove the `<string>` wrapper
    start = decoded_xml.find("<RESULT>")
    end = decoded_xml.find("</RESULT>") + len("</RESULT>")
    cleaned_xml = decoded_xml[start:end]
    # Step 3: Parse XML to a dictionary
    data = xmltodict.parse(cleaned_xml)
    _data = clean_data(data)
    print("data===",data)
    results = _data.get("RESULT", {}).get("txn", {})
    sm = 0
    if isinstance(results, dict) and results:
        
        results = [results]

    
    for ech_result in results:
        sm += float(ech_result.get("HCamt"))

    final_result = {"total_commission_amount": round(abs(sm), 2)}

    return final_result


def total_booking_chart(**kwargs):

    year = kwargs.get("year")
    month = kwargs.get("month")
    organization_id = kwargs.get("organization_id")
    sales_agent_id = kwargs.get('sales_agent_id')
    filters = {}

    yr, mth = int(year), int(month)
    num_days = calendar.monthrange(yr, mth)[1]
    date_list = [
        (datetime(yr, mth, day)).strftime("%Y-%m-%d") for day in range(1, num_days + 1)
    ]
    formatted_dates = [datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b-%Y") for date in date_list]
    if organization_id:
        filters["user__organization_id"] = organization_id
    if sales_agent_id:
        filters["user__organization__sales_agent_id"] = sales_agent_id

    final_list = []
    for date in date_list:
        date_timestart = datetime.strptime(date, "%Y-%m-%d")
        date_timestart_epoch = int(date_timestart.timestamp())
        date_timeend = (
            datetime.strptime(date, "%Y-%m-%d")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        date_timeend_epoch = int(date_timeend.timestamp())

        filters["booked_at__range"] = [date_timestart_epoch, date_timeend_epoch]
        bookings = Booking.objects.filter(**filters)
        # total -booking
        total_bookings = bookings.count()
        # total-confirmed
        bookings_confirmed = bookings.annotate(
            total_itineraries=Count("flightbookingitinerarydetails"),
            confirmed_itineraries=Count(
                "flightbookingitinerarydetails",
                filter=Q(flightbookingitinerarydetails__status="Confirmed"),
            ),
        )

        total_booking_confirmed_count = bookings_confirmed.filter(
            total_itineraries__gt=0,  # Ensure there are itineraries
            total_itineraries=F("confirmed_itineraries"),
        ).count()
        # total - enquiry
        bookings_enquiry = bookings.annotate(
            total_itineraries=Count("flightbookingitinerarydetails"),
            enquiry_itineraries=Count(
                "flightbookingitinerarydetails",
                filter=Q(flightbookingitinerarydetails__status="Enquiry"),
            ),
        )

        total_booking_enquiry_count = bookings_enquiry.filter(
            total_itineraries__gt=0,  # Ensure there are itineraries
            total_itineraries=F("enquiry_itineraries"),
        ).count()
        # total - hold
        bookings_hold = bookings.annotate(
            total_itineraries=Count("flightbookingitinerarydetails"),
            hold_itineraries=Count(
                "flightbookingitinerarydetails",
                filter=Q(flightbookingitinerarydetails__status="On-Hold"),
            ),
        )

        total_booking_hold_count = bookings_hold.filter(
            total_itineraries__gt=0,  # Ensure there are itineraries
            total_itineraries=F("hold_itineraries"),
        ).count()

        # total-failed
        bookings_failed = list(
            set(
                bookings.filter(
                    flightbookingitinerarydetails__status__in=[
                        "Ticketing-Failed",
                        "Hold-Failed",
                    ]
                ).values_list("id", flat=True)
            )
        )
        results = {
            # "total_bookings": total_bookings,
            "total_booking_confirmed_count": total_booking_confirmed_count,
            "total_booking_enquiry_count": total_booking_enquiry_count,
            "total_booking_hold_count": total_booking_hold_count,
            "bookings_failed": len(bookings_failed),
            # "date": date,
        }
        final_list.append(results)
    # data = totalbooking_chart(date_list, final_list)
    data = {
        "date_list" : formatted_dates,
        "data_list" : final_list
    }
    return data


def staff_confirmed_booking_pie_chart(**kwargs):

    filters = {}
    from_date = kwargs.get("from_date")
    to_date = kwargs.get("to_date")
    if from_date and to_date:
        from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
        to_date_obj = (
            datetime.strptime(to_date, "%d/%m/%Y")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        from_date_epoch = int(from_date_obj.timestamp())
        to_date_epoch = int(to_date_obj.timestamp())
        filters["booked_at__range"] = [from_date_epoch, to_date_epoch]

    organization_id = kwargs.get("organization_id")
    if organization_id:
        filters["user__organization_id"] = organization_id

    bookings = Booking.objects.filter(**filters)
    if not bookings:
        message = {}
        return message
    
    bookings_confirmed = bookings.annotate(
        total_itineraries=Count("flightbookingitinerarydetails"),
        confirmed_itineraries=Count(
            "flightbookingitinerarydetails",
            filter=Q(flightbookingitinerarydetails__status="Confirmed"),
        ),
    )

    sales_agent_list = bookings_confirmed.filter(
        total_itineraries__gt=0,  # Ensure there are itineraries
        total_itineraries=F("confirmed_itineraries"),
    ).values(sales_agent=F("user__first_name"), user_uuid=F("user"))
    
    df = pd.DataFrame(sales_agent_list)
    
    sales_agent_counts = (
        df.groupby("sales_agent")["user_uuid"].count().reset_index(name="value")
    )

    # Rename `sales_agent` to `name`
    sales_agent_counts.rename(columns={"sales_agent": "name"}, inplace=True)

    # Convert to a list of dictionaries if needed
    result = sales_agent_counts.to_dict(orient="records")
    result = sorted(result, key=lambda x: x["value"], reverse=True)
    if len(result) > 9:
        top_agents = result[:9]
        others_count = sum(item["value"] for item in result[9:])
        top_agents.append({"name": "Others", "value": others_count})
        result = top_agents

    
    # final_result = staff_booking_piechart(result)
    return result

def airline_confirmed_booking_pie_chart(**kwargs):

    filters = {}
    from_date = kwargs.get("from_date")
    to_date = kwargs.get("to_date")
    year = kwargs.get("year")
    month = kwargs.get("month")
    sales_agent_id = kwargs.get('sales_agent_id')
    if from_date and to_date:
        from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
        to_date_obj = (
            datetime.strptime(to_date, "%d/%m/%Y")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        from_date_epoch = int(from_date_obj.timestamp())
        to_date_epoch = int(to_date_obj.timestamp())
        filters["booked_at__range"] = [from_date_epoch, to_date_epoch]
    if year and month :
        yr, mth = int(year), int(month)
        num_days = calendar.monthrange(yr, mth)[1]
        from_date = f"01/{mth:02d}/{yr}"
        to_date = f"{num_days}/{mth:02d}/{yr}"
        from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
        to_date_obj = (
            datetime.strptime(to_date, "%d/%m/%Y")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        from_date_epoch = int(from_date_obj.timestamp())
        to_date_epoch = int(to_date_obj.timestamp())
        filters["booked_at__range"] = [from_date_epoch, to_date_epoch]


    organization_id = kwargs.get("organization_id")
    if organization_id:
        filters["user__organization_id"] = organization_id

    if sales_agent_id:
        filters["user__organization__sales_agent_id"] = sales_agent_id
    bookings = Booking.objects.filter(**filters)
    if not bookings:
        message = {}
        return message

    confirmed_bookings = bookings.annotate(
        total_itineraries=Count("flightbookingitinerarydetails"),
        confirmed_itineraries=Count(
            "flightbookingitinerarydetails",
            filter=Q(flightbookingitinerarydetails__status="Confirmed"),
        ),
    )
    # airline_code_and_name = 
    airline_data = confirmed_bookings.filter(
    total_itineraries__gt=0,  # Ensure there are itineraries
    total_itineraries=F("confirmed_itineraries"),
    payment_details__new_published_fare__gt=0
        ).annotate(
            first_airline_code=Subquery(
                FlightBookingItineraryDetails.objects.filter(
                    booking=OuterRef('pk')
                ).order_by('created_at').values('flightbookingjourneydetails__flightbookingsegmentdetails__airline_code')[:1]
            ),first_airline_name=Subquery(
        FlightBookingItineraryDetails.objects.filter(
            booking=OuterRef('pk')
        ).order_by('created_at').values('flightbookingjourneydetails__flightbookingsegmentdetails__airline_name')[:1]
    )
        ).values('first_airline_code','payment_details__new_published_fare','first_airline_name')
    
    df = pd.DataFrame(airline_data)
    
    result = []
    if not df.empty:
        # Fill NaN values in the `payment_details__new_published_fare` column with 0
        df['payment_details__new_published_fare'] = df['payment_details__new_published_fare'].fillna(0)

        # Group by `first_airline_name` and sum the `payment_details__new_published_fare`
        grouped_df = df.groupby('first_airline_code', as_index=False).agg({'payment_details__new_published_fare': 'sum','first_airline_name': 'first'})
        grouped_df['payment_details__new_published_fare'] = grouped_df['payment_details__new_published_fare'].round()
        # Sort the grouped DataFrame by the `payment_details__new_published_fare` in descending order
        grouped_df = grouped_df.sort_values(by="payment_details__new_published_fare", ascending=False)

        # Split the data into two parts: Top 9 and the rest
        top_9 = grouped_df.iloc[:9]
        others = grouped_df.iloc[9:]

        # Calculate the sum of amounts in the "Others" group
        others_sum = others["payment_details__new_published_fare"].sum()

        # Append the "Others" row to the `top_9` DataFrame if there are more than 9 entries
        if not others.empty:
            others_row = {
                "first_airline_code": "Others",
                "first_airline_name": "Others",
                "payment_details__new_published_fare": others_sum,
            }
            top_9 = pd.concat([top_9, pd.DataFrame([others_row])], ignore_index=True)

        # Convert the DataFrame to the desired JSON format
        result = top_9.rename(
            columns={
                "first_airline_code": "code",
                "first_airline_name": "name",
                "payment_details__new_published_fare": "value",
            }
        ).to_dict(orient="records")
    
    return result

def admin_or_staff_line_chart(**kwargs):

    year = kwargs.get("year")
    month = kwargs.get("month")
    agent_id = kwargs.get("agent_id")
    sales_agent_id = kwargs.get('sales_agent_id')
    filters = {}
    yr, mth = int(year), int(month)
    num_days = calendar.monthrange(yr, mth)[1]
    date_list = [
        (datetime(yr, mth, day)).strftime("%Y-%m-%d") for day in range(1, num_days + 1)
    ]
    formatted_dates = [datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b-%Y") for date in date_list]
    if agent_id:
        filters["user_id"] = agent_id
    if sales_agent_id:
        filters['user__organization__sales_agent_id'] = sales_agent_id

    data_list = []
    for date in date_list:
        date_timestart = datetime.strptime(date, "%Y-%m-%d")
        date_timestart_epoch = int(date_timestart.timestamp())
        date_timeend = (
            datetime.strptime(date, "%Y-%m-%d")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        date_timeend_epoch = int(date_timeend.timestamp())

        filters["booked_at__range"] = [date_timestart_epoch, date_timeend_epoch]
        bookings = Booking.objects.filter(**filters)
        # total -booking
        total_bookings = bookings.count()
        # total-confirmed
        bookings_confirmed = bookings.annotate(
            total_itineraries=Count("flightbookingitinerarydetails"),
            confirmed_itineraries=Count(
                "flightbookingitinerarydetails",
                filter=Q(flightbookingitinerarydetails__status="Confirmed"),
            ),
        )

        amount = (
            bookings_confirmed.filter(
                total_itineraries__gt=0,  # Ensure there are itineraries
                total_itineraries=F("confirmed_itineraries"),
            ).aggregate(total_amount=Sum("payment_details__new_published_fare"))["total_amount"]
            or 0
        )
        amount = round(amount)
        data_list.append(amount)
    # data = staff_vs_amount_line_chart(date_list, data_list)
    data = {
        "date_list" : formatted_dates,
        "data_list" : data_list
    } 
    return data



def organization_count(**kwargs):
    from_date = kwargs.get('from_date')
    to_date = kwargs.get('to_date')
    sales_agent_id = kwargs.get('sales_agent_id')
    filters = {}
    from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
    to_date_obj = (
        datetime.strptime(to_date, "%d/%m/%Y")
        + timedelta(days=1)
        - timedelta(seconds=1)
    )
    from_date_epoch = int(from_date_obj.timestamp())
    to_date_epoch = int(to_date_obj.timestamp())
    if sales_agent_id:
        filters['sales_agent_id'] = sales_agent_id
    filters["created_at__range"] = [from_date_epoch, to_date_epoch]
    organization = Organization.objects.filter(**filters)
    organization_count = organization.count()
    active_organization = organization.filter(status="active").count()
    inactive_organiztaion = organization.filter(status="inactive").count()
    pending_organiztaion = organization.filter(status="pending").count()
    result = {
        "organization_count" : organization_count,
        "active_organization" : active_organization,
        "inactive_organiztaion" : inactive_organiztaion,
        # "pending_organiztaion" : pending_organiztaion
    }
    return result


def registration_count(**kwargs):
    from_date = kwargs.get('from_date')
    to_date = kwargs.get('to_date')
    sales_agent_id  = kwargs.get('sales_agent_id')
    filters = {}
    from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
    to_date_obj = (
        datetime.strptime(to_date, "%d/%m/%Y")
        + timedelta(days=1)
        - timedelta(seconds=1)
    )
    from_date_epoch = int(from_date_obj.timestamp())
    to_date_epoch = int(to_date_obj.timestamp())
    filters["created_at__range"] = [from_date_epoch, to_date_epoch]
    if sales_agent_id:
        filters['sales_agent_id'] = sales_agent_id

    distribution_agency = Organization.objects.filter(organization_type__name__in=['distributor','agency'],**filters)
    distribution_agency_tot = distribution_agency.count()
    active_distribution_agency = distribution_agency.filter(status="active",).count()

    distribution = Organization.objects.filter(organization_type__name='distributor',**filters)
    distribution_tot = distribution.count()
    active_distribution = distribution.filter(status="active",).count()

    agency = Organization.objects.filter(organization_type__name='agency',**filters)
    agency_tot = agency.count()
    active_agency = agency.filter(status="active").count()
    
    result = {
        "active_agency_and_dist" : active_distribution_agency,
        "total_agency_and_dist" : distribution_agency_tot,
        "active_dist" : active_distribution,
        "total_dist" : distribution_tot ,
        "active_agency" : active_agency,
        "total_agency" : agency_tot ,
        
    }
    return result


def vendor_booking_pie_chart(**kwargs):

    year = kwargs.get("year")
    month = kwargs.get("month")
    yr, mth = int(year), int(month)
    num_days = calendar.monthrange(yr, mth)[1]
    from_date = f"01/{mth:02d}/{yr}"
    to_date = f"{num_days}/{mth:02d}/{yr}"
    filters = {}
    if from_date and to_date:
        from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
        to_date_obj = (
            datetime.strptime(to_date, "%d/%m/%Y")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        from_date_epoch = int(from_date_obj.timestamp())
        to_date_epoch = int(to_date_obj.timestamp())
        filters["booked_at__range"] = [from_date_epoch, to_date_epoch]
    
    organization_id = kwargs.get("organization_id")
    if organization_id:
        filters["user__organization_id"] = organization_id
    bookings = Booking.objects.filter(**filters)
    if not bookings:
        message = {}
        return message

    confirmed_bookings = bookings.annotate(
        total_itineraries=Count("flightbookingitinerarydetails"),
        confirmed_itineraries=Count(
            "flightbookingitinerarydetails",
            filter=Q(flightbookingitinerarydetails__status="Confirmed"),
        ),
    )

    vendor_data = confirmed_bookings.filter(
    total_itineraries__gt=0,  # Ensure there are itineraries
    total_itineraries=F("confirmed_itineraries"),
    payment_details__new_published_fare__gt=0
        ).annotate(
            vendor_name=Subquery(
                FlightBookingItineraryDetails.objects.filter(
                    booking=OuterRef('pk')
                ).order_by('created_at').values('vendor__name')[:1]
            )
        ).values('vendor_name','payment_details__new_published_fare')
    
    df = pd.DataFrame(vendor_data)
    print("df---df",df)

    result = []
    if not df.empty:
        df["payment_details__new_published_fare"] = pd.to_numeric(df["payment_details__new_published_fare"], errors="coerce").fillna(0)

        # Group by vendor name and calculate sum and count
        grouped = df.groupby("vendor_name").agg(
            total_amount=("payment_details__new_published_fare", "sum"),
            count=("payment_details__new_published_fare", "size")
        ).reset_index()
        grouped["total_amount"] = grouped["total_amount"].round()
        # Sort by total_amount in descending order
        sorted_grouped = grouped.sort_values(by="total_amount", ascending=False)
        top_9 = sorted_grouped.iloc[:9]
        others = sorted_grouped.iloc[9:]
        others_sum = others["total_amount"].sum()
        others_count = others["count"].sum()
        if not others.empty:
            others_row = {
                "vendor_name": "Others",
                "total_amount": others_sum,
                "count": others_count
            }
            top_9 = pd.concat([top_9, pd.DataFrame([others_row])], ignore_index=True)
        result = top_9.rename(
            columns={
                "vendor_name": "name",
                "total_amount": "value",
                "count" : "count"
            }
        ).to_dict(orient="records")
            
    
    return result

# def vendor_airline_barchart(kwargs):

#     year = kwargs.get("year")
#     month = kwargs.get("month")
#     vendor_id = kwargs.get('vendor_id')
#     yr, mth = int(year), int(month)
#     num_days = calendar.monthrange(yr, mth)[1]
#     filters = {}
#     date_list = [
#         (datetime(yr, mth, day)).strftime("%Y-%m-%d") for day in range(1, num_days + 1)
#     ]
#     formatted_dates = [datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b-%Y") for date in date_list]
#     if vendor_id:
#         filters["flightbookingitinerarydetails__vendor_id"] = vendor_id

#     list_of_airlines = list(Booking.objects.filter(**filters,flightbookingjourneydetails__flightbookingsegmentdetails__airline_code__isnull=False).annotate(airline_code=F('flightbookingjourneydetails__flightbookingsegmentdetails__airline_code'),airline_name=F('flightbookingjourneydetails__flightbookingsegmentdetails__airline_name')).values('airline_code','airline_name'))
#     if not list_of_airlines:
#         return []
#     df_list_of_airline = pd.DataFrame(list_of_airlines)
#     df_grouped = df_list_of_airline.groupby('airline_code',as_index=False).agg({
#         'airline_name': 'first'  # Retain the first airline_name for each code
#     })
#     df_grouped = df_grouped.drop(columns=['airline_code'])
#     list_of_airlines = df_grouped['airline_name'].tolist()
#     data_list = []
#     for date in date_list:
#         airline_dict = {airline: 0 for airline in list_of_airlines}
#         # airline_dict['date'] = date
#         date_timestart = datetime.strptime(date, "%Y-%m-%d")
#         date_timestart_epoch = int(date_timestart.timestamp())
#         date_timeend = (
#             datetime.strptime(date, "%Y-%m-%d")
#             + timedelta(days=1)
#             - timedelta(seconds=1)
#         )
#         date_timeend_epoch = int(date_timeend.timestamp())

#         filters["booked_at__range"] = [date_timestart_epoch, date_timeend_epoch]
#         bookings = Booking.objects.filter(**filters)
#         # if not bookings:
#         #     message = {}
#         #     return message

#         confirmed_bookings = bookings.annotate(
#             total_itineraries=Count("flightbookingitinerarydetails"),
#             confirmed_itineraries=Count(
#                 "flightbookingitinerarydetails",
#                 filter=Q(flightbookingitinerarydetails__status="Confirmed"),
#             ),
#         )
#         vendor_data = list(confirmed_bookings.filter(
#             total_itineraries__gt=0,  # Ensure there are itineraries
#             total_itineraries=F("confirmed_itineraries"),
#         ).annotate(
#             first_airline_name=Subquery(
#                 FlightBookingItineraryDetails.objects.filter(
#                     booking=OuterRef('pk')
#                 ).order_by('created_at').values('flightbookingjourneydetails__flightbookingsegmentdetails__airline_name')[:1]
#             )
#         ).values('first_airline_name','payment_details__new_published_fare').annotate(
#                 total_payment=Sum('payment_details__new_published_fare')))
#         for airline in vendor_data:
#             airline_name = airline.get('first_airline_name')
#             total_payment = airline.get('total_payment', 0) or 0
            
#             if airline_name in list_of_airlines and airline_name is not None:
#                 airline_dict[airline_name] = airline_dict.get(airline_name, 0) + total_payment
            
#         # Append the result for this date
#         data_list.append(airline_dict.copy())
#         final_result = {
#             "date_list" : formatted_dates,
#             "data_list" :data_list
#         }
#     # print("dt------------------------------",data_list)
#     return final_result



def vendor_airline_barchart(**kwargs):

    year = kwargs.get("year")
    month = kwargs.get("month")
    vendor_id = kwargs.get('vendor_id')
    yr, mth = int(year), int(month)
    num_days = calendar.monthrange(yr, mth)[1]
    from_date = f"01/{mth:02d}/{yr}"
    to_date = f"{num_days}/{mth:02d}/{yr}"
 
    filters = {}
    if from_date and to_date:
        from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
        to_date_obj = (
            datetime.strptime(to_date, "%d/%m/%Y")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        from_date_epoch = int(from_date_obj.timestamp())
        to_date_epoch = int(to_date_obj.timestamp())
        filters["booked_at__range"] = [from_date_epoch, to_date_epoch]
    
    date_list = [
        (datetime(yr, mth, day)).strftime("%Y-%m-%d") for day in range(1, num_days + 1)
    ]
    formatted_dates = [datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b-%Y") for date in date_list]
    if vendor_id:
        filters["flightbookingitinerarydetails__vendor_id"] = vendor_id

    bookings = Booking.objects.filter(**filters)
    
    print("BOOKING----",bookings.count())
    # Filter confirmed bookings
    confirmed_bookings = bookings.annotate(
    total_itineraries=Count("flightbookingitinerarydetails"),
    confirmed_itineraries=Count(
        "flightbookingitinerarydetails",
        filter=Q(flightbookingitinerarydetails__status="Confirmed"),
    ),
    )
    airline_data = confirmed_bookings.filter(
        total_itineraries__gt=0,  # Ensure there are itineraries
        total_itineraries=F("confirmed_itineraries"),
    ).annotate(
        airline_code=Subquery(
            FlightBookingItineraryDetails.objects.filter(
                booking=OuterRef('pk')
            ).order_by('created_at').values('flightbookingjourneydetails__flightbookingsegmentdetails__airline_code')[:1]
        ),
        airline_name=Subquery(
            FlightBookingItineraryDetails.objects.filter(
                booking=OuterRef('pk')
            ).order_by('created_at').values('flightbookingjourneydetails__flightbookingsegmentdetails__airline_name')[:1]
        ),
    ).annotate(
        total_payment=Sum('payment_details__new_published_fare')).values('airline_code', 'airline_name','total_payment')
    

   
    airline_totals = {}
    airline_names = {}
    for data in airline_data:
        airline_code = data['airline_code']
        airline_name = data['airline_name']
        if airline_code:
            airline_totals[airline_code] = airline_totals.get(airline_code, 0) + (data['total_payment'] or 0)
            airline_names[airline_code] = airline_name.strip().lower().capitalize()


    # Sort airlines by total payment in descending order
    sorted_airlines = sorted(airline_totals.items(), key=lambda x: x[1], reverse=True)
    # Limit to top 9 airlines, grouping the rest into "Others"
    top_airlines = sorted_airlines[:9]
    others = sorted_airlines[9:]

    list_of_airlines = [airline_names[code] for code, _ in top_airlines]

    if not list_of_airlines:
        return []
    if others:
        list_of_airlines.append(others)

    data_list = []
    for date in date_list:
        airline_dict = {airline: 0 for airline in list_of_airlines}
        date_timestart = datetime.strptime(date, "%Y-%m-%d")
        date_timestart_epoch = int(date_timestart.timestamp())
        date_timeend = (
            datetime.strptime(date, "%Y-%m-%d")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        date_timeend_epoch = int(date_timeend.timestamp())

        filters["booked_at__range"] = [date_timestart_epoch, date_timeend_epoch]
        

        bookings = Booking.objects.filter(**filters)
       
        confirmed_bookings = bookings.annotate(
            total_itineraries=Count("flightbookingitinerarydetails"),
            confirmed_itineraries=Count(
                "flightbookingitinerarydetails",
                filter=Q(flightbookingitinerarydetails__status="Confirmed"),
            ),
        )
        airline_data = confirmed_bookings.filter(
            total_itineraries__gt=0,
            total_itineraries=F("confirmed_itineraries"),
        ).annotate(
            first_airline_code=Subquery(
                FlightBookingItineraryDetails.objects.filter(
                    booking=OuterRef('pk')
                ).order_by('created_at').values('flightbookingjourneydetails__flightbookingsegmentdetails__airline_code')[:1]
            ),
            first_airline_name=Subquery(
                FlightBookingItineraryDetails.objects.filter(
                    booking=OuterRef('pk')
                ).order_by('created_at').values('flightbookingjourneydetails__flightbookingsegmentdetails__airline_name')[:1]
            )
        ).annotate(
            total_payment=Sum('payment_details__new_published_fare')
        ).values('first_airline_name', 'total_payment')

        

        for airline in airline_data:
            airline_name = airline.get('first_airline_name').strip().lower().capitalize() if airline.get('first_airline_name') else ''
            total_payment = airline.get('total_payment') or 0
            
            if airline_name in list_of_airlines:
                airline_dict[airline_name] += round(total_payment)
            

        data_list.append(airline_dict)

        final_result = {
        "date_list" : formatted_dates,
        "data_list" :data_list
    }
    
            
                    
        
        
            

    return final_result
    


def sales_performace_table(**kwargs):
    
    year = int(kwargs.get("year"))
    month = int(kwargs.get("month"))
    
    current_month_booking_filters = {}
    previous_month_booking_filters = {}
    organization_filters = {}
    if year and month:
        def date_time_epoch_conv(yr,mth) :
            from_date = f"01/{mth:02d}/{yr}"
            num_days = calendar.monthrange(yr, mth)[1]
            to_date = f"{num_days}/{mth:02d}/{yr}"
            from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
            to_date_obj = (
                datetime.strptime(to_date, "%d/%m/%Y")
                + timedelta(days=1)
                - timedelta(seconds=1)
            )
            
            data = {
                "from_date_epoch" : int(from_date_obj.timestamp()),
                "to_date_epoch" : int(to_date_obj.timestamp())
            }
            return data
        p_mth = 12 if month == 1 else month - 1
        p_yr = year-1 if month == 1 else year 
        current_month_booking_filters["booked_at__range"] = [date_time_epoch_conv(year, month).get('from_date_epoch'), date_time_epoch_conv(year, month).get('to_date_epoch')]
        organization_filters["created_at__range"] = [date_time_epoch_conv(year, month).get('from_date_epoch'), date_time_epoch_conv(year, month).get('to_date_epoch')]
        previous_month_booking_filters["booked_at__range"] = [date_time_epoch_conv(p_yr, p_mth).get('from_date_epoch'), date_time_epoch_conv(p_yr, p_mth).get('to_date_epoch')]

    sales_agents = UserDetails.objects.filter(role__name="sales")
    result  = []
    for ech_agent in sales_agents:
        organization = Organization.objects.filter(sales_agent=ech_agent,**organization_filters)
        bookings_current = Booking.objects.filter(user__organization__sales_agent=ech_agent,**current_month_booking_filters)
        bookings_previous = Booking.objects.filter(user__organization__sales_agent=ech_agent,**previous_month_booking_filters)
        def booking(bookings):
            bookings_confirmed= bookings.annotate(
                                    total_itineraries=Count("flightbookingitinerarydetails"),
                                    confirmed_itineraries=Count("flightbookingitinerarydetails",
                                    filter=Q(flightbookingitinerarydetails__status="Confirmed"),
                                    ),
                                ).filter(total_itineraries__gt=0, 
                                        total_itineraries=F("confirmed_itineraries"),
                                        )
            total_amount = bookings_confirmed.values('payment_details__new_published_fare').aggregate(total_amount=Sum('payment_details__new_published_fare')).get('total_amount') or 0
            
            data = {
                "count" : bookings_confirmed.count(),
                "sales_amount" : round(total_amount)
                
            }
            return data
        def act_inact_bookings(bookings):
            organization = Organization.objects.filter(sales_agent=ech_agent)
            bookings_confirmed= bookings.annotate(
                                    total_itineraries=Count("flightbookingitinerarydetails"),
                                    confirmed_itineraries=Count("flightbookingitinerarydetails",
                                    filter=Q(flightbookingitinerarydetails__status="Confirmed"),
                                    ),
                                ).filter(total_itineraries__gt=0, 
                                        total_itineraries=F("confirmed_itineraries"),
                                        )
            
            # active_organization_count = len(list(set(bookings_confirmed.values_list('user__organization__id'))))
            active_organization_count = bookings_confirmed.values_list('user__organization__id').distinct().count()
            total_organization_count = organization.count()
            inactive_organization_count = total_organization_count - active_organization_count
            data = {
                "booking_count" : bookings_confirmed.count(),
                "organization_count" : total_organization_count,
                "active_organization_count":active_organization_count,
                "inactive_organization_count": inactive_organization_count,
                "organization_lists":bookings_confirmed.values('user__organization__organization_name').distinct(),
                
                
            }
            return data

        data = {
            "name" : ech_agent.first_name,
            "sales_id" : ech_agent.id,
            "registration_count" : organization.count(),
            "active_inactive" : [act_inact_bookings(bookings_current).get('active_organization_count'),act_inact_bookings(bookings_current).get('inactive_organization_count')],
            "sales_amount_previous_current" : [ booking(bookings_previous).get('sales_amount') ,booking(bookings_current).get('sales_amount')],
            "booking_previous_current" : [ booking(bookings_previous).get('count') ,booking(bookings_current).get('count')]
        }
        result.append(data)

    return result


def organization_booking_count(**kwargs):
    sales_agent_id = kwargs.get('sales_id')
    year = int(kwargs.get("year"))
    month = int(kwargs.get("month"))
    current_month_booking_filters = {}
    if year and month:
        def date_time_epoch_conv(yr,mth) :
            from_date = f"01/{mth:02d}/{yr}"
            num_days = calendar.monthrange(yr, mth)[1]
            to_date = f"{num_days}/{mth:02d}/{yr}"
            from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
            to_date_obj = (
                datetime.strptime(to_date, "%d/%m/%Y")
                + timedelta(days=1)
                - timedelta(seconds=1)
            )
            
            data = {
                "from_date_epoch" : int(from_date_obj.timestamp()),
                "to_date_epoch" : int(to_date_obj.timestamp())
            }
            return data
    current_month_booking_filters["booked_at__range"] = [date_time_epoch_conv(year, month).get('from_date_epoch'), date_time_epoch_conv(year, month).get('to_date_epoch')]
    organization = Organization.objects.filter(sales_agent_id=sales_agent_id)
    
    def confirmed_booking(bookings):
        bookings_confirmed= bookings.annotate(
                                total_itineraries=Count("flightbookingitinerarydetails"),
                                confirmed_itineraries=Count("flightbookingitinerarydetails",
                                filter=Q(flightbookingitinerarydetails__status="Confirmed"),
                                ),
                            ).filter(total_itineraries__gt=0, 
                                    total_itineraries=F("confirmed_itineraries"),
                                    )
        return bookings_confirmed
   
    final_data = {
        "active_org":[],
        "inactive_org":[]
    }
    for ech_org in organization :
        print("ech_org----",ech_org)
        bookings_current = Booking.objects.filter(user__organization__sales_agent_id=sales_agent_id,**current_month_booking_filters,user__organization=ech_org)
        confirmed_bookings = confirmed_booking(bookings_current)
        pax_count = confirmed_bookings.values('flightbookingpaxdetails').count()
        print("pax_count-----",pax_count)
        total_booking_count  = confirmed_bookings.count()
        _data = {
        "organization_name": ech_org.organization_name,
        "organization_account_code": ech_org.easy_link_account_code,
        "online_count": sum(1 for ech in confirmed_bookings.values_list("source", flat=True) if ech == "Online"),
        "offline_count": sum(1 for ech in confirmed_bookings.values_list("source", flat=True) if ech == "Offline"),
        "pax_count":pax_count,

        }
        


        if total_booking_count != 0:
        # Append only if organization is not already present in `active_org`
            if not any(ech_dat["organization_name"] == _data["organization_name"] for ech_dat in final_data["active_org"]):
                final_data["active_org"].append(_data)
        else:
            # Append only if organization is not already present in `inactive_org`
            if not any(ech_dat["organization_name"] == _data["organization_name"] for ech_dat in final_data["inactive_org"]):
                final_data["inactive_org"].append(_data)

    return final_data

def total_failed_to_rejected_booking(**kwargs):

    filters = {}
    from_date = kwargs.get("from_date")
    to_date = kwargs.get("to_date")
    ops_agent_id = kwargs.get("ops_agent_id")
    if from_date and to_date:
        from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
        to_date_obj = (
            datetime.strptime(to_date, "%d/%m/%Y")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        from_date_epoch = int(from_date_obj.timestamp())
        to_date_epoch = int(to_date_obj.timestamp())
        filters["booked_at__range"] = [from_date_epoch, to_date_epoch]

    organization_id = kwargs.get("organization_id")
    if organization_id:
        filters["user__organization_id"] = organization_id

    if ops_agent_id:
        filters["modified_by__id"] = ops_agent_id

    filters['status'] = "Failed-Rejected"

    bookings = Booking.objects.filter(**filters)
    total_failed_rejected = bookings
    total_pax_count = bookings.aggregate(count=Count("flightbookingpaxdetails"))["count"]
    
    results = {
        "total_failed_rejected": total_failed_rejected.count(),
        "total_pax_count": total_pax_count,
       
    }
    return results



def total_failed_to_confirmed_booking(**kwargs):

    filters = {}
    from_date = kwargs.get("from_date")
    to_date = kwargs.get("to_date")
    ops_agent_id = kwargs.get("ops_agent_id")
    if from_date and to_date:
        from_date_obj = datetime.strptime(from_date, "%d/%m/%Y")
        to_date_obj = (
            datetime.strptime(to_date, "%d/%m/%Y")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        from_date_epoch = int(from_date_obj.timestamp())
        to_date_epoch = int(to_date_obj.timestamp())
        filters["booked_at__range"] = [from_date_epoch, to_date_epoch]

    organization_id = kwargs.get("organization_id")
    if organization_id:
        filters["user__organization_id"] = organization_id

    

    if ops_agent_id:
        filters["modified_by__id"] = ops_agent_id

    filters['status'] = "Failed-Confirmed"

    bookings = Booking.objects.filter(**filters)
    total_failed_confirm = bookings
    total_pax_count = bookings.aggregate(count=Count("flightbookingpaxdetails"))["count"]
    
    results = {
        "total_failed_confirm": total_failed_confirm.count(),
        "total_pax_count": total_pax_count
    }
    return results


def total_failed_to_rejected_chart(**kwargs):

    year = kwargs.get("year")
    month = kwargs.get("month")
    organization_id = kwargs.get("organization_id")
    ops_agent_id = kwargs.get('ops_agent_id')
    filters = {}

    yr, mth = int(year), int(month)
    num_days = calendar.monthrange(yr, mth)[1]
    date_list = [
        (datetime(yr, mth, day)).strftime("%Y-%m-%d") for day in range(1, num_days + 1)
    ]
    formatted_dates = [datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b-%Y") for date in date_list]
    if organization_id:
        filters["user__organization_id"] = organization_id
    if ops_agent_id:
        filters["modified_by__id"] = ops_agent_id
    filters['status'] = "Failed-Rejected"
    final_list = []
    for date in date_list:
        date_timestart = datetime.strptime(date, "%Y-%m-%d")
        date_timestart_epoch = int(date_timestart.timestamp())
        date_timeend = (
            datetime.strptime(date, "%Y-%m-%d")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        date_timeend_epoch = int(date_timeend.timestamp())

        filters["booked_at__range"] = [date_timestart_epoch, date_timeend_epoch]
        failed_rejected_bookings = Booking.objects.filter(**filters)
        
        results = {
            # "total_bookings": total_bookings,
            "failed_rejected_bookings_count": failed_rejected_bookings.count(),

        }
        final_list.append(results)
    # data = totalbooking_chart(date_list, final_list)
    data = {
        "date_list" : formatted_dates,
        "data_list" : final_list
    }
    return data


def total_failed_to_confirmed_chart(**kwargs):

    year = kwargs.get("year")
    month = kwargs.get("month")
    organization_id = kwargs.get("organization_id")
    ops_agent_id = kwargs.get('ops_agent_id')
    filters = {}

    yr, mth = int(year), int(month)
    num_days = calendar.monthrange(yr, mth)[1]
    date_list = [
        (datetime(yr, mth, day)).strftime("%Y-%m-%d") for day in range(1, num_days + 1)
    ]
    formatted_dates = [datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b-%Y") for date in date_list]
    if organization_id:
        filters["user__organization_id"] = organization_id
    if ops_agent_id:
        filters["modified_by__id"] = ops_agent_id
    filters['status'] = "Failed-Confirmed"
    final_list = []
    for date in date_list:
        date_timestart = datetime.strptime(date, "%Y-%m-%d")
        date_timestart_epoch = int(date_timestart.timestamp())
        date_timeend = (
            datetime.strptime(date, "%Y-%m-%d")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        date_timeend_epoch = int(date_timeend.timestamp())

        filters["booked_at__range"] = [date_timestart_epoch, date_timeend_epoch]
        failed_confirmed_bookings = Booking.objects.filter(**filters)
        
        results = {
            # "total_bookings": total_bookings,
            "failed_confirmed_bookings_count": failed_confirmed_bookings.count(),

        }
        final_list.append(results)
    # data = totalbooking_chart(date_list, final_list)
    data = {
        "date_list" : formatted_dates,
        "data_list" : final_list
    }
    return data


def confirmed_booking_chart(**kwargs):

    year = kwargs.get("year")
    month = kwargs.get("month")
    vendor_id = kwargs.get('vendor_id')
    filters = {}

    yr, mth = int(year), int(month)
    num_days = calendar.monthrange(yr, mth)[1]
    date_list = [
        (datetime(yr, mth, day)).strftime("%Y-%m-%d") for day in range(1, num_days + 1)
    ]
    formatted_dates = [datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b-%Y") for date in date_list]
    
    if vendor_id:
        filters["flightbookingitinerarydetails__vendor_id"] = vendor_id


    final_list = []
    for date in date_list:
        date_timestart = datetime.strptime(date, "%Y-%m-%d")
        date_timestart_epoch = int(date_timestart.timestamp())
        date_timeend = (
            datetime.strptime(date, "%Y-%m-%d")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        date_timeend_epoch = int(date_timeend.timestamp())

        filters["booked_at__range"] = [date_timestart_epoch, date_timeend_epoch]
        bookings = Booking.objects.filter(**filters)
        confirmed_bookings = bookings.annotate(
        total_itineraries=Count("flightbookingitinerarydetails"),
        confirmed_itineraries=Count(
            "flightbookingitinerarydetails",
            filter=Q(flightbookingitinerarydetails__status="Confirmed"),
        ),
    )
        results = {
            # "total_bookings": total_bookings,
            "total_booking_confirmed_count": confirmed_bookings.count(),

        }
        final_list.append(results)
    # data = totalbooking_chart(date_list, final_list)
    data = {
        "date_list" : formatted_dates,
        "data_list" : final_list
    }
    return data

def confirmed_line_chart(**kwargs):

    year = kwargs.get("year")
    month = kwargs.get("month")
    vendor_id = kwargs.get("vendor_id")
    
    filters = {}
    yr, mth = int(year), int(month)
    num_days = calendar.monthrange(yr, mth)[1]
    date_list = [
        (datetime(yr, mth, day)).strftime("%Y-%m-%d") for day in range(1, num_days + 1)
    ]
    formatted_dates = [datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b-%Y") for date in date_list]
    if vendor_id:
        filters["flightbookingitinerarydetails__vendor_id"] = vendor_id

    data_list = []
    for date in date_list:
        date_timestart = datetime.strptime(date, "%Y-%m-%d")
        date_timestart_epoch = int(date_timestart.timestamp())
        date_timeend = (
            datetime.strptime(date, "%Y-%m-%d")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        date_timeend_epoch = int(date_timeend.timestamp())

        filters["booked_at__range"] = [date_timestart_epoch, date_timeend_epoch]
        bookings = Booking.objects.filter(**filters)
        bookings_confirmed = bookings.annotate(
            total_itineraries=Count("flightbookingitinerarydetails"),
            confirmed_itineraries=Count(
                "flightbookingitinerarydetails",
                filter=Q(flightbookingitinerarydetails__status="Confirmed"),
            ),
        )

        amount = (
            bookings_confirmed.filter(
                total_itineraries__gt=0,  # Ensure there are itineraries
                total_itineraries=F("confirmed_itineraries"),
            ).aggregate(total_amount=Sum("payment_details__new_published_fare"))["total_amount"]
            or 0
        )
        amount = round(amount)
        data_list.append(amount)
    # data = staff_vs_amount_line_chart(date_list, data_list)
    data = {
        "date_list" : formatted_dates,
        "data_list" : data_list
    } 
    return data


def failed_and_rejected_booking_chart(**kwargs):

    year = kwargs.get("year")
    month = kwargs.get("month")
    vendor_id = kwargs.get('vendor_id')
    filters = {}

    yr, mth = int(year), int(month)
    num_days = calendar.monthrange(yr, mth)[1]
    date_list = [
        (datetime(yr, mth, day)).strftime("%Y-%m-%d") for day in range(1, num_days + 1)
    ]
    formatted_dates = [datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b-%Y") for date in date_list]
    
    if vendor_id:
        filters["flightbookingitinerarydetails__vendor_id"] = vendor_id


    final_list = []
    for date in date_list:
        date_timestart = datetime.strptime(date, "%Y-%m-%d")
        date_timestart_epoch = int(date_timestart.timestamp())
        date_timeend = (
            datetime.strptime(date, "%Y-%m-%d")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        date_timeend_epoch = int(date_timeend.timestamp())

        filters["booked_at__range"] = [date_timestart_epoch, date_timeend_epoch]

        bookings = Booking.objects.filter(**filters)
        # filters['status__in'] = ["Ticketing-Failed","Hold-Failed"]
        # bookings_failed = bookings.filter(**filters)
        # filters.pop('status__in')
        # filters['status'] = "Rejected"
        # print("filters----",filters)
        # bookings_rejeceted = bookings.filter(**filters)

        bookings_failed = list(
        set(
            bookings.filter(
                flightbookingitinerarydetails__status__in=[
                    "Ticketing-Failed",
                    "Hold-Failed",

                ]
            ).values_list("id", flat=True)
        )
        )

        bookings_rejeceted = list(
        set(
            bookings.filter(
                flightbookingitinerarydetails__status="Rejected"
            ).values_list("id", flat=True)
        )
        )
        results = {
            # "total_bookings": total_bookings,
            "total_booking_failed_count": len(bookings_failed),
            "total_booking_rejected_count": len(bookings_rejeceted),
            # "total_booking_failed_count": bookings_failed.count(),
            # "total_booking_rejected_count": bookings_rejeceted.count(),

        }
        final_list.append(results)
    # data = totalbooking_chart(date_list, final_list)
    data = {
        "date_list" : formatted_dates,
        "data_list" : final_list
    }
    return data

def failed_rejected_line_chart(**kwargs):

    year = kwargs.get("year")
    month = kwargs.get("month")
    vendor_id = kwargs.get("vendor_id")
    
    filters = {}
    yr, mth = int(year), int(month)
    num_days = calendar.monthrange(yr, mth)[1]
    date_list = [
        (datetime(yr, mth, day)).strftime("%Y-%m-%d") for day in range(1, num_days + 1)
    ]
    formatted_dates = [datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b-%Y") for date in date_list]
    if vendor_id:
        filters["flightbookingitinerarydetails__vendor_id"] = vendor_id

    data_list = []
    for date in date_list:
        date_timestart = datetime.strptime(date, "%Y-%m-%d")
        date_timestart_epoch = int(date_timestart.timestamp())
        date_timeend = (
            datetime.strptime(date, "%Y-%m-%d")
            + timedelta(days=1)
            - timedelta(seconds=1)
        )
        date_timeend_epoch = int(date_timeend.timestamp())

        filters["booked_at__range"] = [date_timestart_epoch, date_timeend_epoch]
        filters['flightbookingitinerarydetails__status__in'] = ["Ticketing-Failed","Hold-Failed","Rejected"]
        print("filters---",filters)
        amount = Booking.objects.filter(**filters).aggregate(total_amount=Sum("payment_details__new_published_fare"))["total_amount"] or 0
        amount = round(amount)
        data_list.append(amount)
    # data = staff_vs_amount_line_chart(date_list, data_list)
    data = {
        "date_list" : formatted_dates,
        "data_list" : data_list
    } 
    return data