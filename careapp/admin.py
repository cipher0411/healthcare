from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    ServiceUser, CarePlan, PBSPlan, StaffMember, Activity, ActivityPhoto,
    Medication, MedicationAdministration, Incident, Appointment, Visitor,
    Trip, SecurityLog, Department, Role, StaffShift, DailySummary,
    ManagementDailyNote, ManagementHandover, GovernanceRecord, VitalSigns,
    RiskAssessment, CQCMember, Document, AuditLog, SystemSetting, Notification
)


# Custom User Admin to display related StaffMember and CQCMember
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'staff_member_link', 'cqc_member_link')
    list_filter = ('is_staff', 'is_active', 'is_superuser', 'groups')
    
    def staff_member_link(self, obj):
        if hasattr(obj, 'staffmember'):
            url = reverse('admin:careapp_staffmember_change', args=[obj.staffmember.id])
            return format_html('<a href="{}">{}</a>', url, obj.staffmember.staff_id)
        return "—"
    staff_member_link.short_description = 'Staff Member'
    
    def cqc_member_link(self, obj):
        if hasattr(obj, 'cqcmember'):
            url = reverse('admin:careapp_cqcmember_change', args=[obj.cqcmember.id])
            return format_html('<a href="{}">{}</a>', url, obj.cqcmember.cqc_id)
        return "—"
    cqc_member_link.short_description = 'CQC Member'


