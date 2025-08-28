
import csv
import io
import requests
import threading
import uuid

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from vendors.insurance.models import (
    InsuranceAsegoCategory,
    InsuranceAsegoPlan,
    InsuranceAsegoRiderMaster,
    InsuranceAsegoPlanRider,
    InsuranceAsegoPremiumChart,
    InsuranceAsegoVisitingCountry,
)
from common.models import Country  # assuming your common Country model is here


class SyncData():
    def __init__(self, sync_info):
        self.sync_info = sync_info
        print("Syncdata")
    def sync_vendor_data(self):
        files = self.sync_info
        # For each expected CSV file type, call the corresponding sync method.
        if "visiting_countries" in files:
            self.sync_visiting_countries(files["visiting_countries"])
        if "category" in files:
            self.sync_category(files["category"])

        if "rider_master" in files:
            self.sync_rider_master(files["rider_master"])
        if "plan" in files:
            self.sync_plan(files["plan"])

        if "plan_riders" in files:
            self.sync_plan_riders(files["plan_riders"])
        if "premium_chart" in files:
            self.sync_premium_chart(files["premium_chart"])

    def fetch_csv_data(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            csv_file = io.StringIO(response.text)
            reader = csv.DictReader(csv_file)
            return list(reader)
        except Exception as e:
            print(f"Error fetching CSV from {url}: {e}")
            return []



    def sync_visiting_countries(self, url):
        rows = self.fetch_csv_data(url)
        for row in rows:
            country_code = row.get("Country Code", "").strip()
            description = row.get("Description", "").strip()
            country_reference = row.get("Country Reference", "").strip()

            try:
                country_instance = Country.objects.get(lookup__country_code=country_code)
            except Country.DoesNotExist:
                print(f" Country with lookup code {country_code} not found. Skipping row.")
                continue

            obj, created = InsuranceAsegoVisitingCountry.objects.get_or_create(
                country=country_instance,
                description= description,
                reference = country_reference
            )
            if not created:
                obj.description = description
                obj.save()
        print("sync_visiting_countries")


    def sync_category(self, url):
        rows = self.fetch_csv_data(url)
        for row in rows:
            try:
                cat_code = uuid.UUID(row.get("Category Code"))
            except Exception:
                print(f" Invalid Category Code: {row.get('Category Code')}")
                continue

            obj, created = InsuranceAsegoCategory.objects.get_or_create(
                category_code=cat_code,
                defaults={"description": row.get("Description", "").strip()}
            )
            if not created:
                obj.description = row.get("Description", "").strip()
                obj.save()
        print("sync_category")


    def sync_rider_master(self, url):
        rows = self.fetch_csv_data(url)
        FALSE =False
        TRUE = True
        for row in rows:
            try:
                rider_code = uuid.UUID(row.get("Rider Code"))
            except Exception:
                print(f" Invalid Rider Code: {row.get('Rider Code')}")
                continue
            
            obj, created = InsuranceAsegoRiderMaster.objects.get_or_create(
                rider_code=rider_code,
                name=row.get("Name", "").strip(),
                amount=row.get("Amount", "").strip(),
                restricted_amount=row.get("RestrictedAmount", "").strip(),
                deductibles=row.get("Deductibles", "").strip(),
                deductible_text=eval(row.get("DeductibleText").strip()),
                currency=row.get("Currency", "").strip()
            )
            if not created:
                obj.name = row.get("Name", "").strip()
                obj.save()
        print("sync_rider_master")


    def sync_plan(self, url):
        rows = self.fetch_csv_data(url)
        for row in rows:
            try:
                plan_code = uuid.UUID(row.get("Plan Code"))
            except Exception:
                print(f" Invalid Plan Code: {row.get('Plan Code')}")
                continue

            try:
                category = InsuranceAsegoCategory.objects.get(category_code=uuid.UUID(row.get("Category Code")))
            except InsuranceAsegoCategory.DoesNotExist:
                print(f" Category with code {row.get('Category Code')} not found. Skipping row.")
                continue

            try:
                visiting = InsuranceAsegoVisitingCountry.objects.filter(reference=row.get("Country Code")).first()
            except InsuranceAsegoVisitingCountry.DoesNotExist:
                print(f" Visiting country with code {row.get('Country Code')} not found. Skipping row.")
                continue

            obj, created = InsuranceAsegoPlan.objects.get_or_create(
                plan_code=plan_code,
                defaults={
                    "name": row.get("Name", "").strip(),
                    "category": category,
                    "day_plan": row.get("Day Plan", "").strip().lower() == 'true',
                    "trawelltag_option": row.get("Trawell Tag Option", "").strip().lower() == 'true',
                    "annual_plan": row.get("Annual Plan", "").strip().lower() == 'true',
                    "country": visiting,
                }
            )
            if not created:
                obj.name = row.get("Name", "").strip()
                obj.category = category
                obj.day_plan = row.get("Day Plan", "").strip().lower() == 'true'
                obj.trawelltag_option = row.get("Trawell Tag Option", "").strip().lower() == 'true'
                obj.annual_plan = row.get("Annual Plan", "").strip().lower() == 'true'
                obj.country = visiting
                obj.save()
        print("sync_plan")


    def sync_plan_riders(self, url):
        rows = self.fetch_csv_data(url)
        for row in rows:
            try:
                plan_code = uuid.UUID(row.get("Plan Code"))
                rider_code = uuid.UUID(row.get("Rider Code"))
            except Exception:
                print(f" Invalid Plan or Rider Code in Plan Riders: {row}")
                continue

            try:
                plan = InsuranceAsegoPlan.objects.get(plan_code=plan_code)
                rider = InsuranceAsegoRiderMaster.objects.get(rider_code=rider_code)
            except (InsuranceAsegoPlan.DoesNotExist, InsuranceAsegoRiderMaster.DoesNotExist) as e:
                print(f" Plan or Rider not found in Plan Riders: {e}")
                continue

            obj, created = InsuranceAsegoPlanRider.objects.get_or_create(
                plan=plan,
                rider=rider,
                defaults={"trawell_assist_charges_percent": row.get("Trawell Assist Charges Percent").strip()}
            )
            if not created:
                obj.trawell_assist_charges_percent = row.get("Trawell Assist Charges Percent").strip()
                obj.save()
        print("sync_plan_riders")


    def sync_premium_chart(self, url):
        rows = self.fetch_csv_data(url)
        for row in rows:
            try:
                plan_code = uuid.UUID(row.get("Plan Code"))
            except Exception:
                print(f" Invalid Plan Code in Premium Chart: {row.get('Plan Code')}")
                continue

            try:
                plan = InsuranceAsegoPlan.objects.get(plan_code=plan_code)
            except InsuranceAsegoPlan.DoesNotExist:
                print(f" Plan not found in Premium Chart for code: {row.get('Plan Code')}")
                continue

            obj, created = InsuranceAsegoPremiumChart.objects.get_or_create(
                plan=plan,
                age_limit=int(row.get("Age Limit", 0)),
                day_limit=int(row.get("Day Limit", 0)),
                defaults={"premium": float(row.get("Premium", 0))}
            )
            if not created:
                obj.premium = float(row.get("Premium", 0))
                obj.save()
        print("sync_premium_chart")
