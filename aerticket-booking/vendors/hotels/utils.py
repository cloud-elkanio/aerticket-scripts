# Function to add icon types
from django.utils import timezone
from common.models import DailyCounter
from django.db import transaction

def add_icon_types(amenities_list):
    ICON_MAPPING = {
        "wifi": "wifi",
        "wired internet":"wifi",
        "pool": "pool",
        "parking": "car",
        "gym": "dumbbell",
        "restaurant": "utensils",
        "bar": "cocktail",
        "air conditioning": "snowflake",
        "pet": "paw",
        "spa": "spa",
        "front desk": "clock"
    }
    result = []
    for amenity in amenities_list:
        icon = "default-icon"
        for key, value in ICON_MAPPING.items():
            if key.lower() in amenity.lower():
                icon = value
                break
        result.append({"amenity": amenity, "icon": icon})
    return result

def generate_hotel_booking_display_id():
    now = timezone.now()
    today = now.date()
    with transaction.atomic():
        counter, created = DailyCounter.objects.select_for_update().get_or_create(date=today,module="hotel")
        counter.count += 1
        counter.save()
        booking_number = counter.count
    formatted_booking_number = f"{booking_number:04d}"
    day_month = now.strftime("%d%m")  # DDMM format
    year_suffix = now.strftime("%y")  # Last two digits of the year
    return f"HOTEL{year_suffix}-{day_month}-{formatted_booking_number}"
