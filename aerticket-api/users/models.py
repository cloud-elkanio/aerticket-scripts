# from django.db import models
# our own db models implementing soft delete

import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from tools.db.models import  SoftDeleteModel  # our own db models implementing soft delete
from django.utils import timezone
import time
from django.contrib.postgres.fields import ArrayField
import random

AbstractUser._meta.get_field('username').null = True


class LookupOrganizationTypes(SoftDeleteModel):
    ORGANIZATION_CHOICES = (
        ("master","master"),
        ("agency","agency"),
        ("distributor","distributor"),
        ("enterprises","enterprises"),
        ("out_api","out_api"),
        ("supplier","supplier")
    )
    name = models.CharField(max_length=500, choices=ORGANIZATION_CHOICES)



    
    
    def __str__(self):
        return str(self.name)

    class Meta:
        db_table = 'lookup_organization_types'
        ordering = ['-created_at']

class LookupPermission(SoftDeleteModel):
    name = models.CharField(max_length=200)
    # flight
    flight_create = models.BooleanField(default=False)
    flight_view = models.BooleanField(default=False)
    flight_edit = models.BooleanField(default=False)
    flight_delete = models.BooleanField(default=False)


    # hotel 
    hotel_create = models.BooleanField(default=False)
    hotel_view = models.BooleanField(default=False)
    hotel_edit = models.BooleanField(default=False)
    hotel_delete = models.BooleanField(default=False)

    #hotel -search
    hotel_search_create = models.BooleanField(default=False)
    hotel_search_view = models.BooleanField(default=False)
    hotel_search_edit = models.BooleanField(default=False)
    hotel_search_delete = models.BooleanField(default=False)


    #hotel -booking history
    hotel_booking1space1history_create = models.BooleanField(default=False)
    hotel_booking1space1history_view = models.BooleanField(default=False)
    hotel_booking1space1history_edit = models.BooleanField(default=False)
    hotel_booking1space1history_delete = models.BooleanField(default=False)

    #hotel -queues
    hotel_queues_create = models.BooleanField(default=False)
    hotel_queues_view = models.BooleanField(default=False)
    hotel_queues_edit = models.BooleanField(default=False)
    hotel_queues_delete = models.BooleanField(default=False)


    #hotel -queues -failed bookings
    hotel_queues_failed1space1bookings_create = models.BooleanField(default=False)
    hotel_queues_failed1space1bookings_view = models.BooleanField(default=False)
    hotel_queues_failed1space1bookings_edit = models.BooleanField(default=False)
    hotel_queues_failed1space1bookings_delete = models.BooleanField(default=False)

    # holidays
    holidays_create = models.BooleanField(default=False)
    holidays_view = models.BooleanField(default=False)
    holidays_edit = models.BooleanField(default=False)
    holidays_delete = models.BooleanField(default=False)

    #visa 
    visa_create = models.BooleanField(default=False)
    visa_view = models.BooleanField(default=False)
    visa_edit = models.BooleanField(default=False)
    visa_delete = models.BooleanField(default=False)

    #bus
    bus_create = models.BooleanField(default=False)
    bus_view = models.BooleanField(default=False)
    bus_edit = models.BooleanField(default=False)
    bus_delete = models.BooleanField(default=False)

    #cab12 
    cab_create = models.BooleanField(default=False)
    cab_view = models.BooleanField(default=False)
    cab_edit = models.BooleanField(default=False)
    cab_delete = models.BooleanField(default=False)

    #insurance
    insurance_create = models.BooleanField(default=False)
    insurance_view = models.BooleanField(default=False)
    insurance_edit = models.BooleanField(default=False)
    insurance_delete = models.BooleanField(default=False)

    #accounts
    accounts_create = models.BooleanField(default=False)
    accounts_view = models.BooleanField(default=False)
    accounts_edit = models.BooleanField(default=False)
    accounts_delete = models.BooleanField(default=False)

    #accounts -payments
    accounts_payments_create = models.BooleanField(default=False)
    accounts_payments_view = models.BooleanField(default=False)
    accounts_payments_edit = models.BooleanField(default=False)
    accounts_payments_delete = models.BooleanField(default=False)
    
    #accounts -payments -update payments 
    accounts_payments_update1space1payments_create = models.BooleanField(default=False)
    accounts_payments_update1space1payments_view = models.BooleanField(default=False)
    accounts_payments_update1space1payments_edit = models.BooleanField(default=False)
    accounts_payments_update1space1payments_delete = models.BooleanField(default=False)


    #accounts -payments -payment history 
    accounts_payments_payment1space1history_create = models.BooleanField(default=False)
    accounts_payments_payment1space1history_view = models.BooleanField(default=False)
    accounts_payments_payment1space1history_edit = models.BooleanField(default=False)
    accounts_payments_payment1space1history_delete = models.BooleanField(default=False)

    #accounts - credit notes
    accounts_credit1space1notes_create= models.BooleanField(default=False)
    accounts_credit1space1notes_view = models.BooleanField(default=False)
    accounts_credit1space1notes_edit = models.BooleanField(default=False)
    accounts_credit1space1notes_delete = models.BooleanField(default=False)

    #accounts - invoices
    accounts_invoices_create= models.BooleanField(default=False)
    accounts_invoices_view = models.BooleanField(default=False)
    accounts_invoices_edit = models.BooleanField(default=False)
    accounts_invoices_delete = models.BooleanField(default=False)

    #accounts - ledger & statement
    accounts_ledger1space1and1space1statement_create= models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_view = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_edit = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_delete = models.BooleanField(default=False)

    #accounts - ledger & statement - ledger
    accounts_ledger1space1and1space1statement_ledger_create= models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_ledger_view = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_ledger_edit = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_ledger_delete = models.BooleanField(default=False)

    #accounts - ledger & statement - statement
    accounts_ledger1space1and1space1statement_statement_create= models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_statement_view = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_statement_edit = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_statement_delete = models.BooleanField(default=False)


    #accounts - billing
    accounts_billing_create= models.BooleanField(default=False)
    accounts_billing_view = models.BooleanField(default=False)
    accounts_billing_edit = models.BooleanField(default=False)
    accounts_billing_delete = models.BooleanField(default=False)


    #accounts - credit updation
    accounts_credit1space1updation_create= models.BooleanField(default=False)
    accounts_credit1space1updation_view = models.BooleanField(default=False)
    accounts_credit1space1updation_edit = models.BooleanField(default=False)
    accounts_credit1space1updation_delete = models.BooleanField(default=False)

    #operations
    operations_create = models.BooleanField(default=False)
    operations_view = models.BooleanField(default=False)
    operations_edit = models.BooleanField(default=False)
    operations_delete = models.BooleanField(default=False)

    #operations -import & pnr
    operations_import1space1pnr_create = models.BooleanField(default=False)
    operations_import1space1pnr_view = models.BooleanField(default=False)
    operations_import1space1pnr_edit = models.BooleanField(default=False)
    operations_import1space1pnr_delete = models.BooleanField(default=False)

    #operations -visa queues
    operations_visa1space1queues_create = models.BooleanField(default=False)
    operations_visa1space1queues_view = models.BooleanField(default=False)
    operations_visa1space1queues_edit = models.BooleanField(default=False)
    operations_visa1space1queues_delete = models.BooleanField(default=False)


    #operations -holidays queues
    operations_holidays1space1queues_create = models.BooleanField(default=False)
    operations_holidays1space1queues_view = models.BooleanField(default=False)
    operations_holidays1space1queues_edit = models.BooleanField(default=False)
    operations_holidays1space1queues_delete = models.BooleanField(default=False)
    
    
    #operations -client proxy
    operations_client1space1proxy_create = models.BooleanField(default=False)
    operations_client1space1proxy_view = models.BooleanField(default=False)
    operations_client1space1proxy_edit = models.BooleanField(default=False)
    operations_client1space1proxy_delete = models.BooleanField(default=False)


    #control panel
    control1space1panel_create = models.BooleanField(default=False)
    control1space1panel_view = models.BooleanField(default=False)
    control1space1panel_edit = models.BooleanField(default=False)
    control1space1panel_delete = models.BooleanField(default=False)


    #control panel -agency master
    control1space1panel_agency1space1master_create = models.BooleanField(default=False)
    control1space1panel_agency1space1master_view = models.BooleanField(default=False)
    control1space1panel_agency1space1master_edit = models.BooleanField(default=False)
    control1space1panel_agency1space1master_delete = models.BooleanField(default=False)


    #control panel -role assignment
    control1space1panel_role1space1assignment_create = models.BooleanField(default=False)
    control1space1panel_role1space1assignment_view = models.BooleanField(default=False)
    control1space1panel_role1space1assignment_edit = models.BooleanField(default=False)
    control1space1panel_role1space1assignment_delete = models.BooleanField(default=False)


    #control panel - whitelabeling
    control1space1panel_whitelabeling_create = models.BooleanField(default=False)
    control1space1panel_whitelabeling_view = models.BooleanField(default=False)
    control1space1panel_whitelabeling_edit = models.BooleanField(default=False)
    control1space1panel_whitelabeling_delete = models.BooleanField(default=False)


    #control panel - supplier
    control1space1panel_supplier_create = models.BooleanField(default=False)
    control1space1panel_supplier_view = models.BooleanField(default=False)
    control1space1panel_supplier_edit = models.BooleanField(default=False)
    control1space1panel_supplier_delete = models.BooleanField(default=False)


    #control panel - supplier -flights fixed fares
    control1space1panel_supplier_flights1space1fixed1space1fares_create = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_create')
    control1space1panel_supplier_flights1space1fixed1space1fares_view = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_view')
    control1space1panel_supplier_flights1space1fixed1space1fares_edit = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_edit')
    control1space1panel_supplier_flights1space1fixed1space1fares_delete = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_delete')


    #control panel - supplier - hotels products
    control1space1panel_supplier_hotels1space1products_create = models.BooleanField(default=False)
    control1space1panel_supplier_hotels1space1products_view = models.BooleanField(default=False)
    control1space1panel_supplier_hotels1space1products_edit = models.BooleanField(default=False)
    control1space1panel_supplier_hotels1space1products_delete = models.BooleanField(default=False)


    #control panel - approvals
    control1space1panel_approvals_create = models.BooleanField(default=False)
    control1space1panel_approvals_view = models.BooleanField(default=False)
    control1space1panel_approvals_edit = models.BooleanField(default=False)
    control1space1panel_approvals_delete = models.BooleanField(default=False)


    #control panel - approvals -fd fares
    control1space1panel_approvals_fd1space1fares_create = models.BooleanField(default=False)
    control1space1panel_approvals_fd1space1fares_view = models.BooleanField(default=False)
    control1space1panel_approvals_fd1space1fares_edit = models.BooleanField(default=False)
    control1space1panel_approvals_fd1space1fares_delete = models.BooleanField(default=False)


    #control panel - approvals -holidays
    control1space1panel_approvals_holidays_create = models.BooleanField(default=False)
    control1space1panel_approvals_holidays_view = models.BooleanField(default=False)
    control1space1panel_approvals_holidays_edit = models.BooleanField(default=False)
    control1space1panel_approvals_holidays_delete = models.BooleanField(default=False)


    #control panel - approvals -hotels
    control1space1panel_approvals_hotels_create = models.BooleanField(default=False)
    control1space1panel_approvals_hotels_view = models.BooleanField(default=False)
    control1space1panel_approvals_hotels_edit = models.BooleanField(default=False)
    control1space1panel_approvals_hotels_delete = models.BooleanField(default=False)


    #reports 
    reports_create = models.BooleanField(default=False)
    reports_view = models.BooleanField(default=False)
    reports_edit = models.BooleanField(default=False)
    reports_delete = models.BooleanField(default=False)

    #reports -agency productivity
    reports_agency1space1productivity_create = models.BooleanField(default=False)
    reports_agency1space1productivity_view = models.BooleanField(default=False)
    reports_agency1space1productivity_edit = models.BooleanField(default=False)
    reports_agency1space1productivity_delete = models.BooleanField(default=False)


    #reports -staff productivity
    reports_staff1space1productivity_create = models.BooleanField(default=False)
    reports_staff1space1productivity_view = models.BooleanField(default=False)
    reports_staff1space1productivity_edit = models.BooleanField(default=False)
    reports_staff1space1productivity_delete = models.BooleanField(default=False)

    #admin panel  we are giving 1space1 for normal space eg: admin1space1panel--> admin panel 
    admin1space1panel_create = models.BooleanField(default=False)
    admin1space1panel_view = models.BooleanField(default=False)
    admin1space1panel_edit = models.BooleanField(default=False)
    admin1space1panel_delete = models.BooleanField(default=False)

    #admin panel -visa 
    admin1space1panel_visa_create = models.BooleanField(default=False)
    admin1space1panel_visa_view = models.BooleanField(default=False)
    admin1space1panel_visa_edit = models.BooleanField(default=False)
    admin1space1panel_visa_delete = models.BooleanField(default=False)

    # admin panel -holiday
    admin1space1panel_holiday_create = models.BooleanField(default=False)
    admin1space1panel_holiday_view = models.BooleanField(default=False)
    admin1space1panel_holiday_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_delete = models.BooleanField(default=False)


    # admin panel -holiday product
    admin1space1panel_holiday_product_create = models.BooleanField(default=False)
    admin1space1panel_holiday_product_view = models.BooleanField(default=False)
    admin1space1panel_holiday_product_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_product_delete = models.BooleanField(default=False)


    #admin panel - holiday theme
    admin1space1panel_holiday_theme_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_theme_create = models.BooleanField(default=False)
    admin1space1panel_holiday_theme_delete = models.BooleanField(default=False)
    admin1space1panel_holiday_theme_view = models.BooleanField(default=False)


    # api management

    admin1space1panel_api1space1management_create = models.BooleanField(default=False)
    admin1space1panel_api1space1management_view = models.BooleanField(default=False)
    admin1space1panel_api1space1management_edit = models.BooleanField(default=False)
    admin1space1panel_api1space1management_delete = models.BooleanField(default=False)
    

    # communication

    admin1space1panel_communication_create = models.BooleanField(default=False)
    admin1space1panel_communication_view = models.BooleanField(default=False)
    admin1space1panel_communication_edit = models.BooleanField(default=False)
    admin1space1panel_communication_delete = models.BooleanField(default=False)


    #general

    admin1space1panel_general1space1integeration_create = models.BooleanField(default=False)
    admin1space1panel_general1space1integeration_view = models.BooleanField(default=False)
    admin1space1panel_general1space1integeration_edit = models.BooleanField(default=False)
    admin1space1panel_general1space1integeration_delete = models.BooleanField(default=False)

    
    #admin panel - supplier deal manager
    admin1space1panel_supplier1space1deal1space1manager_create = models.BooleanField(default=False)
    admin1space1panel_supplier1space1deal1space1manager_view = models.BooleanField(default=False)
    admin1space1panel_supplier1space1deal1space1manager_edit = models.BooleanField(default=False)
    admin1space1panel_supplier1space1deal1space1manager_delete = models.BooleanField(default=False)


    #     #admin panel - template
    admin1space1panel_template_create = models.BooleanField(default=False)
    admin1space1panel_template_view = models.BooleanField(default=False)
    admin1space1panel_template_edit = models.BooleanField(default=False)
    admin1space1panel_template_delete = models.BooleanField(default=False)


    # admin panel -holiday favourites
    admin1space1panel_holiday_favourites_create = models.BooleanField(default=False)
    admin1space1panel_holiday_favourites_view = models.BooleanField(default=False)
    admin1space1panel_holiday_favourites_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_favourites_delete = models.BooleanField(default=False)

    # admin panel -visa favourites
    admin1space1panel_visa_favourites_create = models.BooleanField(default=False)
    admin1space1panel_visa_favourites_view = models.BooleanField(default=False)
    admin1space1panel_visa_favourites_edit = models.BooleanField(default=False)
    admin1space1panel_visa_favourites_delete = models.BooleanField(default=False)
    
    
    admin1space1panel_visa_products_create = models.BooleanField(default=False)
    admin1space1panel_visa_products_view = models.BooleanField(default=False)
    admin1space1panel_visa_products_edit = models.BooleanField(default=False)
    admin1space1panel_visa_products_delete = models.BooleanField(default=False)
    
    admin1space1panel_visa_category_create = models.BooleanField(default=False)
    admin1space1panel_visa_category_view = models.BooleanField(default=False)
    admin1space1panel_visa_category_edit = models.BooleanField(default=False)
    admin1space1panel_visa_category_delete = models.BooleanField(default=False)
    
    
    admin1space1panel_visa_type_create = models.BooleanField(default=False)
    admin1space1panel_visa_type_view = models.BooleanField(default=False)
    admin1space1panel_visa_type_edit = models.BooleanField(default=False)
    admin1space1panel_visa_type_delete = models.BooleanField(default=False)

    #flight -queues
    flight_queues_create = models.BooleanField(default=False)
    flight_queues_view = models.BooleanField(default=False)
    flight_queues_edit = models.BooleanField(default=False)
    flight_queues_delete = models.BooleanField(default=False)


    #flight -queues -failed bookings
    flight_queues_failed1space1bookings_create = models.BooleanField(default=False)
    flight_queues_failed1space1bookings_view = models.BooleanField(default=False)
    flight_queues_failed1space1bookings_edit = models.BooleanField(default=False)
    flight_queues_failed1space1bookings_delete = models.BooleanField(default=False)

    #flight -queues -hold bookings
    flight_queues_hold1space1bookings_create = models.BooleanField(default=False)
    flight_queues_hold1space1bookings_view = models.BooleanField(default=False)
    flight_queues_hold1space1bookings_edit = models.BooleanField(default=False)
    flight_queues_hold1space1bookings_delete = models.BooleanField(default=False)


    #flight -queues -passenger calendar
    flight_queues_passenger1space1calender_create = models.BooleanField(default=False)
    flight_queues_passenger1space1calender_view = models.BooleanField(default=False)
    flight_queues_passenger1space1calender_edit = models.BooleanField(default=False)
    flight_queues_passenger1space1calender_delete = models.BooleanField(default=False)


    #flight -booking history
    flight_booking1space1history_create = models.BooleanField(default=False)
    flight_booking1space1history_view = models.BooleanField(default=False)
    flight_booking1space1history_edit = models.BooleanField(default=False)
    flight_booking1space1history_delete = models.BooleanField(default=False)
    
    #flight -search
    flight_search_create = models.BooleanField(default=False)
    flight_search_view = models.BooleanField(default=False)
    flight_search_edit = models.BooleanField(default=False)
    flight_search_delete = models.BooleanField(default=False)


    #accounts -branch allocation
    accounts_branch1space1allocation_create = models.BooleanField(default=False)
    accounts_branch1space1allocation_view = models.BooleanField(default=False)
    accounts_branch1space1allocation_edit = models.BooleanField(default=False)
    accounts_branch1space1allocation_delete = models.BooleanField(default=False)

   #flight -queues -cancelled bookings
    flight_queues_cancelled1space1bookings_create = models.BooleanField(default=False)
    flight_queues_cancelled1space1bookings_view = models.BooleanField(default=False)
    flight_queues_cancelled1space1bookings_edit = models.BooleanField(default=False)
    flight_queues_cancelled1space1bookings_delete = models.BooleanField(default=False)


    #admin panel - customer deal manager
    admin1space1panel_customer1space1deal1space1manager_create = models.BooleanField(default=False)
    admin1space1panel_customer1space1deal1space1manager_view = models.BooleanField(default=False)
    admin1space1panel_customer1space1deal1space1manager_edit = models.BooleanField(default=False)
    admin1space1panel_customer1space1deal1space1manager_delete = models.BooleanField(default=False)

    #accounts -offline & ticketing
    accounts_offline1space1ticketing_create = models.BooleanField(default=False)
    accounts_offline1space1ticketing_view = models.BooleanField(default=False)
    accounts_offline1space1ticketing_edit = models.BooleanField(default=False)
    accounts_offline1space1ticketing_delete = models .BooleanField(default=False)

    #holidays -search
    holidays_search_create = models.BooleanField(default=False)
    holidays_search_view = models.BooleanField(default=False)
    holidays_search_edit = models.BooleanField(default=False)
    holidays_search_delete = models.BooleanField(default=False)

    #holidays -enquiry history
    holidays_enquiry1space1history_create = models.BooleanField(default=False)
    holidays_enquiry1space1history_view = models.BooleanField(default=False)
    holidays_enquiry1space1history_edit = models.BooleanField(default=False)
    holidays_enquiry1space1history_delete = models.BooleanField(default=False)

        #visa -search
    visa_search_create = models.BooleanField(default=False)
    visa_search_view = models.BooleanField(default=False)
    visa_search_edit = models.BooleanField(default=False)
    visa_search_delete = models.BooleanField(default=False)

    #visa -enquiry history
    visa_enquiry1space1history_create = models.BooleanField(default=False)
    visa_enquiry1space1history_view = models.BooleanField(default=False)
    visa_enquiry1space1history_edit = models.BooleanField(default=False)
    visa_enquiry1space1history_delete = models.BooleanField(default=False)

    #accounts - ledger & statement - agent statement
    accounts_ledger1space1and1space1statement_agent1space1statement_create= models.BooleanField(default=False,db_column='agent_statement_create')
    accounts_ledger1space1and1space1statement_agent1space1statement_view = models.BooleanField(default=False,db_column='agent_statement_view')
    accounts_ledger1space1and1space1statement_agent1space1statement_edit = models.BooleanField(default=False,db_column='agent_statement_edit')
    accounts_ledger1space1and1space1statement_agent1space1statement_delete = models.BooleanField(default=False,db_column='agent_statement_delete')

    #accounts - credit notes own 
    accounts_credit1space1notes_own_create= models.BooleanField(default=False)
    accounts_credit1space1notes_own_view = models.BooleanField(default=False)
    accounts_credit1space1notes_own_edit = models.BooleanField(default=False)
    accounts_credit1space1notes_own_delete = models.BooleanField(default=False)


    #accounts - credit notes agent 
    accounts_credit1space1notes_agent_create= models.BooleanField(default=False)
    accounts_credit1space1notes_agent_view = models.BooleanField(default=False)
    accounts_credit1space1notes_agent_edit = models.BooleanField(default=False)
    accounts_credit1space1notes_agent_delete = models.BooleanField(default=False)

    #reports -sales performance
    reports_sales1space1performance_create = models.BooleanField(default=False)
    reports_sales1space1performance_view = models.BooleanField(default=False)
    reports_sales1space1performance_edit = models.BooleanField(default=False)
    reports_sales1space1performance_delete = models.BooleanField(default=False)

    #control panel - outapi management
    control1space1panel_out1hyphen1API1space1management_create = models.BooleanField(default=False)
    control1space1panel_out1hyphen1API1space1management_view = models.BooleanField(default=False)
    control1space1panel_out1hyphen1API1space1management_edit = models.BooleanField(default=False)
    control1space1panel_out1hyphen1API1space1management_delete = models.BooleanField(default=False)

    #reports -user journey tracker
    reports_user1space1journey1space1tracker_create = models.BooleanField(default=False)
    reports_user1space1journey1space1tracker_view = models.BooleanField(default=False)
    reports_user1space1journey1space1tracker_edit = models.BooleanField(default=False)
    reports_user1space1journey1space1tracker_delete = models.BooleanField(default=False)

    #reports - finance team performance
    reports_finance1space1team1space1performance_create = models.BooleanField(default=False)
    reports_finance1space1team1space1performance_view = models.BooleanField(default=False)
    reports_finance1space1team1space1performance_edit = models.BooleanField(default=False)
    reports_finance1space1team1space1performance_delete = models.BooleanField(default=False)

    #flight -queues -others
    flight_queues_others_create = models.BooleanField(default=False)
    flight_queues_others_view = models.BooleanField(default=False)
    flight_queues_others_edit = models.BooleanField(default=False)
    flight_queues_others_delete = models.BooleanField(default=False)

    #reports -operation performance 
    reports_operation1space1performance_create = models.BooleanField(default=False)
    reports_operation1space1performance_view = models.BooleanField(default=False)
    reports_operation1space1performance_edit = models.BooleanField(default=False)
    reports_operation1space1performance_delete = models.BooleanField(default=False)

    #control panel - whitelabel management
    control1space1panel_whitelabel1space1management_create = models.BooleanField(default=False)
    control1space1panel_whitelabel1space1management_view = models.BooleanField(default=False)
    control1space1panel_whitelabel1space1management_edit = models.BooleanField(default=False)
    control1space1panel_whitelabel1space1management_delete = models.BooleanField(default=False)

    #Transfers 
    transfers_create = models.BooleanField(default=False)
    transfers_view = models.BooleanField(default=False)
    transfers_edit = models.BooleanField(default=False)
    transfers_delete = models.BooleanField(default=False)

    #transfers -queues
    transfers_queues_create = models.BooleanField(default=False)
    transfers_queues_view = models.BooleanField(default=False)
    transfers_queues_edit = models.BooleanField(default=False)
    transfers_queues_delete = models.BooleanField(default=False)


    #transfers_queues -failed bookings
    transfers_queues_failed1space1bookings_create = models.BooleanField(default=False)
    transfers_queues_failed1space1bookings_view = models.BooleanField(default=False)
    transfers_queues_failed1space1bookings_edit = models.BooleanField(default=False)
    transfers_queues_failed1space1bookings_delete = models.BooleanField(default=False)

    #transfers_queues -others
    transfers_queues_others_create = models.BooleanField(default=False)
    transfers_queues_others_view = models.BooleanField(default=False)
    transfers_queues_others_edit = models.BooleanField(default=False)
    transfers_queues_others_delete = models.BooleanField(default=False)

    #transfers -booking history
    transfers_booking1space1history_create = models.BooleanField(default=False)
    transfers_booking1space1history_view = models.BooleanField(default=False)
    transfers_booking1space1history_edit = models.BooleanField(default=False)
    transfers_booking1space1history_delete = models.BooleanField(default=False)

    #transfers -search
    transfers_search_create = models.BooleanField(default=False)
    transfers_search_view = models.BooleanField(default=False)
    transfers_search_edit = models.BooleanField(default=False)
    transfers_search_delete = models.BooleanField(default=False)

    #control panel -rail management
    control1space1panel_rail1space1management_create = models.BooleanField(default=False)
    control1space1panel_rail1space1management_view = models.BooleanField(default=False)
    control1space1panel_rail1space1management_edit = models.BooleanField(default=False)
    control1space1panel_rail1space1management_delete = models.BooleanField(default=False)

    #rail
    rail_create = models.BooleanField(default=False)
    rail_view = models.BooleanField(default=False)
    rail_edit = models.BooleanField(default=False)
    rail_delete = models.BooleanField(default=False)

    #admin panel -fare management 
    admin1space1panel_fare1space1management_create = models.BooleanField(default=False)
    admin1space1panel_fare1space1management_view = models.BooleanField(default=False)
    admin1space1panel_fare1space1management_edit = models.BooleanField(default=False)
    admin1space1panel_fare1space1management_delete = models.BooleanField(default=False)
    
    #insurance dashboard
    insurance_dashboard_create = models.BooleanField(default=False)
    insurance_dashboard_view = models.BooleanField(default=False)
    insurance_dashboard_edit = models.BooleanField(default=False)
    insurance_dashboard_delete = models.BooleanField(default=False)

    #insurance proposal
    insurance_proposal_create = models.BooleanField(default=False)
    insurance_proposal_view = models.BooleanField(default=False)
    insurance_proposal_edit = models.BooleanField(default=False)
    insurance_proposal_delete = models.BooleanField(default=False)

    #insurance proposal -manage proposal
    insurance_proposal_manage1space1proposal_create = models.BooleanField(default=False)
    insurance_proposal_manage1space1proposal_view = models.BooleanField(default=False)
    insurance_proposal_manage1space1proposal_edit = models.BooleanField(default=False)
    insurance_proposal_manage1space1proposal_delete = models.BooleanField(default=False)

    #insurance proposal -edit proposal
    insurance_proposal_edit1space1proposal_create = models.BooleanField(default=False)
    insurance_proposal_edit1space1proposal_view = models.BooleanField(default=False)
    insurance_proposal_edit1space1proposal_edit = models.BooleanField(default=False)
    insurance_proposal_edit1space1proposal_delete = models.BooleanField(default=False)


    #insurance document
    insurance_document_create = models.BooleanField(default=False)
    insurance_document_view = models.BooleanField(default=False)
    insurance_document_edit = models.BooleanField(default=False)
    insurance_document_delete = models.BooleanField(default=False)

    #insurance document -create document
    insurance_document_create1space1document_create = models.BooleanField(default=False)
    insurance_document_create1space1document_view = models.BooleanField(default=False)
    insurance_document_create1space1document_edit = models.BooleanField(default=False)
    insurance_document_create1space1document_delete = models.BooleanField(default=False)

    #insurance document -search document
    insurance_document_search1space1document_create = models.BooleanField(default=False)
    insurance_document_search1space1document_view = models.BooleanField(default=False)
    insurance_document_search1space1document_edit = models.BooleanField(default=False)
    insurance_document_search1space1document_delete = models.BooleanField(default=False)

    #insurance document - document extension request
    insurance_document_document1space1extension1space1request_create= models.BooleanField(default=False,db_column='insurance_document_extension_request_create')
    insurance_document_document1space1extension1space1request_view = models.BooleanField(default=False,db_column='insurance_document_extension_request_view')
    insurance_document_document1space1extension1space1request_edit = models.BooleanField(default=False,db_column='insurance_document_extension_request_edit')
    insurance_document_document1space1extension1space1request_delete = models.BooleanField(default=False,db_column='insurance_document_extension_request_delete')

    #bus -queues
    bus_queues_create = models.BooleanField(default=False)
    bus_queues_view = models.BooleanField(default=False)
    bus_queues_edit = models.BooleanField(default=False)
    bus_queues_delete = models.BooleanField(default=False)

    #bus -queues -cancelled bookings
    bus_queues_cancelled1space1bookings_create = models.BooleanField(default=False)
    bus_queues_cancelled1space1bookings_view = models.BooleanField(default=False)
    bus_queues_cancelled1space1bookings_edit = models.BooleanField(default=False)
    bus_queues_cancelled1space1bookings_delete = models.BooleanField(default=False)

    #bus_queues -failed bookings
    bus_queues_failed1space1bookings_create = models.BooleanField(default=False)
    bus_queues_failed1space1bookings_view = models.BooleanField(default=False)
    bus_queues_failed1space1bookings_edit = models.BooleanField(default=False)
    bus_queues_failed1space1bookings_delete = models.BooleanField(default=False)

    #bus_queues -others
    bus_queues_others_create = models.BooleanField(default=False)
    bus_queues_others_view = models.BooleanField(default=False)
    bus_queues_others_edit = models.BooleanField(default=False)
    bus_queues_others_delete = models.BooleanField(default=False)

    #bus -booking history
    bus_booking1space1history_create = models.BooleanField(default=False)
    bus_booking1space1history_view = models.BooleanField(default=False)
    bus_booking1space1history_edit = models.BooleanField(default=False)
    bus_booking1space1history_delete = models.BooleanField(default=False)

    #bus -search
    bus_search_create = models.BooleanField(default=False)
    bus_search_view = models.BooleanField(default=False)
    bus_search_edit = models.BooleanField(default=False)
    bus_search_delete = models.BooleanField(default=False)

    # transfers->Cancelled Bookings
    transfers_queues_cancelled1space1bookings_create = models.BooleanField(default=False)
    transfers_queues_cancelled1space1bookings_view = models.BooleanField(default=False)
    transfers_queues_cancelled1space1bookings_edit = models.BooleanField(default=False)
    transfers_queues_cancelled1space1bookings_delete = models.BooleanField(default=False)
    
    #insurance -queues
    insurance_queues_create = models.BooleanField(default=False)
    insurance_queues_view = models.BooleanField(default=False)
    insurance_queues_edit = models.BooleanField(default=False)
    insurance_queues_delete = models.BooleanField(default=False)

    #insurance_queues -failed bookings
    insurance_queues_failed1space1bookings_create = models.BooleanField(default=False)
    insurance_queues_failed1space1bookings_view = models.BooleanField(default=False)
    insurance_queues_failed1space1bookings_edit = models.BooleanField(default=False)
    insurance_queues_failed1space1bookings_delete = models.BooleanField(default=False)

    #insurance _queues -others
    insurance_queues_others_create = models.BooleanField(default=False)
    insurance_queues_others_view = models.BooleanField(default=False)
    insurance_queues_others_edit = models.BooleanField(default=False)
    insurance_queues_others_delete = models.BooleanField(default=False)

    #insurance -booking history
    insurance_booking1space1history_create = models.BooleanField(default=False)
    insurance_booking1space1history_view = models.BooleanField(default=False)
    insurance_booking1space1history_edit = models.BooleanField(default=False)
    insurance_booking1space1history_delete = models.BooleanField(default=False)

    #hotel -queues - cancelled Bookings
    hotel_queues_cancelled1space1bookings_create = models.BooleanField(default=False)
    hotel_queues_cancelled1space1bookings_view = models.BooleanField(default=False)
    hotel_queues_cancelled1space1bookings_edit = models.BooleanField(default=False)
    hotel_queues_cancelled1space1bookings_delete = models.BooleanField(default=False)

    def __str__(self):
        return str(self.name)

    class Meta:
        db_table = 'lookup_permission'
        ordering = ['-created_at']

