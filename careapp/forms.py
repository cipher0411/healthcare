from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User, Group, Permission
from django.core.exceptions import ValidationError
from django.utils import timezone
from phonenumber_field.formfields import PhoneNumberField
import re
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, ButtonHolder, Div, HTML
from crispy_forms.bootstrap import AppendedText, PrependedText, FormActions, TabHolder, Tab

from .models import (
    ServiceUser, CarePlan, PBSPlan, StaffMember, Activity, 
    ActivityPhoto, Medication, MedicationAdministration, 
    Incident, Appointment, Visitor, Trip, Department, Role,
    StaffShift, DailySummary, ManagementDailyNote, ManagementHandover,
    GovernanceRecord, VitalSigns, RiskAssessment, CQCMember, Document,
    AuditLog, SystemSetting, Notification, StaffHandover
)


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'User Account Details',
                Row(
                    Column('username', css_class='form-group col-md-6 mb-0'),
                    Column('email', css_class='form-group col-md-6 mb-0'),
                ),
                Row(
                    Column('first_name', css_class='form-group col-md-6 mb-0'),
                    Column('last_name', css_class='form-group col-md-6 mb-0'),
                ),
                Row(
                    Column('password1', css_class='form-group col-md-6 mb-0'),
                    Column('password2', css_class='form-group col-md-6 mb-0'),
                ),
            ),
            ButtonHolder(
                Submit('submit', 'Create Account', css_class='btn-primary')
            )
        )
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("A user with that username already exists.")
        return username
    
    def clean_password(self):
        password = self.cleaned_data.get('password1')
        # Password strength validation
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter.")
        if not re.search(r'[0-9]', password):
            raise ValidationError("Password must contain at least one number.")
        return password


