from .models import *
from rest_framework import serializers
from tools.time_helper import time_converter


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDetails
        fields = "__all__"


class UserDetailSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="id")

    class Meta:
        model = UserDetails
        fields = (
            "user_id",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "is_email_verified",
            "is_phone_verified",
            "address",
            "is_client_proxy",
        )


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = "__all__"


class CountrySerializer(serializers.ModelSerializer):
    country_name = serializers.SerializerMethodField()
    calling_code = serializers.SerializerMethodField()

    class Meta:
        model = Country
        exclude = ("deleted_at", "is_deleted", "created_at", "modified_at")

    def get_country_name(self, obj):
        # Replace 'name' with the actual field or logic that defines the country name
        return obj.lookup.country_name

    def get_calling_code(self, obj):
        return obj.lookup.calling_code


class LookupCountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupCountry
        exclude = ("deleted_at", "is_deleted", "created_at", "modified_at")


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDetails
        exclude = ("deleted_at", "is_deleted", "created_at", "modified_at")


class ListGroupSerializer(serializers.ModelSerializer):
    organization_name = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()

    class Meta:
        model = UserGroup
        fields = ["name", "id","organization_name","role_name","role","is_visible"]
    def get_organization_name(self, obj):
        return obj.organization.organization_name
    def get_role_name(self,obj):
        return obj.role.name

class UserList(serializers.ModelSerializer):
    class Meta:
        model = UserDetails
        exclude = ("created_at", "modified_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.role:
            data["show_fare_button"] = instance.role.name == "distributor_agent"
        return data


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tickets
        exclude = ("created_at", "modified_at", "deleted_at", "is_deleted")


class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupAirports
        exclude = ("is_deleted", "deleted_at", "created_at", "modified_at")


class LookupAirportsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupAirports
        fields = "__all__"


class CountryDefaultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CountryDefault
        fields = ["country_id", "flights", "hotels"]


# class OrganizationSerializer(serializers.ModelSerializer):
#     country_name = serializers.SerializerMethodField()
#     type=serializers.SerializerMethodField()

#     class Meta:
#         model = Organization
#         fields = ('organization_name',"type","state","country_name")

#     def get_country_name(self, obj):
#         if obj.organization_country:
#             return obj.organization_country.lookup.country_name
#         return None

#     def get_type(self, obj):
#         if obj.organization_type:
#             return obj.organization_type.name
#         return None
# class OrganizationDetailSerializer(serializers.ModelSerializer):
#     country_name = serializers.SerializerMethodField()
#     type=serializers.SerializerMethodField()

#     class Meta:
#         model = Organization
#         exclude = ('created_at','modified_at','deleted_at','is_deleted',"organization_country","organization_type")

#     def get_country_name(self, obj):
#         if obj.organization_country:
#             return obj.organization_country.lookup.country_name
#         return None


#     def get_type(self, obj):
#         if obj.organization_type:
#             return obj.organization_type.name
#         return None


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
    phone = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = (
            "id",
            "organization_name",
            "type",
            "state",
            "country_name",
            "status",
            "easy_link_billing_code",
            "phone",
            "email",
            "support_phone",
            "support_email"
        )

    
    def get_user_with_valid_role(self, obj):
        valid_roles = {'agency_owner', 'distributor_owner', 'out_api_owner'}
        return obj.users_details.filter(role__name__in=valid_roles).first()

    def get_phone(self, obj):
        user = self.get_user_with_valid_role(obj)
        return getattr(user, 'phone_number', None)

    def get_email(self, obj):
        user = self.get_user_with_valid_role(obj)
        return getattr(user, 'email', None)
class OrganizationDetailsSerializer(BaseOrganizationSerializer):
    team_members = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        exclude = (
            "created_at",
            "modified_at",
            "deleted_at",
            "is_deleted",
            "organization_country",
            "organization_type",
            "whitelabel",
        )

    def get_team_members(self, obj):
        team_members = UserDetails.objects.filter(organization=obj)
        return [
            {
                "name": member.get_full_name(),
                "designation": member.role.name if member.role else None,
                "last_login": member.last_login,
            }
            for member in team_members
        ]


class OrganizationStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["status"]


class LookupAirlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupAirline
        fields = ["name", "code"]


class OrganizationProfileSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "organization_name",
            "organization_currency",
            "state",
            "organization_country",
            "organization_gst_number",
            "organization_zipcode",
            "address",
            "organization_tax_number",
            "profile_picture",
            "support_email",
            "support_phone",
            # "virtual_ac_no",
        )

    def to_representation(self, instance):
        request = self.context.get("request")
        organization_owner = UserDetails.objects.filter(id=request.user.id,
            organization_id=request.user.organization.id,
        ).first()

        data = super().to_representation(instance)

        data["organization_country"] = Country.objects.get(
            id=instance.organization_country_id
        ).lookup.country_name
        data["first_name"] = organization_owner.first_name
        data["last_name"] = organization_owner.last_name
        data["email"] = organization_owner.email
        data["phone"] = organization_owner.phone_number
        data["user_id"] = organization_owner.id
        data["country_code"] = Country.objects.get(
            id=instance.organization_country_id
        ).lookup.calling_code
        data["dom_markup"] = organization_owner.dom_markup
        data["int_markup"] = organization_owner.int_markup

        return data


class UpdateBranchAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"


