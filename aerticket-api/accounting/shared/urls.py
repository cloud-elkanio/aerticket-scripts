from .views import *
from django.urls import path
from rest_framework.routers import DefaultRouter



router = DefaultRouter()
router.register(r'accounting/shared/commissions', CustomerCommisionViewSet,basename='control1space1panel_agency1space1master')
router.register(r'accounting/shared/payment-filter', PaymentFilterViewSets)

urlpatterns = [
    path('accounting/shared/credit-balance', CreditBalanceView.as_view(), name='credit-balance'),
    path('accounting/shared/organization/balance', OrganizationCreditBalanceView.as_view(), name='accounts_credit1space1updation'),
    
    path('accounting/shared/update-credit-limit', UpdateCreditLImitView.as_view(), name='credit-limit'),
    path('accounting/shared/temporary-credit-limit', SetTemporaryCreditLimitView.as_view(), name='temporary-credit-limit'),
    path('accounting/shared/remove-credit-limit', RemoveTempCreditLimitView.as_view(), name='remove-credit-limit'),
     
    
    path('accounting/shared/update/limit/credit', UpdateLimitCredit.as_view(), name = 'accounts_credit1space1updation_$_PATCH'),
    path('accounting/shared/update/limit/balance-ammount', UpdateBalanceAmmount.as_view(), name='update-credit-limit'),
    path('accounting/shared/organization-detail/<uuid:id>', OrganizationDetailView.as_view(), name='organization-detail'),
    
    path('accounting/shared/organization-detail/',FlightBilling.as_view(), name='flight-biling'),
    
    path('accounting/shared/credit-log/history',CreditLogHistory.as_view(), name='flight-biling'),
    path('accounting/shared/ledger',LedgerReportApiView.as_view(), name='ledger'),
    path('accounting/shared/distributor-agent-fare-adjustment/<uuid:user_id>', DistributorAgentFareAdjustmentRetrieveUpdateView.as_view(), name='distributor-agent-fare-adjustment-detail'),
    path('accounting/shared/distributor-agent-wallet-adjustment/<uuid:user_id>', DistributorWalletAdjustmentRetrieveUpdateView.as_view(), name='distributor-wallet-fare-adjustment-detail'),
    path('accounting/shared/distributor-agent-balance-update/<uuid:user_id>', DistributorBalanceAdjustmentView.as_view(), name='distributor-balance-fare-adjustment-detail'),
    path('accounting/shared/show-recharge-button/', ShowRechargeButton.as_view(), name='distributor-balUpdateLimitCreditance-fare-adjustment-detail'),
    path('accounting/shared/recharge-wallet/', WalletRecharge.as_view(), name='wallet-recharge'),
    path('accounting/shared/payment-update/', PaymentUpdateView.as_view(), name='accounts_payments_update1space1payments_$_PATCH'),
    path('accounting/shared/payment-status-update/', UpdatePaymentStatusView.as_view(), name='payment-status-update'),
    path('accounting/shared/list-distributor-agents/', ListAllDistributorAgent.as_view(), name='list-distributior-agents'),
    path('accounting/shared/booking-id-list/', ListAgentBookingIDs.as_view(), name='booking-id-list'),
    path('accounting/shared/distributor-agent-transaction/',UpdateDistributorTransactionView.as_view(), name='distributor-transaction'),
    path('accounting/shared/distributor-payment-filter', PaymentUpdatesFilterView.as_view(), name='distributor-payment-filter'),
    path('accounting/shared/get-analysis-report', GetAnalysisReport.as_view(), name='get-analysis-report'),
    path('accounting/shared/get-transaction-pdf', GetTransactionPdf.as_view(), name='get-transaction-pdf'),
    path('update/payment/distributor-agent/<uuid:user_id>', UpdatePaymentDistributorAgentView.as_view()),
    path('accounting/shared/pay-now', PayNowApiView.as_view(), name='pay-now'),

    path('accounting/shared/razor-callback/status', RazorCallbackApi.as_view(), name='razor-callback-status'),
    path('accounting/shared/razor-success-url',razorpay_success_url,name='razor-success-url'),
    path('accounting/agent/statement',GetAgentTransactionLog.as_view()),
    # path('accounting/shared/payment-filter',PaymentFilterApiViews.as_view()),
    path('update/credit/limit/easylink/registration', UpdateCreditLImitEasylinkRegistration.as_view(), name='credit-limit'),

    
    



]

urlpatterns+=router.urls