# Unregister default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# Department Admin
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'manager', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    raw_id_fields = ('manager',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Role Admin
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_management', 'can_manage_staff', 'can_view_reports', 'can_manage_care_plans', 'can_manage_medications')
    list_filter = ('is_management', 'can_manage_staff', 'can_view_reports', 'can_manage_care_plans', 'can_manage_medications')
    search_fields = ('name', 'description')
    filter_horizontal = ('permissions',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Staff Member Admin
@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ('staff_id', 'user', 'position', 'department', 'is_active', 'start_date')
    list_filter = ('is_active', 'department', 'role', 'start_date')
    search_fields = ('user__first_name', 'user__last_name', 'staff_id', 'position')
    raw_id_fields = ('user', 'department', 'role')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'staff_id')
    fieldsets = (
        ('Personal Information', {
            'fields': ('user', 'staff_id', 'photo', 'phone_number')
        }),
        ('Employment Details', {
            'fields': ('department', 'role', 'position', 'qualifications', 'start_date', 'end_date')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship')
        }),
        ('Background Checks', {
            'fields': ('dbs_check_date', 'dbs_check_reference', 'training_records')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# CQC Member Admin
@admin.register(CQCMember)
class CQCMemberAdmin(admin.ModelAdmin):
    list_display = ('cqc_id', 'name', 'email', 'can_view_incidents', 'can_view_audit_logs', 'is_active')
    list_filter = ('is_active', 'can_view_incidents', 'can_view_audit_logs', 'can_view_care_plans', 'can_download_reports')
    search_fields = ('name', 'cqc_id', 'email')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'cqc_id', 'last_access')
    fieldsets = (
        ('Personal Information', {
            'fields': ('user', 'cqc_id', 'name', 'email', 'phone_number')
        }),
        ('Access Permissions', {
            'fields': ('can_view_incidents', 'incident_view_delay_hours', 'can_view_audit_logs', 
                      'can_view_care_plans', 'can_download_reports')
        }),
        ('Status', {
            'fields': ('is_active', 'last_access')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Service User Admin
class CarePlanInline(admin.StackedInline):
    model = CarePlan
    extra = 0
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


class PBSPlanInline(admin.StackedInline):
    model = PBSPlan
    extra = 0
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


class RiskAssessmentInline(admin.TabularInline):
    model = RiskAssessment
    extra = 0
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(ServiceUser)
class ServiceUserAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'room_number', 'age', 'admission_date', 'is_active', 'key_worker')
    list_filter = ('is_active', 'gender', 'marital_status', 'admission_date')
    search_fields = ('first_name', 'last_name', 'room_number', 'unique_id')
    raw_id_fields = ('key_worker',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'unique_id', 'age')
    inlines = [CarePlanInline, PBSPlanInline, RiskAssessmentInline]
    fieldsets = (
        ('Personal Information', {
            'fields': ('unique_id', 'first_name', 'last_name', 'date_of_birth', 'gender', 'marital_status', 'photo', 'bio')
        }),
        ('Residence Details', {
            'fields': ('admission_date', 'room_number', 'bed_number', 'is_active', 'discharge_date', 'discharge_reason')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone_number', 'emergency_contact_name', 'emergency_contact_phone', 
                      'emergency_contact_relationship', 'emergency_contact_address')
        }),
        ('Next of Kin', {
            'fields': ('next_of_kin_name', 'next_of_kin_phone', 'next_of_kin_relationship')
        }),
        ('Medical Information', {
            'fields': ('allergies', 'medical_conditions', 'special_requirements', 'dietary_restrictions',
                      'mobility_requirements', 'communication_needs')
        }),
        ('Legal Documents', {
            'fields': ('has_advanced_directive', 'advanced_directive_details', 'has_power_of_attorney', 'power_of_attorney_details')
        }),
        ('Financial Information', {
            'fields': ('funding_source', 'key_worker')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Care Plan Admin
@admin.register(CarePlan)
class CarePlanAdmin(admin.ModelAdmin):
    list_display = ('service_user', 'last_review_date', 'next_review_date', 'is_active', 'is_due_for_review')
    list_filter = ('is_active', 'last_review_date', 'next_review_date')
    search_fields = ('service_user__first_name', 'service_user__last_name')
    raw_id_fields = ('service_user',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'is_due_for_review')
    fieldsets = (
        ('Service User', {
            'fields': ('service_user',)
        }),
        ('Care Plan Details', {
            'fields': ('personal_care', 'mobility', 'nutrition', 'hydration', 'social_activities',
                      'medical_requirements', 'personal_goals', 'spiritual_needs', 'cultural_needs')
        }),
        ('Review Dates', {
            'fields': ('last_review_date', 'next_review_date', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# PBS Plan Admin
@admin.register(PBSPlan)
class PBSPlanAdmin(admin.ModelAdmin):
    list_display = ('service_user', 'last_review_date', 'next_review_date', 'is_active')
    list_filter = ('is_active', 'last_review_date', 'next_review_date')
    search_fields = ('service_user__first_name', 'service_user__last_name')
    raw_id_fields = ('service_user',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Risk Assessment Admin
@admin.register(RiskAssessment)
class RiskAssessmentAdmin(admin.ModelAdmin):
    list_display = ('service_user', 'category', 'risk_level', 'date_assessed', 'review_date', 'is_active')
    list_filter = ('is_active', 'risk_level', 'category', 'date_assessed')
    search_fields = ('service_user__first_name', 'service_user__last_name', 'category')
    raw_id_fields = ('service_user',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Staff Shift Admin
@admin.register(StaffShift)
class StaffShiftAdmin(admin.ModelAdmin):
    list_display = ('staff_member', 'shift_date', 'shift_type', 'start_time', 'end_time', 'is_completed')
    list_filter = ('is_completed', 'shift_type', 'shift_date')
    search_fields = ('staff_member__user__first_name', 'staff_member__user__last_name')
    raw_id_fields = ('staff_member',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Daily Summary Admin
@admin.register(DailySummary)
class DailySummaryAdmin(admin.ModelAdmin):
    list_display = ('shift', 'shift_date', 'staff_member')
    list_filter = ('shift__shift_date',)
    search_fields = ('shift__staff_member__user__first_name', 'shift__staff_member__user__last_name')
    raw_id_fields = ('shift',)
    filter_horizontal = ('service_users_present',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def shift_date(self, obj):
        return obj.shift.shift_date
    shift_date.short_description = 'Shift Date'
    
    def staff_member(self, obj):
        return obj.shift.staff_member
    staff_member.short_description = 'Staff Member'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Activity Admin with Photos Inline
class ActivityPhotoInline(admin.TabularInline):
    model = ActivityPhoto
    extra = 0
    readonly_fields = ('uploaded_at',)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('title', 'service_user', 'activity_type', 'date', 'start_time', 'is_completed')
    list_filter = ('is_completed', 'activity_type', 'date')
    search_fields = ('title', 'service_user__first_name', 'service_user__last_name')
    raw_id_fields = ('service_user',)
    filter_horizontal = ('staff_involved',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    inlines = [ActivityPhotoInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('service_user', 'activity_type', 'title', 'description')
        }),
        ('Schedule', {
            'fields': ('date', 'start_time', 'end_time', 'location')
        }),
        ('Staff', {
            'fields': ('staff_involved',)
        }),
        ('Meal Details (if applicable)', {
            'fields': ('meal_type', 'food_consumed', 'fluid_intake', 'appetite_level'),
            'classes': ('collapse',)
        }),
        ('Appointment Details (if applicable)', {
            'fields': ('provider', 'notes', 'is_completed'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Medication Admin
class MedicationAdministrationInline(admin.TabularInline):
    model = MedicationAdministration
    extra = 0
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'service_user', 'medication_type', 'dosage', 'frequency', 'start_date', 'is_active')
    list_filter = ('is_active', 'medication_type', 'is_controlled_drug', 'start_date')
    search_fields = ('name', 'service_user__first_name', 'service_user__last_name')
    raw_id_fields = ('service_user',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'current_balance')
    inlines = [MedicationAdministrationInline]
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Medication Administration Admin
@admin.register(MedicationAdministration)
class MedicationAdministrationAdmin(admin.ModelAdmin):
    list_display = ('medication', 'administered_by', 'administered_date', 'administered_time', 'status')
    list_filter = ('status', 'administered_date')
    search_fields = ('medication__name', 'administered_by__user__first_name', 'administered_by__user__last_name')
    raw_id_fields = ('medication', 'administered_by', 'witness')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Incident Admin
@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('incident_type', 'service_user', 'date', 'time', 'severity', 'follow_up_required', 'cqc_viewable_after')
    list_filter = ('incident_type', 'severity', 'follow_up_required', 'date', 'cqc_can_view')
    search_fields = ('title', 'service_user__first_name', 'service_user__last_name')
    raw_id_fields = ('service_user',)
    filter_horizontal = ('staff_involved',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'cqc_viewable_after')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Appointment Admin
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'service_user', 'appointment_type', 'date', 'start_time', 'is_completed')
    list_filter = ('appointment_type', 'is_completed', 'date')
    search_fields = ('title', 'service_user__first_name', 'service_user__last_name')
    raw_id_fields = ('service_user',)
    filter_horizontal = ('staff_accompanying',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Visitor Admin
@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ('visitor_name', 'service_user', 'visit_date', 'arrival_time', 'covid_screening_passed')
    list_filter = ('covid_screening_passed', 'visit_date')
    search_fields = ('visitor_name', 'service_user__first_name', 'service_user__last_name')
    raw_id_fields = ('service_user',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Trip Admin
@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('destination', 'date', 'departure_time', 'risk_assessment_completed')
    list_filter = ('risk_assessment_completed', 'date')
    search_fields = ('destination', 'purpose')
    filter_horizontal = ('service_users', 'staff_accompanying')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Management Daily Note Admin
@admin.register(ManagementDailyNote)
class ManagementDailyNoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'priority', 'action_required', 'is_resolved', 'created_at')
    list_filter = ('priority', 'action_required', 'is_resolved', 'created_at', 'related_department')
    search_fields = ('title', 'note')
    raw_id_fields = ('related_department', 'related_service_user', 'related_staff', 'resolved_by')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'resolved_at')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Management Handover Admin
@admin.register(ManagementHandover)
class ManagementHandoverAdmin(admin.ModelAdmin):
    list_display = ('handed_over_by', 'handed_over_to', 'handover_date', 'acknowledged', 'acknowledged_at')
    list_filter = ('acknowledged', 'handover_date')
    search_fields = ('handed_over_by__user__first_name', 'handed_over_to__user__first_name', 'notes')
    raw_id_fields = ('handed_over_by', 'handed_over_to')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'acknowledged_at')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Governance Record Admin
@admin.register(GovernanceRecord)
class GovernanceRecordAdmin(admin.ModelAdmin):
    list_display = ('title', 'record_type', 'date_occurred', 'follow_up_required', 'is_confidential')
    list_filter = ('record_type', 'follow_up_required', 'is_confidential', 'date_occurred', 'related_department')
    search_fields = ('title', 'description')
    raw_id_fields = ('related_department', 'related_service_user', 'related_staff')
    filter_horizontal = ('documents',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Vital Signs Admin
@admin.register(VitalSigns)
class VitalSignsAdmin(admin.ModelAdmin):
    list_display = ('service_user', 'recorded_by', 'recorded_date', 'recorded_time', 'temperature', 'pulse', 'blood_pressure')
    list_filter = ('recorded_date',)
    search_fields = ('service_user__first_name', 'service_user__last_name', 'recorded_by__user__first_name')
    raw_id_fields = ('service_user', 'recorded_by')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def blood_pressure(self, obj):
        if obj.blood_pressure_systolic and obj.blood_pressure_diastolic:
            return f"{obj.blood_pressure_systolic}/{obj.blood_pressure_diastolic}"
        return "—"
    blood_pressure.short_description = 'Blood Pressure'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Document Admin
@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'document_type', 'service_user', 'effective_date', 'expiry_date', 'is_confidential', 'is_expired')
    list_filter = ('document_type', 'is_confidential', 'cqc_can_view', 'effective_date')
    search_fields = ('title', 'description', 'service_user__first_name', 'service_user__last_name')
    raw_id_fields = ('service_user',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'is_expired')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Audit Log Admin
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'object_id', 'created_at', 'cqc_can_view')
    list_filter = ('action', 'model_name', 'cqc_can_view', 'created_at')
    search_fields = ('user__username', 'model_name', 'object_id')
    readonly_fields = ('user', 'action', 'model_name', 'object_id', 'details', 'ip_address', 'cqc_can_view', 'created_at')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# Security Log Admin
@admin.register(SecurityLog)
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'action', 'status', 'timestamp')
    list_filter = ('status', 'action', 'timestamp')
    search_fields = ('user__username', 'ip_address', 'action')
    readonly_fields = ('user', 'ip_address', 'user_agent', 'timestamp', 'action', 'status', 'details')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# System Setting Admin
@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('key', 'description')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Notification Admin
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'title', 'priority', 'is_read', 'created_at')
    list_filter = ('priority', 'is_read', 'created_at')
    search_fields = ('recipient__username', 'title', 'message')
    raw_id_fields = ('recipient',)
    readonly_fields = ('created_at', 'updated_at', 'read_at')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)



from django.contrib import admin
from .models import StaffHandover

@admin.register(StaffHandover)
class StaffHandoverAdmin(admin.ModelAdmin):
    list_display = ('shift_date', 'shift_type', 'handed_over_by', 'handed_over_to', 'priority', 'acknowledged')
    list_filter = ('shift_date', 'shift_type', 'priority', 'acknowledged')
    search_fields = ('handed_over_by__user__first_name', 'handed_over_by__user__last_name', 
                    'handed_over_to__user__first_name', 'handed_over_to__user__last_name')
    filter_horizontal = ('service_users_covered',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'acknowledged_at')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Custom Admin Site Settings
admin.site.site_header = "Ci-Wellbeing Care Management System Administration"
admin.site.site_title = "Care Management System"
admin.site.index_title = "Welcome to Care Management System Administration"