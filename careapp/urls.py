from django.urls import path
from . import views

urlpatterns = [
    # Dashboard URLs
    path('', views.dashboard, name='dashboard'),
    path('management-dashboard/', views.management_dashboard, name='management_dashboard'),
    path('staff-dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('cqc-dashboard/', views.cqc_dashboard, name='cqc_dashboard'),
    path('login-redirect/', views.custom_login_redirect, name='custom_login_redirect'),
    
    # Service User URLs
    path('service-users/', views.ServiceUserListView.as_view(), name='serviceuser_list'),
    path('service-users/create/', views.ServiceUserCreateView.as_view(), name='serviceuser_create'),
    path('service-users/<int:pk>/', views.ServiceUserDetailView.as_view(), name='serviceuser_detail'),
    path('service-users/<int:pk>/update/', views.ServiceUserUpdateView.as_view(), name='serviceuser_update'),
    path('service-users/<int:pk>/toggle-active/', views.service_user_toggle_active, name='serviceuser_toggle_active'),
    
    # Care Plan URLs
    path('careplans/', views.CarePlanListView.as_view(), name='careplan_list'),
    path('careplan/create/<int:service_user_id>/', views.CarePlanCreateView.as_view(), name='careplan_create'),
    path('careplan/update/<int:service_user_id>/', views.CarePlanUpdateView.as_view(), name='careplan_update'),
    path('careplan/view/<int:service_user_id>/', views.CarePlanDetailView.as_view(), name='careplan_detail'),
    
    # PBS Plan URLs
    path('pbsplans/', views.PBSPlanListView.as_view(), name='pbsplan_list'),
    path('pbsplan/create/<int:service_user_id>/', views.PBSPlanCreateView.as_view(), name='pbsplan_create'),
    path('pbsplan/update/<int:service_user_id>/', views.PBSPlanUpdateView.as_view(), name='pbsplan_update'),
    path('pbsplan/view/<int:service_user_id>/', views.PBSPlanDetailView.as_view(), name='pbsplan_detail'),
    
    # Risk Assessment URLs
    path('risk-assessments/', views.RiskAssessmentListView.as_view(), name='riskassessment_list'),
    path('risk-assessment/create/<int:service_user_id>/', views.RiskAssessmentCreateView.as_view(), name='riskassessment_create'),
    path('risk-assessment/<int:pk>/', views.RiskAssessmentDetailView.as_view(), name='riskassessment_detail'),
    path('risk-assessment/<int:pk>/update/', views.RiskAssessmentUpdateView.as_view(), name='riskassessment_update'),
    path('risk-assessment/<int:pk>/toggle-active/', views.risk_assessment_toggle_active, name='riskassessment_toggle_active'),
    
    # Activity URLs
    path('activities/', views.ActivityListView.as_view(), name='activity_list'),
    path('activities/create/', views.ActivityCreateView.as_view(), name='activity_create'),
    path('activities/<int:pk>/', views.activity_detail, name='activity_detail'),
    path('activities/<int:pk>/update/', views.ActivityUpdateView.as_view(), name='activity_update'),
    path('activities/<int:pk>/complete/', views.mark_activity_completed, name='activity_complete'),
    
    # Medication URLs
    path('medications/', views.MedicationListView.as_view(), name='medication_list'),
    path('medications/create/', views.MedicationCreateView.as_view(), name='medication_create'),
    path('medications/<int:pk>/', views.MedicationDetailView.as_view(), name='medication_detail'),
    path('medications/<int:pk>/update/', views.MedicationUpdateView.as_view(), name='medication_update'),



    path('medications/<int:pk>/toggle-active/', views.medication_toggle_active, name='medication_toggle_active'),   
    
    # Medication Administration URLs
    path('medication/dashboard/', 
         views.MedicationDashboardView.as_view(), 
         name='medication_dashboard'),
    path('medication/administration/', 
         views.MedicationAdministrationCreateView.as_view(), 
         name='medication_administration_create'),
    path('medication/administration/<int:medication_id>/', 
         views.MedicationAdministrationCreateView.as_view(), 
         name='medication_administration_create_for_med'),
    path('medication/administration/list/', 
         views.MedicationAdministrationListView.as_view(), 
         name='medication_administration_list'),
    path('medication/administration/<int:pk>/', 
         views.MedicationAdministrationDetailView.as_view(), 
         name='medication_administration_detail'),
    path('api/medication/<int:medication_id>/details/', 
         views.medication_details_api, 
         name='medication_details_api'),
    
    # Incident URLs
    path('incidents/', views.IncidentListView.as_view(), name='incident_list'),
    path('incidents/create/', views.IncidentCreateView.as_view(), name='incident_create'),
    path('incidents/<int:pk>/', views.incident_detail, name='incident_detail'),
    path('incidents/<int:pk>/update/', views.IncidentUpdateView.as_view(), name='incident_update'),
    path('incidents/<int:pk>/toggle-follow-up/', views.incident_toggle_follow_up, name='incident_toggle_follow_up'),
    
    # Appointment URLs
    path('appointments/', views.AppointmentListView.as_view(), name='appointment_list'),
    path('appointments/create/', views.AppointmentCreateView.as_view(), name='appointment_create'),
    path('appointments/<int:pk>/', views.AppointmentDetailView.as_view(), name='appointment_detail'),
    path('appointments/<int:pk>/update/', views.AppointmentUpdateView.as_view(), name='appointment_update'),
    path('appointments/<int:pk>/complete/', views.mark_appointment_completed, name='appointment_complete'),
    
    # Visitor URLs
    path('visitors/', views.VisitorListView.as_view(), name='visitor_list'),
    path('visitors/create/', views.VisitorCreateView.as_view(), name='visitor_create'),
    path('visitors/<int:pk>/', views.VisitorDetailView.as_view(), name='visitor_detail'),
    path('visitors/<int:pk>/update/', views.VisitorUpdateView.as_view(), name='visitor_update'),
    
    # Trip URLs
    path('trips/', views.TripListView.as_view(), name='trip_list'),
    path('trips/create/', views.TripCreateView.as_view(), name='trip_create'),
    path('trips/<int:pk>/', views.trip_detail, name='trip_detail'),
    path('trips/<int:pk>/update/', views.TripUpdateView.as_view(), name='trip_update'),
    
    # Staff Member URLs
    path('staff/', views.staff_member_list, name='staff_member_list'),
    path('staff/create/', views.staff_member_create, name='staff_member_create'),
    path('staff/<int:pk>/', views.staff_member_detail, name='staff_member_detail'),
    path('staff/<int:pk>/edit/', views.staff_member_edit, name='staff_member_edit'),
    path('staff/<int:pk>/change-password/', views.staff_member_change_password, name='staff_member_change_password'),
    path('staff/<int:pk>/toggle-active/', views.staff_member_toggle_active, name='staff_member_toggle_active'),
    path('staff/<int:pk>/add-to-group/', views.staff_member_add_to_group, name='staff_member_add_to_group'),
    
    # CQC Member URLs
    path('cqc/', views.cqc_member_list, name='cqc_member_list'),
    path('cqc/create/', views.cqc_member_create, name='cqc_member_create'),
    path('cqc/<int:pk>/', views.cqc_member_detail, name='cqc_member_detail'),
    path('cqc/<int:pk>/edit/', views.cqc_member_edit, name='cqc_member_edit'),
    path('cqc/<int:pk>/change-password/', views.cqc_member_change_password, name='cqc_member_change_password'),
    path('cqc/<int:pk>/toggle-active/', views.cqc_member_toggle_active, name='cqc_member_toggle_active'),
    path('cqc/<int:pk>/add-to-group/', views.cqc_member_add_to_group, name='cqc_member_add_to_group'),
    
    # Department URLs
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', views.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/', views.DepartmentDetailView.as_view(), name='department_detail'),
    path('departments/<int:pk>/update/', views.DepartmentUpdateView.as_view(), name='department_update'),
    path('departments/<int:pk>/toggle-active/', views.department_toggle_active, name='department_toggle_active'),
    
    
    # Role URLs
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/create/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:pk>/', views.RoleDetailView.as_view(), name='role_detail'),
    path('roles/<int:pk>/update/', views.RoleUpdateView.as_view(), name='role_update'),
    
    # Staff Shift URLs
    path('staff-shifts/', views.StaffShiftListView.as_view(), name='staffshift_list'),
    path('staff-shifts/create/', views.StaffShiftCreateView.as_view(), name='staffshift_create'),
    path('staff-shifts/<int:pk>/update/', views.StaffShiftUpdateView.as_view(), name='staffshift_update'),
    path('staff-shifts/<int:pk>/', views.StaffShiftDetailView.as_view(), name='staffshift_detail'), 
    path('staff-shifts/<int:pk>/toggle-completed/', views.staff_shift_toggle_completed, name='staffshift_toggle_completed'),
    
    # Daily Summary URLs
    path('daily-summaries/', views.DailySummaryListView.as_view(), name='dailysummary_list'),
    path('daily-summaries/create/', views.DailySummaryCreateView.as_view(), name='dailysummary_create'),
    path('daily-summaries/<int:pk>/', views.daily_summary_detail, name='dailysummary_detail'),
    path('daily-summaries/<int:pk>/update/', views.DailySummaryUpdateView.as_view(), name='dailysummary_update'),

    # Staff Handover URLs
    path('staff-handovers/', views.StaffHandoverListView.as_view(), name='staffhandover_list'),
    path('staff-handovers/create/', views.StaffHandoverCreateView.as_view(), name='staffhandover_create'),
    path('staff-handovers/<int:pk>/', views.staff_handover_detail, name='staffhandover_detail'),
    path('staff-handovers/<int:pk>/update/', views.StaffHandoverUpdateView.as_view(), name='staffhandover_update'),
    path('staff-handovers/<int:pk>/acknowledge/', views.staff_handover_acknowledge, name='staffhandover_acknowledge'),
    
    # Management Daily Note URLs
    path('management-notes/', views.ManagementDailyNoteListView.as_view(), name='managementdailynote_list'),
    path('management-notes/create/', views.ManagementDailyNoteCreateView.as_view(), name='managementdailynote_create'),
    path('management-notes/<int:pk>/update/', views.ManagementDailyNoteUpdateView.as_view(), name='managementdailynote_update'),
    path('management-notes/<int:pk>/resolve/', views.management_daily_note_resolve, name='managementdailynote_resolve'),
    path('management-notes/<int:pk>/', views.ManagementDailyNoteDetailView.as_view(), name='managementdailynote_detail'), 
    
    # Management Handover URLs
    path('management-handovers/', views.ManagementHandoverListView.as_view(), name='managementhandover_list'),
    path('management-handovers/create/', views.ManagementHandoverCreateView.as_view(), name='managementhandover_create'),
    path('management-handovers/<int:pk>/', views.management_handover_detail, name='managementhandover_detail'),
    path('management-handovers/<int:pk>/update/', views.ManagementHandoverUpdateView.as_view(), name='managementhandover_update'),
    path('management-handovers/<int:pk>/acknowledge/', views.management_handover_acknowledge, name='managementhandover_acknowledge'),
    
    # Governance Record URLs
    path('governance-records/', views.GovernanceRecordListView.as_view(), name='governancerecord_list'),
    path('governance-records/create/', views.GovernanceRecordCreateView.as_view(), name='governancerecord_create'),
    path('governance-records/<int:pk>/', views.governance_record_detail, name='governancerecord_detail'),
    path('governance-records/<int:pk>/update/', views.GovernanceRecordUpdateView.as_view(), name='governancerecord_update'),
    
    # Vital Signs URLs
    path('vital-signs/', views.VitalSignsListView.as_view(), name='vitalsigns_list'),
    path('vital-signs/create/', views.VitalSignsCreateView.as_view(), name='vitalsigns_create'),
    path('vital-signs/<int:pk>/', views.vital_signs_detail, name='vitalsigns_detail'),
    path('vital-signs/<int:pk>/update/', views.VitalSignsUpdateView.as_view(), name='vitalsigns_update'),
    
    # Document URLs
    path('documents/', views.DocumentListView.as_view(), name='document_list'),
    path('documents/create/', views.DocumentCreateView.as_view(), name='document_create'),
    path('documents/<int:pk>/', views.document_detail, name='document_detail'),
    path('documents/<int:pk>/update/', views.DocumentUpdateView.as_view(), name='document_update'),
    path('documents/<int:pk>/download/', views.document_download, name='document_download'),
    
    # System Setting URLs
    path('system-settings/', views.SystemSettingListView.as_view(), name='systemsetting_list'),
    path('system-settings/<int:pk>/update/', views.SystemSettingUpdateView.as_view(), name='systemsetting_update'),
    
    # Security Dashboard URL
    path('security-dashboard/', views.security_dashboard, name='security_dashboard'),
    path('security-dashboard/data/', views.security_dashboard_data, name='security_dashboard_data'),
    path('security-dashboard/report/', views.security_report, name='security_report'),
    path('security-dashboard/block-ip/', views.block_ip_address, name='block_ip_address'),
    path('security-logs/search/', views.security_logs_search, name='security_logs_search'),
    path('security-event/<int:event_id>/', views.security_event_detail, name='security_event_detail'),
    path('ip-investigation/', views.ip_investigation, name='ip_investigation'),
    
    # Report Generation URLs
    path('reports/daily-activities/', views.generate_report, {'report_type': 'daily_activities'}, name='report_daily_activities'),
    path('reports/medication/', views.generate_report, {'report_type': 'medication'}, name='report_medication'),
    path('reports/incidents/', views.generate_report, {'report_type': 'incidents'}, name='report_incidents'),
    path('reports/staff-shifts/', views.generate_report, {'report_type': 'staff_shifts'}, name='report_staff_shifts'),
    path(
        'medication-administration/export/', 
        views.export_medication_administrations, 
        name='export_medication_administrations'
    ),
]