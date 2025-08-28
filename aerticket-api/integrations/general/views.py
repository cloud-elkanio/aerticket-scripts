from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from .serializers import *
from django.shortcuts import get_object_or_404

# Create your views here.
class LookUpIntegrationDetails(APIView):
    permission_classes = []
    def get(self, request):
        lookupintegration_obj = LookupIntegration.objects.all().order_by('name')
        serializer = LookupIntegrationSerializer(lookupintegration_obj , many= True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class IntegrationView(APIView):

    permission_classes = []
    def post(self, request):
        try:
            name = request.data['name']
            country = request.data.get("country_name",None)
            apply_all_country= request.data.get("apply_all_country_status",None)
            
            if country == None and apply_all_country == None:
                return Response({"message":"Please pass country id"}, status=status.HTTP_400_BAD_REQUEST)
            if apply_all_country:
                country_list = Country.objects.all()
            else:
                country_list = [Country.objects.get(id=country)]
            for country in country_list:
                obj = LookupIntegration.objects.get(name = name)
                
                is_integeration_exist = Integration.objects.filter(lookup_integration_id = obj.id, country_id=country.id)
                if is_integeration_exist:
                    existing_integeration  = is_integeration_exist.first()
                    serializer = IntegrationSerializer(existing_integeration,data = request.data,partial=True)
                else:
                    request.data['lookup_integration'] = obj.id
                    request.data['country'] = country.id
                    serializer = IntegrationSerializer(data = request.data)
                if not serializer.is_valid():
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                serializer.save()
            return Response({"message":"Integration created successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"message": f"Error Occured {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def get(self, request):
        country = request.query_params.get("country",None)
        
        lookupintegration_obj = Integration.objects.all().order_by('name')
        if country:
            lookupintegration_obj = lookupintegration_obj.filter(country_id=country)
        serializer = IntegrationGetSerializer(lookupintegration_obj, many=True)
        return Response({"data":serializer.data}, status=status.HTTP_200_OK)
    
    def patch(self, request):
        try:
            integration_id = request.data.get('id')
            if integration_id is None:
                return Response({'message': 'Integration ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            integration_obj = Integration.objects.get(id=integration_id)

            serializer = IntegrationSerializer(integration_obj, request.data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            serializer.save()
            return Response({"message": "Integration updated successfully"}, status=status.HTTP_200_OK)

        except Integration.DoesNotExist:
            return Response({'message': 'Integration with the provided ID does not exist'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({'message': 'Internal server error. Please check server logs for details.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request):
        id = request.query_params.get('id')
        if not id:
            return Response({'error': 'Integration ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        get_object_or_404(Integration, id=id).hard_delete()
        return Response({'message': 'Integration deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