class ServiceUserForm(forms.ModelForm):
    class Meta:
        model = ServiceUser
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by', 'unique_id']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'admission_date': forms.DateInput(attrs={'type': 'date'}),
            'discharge_date': forms.DateInput(attrs={'type': 'date'}),
            'dbs_check_date': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 3}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'medical_conditions': forms.Textarea(attrs={'rows': 2}),
            'special_requirements': forms.Textarea(attrs={'rows': 2}),
            'dietary_restrictions': forms.Textarea(attrs={'rows': 2}),
            'communication_needs': forms.Textarea(attrs={'rows': 2}),
            'emergency_contact_address': forms.Textarea(attrs={'rows': 2}),
            'advanced_directive_details': forms.Textarea(attrs={'rows': 2}),
            'power_of_attorney_details': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            TabHolder(
                Tab('Personal Information',
                    Row(
                        Column('first_name', css_class='form-group col-md-6 mb-0'),
                        Column('last_name', css_class='form-group col-md-6 mb-0'),
                    ),
                    Row(
                        Column('date_of_birth', css_class='form-group col-md-4 mb-0'),
                        Column('gender', css_class='form-group col-md-4 mb-0'),
                        Column('marital_status', css_class='form-group col-md-4 mb-0'),
                    ),
                    'photo',
                    'bio',
                ),
                Tab('Contact Details',
                    Row(
                        Column('email', css_class='form-group col-md-6 mb-0'),
                        Column('phone_number', css_class='form-group col-md-6 mb-0'),
                    ),
                    Row(
                        Column('room_number', css_class='form-group col-md-6 mb-0'),
                        Column('bed_number', css_class='form-group col-md-6 mb-0'),
                    ),
                ),
                Tab('Emergency Contacts',
                    Row(
                        Column('emergency_contact_name', css_class='form-group col-md-6 mb-0'),
                        Column('emergency_contact_relationship', css_class='form-group col-md-6 mb-0'),
                    ),
                    'emergency_contact_phone',
                    'emergency_contact_address',
                    Row(
                        Column('next_of_kin_name', css_class='form-group col-md-6 mb-0'),
                        Column('next_of_kin_relationship', css_class='form-group col-md-6 mb-0'),
                    ),
                    'next_of_kin_phone',
                ),
                Tab('Medical Information',
                    'allergies',
                    'medical_conditions',
                    'special_requirements',
                    'dietary_restrictions',
                    Row(
                        Column('mobility_requirements', css_class='form-group col-md-6 mb-0'),
                        Column('communication_needs', css_class='form-group col-md-6 mb-0'),
                    ),
                ),
                Tab('Admission & Status',
                    Row(
                        Column('admission_date', css_class='form-group col-md-6 mb-0'),
                        Column('discharge_date', css_class='form-group col-md-6 mb-0'),
                    ),
                    'discharge_reason',
                    Row(
                        Column('has_advanced_directive', css_class='form-group col-md-6 mb-0'),
                        Column('has_power_of_attorney', css_class='form-group col-md-6 mb-0'),
                    ),
                    'advanced_directive_details',
                    'power_of_attorney_details',
                    'funding_source',
                    'is_active',
                ),
            ),
            ButtonHolder(
                Submit('submit', 'Save Service User', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class CarePlanForm(forms.ModelForm):
    class Meta:
        model = CarePlan
        exclude = ['service_user', 'created_at', 'updated_at', 'created_by', 'updated_by']
        widgets = {
            'last_review_date': forms.DateInput(attrs={'type': 'date'}),
            'next_review_date': forms.DateInput(attrs={'type': 'date'}),
            'personal_care': forms.Textarea(attrs={'rows': 3}),
            'mobility': forms.Textarea(attrs={'rows': 3}),
            'nutrition': forms.Textarea(attrs={'rows': 3}),
            'hydration': forms.Textarea(attrs={'rows': 3}),
            'social_activities': forms.Textarea(attrs={'rows': 3}),
            'medical_requirements': forms.Textarea(attrs={'rows': 3}),
            'personal_goals': forms.Textarea(attrs={'rows': 3}),
            'spiritual_needs': forms.Textarea(attrs={'rows': 2}),
            'cultural_needs': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('last_review_date', css_class='form-group col-md-6 mb-0'),
                Column('next_review_date', css_class='form-group col-md-6 mb-0'),
            ),
            'personal_care',
            'mobility',
            'nutrition',
            'hydration',
            'social_activities',
            'medical_requirements',
            'personal_goals',
            'spiritual_needs',
            'cultural_needs',
            'is_active',
            ButtonHolder(
                Submit('submit', 'Save Care Plan', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class PBSPlanForm(forms.ModelForm):
    class Meta:
        model = PBSPlan
        exclude = ['service_user', 'created_at', 'updated_at', 'created_by', 'updated_by']
        widgets = {
            'last_review_date': forms.DateInput(attrs={'type': 'date'}),
            'next_review_date': forms.DateInput(attrs={'type': 'date'}),
            'behaviors_of_concern': forms.Textarea(attrs={'rows': 3}),
            'triggers': forms.Textarea(attrs={'rows': 3}),
            'prevention_strategies': forms.Textarea(attrs={'rows': 3}),
            'deescalation_techniques': forms.Textarea(attrs={'rows': 3}),
            'emergency_procedures': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('last_review_date', css_class='form-group col-md-6 mb-0'),
                Column('next_review_date', css_class='form-group col-md-6 mb-0'),
            ),
            'behaviors_of_concern',
            'triggers',
            'prevention_strategies',
            'deescalation_techniques',
            'emergency_procedures',
            'is_active',
            ButtonHolder(
                Submit('submit', 'Save PBS Plan', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class RiskAssessmentForm(forms.ModelForm):
    class Meta:
        model = RiskAssessment
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by']
        widgets = {
            'date_assessed': forms.DateInput(attrs={'type': 'date'}),
            'review_date': forms.DateInput(attrs={'type': 'date'}),
            'assessment_details': forms.Textarea(attrs={'rows': 3}),
            'control_measures': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'service_user',
            'category',
            'risk_level',
            Row(
                Column('date_assessed', css_class='form-group col-md-6 mb-0'),
                Column('review_date', css_class='form-group col-md-6 mb-0'),
            ),
            'assessment_details',
            'control_measures',
            'is_active',
            ButtonHolder(
                Submit('submit', 'Save Risk Assessment', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


# forms.py (updated)
from django import forms
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from .models import StaffMember, CQCMember, Department, Role
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Fieldset, HTML, Div
from crispy_forms.bootstrap import PrependedText, AppendedText
from phonenumber_field.formfields import PhoneNumberField
from .models import generate_staff_id, generate_cqc_id
import re

class StaffMemberForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    username = forms.CharField(
        max_length=150, 
        required=True,
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
    )
    password = forms.CharField(
        widget=forms.PasswordInput, 
        required=False,
        help_text="Leave blank to generate a random password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput, 
        required=False,
        help_text="Enter the same password as above for verification"
    )
    
    class Meta:
        model = StaffMember
        fields = [
            'first_name', 'last_name', 'username', 'email', 'photo', 'phone_number', 
            'department', 'role', 'position', 'qualifications', 'start_date',
            'emergency_contact_name', 'emergency_contact_phone', 
            'emergency_contact_relationship', 'dbs_check_date', 
            'dbs_check_reference', 'is_active'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'dbs_check_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3'
        self.helper.field_class = 'col-md-9'
        self.helper.form_enctype = 'multipart/form-data'
        
        # If editing an existing staff member
        if self.instance and self.instance.pk:
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
            self.initial['first_name'] = self.instance.user.first_name
            self.initial['last_name'] = self.instance.user.last_name
            self.initial['email'] = self.instance.user.email
            self.initial['username'] = self.instance.user.username
            
        self.helper.layout = Layout(
            Fieldset(
                'Personal Information',
                Row(
                    Column('first_name', css_class='col-md-6'),
                    Column('last_name', css_class='col-md-6'),
                ),
                Row(
                    Column('username', css_class='col-md-6'),
                    Column('email', css_class='col-md-6'),
                ),
                Row(
                    Column('phone_number', css_class='col-md-6'),
                    Column('photo', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Employment Details',
                Row(
                    Column('department', css_class='col-md-6'),
                    Column('role', css_class='col-md-6'),
                ),
                'position',
                'qualifications',
                Row(
                    Column('start_date', css_class='col-md-6'),
                    Column('is_active', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Security Information',
                Row(
                    Column('dbs_check_date', css_class='col-md-6'),
                    Column('dbs_check_reference', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Emergency Contact',
                'emergency_contact_name',
                Row(
                    Column('emergency_contact_phone', css_class='col-md-6'),
                    Column('emergency_contact_relationship', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Account Settings',
                Row(
                    Column('password', css_class='col-md-6'),
                    Column('confirm_password', css_class='col-md-6'),
                ),
            ),
            Div(
                Submit('submit', 'Save Staff Member', css_class='btn-primary'),
                css_class='form-group row'
            )
        )
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if self.instance and self.instance.pk:
            # Editing existing staff member
            if User.objects.filter(username=username).exclude(pk=self.instance.user.pk).exists():
                raise ValidationError('A user with this username already exists.')
        else:
            # Creating new staff member
            if User.objects.filter(username=username).exists():
                raise ValidationError('A user with this username already exists.')
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if self.instance and self.instance.pk:
            # Editing existing staff member
            if User.objects.filter(email=email).exclude(pk=self.instance.user.pk).exists():
                raise ValidationError('A user with this email already exists.')
        else:
            # Creating new staff member
            if User.objects.filter(email=email).exists():
                raise ValidationError('A user with this email already exists.')
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        # Only validate passwords if creating new user or changing password
        if not self.instance.pk or password:
            if password and confirm_password and password != confirm_password:
                self.add_error('confirm_password', 'Passwords do not match.')
            
            if password:
                try:
                    validate_password(password)
                except ValidationError as e:
                    self.add_error('password', e)
        
        return cleaned_data
    
    def save(self, commit=True):
        staff_member = super().save(commit=False)
        
        if self.instance and self.instance.pk:
            # Update existing user
            user = staff_member.user
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']
            user.username = self.cleaned_data['username']
            
            # Update password if provided
            password = self.cleaned_data.get('password')
            if password:
                user.set_password(password)
            
            if commit:
                user.save()
                staff_member.save()
        else:
            # Create new user
            password = self.cleaned_data.get('password') or User.objects.make_random_password()
            
            # Generate staff ID
            staff_id = generate_staff_id()
            
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                email=self.cleaned_data['email'],
                password=password,
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name']
            )
            
            # Add user to Staff group
            staff_group, created = Group.objects.get_or_create(name='Staff')
            user.groups.add(staff_group)
            
            staff_member.user = user
            staff_member.staff_id = staff_id
            
            if commit:
                staff_member.save()
        
        return staff_member


class CQCMemberForm(forms.ModelForm):
    name = forms.CharField(max_length=200, required=True)
    email = forms.EmailField(required=True)
    username = forms.CharField(
        max_length=150, 
        required=True,
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
    )
    password = forms.CharField(
        widget=forms.PasswordInput, 
        required=False,
        help_text="Leave blank to generate a random password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput, 
        required=False,
        help_text="Enter the same password as above for verification"
    )
    
    class Meta:
        model = CQCMember
        fields = [
            'name', 'username', 'email', 'phone_number', 'can_view_incidents', 
            'incident_view_delay_hours', 'can_view_audit_logs', 
            'can_view_care_plans', 'can_download_reports', 'is_active'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3'
        self.helper.field_class = 'col-md-9'
        
        # If editing an existing CQC member
        if self.instance and self.instance.pk:
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
            self.initial['name'] = self.instance.user.get_full_name()
            self.initial['email'] = self.instance.user.email
            self.initial['username'] = self.instance.user.username
            
        self.helper.layout = Layout(
            Fieldset(
                'Personal Information',
                'name',
                Row(
                    Column('username', css_class='col-md-6'),
                    Column('email', css_class='col-md-6'),
                ),
                'phone_number',
            ),
            Fieldset(
                'Access Permissions',
                Row(
                    Column('can_view_incidents', css_class='col-md-6'),
                    Column('incident_view_delay_hours', css_class='col-md-6'),
                ),
                Row(
                    Column('can_view_audit_logs', css_class='col-md-6'),
                    Column('can_view_care_plans', css_class='col-md-6'),
                ),
                'can_download_reports',
                'is_active',
            ),
            Fieldset(
                'Account Settings',
                Row(
                    Column('password', css_class='col-md-6'),
                    Column('confirm_password', css_class='col-md-6'),
                ),
            ),
            Div(
                Submit('submit', 'Save CQC Member', css_class='btn-primary'),
                css_class='form-group row'
            )
        )
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if self.instance and self.instance.pk:
            # Editing existing CQC member
            if User.objects.filter(username=username).exclude(pk=self.instance.user.pk).exists():
                raise ValidationError('A user with this username already exists.')
        else:
            # Creating new CQC member
            if User.objects.filter(username=username).exists():
                raise ValidationError('A user with this username already exists.')
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if self.instance and self.instance.pk:
            # Editing existing CQC member
            if User.objects.filter(email=email).exclude(pk=self.instance.user.pk).exists():
                raise ValidationError('A user with this email already exists.')
        else:
            # Creating new CQC member
            if User.objects.filter(email=email).exists():
                raise ValidationError('A user with this email already exists.')
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        # Only validate passwords if creating new user or changing password
        if not self.instance.pk or password:
            if password and confirm_password and password != confirm_password:
                self.add_error('confirm_password', 'Passwords do not match.')
            
            if password:
                try:
                    validate_password(password)
                except ValidationError as e:
                    self.add_error('password', e)
        
        return cleaned_data
    
    def save(self, commit=True):
        cqc_member = super().save(commit=False)
        
        if self.instance and self.instance.pk:
            # Update existing user
            user = cqc_member.user
            # Split name into first and last name
            name_parts = self.cleaned_data['name'].split(' ', 1)
            user.first_name = name_parts[0] if len(name_parts) > 0 else ''
            user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            user.email = self.cleaned_data['email']
            user.username = self.cleaned_data['username']
            
            # Update password if provided
            password = self.cleaned_data.get('password')
            if password:
                user.set_password(password)
            
            if commit:
                user.save()
                cqc_member.save()
        else:
            # Create new user
            password = self.cleaned_data.get('password') or User.objects.make_random_password()
            
            # Generate CQC ID
            cqc_id = generate_cqc_id()
            
            # Split name into first and last name
            name_parts = self.cleaned_data['name'].split(' ', 1)
            first_name = name_parts[0] if len(name_parts) > 0 else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                email=self.cleaned_data['email'],
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Add user to CQC_Members group
            cqc_group, created = Group.objects.get_or_create(name='CQC_Members')
            user.groups.add(cqc_group)
            
            cqc_member.user = user
            cqc_member.cqc_id = cqc_id
            
            if commit:
                cqc_member.save()
        
        return cqc_member


class PasswordChangeForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
        help_text="Enter new password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
        help_text="Confirm new password"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3'
        self.helper.field_class = 'col-md-9'
        
        self.helper.layout = Layout(
            'password',
            'confirm_password',
            Div(
                Submit('submit', 'Change Password', css_class='btn-primary'),
                css_class='form-group row'
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')
        
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                self.add_error('password', e)
        
        return cleaned_data


class StaffShiftForm(forms.ModelForm):
    class Meta:
        model = StaffShift
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by']
        widgets = {
            'shift_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['staff_member'].queryset = StaffMember.objects.filter(is_active=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'staff_member',
            Row(
                Column('shift_date', css_class='form-group col-md-4 mb-0'),
                Column('shift_type', css_class='form-group col-md-4 mb-0'),
                Column('is_completed', css_class='form-group col-md-4 mb-0'),
            ),
            Row(
                Column('start_time', css_class='form-group col-md-6 mb-0'),
                Column('end_time', css_class='form-group col-md-6 mb-0'),
            ),
            'notes',
            ButtonHolder(
                Submit('submit', 'Save Shift', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class DailySummaryForm(forms.ModelForm):
    class Meta:
        model = DailySummary
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by']
        widgets = {
            'general_observations': forms.Textarea(attrs={'rows': 4}),
            'issues_concerns': forms.Textarea(attrs={'rows': 3}),
            'positive_events': forms.Textarea(attrs={'rows': 3}),
            'tasks_completed': forms.Textarea(attrs={'rows': 3}),
            'tasks_pending': forms.Textarea(attrs={'rows': 3}),
            'handover_notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'shift',
            'service_users_present',
            'general_observations',
            'issues_concerns',
            'positive_events',
            'tasks_completed',
            'tasks_pending',
            'handover_notes',
            ButtonHolder(
                Submit('submit', 'Save Daily Summary', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class StaffHandoverForm(forms.ModelForm):
    class Meta:
        model = StaffHandover
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by', 'acknowledged', 'acknowledged_at']
        widgets = {
            'shift_date': forms.DateInput(attrs={'type': 'date'}),
            'general_notes': forms.Textarea(attrs={'rows': 4}),
            'tasks_completed': forms.Textarea(attrs={'rows': 4}),
            'tasks_pending': forms.Textarea(attrs={'rows': 3}),
            'urgent_issues': forms.Textarea(attrs={'rows': 3}),
            'medications_administered': forms.Textarea(attrs={'rows': 3}),
            'medications_due': forms.Textarea(attrs={'rows': 3}),
            'incidents_occurred': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['handed_over_by'].queryset = StaffMember.objects.filter(is_active=True)
        self.fields['handed_over_to'].queryset = StaffMember.objects.filter(is_active=True)
        self.fields['service_users_covered'].queryset = ServiceUser.objects.filter(is_active=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('handed_over_by', css_class='form-group col-md-6 mb-0'),
                Column('handed_over_to', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('shift_date', css_class='form-group col-md-6 mb-0'),
                Column('shift_type', css_class='form-group col-md-6 mb-0'),
            ),
            'service_users_covered',
            'general_notes',
            'tasks_completed',
            'tasks_pending',
            'urgent_issues',
            'priority',
            'medications_administered',
            'medications_due',
            'incidents_occurred',
            ButtonHolder(
                Submit('submit', 'Save Handover', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class ManagementDailyNoteForm(forms.ModelForm):
    class Meta:
        model = ManagementDailyNote
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by', 'resolved_by', 'resolved_at']
        widgets = {
            'note': forms.Textarea(attrs={'rows': 4}),
            'action_details': forms.Textarea(attrs={'rows': 3}),
            'resolution_notes': forms.Textarea(attrs={'rows': 3}),
            'action_deadline': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'title',
            'priority',
            'note',
            Row(
                Column('related_department', css_class='form-group col-md-4 mb-0'),
                Column('related_service_user', css_class='form-group col-md-4 mb-0'),
                Column('related_staff', css_class='form-group col-md-4 mb-0'),
            ),
            Row(
                Column('action_required', css_class='form-group col-md-6 mb-0'),
                Column('is_resolved', css_class='form-group col-md-6 mb-0'),
            ),
            'action_details',
            'action_deadline',
            'resolution_notes',
            ButtonHolder(
                Submit('submit', 'Save Management Note', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class ManagementHandoverForm(forms.ModelForm):
    class Meta:
        model = ManagementHandover
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by', 'acknowledged', 'acknowledged_at']
        widgets = {
            'handover_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
            'urgent_matters': forms.Textarea(attrs={'rows': 3}),
            'follow_up_required': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['handed_over_by'].queryset = StaffMember.objects.filter(is_active=True)
        self.fields['handed_over_to'].queryset = StaffMember.objects.filter(is_active=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('handed_over_by', css_class='form-group col-md-6 mb-0'),
                Column('handed_over_to', css_class='form-group col-md-6 mb-0'),
            ),
            'handover_date',
            'notes',
            'urgent_matters',
            'follow_up_required',
            ButtonHolder(
                Submit('submit', 'Save Handover', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


from django import forms
from django.utils import timezone
from .models import GovernanceRecord  # adjust import as needed

class GovernanceRecordForm(forms.ModelForm):
    class Meta:
        model = GovernanceRecord
        # Exclude metadata and documents, keep priority included
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by', 'documents']
        widgets = {
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'date_occurred': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_recorded': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            # Add other widgets as needed here, for example:
            # 'title': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set initial priority if none exists (only on unbound form)
        if not self.is_bound and not self.initial.get('priority'):
            self.initial['priority'] = 'medium'  # default priority value, change as needed

        # Set initial dates to today if not provided (only on unbound form)
        if not self.is_bound:
            if not self.initial.get('date_occurred'):
                self.fields['date_occurred'].initial = timezone.now().date()
            if not self.initial.get('date_recorded'):
                self.fields['date_recorded'].initial = timezone.now().date()

        # Fields that should not be required
        optional_fields = [
            'related_department',
            'related_service_user',
            'related_staff',
            'actions_taken',
            'follow_up_details',
            'follow_up_actions',
            'outcome',
            'notes',
        ]

        for field_name in optional_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False

        # Add 'form-control' class to all fields if not already present
        for field_name, field in self.fields.items():
            existing_classes = field.widget.attrs.get('class', '')
            if 'form-control' not in existing_classes:
                field.widget.attrs['class'] = (existing_classes + ' form-control').strip()



class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by', 'photos']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'food_consumed': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['staff_involved'].queryset = StaffMember.objects.filter(is_active=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'service_user',
            Row(
                Column('activity_type', css_class='form-group col-md-6 mb-0'),
                Column('title', css_class='form-group col-md-6 mb-0'),
            ),
            'description',
            Row(
                Column('date', css_class='form-group col-md-4 mb-0'),
                Column('start_time', css_class='form-group col-md-4 mb-0'),
                Column('end_time', css_class='form-group col-md-4 mb-0'),
            ),
            'location',
            'staff_involved',
            Row(
                Column('meal_type', css_class='form-group col-md-4 mb-0'),
                Column('fluid_intake', css_class='form-group col-md-4 mb-0'),
                Column('appetite_level', css_class='form-group col-md-4 mb-0'),
            ),
            'food_consumed',
            'provider',
            'notes',
            'is_completed',
            ButtonHolder(
                Submit('submit', 'Save Activity', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class ActivityPhotoForm(forms.ModelForm):
    class Meta:
        model = ActivityPhoto
        fields = ['photo', 'caption']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'photo',
            'caption',
            ButtonHolder(
                Submit('submit', 'Upload Photo', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class MedicationForm(forms.ModelForm):
    class Meta:
        model = Medication
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by', 'current_balance', 
                  'last_administered', 'next_due_time']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'instructions': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'prn_instructions': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'special_handling': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'morning_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'afternoon_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'evening_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'night_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3 col-form-label'
        self.helper.field_class = 'col-md-9'
        
        self.helper.layout = Layout(
            # Basic Information
            HTML("""
                <div class="card mb-4">
                    <div class="card-header bg-primary text-white">
                        <h6 class="mb-0">Basic Information</h6>
                    </div>
                    <div class="card-body">
            """),
            'service_user',
            Row(
                Column('name', css_class='form-group col-md-8 mb-0'),
                Column('medication_type', css_class='form-group col-md-4 mb-0'),
            ),
            Row(
                Column('dosage', css_class='form-group col-md-4 mb-0'),
                Column('frequency', css_class='form-group col-md-4 mb-0'),
                Column('route', css_class='form-group col-md-4 mb-0'),
            ),
            HTML("""
                    </div>
                </div>
            """),
            
            # Administration Schedule
            HTML("""
                <div class="card mb-4">
                    <div class="card-header bg-info text-white">
                        <h6 class="mb-0">Administration Schedule</h6>
                    </div>
                    <div class="card-body">
            """),
            HTML("<h6 class='text-muted mb-3'>Select when this medication should be administered:</h6>"),
            
            # Morning Administration
            HTML("<div class='row mb-3 border-bottom pb-3'>"),
            Column(
                Field('administer_morning', css_class='form-check-input'),
                css_class='form-group col-md-2 mb-0'
            ),
            Column(
                HTML("<label class='form-check-label'>Morning Dose</label>"),
                css_class='form-group col-md-2 mb-0'
            ),
            Column(
                Field('morning_time', css_class='form-control'),
                css_class='form-group col-md-4 mb-0'
            ),
            Column(
                Field('morning_dosage', placeholder='Dosage for morning'),
                css_class='form-group col-md-4 mb-0'
            ),
            HTML("</div>"),
            
            # Afternoon Administration
            HTML("<div class='row mb-3 border-bottom pb-3'>"),
            Column(
                Field('administer_afternoon', css_class='form-check-input'),
                css_class='form-group col-md-2 mb-0'
            ),
            Column(
                HTML("<label class='form-check-label'>Afternoon Dose</label>"),
                css_class='form-group col-md-2 mb-0'
            ),
            Column(
                Field('afternoon_time', css_class='form-control'),
                css_class='form-group col-md-4 mb-0'
            ),
            Column(
                Field('afternoon_dosage', placeholder='Dosage for afternoon'),
                css_class='form-group col-md-4 mb-0'
            ),
            HTML("</div>"),
            
            # Evening Administration
            HTML("<div class='row mb-3 border-bottom pb-3'>"),
            Column(
                Field('administer_evening', css_class='form-check-input'),
                css_class='form-group col-md-2 mb-0'
            ),
            Column(
                HTML("<label class='form-check-label'>Evening Dose</label>"),
                css_class='form-group col-md-2 mb-0'
            ),
            Column(
                Field('evening_time', css_class='form-control'),
                css_class='form-group col-md-4 mb-0'
            ),
            Column(
                Field('evening_dosage', placeholder='Dosage for evening'),
                css_class='form-group col-md-4 mb-0'
            ),
            HTML("</div>"),
            
            # Night Administration
            HTML("<div class='row mb-3 border-bottom pb-3'>"),
            Column(
                Field('administer_night', css_class='form-check-input'),
                css_class='form-group col-md-2 mb-0'
            ),
            Column(
                HTML("<label class='form-check-label'>Night Dose</label>"),
                css_class='form-group col-md-2 mb-0'
            ),
            Column(
                Field('night_time', css_class='form-control'),
                css_class='form-group col-md-4 mb-0'
            ),
            Column(
                Field('night_dosage', placeholder='Dosage for night'),
                css_class='form-group col-md-4 mb-0'
            ),
            HTML("</div>"),
            
            # PRN Administration
            HTML("<div class='row mb-3'>"),
            Column(
                Field('administer_prn', css_class='form-check-input'),
                css_class='form-group col-md-2 mb-0'
            ),
            Column(
                HTML("<label class='form-check-label'>PRN (As Needed)</label>"),
                css_class='form-group col-md-2 mb-0'
            ),
            Column(
                Field('prn_max_daily', placeholder='Max daily doses'),
                css_class='form-group col-md-4 mb-0'
            ),
            HTML("</div>"),
            'prn_instructions',
            HTML("""
                    </div>
                </div>
            """),
            
            # Prescription Details
            HTML("""
                <div class="card mb-4">
                    <div class="card-header bg-warning text-dark">
                        <h6 class="mb-0">Prescription Details</h6>
                    </div>
                    <div class="card-body">
            """),
            Row(
                Column('start_date', css_class='form-group col-md-6 mb-0'),
                Column('end_date', css_class='form-group col-md-6 mb-0'),
            ),
            'prescribed_by',
            'reason',
            HTML("""
                    </div>
                </div>
            """),
            
            # Inventory & Additional Information
            HTML("""
                <div class="card mb-4">
                    <div class="card-header bg-secondary text-white">
                        <h6 class="mb-0">Inventory & Additional Information</h6>
                    </div>
                    <div class="card-body">
            """),
            Row(
                Column('is_controlled_drug', css_class='form-group col-md-6 mb-0'),
                Column('total_quantity', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('requires_refrigeration', css_class='form-group col-md-6 mb-0'),
                Column('is_active', css_class='form-group col-md-6 mb-0'),
            ),
            'special_handling',
            'instructions',
            HTML("""
                    </div>
                </div>
            """),
            
            # Form Actions
            ButtonHolder(
                Submit('submit', 'Save Medication', css_class='btn-primary btn-lg me-2'),
                HTML('<a href="{% url \'medication_list\' %}" class="btn btn-secondary btn-lg">Cancel</a>'),
                css_class='text-center mt-4'
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate that at least one time period is selected
        administer_morning = cleaned_data.get('administer_morning')
        administer_afternoon = cleaned_data.get('administer_afternoon')
        administer_evening = cleaned_data.get('administer_evening')
        administer_night = cleaned_data.get('administer_night')
        administer_prn = cleaned_data.get('administer_prn')
        
        if not any([administer_morning, administer_afternoon, administer_evening, administer_night, administer_prn]):
            raise ValidationError("Please select at least one administration time period.")
        
        # Validate PRN fields if PRN is selected
        if administer_prn:
            prn_max_daily = cleaned_data.get('prn_max_daily')
            if not prn_max_daily or prn_max_daily <= 0:
                self.add_error('prn_max_daily', 'Please specify the maximum number of PRN doses per day.')
        
        return cleaned_data


from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, ButtonHolder, HTML, Div, Field
from crispy_forms.bootstrap import AppendedText, PrependedText
from .models import MedicationAdministration, Medication, StaffMember
from django.contrib.auth import authenticate

class MedicationAdministrationForm(forms.ModelForm):
    witness_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'placeholder': 'Enter witness password'
        }),
        required=False,
        label="Witness Password"
    )
    
    confirm_administration = forms.BooleanField(
        required=True,
        label="I confirm that I have administered this medication correctly"
    )
    
    class Meta:
        model = MedicationAdministration
        fields = ['medication', 'administered_date', 'administered_time', 
                 'dose_administered', 'status', 'notes', 'refusal_reason', 'witness']
        widgets = {
            'administered_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'administered_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Additional notes about this administration...'
            }),
            'refusal_reason': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Reason for refusal...'
            }),
            'medication': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Set initial values for date and time
        self.fields['administered_date'].initial = forms.DateField().to_python(None)
        self.fields['administered_time'].initial = forms.TimeField().to_python(None)
        
        # Filter staff members for witness selection
        self.fields['witness'].queryset = StaffMember.objects.filter(is_active=True)
        
        # Make fields required based on context
        self.fields['witness'].required = False
        self.fields['witness_password'].required = False
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-4 col-form-label'
        self.helper.field_class = 'col-md-8'
        
        self.helper.layout = Layout(
            Field('medication', type="hidden"),
            
            HTML("""
                <div class="card mb-4">
                    <div class="card-header bg-primary text-white">
                        <h6 class="mb-0">Administration Details</h6>
                    </div>
                    <div class="card-body">
            """),
            
            Row(
                Column(
                    PrependedText('administered_date', '<i class="fas fa-calendar"></i>'),
                    css_class='form-group col-md-6 mb-0'
                ),
                Column(
                    PrependedText('administered_time', '<i class="fas fa-clock"></i>'),
                    css_class='form-group col-md-6 mb-0'
                ),
            ),
            
            PrependedText('dose_administered', '<i class="fas fa-pills"></i>'),
            
            Row(
                Column(
                    Field('status', css_class='form-select'),
                    css_class='form-group col-md-6 mb-0'
                ),
                Column(
                    Field('confirm_administration'),
                    css_class='form-group col-md-6 mb-0'
                ),
            ),
            
            Div(
                HTML("""
                    <div id="refusal-reason-section" style="display: none;">
                        <h6 class="text-danger mt-3">Refusal Details</h6>
                """),
                'refusal_reason',
                HTML("</div>"),
                css_id='dynamic-fields'
            ),
            
            HTML("""
                    </div>
                </div>
                
                <div class="card mb-4" id="witness-section">
                    <div class="card-header bg-warning text-dark">
                        <h6 class="mb-0">Witness Verification</h6>
                    </div>
                    <div class="card-body">
            """),
            
            Row(
                Column(
                    Field('witness', css_class='form-select'),
                    css_class='form-group col-md-6 mb-0'
                ),
                Column(
                    PrependedText('witness_password', '<i class="fas fa-lock"></i>'),
                    css_class='form-group col-md-6 mb-0'
                ),
            ),
            
            HTML("""
                    </div>
                </div>
                
                <div class="card mb-4">
                    <div class="card-header bg-info text-white">
                        <h6 class="mb-0">Additional Notes</h6>
                    </div>
                    <div class="card-body">
            """),
            
            'notes',
            
            HTML("""
                    </div>
                </div>
            """),
            
            ButtonHolder(
                Submit('submit', 'Record Administration', 
                      css_class='btn btn-lg btn-success me-2',
                      onclick="return confirm('Are you sure you want to record this medication administration?')"),
                HTML('<a href="{% url \'medication_dashboard\' %}" class="btn btn-lg btn-secondary">Cancel</a>'),
                css_class='text-center mt-4'
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        medication = cleaned_data.get('medication')
        status = cleaned_data.get('status')
        witness = cleaned_data.get('witness')
        witness_password = cleaned_data.get('witness_password')
        confirm_administration = cleaned_data.get('confirm_administration')
        
        if not confirm_administration:
            self.add_error('confirm_administration', 
                          "You must confirm that you have administered the medication correctly.")
        
        # Only validate if we have a medication selected
        if medication:
            # Validate controlled drug requirements
            if medication.is_controlled_drug and status == 'given':
                if not witness:
                    self.add_error('witness', "A witness is required for controlled drug administration.")
                
                # Validate witness password
                if witness and witness_password:
                    user = authenticate(username=witness.user.username, password=witness_password)
                    if not user:
                        self.add_error('witness_password', "Invalid witness password.")
                elif witness:
                    self.add_error('witness_password', "Witness password is required for controlled drugs.")
            
            # Validate dose doesn't exceed available balance
            if status == 'given':
                dose = cleaned_data.get('dose_administered', 0)
                if dose > medication.current_balance:
                    self.add_error('dose_administered', 
                                  f"Cannot administer {dose} units. Only {medication.current_balance} units available.")
        
        return cleaned_data


class VitalSignsForm(forms.ModelForm):
    class Meta:
        model = VitalSigns
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by']
        widgets = {
            'recorded_date': forms.DateInput(attrs={'type': 'date'}),
            'recorded_time': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'service_user',
            'recorded_by',
            Row(
                Column('recorded_date', css_class='form-group col-md-6 mb-0'),
                Column('recorded_time', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('temperature', css_class='form-group col-md-3 mb-0'),
                Column('pulse', css_class='form-group col-md-3 mb-0'),
                Column('respiratory_rate', css_class='form-group col-md-3 mb-0'),
                Column('pain_level', css_class='form-group col-md-3 mb-0'),
            ),
            Row(
                Column('blood_pressure_systolic', css_class='form-group col-md-4 mb-0'),
                Column('blood_pressure_diastolic', css_class='form-group col-md-4 mb-0'),
                Column('oxygen_saturation', css_class='form-group col-md-4 mb-0'),
            ),
            'blood_glucose',
            'notes',
            ButtonHolder(
                Submit('submit', 'Save Vital Signs', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class IncidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'actions_taken': forms.Textarea(attrs={'rows': 4}),
            'follow_up_notes': forms.Textarea(attrs={'rows': 3}),
            'antecedent': forms.Textarea(attrs={'rows': 3}),
            'behavior': forms.Textarea(attrs={'rows': 3}),
            'consequence': forms.Textarea(attrs={'rows': 3}),
            'witnesses': forms.Textarea(attrs={'rows': 2}),
            'family_notification_details': forms.Textarea(attrs={'rows': 3}),
            'cqc_viewable_after': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit staff_involved to active staff only
        self.fields['staff_involved'].queryset = StaffMember.objects.filter(is_active=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            TabHolder(
                Tab('Incident Details',
                    'service_user',
                    Row(
                        Column('incident_type', css_class='form-group col-md-6 mb-0'),
                        Column('title', css_class='form-group col-md-6 mb-0'),
                    ),
                    Row(
                        Column('date', css_class='form-group col-md-6 mb-0'),
                        Column('time', css_class='form-group col-md-6 mb-0'),
                    ),
                    'location',
                    Row(
                        Column('severity', css_class='form-group col-md-6 mb-0'),
                        Column('staff_involved', css_class='form-group col-md-6 mb-0'),
                    ),
                    'description',
                    'witnesses',
                ),
                Tab('Response & Follow-up',
                    'actions_taken',
                    Row(
                        Column('follow_up_required', css_class='form-group col-md-6 mb-0'),
                        Column('reported_to_family', css_class='form-group col-md-6 mb-0'),
                    ),
                    'follow_up_notes',
                    'family_notification_details',
                ),
                Tab('ABC Analysis',
                    'antecedent',
                    'behavior',
                    'consequence',
                ),
                Tab('CQC Settings',
                    Row(
                        Column('cqc_can_view', css_class='form-group col-md-6 mb-0'),
                        Column('cqc_viewable_after', css_class='form-group col-md-6 mb-0'),
                    ),
                ),
            ),
            ButtonHolder(
                Submit('submit', 'Save Incident', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'transport_details': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit staff_accompanying to active staff only
        self.fields['staff_accompanying'].queryset = StaffMember.objects.filter(is_active=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'service_user',
            Row(
                Column('appointment_type', css_class='form-group col-md-6 mb-0'),
                Column('title', css_class='form-group col-md-6 mb-0'),
            ),
            'description',
            Row(
                Column('date', css_class='form-group col-md-4 mb-0'),
                Column('start_time', css_class='form-group col-md-4 mb-0'),
                Column('end_time', css_class='form-group col-md-4 mb-0'),
            ),
            'location',
            'provider',
            'staff_accompanying',
            Row(
                Column('transport_arranged', css_class='form-group col-md-6 mb-0'),
                Column('is_completed', css_class='form-group col-md-6 mb-0'),
            ),
            'transport_details',
            'notes',
            ButtonHolder(
                Submit('submit', 'Save Appointment', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class VisitorForm(forms.ModelForm):
    class Meta:
        model = Visitor
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by']
        widgets = {
            'visit_date': forms.DateInput(attrs={'type': 'date'}),
            'arrival_time': forms.TimeInput(attrs={'type': 'time'}),
            'departure_time': forms.TimeInput(attrs={'type': 'time'}),
            'purpose': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'service_user',
            Row(
                Column('visitor_name', css_class='form-group col-md-6 mb-0'),
                Column('relationship', css_class='form-group col-md-6 mb-0'),
            ),
            'phone_number',
            Row(
                Column('visit_date', css_class='form-group col-md-4 mb-0'),
                Column('arrival_time', css_class='form-group col-md-4 mb-0'),
                Column('departure_time', css_class='form-group col-md-4 mb-0'),
            ),
            'purpose',
            Row(
                Column('covid_screening_passed', css_class='form-group col-md-6 mb-0'),
            ),
            'notes',
            ButtonHolder(
                Submit('submit', 'Save Visitor', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'departure_time': forms.TimeInput(attrs={'type': 'time'}),
            'return_time': forms.TimeInput(attrs={'type': 'time'}),
            'purpose': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'risk_assessment_details': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit service_users to active service users only
        self.fields['service_users'].queryset = ServiceUser.objects.filter(is_active=True)
        # Limit staff_accompanying to active staff only
        self.fields['staff_accompanying'].queryset = StaffMember.objects.filter(is_active=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'destination',
            'purpose',
            Row(
                Column('date', css_class='form-group col-md-4 mb-0'),
                Column('departure_time', css_class='form-group col-md-4 mb-0'),
                Column('return_time', css_class='form-group col-md-4 mb-0'),
            ),
            'service_users',
            'staff_accompanying',
            Row(
                Column('estimated_cost', css_class='form-group col-md-6 mb-0'),
                Column('actual_cost', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('risk_assessment_completed', css_class='form-group col-md-6 mb-0'),
            ),
            'risk_assessment_details',
            'notes',
            ButtonHolder(
                Submit('submit', 'Save Trip', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by']
        widgets = {
            'effective_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'title',
            Row(
                Column('document_type', css_class='form-group col-md-6 mb-0'),
                Column('service_user', css_class='form-group col-md-6 mb-0'),
            ),
            'description',
            'file',
            Row(
                Column('effective_date', css_class='form-group col-md-6 mb-0'),
                Column('expiry_date', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('is_confidential', css_class='form-group col-md-6 mb-0'),
                Column('cqc_can_view', css_class='form-group col-md-6 mb-0'),
            ),
            ButtonHolder(
                Submit('submit', 'Save Document', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = '__all__'
        widgets = {
            'value': forms.Textarea(attrs={'rows': 3}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'key',
            'value',
            'description',
            'is_active',
            ButtonHolder(
                Submit('submit', 'Save Setting', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        exclude = ['created_at', 'updated_at', 'created_by', 'updated_by']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'name',
            'description',
            'manager',
            'is_active',
            ButtonHolder(
                Submit('submit', 'Save Department', css_class='btn-primary'),
                Submit('cancel', 'Cancel', css_class='btn-secondary'),
            )
        )

from django import forms
from django.contrib.auth.models import Permission
from django.urls import reverse_lazy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, ButtonHolder, Button  # ✅ Added Button
from .models import Role

class RoleForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    
    class Meta:
        model = Role
        fields = ['name', 'description', 'permissions', 'is_management', 
                  'can_manage_staff', 'can_view_reports', 'can_manage_care_plans', 
                  'can_manage_medications']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3'
        self.helper.field_class = 'col-md-9'
        
        self.helper.layout = Layout(
            'name',
            'description',
            'permissions',
            Row(
                Column('is_management', css_class='form-group col-md-6 mb-0'),
                Column('can_manage_staff', css_class='form-group col-md-6 mb-0'),
            ),
            Row(
                Column('can_view_reports', css_class='form-group col-md-6 mb-0'),
                Column('can_manage_care_plans', css_class='form-group col-md-6 mb-0'),
            ),
            'can_manage_medications',
            ButtonHolder(
                Submit('submit', 'Save Role', css_class='btn-primary'),
                Button('cancel', 'Cancel', css_class='btn-secondary', 
                       onclick="window.location.href='{}';".format(reverse_lazy('role_list')))
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        is_management = cleaned_data.get('is_management')
        
        if is_management:
            cleaned_data['can_manage_staff'] = True
            cleaned_data['can_view_reports'] = True
            cleaned_data['can_manage_care_plans'] = True
            cleaned_data['can_manage_medications'] = True
            
        return cleaned_data
