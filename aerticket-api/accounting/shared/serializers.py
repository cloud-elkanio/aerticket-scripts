from .models import *
from rest_framework import serializers
from tools.time_helper import time_converter
from integrations.general.models import Integration
from rest_framework.pagination import PageNumberPagination
import requests
from tools.easy_link.xml_restructure import XMLData

from datetime import datetime
class CustomPagination(PageNumberPagination):
    page_size = 6  # Default page size
    page_size_query_param = 'page_size'  # Allow clients to override the page size
    max_page_size = 100  # Maximum limit
        
class HistorySerializer(serializers.ModelSerializer):
        user = serializers.SerializerMethodField()  # Custom user serialization
        organization = serializers.SerializerMethodField() 
        class Meta:
            model = CreditLog
            fields = "__all__"
            
        
        def get_user(self,obj):
            if obj.user:
                return obj.user.first_name + obj.user.last_name
        
        
        def get_organization(self,obj):
            if obj.user:
                return obj.organization.organization_name
            
            
        

class BaseOrganizationSerializer(serializers.ModelSerializer):
    country_name = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()

    def get_country_name(self, obj):
        if obj.organization_country:
            return obj.organization_country.lookup.country_name
        return None

    def get_type(self, obj):
        if obj.organization_type:
            return obj.organization_type.name
        return None

class OrganizationSerializer(BaseOrganizationSerializer):
    class Meta:
        model = Organization
        fields = ('id','organization_name', 'type', 'state', 'country_name','status')

class OrganizationDetailSerializer(BaseOrganizationSerializer):
    team_members = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        exclude = ('created_at', 'modified_at', 'deleted_at', 'is_deleted', 
                   'organization_country', 'organization_type',"whitelabel")
        
       
    def get_team_members(self, obj):
        team_members = UserDetails.objects.filter(organization=obj)
        return [
            {
                'name': member.get_full_name(),  
                'designation': member.role.name if member.role else None,
                 'last_login': member.last_login 
            }
            for member in team_members
        ]
                
    def get_history(self, obj):
        request = self.context.get('request')
        credit_obj = CreditLog.objects.filter(organization=obj).order_by('-created_at')
        paginator = CustomPagination()
        paginated_data = paginator.paginate_queryset(credit_obj, request)
        serialized_data = HistorySerializer(paginated_data, many=True).data
        return paginator.get_paginated_response(serialized_data).data
    

class CustomerCommisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationFareAdjustment
        fields = ('id','cashback', 'parting_percentage', 'markup', 'cancellation_charges','organization','module')
        
        
    def validate(self, data):
        """
        checking if the data is already present in the table
        """
        organization = data.get('organization')
        is_percentage= data.get('organization')
        module = data.get('module')
        request = self.context.get('request')
        
         
        if not organization:
            raise serializers.ValidationError({'organization_id': 'This field is required.'})

        if request.method == "PATCH":
            return data

        if OrganizationFareAdjustment.objects.filter(organization_id=organization, module=module).exists():
            raise serializers.ValidationError(
                f'The organization has already added markup for module {module}. Please try updating the existing one.'
            )
        
        return data
        
        
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['organization'] = instance.organization.organization_name
        # representation['issued_by'] = instance.issued_by.first_name if instance.issued_by else None
        return representation


class DistributorAgentFareAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DistributorAgentFareAdjustment
        fields = ("cashback","markup","cancellation_charges","parting_percentage","module")
        
        
   
class AgentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DistributorAgentTransaction 
        exclude = ("user","is_deleted","deleted_at","modified_at")
        
    def to_representation(self, instance):
        data =  super().to_representation(instance)
        data['created_at'] = self.epoch_to_custom_format(instance.created_at)
        return data
    
    def epoch_to_custom_format(self, epoch_time):
        date_time = datetime.fromtimestamp(epoch_time)

        day = date_time.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]
        
        # Format: Month day[suffix] Year, hour:minute AM/PM
        return date_time.strftime(f'%b {day}{suffix} %Y %I:%M %p')
    
    