class AgencyMasterListSerializer(serializers.ModelSerializer):
    organization_type_name = serializers.SerializerMethodField()
    organization_country_name = serializers.SerializerMethodField()
    created_date = serializers.SerializerMethodField()
    updated_date = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        exclude = (
            "created_at",
            "modified_at",
            "deleted_at",
            "is_deleted",
            "whitelabel",
            "virtual_ac_no",
        )

    def get_organization_type_name(self, obj):
        return obj.organization_type.name if obj.organization_type else None

    def get_organization_country_name(self, obj):
        return (
            obj.organization_country.lookup.country_name
            if obj.organization_country
            else None
        )

    def get_created_date(self, obj):
        standard_date = datetime.fromtimestamp(obj.created_at).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return standard_date

    def get_updated_date(self, obj):
        standard_date = datetime.fromtimestamp(obj.modified_at).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return standard_date


class AgencyMasterUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"

class OutApiDetailGetSerializer(serializers.ModelSerializer):
    easy_link_account_code = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    class Meta:
        model = OutApiDetail
        fields = ("id", "status","easy_link_account_code", "organization_name")
    def get_easy_link_account_code(self,obj):
        easy_link_account_code = obj.organization.easy_link_billing_code
        return easy_link_account_code
    def get_organization_name(self,obj):
        organization_name = obj.organization.organization_name
        return organization_name

class ThemeSerializer(serializers.ModelSerializer):
    organization_name = serializers.SerializerMethodField()
    class Meta:
        model = OrganizationTheme
        exclude = ('is_deleted','deleted_at','created_at','modified_at')
    def get_organization_name(self,obj):
        org_name = obj.organization_id.organization_name
        return org_name
    
class ThemeGetSerializer(serializers.ModelSerializer):
    organization_name = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    class Meta:
        model = OrganizationTheme
        exclude = ('is_deleted','deleted_at','created_at','modified_at')
    def get_organization_name(self,obj):
        org_name = obj.organization_id.organization_name
        return org_name
    def get_profile_picture(self,obj):
        profile_picture = obj.organization_id.profile_picture
        if profile_picture and hasattr(profile_picture, 'url'):
            return profile_picture.url
        return None
    
class ThemeTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupTemplate
        exclude = ('is_deleted','deleted_at','created_at','modified_at')

class LookupThemeSerializer(serializers.ModelSerializer):
    organization_name = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    organization_id  = serializers.SerializerMethodField()
    class Meta:
        model = LookupTheme
        exclude = ('is_deleted','deleted_at','created_at','modified_at')
    def get_organization_name(self,obj):
        org_id = self.context.get("org_id")
        if org_id:
            organization = Organization.objects.filter(id=org_id).first()
            return organization.organization_name if organization else None
        return None
    
    def get_profile_picture(self, obj):
        org_id = self.context.get("org_id")
        if org_id:
            organization = Organization.objects.filter(id=org_id).first()
            if organization and organization.profile_picture:
                profile_picture = organization.profile_picture
                if hasattr(profile_picture, 'url'):
                    return profile_picture.url
        return None
    def get_organization_id(self, obj):
        return self.context.get("org_id")

class UserGroupUnderOrganizationlistSerializer(serializers.ModelSerializer):
    organization_name = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()
    class Meta:
        model = UserGroup
        fields = (
        "id",
        "name",
        "is_visible",
        "role_name",
        "organization_name",
        "role"
    )
    def get_organization_name(self, obj):
        return obj.organization.organization_name if obj.organization else None
    def get_role_name(self, obj):
        return obj.role.name if obj.role else None
    
class WhiteLabelPageSerializer(serializers.ModelSerializer):
    organization_name = serializers.SerializerMethodField()
    class Meta:
        model = WhiteLabelPage
        exclude = ('created_at','modified_at','is_deleted','deleted_at')
    def get_organization_name(self, obj):
        return obj.organization.organization_name if obj.organization else None
class CMSContentViewSerializer(serializers.ModelSerializer):
    organization_name = serializers.SerializerMethodField()
    class Meta:
        model = WhiteLabelPage
        exclude = ('created_at','modified_at','is_deleted','deleted_at')
    def get_organization_name(self, obj):
        return obj.organization.organization_name if obj.organization else None

class OrgWhiteLabelGetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ('id','organization_name','easy_link_billing_code','is_white_label')

class FareManagementViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = FareManagement
        fields ="__all__"

class FareManagementGetSerializer(serializers.ModelSerializer):
    combinations = serializers.SerializerMethodField()
    class Meta:
        model = FareManagement
        fields =('brand_name','combinations')

    def get_combinations(self, obj):
        fares = FareManagement.objects.filter(id = obj.id)
        return[
            {   "id": obj.id,
                "supplier":fare.supplier_id.id,
                "name": fare.supplier_fare_name,
                "position": fare.priority
            }  for fare in fares
        ]
    
# class FareManagementGetSerializer(serializers.ModelSerializer):
#     combinations = serializers.SerializerMethodField()
#     class Meta:
#         model = FareManagement
#         fields =('id','brand_name','combinations')

#     def get_combinations(self, obj):
#         fares = FareManagement.objects.filter(brand_name = obj.brand_name)
#         return[
#             {
#                 "supplier":fare.supplier_id.id,
#                 "name": fare.supplier_fare_name,
#                 "position": fare.priority
#             }  for fare in fares
#         ]