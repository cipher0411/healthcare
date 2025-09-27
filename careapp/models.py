import os
import uuid
from django.db import models
from django.contrib.auth.models import User, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from PIL import Image
from django.db.models import JSONField
from django.contrib.contenttypes.fields import GenericRelation
from phonenumber_field.modelfields import PhoneNumberField
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.crypto import get_random_string
from datetime import timedelta
from datetime import datetime


def generate_staff_id():
    return f"ST{get_random_string(6, '0123456789')}"

def generate_cqc_id():
    return f"CQC{get_random_string(6, '0123456789')}"

def default_cqc_viewable_after():
    return timezone.now() + timedelta(hours=48)


def service_user_photo_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('profiles', filename)


def activity_photo_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('activities', filename)


def document_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('documents', filename)


def staff_photo_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('staff', filename)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='%(class)s_created')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='%(class)s_updated')

    class Meta:
        abstract = True


class SecurityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=100)
    status = models.CharField(max_length=50)  # Success, Failed, Suspicious
    details = JSONField(default=dict)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]


class Department(TimeStampedModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    manager = models.ForeignKey('StaffMember', on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_departments')
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name


# Add this to your existing models.py
from django.contrib.auth.models import User, Group, Permission
from django.db import models
from django.core.exceptions import ValidationError

class Role(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    is_management = models.BooleanField(default=False)
    can_manage_staff = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    can_manage_care_plans = models.BooleanField(default=False)
    can_manage_medications = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name
    
    def clean(self):
        # Ensure management roles have all permissions
        if self.is_management:
            self.can_manage_staff = True
            self.can_view_reports = True
            self.can_manage_care_plans = True
            self.can_manage_medications = True
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['name']


class StaffMember(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    staff_id = models.CharField(max_length=20, unique=True, default=generate_staff_id)
    photo = models.ImageField(upload_to=staff_photo_path, null=True, blank=True)
    phone_number = PhoneNumberField()
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.CharField(max_length=100)
    qualifications = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = PhoneNumberField(blank=True)
    emergency_contact_relationship = models.CharField(max_length=100, blank=True)
    dbs_check_date = models.DateField(null=True, blank=True)
    dbs_check_reference = models.CharField(max_length=100, blank=True)
    training_records = JSONField(default=dict, blank=True)  # Stores training completion dates
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['user__last_name', 'user__first_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.position}"
    
    def save(self, *args, **kwargs):
        # If role is assigned, update user permissions
        super().save(*args, **kwargs)
        
        if self.role and self.user:
            # Clear existing permissions
            self.user.user_permissions.clear()
            
            # Add role permissions to user
            self.user.user_permissions.set(self.role.permissions.all())
            
            # Add to appropriate groups based on role
            if self.role.is_management:
                management_group, created = Group.objects.get_or_create(name='Management')
                self.user.groups.add(management_group)
            else:
                # Remove from management group if not management
                management_group = Group.objects.filter(name='Management').first()
                if management_group and management_group in self.user.groups.all():
                    self.user.groups.remove(management_group)
    
    def save(self, *args, **kwargs):
        # If this is a new staff member, create a user account if not exists
        if not self.user_id:
            # Create a user with a temporary password
            username = f"{self.staff_id.lower()}"
            temp_password = get_random_string(12)
            user = User.objects.create_user(
                username=username,
                email=f"{username}@carehome.com",
                password=temp_password,
                first_name=getattr(self, 'first_name', ''),
                last_name=getattr(self, 'last_name', '')
            )
            self.user = user
            
            # Send welcome email with credentials
            if settings.EMAIL_HOST_USER:
                subject = f"Welcome to CareHome Management System - Your Account Details"
                message = render_to_string('emails/staff_welcome.html', {
                    'staff_member': self,
                    'username': username,
                    'temp_password': temp_password,
                    'login_url': settings.LOGIN_URL
                })
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
        
        super().save(*args, **kwargs)
        
        # Resize photo if it exists
        if self.photo:
            img = Image.open(self.photo.path)
            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                img.save(self.photo.path)

        


class CQCMember(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    cqc_id = models.CharField(max_length=20, unique=True, default=generate_cqc_id)
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone_number = PhoneNumberField(blank=True)
    can_view_incidents = models.BooleanField(default=True)
    incident_view_delay_hours = models.PositiveIntegerField(default=48, help_text="Hours before CQC can view incidents")
    can_view_audit_logs = models.BooleanField(default=False)
    can_view_care_plans = models.BooleanField(default=False)
    can_download_reports = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    last_access = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} (CQC ID: {self.cqc_id})"
    
    def save(self, *args, **kwargs):
        # If this is a new CQC member, create a user account
        if not self.user_id:
            # Create a user with a temporary password
            username = f"cqc_{self.cqc_id.lower()}"
            temp_password = get_random_string(12)
            user = User.objects.create_user(
                username=username,
                email=self.email,
                password=temp_password,
                first_name=self.name.split()[0] if self.name else '',
                last_name=' '.join(self.name.split()[1:]) if self.name else ''
            )
            self.user = user
            
            # Add to CQC group
            cqc_group, created = Group.objects.get_or_create(name='CQC_Members')
            user.groups.add(cqc_group)
            
            # Send welcome email with credentials
            if settings.EMAIL_HOST_USER:
                subject = f"CQC Access to CareHome Management System"
                message = render_to_string('emails/cqc_welcome.html', {
                    'cqc_member': self,
                    'username': username,
                    'temp_password': temp_password,
                    'login_url': settings.LOGIN_URL
                })
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [self.email])
        
        super().save(*args, **kwargs)


class ServiceUser(TimeStampedModel):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('U', 'Prefer not to say'),
    ]
    
    MARITAL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
        ('separated', 'Separated'),
    ]
    
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    marital_status = models.CharField(max_length=10, choices=MARITAL_STATUS_CHOICES, blank=True)
    photo = models.ImageField(upload_to=service_user_photo_path, null=True, blank=True)
    bio = models.TextField(blank=True)
    admission_date = models.DateField()
    room_number = models.CharField(max_length=20)
    bed_number = models.CharField(max_length=10, blank=True)
    
    # Contact information
    email = models.EmailField(blank=True)
    phone_number = PhoneNumberField(blank=True)
    
    # Emergency contact
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_phone = PhoneNumberField()
    emergency_contact_relationship = models.CharField(max_length=100)
    emergency_contact_address = models.TextField(blank=True)
    
    # Next of kin
    next_of_kin_name = models.CharField(max_length=100, blank=True)
    next_of_kin_phone = PhoneNumberField(blank=True)
    next_of_kin_relationship = models.CharField(max_length=100, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    discharge_date = models.DateField(null=True, blank=True)
    discharge_reason = models.TextField(blank=True)
    
    # Medical information
    allergies = models.TextField(blank=True)
    medical_conditions = models.TextField(blank=True)
    special_requirements = models.TextField(blank=True)
    dietary_restrictions = models.TextField(blank=True)
    mobility_requirements = models.CharField(max_length=100, blank=True)
    communication_needs = models.TextField(blank=True)
    
    # Important documents
    has_advanced_directive = models.BooleanField(default=False)
    advanced_directive_details = models.TextField(blank=True)
    has_power_of_attorney = models.BooleanField(default=False)
    power_of_attorney_details = models.TextField(blank=True)
    
    # Financial information (simplified)
    funding_source = models.CharField(max_length=100, blank=True)
    key_worker = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='service_users')
    
    class Meta:
        ordering = ['first_name', 'last_name']
        indexes = [
            models.Index(fields=['first_name', 'last_name']),
            models.Index(fields=['room_number']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    def age(self):
        today = timezone.now().date()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
    
    def save(self, *args, **kwargs):
        # Resize photo if it exists
        super().save(*args, **kwargs)
        if self.photo:
            img = Image.open(self.photo.path)
            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                img.save(self.photo.path)

    def get_active_medications(self):
        """Get all active medications for this service user"""
        return self.medications.filter(is_active=True)
    
    def get_medications_by_time_period(self, time_period):
        """Get medications for a specific time period"""
        medications = self.get_active_medications()
        # Add logic to filter by time period based on frequency
        return medications


class CarePlan(TimeStampedModel):
    service_user = models.OneToOneField(ServiceUser, on_delete=models.CASCADE, related_name='care_plan')
    personal_care = models.TextField(blank=True)
    mobility = models.TextField(blank=True)
    nutrition = models.TextField(blank=True)
    hydration = models.TextField(blank=True)
    social_activities = models.TextField(blank=True)
    medical_requirements = models.TextField(blank=True)
    personal_goals = models.TextField(blank=True)
    spiritual_needs = models.TextField(blank=True)
    cultural_needs = models.TextField(blank=True)
    last_review_date = models.DateField()
    next_review_date = models.DateField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Care Plan for {self.service_user}"
    
    @property
    def is_due_for_review(self):
        return timezone.now().date() >= self.next_review_date


class RiskAssessment(TimeStampedModel):
    service_user = models.ForeignKey(ServiceUser, on_delete=models.CASCADE, related_name='risk_assessments')
    category = models.CharField(max_length=100)  # e.g., Falls, Nutrition, Skin Integrity
    risk_level = models.CharField(max_length=20, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')])
    assessment_details = models.TextField()
    control_measures = models.TextField()
    date_assessed = models.DateField(default=timezone.now)
    review_date = models.DateField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.category} Risk Assessment for {self.service_user}"


class PBSPlan(TimeStampedModel):
    service_user = models.OneToOneField(ServiceUser, on_delete=models.CASCADE, related_name='pbs_plan')
    behaviors_of_concern = models.TextField()
    triggers = models.TextField()
    prevention_strategies = models.TextField()
    deescalation_techniques = models.TextField()
    emergency_procedures = models.TextField()
    last_review_date = models.DateField()
    next_review_date = models.DateField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"PBS Plan for {self.service_user}"


class StaffShift(TimeStampedModel):
    SHIFT_TYPES = [
        ('morning', 'Morning Shift (7am-3pm)'),
        ('evening', 'Evening Shift (3pm-11pm)'),
        ('night', 'Night Shift (11pm-7am)'),
        ('long_day', 'Long Day (7am-11pm)'),
    ]
    
    staff_member = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name='shifts')
    shift_date = models.DateField()
    shift_type = models.CharField(max_length=20, choices=SHIFT_TYPES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    notes = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['shift_date', 'start_time']
        unique_together = ['staff_member', 'shift_date']
    
    def __str__(self):
        return f"{self.staff_member} - {self.shift_date} ({self.shift_type})"


class DailySummary(TimeStampedModel):
    shift = models.OneToOneField(StaffShift, on_delete=models.CASCADE, related_name='daily_summary')
    service_users_present = models.ManyToManyField(ServiceUser, related_name='daily_summaries')
    general_observations = models.TextField()
    issues_concerns = models.TextField(blank=True)
    positive_events = models.TextField(blank=True)
    tasks_completed = models.TextField()
    tasks_pending = models.TextField(blank=True)
    handover_notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Daily Summary - {self.shift.staff_member} - {self.shift.shift_date}"
    

class StaffHandover(TimeStampedModel):
    PRIORITY_CHOICES = [
        ('low', 'Low Priority'),
        ('medium', 'Medium Priority'),
        ('high', 'High Priority'),
    ]
    
    handed_over_by = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name='staff_handovers_given')
    handed_over_to = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name='staff_handovers_received')
    shift_date = models.DateField(default=timezone.now)
    shift_type = models.CharField(max_length=20, choices=StaffShift.SHIFT_TYPES)
    
    # Service user information
    service_users_covered = models.ManyToManyField(ServiceUser, related_name='staff_handovers')
    
    # Handover content
    general_notes = models.TextField(help_text="General observations and notes from the shift")
    tasks_completed = models.TextField(help_text="Tasks completed during the shift")
    tasks_pending = models.TextField(blank=True, help_text="Tasks that need to be followed up")
    urgent_issues = models.TextField(blank=True, help_text="Any urgent issues that need attention")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Medications
    medications_administered = models.TextField(blank=True, help_text="Medications given during the shift")
    medications_due = models.TextField(blank=True, help_text="Medications due in the next shift")
    
    # Incidents
    incidents_occurred = models.TextField(blank=True, help_text="Any incidents that occurred")
    
    # Status
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-shift_date', '-created_at']
    
    def __str__(self):
        return f"Staff Handover: {self.shift_date} ({self.shift_type}) - {self.handed_over_by} to {self.handed_over_to}"


class ManagementDailyNote(TimeStampedModel):
    PRIORITY_CHOICES = [
        ('low', 'Low Priority'),
        ('medium', 'Medium Priority'),
        ('high', 'High Priority'),
        ('urgent', 'Urgent'),
    ]
    
    title = models.CharField(max_length=200)
    note = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    related_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    related_service_user = models.ForeignKey(ServiceUser, on_delete=models.SET_NULL, null=True, blank=True)
    related_staff = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True)
    action_required = models.BooleanField(default=False)
    action_details = models.TextField(blank=True)
    action_deadline = models.DateField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_notes')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Management Note: {self.title} - {self.created_at.date()}"


class ManagementHandover(TimeStampedModel):
    handed_over_by = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name='handovers_given')
    handed_over_to = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name='handovers_received')
    handover_date = models.DateField(default=timezone.now)
    notes = models.TextField()
    urgent_matters = models.TextField(blank=True)
    follow_up_required = models.TextField(blank=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-handover_date', '-created_at']
    
    def __str__(self):
        return f"Handover from {self.handed_over_by} to {self.handed_over_to} on {self.handed_over_date}"


class GovernanceRecord(TimeStampedModel):
    RECORD_TYPES = [
        ('policy', 'Policy Review'),
        ('audit', 'Audit'),
        ('complaint', 'Complaint'),
        ('compliment', 'Compliment'),
        ('incident', 'Incident Review'),
        ('training', 'Training'),
        ('meeting', 'Meeting Minutes'),
        ('other', 'Other'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    title = models.CharField(max_length=200)
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)
    description = models.TextField()
    date_occurred = models.DateField(default=timezone.now)
    date_recorded = models.DateField(default=timezone.now)
    related_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    related_service_user = models.ForeignKey(ServiceUser, on_delete=models.SET_NULL, null=True, blank=True)
    related_staff = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True)
    actions_taken = models.TextField(blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_details = models.TextField(blank=True)
    follow_up_actions = models.TextField(blank=True)
    outcome = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_confidential = models.BooleanField(default=False)
    
    # Keep the ManyToMany relationship with Document
    documents = models.ManyToManyField('Document', blank=True, related_name='governance_records')
    
    class Meta:
        ordering = ['-date_occurred', '-created_at']
    
    def __str__(self):
        return f"{self.get_record_type_display()}: {self.title}"


class Activity(TimeStampedModel):
    ACTIVITY_TYPES = [
        ('personal_care', 'Personal Care'),
        ('meal', 'Meal'),
        ('social', 'Social Activity'),
        ('therapy', 'Therapy'),
        ('medical', 'Medical Appointment'),
        ('outing', 'Outing/Trip'),
        ('exercise', 'Exercise'),
        ('entertainment', 'Entertainment'),
        ('religious', 'Religious Service'),
        ('other', 'Other'),
    ]
    
    MEAL_TYPES = [
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner'),
        ('supper', 'Supper'),
        ('snack', 'Snack'),
    ]
    
    service_user = models.ForeignKey(ServiceUser, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateField(default=timezone.now)
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    staff_involved = models.ManyToManyField(StaffMember, related_name='activities', blank=True)
    
    # For meal activities
    meal_type = models.CharField(max_length=10, choices=MEAL_TYPES, null=True, blank=True)
    food_consumed = models.TextField(blank=True)
    fluid_intake = models.PositiveIntegerField(help_text="In ml", null=True, blank=True)
    appetite_level = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], 
        null=True, blank=True,
        help_text="1 (Poor) to 5 (Excellent)"
    )
    
    # For appointments
    provider = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-date', '-start_time']
        indexes = [
            models.Index(fields=['service_user', 'date']),
            models.Index(fields=['activity_type', 'date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.service_user} - {self.date}"


class ActivityPhoto(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='activity_photos')
    photo = models.ImageField(upload_to=activity_photo_path)
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Photo for {self.activity}"


class Medication(TimeStampedModel):
    MEDICATION_TYPES = [
        ('tablet', 'Tablet'),
        ('capsule', 'Capsule'),
        ('liquid', 'Liquid'),
        ('injection', 'Injection'),
        ('inhaler', 'Inhaler'),
        ('topical', 'Topical'),
        ('patch', 'Transdermal Patch'),
        ('drops', 'Eye/Ear Drops'),
        ('other', 'Other'),
    ]
    
    TIME_PERIODS = [
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('evening', 'Evening'),
        ('night', 'Night'),
        ('prn', 'PRN (As Needed)'),
        ('custom', 'Custom Schedule'),
    ]
    
    FREQUENCY_CHOICES = [
        ('once_daily', 'Once Daily'),
        ('twice_daily', 'Twice Daily'),
        ('three_times_daily', 'Three Times Daily'),
        ('four_times_daily', 'Four Times Daily'),
        ('prn', 'As Needed (PRN)'),
        ('other', 'Other'),
    ]
    
    CONTROLLED_DRUG_CHOICES = [
        (False, 'No'),
        (True, 'Yes - Requires Witness'),
    ]
    
    service_user = models.ForeignKey(ServiceUser, on_delete=models.CASCADE, related_name='medications')
    name = models.CharField(max_length=200)
    medication_type = models.CharField(max_length=20, choices=MEDICATION_TYPES)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='once_daily')
    
    # Time-specific administration details
    administer_morning = models.BooleanField(default=False, verbose_name="Morning Dose")
    morning_time = models.TimeField(default='08:00', null=True, blank=True, verbose_name="Morning Time")
    morning_dosage = models.CharField(max_length=50, blank=True, verbose_name="Morning Dosage")
    
    administer_afternoon = models.BooleanField(default=False, verbose_name="Afternoon Dose")
    afternoon_time = models.TimeField(default='13:00', null=True, blank=True, verbose_name="Afternoon Time")
    afternoon_dosage = models.CharField(max_length=50, blank=True, verbose_name="Afternoon Dosage")
    
    administer_evening = models.BooleanField(default=False, verbose_name="Evening Dose")
    evening_time = models.TimeField(default='18:00', null=True, blank=True, verbose_name="Evening Time")
    evening_dosage = models.CharField(max_length=50, blank=True, verbose_name="Evening Dosage")
    
    administer_night = models.BooleanField(default=False, verbose_name="Night Dose")
    night_time = models.TimeField(default='22:00', null=True, blank=True, verbose_name="Night Time")
    night_dosage = models.CharField(max_length=50, blank=True, verbose_name="Night Dosage")
    
    administer_prn = models.BooleanField(default=False, verbose_name="PRN Dose")
    prn_instructions = models.TextField(blank=True, verbose_name="PRN Instructions")
    prn_max_daily = models.PositiveIntegerField(default=0, verbose_name="Max Daily PRN Doses")
    
    route = models.CharField(max_length=50, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    prescribed_by = models.CharField(max_length=200)
    reason = models.TextField(blank=True)
    is_controlled_drug = models.BooleanField(choices=CONTROLLED_DRUG_CHOICES, default=False)
    total_quantity = models.PositiveIntegerField()
    current_balance = models.PositiveIntegerField()
    instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Additional fields for better tracking
    last_administered = models.DateTimeField(null=True, blank=True)
    next_due_time = models.DateTimeField(null=True, blank=True)
    requires_refrigeration = models.BooleanField(default=False)
    special_handling = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['service_user', 'is_controlled_drug']),
            models.Index(fields=['next_due_time']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.service_user}"
    
    def save(self, *args, **kwargs):
        # If this is a new medication, set current_balance to total_quantity
        if not self.pk:
            self.current_balance = self.total_quantity
        
        # Set default dosages if not specified
        if not self.morning_dosage and self.administer_morning:
            self.morning_dosage = self.dosage
        if not self.afternoon_dosage and self.administer_afternoon:
            self.afternoon_dosage = self.dosage
        if not self.evening_dosage and self.administer_evening:
            self.evening_dosage = self.dosage
        if not self.night_dosage and self.administer_night:
            self.night_dosage = self.dosage
        
        super().save(*args, **kwargs)
    
    def get_time_periods(self):
        """Return list of time periods when this medication should be administered"""
        periods = []
        if self.administer_morning:
            periods.append(('morning', self.morning_time, self.morning_dosage))
        if self.administer_afternoon:
            periods.append(('afternoon', self.afternoon_time, self.afternoon_dosage))
        if self.administer_evening:
            periods.append(('evening', self.evening_time, self.evening_dosage))
        if self.administer_night:
            periods.append(('night', self.night_time, self.night_dosage))
        if self.administer_prn:
            periods.append(('prn', None, self.dosage))
        return periods
    
    def get_next_due_time(self):
        """Calculate when this medication is next due"""
        if not self.is_active:
            return None
        
        now = timezone.now()
        current_time = now.time()
        
        # Check each time period to find the next due time
        time_periods = self.get_time_periods()
        for period, time, _ in time_periods:
            if time and time > current_time:
                return timezone.make_aware(datetime.combine(now.date(), time))
        
        # If no times today, check first time tomorrow
        if time_periods:
            first_period, first_time, _ = time_periods[0]
            if first_time:
                tomorrow = now.date() + timedelta(days=1)
                return timezone.make_aware(datetime.combine(tomorrow, first_time))
        
        return None
    
    def get_medication_type_display(self):
        return dict(self.MEDICATION_TYPES).get(self.medication_type, self.medication_type)
    
    def get_frequency_display(self):
        return dict(self.FREQUENCY_CHOICES).get(self.frequency, self.frequency)
    
    @property
    def is_due(self):
        """Check if medication is due for administration"""
        if not self.is_active:
            return False
        
        next_due = self.get_next_due_time()
        if not next_due:
            return False
        
        return timezone.now() >= next_due
    
    @property
    def status(self):
        """Get medication status"""
        if not self.is_active:
            return 'inactive'
        elif self.current_balance <= 0:
            return 'out_of_stock'
        elif self.is_due:
            return 'due'
        else:
            return 'ok'


class MedicationAdministration(TimeStampedModel):
    STATUS_CHOICES = [
        ('given', 'Given'),
        ('refused', 'Refused'),
        ('omitted', 'Omitted'),
        ('held', 'Held'),
    ]
    
    medication = models.ForeignKey(Medication, on_delete=models.CASCADE, related_name='administrations')
    administered_by = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name='medications_administered')
    administered_date = models.DateField(default=timezone.now)
    administered_time = models.TimeField(default=timezone.now)
    scheduled_time = models.TimeField(null=True, blank=True)
    dose_administered = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='given')
    witness = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name='medications_witnessed')
    notes = models.TextField(blank=True)
    refusal_reason = models.TextField(blank=True)
    administered_date = models.DateField(default=timezone.now)
    administered_time = models.TimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-administered_date', '-administered_time']
        indexes = [
            models.Index(fields=['medication', 'administered_date']),
            models.Index(fields=['administered_by', 'administered_date']),
        ]
    
    def __str__(self):
        return f"{self.medication.name} administered to {self.medication.service_user} on {self.administered_date}"
    
    def save(self, *args, **kwargs):
        # Update medication balance
        if not self.pk and self.status == 'given':  # Only for new administrations that were given
            self.medication.current_balance -= self.dose_administered
            if self.medication.current_balance < 0:
                raise ValidationError("Cannot administer more medication than available.")
            self.medication.save()
        
        # Check if witness is required for controlled drugs
        if self.medication.is_controlled_drug and self.status == 'given' and not self.witness:
            raise ValidationError("A witness is required for controlled drug administration.")
        
        super().save(*args, **kwargs)


