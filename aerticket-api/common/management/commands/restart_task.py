import time
import threading
from django.core.management.base import BaseCommand
from django.test import RequestFactory  # To create a mock request
from giata.models import GiataErrorLog
from giata.views import FetchCountriesView  # Import your view correctly
from datetime import datetime
class Command(BaseCommand):
    help = "Restart FetchCountriesView task asynchronously"

    def handle(self, *args, **kwargs):
        def restart_task():
            time.sleep(2)
            loc_time = datetime.now()
            GiataErrorLog.objects.create(error_message="Restart FetchCountriesView task asynchronously", 
                                        timestamp= loc_time.strftime("%Y-%m-%d %H:%M:%S"),
                                        traceback = "",
                                        giata_id = "",
                                        base_url = "",
                                        variables = loc_time.strftime("%Y-%m-%d %H:%M:%S")
                                        )
            factory = RequestFactory()
            request = factory.post("/fetch-countries/")

            view_instance = FetchCountriesView.as_view()
            response = view_instance(request)

            if response.status_code == 200:
                print("Task restarted successfully!")
            else:
                print(f"Failed to restart task. Status: {response.status_code}")

        task_thread = threading.Thread(target=restart_task)
        task_thread.start()

        self.stdout.write(self.style.SUCCESS("Task restart initiated!"))





