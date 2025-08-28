from django.core.exceptions import ObjectDoesNotExist
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import HttpResponse
import requests
from datetime import datetime, timedelta
from tools.easy_link.xml_restructure import XMLData
from integrations.general.models import Integration
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from users.models import Organization
from .models import CreditLog, OrganizationFareAdjustment, Payments,DistributorAgentTransaction
from rest_framework.generics import RetrieveAPIView, RetrieveUpdateAPIView
from .serializers import *
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
from rest_framework import viewsets
from datetime import datetime, timezone
from django.http import JsonResponse
from .models import (
    DistributorAgentFareAdjustment,
    DistributorAgentTransaction,
    DistributorAgentFareAdjustmentLog,
    PaymentUpdates,
)
from django.db.models import Q, Count

from users.models import Country, UserDetails, ErrorLog
from bookings.flight.models import Booking,FlightBookingItineraryDetails
import razorpay
from tools.kafka_config.config import invoke
from .services import (
    getanalysisreport,
    structure_data,
    razor_webhook,
    razor_pay,
    get_ledger_report,
    update_credit_limit,
    get_accounting_software_credentials,
    get_credit_limit,
)
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from api.settings import API_URL, WEB_URL
import html
import re
import xml.etree.ElementTree as ET
import time
from users.views import Registration
from users.permission import HasAPIAccess


class CustomPageNumberPagination(PageNumberPagination):
    def __init__(self, page_size=15, *args, **kwargs):
        self.page_size = page_size
        return super().__init__(*args, **kwargs)

    page_size_query_param = "page_size"
    max_page_size = 100


