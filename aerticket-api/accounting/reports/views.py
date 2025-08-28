from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from .flight_module import flight_commission, total_confirmed_booking, total_amount_confirmed_booking, total_bookings,\
                            total_booking_chart, staff_confirmed_booking_pie_chart, organization_count,\
                            registration_count, admin_or_staff_line_chart, vendor_booking_pie_chart,\
                            airline_confirmed_booking_pie_chart, vendor_airline_barchart, sales_performace_table, organization_booking_count,\
                            total_failed_to_rejected_booking,total_failed_to_confirmed_booking, total_failed_to_rejected_chart, total_failed_to_confirmed_chart,\
                            confirmed_booking_chart, confirmed_line_chart,failed_and_rejected_booking_chart, failed_rejected_line_chart



# class CustomPagination(PageNumberPagination):
#     page_size = 15  # Default page size
#     page_size_query_param = 'page_size'
#     max_page_size = 100
    
global_permission_classes = [IsAuthenticated,]
global_authentication_classes = [JWTAuthentication,]
# global_permission_classes = []
# global_authentication_classes = []

# class CustomPageNumberPagination(PageNumberPagination):
#     def __init__(self, page_size=15, *args, **kwargs):
#         self.page_size=page_size
#         return super().__init__(*args,**kwargs)
#     page_size_query_param = 'page_size'
#     max_page_size = 100


class CustomPagination(PageNumberPagination):
    page_size = 15  # Default page size
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_page_size(self, request):
        """Dynamically set page_size from query params, fallback to default (15)."""
        return int(request.query_params.get(self.page_size_query_param, self.page_size))

#-----------------------------Distribution-dashboard----------------------------------------------#


class TotalConfirmedBookingApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            user = request.user
            if user.role.name == 'sales':
                sales_agent_id = user.id 
            else:
                sales_agent_id = request.query_params.get("sales_agent_id", None)
            kwargs = {
                "from_date": request.query_params.get("from_date", None),
                "to_date": request.query_params.get("to_date", None),
                "organization_id": request.query_params.get("organization_id"),
                "sales_agent_id" : sales_agent_id
            }
            results = total_confirmed_booking(**kwargs)

            return Response(results, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TotalAmountBookingConfirmedApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            user = request.user
            if user.role.name == 'sales':
                sales_agent_id = user.id 
            else:
                sales_agent_id = request.query_params.get("sales_agent_id", None)
            kwargs = {
                "from_date": request.query_params.get("from_date", None),
                "to_date": request.query_params.get("to_date", None),
                "organization_id": request.query_params.get("organization_id"),
                "sales_agent_id" : sales_agent_id
            }
            results = total_amount_confirmed_booking(**kwargs)
            return Response(results, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TotalBookingApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            user = request.user
            if user.role.name == 'sales':
                sales_agent_id = user.id 
            else:
                sales_agent_id = request.query_params.get("sales_agent_id", None)
            kwargs = {
                "from_date": request.query_params.get("from_date", None),
                "to_date": request.query_params.get("to_date", None),
                "organization_id": request.query_params.get("organization_id"),
                "sales_agent_id" : sales_agent_id

            }
            results = total_bookings(**kwargs)
            return Response(results, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class CommisionAPIView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):

        module = request.query_params.get("module", None)

        kwargs = {
            "from_date": request.query_params.get("from_date", None),
            "to_date": request.query_params.get("to_date", None),
            "organization_id": request.query_params.get("organization_id"),
        }
        if not (
            kwargs.get("from_date")
            and kwargs.get("to_date")
            and kwargs.get("organization_id")
        ):
            return Response(
                {f"message": "from_date or to_date or organization_id are missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if module == "flight":
            final_result = flight_commission(**kwargs)
            if final_result:
                return Response(final_result, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"message": "failed"}, status=status.HTTP_400_BAD_REQUEST
                )
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TotalBookingChartApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):

        module = request.query_params.get("module", None)
        if module == "flight":

            kwargs = {
                "year": request.query_params.get("year", None),
                "month": request.query_params.get("month", None),
                "organization_id": request.query_params.get("organization_id"),
            }
            if not (kwargs.get("year") and kwargs.get("month")):
                return Response(
                    {"message": f"year and month required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                data = total_booking_chart(**kwargs)
                return Response(data, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )



class StaffConfirmedBookingPieChartApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        # need organization_id and date range (it is taken from the top of the UI)
        module = request.query_params.get("module", None)
        if module == "flight":
            
            kwargs = {
                "from_date": request.query_params.get("from_date", None),
                "to_date": request.query_params.get("to_date", None),
                "organization_id": request.query_params.get("organization_id"),
            }
            final_result = staff_confirmed_booking_pie_chart(**kwargs)
            return Response(final_result, status=status.HTTP_200_OK)
        elif module == 'hotel':
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response({"message":"module missing or invalid module"}, status=status.HTTP_400_BAD_REQUEST)
        
class AirlineConfirmedBookingPieChartApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        # need organization_id and date range (it is taken from the top of the UI)
        module = request.query_params.get("module", None)
        if module == "flight":
            user = request.user
            if user.role.name == 'sales':
                sales_agent_id = user.id 
                
            else:
                sales_agent_id = request.query_params.get("sales_agent_id", None)
            
            kwargs = {
                "from_date": request.query_params.get("from_date", None),
                "to_date": request.query_params.get("to_date", None),
                "organization_id": request.query_params.get("organization_id"),
                "month": request.query_params.get("month", None),
                "year": request.query_params.get("year", None),
                "sales_agent_id" : sales_agent_id
            }
            final_result = airline_confirmed_booking_pie_chart(**kwargs)
            
            return Response(final_result, status=status.HTTP_200_OK)
        elif module == 'hotel':
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response({"message":"module missing or invalid module"}, status=status.HTTP_400_BAD_REQUEST)



class StaffBookingLineChartAPIView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):

        module = request.query_params.get("module", None)
        if module == "flight":

            kwargs = {
                "year": request.query_params.get("year", None),
                "month": request.query_params.get("month", None),
                "agent_id": request.query_params.get("agent_id"),
            }
            if not (kwargs.get("year") and kwargs.get("month")):
                return Response(
                    {"message": f"year and month required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                data = admin_or_staff_line_chart(**kwargs)
                return Response(data, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )



class OrganizationCountAPIView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        
        module = request.query_params.get("module", None)
        if module == "flight":
            user = request.user
            if user.role.name == 'sales':
                sales_agent_id = user.id 
            else:
                sales_agent_id = request.query_params.get("sales_agent_id", None)
                
            
            kwargs = {
                "from_date": request.query_params.get("from_date", None),
                "to_date": request.query_params.get("to_date", None),
                "sales_agent_id" : sales_agent_id
                
            }
            
            results = organization_count(**kwargs)

            return Response(results, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )

class RegistrationCountAPIView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            user = request.user
            if user.role.name == 'sales':
                sales_agent_id = user.id 
            else:
                sales_agent_id = request.query_params.get("sales_agent_id", None)
            kwargs = {
                "from_date": request.query_params.get("from_date", None),
                "to_date": request.query_params.get("to_date", None),
                "sales_agent_id" : sales_agent_id
                
            }
            results = registration_count(**kwargs)

            return Response(results, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TotalBookingsBarAndLineAmountApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            user = request.user
            if user.role.name == 'sales':
                sales_agent_id = user.id 
            else:
                sales_agent_id = request.query_params.get("sales_agent_id", None)
            kwargs = {
                "month": request.query_params.get("month", None),
                "year": request.query_params.get("year", None),
                "sales_agent_id" : sales_agent_id
                
            }
            booking_chart_results = total_booking_chart(**kwargs)
            line_chart_results = admin_or_staff_line_chart(**kwargs)
            result = {
                "booking_chart_result" : booking_chart_results,
                "line_chart_result" : line_chart_results
            }
            return Response(result, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        

class VendorConfirmedBookingAmountPieChartApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            kwargs = {
                "month": request.query_params.get("month", None),
                "year": request.query_params.get("year", None),
                
            }
            result = vendor_booking_pie_chart(**kwargs)
            return Response(result, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )

class VendorAirlineConfirmedBookingBarChartApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            kwargs = {
                "month": request.query_params.get("month", None),
                "year": request.query_params.get("year", None),
                "vendor_id" : request.query_params.get('vendor_id')
                
            }
            result = vendor_airline_barchart(**kwargs)
            
            return Response(result, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        


class SalesPerformanceApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            kwargs = {
                "month": request.query_params.get("month", None),
                "year": request.query_params.get("year", None),
                
            }
            result = sales_performace_table(**kwargs)
            
            return Response(result, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
class SalesPerformanceActiveOrganizationApiView(APIView):
    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            kwargs = {
                "month": request.query_params.get("month"),
                "year": request.query_params.get("year"),
                "sales_id": request.query_params.get("sales_id"),
            }
            data = organization_booking_count(**kwargs)  
            page = int(request.query_params.get('page', 1))  
            page_size = int(request.query_params.get('page_size', 15))  
            start = (page - 1) * page_size
            end = start + page_size
            active_org_paginated = data["active_org"][start:end]
            # inactive_org_paginated = data["inactive_org"][start:end]

            return Response({
                "active_organizations": {
                    "count": len(data["active_org"]),
                    "next": None if len(data["active_org"]) <= end else f"{request.build_absolute_uri()}?module=flight&page={page + 1}&page_size={page_size}",
                    "previous": None if page == 1 else f"{request.build_absolute_uri()}?module=flight&page={page - 1}&page_size={page_size}",
                    "results": active_org_paginated
                }
            }, status=status.HTTP_200_OK)

        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )

class SalesPerformanceInactiveOrganizationApiView(APIView):
    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            kwargs = {
                "month": request.query_params.get("month"),
                "year": request.query_params.get("year"),
                "sales_id": request.query_params.get("sales_id"),
            }
            data = organization_booking_count(**kwargs)  
            page = int(request.query_params.get('page', 1))  
            page_size = int(request.query_params.get('page_size', 15))  
            start = (page - 1) * page_size
            end = start + page_size
            # active_org_paginated = data["active_org"][start:end]
            inactive_org_paginated = data["inactive_org"][start:end]

            return Response({
                "inactive_organizations": {
                    "count": len(data["inactive_org"]),
                    "next": None if len(data["inactive_org"]) <= end else f"{request.build_absolute_uri()}?module=flight&page={page + 1}&page_size={page_size}",
                    "previous": None if page == 1 else f"{request.build_absolute_uri()}?module=flight&page={page - 1}&page_size={page_size}",
                    "results": inactive_org_paginated
                }
            }, status=status.HTTP_200_OK)

        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TotalFailedToRejectedBookingApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            user = request.user
            if user.role.name == 'operations':
                ops_agent_id = user.id
            else:
                ops_agent_id = request.query_params.get("ops_agent_id", None)

            
                
            kwargs = {
                "from_date": request.query_params.get("from_date", None),
                "to_date": request.query_params.get("to_date", None),
                "organization_id": request.query_params.get("organization_id"),

                "ops_agent_id" : ops_agent_id

            }
            results = total_failed_to_rejected_booking(**kwargs)
            return Response(results, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        


class TotalFailedToConfirmedBookingApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            user = request.user
            if user.role.name == 'operations':
                ops_agent_id = user.id
            else:
                ops_agent_id = request.query_params.get("ops_agent_id", None)

            
                
            kwargs = {
                "from_date": request.query_params.get("from_date", None),
                "to_date": request.query_params.get("to_date", None),
                "organization_id": request.query_params.get("organization_id"),
                "ops_agent_id" : ops_agent_id

            }
            results = total_failed_to_confirmed_booking(**kwargs)
            return Response(results, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        

class TotalFailedtoRejectedBookingChartApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):

        module = request.query_params.get("module", None)
        if module == "flight":
            user = request.user
            if user.role.name == 'operations':
                ops_agent_id = user.id
            else:
                ops_agent_id = request.query_params.get("ops_agent_id", None)

            kwargs = {
                "year": request.query_params.get("year", None),
                "month": request.query_params.get("month", None),
                "organization_id": request.query_params.get("organization_id"),
                "ops_agent_id":ops_agent_id
            }
            if not (kwargs.get("year") and kwargs.get("month")):
                return Response(
                    {"message": f"year and month required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                data = total_failed_to_rejected_chart(**kwargs)
                return Response(data, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        

class TotalFailedtoConfirmedBookingChartApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):

        module = request.query_params.get("module", None)
        if module == "flight":
            user = request.user
            if user.role.name == 'operations':
                ops_agent_id = user.id
            else:
                ops_agent_id = request.query_params.get("ops_agent_id", None)

            kwargs = {
                "year": request.query_params.get("year", None),
                "month": request.query_params.get("month", None),
                "organization_id": request.query_params.get("organization_id"),
                "ops_agent_id":ops_agent_id
            }
            if not (kwargs.get("year") and kwargs.get("month")):
                return Response(
                    {"message": f"year and month required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                data = total_failed_to_confirmed_chart(**kwargs)
                return Response(data, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        


class ConfirmedBookingsBarAndLineAmountApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            user = request.user
            
            kwargs = {
                "month": request.query_params.get("month", None),
                "year": request.query_params.get("year", None),
                "vendor_id" : request.query_params.get("vendor_id", None),
                
            }
            confirmed_booking_chart_results = confirmed_booking_chart(**kwargs)
            line_chart_results = confirmed_line_chart(**kwargs)
            result = {
                "booking_chart_result" : confirmed_booking_chart_results,
                "line_chart_result" : line_chart_results
            }
            return Response(result, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        

class FailedAndRejectedBookingsBarAndLineAmountApiView(APIView):

    permission_classes = global_permission_classes
    authentication_classes = global_authentication_classes

    def get(self, request):
        module = request.query_params.get("module", None)
        if module == "flight":
            
            kwargs = {
                "month": request.query_params.get("month", None),
                "year": request.query_params.get("year", None),
                "vendor_id" : request.query_params.get("vendor_id", None)
                
            }
            failed_and_rejected_chart_results = failed_and_rejected_booking_chart(**kwargs)
            failed_rejected_line_chart_results = failed_rejected_line_chart(**kwargs)
            result = {
                "booking_chart_result" : failed_and_rejected_chart_results,
                "line_chart_result" : failed_rejected_line_chart_results
            }
            return Response(result, status=status.HTTP_200_OK)
        elif module == "hotel":
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "module missing or invalid module"},
                status=status.HTTP_400_BAD_REQUEST,
            )