class VitalSigns(TimeStampedModel):
    service_user = models.ForeignKey(ServiceUser, on_delete=models.CASCADE, related_name='vital_signs')
    recorded_by = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name='vital_signs_recorded')
    recorded_date = models.DateField(default=timezone.now)
    recorded_time = models.TimeField(default=timezone.now)
    
    # Vital signs
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="°C")
    pulse = models.PositiveIntegerField(null=True, blank=True, help_text="beats per minute")
    respiratory_rate = models.PositiveIntegerField(null=True, blank=True, help_text="breaths per minute")
    blood_pressure_systolic = models.PositiveIntegerField(null=True, blank=True)
    blood_pressure_diastolic = models.PositiveIntegerField(null=True, blank=True)
    oxygen_saturation = models.PositiveIntegerField(
        null=True, blank=True, 
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="SpO2 %"
    )
    blood_glucose = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="mmol/L")
    pain_level = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="0 (No pain) to 10 (Worst pain)"
    )
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-recorded_date', '-recorded_time']
    
    def __str__(self):
        return f"Vital Signs for {self.service_user} on {self.recorded_date}"


class Incident(TimeStampedModel):
    INCIDENT_TYPES = [
        ('fall', 'Fall'),
        ('aggression', 'Aggression'),
        ('wandering', 'Wandering/Elopement'),
        ('medication_error', 'Medication Error'),
        ('injury', 'Injury'),
        ('skin_integrity', 'Skin Integrity Issue'),
        ('choking', 'Choking'),
        ('other', 'Other'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    service_user = models.ForeignKey(ServiceUser, on_delete=models.CASCADE, related_name='incidents')
    incident_type = models.CharField(max_length=50, choices=INCIDENT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateField(default=timezone.now)
    time = models.TimeField(default=timezone.now)
    location = models.CharField(max_length=200)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    staff_involved = models.ManyToManyField(StaffMember, related_name='incidents')
    witnesses = models.TextField(blank=True)
    actions_taken = models.TextField()
    follow_up_required = models.BooleanField(default=False)
    follow_up_notes = models.TextField(blank=True)
    reported_to_family = models.BooleanField(default=False)
    family_notification_details = models.TextField(blank=True)
    
    # ABC Chart data
    antecedent = models.TextField(blank=True, help_text="What happened before the incident?")
    behavior = models.TextField(blank=True, help_text="Describe the behavior in detail")
    consequence = models.TextField(blank=True, help_text="What happened after the incident?")
    
    # CQC access control
    cqc_can_view = models.BooleanField(default=True)
    cqc_viewable_after = models.DateTimeField(
    default=default_cqc_viewable_after,
    help_text="Date/time when CQC can view this incident"
    )
    
    class Meta:
        ordering = ['-date', '-time']
        indexes = [
            models.Index(fields=['service_user', 'date']),
            models.Index(fields=['incident_type', 'date']),
        ]
    
    def __str__(self):
        return f"{self.incident_type} incident - {self.service_user} - {self.date}"
    
    def is_viewable_by_cqc(self):
        """Check if CQC can view this incident based on the delay setting"""
        return self.cqc_can_view and timezone.now() >= self.cqc_viewable_after


class Appointment(TimeStampedModel):
    APPOINTMENT_TYPES = [
        ('medical', 'Medical'),
        ('dental', 'Dental'),
        ('therapy', 'Therapy'),
        ('social', 'Social'),
        ('other', 'Other'),
    ]
    
    service_user = models.ForeignKey(ServiceUser, on_delete=models.CASCADE, related_name='appointments')
    appointment_type = models.CharField(max_length=20, choices=APPOINTMENT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=200)
    provider = models.CharField(max_length=200, blank=True)
    staff_accompanying = models.ManyToManyField(StaffMember, related_name='appointments', blank=True)
    notes = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    transport_arranged = models.BooleanField(default=False)
    transport_details = models.TextField(blank=True)
    
    class Meta:
        ordering = ['date', 'start_time']
        indexes = [
            models.Index(fields=['service_user', 'date']),
            models.Index(fields=['appointment_type', 'date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.service_user} - {self.date}"


class Visitor(TimeStampedModel):
    service_user = models.ForeignKey(ServiceUser, on_delete=models.CASCADE, related_name='visitors')
    visitor_name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=100)
    phone_number = PhoneNumberField(blank=True)
    visit_date = models.DateField(default=timezone.now)
    arrival_time = models.TimeField(default=timezone.now)
    departure_time = models.TimeField(null=True, blank=True)
    purpose = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    covid_screening_passed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-visit_date', '-arrival_time']
        indexes = [
            models.Index(fields=['service_user', 'visit_date']),
        ]
    
    def __str__(self):
        return f"{self.visitor_name} visiting {self.service_user} on {self.visit_date}"
    
    def get_visit_duration(self):
        """Calculate the duration of the visit if departure time is recorded"""
        if self.arrival_time and self.departure_time:
            # Convert times to datetime objects for calculation
            arrival_dt = datetime.combine(self.visit_date, self.arrival_time)
            departure_dt = datetime.combine(self.visit_date, self.departure_time)
            
            # Handle cases where departure is after midnight
            if departure_dt < arrival_dt:
                departure_dt += timedelta(days=1)
                
            duration = departure_dt - arrival_dt
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes = remainder // 60
            
            return {'hours': int(hours), 'minutes': int(minutes)}
        return None


class Trip(TimeStampedModel):
    service_users = models.ManyToManyField(ServiceUser, related_name='trips')
    destination = models.CharField(max_length=200)
    purpose = models.TextField()
    date = models.DateField()
    departure_time = models.TimeField()
    return_time = models.TimeField(null=True, blank=True)
    staff_accompanying = models.ManyToManyField(StaffMember, related_name='trips')
    notes = models.TextField(blank=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    risk_assessment_completed = models.BooleanField(default=False)
    risk_assessment_details = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-date', '-departure_time']
        indexes = [
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"Trip to {self.destination} on {self.date}"


class Document(TimeStampedModel):
    DOCUMENT_TYPES = [
        ('care_plan', 'Care Plan'),
        ('assessment', 'Assessment'),
        ('consent', 'Consent Form'),
        ('policy', 'Policy'),
        ('procedure', 'Procedure'),
        ('report', 'Report'),
        ('contract', 'Contract/Agreement'),
        ('medical', 'Medical Record'),
        ('other', 'Other'),
    ]
    
    title = models.CharField(max_length=200)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to=document_upload_path, validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])
    ])
    service_user = models.ForeignKey(ServiceUser, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    effective_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_confidential = models.BooleanField(default=False)
    cqc_can_view = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def is_expired(self):
        if self.expiry_date:
            return timezone.now().date() > self.expiry_date
        return False


class AuditLog(TimeStampedModel):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('export', 'Export'),
        ('print', 'Print'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    details = JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    cqc_can_view = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name} - {self.created_at}"


class CQCAccessLog(TimeStampedModel):
    cqc_member = models.ForeignKey(CQCMember, on_delete=models.CASCADE, related_name='access_logs')
    accessed_item_type = models.CharField(max_length=100)
    accessed_item_id = models.CharField(max_length=100)
    accessed_item_title = models.CharField(max_length=200)
    access_date = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    
    class Meta:
        ordering = ['-access_date']
    
    def __str__(self):
        return f"{self.cqc_member} accessed {self.accessed_item_type} on {self.access_date}"


class SystemSetting(TimeStampedModel):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.key


class Notification(TimeStampedModel):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    action_url = models.CharField(max_length=200, blank=True)
    related_model = models.CharField(max_length=100, blank=True)
    related_id = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification for {self.recipient}: {self.title}"