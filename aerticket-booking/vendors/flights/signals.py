# signals.py
from django.db.models.signals import pre_save
from django.dispatch import receiver
from common.models import FlightBookingItineraryDetails

@receiver(pre_save, sender=FlightBookingItineraryDetails)
def update_booking_on_itinerary_change(sender, instance, **kwargs):
    if instance.pk:
        changed_fields = instance.tracker.changed()
        if 'status' in changed_fields:
            if instance.status not in ["Failed-Rejected","Failed-Confirmed"]:
                instance.booking.status = instance.status
                instance.booking.modified_at = instance.modified_at
                instance.booking.save(update_fields=['status', 'modified_at'])
