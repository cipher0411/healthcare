import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Count, Sum, F
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth.models import Group
from django.db.models import Q
from django.core.mail import send_mail
from django.template.loader import render_to_string
from datetime import timedelta
from django.core.paginator import Paginator
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm as AuthPasswordChangeForm
from django.views.generic import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils.crypto import get_random_string
from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm



from .models import (
    ServiceUser, CarePlan, PBSPlan, StaffMember, Activity, 
    ActivityPhoto, Medication, MedicationAdministration, 
    Incident, Appointment, Visitor, Trip, SecurityLog, Department,
    Role, StaffShift, DailySummary, ManagementDailyNote, ManagementHandover,
    GovernanceRecord, VitalSigns, RiskAssessment, CQCMember, Document,
    AuditLog, SystemSetting, Notification, TimeStampedModel, StaffHandover
)
from .forms import (
    ServiceUserForm, CarePlanForm, PBSPlanForm, StaffMemberForm,
    ActivityForm, MedicationForm, MedicationAdministrationForm,
    IncidentForm, AppointmentForm, VisitorForm, TripForm, DepartmentForm,
    RoleForm, StaffShiftForm, DailySummaryForm, ManagementDailyNoteForm,
    ManagementHandoverForm, GovernanceRecordForm, VitalSignsForm,
    RiskAssessmentForm, CQCMemberForm, DocumentForm, SystemSettingForm, StaffHandoverForm
)
from .utils import log_security_event, is_management, is_staff, get_client_ip, is_staff_or_management

logger = logging.getLogger(__name__)


# Utility function to check if user is CQC member
def is_cqc(user):
    return user.groups.filter(name='CQC_Members').exists()



@login_required
def custom_login_redirect(request):
    """Custom login redirect that sends users to their appropriate dashboard based on role"""
    if request.user.is_superuser:
        redirect_url = 'dashboard'
        role = 'admin'
    elif is_management(request.user):
        redirect_url = 'management_dashboard'
        role = 'management'
    elif is_staff(request.user):
        redirect_url = 'staff_dashboard'
        role = 'staff'
    elif is_cqc(request.user):
        redirect_url = 'cqc_dashboard'
        role = 'cqc'
    else:
        redirect_url = 'dashboard'
        role = 'unknown'
    
    # Log the login redirect
    log_security_event(
        request, 
        "Login Redirect", 
        "Success", 
        {"user_id": request.user.id, "username": request.user.username, "role": role, "redirect_to": redirect_url}
    )
    
    return redirect(redirect_url)


# Dashboard views for different user types
@login_required
def dashboard(request):
    """Main dashboard that redirects to appropriate dashboard based on user role"""
    if is_management(request.user):
        return redirect('management_dashboard')
    elif is_staff(request.user):
        return redirect('staff_dashboard')
    elif is_cqc(request.user):
        return redirect('cqc_dashboard')
    else:
        # Default dashboard for users without specific roles
        return render(request, 'careapp/dashboard.html', {})


@login_required
@user_passes_test(is_management)
def management_dashboard(request):
    """Dashboard for management users"""
    today = timezone.now().date()
    
    # Get statistics
    active_service_users = ServiceUser.objects.filter(is_active=True).count()
    active_staff = StaffMember.objects.filter(is_active=True).count()
    today_activities = Activity.objects.filter(date=today).count()
    pending_incidents = Incident.objects.filter(follow_up_required=True).count()
    
    # Get recent management notes
    recent_notes = ManagementDailyNote.objects.filter(
        action_required=True, is_resolved=False
    ).order_by('-created_at')[:5]
    
    # Get upcoming handovers
    upcoming_handovers = ManagementHandover.objects.filter(
        handover_date__gte=today
    ).order_by('handover_date')[:5]
    
    # Get governance records needing attention
    governance_issues = GovernanceRecord.objects.filter(
        follow_up_required=True
    ).order_by('-created_at')[:5]
    
    context = {
        'active_service_users': active_service_users,
        'active_staff': active_staff,
        'today_activities': today_activities,
        'pending_incidents': pending_incidents,
        'recent_notes': recent_notes,
        'upcoming_handovers': upcoming_handovers,
        'governance_issues': governance_issues,
    }
    
    # Log dashboard access
    log_security_event(
        request, 
        "Management Dashboard Access", 
        "Success", 
        {"page": "management_dashboard"}
    )
    
    return render(request, 'careapp/management_dashboard.html', context)

from datetime import datetime, timedelta

@login_required
@user_passes_test(is_staff)
def staff_dashboard(request):
    """Dashboard for staff users"""
    # Get selected date from request or default to today
    selected_date = request.GET.get('date', timezone.now().date().isoformat())
    try:
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        selected_date = timezone.now().date()
    
    try:
        staff_member = StaffMember.objects.get(user=request.user)
    except StaffMember.DoesNotExist:
        messages.error(request, "Staff profile not found. Please contact administrator.")
        return redirect('dashboard')
    
    # Get assigned service users
    assigned_service_users = ServiceUser.objects.filter(
        key_worker=staff_member, is_active=True
    )
    
    # Get data for each service user for the selected date
    service_users_data = []
    for service_user in assigned_service_users:
        # Get activities for the selected date
        activities = Activity.objects.filter(
            service_user=service_user,
            date=selected_date
        ).order_by('-created_at')
        
        # Get medications for the service user
        medications = Medication.objects.filter(
            service_user=service_user,
            is_active=True
        ).order_by('-created_at')
        
        # Get incidents for the selected date
        incidents = Incident.objects.filter(
            service_user=service_user,
            date=selected_date
        ).order_by('-created_at')
        
        # Get visitors for the selected date
        visitors = Visitor.objects.filter(
            service_user=service_user,
            visit_date=selected_date
        ).order_by('-created_at')
        
        # Get trips for the selected date
        trips = Trip.objects.filter(
            service_users=service_user,
            date=selected_date
        ).order_by('-created_at')
        
        # Get daily summaries for the selected date
        daily_summaries = DailySummary.objects.filter(
            shift__shift_date=selected_date,
            service_users_present=service_user
        ).order_by('-created_at')
        
        # Get handovers that mention this service user for the selected date
        handovers = StaffHandover.objects.filter(
            shift_date=selected_date,
            service_users_covered=service_user
        ).order_by('-created_at')
        
        # Get appointments for the selected date
        appointments = Appointment.objects.filter(
            service_user=service_user,
            date=selected_date
        ).order_by('-created_at')
        
        # Get vital signs for the selected date
        vital_signs = VitalSigns.objects.filter(
            service_user=service_user,
            recorded_date=selected_date
        ).order_by('-created_at')
        
        service_users_data.append({
            'service_user': service_user,
            'activities': activities,
            'medications': medications,
            'incidents': incidents,
            'visitors': visitors,
            'trips': trips,
            'daily_summaries': daily_summaries,
            'handovers': handovers,
            'appointments': appointments,
            'vital_signs': vital_signs,
        })
    
    # Get previous and next dates for navigation
    prev_date = selected_date - timedelta(days=1)
    next_date = selected_date + timedelta(days=1)
    
    # Check if next_date is in the future
    if next_date > timezone.now().date():
        next_date = None
    
    context = {
        'staff_member': staff_member,
        'selected_date': selected_date,
        'prev_date': prev_date,
        'next_date': next_date,
        'service_users_data': service_users_data,
        'today': timezone.now().date(),
    }
    
    # Log dashboard access
    log_security_event(
        request, 
        "Staff Dashboard Access", 
        "Success", 
        {"page": "staff_dashboard", "staff_id": staff_member.staff_id, "date": selected_date.isoformat()}
    )
    
    return render(request, 'careapp/staff_dashboard.html', context)


@login_required
@user_passes_test(is_cqc)
def cqc_dashboard(request):
    """Dashboard for CQC users"""
    today = timezone.now().date()
    
    try:
        cqc_member = CQCMember.objects.get(user=request.user)
    except CQCMember.DoesNotExist:
        messages.error(request, "CQC profile not found. Please contact administrator.")
        return redirect('dashboard')
    
    # Get viewable incidents (based on delay setting)
    viewable_incidents = Incident.objects.filter(
        cqc_can_view=True,
        cqc_viewable_after__lte=timezone.now()
    ).order_by('-date')[:10]
    
    # Get accessible documents
    accessible_documents = Document.objects.filter(
        cqc_can_view=True
    ).order_by('-created_at')[:10]
    
    # Get recent audit logs if permitted
    recent_audit_logs = []
    if cqc_member.can_view_audit_logs:
        recent_audit_logs = AuditLog.objects.filter(
            cqc_can_view=True
        ).order_by('-created_at')[:10]
    
    # Get accessible care plans if permitted
    accessible_care_plans = []
    if cqc_member.can_view_care_plans:
        accessible_care_plans = CarePlan.objects.filter(
            is_active=True
        ).select_related('service_user')[:5]
    
    context = {
        'cqc_member': cqc_member,
        'viewable_incidents': viewable_incidents,
        'accessible_documents': accessible_documents,
        'recent_audit_logs': recent_audit_logs,
        'accessible_care_plans': accessible_care_plans,
    }
    
    # Log dashboard access
    log_security_event(
        request, 
        "CQC Dashboard Access", 
        "Success", 
        {"page": "cqc_dashboard", "cqc_id": cqc_member.cqc_id}
    )
    
    return render(request, 'careapp/cqc_dashboard.html', context)