class LookupRoles(SoftDeleteModel):
    ROLE_CHOICES = (
        ("super_admin","super_admin"),
        ("admin","admin"),
        ("operations","operations"),
        ("finance","finance"),
        ("sales","sales"),
        ("agency_owner","agency_owner"),
        ("agency_staff","agency_staff"),
        ("distributor_owner","distributor_owner"),
        ("distributor_staff","distributor_staff"),
        ("distributor_agent","distributor_agent"),
        ("out_api_owner","out_api_owner"),
        ("out_api_staff","out_api_staff"),
        ("enterprise_owner","enterprise_owner"),
        ("supplier","supplier")
    )
    
    name = models.CharField(max_length=500,choices=ROLE_CHOICES)
    lookup_organization_type = models.ForeignKey(LookupOrganizationTypes,on_delete=models.CASCADE)
    lookup_permission = models.ForeignKey(LookupPermission, on_delete=models.CASCADE)
    level=models.IntegerField(null=True)
    
    class Meta:
        db_table = 'lookup_roles'
        ordering = ['-created_at']
        
    def __str__(self) -> str:
        return self.name
    
#total country 
class LookupCountry(SoftDeleteModel):
    country_name = models.CharField(max_length=200)
    country_code = models.CharField(max_length=300)
    is_active = models.BooleanField(default=True)
    calling_code = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        db_table = 'lookup_country'
        ordering = ['-created_at']