class DistributorAgentWalletAdjustmentSerializer(serializers.ModelSerializer):
    history = serializers.SerializerMethodField()
    class Meta:
        model = DistributorAgentFareAdjustment
        fields = ("available_balance","credit_limit","history") 
        
    def validate(self, data):
        """
        checking if the data is already present in the table
        """
        new_credit_limit = data.get('credit_limit',None)
        request = self.context.get('request')
        user_id = request.parser_context.get('kwargs').get('user_id')
        if request.method == "PATCH":
            distributor_agent = DistributorAgentFareAdjustment.objects.get(user_id=user_id)
            current_credit_limit = distributor_agent.credit_limit
            available_balance = distributor_agent.available_balance
            if (new_credit_limit - current_credit_limit)+available_balance <0:
                raise serializers.ValidationError(f'the user will have a negative balance  the user has to pay you  '
                                                  f'current_credit_limit = {current_credit_limit} new_credit_limit = {new_credit_limit}'
                                                  f'available_balance ={available_balance} new limit will be {(new_credit_limit - current_credit_limit)+available_balance}')
            organization_wallent_ammount_sufficient, organization_balance = self.is_wallet_ammount_applicable(requested_wallet_amount = (new_credit_limit - current_credit_limit)+available_balance,
                                                 country_id = distributor_agent.user.organization.organization_country.id,easy_link_billing_code=distributor_agent.user.organization.easy_link_billing_code)
            if not organization_wallent_ammount_sufficient:
                  raise serializers.ValidationError(f"Your available  balace is {organization_balance}  which is less than the requested amount  {new_credit_limit} ")
              
            data['available_balance'] = (new_credit_limit - current_credit_limit)+available_balance
            DistributorAgentFareAdjustmentLog.objects.create(old_credit_limit=current_credit_limit,old_available_balance=available_balance,new_credit_limit=new_credit_limit,new_available_balance=(new_credit_limit - current_credit_limit)+available_balance)
            DistributorAgentTransaction.objects.create(user=distributor_agent.user,transtransaction_type='credit', amount=(new_credit_limit - current_credit_limit)+available_balance,booking_type='OD Limit/Cash Credit')
        return data
    
    
    def is_wallet_ammount_applicable(self,requested_wallet_amount,country_id,easy_link_billing_code):
        """ return true if organization wallet amount is less than request amount  """
        url,  branch_code,  portal_reference_code = self.get_accounting_software_credentials(country_id) # getting the easy link details for checkinh the organization's wallet
        response = self.get_credit_limit(portal_ref_code=portal_reference_code,billing_code=easy_link_billing_code, base_url = url)
        credit_data = response.data
        try:
            credit_data['F']
        except KeyError as e:
            raise Exception ("esy link account error")
        return float(requested_wallet_amount) < float(credit_data['F']), credit_data['F']
    
    def get_accounting_software_credentials(self, country_id):
        # getting objects 
            try:
                obj = Integration.objects.get(name = "easy-link  backoffice suit",country_id=country_id)
            except Integration.DoesNotExist:
                raise Exception("easy-link  backoffice suit is not configured in  the  portal ")
            except Exception as e:
                raise Exception(str(e))
            
            # getting credentials 
            try:
                data = obj.data[0]
                url = data["url"]
                branch_code = data["branch_code"]
                portal_reference_code = data["portal_reference_code"]
            except KeyError as e:
                raise Exception(f"{obj.name} is not configured correctly missing keys {e} ")
            except Exception as e:
                raise Exception(str(e))
            
            return url,branch_code,portal_reference_code
        
    def get_credit_limit(self,
                             portal_ref_code,
                                billing_code,
                                base_url
                                ):
            url = f"{base_url}/getAvlCreditLimit/?PortalRefCode={portal_ref_code}&sAcCode=&sRefAcCode={billing_code}"
            header = {"Content-Type":"text/plain"}
            response = requests.post(url=url, headers=header)
            return XMLData.get_credit_limit_response(response)
        
        

    
    def get_history(self, obj):
        request = self.context.get('request')
        agent_history = DistributorAgentTransaction.objects.filter(user=obj.user,transtransaction_type='credit').order_by('-created_at')
        total_length = len(agent_history)
        # Apply pagination to the queryset
        paginator = CustomPagination()
        paginated_data = paginator.paginate_queryset(agent_history, request)

        # Serialize the paginated data
        serialized_data = AgentHistorySerializer(paginated_data, many=True).data
        return paginator.get_paginated_response(serialized_data).data
        
    
class PaymentUpdateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = PaymentUpdates
        fields = "__all__"

    # def to_representation(self, instance):
    #     representation = super().to_representation(instance)
    #     representation['status'] = representation.pop('choice')  # Rename 'choice' to 'renamed_field'
    #     return representation

class UserDetailDistributorsSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source='id')

    class Meta:
        model =UserDetails
        fields =('user_id',
                 'first_name',
                 'last_name',
                 'email',
                 'phone_number',
                 'is_email_verified',
                 'is_phone_verified',
                 'address',
                 'is_client_proxy'
                 )
        
class DistributorAgentTransactionSerializer(serializers.ModelSerializer):
    booking_id = serializers.SerializerMethodField()
    class Meta:
        model = DistributorAgentTransaction
        fields = ('id','user','module', 'booking_type','booking_id','amount',"created_at","transtransaction_type")

    def get_booking_id(self, obj):
        # This method retrieves the display_id from the related Booking object
        return obj.booking.display_id if obj.booking else None
    def to_representation(self, instance):
        data =  super().to_representation(instance)
        data['created_at'] = self.epoch_to_custom_format(instance.created_at)
        return data
    def epoch_to_custom_format(self, epoch_time):
        date_time = datetime.fromtimestamp(epoch_time)

        day = date_time.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]
        
        # Format: Month day[suffix] Year, hour:minute AM/PM
        return date_time.strftime(f'%b {day}{suffix} %Y %I:%M %p')
    
    

class PaymentSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Payments
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['account_code'] = instance.agency.organization.easy_link_account_code
        data['paid_by'] = instance.agency.first_name
        data['organization_name'] = instance.agency.organization.organization_name
        data['billing_code'] = instance.agency.organization.easy_link_billing_code
        return data