# Service User Views
class ServiceUserListView(LoginRequiredMixin, ListView):
    model = ServiceUser
    template_name = 'careapp/serviceuser_list.html'
    context_object_name = 'service_users'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to service user list
        log_security_event(
            self.request, 
            "Service User List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = ServiceUser.objects.all().select_related('care_plan', 'key_worker__user')
        
        # Filter by active status if provided
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=(is_active == 'true'))
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(room_number__icontains=search_query)
            )
        
        return queryset.order_by('first_name', 'last_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add count of active service users
        context['active_count'] = ServiceUser.objects.filter(is_active=True).count()
        context['inactive_count'] = ServiceUser.objects.filter(is_active=False).count()
        
        # Add filter parameters to context
        for param in ['is_active', 'search']:
            context[param] = self.request.GET.get(param)
        
        return context


class ServiceUserDetailView(LoginRequiredMixin, DetailView):
    model = ServiceUser
    template_name = 'careapp/serviceuser_detail.html'
    context_object_name = 'service_user'
    
    def get(self, request, *args, **kwargs):
        # Log access to service user detail
        service_user = self.get_object()
        log_security_event(
            request, 
            "Service User Detail Access", 
            "Success", 
            {"service_user_id": service_user.id, "service_user_name": f"{service_user.first_name} {service_user.last_name}"}
        )
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_user = self.get_object()
        
        # Get current date and time
        now = timezone.now()
        
        # Get all related data
        context['current_date'] = now.date()
        context['current_time'] = now.time()
        
        # Get care plan if exists
        try:
            context['care_plan'] = service_user.care_plan
        except ServiceUser.care_plan.RelatedObjectDoesNotExist:
            context['care_plan'] = None
            
        # Get risk assessments
        context['risk_assessments'] = RiskAssessment.objects.filter(
            service_user=service_user,
            is_active=True
        )[:5]
        
        # Get PBS plan if exists
        try:
            context['pbs_plan'] = service_user.pbs_plan
        except ServiceUser.pbs_plan.RelatedObjectDoesNotExist:
            context['pbs_plan'] = None
            
        # Get current medications
        context['medications'] = Medication.objects.filter(
            service_user=service_user,
            is_active=True
        )
        
        # Get recent vital signs
        context['vital_signs'] = VitalSigns.objects.filter(
            service_user=service_user
        ).order_by('-recorded_date', '-recorded_time')[:5]
        
        # Get upcoming appointments
        today = timezone.now().date()
        context['upcoming_appointments'] = Appointment.objects.filter(
            service_user=service_user,
            date__gte=today,
            is_completed=False
        ).select_related('service_user')[:5]
        
        # Get recent incidents
        context['recent_incidents'] = Incident.objects.filter(
            service_user=service_user
        ).select_related('service_user')[:5]
        
        # Get documents
        context['documents'] = Document.objects.filter(
            service_user=service_user
        )[:5]
        
        # Add permission checks
        context['is_staff_or_management'] = is_staff_or_management(self.request.user)
        context['is_management'] = is_management(self.request.user)

        return context


class ServiceUserCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ServiceUser
    form_class = ServiceUserForm
    template_name = 'careapp/serviceuser_form.html'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('serviceuser_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        
        # Create empty care plan and PBS plan
        CarePlan.objects.create(
            service_user=self.object,
            created_by=self.request.user,
            updated_by=self.request.user,
            last_review_date=timezone.now().date(),
            next_review_date=timezone.now().date() + timezone.timedelta(days=90)
        )
        
        PBSPlan.objects.create(
            service_user=self.object,
            created_by=self.request.user,
            updated_by=self.request.user,
            last_review_date=timezone.now().date(),
            next_review_date=timezone.now().date() + timezone.timedelta(days=90)
        )
        
        log_security_event(
            self.request, 
            "Service User Created", 
            "Success", 
            {"service_user_id": self.object.id, "service_user_name": f"{self.object.first_name} {self.object.last_name}"}
        )
        return response


class ServiceUserUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ServiceUser
    form_class = ServiceUserForm
    template_name = 'careapp/serviceuser_form.html'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('serviceuser_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log service user update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Service User Updated", 
            "Success", 
            {"service_user_id": self.object.id, "service_user_name": f"{self.object.first_name} {self.object.last_name}"}
        )
        return response


@login_required
@user_passes_test(is_management)
def service_user_toggle_active(request, pk):
    service_user = get_object_or_404(ServiceUser, pk=pk)
    service_user.is_active = not service_user.is_active
    service_user.save()
    
    status = "activated" if service_user.is_active else "deactivated"
    messages.success(request, f"Service user {status} successfully.")
    
    # Log service user status change
    log_security_event(
        request, 
        f"Service User {status.capitalize()}", 
        "Success", 
        {"service_user_id": service_user.id, "service_user_name": f"{service_user.first_name} {service_user.last_name}"}
    )
    
    return redirect('serviceuser_list')






# Care Plan Views
# Care Plan List View
class CarePlanListView(LoginRequiredMixin, ListView):
    model = CarePlan
    template_name = 'careapp/careplan_list.html'
    context_object_name = 'care_plans'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to care plan list
        log_security_event(
            self.request, 
            "Care Plan List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = CarePlan.objects.all().select_related('service_user', 'created_by', 'updated_by')
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(service_user_id=service_user_id)
        
        # Filter by active status if provided
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=(is_active == 'true'))
        
        # Filter by review status if provided
        review_status = self.request.GET.get('review_status')
        if review_status == 'due':
            queryset = queryset.filter(next_review_date__lte=timezone.now().date())
        elif review_status == 'upcoming':
            queryset = queryset.filter(next_review_date__gt=timezone.now().date())
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(service_user__first_name__icontains=search_query) |
                Q(service_user__last_name__icontains=search_query) |
                Q(personal_care__icontains=search_query) |
                Q(medical_requirements__icontains=search_query)
            )
        
        return queryset.order_by('service_user__first_name', 'service_user__last_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_users'] = ServiceUser.objects.filter(is_active=True)
        
        # Add filter parameters to context
        for param in ['service_user', 'is_active', 'review_status', 'search']:
            context[param] = self.request.GET.get(param)
        
        # Add counts for statistics
        context['total_count'] = CarePlan.objects.count()
        context['active_count'] = CarePlan.objects.filter(is_active=True).count()
        context['due_for_review_count'] = CarePlan.objects.filter(
            next_review_date__lte=timezone.now().date()
        ).count()
        
        return context
    

class CarePlanCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = CarePlan
    form_class = CarePlanForm
    template_name = 'careapp/careplan_form.html'

    def test_func(self):
        return is_management(self.request.user) or is_staff(self.request.user)

    def get_success_url(self):
        return reverse_lazy('serviceuser_detail', kwargs={'pk': self.kwargs['service_user_id']})

    def form_valid(self, form):
        service_user = get_object_or_404(ServiceUser, pk=self.kwargs['service_user_id'])
        form.instance.service_user = service_user
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user

        response = super().form_valid(form)

        # Log security event
        log_security_event(
            self.request,
            "Care Plan Created",
            "Success",
            {
                "care_plan_id": self.object.id,
                "service_user_id": service_user.id,
                "service_user_name": f"{service_user.first_name} {service_user.last_name}",
            }
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_user = get_object_or_404(ServiceUser, pk=self.kwargs['service_user_id'])
        context['service_user'] = service_user
        context['title'] = 'Create Care Plan'
        return context


class CarePlanUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = CarePlan
    form_class = CarePlanForm
    template_name = 'careapp/careplan_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or is_staff(self.request.user)
    
    def get_object(self):
        service_user = get_object_or_404(ServiceUser, pk=self.kwargs['service_user_id'])
        return get_object_or_404(CarePlan, service_user=service_user)
    
    def get_success_url(self):
        return reverse_lazy('serviceuser_detail', kwargs={'pk': self.kwargs['service_user_id']})
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log care plan update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Care Plan Updated", 
            "Success", 
            {
                "care_plan_id": self.object.id, 
                "service_user_id": self.object.service_user.id,
                "service_user_name": f"{self.object.service_user.first_name} {self.object.service_user.last_name}"
            }
        )
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_user'] = get_object_or_404(ServiceUser, pk=self.kwargs['service_user_id'])
        context['title'] = 'Update Care Plan'
        return context


class CarePlanDetailView(LoginRequiredMixin, DetailView):
    model = CarePlan
    template_name = 'careapp/careplan_detail.html'
    context_object_name = 'care_plan'
    
    def get_object(self):
        service_user = get_object_or_404(ServiceUser, pk=self.kwargs['service_user_id'])
        return get_object_or_404(CarePlan, service_user=service_user)
    
    def get(self, request, *args, **kwargs):
        # Log access to care plan detail
        care_plan = self.get_object()
        log_security_event(
            request, 
            "Care Plan Detail Access", 
            "Success", 
            {
                "care_plan_id": care_plan.id, 
                "service_user_id": care_plan.service_user.id,
                "service_user_name": f"{care_plan.service_user.first_name} {care_plan.service_user.last_name}"
            }
        )
        return super().get(request, *args, **kwargs)




# PBS Plan Views
# PBS Plan List View
class PBSPlanListView(LoginRequiredMixin, ListView):
    model = PBSPlan
    template_name = 'careapp/pbsplan_list.html'
    context_object_name = 'pbs_plans'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to PBS plan list
        log_security_event(
            self.request, 
            "PBS Plan List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = PBSPlan.objects.all().select_related('service_user', 'created_by', 'updated_by')
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(service_user_id=service_user_id)
        
        # Filter by active status if provided
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=(is_active == 'true'))
        
        # Filter by review status if provided
        review_status = self.request.GET.get('review_status')
        if review_status == 'due':
            queryset = queryset.filter(next_review_date__lte=timezone.now().date())
        elif review_status == 'upcoming':
            queryset = queryset.filter(next_review_date__gt=timezone.now().date())
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(service_user__first_name__icontains=search_query) |
                Q(service_user__last_name__icontains=search_query) |
                Q(behaviors_of_concern__icontains=search_query) |
                Q(prevention_strategies__icontains=search_query)
            )
        
        return queryset.order_by('service_user__first_name', 'service_user__last_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_users'] = ServiceUser.objects.filter(is_active=True)
        
        # Add filter parameters to context
        for param in ['service_user', 'is_active', 'review_status', 'search']:
            context[param] = self.request.GET.get(param)
        
        # Add counts for statistics
        context['total_count'] = PBSPlan.objects.count()
        context['active_count'] = PBSPlan.objects.filter(is_active=True).count()
        context['due_for_review_count'] = PBSPlan.objects.filter(
            next_review_date__lte=timezone.now().date()
        ).count()
        
        return context
        

class PBSPlanCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = PBSPlan
    form_class = PBSPlanForm
    template_name = 'careapp/pbsplan_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or is_staff(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('serviceuser_detail', kwargs={'pk': self.kwargs['service_user_id']})
    
    def form_valid(self, form):
        service_user = get_object_or_404(ServiceUser, pk=self.kwargs['service_user_id'])
        form.instance.service_user = service_user
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log PBS plan creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "PBS Plan Created", 
            "Success", 
            {
                "pbs_plan_id": self.object.id, 
                "service_user_id": service_user.id,
                "service_user_name": f"{service_user.first_name} {service_user.last_name}"
            }
        )
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_user'] = get_object_or_404(ServiceUser, pk=self.kwargs['service_user_id'])
        context['title'] = 'Create PBS Plan'
        return context


class PBSPlanUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = PBSPlan
    form_class = PBSPlanForm
    template_name = 'careapp/pbsplan_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or is_staff(self.request.user)
    
    def get_object(self):
        service_user = get_object_or_404(ServiceUser, pk=self.kwargs['service_user_id'])
        return get_object_or_404(PBSPlan, service_user=service_user)
    
    def get_success_url(self):
        return reverse_lazy('serviceuser_detail', kwargs={'pk': self.kwargs['service_user_id']})
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log PBS plan update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "PBS Plan Updated", 
            "Success", 
            {
                "pbs_plan_id": self.object.id, 
                "service_user_id": self.object.service_user.id,
                "service_user_name": f"{self.object.service_user.first_name} {self.object.service_user.last_name}"
            }
        )
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_user'] = get_object_or_404(ServiceUser, pk=self.kwargs['service_user_id'])
        context['title'] = 'Update PBS Plan'
        return context


class PBSPlanDetailView(LoginRequiredMixin, DetailView):
    model = PBSPlan
    template_name = 'careapp/pbsplan_detail.html'
    context_object_name = 'pbs_plan'
    
    def get_object(self):
        service_user = get_object_or_404(ServiceUser, pk=self.kwargs['service_user_id'])
        return get_object_or_404(PBSPlan, service_user=service_user)
    
    def get(self, request, *args, **kwargs):
        # Log access to PBS plan detail
        pbs_plan = self.get_object()
        log_security_event(
            request, 
            "PBS Plan Detail Access", 
            "Success", 
            {
                "pbs_plan_id": pbs_plan.id, 
                "service_user_id": pbs_plan.service_user.id,
                "service_user_name": f"{pbs_plan.service_user.first_name} {pbs_plan.service_user.last_name}"
            }
        )
        return super().get(request, *args, **kwargs)


# Risk Assessment Views
class RiskAssessmentListView(LoginRequiredMixin, ListView):
    model = RiskAssessment
    template_name = 'careapp/riskassessment_list.html'
    context_object_name = 'risk_assessments'
    paginate_by = 12  # Reduced for better card view
    
    def get_queryset(self):
        # Log access to risk assessment list
        log_security_event(
            self.request, 
            "Risk Assessment List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = RiskAssessment.objects.all().select_related('service_user', 'created_by', 'updated_by')
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(service_user_id=service_user_id)
        
        # Filter by risk level if provided
        risk_level = self.request.GET.get('risk_level')
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)
        
        # Filter by active status if provided
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=(is_active == 'true'))
        
        # Filter by date assessed range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(date_assessed__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_assessed__lte=date_to)
        
        # Filter by review date range
        review_date_from = self.request.GET.get('review_date_from')
        review_date_to = self.request.GET.get('review_date_to')
        if review_date_from:
            queryset = queryset.filter(review_date__gte=review_date_from)
        if review_date_to:
            queryset = queryset.filter(review_date__lte=review_date_to)
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(category__icontains=search) |
                Q(description__icontains=search) |
                Q(service_user__first_name__icontains=search) |
                Q(service_user__last_name__icontains=search)
            )
        
        return queryset.order_by('-date_assessed')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_users'] = ServiceUser.objects.filter(is_active=True)
        
        # Add filter parameters to context
        for param in ['service_user', 'risk_level', 'is_active', 'search', 
                     'date_from', 'date_to', 'review_date_from', 'review_date_to']:
            context[param] = self.request.GET.get(param)
        
        return context


class RiskAssessmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = RiskAssessment
    form_class = RiskAssessmentForm
    template_name = 'careapp/riskassessment_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or is_staff(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('riskassessment_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log risk assessment creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Risk Assessment Created", 
            "Success", 
            {"risk_assessment_id": self.object.id, "category": self.object.category}
        )
        return response


class RiskAssessmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = RiskAssessment
    form_class = RiskAssessmentForm
    template_name = 'careapp/riskassessment_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or is_staff(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('riskassessment_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log risk assessment update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Risk Assessment Updated", 
            "Success", 
            {"risk_assessment_id": self.object.id, "category": self.object.category}
        )
        return response


@login_required
@user_passes_test(is_management)
def risk_assessment_toggle_active(request, pk):
    risk_assessment = get_object_or_404(RiskAssessment, pk=pk)
    risk_assessment.is_active = not risk_assessment.is_active
    risk_assessment.save()
    
    status = "activated" if risk_assessment.is_active else "deactivated"
    messages.success(request, f"Risk assessment {status} successfully.")
    
    # Log risk assessment status change
    log_security_event(
        request, 
        f"Risk Assessment {status.capitalize()}", 
        "Success", 
        {"risk_assessment_id": risk_assessment.id, "category": risk_assessment.category}
    )
    
    return redirect('riskassessment_list')




class RiskAssessmentDetailView(LoginRequiredMixin, DetailView):
    model = RiskAssessment
    template_name = 'careapp/riskassessment_detail.html'
    context_object_name = 'risk_assessment'
    
    def get(self, request, *args, **kwargs):
        # Log access to risk assessment detail
        log_security_event(
            self.request, 
            "Risk Assessment Detail Access", 
            "Success", 
            {"risk_assessment_id": self.get_object().id}
        )
        return super().get(request, *args, **kwargs)