#
        
    def __str__(self) -> str:
        return self.country_name

class Country(SoftDeleteModel):
    currency_name =  models.CharField(max_length=200)
    currency_code = models.CharField(max_length=200)
    currency_symbol = models.CharField(max_length=200)
    inr_conversion_rate = models.DecimalField(default = 0.0,max_digits=100, decimal_places=4)
    is_active = models.BooleanField(default=False)
    lookup = models.ForeignKey(LookupCountry, on_delete=models.CASCADE)



    def __str__(self):
        return str(self.lookup)
    

class ErrorLog(SoftDeleteModel):
    module = models.TextField()
    erros = models.JSONField()

    class Meta:
        ordering = ['-created_at']


    def __str__(self):
        return str(self.module)
    
class Permission(SoftDeleteModel):
    name = models.CharField(max_length=200)
    # flight
    flight_create = models.BooleanField(default=False)
    flight_view = models.BooleanField(default=False)
    flight_edit = models.BooleanField(default=False)
    flight_delete = models.BooleanField(default=False)


    # hotel 
    hotel_create = models.BooleanField(default=False)
    hotel_view = models.BooleanField(default=False)
    hotel_edit = models.BooleanField(default=False)
    hotel_delete = models.BooleanField(default=False)

    #hotel -search
    hotel_search_create = models.BooleanField(default=False)
    hotel_search_view = models.BooleanField(default=False)
    hotel_search_edit = models.BooleanField(default=False)
    hotel_search_delete = models.BooleanField(default=False)

    #hotel -booking history
    hotel_booking1space1history_create = models.BooleanField(default=False)
    hotel_booking1space1history_view = models.BooleanField(default=False)
    hotel_booking1space1history_edit = models.BooleanField(default=False)
    hotel_booking1space1history_delete = models.BooleanField(default=False)

    #hotel -queues
    hotel_queues_create = models.BooleanField(default=False)
    hotel_queues_view = models.BooleanField(default=False)
    hotel_queues_edit = models.BooleanField(default=False)
    hotel_queues_delete = models.BooleanField(default=False)


    #hotel -queues -failed bookings
    hotel_queues_failed1space1bookings_create = models.BooleanField(default=False)
    hotel_queues_failed1space1bookings_view = models.BooleanField(default=False)
    hotel_queues_failed1space1bookings_edit = models.BooleanField(default=False)
    hotel_queues_failed1space1bookings_delete = models.BooleanField(default=False)

    # holidays
    holidays_create = models.BooleanField(default=False)
    holidays_view = models.BooleanField(default=False)
    holidays_edit = models.BooleanField(default=False)
    holidays_delete = models.BooleanField(default=False)

    #visa 
    visa_create = models.BooleanField(default=False)
    visa_view = models.BooleanField(default=False)
    visa_edit = models.BooleanField(default=False)
    visa_delete = models.BooleanField(default=False)

    #bus
    bus_create = models.BooleanField(default=False)
    bus_view = models.BooleanField(default=False)
    bus_edit = models.BooleanField(default=False)
    bus_delete = models.BooleanField(default=False)

    #cab12 
    cab_create = models.BooleanField(default=False)
    cab_view = models.BooleanField(default=False)
    cab_edit = models.BooleanField(default=False)
    cab_delete = models.BooleanField(default=False)

    #insurance
    insurance_create = models.BooleanField(default=False)
    insurance_view = models.BooleanField(default=False)
    insurance_edit = models.BooleanField(default=False)
    insurance_delete = models.BooleanField(default=False)

    #accounts
    accounts_create = models.BooleanField(default=False)
    accounts_view = models.BooleanField(default=False)
    accounts_edit = models.BooleanField(default=False)
    accounts_delete = models.BooleanField(default=False)

    #accounts -payments
    accounts_payments_create = models.BooleanField(default=False)
    accounts_payments_view = models.BooleanField(default=False)
    accounts_payments_edit = models.BooleanField(default=False)
    accounts_payments_delete = models.BooleanField(default=False)
    
    #accounts -payments -update payments 
    accounts_payments_update1space1payments_create = models.BooleanField(default=False)
    accounts_payments_update1space1payments_view = models.BooleanField(default=False)
    accounts_payments_update1space1payments_edit = models.BooleanField(default=False)
    accounts_payments_update1space1payments_delete = models.BooleanField(default=False)


    #accounts -payments -payment history 
    accounts_payments_payment1space1history_create = models.BooleanField(default=False)
    accounts_payments_payment1space1history_view = models.BooleanField(default=False)
    accounts_payments_payment1space1history_edit = models.BooleanField(default=False)
    accounts_payments_payment1space1history_delete = models.BooleanField(default=False)

    #accounts - credit notes
    accounts_credit1space1notes_create= models.BooleanField(default=False)
    accounts_credit1space1notes_view = models.BooleanField(default=False)
    accounts_credit1space1notes_edit = models.BooleanField(default=False)
    accounts_credit1space1notes_delete = models.BooleanField(default=False)

    #accounts - invoices
    accounts_invoices_create= models.BooleanField(default=False)
    accounts_invoices_view = models.BooleanField(default=False)
    accounts_invoices_edit = models.BooleanField(default=False)
    accounts_invoices_delete = models.BooleanField(default=False)

    #accounts - ledger & statement
    accounts_ledger1space1and1space1statement_create= models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_view = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_edit = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_delete = models.BooleanField(default=False)

    #accounts - ledger & statement - ledger
    accounts_ledger1space1and1space1statement_ledger_create= models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_ledger_view = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_ledger_edit = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_ledger_delete = models.BooleanField(default=False)

    #accounts - ledger & statement - statement
    accounts_ledger1space1and1space1statement_statement_create= models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_statement_view = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_statement_edit = models.BooleanField(default=False)
    accounts_ledger1space1and1space1statement_statement_delete = models.BooleanField(default=False)


    #accounts - billing
    accounts_billing_create= models.BooleanField(default=False)
    accounts_billing_view = models.BooleanField(default=False)
    accounts_billing_edit = models.BooleanField(default=False)
    accounts_billing_delete = models.BooleanField(default=False)


    #accounts - credit updation
    accounts_credit1space1updation_create= models.BooleanField(default=False)
    accounts_credit1space1updation_view = models.BooleanField(default=False)
    accounts_credit1space1updation_edit = models.BooleanField(default=False)
    accounts_credit1space1updation_delete = models.BooleanField(default=False)

    #operations
    operations_create = models.BooleanField(default=False)
    operations_view = models.BooleanField(default=False)
    operations_edit = models.BooleanField(default=False)
    operations_delete = models.BooleanField(default=False)

    #operations -import & pnr
    operations_import1space1pnr_create = models.BooleanField(default=False)
    operations_import1space1pnr_view = models.BooleanField(default=False)
    operations_import1space1pnr_edit = models.BooleanField(default=False)
    operations_import1space1pnr_delete = models.BooleanField(default=False)


    #operations -visa queues
    operations_visa1space1queues_create = models.BooleanField(default=False)
    operations_visa1space1queues_view = models.BooleanField(default=False)
    operations_visa1space1queues_edit = models.BooleanField(default=False)
    operations_visa1space1queues_delete = models.BooleanField(default=False)


    #operations -holidays queues
    operations_holidays1space1queues_create = models.BooleanField(default=False)
    operations_holidays1space1queues_view = models.BooleanField(default=False)
    operations_holidays1space1queues_edit = models.BooleanField(default=False)
    operations_holidays1space1queues_delete = models.BooleanField(default=False)
    
    
    #operations -client proxy
    operations_client1space1proxy_create = models.BooleanField(default=False)
    operations_client1space1proxy_view = models.BooleanField(default=False)
    operations_client1space1proxy_edit = models.BooleanField(default=False)
    operations_client1space1proxy_delete = models.BooleanField(default=False)


    #control panel
    control1space1panel_create = models.BooleanField(default=False)
    control1space1panel_view = models.BooleanField(default=False)
    control1space1panel_edit = models.BooleanField(default=False)
    control1space1panel_delete = models.BooleanField(default=False)


    #control panel -agency master
    control1space1panel_agency1space1master_create = models.BooleanField(default=False)
    control1space1panel_agency1space1master_view = models.BooleanField(default=False)
    control1space1panel_agency1space1master_edit = models.BooleanField(default=False)
    control1space1panel_agency1space1master_delete = models.BooleanField(default=False)


    #control panel -role assignment
    control1space1panel_role1space1assignment_create = models.BooleanField(default=False)
    control1space1panel_role1space1assignment_view = models.BooleanField(default=False)
    control1space1panel_role1space1assignment_edit = models.BooleanField(default=False)
    control1space1panel_role1space1assignment_delete = models.BooleanField(default=False)


    #control panel - whitelabeling
    control1space1panel_whitelabeling_create = models.BooleanField(default=False)
    control1space1panel_whitelabeling_view = models.BooleanField(default=False)
    control1space1panel_whitelabeling_edit = models.BooleanField(default=False)
    control1space1panel_whitelabeling_delete = models.BooleanField(default=False)


    #control panel - supplier
    control1space1panel_supplier_create = models.BooleanField(default=False)
    control1space1panel_supplier_view = models.BooleanField(default=False)
    control1space1panel_supplier_edit = models.BooleanField(default=False)
    control1space1panel_supplier_delete = models.BooleanField(default=False)


    #control panel - supplier -flights fixed fares
    control1space1panel_supplier_flights1space1fixed1space1fares_create = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_create')
    control1space1panel_supplier_flights1space1fixed1space1fares_view = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_view')
    control1space1panel_supplier_flights1space1fixed1space1fares_edit = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_edit')
    control1space1panel_supplier_flights1space1fixed1space1fares_delete = models.BooleanField(default=False,db_column='c_p_flight_fixed_fares_delete')


    #control panel - supplier - hotels products
    control1space1panel_supplier_hotels1space1products_create = models.BooleanField(default=False)
    control1space1panel_supplier_hotels1space1products_view = models.BooleanField(default=False)
    control1space1panel_supplier_hotels1space1products_edit = models.BooleanField(default=False)
    control1space1panel_supplier_hotels1space1products_delete = models.BooleanField(default=False)


    #control panel - approvals
    control1space1panel_approvals_create = models.BooleanField(default=False)
    control1space1panel_approvals_view = models.BooleanField(default=False)
    control1space1panel_approvals_edit = models.BooleanField(default=False)
    control1space1panel_approvals_delete = models.BooleanField(default=False)


    #control panel - approvals -fd fares
    control1space1panel_approvals_fd1space1fares_create = models.BooleanField(default=False)
    control1space1panel_approvals_fd1space1fares_view = models.BooleanField(default=False)
    control1space1panel_approvals_fd1space1fares_edit = models.BooleanField(default=False)
    control1space1panel_approvals_fd1space1fares_delete = models.BooleanField(default=False)


    #control panel - approvals -holidays
    control1space1panel_approvals_holidays_create = models.BooleanField(default=False)
    control1space1panel_approvals_holidays_view = models.BooleanField(default=False)
    control1space1panel_approvals_holidays_edit = models.BooleanField(default=False)
    control1space1panel_approvals_holidays_delete = models.BooleanField(default=False)


    #control panel - approvals -hotels
    control1space1panel_approvals_hotels_create = models.BooleanField(default=False)
    control1space1panel_approvals_hotels_view = models.BooleanField(default=False)
    control1space1panel_approvals_hotels_edit = models.BooleanField(default=False)
    control1space1panel_approvals_hotels_delete = models.BooleanField(default=False)


    #reports 
    reports_create = models.BooleanField(default=False)
    reports_view = models.BooleanField(default=False)
    reports_edit = models.BooleanField(default=False)
    reports_delete = models.BooleanField(default=False)

    #reports -agency productivity
    reports_agency1space1productivity_create = models.BooleanField(default=False)
    reports_agency1space1productivity_view = models.BooleanField(default=False)
    reports_agency1space1productivity_edit = models.BooleanField(default=False)
    reports_agency1space1productivity_delete = models.BooleanField(default=False)


    #reports -staff productivity
    reports_staff1space1productivity_create = models.BooleanField(default=False)
    reports_staff1space1productivity_view = models.BooleanField(default=False)
    reports_staff1space1productivity_edit = models.BooleanField(default=False)
    reports_staff1space1productivity_delete = models.BooleanField(default=False)


    #admin panel  we are giving 1space1 for normal space eg: admin1space1panel--> admin panel 
    admin1space1panel_create = models.BooleanField(default=False)
    admin1space1panel_view = models.BooleanField(default=False)
    admin1space1panel_edit = models.BooleanField(default=False)
    admin1space1panel_delete = models.BooleanField(default=False)

    #admin panel -visa 
    admin1space1panel_visa_create = models.BooleanField(default=False)
    admin1space1panel_visa_view = models.BooleanField(default=False)
    admin1space1panel_visa_edit = models.BooleanField(default=False)
    admin1space1panel_visa_delete = models.BooleanField(default=False)

    # admin panel -holiday
    admin1space1panel_holiday_create = models.BooleanField(default=False)
    admin1space1panel_holiday_view = models.BooleanField(default=False)
    admin1space1panel_holiday_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_delete = models.BooleanField(default=False)


    # admin panel -holiday product
    admin1space1panel_holiday_product_create = models.BooleanField(default=False)
    admin1space1panel_holiday_product_view = models.BooleanField(default=False)
    admin1space1panel_holiday_product_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_product_delete = models.BooleanField(default=False)


    #admin panel - holiday theme
    admin1space1panel_holiday_theme_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_theme_create = models.BooleanField(default=False)
    admin1space1panel_holiday_theme_delete = models.BooleanField(default=False)
    admin1space1panel_holiday_theme_view = models.BooleanField(default=False)


    # api management

    admin1space1panel_api1space1management_create = models.BooleanField(default=False)
    admin1space1panel_api1space1management_view = models.BooleanField(default=False)
    admin1space1panel_api1space1management_edit = models.BooleanField(default=False)
    admin1space1panel_api1space1management_delete = models.BooleanField(default=False)
    

    # communication

    admin1space1panel_communication_create = models.BooleanField(default=False)
    admin1space1panel_communication_view = models.BooleanField(default=False)
    admin1space1panel_communication_edit = models.BooleanField(default=False)
    admin1space1panel_communication_delete = models.BooleanField(default=False)


    #general

    admin1space1panel_general1space1integeration_create = models.BooleanField(default=False)
    admin1space1panel_general1space1integeration_view = models.BooleanField(default=False)
    admin1space1panel_general1space1integeration_edit = models.BooleanField(default=False)
    admin1space1panel_general1space1integeration_delete = models.BooleanField(default=False)

    
    #admin panel - supplier deal manager
    admin1space1panel_supplier1space1deal1space1manager_create = models.BooleanField(default=False)
    admin1space1panel_supplier1space1deal1space1manager_view = models.BooleanField(default=False)
    admin1space1panel_supplier1space1deal1space1manager_edit = models.BooleanField(default=False)
    admin1space1panel_supplier1space1deal1space1manager_delete = models.BooleanField(default=False)


    #     #admin panel - template
    admin1space1panel_template_create = models.BooleanField(default=False)
    admin1space1panel_template_view = models.BooleanField(default=False)
    admin1space1panel_template_edit = models.BooleanField(default=False)
    admin1space1panel_template_delete = models.BooleanField(default=False)


    # admin panel -holiday favourites
    admin1space1panel_holiday_favourites_create = models.BooleanField(default=False)
    admin1space1panel_holiday_favourites_view = models.BooleanField(default=False)
    admin1space1panel_holiday_favourites_edit = models.BooleanField(default=False)
    admin1space1panel_holiday_favourites_delete = models.BooleanField(default=False)

    # admin panel -visa favourites
    admin1space1panel_visa_favourites_create = models.BooleanField(default=False)
    admin1space1panel_visa_favourites_view = models.BooleanField(default=False)
    admin1space1panel_visa_favourites_edit = models.BooleanField(default=False)
    admin1space1panel_visa_favourites_delete = models.BooleanField(default=False)
    
    
    admin1space1panel_visa_products_create = models.BooleanField(default=False)
    admin1space1panel_visa_products_view = models.BooleanField(default=False)
    admin1space1panel_visa_products_edit = models.BooleanField(default=False)
    admin1space1panel_visa_products_delete = models.BooleanField(default=False)
    
    admin1space1panel_visa_category_create = models.BooleanField(default=False)
    admin1space1panel_visa_category_view = models.BooleanField(default=False)
    admin1space1panel_visa_category_edit = models.BooleanField(default=False)
    admin1space1panel_visa_category_delete = models.BooleanField(default=False)
    
    
    admin1space1panel_visa_type_create = models.BooleanField(default=False)
    admin1space1panel_visa_type_view = models.BooleanField(default=False)
    admin1space1panel_visa_type_edit = models.BooleanField(default=False)
    admin1space1panel_visa_type_delete = models.BooleanField(default=False)

    #flight -queues
    flight_queues_create = models.BooleanField(default=False)
    flight_queues_view = models.BooleanField(default=False)
    flight_queues_edit = models.BooleanField(default=False)
    flight_queues_delete = models.BooleanField(default=False)


    #flight -queues -failed bookings
    flight_queues_failed1space1bookings_create = models.BooleanField(default=False)
    flight_queues_failed1space1bookings_view = models.BooleanField(default=False)
    flight_queues_failed1space1bookings_edit = models.BooleanField(default=False)
    flight_queues_failed1space1bookings_delete = models.BooleanField(default=False)

    #flight -queues -hold bookings
    flight_queues_hold1space1bookings_create = models.BooleanField(default=False)
    flight_queues_hold1space1bookings_view = models.BooleanField(default=False)
    flight_queues_hold1space1bookings_edit = models.BooleanField(default=False)
    flight_queues_hold1space1bookings_delete = models.BooleanField(default=False)


    #flight -queues -passenger calendar
    flight_queues_passenger1space1calender_create = models.BooleanField(default=False)
    flight_queues_passenger1space1calender_view = models.BooleanField(default=False)
    flight_queues_passenger1space1calender_edit = models.BooleanField(default=False)
    flight_queues_passenger1space1calender_delete = models.BooleanField(default=False)


    #flight -booking history
    flight_booking1space1history_create = models.BooleanField(default=False)
    flight_booking1space1history_view = models.BooleanField(default=False)
    flight_booking1space1history_edit = models.BooleanField(default=False)
    flight_booking1space1history_delete = models.BooleanField(default=False)
    
    #flight -search
    flight_search_create = models.BooleanField(default=False)
    flight_search_view = models.BooleanField(default=False)
    flight_search_edit = models.BooleanField(default=False)
    flight_search_delete = models.BooleanField(default=False)


    #accounts -branch allocation
    accounts_branch1space1allocation_create = models.BooleanField(default=False)
    accounts_branch1space1allocation_view = models.BooleanField(default=False)
    accounts_branch1space1allocation_edit = models.BooleanField(default=False)
    accounts_branch1space1allocation_delete = models.BooleanField(default=False)

   #flight -queues -cancelled bookings
    flight_queues_cancelled1space1bookings_create = models.BooleanField(default=False)
    flight_queues_cancelled1space1bookings_view = models.BooleanField(default=False)
    flight_queues_cancelled1space1bookings_edit = models.BooleanField(default=False)
    flight_queues_cancelled1space1bookings_delete = models.BooleanField(default=False)


    #admin panel - customer deal manager
    admin1space1panel_customer1space1deal1space1manager_create = models.BooleanField(default=False)
    admin1space1panel_customer1space1deal1space1manager_view = models.BooleanField(default=False)
    admin1space1panel_customer1space1deal1space1manager_edit = models.BooleanField(default=False)
    admin1space1panel_customer1space1deal1space1manager_delete = models.BooleanField(default=False)

    #accounts -offline & ticketing
    accounts_offline1space1ticketing_create = models.BooleanField(default=False)
    accounts_offline1space1ticketing_view = models.BooleanField(default=False)
    accounts_offline1space1ticketing_edit = models.BooleanField(default=False)
    accounts_offline1space1ticketing_delete = models.BooleanField(default=False)

    #holidays -search
    holidays_search_create = models.BooleanField(default=False)
    holidays_search_view = models.BooleanField(default=False)
    holidays_search_edit = models.BooleanField(default=False)
    holidays_search_delete = models.BooleanField(default=False)

    #holidays -enquiry history
    holidays_enquiry1space1history_create = models.BooleanField(default=False)
    holidays_enquiry1space1history_view = models.BooleanField(default=False)
    holidays_enquiry1space1history_edit = models.BooleanField(default=False)
    holidays_enquiry1space1history_delete = models.BooleanField(default=False)

        #visa -search
    visa_search_create = models.BooleanField(default=False)
    visa_search_view = models.BooleanField(default=False)
    visa_search_edit = models.BooleanField(default=False)
    visa_search_delete = models.BooleanField(default=False)

    #visa -enquiry history
    visa_enquiry1space1history_create = models.BooleanField(default=False)
    visa_enquiry1space1history_view = models.BooleanField(default=False)
    visa_enquiry1space1history_edit = models.BooleanField(default=False)
    visa_enquiry1space1history_delete = models.BooleanField(default=False)

    #accounts - ledger & statement - agent statement
    accounts_ledger1space1and1space1statement_agent1space1statement_create= models.BooleanField(default=False,db_column='agent_statement_create')
    accounts_ledger1space1and1space1statement_agent1space1statement_view = models.BooleanField(default=False,db_column='agent_statement_view')
    accounts_ledger1space1and1space1statement_agent1space1statement_edit = models.BooleanField(default=False,db_column='agent_statement_edit')
    accounts_ledger1space1and1space1statement_agent1space1statement_delete = models.BooleanField(default=False,db_column='agent_statement_delete')

    #accounts - credit notes own 
    accounts_credit1space1notes_own_create= models.BooleanField(default=False)
    accounts_credit1space1notes_own_view = models.BooleanField(default=False)
    accounts_credit1space1notes_own_edit = models.BooleanField(default=False)
    accounts_credit1space1notes_own_delete = models.BooleanField(default=False)


    #accounts - credit notes agent 
    accounts_credit1space1notes_agent_create= models.BooleanField(default=False)
    accounts_credit1space1notes_agent_view = models.BooleanField(default=False)
    accounts_credit1space1notes_agent_edit = models.BooleanField(default=False)
    accounts_credit1space1notes_agent_delete = models.BooleanField(default=False)
    
    #reports -sales performance
    reports_sales1space1performance_create = models.BooleanField(default=False)
    reports_sales1space1performance_view = models.BooleanField(default=False)
    reports_sales1space1performance_edit = models.BooleanField(default=False)
    reports_sales1space1performance_delete = models.BooleanField(default=False)

    #control panel - outapi management
    control1space1panel_out1hyphen1API1space1management_create = models.BooleanField(default=False)
    control1space1panel_out1hyphen1API1space1management_view = models.BooleanField(default=False)
    control1space1panel_out1hyphen1API1space1management_edit = models.BooleanField(default=False)
    control1space1panel_out1hyphen1API1space1management_delete = models.BooleanField(default=False)
    
    #reports -user journey tracker
    reports_user1space1journey1space1tracker_create = models.BooleanField(default=False)
    reports_user1space1journey1space1tracker_view = models.BooleanField(default=False)
    reports_user1space1journey1space1tracker_edit = models.BooleanField(default=False)
    reports_user1space1journey1space1tracker_delete = models.BooleanField(default=False)

    #reports - finance team performance
    reports_finance1space1team1space1performance_create = models.BooleanField(default=False)
    reports_finance1space1team1space1performance_view = models.BooleanField(default=False)
    reports_finance1space1team1space1performance_edit = models.BooleanField(default=False)
    reports_finance1space1team1space1performance_delete = models.BooleanField(default=False)
    
    #flight -queues -others
    flight_queues_others_create = models.BooleanField(default=False)
    flight_queues_others_view = models.BooleanField(default=False)
    flight_queues_others_edit = models.BooleanField(default=False)
    flight_queues_others_delete = models.BooleanField(default=False)

    #reports -operation performance 
    reports_operation1space1performance_create = models.BooleanField(default=False)
    reports_operation1space1performance_view = models.BooleanField(default=False)
    reports_operation1space1performance_edit = models.BooleanField(default=False)
    reports_operation1space1performance_delete = models.BooleanField(default=False)

    #control panel - whitelabel management
    control1space1panel_whitelabel1space1management_create = models.BooleanField(default=False)
    control1space1panel_whitelabel1space1management_view = models.BooleanField(default=False)
    control1space1panel_whitelabel1space1management_edit = models.BooleanField(default=False)
    control1space1panel_whitelabel1space1management_delete = models.BooleanField(default=False)

    #Transfers 
    transfers_create = models.BooleanField(default=False)
    transfers_view = models.BooleanField(default=False)
    transfers_edit = models.BooleanField(default=False)
    transfers_delete = models.BooleanField(default=False)

    #transfers -queues
    transfers_queues_create = models.BooleanField(default=False)
    transfers_queues_view = models.BooleanField(default=False)
    transfers_queues_edit = models.BooleanField(default=False)
    transfers_queues_delete = models.BooleanField(default=False)


    #transfers_queues -failed bookings
    transfers_queues_failed1space1bookings_create = models.BooleanField(default=False)
    transfers_queues_failed1space1bookings_view = models.BooleanField(default=False)
    transfers_queues_failed1space1bookings_edit = models.BooleanField(default=False)
    transfers_queues_failed1space1bookings_delete = models.BooleanField(default=False)

    #transfers_queues -others
    transfers_queues_others_create = models.BooleanField(default=False)
    transfers_queues_others_view = models.BooleanField(default=False)
    transfers_queues_others_edit = models.BooleanField(default=False)
    transfers_queues_others_delete = models.BooleanField(default=False)

    #transfers -booking history
    transfers_booking1space1history_create = models.BooleanField(default=False)
    transfers_booking1space1history_view = models.BooleanField(default=False)
    transfers_booking1space1history_edit = models.BooleanField(default=False)
    transfers_booking1space1history_delete = models.BooleanField(default=False)

    #transfers -search
    transfers_search_create = models.BooleanField(default=False)
    transfers_search_view = models.BooleanField(default=False)
    transfers_search_edit = models.BooleanField(default=False)
    transfers_search_delete = models.BooleanField(default=False)

    #control panel -rail management
    control1space1panel_rail1space1management_create = models.BooleanField(default=False)
    control1space1panel_rail1space1management_view = models.BooleanField(default=False)
    control1space1panel_rail1space1management_edit = models.BooleanField(default=False)
    control1space1panel_rail1space1management_delete = models.BooleanField(default=False)
    
    #rail
    rail_create = models.BooleanField(default=False)
    rail_view = models.BooleanField(default=False)
    rail_edit = models.BooleanField(default=False)
    rail_delete = models.BooleanField(default=False)

    #admin panel -fare management 
    admin1space1panel_fare1space1management_create = models.BooleanField(default=False)
    admin1space1panel_fare1space1management_view = models.BooleanField(default=False)
    admin1space1panel_fare1space1management_edit = models.BooleanField(default=False)
    admin1space1panel_fare1space1management_delete = models.BooleanField(default=False)
    
    #insurance dashboard
    insurance_dashboard_create = models.BooleanField(default=False)
    insurance_dashboard_view = models.BooleanField(default=False)
    insurance_dashboard_edit = models.BooleanField(default=False)
    insurance_dashboard_delete = models.BooleanField(default=False)

    #insurance proposal
    insurance_proposal_create = models.BooleanField(default=False)
    insurance_proposal_view = models.BooleanField(default=False)
    insurance_proposal_edit = models.BooleanField(default=False)
    insurance_proposal_delete = models.BooleanField(default=False)

    #insurance proposal -manage proposal
    insurance_proposal_manage1space1proposal_create = models.BooleanField(default=False)
    insurance_proposal_manage1space1proposal_view = models.BooleanField(default=False)
    insurance_proposal_manage1space1proposal_edit = models.BooleanField(default=False)
    insurance_proposal_manage1space1proposal_delete = models.BooleanField(default=False)

    #insurance proposal -edit proposal
    insurance_proposal_edit1space1proposal_create = models.BooleanField(default=False)
    insurance_proposal_edit1space1proposal_view = models.BooleanField(default=False)
    insurance_proposal_edit1space1proposal_edit = models.BooleanField(default=False)
    insurance_proposal_edit1space1proposal_delete = models.BooleanField(default=False)


    #insurance document
    insurance_document_create = models.BooleanField(default=False)
    insurance_document_view = models.BooleanField(default=False)
    insurance_document_edit = models.BooleanField(default=False)
    insurance_document_delete = models.BooleanField(default=False)

    #insurance document -create document
    insurance_document_create1space1document_create = models.BooleanField(default=False)
    insurance_document_create1space1document_view = models.BooleanField(default=False)
    insurance_document_create1space1document_edit = models.BooleanField(default=False)
    insurance_document_create1space1document_delete = models.BooleanField(default=False)

    #insurance document -search document
    insurance_document_search1space1document_create = models.BooleanField(default=False)
    insurance_document_search1space1document_view = models.BooleanField(default=False)
    insurance_document_search1space1document_edit = models.BooleanField(default=False)
    insurance_document_search1space1document_delete = models.BooleanField(default=False)

    #insurance document - document extension request
    insurance_document_document1space1extension1space1request_create= models.BooleanField(default=False,db_column='insurance_document_extension_request_create')
    insurance_document_document1space1extension1space1request_view = models.BooleanField(default=False,db_column='insurance_document_extension_request_view')
    insurance_document_document1space1extension1space1request_edit = models.BooleanField(default=False,db_column='insurance_document_extension_request_edit')
    insurance_document_document1space1extension1space1request_delete = models.BooleanField(default=False,db_column='insurance_document_extension_request_delete')

    #bus -queues
    bus_queues_create = models.BooleanField(default=False)
    bus_queues_view = models.BooleanField(default=False)
    bus_queues_edit = models.BooleanField(default=False)
    bus_queues_delete = models.BooleanField(default=False)

    #bus -queues -cancelled bookings
    bus_queues_cancelled1space1bookings_create = models.BooleanField(default=False)
    bus_queues_cancelled1space1bookings_view = models.BooleanField(default=False)
    bus_queues_cancelled1space1bookings_edit = models.BooleanField(default=False)
    bus_queues_cancelled1space1bookings_delete = models.BooleanField(default=False)

    #bus_queues -failed bookings
    bus_queues_failed1space1bookings_create = models.BooleanField(default=False)
    bus_queues_failed1space1bookings_view = models.BooleanField(default=False)
    bus_queues_failed1space1bookings_edit = models.BooleanField(default=False)
    bus_queues_failed1space1bookings_delete = models.BooleanField(default=False)

    #bus_queues -others
    bus_queues_others_create = models.BooleanField(default=False)
    bus_queues_others_view = models.BooleanField(default=False)
    bus_queues_others_edit = models.BooleanField(default=False)
    bus_queues_others_delete = models.BooleanField(default=False)

    #bus -booking history
    bus_booking1space1history_create = models.BooleanField(default=False)
    bus_booking1space1history_view = models.BooleanField(default=False)
    bus_booking1space1history_edit = models.BooleanField(default=False)
    bus_booking1space1history_delete = models.BooleanField(default=False)

    #bus -search
    bus_search_create = models.BooleanField(default=False)
    bus_search_view = models.BooleanField(default=False)
    bus_search_edit = models.BooleanField(default=False)
    bus_search_delete = models.BooleanField(default=False)

    # transfers queues ->cancelled Bookings
    transfers_queues_cancelled1space1bookings_create = models.BooleanField(default=False)
    transfers_queues_cancelled1space1bookings_view = models.BooleanField(default=False)
    transfers_queues_cancelled1space1bookings_edit = models.BooleanField(default=False)
    transfers_queues_cancelled1space1bookings_delete = models.BooleanField(default=False)

    
    #insurance -queues
    insurance_queues_create = models.BooleanField(default=False)
    insurance_queues_view = models.BooleanField(default=False)
    insurance_queues_edit = models.BooleanField(default=False)
    insurance_queues_delete = models.BooleanField(default=False)

    #insurance_queues -failed bookings
    insurance_queues_failed1space1bookings_create = models.BooleanField(default=False)
    insurance_queues_failed1space1bookings_view = models.BooleanField(default=False)
    insurance_queues_failed1space1bookings_edit = models.BooleanField(default=False)
    insurance_queues_failed1space1bookings_delete = models.BooleanField(default=False)

    #insurance _queues -others
    insurance_queues_others_create = models.BooleanField(default=False)
    insurance_queues_others_view = models.BooleanField(default=False)
    insurance_queues_others_edit = models.BooleanField(default=False)
    insurance_queues_others_delete = models.BooleanField(default=False)

    #insurance -booking history
    insurance_booking1space1history_create = models.BooleanField(default=False)
    insurance_booking1space1history_view = models.BooleanField(default=False)
    insurance_booking1space1history_edit = models.BooleanField(default=False)
    insurance_booking1space1history_delete = models.BooleanField(default=False)
    
    #hotel -queues - cancelled Bookings
    hotel_queues_cancelled1space1bookings_create = models.BooleanField(default=False)
    hotel_queues_cancelled1space1bookings_view = models.BooleanField(default=False)
    hotel_queues_cancelled1space1bookings_edit = models.BooleanField(default=False)
    hotel_queues_cancelled1space1bookings_delete = models.BooleanField(default=False)

    def __str__(self):
        return str(self.name)
    