class OrganizationCreditBalanceView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]

    def get(self, request):
        organization_id = request.GET["organization_id"]
        obj = Organization.objects.get(id=organization_id)
        try:
            # url,  branch_code,  portal_reference_code = self.get_accounting_software_credentials(request.user.organization.organization_country.id, request.user.organization)
            url, branch_code, portal_reference_code = (
                get_accounting_software_credentials(request.user.organization)
            )
        except Exception as e:
            return Response(
                {"error_code": 1, "error": str(e), "message": str(e), "data": None},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            response = get_credit_limit(
                base_url=url,
                portal_ref_code=portal_reference_code,
                billing_code=obj.easy_link_billing_code,
            )
            credit_data = response.data
            return Response(credit_data)
        except Exception as e:
            return Response(
                {
                    "error_code": 1,
                    "error": "Unable to fetch credit data",
                    "message": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

from api import settings

class CreditBalanceView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # url,  branch_code,  portal_reference_code = self.get_accounting_software_credentials(request.user.organization.organization_country.id)
            url, branch_code, portal_reference_code = (
                get_accounting_software_credentials(request.user.organization)
            )
        except Exception as e:
            return Response(
                {
                    "error_code": 1,
                    "error": str(e),
                    "message": str(e),
                    "data": {
                        "country_id": request.user.organization.organization_country.id
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )

        try:
            if request.user.role.name == "distributor_agent":
                agent = DistributorAgentFareAdjustment.objects.filter(user=request.user)
                if not agent:
                    return Response(
                        {
                            "message": "internal server error",
                            "error_code": "ac-sh-credit1",
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                else:
                    agent = agent.first()
                    data = {
                        "L": "0.00",
                        "F": agent.available_balance,
                        "V": "0",
                        "I": "0",
                        "O": "0",
                        "H": "0",
                        "LC": "0.00",
                        "FC": agent.credit_limit,
                        "VC": "0",
                        "IC": "0",
                        "OC": "0",
                        "HC": "0",
                    }
                    return Response(data)
            response = get_credit_limit(
                portal_ref_code=portal_reference_code,
                billing_code=request.user.organization.easy_link_billing_code,
                base_url=url,
            )
            if settings.DEBUG:
                data = {
                    "L": "0.00",
                    "F": "1000000",
                    "V": "0",
                    "I": "0",
                    "O": "100000",
                    "H": "0",
                    "LC": "0.00",
                    "FC": "10000",
                    "VC": "0",
                    "IC": "0",
                    "OC": "100000",
                    "HC": "0",
                }
                return Response(data)
            else:
                credit_data = response.data
                return Response(credit_data)
        except Exception as e:
            return Response(
                {
                    "error_code": 1,
                    "error": "Unable to fetch credit data",
                    "message": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class UpdateCreditLImitView(CreditBalanceView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data

        organization_id = data.get("organization_id")
        credit_limit = data.get("credit_limit")
        try:
            # url,  branch_code,  portal_reference_code = self.get_accounting_software_credentials(request.user.organization.organization_country.id)
            url, branch_code, portal_reference_code = (
                get_accounting_software_credentials(request.user.organization)
            )

        except Exception as e:
            return Response(
                {"error_code": 1, "error": str(e), "message": str(e), "data": None},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            organization = Organization.objects.get(id=organization_id)
            s_acc_code = organization.easy_link_account_code
        except Organization.DoesNotExist:
            return Response(
                {"error_code": 1, "error": "Organization not found", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        available_limit = update_credit_limit(
            s_br_code=branch_code,
            portal_ref_code=portal_reference_code,
            s_acc_code=s_acc_code,
            s_cred_limit=credit_limit,
            s_credit_type="F",
            base_url=url,
        )
    
        if available_limit.status_code == 200:
            data = available_limit.data
            data["message"] = "successfully updated"
            CreditLog.objects.create(
                user=request.user,
                ammount=credit_limit,
                organization=organization,
                credit_type="credit_limit",
                log_message=f"New ammount: {credit_limit}",
            )
            return Response(data, status=status.HTTP_200_OK)
        elif available_limit.status_code == 400:
            return Response(
                {
                    "error": "Cannot update credit limit",
                    "message": f"Cannot update credit limit error->{available_limit.error}",
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response("errrorr")

    def get_balance(self, request):
        url, branch_code, portal_reference_code = get_accounting_software_credentials(
            request.user.organization
        )

        response = get_credit_limit(
            portal_ref_code=portal_reference_code,
            billing_code=request.user.organization.easy_link_billing_code,
        )
        credit_data = response.data
        return credit_data

# This class `UpdateLimitCredit` handles updating credit limits for organizations with error handling
# and logging.

class UpdateLimitCredit(CreditBalanceView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]

    def post(self, request):
        data = request.data
        organization_id = data.get("organization_id")
        old_credit_limit = data.get("old_credit_limit")
        old_available_balance = data.get("old_available_balance")
        amount = data.get("amount")
        required_fields = {
            "organization_id": organization_id,

            "old_credit_limit": old_credit_limit,

            "old_available_balance": old_available_balance,

            "amount": amount,

        }
        
        missing_fields = [i for i in required_fields if not i]
        if missing_fields:
            missing_fields = "".join(missing_fields)
            return Response(
                {
                    "error_code": 1,
                    "error": f"{missing_fields}",
                    "message": " payload data is missing",
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # url,  branch_code,  portal_reference_code = self.get_accounting_software_credentials(request.user.organization.organization_country.id)
            url, branch_code, portal_reference_code = (
                get_accounting_software_credentials(request.user.organization)
            )

        except Exception as e:
            return Response(
                {"error_code": 1, "error": str(e), "message": str(e), "data": None},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            organization = Organization.objects.get(id=organization_id)
            s_acc_code = organization.easy_link_account_code
        except Organization.DoesNotExist:
            return Response(
                {"error_code": 1, "error": "Organization not found", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        credit_balance = update_credit_limit(
            s_br_code=branch_code,
            portal_ref_code=portal_reference_code,
            s_acc_code=s_acc_code,
            s_cred_limit=amount,
            s_credit_type="F",
            base_url=url,
        )
        if credit_balance.status_code == 200:
            data = credit_balance.data
            data["message"] = "successfully updated"

            # ------------------------START----------------------------------------
            sales_team_mail = (
                organization.sales_agent.email if organization.sales_agent else None
            )
            email = [request.user.email]
            email.append(sales_team_mail)
            activation_date = datetime.fromtimestamp(organization.modified_at).strftime(
                "%d-%m-%Y"
            )
            data_list = {
                "agent_name": organization.organization_name,
                "updated_credit_amount": amount,
                "update_date": activation_date,
                "sales_person_email_id": sales_team_mail,
                "user": request.user.first_name,
                "country_name": request.user.base_country.lookup.country_name,
            }
            invoke(
                event="Credit_Amount_Updated",
                number_list=[],
                email_list=email,
                data=data_list,
            )
            # --------------------------END--------------------------------------

            CreditLog.objects.create(
                user=request.user,
                ammount=amount,
                organization=organization,
                credit_type="credit_limit",
                log_message=f"Old Credit Limit: {old_credit_limit}, Old Available Balance :{old_available_balance}",
            )

            return Response(data, status=status.HTTP_200_OK)

        elif credit_balance.status_code == 400:
            return Response(
                {
                    "error": "Cannot update credit limit",
                    "message": f"Cannot update credit limit error->{credit_balance.error}",
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response("errrorr")


class UpdateBalanceAmmount(CreditBalanceView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data

        organization_id = data.get("organization_id")
        amount = data.get("amount")
        try:
            # url,  branch_code,  portal_reference_code = self.get_accounting_software_credentials(request.user.organization.organization_country.id)
            url, branch_code, portal_reference_code = (
                get_accounting_software_credentials(request.user.organization)
            )

        except Exception as e:
            return Response(
                {"error_code": 1, "error": str(e), "message": str(e), "data": None},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            organization = Organization.objects.get(id=organization_id)
            s_acc_code = organization.easy_link_account_code
        except Organization.DoesNotExist:
            return Response(
                {"error_code": 1, "error": "Organization not found", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        available_limit = update_credit_limit(
            s_br_code=branch_code,
            portal_ref_code=portal_reference_code,
            s_acc_code=s_acc_code,
            s_cred_limit=amount,
            s_credit_type="F",
            base_url=url,
        )

        if available_limit.status_code == 200:
            data = available_limit.data

            data["message"] = "successfully updated"
            CreditLog.objects.create(
                user=request.user,
                ammount=amount,
                organization=organization,
                credit_type="available_balance",
            )

            return Response(data, status=status.HTTP_200_OK)
        elif available_limit.status_code == 400:

            return Response(
                {
                    "error": "Cannot update credit limit",
                    "message": f"Cannot update credit limit error->{available_limit.error}",
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response("errrorr")


class SetTemporaryCreditLimitView(CreditBalanceView):

    def post(self, request):
        data = request.data

        organization_id = data.get("organization_id")
        credit_limit = data.get("credit_limit")
        try:
            # url,  branch_code,  portal_reference_code = self.get_accounting_software_credentials(request.user.organization.organization_country.id)
            url, branch_code, portal_reference_code = (
                get_accounting_software_credentials(request.user.organization)
            )

        except Exception as e:
            return Response(
                {"error_code": 1, "error": str(e), "message": str(e), "data": None},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            organization = Organization.objects.get(id=organization_id)
            s_ref_code = organization.easy_link_account_code

        except Organization.DoesNotExist:
            return Response(
                {"error_code": 1, "error": "Organization not found", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        response = self.set_temporary_credit_limit(
            sbr_code=branch_code,
            portal_code=portal_reference_code,
            reference_id="122344",
            ref_ac_code=s_ref_code,
            credit_limit=credit_limit,
            credit_type="L",
            base_url=url,
        )

        if response.status_code == 200:
            return Response({"data": response.data})
        elif response.status_code == 400:
            return Response(
                {
                    "error": "Cannot set temporary credit limit",
                    "message": response.error,
                },
                status=400,
            )

    def set_temporary_credit_limit(
        self,
        sbr_code,
        portal_code,
        reference_id,
        ref_ac_code,
        credit_limit,
        credit_type,
        base_url,
    ):
        url = f"""{base_url}/SetTempCreditLimit/?sBrCode={sbr_code}&PortalRefCode={portal_code}
        &sAcCode=&sRefAcCode={ref_ac_code}&sCreditLimit={credit_limit}&sCreditType={credit_type}&sRefID={reference_id}"""

        payload = {}
        headers = {}

        response = requests.request("POST", url, headers=headers, data=payload)
        return XMLData.set_temporary_credit_limit_response(response)


class RemoveTempCreditLimitView(CreditBalanceView):

    def post(self, request):
        data = request.data

        organization_id = data["organization_id"]
        credit_limit = data["credit_limit"]
        try:
            # url, branch_code, portal_reference_code = self.get_accounting_software_credentials(request.user.organization.organization_country.id)
            url, branch_code, portal_reference_code = (
                get_accounting_software_credentials(request.user.organization)
            )

        except Exception as e:
            return Response(
                {"error_code": 1, "error": str(e), "message": str(e), "data": None},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            organization = Organization.objects.get(id=organization_id)
            s_ref_code = organization.easy_link_account_code
        except Organization.DoesNotExist:
            return Response(
                {"error_code": 1, "error": "Organization not found", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        response = self.remove_temp_credit_limit(
            sbr_code=branch_code,
            portal_code=portal_reference_code,
            reference_id="ref code",
            ref_ac_code=s_ref_code,
            credit_limit=credit_limit,
            credit_type="L",
            base_url=url,
        )

        if response.status_code == 200:
            return Response({"data": response.data})
        elif response.status_code == 400:
            return Response(
                {
                    "error": "Cannot remove temporary credit limit",
                    "message": response.error,
                },
                status=400,
            )

    def remove_temp_credit_limit(
        self,
        sbr_code,
        portal_code,
        reference_id,
        ref_ac_code,
        credit_limit,
        credit_type,
        base_url,
    ):
        url = f"""{base_url}/RemoveTempCreditLimit/?
        sBrCode={sbr_code}&PortalRefCode={portal_code}&sAcCode=&sRefAcCode={ref_ac_code}&sCreditLimit={credit_limit}&sCreditType={credit_type}&sRefID={reference_id}"""

        payload = {}
        headers = {}

        response = requests.request("POST", url, headers=headers, data=payload)

        return XMLData.remove_temporary_credit_limit_response(response)


class OrganizationDetailView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    queryset = Organization.objects.all()
    serializer_class = OrganizationDetailSerializer
    lookup_field = "id"


class FlightBilling(APIView):
    def post(self, request):
        soap_url = "http://demo.e-travel.co.in/ws/etbTktService.svc"

        # Define the SOAP envelope with your method and data
        soap_envelope = f"""
                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <processEasyBillImp xmlns="http://tempuri.org/">
                    <sBrCode>000001BOM</sBrCode>
                    <sPortalRefCode>DEMOPORTAL2</sPortalRefCode>
                    <sXMLtktData>
                        <![CDATA[
                        <Invoicedata>
                        <Invoice XORef="" CustCode="AP787" S3Date="" S4Date="" S5Date ="" S6Date="" suppcode="" AirCode="AI098" diflg="I" PNRAir="" PNRCrs="" tktRef="RAMESH" tktNo="1234123901" tktDt="05/03/2024" tkttype="B" RCFlag="" ReftktNo="" Region="" ReftktDt="" AirCCNo="" PaxName="MR ASDFASFDF" Sector="BOM/DXB" CRS="GA" FareBasis="" DealCode="" S1Sector="BOM/DXB" S1FltNo="AI" S1Date="05/03/2024" S1Class="" S1FltType="" S2Sector="" S2FltNo="" S2Date="" S2Class="" S2FltType="" BasicFare="15000.0000" AddlAmt="0.0000" SuppAddlAmt="0.0000" NC1Tax="0.0000" NC1AddlAmt="0.0000" NC2Tax="0.0000" NC2AddlAmt="0.0000" CTax="0.0000" CAddlAmt="0.0000" JNTax="0.0000" JNAddlAmt="0.0000" TxnFees="0.0000" OCTax="0.0000" StdComm="0.0000" CPInc="0.0000" NCPInc="0.0000" PLB="0.0000" OR="0.0000" SrvChrgs="0.0000" MGTFee="0.0000" CustStdComm="50.0000" CustCPInc="1495.0000" CustNCPInc="1346.0000" CustPLB="1211.0000" CustOR="1090.0000" CustSrvChrgs="10.0000" CustMGTFee="2500.0000" PercTDS="0.0000" TDS="0.0000" CustPercTDS="0.0000" CustTDS="0.0000" sGTAX="" PercGTAX="0.0000" GTAX="0.0000" sCustGTAX="B" CustPercGTAX="0.0000" CustGTAX="0.0000" CustGTAXAdl="0.0000" SCPercGTAX="0.0000" SCGTAX="0.0000" SCPercSrch="0.0000" SCSrch="0.0000" CustSCPercGTAX="12.0000" CustSCGTAX="1.2000" CustSCPercSrch="2.0000" CustSCSrch="0.0200" />
                        </Invoicedata>
                        ]]>
                    </sXMLtktData>
                    </processEasyBillImp>
                </soap:Body>
                </soap:Envelope>
                """

        # Define headers for the SOAP request
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "http://tempuri.org/IetbTktService/processEasyBillImp",
        }

        # Send the POST request
        response = requests.post(soap_url, data=soap_envelope, headers=headers)
        return Response({"message": "success"})

    # def get_ledger_accounts(sbr_code:str, portal_code:str, account_type:str,
    #                     account_code:str, from_date:str, to_date:str):
    #     url = f"http://demo.e-travel.co.in/ws/etbSoap.svc/getLedgerRptXML/?sBrCode={sbr_code}&PortalRefCode={portal_code}"

    #     payload = f"<Filterdata>\r\n<param AcType=\"{account_type}\" AcCode=\"{account_code}\" Format=\"AAB\" FromDate=\"{from_date}\" ToDate=\"{to_date}\" />\r\n</Filterdata>"
    #     headers = {
    #         'Content-Type': 'text/plain',
    #     }

    #     response = requests.request("POST", url, headers=headers, data=payload)
    #     return XMLData.get_ledger_accounts_response(response)


class CreditLogHistory(APIView):
    def get(self, request):
        page_size = int(request.query_params.get("page_size", 15))
        search = request.query_params.get("search_key", None)
        obj_list = CreditLog.objects.all().order_by("-created_at")
        total_data = len(obj_list)

        if search:
            obj_list = obj_list.filter(
                Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(organization__organization_name__icontains=search)
            )
        paginator = CustomPageNumberPagination(page_size=page_size)
        paginated_queryset = paginator.paginate_queryset(obj_list, request)
        serializer = HistorySerializer(paginated_queryset, many=True)
        data = {
            "results": serializer.data,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next_page": paginator.get_next_link(),
            "prev_page": paginator.get_previous_link(),
            "total_data": total_data,
            "page_size": page_size,
        }

        return Response(data, status=status.HTTP_200_OK)

from rest_framework.decorators import action

class CustomerCommisionViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
    queryset = OrganizationFareAdjustment.objects.all()
    serializer_class = CustomerCommisionSerializer
# 
    def get_queryset(self):
        if self.request.method == "GET":
            organization_id = self.request.query_params["organization_id"]
            if organization_id:
                queryset = OrganizationFareAdjustment.objects.filter(
                    organization_id=organization_id
                )
                return queryset if queryset.exists() else OrganizationFareAdjustment.objects.none()
        else:
            queryset = OrganizationFareAdjustment.objects.all()
            return queryset
        
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response(
                [{
                    "cashback": 0.0,
                    "markup": 0.0,
                    "cancellation_charges": 0.0,
                    "parting_percentage": 100.0,
                    "module": "flight",
                }],
                status=status.HTTP_200_OK
            )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def update(self, request,*args, **kwargs):
        data = request.data
        if isinstance(data, list):
            for item in data:
                org = item.get('organization')
                module = item.get('module')
                cashback = item.get('cashback')
                parting_percentage = item.get('parting_percentage')
                markup = item.get('markup')
                cancellation_charges = item.get('cancellation_charges')
                obj, created = OrganizationFareAdjustment.objects.update_or_create(
                    organization_id=org, 
                    module=module,
                    defaults={
                        'cashback': cashback,
                        'parting_percentage': parting_percentage,
                        'markup': markup,
                        'cancellation_charges': cancellation_charges
                    }
                )
                if created:
                    print(f"New row created for module {module}")
                else:
                    print(f"Row updated for module {module}")
        else:
            return  Response({"message":"The data should be in a list format"})
        return Response({"message":"Updated Successfully"})


class DistributorAgentFareAdjustmentRetrieveUpdateView(APIView):
    permission_classes = []
    authentication_classes = []
    
    def get(self, request, user_id):
        adjustments = DistributorAgentFareAdjustment.objects.filter(user__id=user_id)
        if not adjustments:
            return Response(
                [{
                    "cashback": 0.0,
                    "markup": 0.0,
                    "cancellation_charges": 0.0,
                    "parting_percentage": 100.0,
                    "module": "flight",
                }],
                status=status.HTTP_200_OK
            )
        serializer = DistributorAgentFareAdjustmentSerializer(adjustments, many=True)
        return Response(serializer.data)
    
    def patch(self, request, user_id):
        adjustments = DistributorAgentFareAdjustment.objects.filter(user__id=user_id)
        if not adjustments:
            return Response({"message": "No user found"}, status=status.HTTP_404_NOT_FOUND)
        update_data = request.data
        if isinstance(update_data,list):
            for data in update_data:
                module = data.get("module")
                try:
                    adjustment = adjustments.get(user__id=user_id, module = module)
                    serializer = DistributorAgentFareAdjustmentSerializer(adjustment, data=data, partial=True)
                    if serializer.is_valid():
                        serializer.save()
                    else:
                        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                except DistributorAgentFareAdjustment.DoesNotExist:
                    return Response({"message": "Record not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({"message": "The data should be in a list format"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "Updated successfully"}, status=status.HTTP_200_OK)
    
# class DistributorAgentFareAdjustmentRetrieveUpdateView(RetrieveUpdateAPIView):
    # permission_classes = []
    # authentication_classes = []
    # queryset = DistributorAgentFareAdjustment.objects.all()
    # serializer_class = DistributorAgentFareAdjustmentSerializer
    # lookup_field = "user_id"
    # allowed_methods = (
    #     "GET",
    #     "PATCH",
    # )

    # def get_queryset(self):
    #     if self.request.method == "GET":
    #         print("yes")
    #         user_id = self.kwargs["user_id"]
    #         print("user_id", user_id)
    #         if user_id:
    #             return DistributorAgentFareAdjustment.objects.filter(user__id=user_id)
    #         return DistributorAgentFareAdjustment.objects.none() 


class DistributorWalletAdjustmentRetrieveUpdateView(RetrieveUpdateAPIView):
    permission_classes = []
    authentication_classes = []
    queryset = DistributorAgentFareAdjustment.objects.all()
    serializer_class = DistributorAgentWalletAdjustmentSerializer
    lookup_field = "user_id"
    allowed_methods = (
        "GET",
        "PATCH",
    )

    def get_queryset(self):
        return DistributorAgentFareAdjustment.objects.filter(
            user__id=self.kwargs["user_id"]
        )

    def get_serializer_context(self):

        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class LedgerReportApiView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:

            organization_id = request.data.get("organization_id")
            organization_obj = Organization.objects.filter(id=organization_id).first()
            easy_link_billing_obj = organization_obj.easy_link_billing_account
            account_code = (
                organization_obj.easy_link_billing_code
            )  # EASY_LINK_BILLING_CODE
            result = {}
            if easy_link_billing_obj:
                for item in easy_link_billing_obj.data:
                    result.update(item)
            baseurl = result.get("url")
            branch_code = result.get("branch_code")
            portal_reference_code = result.get("portal_reference_code")
            kwargs = {
                "from_date": request.data.get("from_date"),
                "to_date": request.data.get("to_date"),
                "base_url": baseurl if baseurl else None,
                "branch_code": branch_code if branch_code else None,
                "portal_reference_code": (
                    portal_reference_code if portal_reference_code else None
                ),
                "account_code": account_code,
            }
            report_data = get_ledger_report(kwargs)
            ErrorLog.objects.create(
                module="get_ledger_report",
                erros={
                    "report_data.text": report_data.text,
                    "account_code": account_code,
                },
            )

            # final_response = structure_data(report_data,organization_obj,kwargs)
            # if final_response:
            #     return Response(final_response)
            if not report_data:
                return Response({})

            final_response =  report_data.text
            # Step 1: Extract the inner XML content from the <string> tag
            root = ET.fromstring(final_response)
            inner_xml = root.text

            # Step 2: Decode the inner XML (handle HTML entities)
            decoded_xml = html.unescape(inner_xml)

            # Step 3: Clean up whitespace, control characters, and non-ASCII characters
            cleaned_xml = re.sub(r'[\n\r\t]+', ' ', decoded_xml)  # Remove newlines and tabs
            cleaned_xml = re.sub(r'[^ -~]+', ' ', cleaned_xml)  # Remove non-ASCII characters
            cleaned_xml = cleaned_xml.replace('&#xD;', '')  # Remove carriage returns
            cleaned_xml = cleaned_xml.strip()  # Remove extra spaces

            # Step 4: Properly encode XML special characters
            cleaned_xml = cleaned_xml.replace('&', '&amp;')
            print("cleaned_xml-----------",cleaned_xml)
            # Step 5: Parse the cleaned XML
            try:
                inner_root = ET.fromstring(cleaned_xml)
            except ET.ParseError as e:
                print(f"XML Parse Error: {e}")
                raise

            # Step 6: Extract transaction data
            data = []
            for txn in inner_root.findall('txn'):
                txn_data = {
                    'accode': txn.attrib.get('accode', ''),
                    'acname': txn.attrib.get('acname', ''),
                    'txnid': txn.attrib.get('txnid', ''),
                    'txncode': txn.attrib.get('txncode', ''),
                    'tmdate': txn.attrib.get('tmdate', ''),
                    'tmref': txn.attrib.get('tmref', ''),
                    'tnarr': txn.attrib.get('tnarr', ''),
                    'damt': txn.attrib.get('damt', '0.0'),
                    'camt': txn.attrib.get('camt', '0.0'),
                    'chqdetail': txn.attrib.get('chqdetail', ''),
                    'dopamt': txn.attrib.get('dopamt', '0.0'),
                    'copamt': txn.attrib.get('copamt', '0.0'),
                }
                data.append(txn_data)


            return Response({"data": {"RESULT":data}})
        except Exception as e:

            return Response({"error": str(e)})


class DistributorBalanceAdjustmentView(APIView):
    def post(self, request, user_id):
        new_available_balance = request.data.get("new_available_balance")
        if not new_available_balance:
            return Response(
                {"message": "new_available_balance-- key mising in payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            agent = DistributorAgentFareAdjustment.objects.get(user__id=user_id)
        except DistributorAgentFareAdjustment.DoesNotExist:
            return Response(
                {"message": "Agent Balance doesnt exist"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        old_available_balance = agent.available_balance

        if new_available_balance < old_available_balance:
            return Response(
                {
                    "message": f"new balance amount:{new_available_balance} cannot be less than old balance {old_available_balance} "
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        DistributorAgentTransaction.objects.create(
            user=agent.user,
            transtransaction_type="credit",
            amount=new_available_balance,
        )
        DistributorAgentFareAdjustmentLog.objects.create(
            old_credit_limit=agent.credit_limit,
            old_available_balance=agent.available_balance,
            new_credit_limit=agent.credit_limit,
            new_available_balance=new_available_balance,
        )
        agent.available_balance = new_available_balance
        agent.save()

        # ------------------------START----------------------------------------
        organization = request.user.organization
        sales_team_mail = (
            organization.sales_agent.email if organization.sales_agent else None
        )
        dis_owner_email = [request.user.email]

        dis_agent_email = agent.user.email
        email = dis_owner_email
        email.append(dis_agent_email)
        activation_date = datetime.fromtimestamp(organization.modified_at).strftime(
            "%d-%m-%Y"
        )
        data_list = {
            "Agent": agent.user.organization.organization_name,
            "agent_name": agent.user.first_name,
            "updated_credit_amount": new_available_balance,
            "update_date": activation_date,
            "Distributor_Name": request.user.first_name,
            "country_name": request.user.base_country.lookup.country_name,
        }
        invoke(
            event="Credit_Amount_Intimation",
            number_list=[],
            email_list=email,
            data=data_list,
        )
        # --------------------------END--------------------------------------
        return Response({"message": "success"}, status=status.HTTP_200_OK)


class ShowRechargeButton(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        show_button = request.user.role.name != "distributor_agent"
        organization = request.user.organization
        
        billing_code = organization.easy_link_billing_code if organization else None
        return Response(
            {
                "message": "success",
                "data": {
                    "show_button": show_button,
                    "billing_code": billing_code,
                },
            },
            status=status.HTTP_200_OK,
        )
     


class WalletRecharge(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = request.data.get("amount", None)
        base_url = request.data.get("base_url", None)
        if not amount:
            return Response(
                {"message": "amount -- key missing in payload"},
                status=status.HTTP_200_OK,
            )
        if not base_url:
            return Response(
                {"message": "base_url -- key missing in payload"},
                status=status.HTTP_200_OK,
            )

        organization_country_id = request.user.organization.organization_country_id
        data, is_success = self.get_razorpay_credentials(organization_country_id)
        if not is_success:
            return Response(
                {"message": data}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        api_key = data["api_key"]
        api_secret = data["api_secret"]

        data, is_success = self.initiate_razor_pay(
            api_key, api_secret, amount, base_url
        )
        if not is_success:
            return Response(
                {"message": f"{data} error_code:a-s-wr-824"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        session_id = data["session_id"]
        short_url = data["short_url"]
        return Response(
            {"data": {"session_id": session_id, "short_url": short_url}},
            status=status.HTTP_200_OK,
        )

    def get_razorpay_credentials(self, country_id):
        try:
            obj = Integration.objects.get(name="razorpay", country_id=country_id)
        except Integration.DoesNotExist:
            counry = Country.objects.get(id=country_id)
            return (
                f"razorpay is not installed in this portal for country {counry.lookup.country_name} please contact admin",
                False,
            )
        obj = obj.data[0]
        data = dict(api_key=obj["api_key"], api_secret=obj["api_secret"])
        return data, True

    def initiate_razor_pay(self, api_key, api_secret, amount, base_url):
        try:
            client = razorpay.Client(auth=(api_key, api_secret))
            response = client.payment_link.create(
                {
                    "amount": 100 * amount,
                    "currency": "INR",
                    "description": "description",
                    "customer": {
                        "name": "",
                        "email": "",
                        "contact": "",
                    },
                    "notify": {"sms": True, "email": True},
                    "reminder_enable": True,
                    "notes": {"policy_name": "policy_name"},
                    "callback_url": f"{base_url}status?confirmation=success&payment_method=razor_pay",
                    "callback_method": "get",
                }
            )

            session_id = response.get("id")
            short_url = response.get("short_url")
            data = dict(session_id=session_id, short_url=short_url)
            return data, True
        except Exception as e:
            return str(e), False


class PaymentUpdateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [HasAPIAccess]
    serializer_classes = PaymentUpdateSerializer

    def post(self, request):
        agency_name = request.data.get("agency_name")
        agency_id = request.data.get("agency_id")
        amount = request.data.get("amount")
        bank_name = request.data.get("bank_name")
        attachment_url = request.data.get("attachment_url")
        date = request.data.get("date")
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        remarks = request.data.get("remarks")
        agency_id = request.user

        payment_update = PaymentUpdates.objects.create(
            agency_name=agency_name,
            amount=amount,
            agency=agency_id,
            bank_name=bank_name,
            date=date_obj,
            attachment_url=attachment_url,
            remarks=remarks,
        )
        # if to_do:
        country_name = (
            request.user.organization.organization_country.lookup.country_name
        )
        sales_team_mail = (
            request.user.organization.sales_agent.email
            if request.user.organization.sales_agent
            else None
        )
        email_data = [request.user.email]
        if sales_team_mail:
            email_data.append(sales_team_mail)

        if request.user.role.name in ["agency_owner", "distributor_owner", "out_api_owner"]:
            data_list = {
                "agent_name": agency_name,
                "amount_transferred": amount,
                "transaction_id": remarks,
                "transfer_date": date,
                "Bank": bank_name,
                "country_name": country_name,
            }
            invoke(
                event="Payment_Intimation",
                number_list=[],
                email_list=email_data,
                data=data_list,
            )

            return Response({"message": "success"}, status=status.HTTP_201_CREATED)
        elif request.user.role.name in [
            "agency_staff",
            "distributor_agent",
            "distributor_staff",
            "out_api_staff"
        ]:
            data_list = {
                "Agent": agency_name,
                "agent_name": agency_name,
                "bank_name": bank_name,
                "amount_transferred": amount,
                "transaction_id": remarks,
                "transfer_date": date,
                "country_name": country_name,
                "agent_email": request.user.email,
            }
            invoke(
                event="Bank_Transfer_Notification",
                number_list=[],
                email_list=email_data,
                data=data_list,
            )
            return Response({"message": "success"}, status=status.HTTP_201_CREATED)

    def get(self, request):
        agency = self.request.query_params.get("id")
        payment_updates = PaymentUpdates.objects.filter(agency=agency)
        # payment_updates = PaymentUpdates.objects.filter(agency="bebdc6eb-d99f-45cb-affa-e93e223c3c50")
        serializer = self.serializer_classes(payment_updates, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PaymentUpdatesFilterView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    # permission_classes=[AllowAny]
    serializer_classes = PaymentUpdateSerializer

    def post(self, request):
        from_date = request.data.get("from_date")
        to_date = request.data.get("to_date")
        agent = request.data.get("agent")
        from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
        to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
        filters = {"status": "pending"}
        if agent:
            filters["agency"] = agent
        if from_date_obj and to_date_obj:
            filters["date__range"] = (from_date_obj, to_date_obj)
        payment_updates = PaymentUpdates.objects.filter(**filters)

        serializer = self.serializer_classes(payment_updates, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UpdatePaymentStatusView(APIView):
    # permission_classes = [AllowAny]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Validate request data
            status_choice = request.data.get("status")
            payment_id = request.data.get("payment_id")
            if not status_choice or not payment_id:
                return Response(
                    {"message": "Invalid data provided"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Retrieve payment object
            payment_obj = PaymentUpdates.objects.filter(id=payment_id).first()
            if not payment_obj:
                return Response(
                    {"message": "Payment record not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            # Update and save the object
            payment_obj.status = status_choice
            payment_obj.save()

            amount = payment_obj.amount
            if amount is None:
                return Response(
                    {"message": "Amount is missing for the payment record"},
                    status=status.HTTP_400_BAD_REQUEST,
                    )
            user_id = payment_obj.agency.id

            if not user_id:
                return Response(
                    {"message": "Agency/User ID is missing in the payment record"},
                    status=status.HTTP_400_BAD_REQUEST,
                )


#-------------------------------------------------------------------------------------------------------
            if status_choice == "approve":
                new_available_balance = amount
                if not new_available_balance:
                    return Response(
                        {"message": "new_available_balance-- key mising in payload"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                try:
                    agent = DistributorAgentFareAdjustment.objects.get(user__id=user_id)
                except DistributorAgentFareAdjustment.DoesNotExist:
                    return Response(
                        {"message": "Agent Balance doesnt exist"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                old_available_balance = agent.available_balance
                current_available_balance = old_available_balance + float(new_available_balance)
                DistributorAgentTransaction.objects.create(
                    user=agent.user,
                    transtransaction_type="credit",
                    amount=new_available_balance,
                    booking_type = 'Bank Credit Receipt'
                )
                DistributorAgentFareAdjustmentLog.objects.create(
                    old_credit_limit=agent.credit_limit,
                    old_available_balance=agent.available_balance,
                    new_credit_limit=agent.credit_limit,
                    new_available_balance=current_available_balance,
                )
                agent.available_balance = current_available_balance
                agent.save()
            else:
                pass
        #--------------------------------------------------------------------------------------------------

            return Response({"message": "success"}, status=status.HTTP_200_OK)
        except ObjectDoesNotExist as e:
            return Response(
                {"message": f"Error: {str(e)}"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"message": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ListAllDistributorAgent(APIView):
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    # permission_classes=[AllowAny]
    serializer_classes = UserDetailDistributorsSerializer

    def get(self, request):
        user = request.user
        if user.role.name == "distributor_owner":
            organization_obj = request.user.organization
            user_det = UserDetails.objects.filter(
                organization=organization_obj, role__name="distributor_agent"
            )
            serializer = self.serializer_classes(user_det, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        else:
            return Response(
                {"message": "failed"},
                status=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
            )
class ListAgentBookingIDs(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request):
        agent_id = request.query_params.get('agent_id')
        search_booking_id = request.query_params.get('search')

        if not agent_id:
            return Response(
                {"message": "agent_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            agent = UserDetails.objects.get(id=agent_id, role__name="distributor_agent")
        except UserDetails.DoesNotExist:
            return Response(
                {"message": "Agent not found or is not a distributor agent"},
                status=status.HTTP_404_NOT_FOUND
            )
        # transaction_booking_ids = DistributorAgentTransaction.objects.values_list('booking_id', flat=True)
        valid_bookings = Booking.objects.filter(
            user=agent,
        )
        # .exclude(
        #     id__in=transaction_booking_ids
        # )
        if search_booking_id:
            valid_bookings = valid_bookings.filter(display_id__icontains=search_booking_id)
        valid_bookings = valid_bookings.distinct().values("id", "display_id").order_by('-booked_at')[:10]
        return Response(
            {"bookings": list(valid_bookings)},
            status=status.HTTP_200_OK
        )
class UpdateDistributorTransactionView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:            
            data = request.data            
            agent_id = data.get('agent_id')
            booking_id = data.get('booking_id')
            amount = data.get('amount')
            created_date = data.get('date')                        
            if not all([agent_id, booking_id, amount, created_date]):
                return JsonResponse({"error": "Missing required fields."}, status=400)

            try:
                created_at = datetime.strptime(created_date, "%d/%m/%Y")
            except ValueError:
                return JsonResponse({"error": "Invalid date format. Use dd/mm/yyyy."}, status=400)

            created_at_timestamp = int(created_at.timestamp())

            agent = UserDetails.objects.filter(id=agent_id).first()
            if not agent:
                return JsonResponse({"error": "Agent not found."}, status=404)

            booking = Booking.objects.filter(id=booking_id, user=agent).first()
            if not booking:
                return JsonResponse({"error": "Booking not found for this agent."}, status=404)

            DistributorAgentTransaction.objects.create(
                user=agent,
                transtransaction_type="credit", 
                booking_type="cancellation",     
                module="flight",                
                amount=float(amount),   
                booking=booking,         
                created_at=created_at_timestamp, 
            )

            fare_adjustment = DistributorAgentFareAdjustment.objects.filter(user=agent).first()
            if fare_adjustment:
                fare_adjustment.available_balance += float(amount)
                fare_adjustment.save()  
            return JsonResponse({"success": "Transaction updated successfully."}, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

   
import traceback


class GetAnalysisReport(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization_id = request.data.get("organization_id")
        organization_obj = Organization.objects.filter(id=organization_id).first()
        # _____________________________start___________________________________________________
        easy_link_billing_obj = organization_obj.easy_link_billing_account
        result = {}
        if easy_link_billing_obj:
            for item in easy_link_billing_obj.data:
                result.update(item)
        baseurl = result.get("url")
        branch_code = result.get("branch_code")
        portal_reference_code = result.get("portal_reference_code")
        # ______________________________end__________________________________________________

        account_code = organization_obj.easy_link_billing_code
        # account_code = "B0155"
        kwargs = {
            "account_type": request.data.get("account_type", "CC"),
            "account_code": account_code,
            "format": request.data.get("format", "AAB"),
            "from_date": request.data.get("from_date"),
            "to_date": request.data.get("to_date"),
            "transaction_types": request.data.get("transaction_types"),
            "merge_child": request.data.get("merge_child", "Y"),
            "base_url": baseurl if baseurl else None,
            "branch_code": branch_code if branch_code else None,
            "portal_reference_code": (
                portal_reference_code if portal_reference_code else None
            ),
        }
        try:
            # Assuming LedgerReport.getanalysisreport returns a dictionary-like response
            report_data = getanalysisreport(kwargs)
            if not report_data:
                return Response({})
            final_response = structure_data(report_data, organization_obj, kwargs)
            if final_response:
                return Response(final_response)
            else:
                return Response({})
        except Exception as e:
            # Print the traceback with line number
            traceback.print_exc()
            # Handling errors and returning a meaningful response
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GetTransactionPdf(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    # permission_classes = [AllowAny]

    def get(self, request):
        # easy_link_billing_account = UserDetails.objects.filter(id="599b1d23-120a-42ae-be6f-7386b5528006").first().organization.easy_link_billing_account.data
        txn_code = request.query_params.get("txn_code")
        easy_link_billing_account = (
            request.user.organization.easy_link_billing_account.data
        )
        result = {}
        for item in easy_link_billing_account:
            result.update(item)
        url = result.get("url")
        branch_code = result.get("branch_code")
        portal_reference_code = result.get("portal_reference_code")
        full_url = f"{url}/GetTxnPDF?sBrCode={branch_code}&PortalRefCode={portal_reference_code}&sTxnCode={txn_code}"
        headers = {"Cookie": "ASP.NET_SessionId=ekv3h5hgkhvhcavasnxssar1"}
        payload = {}
        response = requests.request("GET", full_url, headers=headers, data=payload)
        pdf_response = HttpResponse(response, content_type="application/pdf")
        pdf_response["Content-Disposition"] = f"attachment; filename=transaction.pdf"

        return pdf_response


class UpdatePaymentDistributorAgentView(APIView):
    def post(self, request, user_id):
        return Response({"message": "success"}, status=status.HTTP_200_OK)


@csrf_exempt
def razorpay_success_url(request):
    status = request.query_params.get("confirmation")
    url = ""
    if status == "success":
        return redirect(f"{url}payment-success")
    else:
        return redirect(f"{url}payment-failed")


class RazorCallbackApi(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request, format=None):
        try:
            callback_status = request.query_params.get("confirmation")
            web_url = WEB_URL
            if callback_status == "success":

                kwargs = {
                    "razorpay_payment_id": request.query_params.get(
                        "razorpay_payment_id"
                    ),
                    "razorpay_payment_link_id": request.query_params.get(
                        "razorpay_payment_link_id"
                    ),
                    "razorpay_payment_link_status": request.query_params.get(
                        "razorpay_payment_link_status"
                    ),
                    "status": callback_status,
                }
                # razorpay_success_url(kwargs)

                ErrorLog.objects.create(
                    module="call_back_checkup", erros={"call_back_status": kwargs}
                )
                payment_obj = Payments.objects.filter(
                    payment_id_link=kwargs.get("razorpay_payment_link_id"),
                    call_back=False,
                    status="unpaid",
                ).first()
                ErrorLog.objects.create(
                    module="payment_obj", erros={"payment_obj": str(payment_obj)}
                )
                if payment_obj:
                    payment_obj.status = "paid"
                    payment_obj.call_back = True
                    payment_obj.razorpay_payment_id = kwargs.get("razorpay_payment_id")
                    payment_obj.save()
                    try:
                        razor_webhook(kwargs)
                    except:
                        pass
                return redirect(f"{web_url}recharge/payment-success")
                # call_razor_webhook(kwargs)
                # return Response({"status":"success"})
            else:
                kwargs = {"status": callback_status}
                # razorpay_success_url(kwargs)
                return redirect(f"{web_url}recharge/payment-failure")

        except:
            import traceback

            res = {"status": "failure", "message": str(traceback.format_exc())}
            return Response(res)


class PayNowApiView(APIView):
    permission_classes = []

    def post(self, request, format=None):
        try:
            kwargs = request.data
            payment_data = {"agency": request.user, "amount": kwargs.get("amount")}
            payment_obj = Payments.objects.create(**payment_data)
            base_url = API_URL
            ErrorLog.objects.create(
                module="callback_url", erros={"error": str(base_url)}
            )
            country_id = {}
            try:
                organization_id = request.user.organization.id
                organization_det = Organization.objects.filter(id=organization_id).values('id','easy_link_billing_code',
                                                                                                   'easy_link_account_code','organization_name','organization_country_id').first()
                if organization_det.get('organization_country_id') :
                    country_id['country_id'] = organization_det.get('organization_country_id')  
            except:
                
                organization_id = None
                country_id = None

                pass
            
            razorpay_data = (
                Integration.objects.filter(name="razorpay", **country_id).first().data
            )

            result = {}
            for item in razorpay_data:
                result.update(item)
            kwargs["api_key"] = result.get("api_key")
            kwargs["api_secret"] = result.get("api_secret")
            kwargs["callback_url"] = base_url + result.get("callback_url")
            kwargs["organization_id"] = str(organization_det.get('id'))
            kwargs["organization_name"] = organization_det.get('organization_name')
            kwargs["user"] = request.user.first_name
            kwargs["billing_code"] = organization_det.get('easy_link_billing_code')
            kwargs["account_code"] = organization_det.get('easy_link_account_code')
            kwargs["payment_obj"] = payment_obj
            ErrorLog.objects.create(
                module="callback_url", erros={"error": str(kwargs["callback_url"])}
            )

            response = razor_pay(kwargs)
            return Response(response)
        except Exception as e:
            pass
            import traceback

            res = {"status": "failed", "message": str(e)}
            return Response(res, status=status.HTTP_400_BAD_REQUEST)
class GetAgentTransactionLog(APIView):
    def post(self, request):
        agent_id = request.data.get('agent_id')
        from_date = request.data.get('from_date')
        to_date = request.data.get('to_date')

        if not agent_id:
            agent_id = request.user.id

        agent_name = request.data.get("search", "").strip()
        if agent_name and len(agent_name) < 3:
            return Response(
                {"message": "Search term must be at least 3 characters long."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        agent_ids_query = UserDetails.objects.filter(
            organization=request.user.organization,
            role__name="distributor_agent"
        ) if request.user.role.name == "distributor_owner" else UserDetails.objects.filter(id=agent_id)

        agent_ids = agent_ids_query.values_list("id", flat=True)       
    
        transactions_query = DistributorAgentTransaction.objects.filter(
            user__id__in=agent_ids
        )
        if agent_name:
            transactions_query = transactions_query.filter(
                Q(user__first_name__icontains=agent_name) |
                Q(user__last_name__icontains=agent_name) |
                Q(booking__display_id__icontains = agent_name)
            )
        if from_date and to_date:
            from_time = datetime.strptime(from_date,"%d-%m-%y")
            to_time = datetime.strptime(to_date,"%d-%m-%y")  + timedelta(days=1)
            from_timestamp = int(from_time.timestamp())
            to_timestamp = int(to_time.timestamp())

            transactions_query = transactions_query.filter(
            created_at__gte=from_timestamp,
            created_at__lte=to_timestamp
        )
        serializer = DistributorAgentTransactionSerializer(
            transactions_query.order_by("-created_at"), many=True
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
#
class PaymentFilterViewSets(viewsets.ModelViewSet):

    # authentication_classes=[JWTAuthentication]
    permission_classes = []
    serializer_class = PaymentSerializer
    queryset = Payments.objects.all().order_by("-created_at")

    def list(self, request, *args, **kwargs):

        payment_status = request.query_params.get("status")
        payment_types = request.query_params.get("payment_types")
        easy_link_account_code = request.query_params.get("account_code")
        easy_link_billing_code = request.query_params.get("billing_code")
        razorpay_payment_id = request.query_params.get("razorpay_payment_id")
        filters = {}
        if payment_status:
            filters["status"] = payment_status
        if payment_types:
            filters["payment_types"] = payment_types
        if easy_link_account_code:
            filters["agency__organization__easy_link_account_code"] = (
                easy_link_account_code
            )
        if easy_link_billing_code:
            filters["agency__organization__easy_link_billing_code"] = (
                easy_link_billing_code
            )
        if razorpay_payment_id:
            filters["razorpay_payment_id"] = razorpay_payment_id
        filtered_queryset = self.queryset.filter(**filters)
        serializer = self.get_serializer(filtered_queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)




class UpdateCreditLImitEasylinkRegistration(CreditBalanceView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        organization_id = data.get("organization_id")
        credit_limit = data.get("credit_limit")
        if not organization_id or not credit_limit:
            return Response(
                {"error": "Organization ID and Credit Limit are required", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            url, branch_code, portal_reference_code = (
                get_accounting_software_credentials(request.user.organization)
            )

        except Exception as e:
            return Response(
                {"error_code": 1, "error": str(e), "message": str(e), "data": None},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            organization = Organization.objects.get(id=organization_id)
            userdetails = UserDetails.objects.filter(organization=organization).values('email','base_country','phone_number','first_name','last_name').first()
            if userdetails:
                last_name = userdetails.get('last_name','')
                first_name = userdetails.get('first_name', '')
                email = userdetails.get('email', '')
                phone = userdetails.get('phone_number', '')
                base_country = userdetails.get('base_country')
                if base_country:
                    country_name = Country.objects.get(id=base_country)
            try:
                if organization.status =='pending':
                    registration_instance = Registration()
                    company_id = organization.easy_link_billing_code if organization.easy_link_billing_code else registration_instance.create_company_id("")
                    easylink_account_response = registration_instance.register_accounting_software(
                            url = url,
                            sbr_code = branch_code,
                            portal_code = portal_reference_code,
                            account_code = "NEWID",
                            ref_ac_code = company_id,
                            acc_type="CC",
                            ac_name=organization.organization_name,
                            contact_person = first_name + last_name,
                            address_1 = organization.address,
                            address_2 = "",
                            address_3 = "",
                            city = "",
                            pin_code = organization.organization_zipcode,
                            state = organization.state,
                            country = country_name if country_name else None,
                            phone_number1 = phone,
                            phone_number2 = "",
                            phone_number3 = "",
                            fax = "",
                            mobile1 = phone,
                            mobile2 = "",
                            email1 =  email,
                            email2 = "",
                            credit_limit = "1",
                            opening_balance = "0",
                            openiong_balance_type = "C",
                            family= "999",
                            category = "TRAVEL AND TOURS" ,
                            sales_man = "",
                            collection_list = "TEST",
                            pan = "",
                            gst_no = organization.organization_gst_number if organization.organization_gst_number else "",
                    )
                    if easylink_account_response.status_code == 200:
                        data = easylink_account_response.data
                        account_code = data['account_code']
                        account_name = data['account_name']
                        organization.easy_link_account_code = account_code
                        organization.easy_link_account_name = account_name
                        organization.save()
                    else:
                        organization.status = 'pending'
                        organization.save()
                        return Response(
                                        {"error_code": 1, "error": "Failed to create Easylink Customer", "message": "Failed to create Easylink Customer", "data": None},
                                        status=status.HTTP_409_CONFLICT,
                                    )
            except Exception as e:
                return Response(
                    {"error_code": 1, "error": str(e), "message": str(e), "data": None},
                    status=status.HTTP_409_CONFLICT,
                )

            s_acc_code = organization.easy_link_account_code
        except Organization.DoesNotExist:
            return Response(
                {"error_code": 1, "error": "Organization not found", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        available_limit = update_credit_limit(
            s_br_code=branch_code,
            portal_ref_code=portal_reference_code,
            s_acc_code=s_acc_code,
            s_cred_limit=credit_limit,
            s_credit_type="F",
            base_url=url,
        )
    
        if available_limit.status_code == 200:
            data = available_limit.data
            data["message"] = "successfully updated"
            CreditLog.objects.create(
                user=request.user,
                ammount=credit_limit,
                organization=organization,
                credit_type="credit_limit",
                log_message=f"New ammount: {credit_limit}",
            )
            return Response(data, status=status.HTTP_200_OK)
        elif available_limit.status_code == 400:
            return Response(
                {
                    "error": "Cannot update credit limit",
                    "message": f"Cannot update credit limit error->{available_limit.error}",
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response("errrorr")
    