# Activity Views
class ActivityListView(LoginRequiredMixin, ListView):
    model = Activity
    template_name = 'careapp/activity_list.html'
    context_object_name = 'activities'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to activity list
        log_security_event(
            self.request, 
            "Activity List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = Activity.objects.all().select_related('service_user').prefetch_related('staff_involved')
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(service_user_id=service_user_id)
        
        # Filter by date range if provided
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        # Filter by activity type if provided
        activity_type = self.request.GET.get('activity_type')
        if activity_type:
            queryset = queryset.filter(activity_type=activity_type)
        
        # Filter by completion status if provided
        is_completed = self.request.GET.get('is_completed')
        if is_completed in ['true', 'false']:
            queryset = queryset.filter(is_completed=(is_completed == 'true'))
        
        return queryset.order_by('-date', '-start_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_users'] = ServiceUser.objects.filter(is_active=True)
        context['activity_types'] = Activity.ACTIVITY_TYPES
        
        # Add filter parameters to context
        for param in ['service_user', 'date_from', 'date_to', 'activity_type', 'is_completed']:
            context[param] = self.request.GET.get(param)
        
        return context


class ActivityCreateView(LoginRequiredMixin, CreateView):
    model = Activity
    form_class = ActivityForm
    template_name = 'careapp/activity_form.html'
    
    def get_success_url(self):
        return reverse_lazy('activity_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log activity creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Activity Created", 
            "Success", 
            {"activity_id": self.object.id, "activity_title": self.object.title}
        )
        
        # Handle multiple photo uploads
        photos = self.request.FILES.getlist('photos')
        for photo in photos:
            ActivityPhoto.objects.create(activity=self.object, photo=photo)
        
        return response


class ActivityUpdateView(LoginRequiredMixin, UpdateView):
    model = Activity
    form_class = ActivityForm
    template_name = 'careapp/activity_form.html'
    
    def get_success_url(self):
        return reverse_lazy('activity_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log activity update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Activity Updated", 
            "Success", 
            {"activity_id": self.object.id, "activity_title": self.object.title}
        )
        
        # Handle multiple photo uploads
        photos = self.request.FILES.getlist('photos')
        for photo in photos:
            ActivityPhoto.objects.create(activity=self.object, photo=photo)
        
        return response


@login_required
def activity_detail(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    
    # Log activity detail access
    log_security_event(
        request, 
        "Activity Detail Access", 
        "Success", 
        {"activity_id": activity.id, "activity_title": activity.title}
    )
    
    return render(request, 'careapp/activity_detail.html', {'activity': activity})


@login_required
def mark_activity_completed(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    activity.is_completed = True
    activity.save()
    
    messages.success(request, "Activity marked as completed.")
    
    # Log activity completion
    log_security_event(
        request, 
        "Activity Completed", 
        "Success", 
        {"activity_id": activity.id, "activity_title": activity.title}
    )
    
    return redirect('activity_list')


# Medication Views
class MedicationListView(LoginRequiredMixin, ListView):
    model = Medication
    template_name = 'careapp/medication_list.html'
    context_object_name = 'medications'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to medication list
        log_security_event(
            self.request, 
            "Medication List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = Medication.objects.all().select_related('service_user')
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(service_user_id=service_user_id)
        
        # Filter by controlled drug status if provided
        is_controlled = self.request.GET.get('is_controlled')
        if is_controlled in ['true', 'false']:
            queryset = queryset.filter(is_controlled_drug=(is_controlled == 'true'))
        
        # Filter by active status if provided
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=(is_active == 'true'))
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_users'] = ServiceUser.objects.filter(is_active=True)
        
        # Add filter parameters to context
        for param in ['service_user', 'is_controlled', 'is_active']:
            context[param] = self.request.GET.get(param)
        
        return context


class MedicationCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Medication
    form_class = MedicationForm
    template_name = 'careapp/medication_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or is_staff(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('medication_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Calculate next due time
        medication = form.save(commit=False)
        medication.next_due_time = medication.get_next_due_time()
        
        response = super().form_valid(form)
        
        # Log medication creation
        log_security_event(
            self.request, 
            "Medication Created", 
            "Success", 
            {"medication_id": self.object.id, "medication_name": self.object.name}
        )
        return response


class MedicationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Medication
    form_class = MedicationForm
    template_name = 'careapp/medication_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or is_staff(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('medication_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Update next due time
        medication = form.save(commit=False)
        medication.next_due_time = medication.get_next_due_time()
        
        response = super().form_valid(form)
        
        # Log medication update
        log_security_event(
            self.request, 
            "Medication Updated", 
            "Success", 
            {"medication_id": self.object.id, "medication_name": self.object.name}
        )
        return response
    


from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Medication, MedicationAdministration

class MedicationDetailView(LoginRequiredMixin, DetailView):
    model = Medication
    template_name = 'careapp/medication_detail.html'
    context_object_name = 'medication'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        medication = self.object
        
        # Get recent administrations for this medication
        context['recent_administrations'] = MedicationAdministration.objects.filter(
            medication=medication
        ).select_related('administered_by', 'witness').order_by(
            '-administered_date', '-administered_time'
        )[:10]
        
        # Calculate administration statistics
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        # Get administration counts
        context['today_count'] = MedicationAdministration.objects.filter(
            medication=medication,
            administered_date=today,
            status='given'
        ).count()
        
        context['week_count'] = MedicationAdministration.objects.filter(
            medication=medication,
            administered_date__gte=week_ago,
            status='given'
        ).count()
        
        context['total_count'] = MedicationAdministration.objects.filter(
            medication=medication,
            status='given'
        ).count()
        
        # Get missed administrations (last 7 days)
        context['missed_count'] = self.get_missed_administrations_count(medication, week_ago, today)
        
        # Get next due time
        context['next_due_time'] = medication.get_next_due_time()
        context['is_due'] = medication.is_due
        
        # Get time period administrations
        context['time_periods'] = medication.get_time_periods()
        
        return context
    
    def get_missed_administrations_count(self, medication, start_date, end_date):
        """Calculate missed administrations based on schedule"""
        missed_count = 0
        current_date = start_date
        
        while current_date <= end_date:
            # Check if medication should be administered on this date
            if medication.is_active and current_date >= medication.start_date and (not medication.end_date or current_date <= medication.end_date):
                # Check each time period
                for period, time, _ in medication.get_time_periods():
                    if period != 'prn' and time:  # Skip PRN for missed count
                        # Check if administration exists for this time period
                        administration_exists = MedicationAdministration.objects.filter(
                            medication=medication,
                            administered_date=current_date,
                            status='given'
                        ).exists()
                        
                        if not administration_exists:
                            missed_count += 1
            
            current_date += timedelta(days=1)
        
        return missed_count


class MedicationListView(LoginRequiredMixin, ListView):
    model = Medication
    template_name = 'careapp/medication_list.html'
    context_object_name = 'medications'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to medication list
        log_security_event(
            self.request, 
            "Medication List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = Medication.objects.all().select_related('service_user')
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(service_user_id=service_user_id)
        
        # Filter by medication type if provided
        medication_type = self.request.GET.get('medication_type')
        if medication_type:
            queryset = queryset.filter(medication_type=medication_type)
        
        # Filter by controlled drug status if provided
        is_controlled = self.request.GET.get('is_controlled')
        if is_controlled in ['true', 'false']:
            queryset = queryset.filter(is_controlled_drug=(is_controlled == 'true'))
        
        # Filter by active status if provided
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=(is_active == 'true'))
        
        # Filter by low stock if provided
        low_stock = self.request.GET.get('low_stock')
        if low_stock == 'true':
            queryset = queryset.filter(current_balance__lte=5)  # Consider 5 or fewer as low stock
        elif low_stock == 'false':
            queryset = queryset.filter(current_balance__gt=5)
        
        # Search by medication name if provided
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_users'] = ServiceUser.objects.filter(is_active=True)
        context['medication_types'] = Medication.MEDICATION_TYPES
        
        # Add filter parameters to context
        for param in ['service_user', 'medication_type', 'is_controlled', 'is_active', 'low_stock', 'search']:
            context[param] = self.request.GET.get(param)
        
        return context


@login_required
@user_passes_test(is_management)
def medication_toggle_active(request, pk):
    medication = get_object_or_404(Medication, pk=pk)
    medication.is_active = not medication.is_active
    medication.save()
    
    status = "activated" if medication.is_active else "deactivated"
    messages.success(request, f"Medication {status} successfully.")
    
    # Log medication status change
    log_security_event(
        request, 
        f"Medication {status.capitalize()}", 
        "Success", 
        {"medication_id": medication.id, "medication_name": medication.name}
    )
    
    return redirect('medication_list')




from django.views.generic import CreateView, ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from .models import MedicationAdministration, Medication, ServiceUser, StaffMember
from .forms import MedicationAdministrationForm

class MedicationDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'careapp/medication_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current time to determine medication schedule
        now = timezone.now()
        current_hour = now.hour
        
        # Determine current time of day
        if 6 <= current_hour < 12:
            time_period = 'morning'
        elif 12 <= current_hour < 17:
            time_period = 'afternoon'
        elif 17 <= current_hour < 22:
            time_period = 'evening'
        else:
            time_period = 'night'
        
        # Get all active service users with their medications
        service_users = ServiceUser.objects.filter(
            is_active=True,
            medications__is_active=True
        ).distinct().prefetch_related(
            'medications'
        ).order_by('first_name', 'last_name')
        
        # Organize medications by service user and time period
        medication_schedule = {}
        for user in service_users:
            medication_schedule[user.id] = {
                'user': user,
                'morning': [],
                'afternoon': [],
                'evening': [],
                'night': [],
                'prn': []
            }
            
            for medication in user.medications.filter(is_active=True):
                frequency = medication.frequency.lower()
                
                # Categorize medications by time
                if 'prn' in frequency or 'as needed' in frequency:
                    medication_schedule[user.id]['prn'].append(medication)
                elif 'morning' in frequency or 'breakfast' in frequency or 'once daily' in frequency:
                    medication_schedule[user.id]['morning'].append(medication)
                elif 'afternoon' in frequency or 'lunch' in frequency or 'twice daily' in frequency:
                    medication_schedule[user.id]['afternoon'].append(medication)
                elif 'evening' in frequency or 'dinner' in frequency:
                    medication_schedule[user.id]['evening'].append(medication)
                elif 'night' in frequency or 'bedtime' in frequency:
                    medication_schedule[user.id]['night'].append(medication)
                else:
                    # Default to morning if no specific time mentioned
                    medication_schedule[user.id]['morning'].append(medication)
        
        context.update({
            'service_users': service_users,
            'medication_schedule': medication_schedule,
            'current_time_period': time_period,
            'current_date': now.date(),
            'current_time': now.time(),
        })
        
        return context

class MedicationAdministrationCreateView(LoginRequiredMixin, CreateView):
    model = MedicationAdministration
    form_class = MedicationAdministrationForm
    template_name = 'careapp/medication_administration_form.html'
    success_url = reverse_lazy('medication_dashboard')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        medication_id = self.kwargs.get('medication_id')
        
        if medication_id:
            medication = get_object_or_404(Medication, id=medication_id)
            initial['medication'] = medication
            initial['dose_administered'] = medication.dosage.split()[0] if medication.dosage else 1
        
        return initial
    
    def form_valid(self, form):
        # Set the staff member who is administering the medication
        form.instance.administered_by = self.request.user.staffmember
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get medication ID from URL if provided
        medication_id = self.kwargs.get('medication_id')
        if medication_id:
            medication = get_object_or_404(Medication, id=medication_id)
            context['selected_medication'] = medication
        
        # Add all staff members for witness selection
        context['staff_members'] = StaffMember.objects.filter(is_active=True)
        
        return context

class MedicationAdministrationListView(LoginRequiredMixin, ListView):
    model = MedicationAdministration
    template_name = 'careapp/medication_administration_list.html'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'medication', 'medication__service_user', 'administered_by'
        )
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(medication__service_user_id=service_user_id)
        
        # Filter by date if provided
        date_filter = self.request.GET.get('date')
        if date_filter:
            queryset = queryset.filter(administered_date=date_filter)
        
        return queryset.order_by('-administered_date', '-administered_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_users'] = ServiceUser.objects.all()
        return context

class MedicationAdministrationDetailView(LoginRequiredMixin, DetailView):
    model = MedicationAdministration
    template_name = 'careapp/medication_administration_detail.html'
    context_object_name = 'administration'

@login_required
@require_GET
def medication_details_api(request, medication_id):
    try:
        medication = Medication.objects.select_related('service_user').get(id=medication_id)
        data = {
            'id': medication.id,
            'name': medication.name,
            'medication_type': medication.medication_type,
            'medication_type_display': medication.get_medication_type_display(),
            'dosage': medication.dosage,
            'frequency': medication.frequency,
            'route': medication.route,
            'instructions': medication.instructions,
            'current_balance': medication.current_balance,
            'is_controlled_drug': medication.is_controlled_drug,
            'service_user_name': f"{medication.service_user.first_name} {medication.service_user.last_name}",
            'service_user_room': medication.service_user.room_number,
            'service_user_allergies': medication.service_user.allergies,
            'service_user_conditions': medication.service_user.medical_conditions,
        }
        return JsonResponse(data)
    except Medication.DoesNotExist:
        return JsonResponse({'error': 'Medication not found'}, status=404)


# Incident Views
class IncidentListView(LoginRequiredMixin, ListView):
    model = Incident
    template_name = 'careapp/incident_list.html'
    context_object_name = 'incidents'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to incident list
        log_security_event(
            self.request, 
            "Incident List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = Incident.objects.all().select_related('service_user').prefetch_related('staff_involved')
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(service_user_id=service_user_id)
        
        # Filter by date range if provided
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        # Filter by incident type if provided
        incident_type = self.request.GET.get('incident_type')
        if incident_type:
            queryset = queryset.filter(incident_type=incident_type)
        
        # Filter by severity if provided
        severity = self.request.GET.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # Filter by follow-up required if provided
        follow_up_required = self.request.GET.get('follow_up_required')
        if follow_up_required in ['true', 'false']:
            queryset = queryset.filter(follow_up_required=(follow_up_required == 'true'))
        
        return queryset.order_by('-date', '-time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_users'] = ServiceUser.objects.filter(is_active=True)
        context['incident_types'] = Incident.INCIDENT_TYPES
        context['severity_levels'] = Incident.SEVERITY_CHOICES
        
        # Add filter parameters to context
        for param in ['service_user', 'date_from', 'date_to', 'incident_type', 'severity', 'follow_up_required']:
            context[param] = self.request.GET.get(param)
        
        return context


class IncidentCreateView(LoginRequiredMixin, CreateView):
    model = Incident
    form_class = IncidentForm
    template_name = 'careapp/incident_form.html'
    
    def get_success_url(self):
        return reverse_lazy('incident_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log incident creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Incident Created", 
            "Success", 
            {"incident_id": self.object.id, "incident_type": self.object.incident_type}
        )
        return response


class IncidentUpdateView(LoginRequiredMixin, UpdateView):
    model = Incident
    form_class = IncidentForm
    template_name = 'careapp/incident_form.html'
    
    def get_success_url(self):
        return reverse_lazy('incident_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log incident update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Incident Updated", 
            "Success", 
            {"incident_id": self.object.id, "incident_type": self.object.incident_type}
        )
        return response


@login_required
def incident_detail(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    
    # Check if CQC user can view this incident
    if is_cqc(request.user) and not incident.is_viewable_by_cqc():
        raise PermissionDenied("This incident is not yet available for CQC viewing.")
    
    # Log incident detail access
    log_security_event(
        request, 
        "Incident Detail Access", 
        "Success", 
        {"incident_id": incident.id, "incident_type": incident.incident_type}
    )
    
    return render(request, 'careapp/incident_detail.html', {'incident': incident})


@login_required
@user_passes_test(is_management)
def incident_toggle_follow_up(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    incident.follow_up_required = not incident.follow_up_required
    incident.save()
    
    status = "marked as requiring follow-up" if incident.follow_up_required else "marked as not requiring follow-up"
    messages.success(request, f"Incident {status}.")
    
    # Log incident status change
    log_security_event(
        request, 
        f"Incident Follow-up Status Changed", 
        "Success", 
        {"incident_id": incident.id, "follow_up_required": incident.follow_up_required}
    )
    
    return redirect('incident_list')


# Appointment Views
class AppointmentListView(LoginRequiredMixin, ListView):
    model = Appointment
    template_name = 'careapp/appointment_list.html'
    context_object_name = 'appointments'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to appointment list
        log_security_event(
            self.request, 
            "Appointment List Access", 
            "Success", 
            {"view": "list"}
        )
        
        today = timezone.now().date()
        queryset = Appointment.objects.all().select_related('service_user').prefetch_related('staff_accompanying')
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(service_user_id=service_user_id)
        
        # Filter by date range if provided
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        # Filter by appointment type if provided
        appointment_type = self.request.GET.get('appointment_type')
        if appointment_type:
            queryset = queryset.filter(appointment_type=appointment_type)
        
        # Filter by completion status if provided
        is_completed = self.request.GET.get('is_completed')
        if is_completed in ['true', 'false']:
            queryset = queryset.filter(is_completed=(is_completed == 'true'))
        
        return queryset.order_by('date', 'start_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_users'] = ServiceUser.objects.filter(is_active=True)
        context['appointment_types'] = Appointment.APPOINTMENT_TYPES
        
        # Add filter parameters to context
        for param in ['service_user', 'date_from', 'date_to', 'appointment_type', 'is_completed']:
            context[param] = self.request.GET.get(param)
        
        return context


class AppointmentCreateView(LoginRequiredMixin, CreateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = 'careapp/appointment_form.html'
    
    def get_success_url(self):
        return reverse_lazy('appointment_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log appointment creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Appointment Created", 
            "Success", 
            {"appointment_id": self.object.id, "appointment_title": self.object.title}
        )
        return response


class AppointmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = 'careapp/appointment_form.html'
    
    def get_success_url(self):
        return reverse_lazy('appointment_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log appointment update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Appointment Updated", 
            "Success", 
            {"appointment_id": self.object.id, "appointment_title": self.object.title}
        )
        return response
    

# careapp/views.py
from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Appointment
from .utils import log_security_event

class AppointmentDetailView(LoginRequiredMixin, DetailView):
    model = Appointment
    template_name = 'careapp/appointment_detail.html'
    context_object_name = 'appointment'
    
    def get(self, request, *args, **kwargs):
        # Log appointment detail access
        appointment = self.get_object()
        log_security_event(
            request, 
            "Appointment Detail Access", 
            "Success", 
            {"appointment_id": appointment.id, "appointment_title": appointment.title}
        )
        return super().get(request, *args, **kwargs)


@login_required
def mark_appointment_completed(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    appointment.is_completed = True
    appointment.save()
    
    messages.success(request, "Appointment marked as completed.")
    
    # Log appointment completion
    log_security_event(
        request, 
        "Appointment Completed", 
        "Success", 
        {"appointment_id": appointment.id, "appointment_title": appointment.title}
    )
    
    return redirect('appointment_list')


# Visitor Views
class VisitorListView(LoginRequiredMixin, ListView):
    model = Visitor
    template_name = 'careapp/visitor_list.html'
    context_object_name = 'visitors'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to visitor list
        log_security_event(
            self.request, 
            "Visitor List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = Visitor.objects.all().select_related('service_user')
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(service_user_id=service_user_id)
        
        # Filter by date range if provided
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(visit_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(visit_date__lte=date_to)
        
        # Filter by COVID screening status if provided
        covid_screening_passed = self.request.GET.get('covid_screening_passed')
        if covid_screening_passed in ['true', 'false']:
            queryset = queryset.filter(covid_screening_passed=(covid_screening_passed == 'true'))
        
        # Filter by relationship if provided
        relationship = self.request.GET.get('relationship')
        if relationship:
            queryset = queryset.filter(relationship__icontains=relationship)
        
        # Search by visitor name or phone number
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(visitor_name__icontains=search) |
                Q(phone_number__icontains=search)
            )
        
        return queryset.order_by('-visit_date', '-arrival_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_users'] = ServiceUser.objects.filter(is_active=True)
        
        # Add filter parameters to context
        for param in ['service_user', 'date_from', 'date_to', 'covid_screening_passed', 'relationship', 'search']:
            context[param] = self.request.GET.get(param)
        
        return context
    


class VisitorCreateView(LoginRequiredMixin, CreateView):
    model = Visitor
    form_class = VisitorForm
    template_name = 'careapp/visitor_form.html'
    
    def get_success_url(self):
        return reverse_lazy('visitor_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log visitor creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Visitor Created", 
            "Success", 
            {"visitor_id": self.object.id, "visitor_name": self.object.visitor_name}
        )
        return response


class VisitorUpdateView(LoginRequiredMixin, UpdateView):
    model = Visitor
    form_class = VisitorForm
    template_name = 'careapp/visitor_form.html'
    
    def get_success_url(self):
        return reverse_lazy('visitor_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log visitor update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Visitor Updated", 
            "Success", 
            {"visitor_id": self.object.id, "visitor_name": self.object.visitor_name}
        )
        return response
    

class VisitorDetailView(LoginRequiredMixin, DetailView):
    model = Visitor
    template_name = 'careapp/visitor_detail.html'
    context_object_name = 'visitor'
    
    def get(self, request, *args, **kwargs):
        # Log access to visitor detail
        log_security_event(
            self.request, 
            "Visitor Detail Access", 
            "Success", 
            {"visitor_id": self.get_object().id, "visitor_name": self.get_object().visitor_name}
        )
        return super().get(request, *args, **kwargs)


# Trip Views
class TripListView(LoginRequiredMixin, ListView):
    model = Trip
    template_name = 'careapp/trip_list.html'
    context_object_name = 'trips'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to trip list
        log_security_event(
            self.request, 
            "Trip List Access", 
            "Success", 
            {"view": "list"}
        )
        
        today = timezone.now().date()
        queryset = Trip.objects.all().prefetch_related('service_users', 'staff_accompanying')
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(service_users__id=service_user_id)
        
        # Filter by date range if provided
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        # Filter by risk assessment completion if provided
        risk_assessment_completed = self.request.GET.get('risk_assessment_completed')
        if risk_assessment_completed in ['true', 'false']:
            queryset = queryset.filter(risk_assessment_completed=(risk_assessment_completed == 'true'))
        
        return queryset.order_by('date', 'departure_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_users'] = ServiceUser.objects.filter(is_active=True)
        
        # Add filter parameters to context
        for param in ['service_user', 'date_from', 'date_to', 'risk_assessment_completed']:
            context[param] = self.request.GET.get(param)
        
        return context


class TripCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Trip
    form_class = TripForm
    template_name = 'careapp/trip_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or is_staff(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('trip_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log trip creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Trip Created", 
            "Success", 
            {"trip_id": self.object.id, "trip_destination": self.object.destination}
        )
        return response


class TripUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Trip
    form_class = TripForm
    template_name = 'careapp/trip_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or is_staff(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('trip_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log trip update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Trip Updated", 
            "Success", 
            {"trip_id": self.object.id, "trip_destination": self.object.destination}
        )
        return response


@login_required
def trip_detail(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    
    # Log trip detail access
    log_security_event(
        request, 
        "Trip Detail Access", 
        "Success", 
        {"trip_id": trip.id, "trip_destination": trip.destination}
    )
    
    return render(request, 'careapp/trip_detail.html', {'trip': trip})


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from .models import StaffMember, CQCMember, Department, Role
from .forms import StaffMemberForm, CQCMemberForm, PasswordChangeForm
from .utils import is_management

# Staff Member Views

@login_required
@user_passes_test(is_management)
def staff_member_list(request):
    staff_members = StaffMember.objects.select_related('user', 'department', 'role').all()
    
    # Filtering
    search_query = request.GET.get('search', '')
    department_filter = request.GET.get('department', '')
    status_filter = request.GET.get('status', '')
    
    if search_query:
        staff_members = staff_members.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(staff_id__icontains=search_query) |
            Q(position__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )
    
    if department_filter:
        staff_members = staff_members.filter(department_id=department_filter)
    
    if status_filter:
        if status_filter == 'active':
            staff_members = staff_members.filter(is_active=True)
        elif status_filter == 'inactive':
            staff_members = staff_members.filter(is_active=False)
    
    # Pagination
    paginator = Paginator(staff_members, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    departments = Department.objects.filter(is_active=True)
    
    context = {
        'page_obj': page_obj,
        'departments': departments,
        'search_query': search_query,
        'department_filter': department_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'careapp/staff_member_list.html', context)


@login_required
@user_passes_test(is_management)
def staff_member_detail(request, pk):
    staff_member = get_object_or_404(StaffMember.objects.select_related('user', 'department', 'role'), pk=pk)
    
    # Check if user is in Staff group
    is_in_staff_group = staff_member.user.groups.filter(name='Staff').exists()
    
    context = {
        'staff_member': staff_member,
        'is_in_staff_group': is_in_staff_group
    }
    
    return render(request, 'careapp/staff_member_detail.html', context)


@login_required
@user_passes_test(is_management)
def staff_member_create(request):
    if request.method == 'POST':
        form = StaffMemberForm(request.POST, request.FILES)
        if form.is_valid():
            staff_member = form.save()
            messages.success(request, f'Staff member {staff_member.user.get_full_name()} created successfully.')
            return redirect('staff_member_list')
    else:
        form = StaffMemberForm()
    
    context = {
        'form': form,
        'title': 'Create New Staff Member'
    }
    
    return render(request, 'careapp/staff_member_form.html', context)


@login_required
@user_passes_test(is_management)
def staff_member_edit(request, pk):
    staff_member = get_object_or_404(StaffMember, pk=pk)
    
    if request.method == 'POST':
        form = StaffMemberForm(request.POST, request.FILES, instance=staff_member)
        if form.is_valid():
            staff_member = form.save()
            messages.success(request, f'Staff member {staff_member.user.get_full_name()} updated successfully.')
            return redirect('staff_member_list')
    else:
        form = StaffMemberForm(instance=staff_member)
    
    context = {
        'form': form,
        'title': f'Edit Staff Member: {staff_member.user.get_full_name()}',
        'staff_member': staff_member
    }
    
    return render(request, 'careapp/staff_member_form.html', context)


@login_required
@user_passes_test(is_management)
def staff_member_change_password(request, pk):
    staff_member = get_object_or_404(StaffMember, pk=pk)
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['password']
            staff_member.user.set_password(password)
            staff_member.user.save()
            messages.success(request, f'Password for {staff_member.user.get_full_name()} changed successfully.')
            return redirect('staff_member_list')
    else:
        form = PasswordChangeForm()
    
    context = {
        'form': form,
        'title': f'Change Password for {staff_member.user.get_full_name()}',
        'staff_member': staff_member
    }
    
    return render(request, 'careapp/password_change.html', context)


@login_required
@user_passes_test(is_management)
def staff_member_toggle_active(request, pk):
    staff_member = get_object_or_404(StaffMember, pk=pk)
    
    if staff_member.is_active:
        staff_member.is_active = False
        action = 'deactivated'
    else:
        staff_member.is_active = True
        action = 'activated'
    
    staff_member.save()
    
    # Also update the user account status
    staff_member.user.is_active = staff_member.is_active
    staff_member.user.save()
    
    messages.success(request, f'Staff member {staff_member.user.get_full_name()} {action} successfully.')
    
    return redirect('staff_member_list')


@login_required
@user_passes_test(is_management)
def staff_member_add_to_group(request, pk):
    staff_member = get_object_or_404(StaffMember, pk=pk)
    
    # Add user to Staff group
    staff_group, created = Group.objects.get_or_create(name='Staff')
    staff_member.user.groups.add(staff_group)
    
    messages.success(request, f'Staff member {staff_member.user.get_full_name()} added to Staff group successfully.')
    
    return redirect('staff_member_detail', pk=staff_member.pk)


# CQC Member Views

@login_required
@user_passes_test(is_management)
def cqc_member_list(request):
    cqc_members = CQCMember.objects.select_related('user').all()
    
    # Filtering
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    if search_query:
        cqc_members = cqc_members.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(cqc_id__icontains=search_query) |
            Q(name__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )
    
    if status_filter:
        if status_filter == 'active':
            cqc_members = cqc_members.filter(is_active=True)
        elif status_filter == 'inactive':
            cqc_members = cqc_members.filter(is_active=False)
    
    # Pagination
    paginator = Paginator(cqc_members, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    
    return render(request, 'careapp/cqc_member_list.html', context)


@login_required
@user_passes_test(is_management)
def cqc_member_detail(request, pk):
    cqc_member = get_object_or_404(CQCMember.objects.select_related('user'), pk=pk)
    
    # Check if user is in CQC_Members group
    is_in_cqc_group = cqc_member.user.groups.filter(name='CQC_Members').exists()
    
    context = {
        'cqc_member': cqc_member,
        'is_in_cqc_group': is_in_cqc_group
    }
    
    return render(request, 'careapp/cqc_member_detail.html', context)


@login_required
@user_passes_test(is_management)
def cqc_member_create(request):
    if request.method == 'POST':
        form = CQCMemberForm(request.POST)
        if form.is_valid():
            cqc_member = form.save()
            messages.success(request, f'CQC member {cqc_member.name} created successfully.')
            return redirect('cqc_member_list')
    else:
        form = CQCMemberForm()
    
    context = {
        'form': form,
        'title': 'Create New CQC Member'
    }
    
    return render(request, 'careapp/cqc_member_form.html', context)


@login_required
@user_passes_test(is_management)
def cqc_member_edit(request, pk):
    cqc_member = get_object_or_404(CQCMember, pk=pk)
    
    if request.method == 'POST':
        form = CQCMemberForm(request.POST, instance=cqc_member)
        if form.is_valid():
            cqc_member = form.save()
            messages.success(request, f'CQC member {cqc_member.name} updated successfully.')
            return redirect('cqc_member_list')
    else:
        form = CQCMemberForm(instance=cqc_member)
    
    context = {
        'form': form,
        'title': f'Edit CQC Member: {cqc_member.name}',
        'cqc_member': cqc_member
    }
    
    return render(request, 'careapp/cqc_member_form.html', context)


@login_required
@user_passes_test(is_management)
def cqc_member_change_password(request, pk):
    cqc_member = get_object_or_404(CQCMember, pk=pk)
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['password']
            cqc_member.user.set_password(password)
            cqc_member.user.save()
            messages.success(request, f'Password for {cqc_member.name} changed successfully.')
            return redirect('cqc_member_list')
    else:
        form = PasswordChangeForm()
    
    context = {
        'form': form,
        'title': f'Change Password for {cqc_member.name}',
        'cqc_member': cqc_member
    }
    
    return render(request, 'careapp/password_change.html', context)


@login_required
@user_passes_test(is_management)
def cqc_member_toggle_active(request, pk):
    cqc_member = get_object_or_404(CQCMember, pk=pk)
    
    if cqc_member.is_active:
        cqc_member.is_active = False
        action = 'deactivated'
    else:
        cqc_member.is_active = True
        action = 'activated'
    
    cqc_member.save()
    
    # Also update the user account status
    cqc_member.user.is_active = cqc_member.is_active
    cqc_member.user.save()
    
    messages.success(request, f'CQC member {cqc_member.name} {action} successfully.')
    
    return redirect('cqc_member_list')


@login_required
@user_passes_test(is_management)
def cqc_member_add_to_group(request, pk):
    cqc_member = get_object_or_404(CQCMember, pk=pk)
    
    # Add user to CQC_Members group
    cqc_group, created = Group.objects.get_or_create(name='CQC_Members')
    cqc_member.user.groups.add(cqc_group)
    
    messages.success(request, f'CQC member {cqc_member.name} added to CQC group successfully.')
    
    return redirect('cqc_member_detail', pk=cqc_member.pk)




# Department Views
class DepartmentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Department
    template_name = 'careapp/department_list.html'
    context_object_name = 'departments'
    paginate_by = 12
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_queryset(self):
        # Log access to department list
        log_security_event(
            self.request, 
            "Department List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = Department.objects.all().select_related('manager__user')
        
        # Filter by active status if provided
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=(is_active == 'true'))
        
        # Filter by manager if provided
        manager_id = self.request.GET.get('manager')
        if manager_id:
            queryset = queryset.filter(manager_id=manager_id)
        
        # Search by department name
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        # Sort the results
        sort_by = self.request.GET.get('sort', 'name')
        if sort_by == 'staff_count':
            queryset = queryset.annotate(staff_count=Count('staffmember')).order_by('staff_count')
        elif sort_by == '-staff_count':
            queryset = queryset.annotate(staff_count=Count('staffmember')).order_by('-staff_count')
        else:
            queryset = queryset.order_by(sort_by)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter parameters to context
        context['is_active'] = self.request.GET.get('is_active')
        context['manager'] = self.request.GET.get('manager')
        context['search'] = self.request.GET.get('search')
        context['sort'] = self.request.GET.get('sort', 'name')
        
        # Get all managers for the filter dropdown
        from careapp.models import StaffMember
        context['managers'] = StaffMember.objects.filter(
            user__is_active=True
        ).select_related('user').order_by('user__first_name', 'user__last_name')
        
        return context


class DepartmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'careapp/department_form.html'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('department_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log department creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Department Created", 
            "Success", 
            {"department_id": self.object.id, "department_name": self.object.name}
        )
        return response


class DepartmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'careapp/department_form.html'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('department_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log department update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Department Updated", 
            "Success", 
            {"department_id": self.object.id, "department_name": self.object.name}
        )
        return response
    

class DepartmentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Department
    template_name = 'careapp/department_detail.html'
    context_object_name = 'department'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Log access to department detail
        log_security_event(
            self.request, 
            "Department Detail Access", 
            "Success", 
            {"department_id": self.object.id, "department_name": self.object.name}
        )
        
        return context


@login_required
@user_passes_test(is_management)
def department_toggle_active(request, pk):
    department = get_object_or_404(Department, pk=pk)
    department.is_active = not department.is_active
    department.save()
    
    status = "activated" if department.is_active else "deactivated"
    messages.success(request, f"Department {status} successfully.")
    
    # Log department status change
    log_security_event(
        request, 
        f"Department {status.capitalize()}", 
        "Success", 
        {"department_id": department.id, "department_name": department.name}
    )
    
    return redirect('department_list')


from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.db.models import Q
from django.shortcuts import redirect
from .models import Role, StaffMember
from .forms import RoleForm
from .utils import is_management, log_security_event

class RoleListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Role
    template_name = 'careapp/role_list.html'
    context_object_name = 'roles'
    paginate_by = 12
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_queryset(self):
        # Log access to role list
        log_security_event(
            self.request, 
            "Role List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = Role.objects.all().order_by('name')
        
        # Apply filters
        search = self.request.GET.get('search')
        is_management_filter = self.request.GET.get('is_management')
        can_manage_staff_filter = self.request.GET.get('can_manage_staff')
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search)
            )
        
        if is_management_filter:
            if is_management_filter.lower() == 'true':
                queryset = queryset.filter(is_management=True)
            elif is_management_filter.lower() == 'false':
                queryset = queryset.filter(is_management=False)
        
        if can_manage_staff_filter:
            if can_manage_staff_filter.lower() == 'true':
                queryset = queryset.filter(can_manage_staff=True)
            elif can_manage_staff_filter.lower() == 'false':
                queryset = queryset.filter(can_manage_staff=False)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add filter values to context for preserving in pagination
        context['filter_params'] = self.request.GET.copy()
        if 'page' in context['filter_params']:
            del context['filter_params']['page']
        return context


class RoleCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = 'careapp/role_form.html'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('role_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Save the form first to get the instance
        response = super().form_valid(form)
        
        # Log role creation
        log_security_event(
            self.request, 
            "Role Created", 
            "Success", 
            {"role_id": self.object.id, "role_name": self.object.name}
        )
        return response
    
    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class RoleUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = 'careapp/role_form.html'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('role_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Save the form first to get the instance
        response = super().form_valid(form)
        
        # Log role update
        log_security_event(
            self.request, 
            "Role Updated", 
            "Success", 
            {"role_id": self.object.id, "role_name": self.object.name}
        )
        return response
    
    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class RoleDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Role
    template_name = 'careapp/role_detail.html'
    context_object_name = 'role'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role = self.get_object()

        # Get users with this role from StaffMember
        staff_with_role = StaffMember.objects.filter(role=role).select_related('user')
        context['users_with_role'] = [staff.user for staff in staff_with_role]

        # Log access
        log_security_event(
            self.request, 
            "Role Detail Access", 
            "Success", 
            {"role_id": role.id, "role_name": role.name}
        )
        return context


# Staff Shift Views
class StaffShiftListView(LoginRequiredMixin, ListView):
    model = StaffShift
    template_name = 'careapp/staffshift_list.html'
    context_object_name = 'shifts'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to staff shift list
        log_security_event(
            self.request, 
            "Staff Shift List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = StaffShift.objects.all().select_related('staff_member__user')
        
        # Filter by staff member if provided
        staff_member_id = self.request.GET.get('staff_member')
        if staff_member_id:
            queryset = queryset.filter(staff_member_id=staff_member_id)
        
        # Filter by date range if provided
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(shift_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(shift_date__lte=date_to)
        
        # Filter by shift type if provided
        shift_type = self.request.GET.get('shift_type')
        if shift_type:
            queryset = queryset.filter(shift_type=shift_type)
        
        # Filter by completion status if provided
        is_completed = self.request.GET.get('is_completed')
        if is_completed in ['true', 'false']:
            queryset = queryset.filter(is_completed=(is_completed == 'true'))
        
        return queryset.order_by('-shift_date', 'start_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff_members'] = StaffMember.objects.filter(is_active=True)
        context['shift_types'] = StaffShift.SHIFT_TYPES
        
        # Add filter parameters to context
        for param in ['staff_member', 'date_from', 'date_to', 'shift_type', 'is_completed']:
            context[param] = self.request.GET.get(param)
        
        return context


class StaffShiftCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = StaffShift
    form_class = StaffShiftForm
    template_name = 'careapp/staffshift_form.html'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('staffshift_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log staff shift creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Staff Shift Created", 
            "Success", 
            {"staff_shift_id": self.object.id, "staff_member": f"{self.object.staff_member.user.first_name} {self.object.staff_member.user.last_name}"}
        )
        return response


class StaffShiftUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = StaffShift
    form_class = StaffShiftForm
    template_name = 'careapp/staffshift_form.html'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('staffshift_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log staff shift update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Staff Shift Updated", 
            "Success", 
            {"staff_shift_id": self.object.id, "staff_member": f"{self.object.staff_member.user.first_name} {self.object.staff_member.user.last_name}"}
        )
        return response


# views.py
from django.views.generic import DetailView

class StaffShiftDetailView(LoginRequiredMixin, DetailView):
    model = StaffShift
    template_name = 'careapp/staffshift_detail.html'
    context_object_name = 'staff_shift'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Log access to staff shift detail
        log_security_event(
            self.request,
            "Staff Shift Detail Access",
            "Success",
            {"staff_shift_id": self.object.id}
        )
        return context


@login_required
@user_passes_test(is_management)
def staff_shift_toggle_completed(request, pk):
    staff_shift = get_object_or_404(StaffShift, pk=pk)
    staff_shift.is_completed = not staff_shift.is_completed
    staff_shift.save()
    
    status = "completed" if staff_shift.is_completed else "marked as not completed"
    messages.success(request, f"Staff shift {status}.")
    
    # Log staff shift status change
    log_security_event(
        request, 
        f"Staff Shift Completion Status Changed", 
        "Success", 
        {"staff_shift_id": staff_shift.id, "is_completed": staff_shift.is_completed}
    )
    
    return redirect('staffshift_list')


# Daily Summary Views
class DailySummaryListView(LoginRequiredMixin, ListView):
    model = DailySummary
    template_name = 'careapp/dailysummary_list.html'
    context_object_name = 'dailysummaries'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to daily summary list
        log_security_event(
            self.request, 
            "Daily Summary List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = DailySummary.objects.all().select_related('shift__staff_member__user')
        
        # Filter by staff member if provided
        staff_member_id = self.request.GET.get('staff_member')
        if staff_member_id:
            queryset = queryset.filter(shift__staff_member_id=staff_member_id)
        
        # Filter by date range if provided
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(shift__shift_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(shift__shift_date__lte=date_to)
        
        return queryset.order_by('-shift__shift_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff_members'] = StaffMember.objects.filter(is_active=True)
        
        # Add filter parameters to context
        for param in ['staff_member', 'date_from', 'date_to']:
            context[param] = self.request.GET.get(param)
        
        return context


class DailySummaryCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = DailySummary
    form_class = DailySummaryForm
    template_name = 'careapp/dailysummary_form.html'
    
    def test_func(self):
        # Only allow staff to create their own daily summaries
        try:
            staff_member = StaffMember.objects.get(user=self.request.user)
            return True
        except StaffMember.DoesNotExist:
            return False
    
    def get_success_url(self):
        return reverse_lazy('dailysummary_list')
    
    def form_valid(self, form):
      # Get current staff member
      try:
          staff_member = StaffMember.objects.get(user=self.request.user)
      except StaffMember.DoesNotExist:
          raise PermissionDenied("Only staff members can create daily summaries.")
      
      # Check if a summary already exists for this shift
      shift = form.cleaned_data['shift']
      if shift.staff_member != staff_member:
          form.add_error('shift', 'You can only create summaries for your own shifts.')
          return self.form_invalid(form)
      
      if DailySummary.objects.filter(shift=shift).exists():
          form.add_error('shift', 'A summary already exists for this shift.')
          return self.form_invalid(form)
      
      form.instance.created_by = self.request.user
      form.instance.updated_by = self.request.user
      
      # Log daily summary creation
      response = super().form_valid(form)
      log_security_event(
          self.request, 
          "Daily Summary Created", 
          "Success", 
          {
              "daily_summary_id": self.object.id, 
              "shift_date": str(self.object.shift.shift_date)  # Convert to string
          }
      )
      return response


class DailySummaryUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = DailySummary
    form_class = DailySummaryForm
    template_name = 'careapp/dailysummary_form.html'
    
    def test_func(self):
        # Only allow the creator or management to update daily summaries
        if is_management(self.request.user):
            return True
        
        try:
            staff_member = StaffMember.objects.get(user=self.request.user)
            return self.object.shift.staff_member == staff_member
        except StaffMember.DoesNotExist:
            return False
    
    def get_success_url(self):
        return reverse_lazy('dailysummary_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log daily summary update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Daily Summary Updated", 
            "Success", 
            {"daily_summary_id": self.object.id, "shift_date": self.object.shift.shift_date}
        )
        return response


@login_required
def daily_summary_detail(request, pk):
    dailysummary = get_object_or_404(DailySummary, pk=pk)
    
    # Log daily summary detail access
    log_security_event(
        request, 
        "Daily Summary Detail Access", 
        "Success", 
        {
            "daily_summary_id": dailysummary.id,
            "shift_date": str(dailysummary.shift.shift_date)  # Ensure it's string for JSON
        }
    )
    
    return render(request, 'careapp/dailysummary_detail.html', {'dailysummary': dailysummary})



# Utility function to check if user is staff

# Utility function to check if user is admin
def is_admin(user):
    return user.is_superuser or user.is_staff

class StaffHandoverListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = StaffHandover
    template_name = 'careapp/staffhandover_list.html'
    context_object_name = 'handovers'
    paginate_by = 20
    
    def test_func(self):
        # Allow staff, management, and admin users
        return is_staff(self.request.user) or is_management(self.request.user) or is_admin(self.request.user)
    
    def get_queryset(self):
        # Log access to staff handover list
        log_security_event(
            self.request, 
            "Staff Handover List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = StaffHandover.objects.all().select_related(
            'handed_over_by__user', 'handed_over_to__user'
        )
        
        # Filter by date range if provided
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(shift_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(shift_date__lte=date_to)
        
        # Filter by shift type if provided
        shift_type = self.request.GET.get('shift_type')
        if shift_type:
            queryset = queryset.filter(shift_type=shift_type)
        
        # Filter by acknowledged status if provided
        acknowledged = self.request.GET.get('acknowledged')
        if acknowledged in ['true', 'false']:
            queryset = queryset.filter(acknowledged=(acknowledged == 'true'))
        
        # If user is staff (not management/admin), show only their handovers or handovers to them
        if is_staff(self.request.user) and not (is_management(self.request.user) or is_admin(self.request.user)):
            staff_member = self.request.user.staffmember
            queryset = queryset.filter(
                Q(handed_over_by=staff_member) | 
                Q(handed_over_to=staff_member)
            )
        
        return queryset.order_by('-shift_date', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter parameters to context
        for param in ['date_from', 'date_to', 'shift_type', 'acknowledged']:
            context[param] = self.request.GET.get(param)
        
        # Add user type to context for template logic
        context['is_management'] = is_management(self.request.user)
        context['is_admin'] = is_admin(self.request.user)
        
        return context


class StaffHandoverCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = StaffHandover
    form_class = StaffHandoverForm
    template_name = 'careapp/staffhandover_form.html'
    
    def test_func(self):
        # Allow staff, management, and admin users to create handovers
        return is_staff(self.request.user) or is_management(self.request.user) or is_admin(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('staffhandover_list')
    
    def get_initial(self):
        initial = super().get_initial()
        # Set current staff member as the one handing over if they are staff
        if hasattr(self.request.user, 'staffmember'):
            initial['handed_over_by'] = self.request.user.staffmember
        # Set default date to today
        initial['shift_date'] = timezone.now().date()
        return initial
    
    def form_valid(self, form):
        # Get current user
        user = self.request.user
        
        # If user is staff, set them as the one handing over
        if hasattr(user, 'staffmember'):
            form.instance.handed_over_by = user.staffmember
        
        form.instance.created_by = user
        form.instance.updated_by = user
        
        # Log staff handover creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Staff Handover Created", 
            "Success", 
            {
                "handover_id": self.object.id,
                "shift_date": self.object.shift_date.isoformat()  # <-- FIX
            }
        )
        return response


class StaffHandoverUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = StaffHandover
    form_class = StaffHandoverForm
    template_name = 'careapp/staffhandover_form.html'
    
    def test_func(self):
        handover = self.get_object()
        user = self.request.user
        
        # Allow update if:
        # 1. User is admin or management
        # 2. User created the handover
        return (is_management(user) or is_admin(user) or 
                (hasattr(user, 'staffmember') and handover.handed_over_by.user == user))
    
    def get_success_url(self):
        return reverse_lazy('staffhandover_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log staff handover update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Staff Handover Updated", 
            "Success", 
            {"handover_id": self.object.id, "shift_date": self.object.shift_date}
        )
        return response


@login_required
def staff_handover_acknowledge(request, pk):
    handover = get_object_or_404(StaffHandover, pk=pk)
    user = request.user
    
    # Check if user is the recipient of the handover or has management/admin privileges
    if not (hasattr(user, 'staffmember') and handover.handed_over_to.user == user) and not (is_management(user) or is_admin(user)):
        raise PermissionDenied("You can only acknowledge handovers addressed to you.")
    
    if not handover.acknowledged:
        handover.acknowledged = True
        handover.acknowledged_at = timezone.now()
        handover.save()
        
        messages.success(request, "Handover acknowledged.")
        
        # Log handover acknowledgment
        log_security_event(
            request, 
            "Staff Handover Acknowledged", 
            "Success", 
            {"handover_id": handover.id, "shift_date": handover.shift_date}
        )
    
    return redirect('staffhandover_list')


@login_required
def staff_handover_detail(request, pk):
    handover = get_object_or_404(StaffHandover, pk=pk)
    user = request.user
    
    # Check if user has permission to view this handover
    # Allow if:
    # 1. User is management or admin
    # 2. User created the handover
    # 3. User is the recipient of the handover
    if (not (is_management(user) or is_admin(user)) and 
        not (hasattr(user, 'staffmember') and 
             (handover.handed_over_by.user == user or 
              handover.handed_over_to.user == user))):
        raise PermissionDenied("You don't have permission to view this handover.")
    
    # Log handover detail access
    log_security_event(
          request, 
          "Staff Handover Detail Access", 
          "Success", 
          {
              "handover_id": handover.id,
              "shift_date": handover.shift_date.isoformat()  # Convert to string
          }
      )
    
    return render(request, 'careapp/staffhandover_detail.html', {
        'handover': handover,
        'is_management': is_management(user),
        'is_admin': is_admin(user)
    })


# Management Daily Note Views
class ManagementDailyNoteListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ManagementDailyNote
    template_name = 'careapp/managementdailynote_list.html'
    context_object_name = 'managementdailynotes'
    paginate_by = 20
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_queryset(self):
        # Log access to management daily note list
        log_security_event(
            self.request, 
            "Management Daily Note List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = ManagementDailyNote.objects.all().select_related(
            'related_department', 'related_service_user', 'related_staff__user',
            'resolved_by__user'
        )
        
        # Filter by priority if provided
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Filter by action required if provided
        action_required = self.request.GET.get('action_required')
        if action_required in ['true', 'false']:
            queryset = queryset.filter(action_required=(action_required == 'true'))
        
        # Filter by resolved status if provided
        is_resolved = self.request.GET.get('is_resolved')
        if is_resolved in ['true', 'false']:
            queryset = queryset.filter(is_resolved=(is_resolved == 'true'))
        
        # Filter by department if provided
        department_id = self.request.GET.get('department')
        if department_id:
            queryset = queryset.filter(related_department_id=department_id)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['priorities'] = [choice[0] for choice in ManagementDailyNote._meta.get_field('priority').choices]
        context['departments'] = Department.objects.filter(is_active=True)
        
        # Add filter parameters to context
        for param in ['priority', 'action_required', 'is_resolved', 'department']:
            context[param] = self.request.GET.get(param)
        
        return context


class ManagementDailyNoteCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ManagementDailyNote
    form_class = ManagementDailyNoteForm
    template_name = 'careapp/managementdailynote_form.html'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('managementdailynote_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log management daily note creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Management Daily Note Created", 
            "Success", 
            {"note_id": self.object.id, "note_title": self.object.title}
        )
        return response


class ManagementDailyNoteUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ManagementDailyNote
    form_class = ManagementDailyNoteForm
    template_name = 'careapp/managementdailynote_form.html'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('managementdailynote_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # If note is being resolved, set resolved_by and resolved_at
        if form.cleaned_data.get('is_resolved') and not self.object.is_resolved:
            try:
                staff_member = StaffMember.objects.get(user=self.request.user)
                form.instance.resolved_by = staff_member
                form.instance.resolved_at = timezone.now()
            except StaffMember.DoesNotExist:
                pass
        
        # Log management daily note update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Management Daily Note Updated", 
            "Success", 
            {"note_id": self.object.id, "note_title": self.object.title}
        )
        return response
    

from django.views.generic.detail import DetailView

class ManagementDailyNoteDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = ManagementDailyNote
    template_name = 'careapp/managementdailynote_detail.html'
    context_object_name = 'note'

    def test_func(self):
        return is_management(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Log note detail access
        log_security_event(
            self.request,
            "Management Daily Note Detail Access",
            "Success",
            {"note_id": self.object.id, "note_title": self.object.title}
        )
        return context



@login_required
@user_passes_test(is_management)
def management_daily_note_resolve(request, pk):
    note = get_object_or_404(ManagementDailyNote, pk=pk)
    
    if not note.is_resolved:
        note.is_resolved = True
        try:
            staff_member = StaffMember.objects.get(user=request.user)
            note.resolved_by = staff_member
            note.resolved_at = timezone.now()
        except StaffMember.DoesNotExist:
            pass
        note.save()
        
        messages.success(request, "Note marked as resolved.")
        
        # Log note resolution
        log_security_event(
            request, 
            "Management Daily Note Resolved", 
            "Success", 
            {"note_id": note.id, "note_title": note.title}
        )
    
    return redirect('managementdailynote_list')



# Management Handover Views
class ManagementHandoverListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ManagementHandover
    template_name = 'careapp/managementhandover_list.html'
    context_object_name = 'managementhandovers'
    paginate_by = 20
    
    def test_func(self):
        return is_management(self.request.user) or self.request.user.is_staff
    
    def get_queryset(self):
        # Log access to management handover list
        log_security_event(
            self.request, 
            "Management Handover List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = ManagementHandover.objects.all().select_related(
            'handed_over_by__user', 'handed_over_to__user'
        )
        
        # Filter by date range if provided
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(handover_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(handover_date__lte=date_to)
        
        # Filter by handed over by if provided
        handed_over_by = self.request.GET.get('handed_over_by')
        if handed_over_by:
            queryset = queryset.filter(handed_over_by_id=handed_over_by)
        
        # Filter by handed over to if provided
        handed_over_to = self.request.GET.get('handed_over_to')
        if handed_over_to:
            queryset = queryset.filter(handed_over_to_id=handed_over_to)
        
        # Filter by acknowledged status if provided
        acknowledged = self.request.GET.get('acknowledged')
        if acknowledged in ['true', 'false']:
            queryset = queryset.filter(acknowledged=(acknowledged == 'true'))
        
        # Search filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(urgent_matters__icontains=search) |
                Q(key_tasks__icontains=search) |
                Q(general_notes__icontains=search)
            )
        
        return queryset.order_by('-handover_date', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_staff'] = StaffMember.objects.all()
        
        # Add filter parameters to context
        for param in ['date_from', 'date_to', 'acknowledged', 'handed_over_by', 'handed_over_to', 'search']:
            context[param] = self.request.GET.get(param)
        
        return context


class ManagementHandoverCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ManagementHandover
    form_class = ManagementHandoverForm
    template_name = 'careapp/managementhandover_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or self.request.user.is_staff
    
    def get_success_url(self):
        return reverse_lazy('managementhandover_list')
    
    def form_valid(self, form):
        # Get current staff member
        try:
            staff_member = StaffMember.objects.get(user=self.request.user)
            form.instance.handed_over_by = staff_member
        except StaffMember.DoesNotExist:
            raise PermissionDenied("Only staff members can create handovers.")
        
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log management handover creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Management Handover Created", 
            "Success", 
            {"handover_id": self.object.id, "handover_date": self.object.handover_date}
        )
        return response


class ManagementHandoverUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ManagementHandover
    form_class = ManagementHandoverForm
    template_name = 'careapp/managementhandover_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or self.request.user.is_staff
    
    def get_success_url(self):
        return reverse_lazy('managementhandover_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log management handover update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Management Handover Updated", 
            "Success", 
            {"handover_id": self.object.id, "handover_date": self.object.handover_date}
        )
        return response


@login_required
@user_passes_test(lambda u: is_management(u) or u.is_staff)
def management_handover_acknowledge(request, pk):
    handover = get_object_or_404(ManagementHandover, pk=pk)
    
    if not handover.acknowledged:
        handover.acknowledged = True
        handover.acknowledged_at = timezone.now()
        handover.save()
        
        messages.success(request, "Handover acknowledged.")
        
        # Log handover acknowledgment
        log_security_event(
            request, 
            "Management Handover Acknowledged", 
            "Success", 
            {"handover_id": handover.id, "handover_date": handover.handover_date}
        )
    
    return redirect('managementhandover_list')


@login_required
@user_passes_test(lambda u: is_management(u) or u.is_staff)
def management_handover_detail(request, pk):
    handover = get_object_or_404(ManagementHandover, pk=pk)
    
    # Log handover detail access
    log_security_event(
        request, 
        "Management Handover Detail Access", 
        "Success", 
        {"handover_id": handover.id, "handover_date": handover.handover_date}
    )
    
    return render(request, 'careapp/managementhandover_detail.html', {'handover': handover})


# Governance Record Views
class GovernanceRecordListView(LoginRequiredMixin, ListView):
    model = GovernanceRecord
    template_name = 'careapp/governancerecord_list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        # Log access to governance record list
        log_security_event(
            self.request,
            "Governance Record List Access",
            "Success",
            {"view": "list"}
        )

        queryset = GovernanceRecord.objects.all().select_related(
            'related_department', 'related_service_user', 'related_staff__user'
        ).prefetch_related('documents')

        # Filter by record type if provided
        record_type = self.request.GET.get('record_type')
        if record_type:
            queryset = queryset.filter(record_type=record_type)

        # Filter by follow-up required if provided
        follow_up_required = self.request.GET.get('follow_up_required')
        if follow_up_required in ['true', 'false']:
            queryset = queryset.filter(follow_up_required=(follow_up_required == 'true'))

        # Filter by confidential status if provided
        is_confidential = self.request.GET.get('is_confidential')
        if is_confidential in ['true', 'false']:
            queryset = queryset.filter(is_confidential=(is_confidential == 'true'))

        # Filter by department if provided
        department_id = self.request.GET.get('department')
        if department_id:
            queryset = queryset.filter(related_department_id=department_id)

        return queryset.order_by('-date_occurred', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['record_types'] = GovernanceRecord.RECORD_TYPES
        context['departments'] = Department.objects.filter(is_active=True)

        # Add filter parameters to context
        for param in ['record_type', 'follow_up_required', 'is_confidential', 'department']:
            context[param] = self.request.GET.get(param)

        return context


class GovernanceRecordCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = GovernanceRecord
    form_class = GovernanceRecordForm
    template_name = 'careapp/governancerecord_form.html'

    def test_func(self):
        return is_management(self.request.user)

    def get_success_url(self):
        return reverse_lazy('governancerecord_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user

        # Save the form and set self.object
        response = super().form_valid(form)

        # Log creation event
        log_security_event(
            self.request,
            "Governance Record Created",
            "Success",
            {
                "record_id": self.object.id,
                "record_title": self.object.title
            }
        )
        return response


class GovernanceRecordUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = GovernanceRecord
    form_class = GovernanceRecordForm
    template_name = 'careapp/governancerecord_form.html'

    def test_func(self):
        return is_management(self.request.user)

    def get_success_url(self):
        return reverse_lazy('governancerecord_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user

        # Save the form and set self.object
        response = super().form_valid(form)

        # Log update event
        log_security_event(
            self.request,
            "Governance Record Updated",
            "Success",
            {
                "record_id": self.object.id,
                "record_title": self.object.title
            }
        )
        return response


@login_required
def governance_record_detail(request, pk):
    record = get_object_or_404(GovernanceRecord, pk=pk)

    # Restrict confidential records to management only
    if record.is_confidential and not is_management(request.user):
        raise PermissionDenied("You don't have permission to view this confidential record.")

    # Log detail access
    log_security_event(
        request,
        "Governance Record Detail Access",
        "Success",
        {"record_id": record.id, "record_title": record.title}
    )

    return render(request, 'careapp/governancerecord_detail.html', {'record': record})



# Vital Signs Views
class VitalSignsListView(LoginRequiredMixin, ListView):
    model = VitalSigns
    template_name = 'careapp/vitalsigns_list.html'
    context_object_name = 'vital_signs'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to vital signs list
        log_security_event(
            self.request, 
            "Vital Signs List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = VitalSigns.objects.all().select_related('service_user', 'recorded_by__user')
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(service_user_id=service_user_id)
        
        # Filter by date range if provided
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(recorded_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(recorded_date__lte=date_to)
        
        return queryset.order_by('-recorded_date', '-recorded_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_users'] = ServiceUser.objects.filter(is_active=True)
        
        # Add filter parameters to context
        for param in ['service_user', 'date_from', 'date_to']:
            context[param] = self.request.GET.get(param)
        
        return context


class VitalSignsCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = VitalSigns
    form_class = VitalSignsForm
    template_name = 'careapp/vitalsigns_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or is_staff(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('vitalsigns_list')
    
    def form_valid(self, form):
        # Get current staff member
        try:
            staff_member = StaffMember.objects.get(user=self.request.user)
            form.instance.recorded_by = staff_member
        except StaffMember.DoesNotExist:
            raise PermissionDenied("Only staff members can record vital signs.")
        
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log vital signs creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Vital Signs Recorded", 
            "Success", 
            {"vital_signs_id": self.object.id, "service_user": f"{self.object.service_user.first_name} {self.object.service_user.last_name}"}
        )
        return response


class VitalSignsUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = VitalSigns
    form_class = VitalSignsForm
    template_name = 'careapp/vitalsigns_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or is_staff(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('vitalsigns_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log vital signs update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Vital Signs Updated", 
            "Success", 
            {"vital_signs_id": self.object.id, "service_user": f"{self.object.service_user.first_name} {self.object.service_user.last_name}"}
        )
        return response


@login_required
def vital_signs_detail(request, pk):
    vital_signs = get_object_or_404(VitalSigns, pk=pk)
    
    # Log vital signs detail access
    log_security_event(
        request, 
        "Vital Signs Detail Access", 
        "Success", 
        {"vital_signs_id": vital_signs.id, "service_user": f"{vital_signs.service_user.first_name} {vital_signs.service_user.last_name}"}
    )
    
    return render(request, 'careapp/vitalsigns_detail.html', {'vital_signs': vital_signs})






# Document Views
class DocumentListView(LoginRequiredMixin, ListView):
    model = Document
    template_name = 'careapp/document_list.html'
    context_object_name = 'documents'
    paginate_by = 20
    
    def get_queryset(self):
        # Log access to document list
        log_security_event(
            self.request, 
            "Document List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = Document.objects.all().select_related('service_user')
        
        # Filter by document type if provided
        document_type = self.request.GET.get('document_type')
        if document_type:
            queryset = queryset.filter(document_type=document_type)
        
        # Filter by service user if provided
        service_user_id = self.request.GET.get('service_user')
        if service_user_id:
            queryset = queryset.filter(service_user_id=service_user_id)
        
        # Filter by confidential status if provided
        is_confidential = self.request.GET.get('is_confidential')
        if is_confidential in ['true', 'false']:
            queryset = queryset.filter(is_confidential=(is_confidential == 'true'))
        
        # Filter by CQC viewable status if provided
        cqc_can_view = self.request.GET.get('cqc_can_view')
        if cqc_can_view in ['true', 'false']:
            queryset = queryset.filter(cqc_can_view=(cqc_can_view == 'true'))
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )
        
        # For CQC users, only show documents they can view
        if is_cqc(self.request.user):
            queryset = queryset.filter(cqc_can_view=True)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['document_types'] = Document.DOCUMENT_TYPES
        context['service_users'] = ServiceUser.objects.filter(is_active=True)
        
        # Add filter parameters to context
        for param in ['document_type', 'service_user', 'is_confidential', 'cqc_can_view', 'search']:
            context[param] = self.request.GET.get(param)
        
        return context


class DocumentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Document
    form_class = DocumentForm
    template_name = 'careapp/document_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or self.request.user.is_staff
    
    def get_success_url(self):
        return reverse_lazy('document_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Log document creation
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Document Created", 
            "Success", 
            {"document_id": self.object.id, "document_title": self.object.title}
        )
        return response


class DocumentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Document
    form_class = DocumentForm
    template_name = 'careapp/document_form.html'
    
    def test_func(self):
        return is_management(self.request.user) or self.request.user.is_staff
    
    def get_success_url(self):
        return reverse_lazy('document_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log document update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "Document Updated", 
            "Success", 
            {"document_id": self.object.id, "document_title": self.object.title}
        )
        return response


@login_required
def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Check if user can view confidential documents
    if document.is_confidential and not (is_management(request.user) or request.user.is_staff):
        raise PermissionDenied("You don't have permission to view this confidential document.")
    
    # Check if CQC user can view this document
    if is_cqc(request.user) and not document.cqc_can_view:
        raise PermissionDenied("This document is not available for CQC viewing.")
    
    # Log document detail access
    log_security_event(
        request, 
        "Document Detail Access", 
        "Success", 
        {"document_id": document.id, "document_title": document.title}
    )
    
    return render(request, 'careapp/document_detail.html', {'document': document})


@login_required
def document_download(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Check if user can download confidential documents
    if document.is_confidential and not (is_management(request.user) or request.user.is_staff):
        raise PermissionDenied("You don't have permission to download this confidential document.")
    
    # Check if CQC user can download this document
    if is_cqc(request.user) and not document.cqc_can_view:
        raise PermissionDenied("This document is not available for CQC download.")
    
    # Log document download
    log_security_event(
        request, 
        "Document Downloaded", 
        "Success", 
        {"document_id": document.id, "document_title": document.title, "downloaded_by": request.user.username}
    )
    
    # Serve the file for download
    response = FileResponse(document.file.open(), as_attachment=True, filename=document.file.name)
    return response


# System Setting Views
class SystemSettingListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = SystemSetting
    template_name = 'careapp/systemsetting_list.html'
    context_object_name = 'settings'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_queryset(self):
        # Log access to system setting list
        log_security_event(
            self.request, 
            "System Setting List Access", 
            "Success", 
            {"view": "list"}
        )
        
        queryset = SystemSetting.objects.all()
        
        # Filter by active status if provided
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=(is_active == 'true'))
        
        return queryset.order_by('key')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter parameters to context
        context['is_active'] = self.request.GET.get('is_active')
        
        return context


class SystemSettingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = SystemSetting
    form_class = SystemSettingForm
    template_name = 'careapp/systemsetting_form.html'
    
    def test_func(self):
        return is_management(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('systemsetting_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Log system setting update
        response = super().form_valid(form)
        log_security_event(
            self.request, 
            "System Setting Updated", 
            "Success", 
            {"setting_id": self.object.id, "setting_key": self.object.key}
        )
        return response


# Security Dashboard View
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q, F
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from datetime import timedelta
import json
from .models import SecurityLog, StaffMember, User, AuditLog, CQCAccessLog
from .utils import is_management, log_security_event, get_location_from_ip, check_brute_force

@login_required
@user_passes_test(is_management)
def security_dashboard(request):
    """Enhanced security dashboard with comprehensive monitoring"""
    
    # Time filters
    time_range = request.GET.get('time_range', '24h')
    
    if time_range == '7d':
        start_time = timezone.now() - timedelta(days=7)
    elif time_range == '30d':
        start_time = timezone.now() - timedelta(days=30)
    else:  # 24h default
        start_time = timezone.now() - timedelta(hours=24)
    
    # Basic security metrics
    security_logs = SecurityLog.objects.all().select_related('user').order_by('-timestamp')
    
    # Paginate security logs
    logs_paginator = Paginator(security_logs, 50)  # 50 events per page
    logs_page = request.GET.get('logs_page')
    logs_page_obj = logs_paginator.get_page(logs_page)
    
    failed_logins_count = SecurityLog.objects.filter(
        action__icontains='login',
        status='Failed',
        timestamp__gte=start_time
    ).count()
    
    suspicious_activities_count = SecurityLog.objects.filter(
        status='Suspicious',
        timestamp__gte=start_time
    ).count()
    
    unique_ips_count = SecurityLog.objects.filter(
        timestamp__gte=start_time
    ).values('ip_address').distinct().count()
    
    # Advanced metrics
    brute_force_attempts = SecurityLog.objects.filter(
        action__icontains='brute force',
        timestamp__gte=start_time
    ).count()
    
    sql_injection_attempts = SecurityLog.objects.filter(
        action__icontains='sql injection',
        timestamp__gte=start_time
    ).count()
    
    # User activity metrics
    active_users_count = SecurityLog.objects.filter(
        timestamp__gte=start_time,
        user__isnull=False
    ).values('user').distinct().count()
    
    # Top suspicious IPs
    top_suspicious_ips = SecurityLog.objects.filter(
        status='Suspicious',
        timestamp__gte=start_time
    ).values('ip_address').annotate(
        count=Count('id'),
        last_activity=F('timestamp')
    ).order_by('-count')[:10]
    
    # Add location data to suspicious IPs
    for ip_data in top_suspicious_ips:
        ip_data['location'] = get_location_from_ip(ip_data['ip_address'])
    
    # Failed login trends
    failed_login_trends = []
    if time_range == '24h':
        for i in range(24):
            hour_start = start_time + timedelta(hours=i)
            hour_end = hour_start + timedelta(hours=1)
            count = SecurityLog.objects.filter(
                action__icontains='login',
                status='Failed',
                timestamp__gte=hour_start,
                timestamp__lt=hour_end
            ).count()
            failed_login_trends.append({
                'hour': hour_start.strftime('%H:00'),
                'count': count
            })
    else:
        # For longer time ranges, show daily trends
        days = 7 if time_range == '7d' else 30
        for i in range(days):
            day_start = start_time + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            count = SecurityLog.objects.filter(
                action__icontains='login',
                status='Failed',
                timestamp__gte=day_start,
                timestamp__lt=day_end
            ).count()
            failed_login_trends.append({
                'hour': day_start.strftime('%m/%d'),
                'count': count
            })
    
    # User agent analysis
    top_user_agents = SecurityLog.objects.filter(
        timestamp__gte=start_time
    ).values('details__browser').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Geographic distribution
    geographic_data = []
    unique_ips = SecurityLog.objects.filter(
        timestamp__gte=start_time
    ).values_list('ip_address', flat=True).distinct()
    
    for ip in unique_ips[:50]:  # Limit to first 50 for performance
        location = get_location_from_ip(ip)
        if location:
            geographic_data.append({
                'ip': ip,
                'country': location.get('country', 'Unknown'),
                'city': location.get('city', 'Unknown'),
                'lat': location.get('latitude'),
                'lng': location.get('longitude')
            })
    
    # CQC access monitoring
    cqc_access_logs = CQCAccessLog.objects.select_related('cqc_member').order_by('-access_date')[:50]
    
    # System audit logs
    system_audit_logs = AuditLog.objects.select_related('user').order_by('-created_at')[:50]
    
    # Staff security status
    staff_security_status = []
    for staff in StaffMember.objects.filter(is_active=True).select_related('user')[:20]:
        last_login = SecurityLog.objects.filter(
            user=staff.user,
            action__icontains='login',
            status='Success'
        ).order_by('-timestamp').first()
        
        failed_attempts = SecurityLog.objects.filter(
            user=staff.user,
            action__icontains='login',
            status='Failed',
            timestamp__gte=start_time
        ).count()
        
        staff_security_status.append({
            'staff': staff,
            'last_login': last_login.timestamp if last_login else None,
            'failed_attempts': failed_attempts,
            'status': 'Active' if last_login and last_login.timestamp >= start_time else 'Inactive'
        })
    
    context = {
        # Basic metrics
        'logs_page_obj': logs_page_obj,
        'failed_logins': failed_logins_count,
        'suspicious_activities': suspicious_activities_count,
        'unique_ips': unique_ips_count,
        
        # Advanced metrics
        'brute_force_attempts': brute_force_attempts,
        'sql_injection_attempts': sql_injection_attempts,
        'active_users': active_users_count,
        
        # Detailed data
        'top_suspicious_ips': top_suspicious_ips,
        'failed_login_trends': failed_login_trends,
        'top_user_agents': top_user_agents,
        'geographic_data': geographic_data,
        'cqc_access_logs': cqc_access_logs,
        'system_audit_logs': system_audit_logs,
        'staff_security_status': staff_security_status,
        
        # Time ranges for filters
        'time_range': time_range,
        'start_time': start_time,
    }
    
    # Log access to security dashboard
    log_security_event(
        request, 
        "Security Dashboard Access", 
        "Success", 
        {"page": "security_dashboard", "time_range": time_range}
    )
    
    return render(request, 'careapp/security_dashboard.html', context)

@login_required
@user_passes_test(is_management)
def security_dashboard_data(request):
    """AJAX endpoint for security dashboard data"""
    time_range = request.GET.get('time_range', '24h')
    
    if time_range == '7d':
        start_time = timezone.now() - timedelta(days=7)
    elif time_range == '30d':
        start_time = timezone.now() - timedelta(days=30)
    else:  # 24h default
        start_time = timezone.now() - timedelta(hours=24)
    
    # Security events by type
    security_events_by_type = SecurityLog.objects.filter(
        timestamp__gte=start_time
    ).values('action').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Security events by status
    security_events_by_status = SecurityLog.objects.filter(
        timestamp__gte=start_time
    ).values('status').annotate(
        count=Count('id')
    )
    
    # Hourly activity for the selected period
    hourly_data = []
    if time_range == '24h':
        intervals = 24
        delta = timedelta(hours=1)
    elif time_range == '7d':
        intervals = 7
        delta = timedelta(days=1)
    else:  # 30d
        intervals = 30
        delta = timedelta(days=1)
    
    for i in range(intervals):
        interval_start = start_time + (delta * i)
        interval_end = interval_start + delta
        
        count = SecurityLog.objects.filter(
            timestamp__gte=interval_start,
            timestamp__lt=interval_end
        ).count()
        
        if time_range == '24h':
            label = interval_start.strftime('%H:00')
        else:
            label = interval_start.strftime('%Y-%m-%d')
        
        hourly_data.append({
            'label': label,
            'count': count
        })
    
    data = {
        'events_by_type': list(security_events_by_type),
        'events_by_status': list(security_events_by_status),
        'hourly_activity': hourly_data,
        'time_range': time_range
    }
    
    return JsonResponse(data)

@login_required
@user_passes_test(is_management)
def security_logs_search(request):
    """Search and filter security logs"""
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    action_filter = request.GET.get('action', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    ip_address = request.GET.get('ip_address', '')
    
    security_logs = SecurityLog.objects.all().select_related('user').order_by('-timestamp')
    
    # Apply filters
    if query:
        security_logs = security_logs.filter(
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(action__icontains=query) |
            Q(details__icontains=query)
        )
    
    if status_filter:
        security_logs = security_logs.filter(status=status_filter)
    
    if action_filter:
        security_logs = security_logs.filter(action__icontains=action_filter)
    
    if ip_address:
        security_logs = security_logs.filter(ip_address__icontains=ip_address)
    
    if date_from:
        security_logs = security_logs.filter(timestamp__date__gte=date_from)
    
    if date_to:
        security_logs = security_logs.filter(timestamp__date__lte=date_to)
    
    # Get unique values for filter dropdowns
    status_choices = SecurityLog.objects.values_list('status', flat=True).distinct()
    action_choices = SecurityLog.objects.values_list('action', flat=True).distinct()
    
    # Pagination
    paginator = Paginator(security_logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'action_filter': action_filter,
        'ip_address': ip_address,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': status_choices,
        'action_choices': action_choices,
    }
    
    return render(request, 'careapp/security_logs_search.html', context)

@login_required
@user_passes_test(is_management)
def security_event_detail(request, event_id):
    """View detailed information about a security event"""
    security_event = get_object_or_404(SecurityLog, id=event_id)
    
    # Get related events from same IP with pagination
    related_events = SecurityLog.objects.filter(
        ip_address=security_event.ip_address
    ).exclude(id=event_id).order_by('-timestamp')
    
    # Paginate related events
    related_events_paginator = Paginator(related_events, 10)  # 10 events per page
    related_events_page = request.GET.get('related_page')
    related_events_page_obj = related_events_paginator.get_page(related_events_page)
    
    # Get related events from same user with pagination
    user_related_events = []
    if security_event.user:
        user_related_events = SecurityLog.objects.filter(
            user=security_event.user
        ).exclude(id=event_id).order_by('-timestamp')
        
        # Paginate user related events
        user_events_paginator = Paginator(user_related_events, 10)  # 10 events per page
        user_events_page = request.GET.get('user_events_page')
        user_events_page_obj = user_events_paginator.get_page(user_events_page)
    else:
        user_events_page_obj = None
    
    context = {
        'event': security_event,
        'related_events_page_obj': related_events_page_obj,
        'user_events_page_obj': user_events_page_obj,
    }
    
    return render(request, 'careapp/security_event_detail.html', context)

@login_required
@user_passes_test(is_management)
def ip_investigation(request):
    """Investigate activities from a specific IP address"""
    ip_address = request.GET.get('ip', '')
    
    if not ip_address:
        return render(request, 'careapp/ip_investigation.html', {'error': 'No IP address provided'})
    
    # Get all events from this IP with pagination
    events = SecurityLog.objects.filter(ip_address=ip_address).select_related('user').order_by('-timestamp')
    
    # Paginate events
    events_paginator = Paginator(events, 25)  # 25 events per page
    events_page = request.GET.get('events_page')
    events_page_obj = events_paginator.get_page(events_page)
    
    # Get location information
    location = get_location_from_ip(ip_address)
    
    # Get summary statistics
    total_events = events.count()
    unique_users = events.filter(user__isnull=False).values('user').distinct().count()
    first_seen = events.last().timestamp if events.exists() else None
    last_seen = events.first().timestamp if events.exists() else None
    
    # Events by status
    events_by_status = events.values('status').annotate(count=Count('id'))
    
    # Events by action
    events_by_action = events.values('action').annotate(count=Count('id')).order_by('-count')[:10]
    
    context = {
        'ip_address': ip_address,
        'events_page_obj': events_page_obj,
        'location': location,
        'total_events': total_events,
        'unique_users': unique_users,
        'first_seen': first_seen,
        'last_seen': last_seen,
        'events_by_status': events_by_status,
        'events_by_action': events_by_action,
    }
    
    return render(request, 'careapp/ip_investigation.html', context)

@login_required
@user_passes_test(is_management)
def block_ip_address(request):
    """Block an IP address from accessing the system"""
    if request.method == 'POST':
        ip_address = request.POST.get('ip_address')
        reason = request.POST.get('reason', '')
        
        # Log the blocking action
        log_security_event(
            request,
            "IP Address Blocked",
            "Success",
            {
                "ip_address": ip_address,
                "reason": reason,
                "blocked_by": request.user.username
            }
        )
        
        # In a real implementation, you would add the IP to a blocked list
        # This could be stored in the database or in a firewall rule
        
        # For now, we'll just show a success message
        messages.success(request, f'IP address {ip_address} has been blocked successfully.')
        return redirect('security_dashboard')
    
    return redirect('security_dashboard')

@login_required
@user_passes_test(is_management)
def security_report(request):
    """Generate security reports"""
    time_range = request.GET.get('time_range', '7d')
    
    if time_range == '24h':
        start_time = timezone.now() - timedelta(hours=24)
    elif time_range == '30d':
        start_time = timezone.now() - timedelta(days=30)
    else:  # 7d default
        start_time = timezone.now() - timedelta(days=7)
    
    # Comprehensive security report data
    report_data = {
        'time_range': time_range,
        'generated_at': timezone.now(),
        'total_events': SecurityLog.objects.filter(timestamp__gte=start_time).count(),
        'failed_logins': SecurityLog.objects.filter(
            action__icontains='login',
            status='Failed',
            timestamp__gte=start_time
        ).count(),
        'suspicious_activities': SecurityLog.objects.filter(
            status='Suspicious',
            timestamp__gte=start_time
        ).count(),
        'top_offending_ips': list(SecurityLog.objects.filter(
            timestamp__gte=start_time
        ).values('ip_address').annotate(
            count=Count('id')
        ).order_by('-count')[:10]),
        'user_activity_summary': list(SecurityLog.objects.filter(
            timestamp__gte=start_time,
            user__isnull=False
        ).values('user__username').annotate(
            count=Count('id'),
            last_activity=F('timestamp')
        ).order_by('-count')[:20]),
    }
    
    return JsonResponse(report_data)

# Report Generation Views
from .templatetags.medication_filters import is_due_soon
@login_required
@user_passes_test(is_management)
def generate_report(request, report_type):
    today = timezone.now().date()
    
    if report_type == 'daily_activities':
        # Generate daily activities report
        activities = Activity.objects.filter(date=today).select_related('service_user').prefetch_related('staff_involved')
        context = {'activities': activities, 'report_date': today}
        return render(request, 'reports/daily_activities.html', context)
    
    elif report_type == 'medication':
        # Generate medication report
        medications = Medication.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).select_related('service_user').prefetch_related('administrations')
        
        # Calculate statistics
        active_medications = medications.filter(is_active=True).count()
        low_stock_count = sum(1 for med in medications if med.is_active and (med.current_balance / med.total_quantity) * 100 <= 25)
        due_soon_count = sum(1 for med in medications if med.is_active and is_due_soon(med))
        
        context = {
            'medications': medications, 
            'report_date': today,
            'active_medications': active_medications,
            'low_stock_count': low_stock_count,
            'due_soon_count': due_soon_count,
        }
        return render(request, 'reports/medication_report.html', context)
    
    elif report_type == 'incidents':
        # Generate incidents report
        thirty_days_ago = today - timezone.timedelta(days=30)
        incidents = Incident.objects.filter(
            date__gte=thirty_days_ago
        ).select_related('service_user')
        context = {'incidents': incidents, 'report_date': today, 'period': '30 days'}
        return render(request, 'reports/incidents_report.html', context)
    
    elif report_type == 'staff_shifts':
        # Generate staff shifts report
        shifts = StaffShift.objects.filter(
            shift_date=today
        ).select_related('staff_member__user')
        context = {'shifts': shifts, 'report_date': today}
        return render(request, 'reports/staff_shifts_report.html', context)
    
    # Log report generation
    log_security_event(
        request, 
        f"Report Generated: {report_type}", 
        "Success", 
        {"report_type": report_type}
    )
    
    return redirect('dashboard')



from django.http import HttpResponse

def export_medication_administrations(request):
    # Temporary placeholder view
    return HttpResponse("Export functionality coming soon.")



# Permission Denied View
def permission_denied_view(request, exception=None):
    return render(request, '403.html', status=403)