class WhiteLabel(SoftDeleteModel):
    host = models.CharField(max_length=2000)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return str(self.host)

    class Meta:
        db_table = 'whitelabel'
        ordering = ['-created_at']

from integrations.general.models import Integration

class Organization(SoftDeleteModel):
    STATUS_CHOICES = (
        ("active","active"),
        ("inactive", "inactive"),
        ("pending","pending"),
        
    )
    organization_name = models.CharField(max_length=2000)
    organization_type = models.ForeignKey(LookupOrganizationTypes, on_delete = models.CASCADE)
    is_iata_or_arc = models.BooleanField()
    iata_or_arc_code =models.CharField(max_length=2000, null=True, blank=True)
    address = models.TextField()
    state = models.CharField(max_length=2000, null=True, blank=True)
    organization_country = models.ForeignKey(Country, on_delete=models.DO_NOTHING,null=True, blank=True)
    whitelabel = models.ForeignKey(WhiteLabel, on_delete=models.CASCADE, null=True, blank=True)
    organization_zipcode = models.CharField(null=True, blank=True)
    organization_pan_number = models.CharField(max_length=2000, null=True, blank=True)
    organization_gst_number = models.CharField(max_length=2000, null=True, blank=True)
    organization_tax_number = models.CharField(max_length=2000, null=True, blank=True)
    organization_currency = models.CharField(max_length=200)
    easy_link_account_code = models.CharField(max_length=2000, null=True, blank=True)
    easy_link_account_name = models.CharField(max_length=2000, null=True, blank=True)
    status = models.CharField(max_length=2000, null=True, blank=True, choices = STATUS_CHOICES, default="pending")
    # markup_or_service_charge = models.DecimalField(max_digits =10,decimal_places=2)
    # credit_update = models.DecimalField(max_digits =10,decimal_places=2)
    rand_code = models.TextField(null=True)
    profile_picture = models.ImageField(upload_to = 'btob/gallery', null=True, blank=True)
    easy_link_billing_account = models.ForeignKey(Integration, on_delete=models.CASCADE, blank=True, null=True)
    support_email = models.CharField(max_length=2000, null=True, blank=True)
    support_phone = models.CharField(max_length=2000, null=True, blank=True)
    virtual_ac_no = models.CharField(max_length=2000, null=True, blank=True)
    sales_agent = models.ForeignKey("UserDetails", on_delete=models.CASCADE, null=True, blank=True, related_name=  'users_as_sales_agent')
    easy_link_billing_code = models.CharField(max_length=2000, null=True, blank=True)
    WHITELABEL_CHOICES = (
        ('not_requested','not_requested'),
        ('pending','pending'),
        ('active','active'),
    )
    is_white_label = models.CharField(max_length = 200, default = 'not_requested', choices=WHITELABEL_CHOICES )
    def save(self, *args, **kwargs):
        rand_code = "BTA" + str(random.randint(10000,100000))
        if self.rand_code is None:
            while  Organization.objects.filter(rand_code=rand_code).exists():
                rand_code = "BTA" + str(random.randint(10000,100000))
        self.rand_code = rand_code
        return super(Organization, self).save(*args, **kwargs)
    
    
    def __str__(self):  
        return str(self.organization_name)
    
    class Meta:
        db_table = 'organization'
        ordering = ['-created_at']
 
