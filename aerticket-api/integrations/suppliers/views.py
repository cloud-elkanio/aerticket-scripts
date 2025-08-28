from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from .serializers import *
from django.shortcuts import get_object_or_404
from typing import Optional,Union
import uuid
from users.models import Organization
from users.permission import HasAPIAccess

# Create your views here.

class LookupSupplierIntegrationView(APIView):
    def get(self, request):
        integration_type = request.query_params.get('integratin_type')
        if not integration_type:
            return Response({"message":"integration_type is missing in query params"},status=status.HTTP_400_BAD_REQUEST)
        lookupintegration_obj = LookupSupplierIntegration.objects.filter(integration_type=integration_type).order_by('name')
        serializer = LookupSupplierIntegrationSerializer(lookupintegration_obj , many= True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class GetSupplierIntegrationType(APIView):
    def get(self, request):
        supplier_obj = LookupSupplierIntegration.objects.values_list('integration_type' , flat=True).distinct()
        return Response({"data":set(list(supplier_obj))}, status=status.HTTP_200_OK)

class SupplierIntegrationView(APIView):
    permission_classes = [HasAPIAccess]
    def post(self, request):
        try:
            name = request.data['name']
            integration_type = request.data['integration_type']
            obj = LookupSupplierIntegration.objects.get(name = name, integration_type=integration_type)
            request.data['lookup_supplier'] = obj.id
            country = request.data.get('country')

            if not country:
                country_instance = Country.objects.all()
                for country in country_instance:
                    request.data['country'] = country.id
                    serializer = SupplierIntegrationSerializer(data = request.data)
                    if self.already_exist(name,country,integration_type):
                        return Response({"message":"Supplier Integration already exist"}, status=status.HTTP_409_CONFLICT)

                    if not serializer.is_valid():
                        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                    serializer.save()
            else:
                serializer = SupplierIntegrationSerializer(data = request.data)
                if self.already_exist(name,country,integration_type):
                    return Response({"message":"Supplier Integration already exist"}, status=status.HTTP_409_CONFLICT)

                if not serializer.is_valid():
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                serializer.save()

            return Response({"message":"Supplier Integration created successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    def already_exist(self,name,country,integration_type):
        return SupplierIntegration.objects.filter(name=name, country=country, integration_type=integration_type).exists()
        
    def get(self, request):
        integration_type = request.query_params.get('integration_type')
        if not integration_type:
            return Response({"message":"integration_type is missing in query params"},status=status.HTTP_400_BAD_REQUEST)
        lookup_supplier_integration_obj = SupplierIntegration.objects.filter(integration_type__icontains=integration_type).order_by('name')
        serializer = SupplierIntegrationGetSerializer(lookup_supplier_integration_obj, many=True)
        return Response({"data":serializer.data}, status=status.HTTP_200_OK)

    def patch(self, request):
        try:
            supplier_integration_id = request.data.get('id')
            if supplier_integration_id is None:
                # custom error
                return Response({'message': 'Supplier Integration ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            supplier_integration_obj = SupplierIntegration.objects.get(id=supplier_integration_id)

            serializer = SupplierIntegrationSerializer(supplier_integration_obj, request.data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            serializer.save()
            return Response({"message": "Supplier Integration updated successfully"}, status=status.HTTP_200_OK)

        except SupplierIntegration.DoesNotExist:
            return Response({'message': 'Supplier Integration with the provided ID does not exist'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({'message': 'Internal server error. Please check server logs for details.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request):
        id = request.query_params.get('id')
        if not id:
            return Response({'error': 'Supplier Integration ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        get_object_or_404(SupplierIntegration, id=id).hard_delete()
        return Response({'message': 'Supplier Integration deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
    
    
class SupplierList(APIView):
    def get(self, request):
        integration_type = request.query_params.get('integration_type')
        search_key = request.query_params.get('search_key')

        if not integration_type:
            return Response({"message": "integration_type is missing in query params"}, status=status.HTTP_400_BAD_REQUEST)

        supplier_integration_obj = SupplierIntegration.objects.filter(
            integration_type__icontains=integration_type
        )

        if search_key:
            supplier_integration_obj = supplier_integration_obj.filter(name__icontains=search_key)

        supplier_integration_obj = supplier_integration_obj.order_by('name')

        serializer = SupplierListSerializer(supplier_integration_obj, many=True)
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)


class AgencyIntegeration(APIView):
    def get(self,request,agency_id:uuid):
        agency, error = self.get_agency(agency_id)
        if error:
            return error
        
        existing_integerations = OrganizationSupplierIntegeration.objects.filter(organization = agency)

        all_integeration_list = SupplierIntegration.objects.filter(country_id=agency.organization_country_id).exclude(id__in=existing_integerations.values_list('supplier_integeration_id', flat=True))
        all_integeration_list_count =len(all_integeration_list)  if len(all_integeration_list) > 0 else None
        
        data = {
            "all_integeration_list":SupplierIntegratingSerializer(all_integeration_list,many=True).data,
            "existing_integerations":OrganizationSupplierIntegerationSerializer(existing_integerations,many=True).data,
            "all_integeration_list_count":all_integeration_list_count
        }
        return Response(data)
    
    def get_agency(self,id)-> Union[Response, Organization] :
        """
        get agency id or return error as Response
        
        Args:
            index(id):the id of the organization 
        
        Returns:
            Obj  : returns object or return ErrorResponse
            
        Raises:
            ValueError : returns error if object not found.
        """
        try:
            agency = Organization.objects.get(id=id)
            return agency, None
        except Organization.DoesNotExist:
            return None ,Response({"message":"the organization does not exists"}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            return None ,Response({"message":f"Internal Server Error {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            

        



class UpdateSupplierStatus(APIView):
    def post(self,request):
        toogle_status = request.data['status']
        supplier_id = request.data['supplier_id']
        agency_id = request.data['agency_id']
        
        try:
            obj = OrganizationSupplierIntegeration.objects.get(supplier_integeration_id=supplier_id,organization_id=agency_id)
            obj.is_enabled = toogle_status
            obj.save()
        except OrganizationSupplierIntegeration.DoesNotExist:
            OrganizationSupplierIntegeration.objects.create(supplier_integeration_id=supplier_id, organization_id=agency_id)
        except Exception as e:
            return Response({"message":e},status=status.HTTP_200_OK)
        return Response({"message":"success"},status=status.HTTP_200_OK)
##
#
#
#