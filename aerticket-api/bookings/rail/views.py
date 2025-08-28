from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import RailOrganizationDetails
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from users.models import UserDetails
from rest_framework import generics, filters
from .serializers import RailOrganizationDetailsSerializer, UpdateAgentIrctcSerializer
from .pagination import RailOrganizationDetailsPagination

class CreateRequest(APIView):
    permission_classes=[IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    def post(self, request, *args, **kwargs):
        # Extract required fields from the request payload
        data = request.data
        required_fields = [
            'agency_name', 'email', 'pan', 'dob', 'address', 
            'landmark', 'country', 'state', 'city', 'pincode'
        ]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return Response(
                {"error": f"Missing fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_id = request.user.id
        user =  UserDetails.objects.filter(id=user_id ).first()
        organization = user.organization
        # Validate and convert pincode to integer
        try:
            pincode = int(data.get('pincode'))
        except (TypeError, ValueError):
            return Response(
                {"error": "Invalid pincode value."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if RailOrganizationDetails.objects.filter(organization=organization).exists():
            return Response(
                {"error": "Rail Application Form previously submitted for this organization."},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Create the RailOrganizationDetails record.
        rail_org = RailOrganizationDetails.objects.create(
            organization=organization,
            agency_name=data.get('agency_name'),
            email=data.get('email'),
            pan=data.get('pan'),
            dob=data.get('dob'),
            address=data.get('address'),
            landmark=data.get('landmark'),
            country=data.get('country'),
            state=data.get('state'),
            city=data.get('city'),
            pincode=pincode,
            created_by=user,
            updated_by=user,
            agent_id='',    
            irctc_id='',    
            is_active=False,  # Explicitly set inactive
            status="Pending"  # Set the status to Pending
        )
        return Response(
            {"message": "Rail Application Form submitted successfully", "id": rail_org.id},
            status=status.HTTP_201_CREATED
        )


class RailOrganizationDetailsList(generics.ListAPIView):
    queryset = RailOrganizationDetails.objects.all()
    serializer_class = RailOrganizationDetailsSerializer
    pagination_class = RailOrganizationDetailsPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ['agency_name', 'organization__easy_link_billing_code']
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]


class UpdateAgentIrctcAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, pk):
        try:
            rail_org = RailOrganizationDetails.objects.get(id=pk)
        except RailOrganizationDetails.DoesNotExist:
            return Response({'detail': 'RailOrganizationDetails not found.'}, status=status.HTTP_404_NOT_FOUND)


        serializer = UpdateAgentIrctcSerializer(rail_org, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(status="Approved", is_active=True)
            return Response({"status":True}, status=status.HTTP_200_OK)
        return Response({"status":False}, status=status.HTTP_400_BAD_REQUEST)