class UserGroup(SoftDeleteModel):
    name = models.CharField(max_length=2000)
    role = models.ForeignKey(LookupRoles, on_delete=models.CASCADE,null=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)
    is_visible= models.BooleanField(default=False)
    
    class Meta:
        db_table = 'user_group'
        ordering = ['-created_at']

    def __str__(self):
        return str(self.name)

class UserDetails(AbstractUser, SoftDeleteModel):
    phone_code=models.CharField(max_length=100,null=True, blank=True)
    phone_number = models.CharField(max_length=100,null=True, blank=True)
    role = models.ForeignKey(LookupRoles, on_delete=models.CASCADE, null=True)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    address = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_first_time = models.BooleanField(default=True)
    base_country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True)
    # state = models.CharField(max_length=300,null=True, blank=True)
    zip_code = models.IntegerField(null=True, blank=True)
    user_group = models.ForeignKey(UserGroup,on_delete=models.CASCADE,null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True,related_name="users_details")
    agency_name =  models.CharField(max_length=500, null=True, blank=True)
    created_by = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True)
    is_client_proxy = models.BooleanField(default=False)
    user_external_id = models.CharField(max_length=150, null=True, blank=True)
    last_login_ip = models.CharField(max_length=150,null=True, blank=True)
    # markup = models.IntegerField(null=True, blank=True)
    dom_markup = models.IntegerField(null=True, blank=True)
    int_markup = models.IntegerField(null=True, blank=True)


    class Meta:
        db_table = 'user_details'
        ordering = ['-created_at']
        
        
    def __str__(self):
        return str(self.first_name)
    
    def save(self, *args, **kwargs):
        now = int(time.time())
        if not self.id:
            if not self.user.organization:
                self.user.user_internal_id = f"NOR-{''.join(str(now).split('.')[0])}"
            else:
                self.user_internal_id = f"{''.join([i[0].title() for i in self.organization.organization_name.split()])}-{''.join(str(now).split('.')[0])}"
        self.modified_at = now
        super(SoftDeleteModel, self).save(*args, **kwargs)
        
