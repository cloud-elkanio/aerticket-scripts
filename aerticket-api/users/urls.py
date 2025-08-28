"""
URL configuration for api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from .views import *
                   
from rest_framework.routers import DefaultRouter




urlpatterns = [
    
    
    path('init', Initialize.as_view()),
    path('verify/user',Login.as_view(), name='verify'),
    path('otp/verify', OtpVerify.as_view(), name='otp'),
    path('without-otp/verify', WithoutOtpVerify.as_view(), name='otp'),
    path('update/password', UpdatePassword.as_view()),
    path('first_time/update/password', FirstTimeUpdatePassword.as_view()),

    path('user/validate', UserValidateTokenGenerateView.as_view()),
    path('user/validate-token',ValidateTokenView.as_view()),
    path('registration', Registration.as_view()),
    path('country',CountryDetailGet.as_view()),    
    
    #gst-verify
    path("verify_gstin/", VerifyGSTIN.as_view(), name="verify_gstin"),
    path("verify_pan/", VerifyPAN.as_view(), name="verify_pan"),

    # user-detail
    path('users/team/detail/<uuid:id>/', UserDetailsView.as_view(), name='user-details'),

    
    # ----team creation-------------------------------------------------------------------------------
    path('get-user',GetUser.as_view()),
    path('user/exist/check', UserExistCheck.as_view()),
    path('team/create',TeamCreate.as_view(), name = 'control1space1panel_role1space1assignment'),
    # path('team/create',TeamCreate.as_view()),
# 
    path('user/toggle-status', ToggleUserStatusView.as_view(), name = 'control1space1panel_role1space1assignment'),
    path('role/suggest',RoleSuggest.as_view()),
    path('show/permission', ShowPermissions.as_view()),
    path('create/group/permission',CreateGroupPermission.as_view(), name = 'control1space1panel_role1space1assignment'),
    path('list/group/name', GroupNames.as_view()),
    path('list/operations', OperationsLists.as_view()),
    # path('update/group/permission',UpdateGroupPermission.as_view()),
    # end- team creation -------------------------------------------------------------------------------
    
    path('ticket',TicketView.as_view()),

    path('lookup_country',LookupCountryCreate.as_view()),
    path('lookup_airport',LookupAirportCreate.as_view()),
    path('lookup-airport-deal-managaement',LookupAirportDealManagement.as_view()),
    path('airport_location',Airport_Location.as_view()),
    path('nearest_airport',NearestAirports.as_view()),
    path('search_airport',SearchAirport.as_view()),
    path('default_values',CountryDefaultCreateView.as_view()),

    #organization
    path('organization',OrganizationListView.as_view(), name = 'control1space1panel_agency1space1master'),
    path('organization/<uuid:id>', OrganizationDetailView.as_view()),
    path('organization/<uuid:id>/status/', OrganizationStatusUpdateView.as_view()),
    path('organization/view/team/', TeamMemebersOrganization.as_view()),
    path('organization/team/user/activate-proxy', ActivateProxy.as_view()),

#
    path('airline', LookupAirlineCreate.as_view()),
    path('user/profile/proxy-status', ClientProxy.as_view()),
    
    path('user/permisions',GetUserPermissions.as_view()),
    path('user/organization/profile',OrganizationProfile.as_view()),
    path('user/integerate/id',InternalidGenerate.as_view()),

    path('update/easylink/billing/account',UpdateLinkForOrganization.as_view()),
    path('branch/allocation/dropdown',EasyLinkBranchAllocationDropDown.as_view()),
    
    path('branch/allocation',BranchAllocationView.as_view()),
    path('update/already/existing/finance/operation',UpdateAlreadyExisting_Finanace_And_Operation.as_view()), 
    path('list/agency/master',AgencyMasterListAPI.as_view()),
    path('list/sales/agent',GetSalesAgentList.as_view()),
    path('update/agency/master',UpdateAgencyMaster.as_view(), name = 'control1space1panel_agency1space1master_$_PATCH'),

    path('resend/otp',ResendOtpView.as_view()),

    path('markup/view',GetMarkupView.as_view()),
    path('create/excel',CreateExcelTemplateForTeamCreate.as_view()),
    

    path('list/outapi',ListOutApiView.as_view(),name = 'control1space1panel_out1hyphen1API1space1management'),
    path('outapi/status/change',OutApiStatusChange.as_view(), name = 'control1space1panel_out1hyphen1API1space1management'),
    path('generate/accesstoken',CreateAccesToken.as_view()),
    path('accesstoken/detail',ListAccesToken.as_view()),

    path('user/name',Testgetuserusingorg.as_view()), #for test
    path('theme/detail',ThemeView.as_view()),
    path('theme/template/list',GetThemeTemplate.as_view()),
    
    path('user/group/permission',UserGroupPermissionListAndUpdate.as_view(), name = 'control1space1panel_role1space1assignment_$_PATCH'),
    path('update/team/member',UpdateTeamMember.as_view(), name = 'control1space1panel_role1space1assignment_$_PATCH'),
    path('organization/user/group/list',UserGroupListUnderOrganization.as_view()),
    path('user/group/status/change',UserGroupIsActiveChangeAPI.as_view()),

    path('organization/whitelabel/status',GetWhiteLabelStatus.as_view()),
    path('organization/whitelabel/change/status',ChangeOrgWhiteLabelStatus.as_view()),
    path('organization/whitelabel',WhiteLabelPagesView.as_view()),
    path('organization/whitelabel/<uuid:id>/', WhiteLabelPagesView.as_view()),  # For DELETE
    path('organization/whitelabel/host', HostView.as_view()),
    path('organization/cms/content', CMSContentView.as_view()),

    path('fare/management', FareManagementView.as_view()),
    path('fare/management/<str:brand_name>', FareManagementView.as_view()),

]