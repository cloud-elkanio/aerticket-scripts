from django.apps import AppConfig


class FlightsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "vendors.flights"

    def ready(self):
        import vendors.flights.signals