class Tickets(SoftDeleteModel):
    TICKET_TYPE_CHOICES = (
        ("Open" , "Open"),
        ("Close" , "Close")
    )
    TICKET_STATUS_CHOICES = (
        ("Register" , "New Customer Registration"),
        ("Limit_Reached" , "Customer Inactive - Max Retry Limit Reached")
                )
                
    ticket_type = models.CharField(max_length = 200, choices = TICKET_TYPE_CHOICES)
    status = models.CharField(max_length = 400, choices = TICKET_STATUS_CHOICES)
    user = models.ForeignKey(UserDetails, on_delete=models.CASCADE, related_name='user_details')  #used to store user id( if register)), or ticket log status
    data = models.JSONField(null =True)
    modified_by = models.ForeignKey(UserDetails, on_delete=models.CASCADE,  related_name='modified_by', null=True)

class OtpDetails(SoftDeleteModel):
    user = models.OneToOneField(UserDetails,on_delete=models.CASCADE, blank=True)
    code = models.CharField(max_length=200)
    expiration_time = models.DateTimeField()
    error_count = models.IntegerField()
    class Meta:
        db_table = 'otp_details'
        ordering = ['-created_at']

class NotificationTemplate(SoftDeleteModel):    
    NOTIFICATION_TYPE_CHOICES = (
        ('registration', 'registration'),
    )
    CHANNEL_CHOICES = (
        ('email', 'email'),
    )
    MEMORY_VARIABLE_CHOICES = (
        ("customer_email", "customer_email"),
        ("customer_id", "customer_id"),
        ("customer_name", "customer_name"),
        ("customer_phone", "customer_phone"),
        ("customer_password", "customer_password"),
    )
    notification_type = models.CharField(
        max_length=45, choices=NOTIFICATION_TYPE_CHOICES)
    heading = models.CharField(max_length=150)
    content = models.TextField()
    channel = models.CharField(max_length=150, choices=CHANNEL_CHOICES)
    is_active = models.BooleanField(default=True)
    class Meta:
        db_table = 'notification_templates'
        managed = False
        ordering = ['-created_at']

