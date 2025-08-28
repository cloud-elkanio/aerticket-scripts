
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

class HealthView(APIView):
    permission_classes = []
    def post(self, request):
        data ={"sample":"data"}
        return Response({"success":True,"data":data}, status=status.HTTP_200_OK),

    def get(self, request):
        data ={"sample":"data get"}
        return Response({"success":True,"data":data}, status=status.HTTP_200_OK),