class LookupTemplate(SoftDeleteModel):
    name = models.CharField(max_length=2000)
    image_url = models.CharField(max_length=2000, null=True, blank=True)
    is_default = models.BooleanField()
    
class LookupTheme(SoftDeleteModel):
    customer_journey_button_first_color = models.CharField(max_length=500, null=True, blank=True)
    customer_journey_button_second_color = models.CharField(max_length=500, null=True,blank=True)
    general_button_first_color = models.CharField(max_length=500, null=True,blank=True)
    general_button_second_color = models.CharField(max_length=500, null=True, blank=True)
    background_color = models.CharField(max_length=500, null=True, blank=True)
    nav_bar_text_color = models.CharField(max_length=500, null=True, blank=True)
    nav_bar_drop_down_color = models.CharField(max_length=500, null=True, blank=True)
    nav_bar_bg_color = models.CharField(max_length=500, null=True, blank=True)
    nav_bar_selected_text_color = models.CharField(max_length=500, null=True, blank=True)
    nav_bar_selected_bg_color = models.CharField(max_length=500, null=True, blank=True)
    loader_color = models.CharField(max_length=500, null=True, blank=True)
    template_id = models.ForeignKey(LookupTemplate, on_delete=models.CASCADE, null=True)
    customer_journey_text_color = models.CharField(max_length=500, null=True, blank=True)
    general_button_text_color = models.CharField(max_length=500, null=True, blank=True)

class LookUpIntegerationNotification(SoftDeleteModel):
    INTEGERATION_TYPE_CHOICES = [("email","email"),
                                 ("sms","sms"),
                                 ("whatsapp","whatsapp")]
    name = models.CharField(max_length=2000)
    integeration_type = models.CharField(max_length=200, choices=INTEGERATION_TYPE_CHOICES)
    keys = ArrayField(models.CharField(max_length=600), blank=True, default=list)
    icon_url = models.CharField(max_length=600)
    

class NotificationIntegeration(SoftDeleteModel):
    INTEGERATION_TYPE_CHOICES = [("email","email"),
                                 ("sms","sms"),
                                 ("whatsapp","whatsapp")]
    country = models.ForeignKey(Country,on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    data = models.JSONField()
    icon_url = models.CharField(max_length=600)
    integeration_type = models.CharField(max_length=200, choices=INTEGERATION_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    look_up = models.ForeignKey(LookUpIntegerationNotification, on_delete=models.CASCADE)
    
class OrganizationTheme(SoftDeleteModel):
    organization_id =  models.ForeignKey(Organization, on_delete=models.CASCADE)
    customer_journey_button_first_color = models.CharField(max_length=500, null=True, blank=True)
    customer_journey_button_second_color = models.CharField(max_length=500, null=True,blank=True)
    general_button_first_color = models.CharField(max_length=500, null=True,blank=True)
    general_button_second_color = models.CharField(max_length=500, null=True, blank=True)
    background_color = models.CharField(max_length=500, null=True, blank=True)
    nav_bar_text_color = models.CharField(max_length=500, null=True, blank=True)
    nav_bar_drop_down_color = models.CharField(max_length=500, null=True, blank=True)
    nav_bar_bg_color = models.CharField(max_length=500, null=True, blank=True)
    nav_bar_selected_text_color = models.CharField(max_length=500, null=True, blank=True)
    nav_bar_selected_bg_color = models.CharField(max_length=500, null=True, blank=True)
    loader_color = models.CharField(max_length=500, null=True, blank=True)
    template_id = models.ForeignKey(LookupTemplate, on_delete=models.CASCADE, null= True)
    customer_journey_text_color = models.CharField(max_length=500, null=True, blank=True)
    general_button_text_color = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = 'organization_theme'
        ordering = ['-created_at']

    def __str__(self):
        return str(self.organization_id.organization_name)

class LookupAirports(SoftDeleteModel):
    name = models.CharField(max_length=300, null = True)
    code = models.CharField(max_length=300 , null = True)
    city = models.CharField(max_length=300 , null = True)
    country = models.ForeignKey(LookupCountry, on_delete=models.CASCADE, null = True)
    index = models.IntegerField(null = True)
    common = models.CharField(max_length=400 , null=True)
    latitude = models.FloatField(null = True)
    longitude = models.FloatField(null = True)
    nearest = ArrayField(models.CharField(max_length=2000), null= True)
    timezone =  models.CharField(max_length=60 , null = True)
    def __str__(self):
        return str(self.name)
    class Meta:
        db_table = 'lookup_airports'
        ordering = ['-created_at']

class CountryDefault(SoftDeleteModel):
    country_id = models.ForeignKey(Country, on_delete=models.CASCADE, null =True)
    flights = models.JSONField(null=True, blank= True)
    hotels = models.JSONField(null=True, blank= True)
    holiday =  models.JSONField(null=True, blank= True)
    visa =  models.JSONField(null=True, blank= True)
    def __str__(self):
        return str(self.country_id.lookup.country_name)
    class Meta:
        db_table = 'country_default'
        ordering = ['-created_at']



class ErrorLogAdvanced(models.Model):

    error_message = models.TextField()  
    traceback = models.TextField()  
    

    path = models.CharField(max_length=255)  
    method = models.CharField(max_length=10)  
    user = models.ForeignKey(UserDetails, null=True, blank=True, on_delete=models.SET_NULL) 
    

    headers = models.TextField()  
    query_params = models.TextField()  
    post_data = models.TextField()  
    

    timestamp = models.DateTimeField(auto_now_add=True)  
    meta_info= models.JSONField(null=True)
    user_agent=models.TextField(null=True)  
    os_name=models.TextField(null=True)  
    device_type=models.TextField(null=True)  

    def __str__(self):
        return f"Error at {self.timestamp} on {self.path}"
    
    
class LookupAirline(SoftDeleteModel):
    name = models.CharField(max_length=500, null = True)
    code = models.CharField(max_length=500 , null = True)
    def __str__(self):
        return str(self.name)
    class Meta:
        db_table = 'lookup_airline'
        ordering = ['-created_at']

class CountryTax(SoftDeleteModel):
    country_id = models.ForeignKey(Country, on_delete=models.CASCADE, null = True)
    tax = models.FloatField(default= 0)
    tds = models.FloatField(default= 0)

    class Meta:
        db_table = 'country_tax'
        ordering = ['-created_at']



import time
from datetime import datetime
import pytz
class ProxyLog(SoftDeleteModel):
    operation_team_user =  models.ForeignKey(UserDetails, on_delete=models.CASCADE, related_name="operation_team_user") # loged in user 
    proxy_user = models.ForeignKey(UserDetails, on_delete=models.CASCADE,related_name="proxy_user") # to whom the user requested for access
    start_time_epoch = models.BigIntegerField(null=True, editable=False)
    valid_till_epoch = models.BigIntegerField(null=True, editable=False)
    end_time_epoch = models.TextField(null=True)
    
    start_time= models.DateTimeField(null=True)
    valid_till = models.DateTimeField(null=True)
    end_time = models.TextField(null=True)
    
    additional_log = models.JSONField(null=True)
    
    def save(self, *args, **kwargs):
        if self._state.adding:  # Check if this is a new instance
            self.start_time_epoch = time.time()
            self.valid_till_epoch = self.start_time_epoch + 1800  # Add 30 minutes
            ist_timezone = pytz.timezone('Asia/Kolkata')
            self.start_time = datetime.fromtimestamp(self.start_time_epoch, ist_timezone)
            self.valid_till = datetime.fromtimestamp(self.valid_till_epoch, ist_timezone)
            self.additional_log = {
                "system generated": f" user {self.operation_team_user.first_name}\ requested token for {self.proxy_user.first_name}\
                from organization : {self.proxy_user.organization.organization_name}"
            }
        return super(ProxyLog, self).save(*args, **kwargs)
    
    class Meta:
        db_table = 'proxy_log'
        ordering = ['-created_at']


class OutApiDetail(SoftDeleteModel):
    status_choice = [ 
                ("Approved", "Approved"),
                ("Rejected", "Rejected"),
                ("Pending", "Pending")
                ]
    status = models.CharField(max_length=200, choices=status_choice)
    token = models.CharField(max_length= 1000, null=True, blank =True)
    exp_time_epoch = models.BigIntegerField(null=True, blank =True)
    organization =  models.ForeignKey(Organization, on_delete=models.CASCADE)
    class Meta:
        db_table = 'out_api_detail'
        ordering = ['-created_at']
    def __str__(self):
        return str(self.organization.organization_name)
class APICriticalTransactionLog(SoftDeleteModel):
    user = models.ForeignKey(UserDetails, on_delete = models.CASCADE, null =True, blank=True)
    payload = models.JSONField(null=True, blank=True)
    url = models.CharField(max_length= 400, null=True, blank =True)
    type = models.CharField(max_length= 400, null=True, blank =True)
    created_time = models.BigIntegerField(null=True, editable=False)
    class Meta:
        db_table = 'api_critical_transaction_log'
        ordering = ['-created_at']
    def __str__(self):
        user_name = self.user.first_name if self.user else "Unknown User"
        return f"{user_name} - {self.url} - {self.type}"
#

from integrations.suppliers.models import SupplierIntegration
from django.db.models.functions import Upper, Lower
class WhiteLabelPage(SoftDeleteModel):
    slug_url = models.CharField(max_length=500)
    heading = models.CharField(max_length=1000)
    html_content = models.TextField()
    css_style = models.TextField(null=True, blank=True)
    js_code = models.TextField(null=True, blank=True)
    page_content = models.TextField()
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    whitelabel = models.ForeignKey(WhiteLabel, on_delete=models.CASCADE, null =True, blank = True)
    def __str__(self):
        return f"{self.organization.organization_name} - {self.slug_url} - {self.whitelabel.host}"

    class Meta:
        db_table = 'white_label_page'
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(
            Lower('slug_url'),
            'whitelabel',
            name = 'unique_slug_url_whitelabel_host'
        )]

class FareManagement(SoftDeleteModel):
    supplier_id = models.ForeignKey(SupplierIntegration,  on_delete=models.CASCADE)
    supplier_fare_name = models.CharField(max_length=500)
    brand_name = models.CharField(max_length=500)
    priority = models.IntegerField()
    class Meta:
        db_table = 'fare_management'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                Upper('supplier_fare_name'),
                'supplier_id',
                name='unique_supplier_id_fare_name')
            # ),
            # models.UniqueConstraint(
            #     Upper('brand_name'),
            #     'priority',
            #     name='unique_UniqueConstraint_priority')
        ]
    def __str__(self):
        return f"{self.brand_name} - {self.supplier_id.name} - {self.supplier_fare_name}"