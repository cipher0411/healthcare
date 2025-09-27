from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from careapp.models import ServiceUser, Activity, Medication, Incident, Appointment, Visitor, CQCMember

class Command(BaseCommand):
    help = 'Setup initial user groups and permissions'

    def handle(self, *args, **options):
        # Create groups
        management_group, created = Group.objects.get_or_create(name='Management')
        staff_group, created = Group.objects.get_or_create(name='Staff')
        cqc_group, created = Group.objects.get_or_create(name='CQC_Members')
        
        # Get content types for models
        service_user_ct = ContentType.objects.get_for_model(ServiceUser)
        activity_ct = ContentType.objects.get_for_model(Activity)
        medication_ct = ContentType.objects.get_for_model(Medication)
        incident_ct = ContentType.objects.get_for_model(Incident)
        appointment_ct = ContentType.objects.get_for_model(Appointment)
        visitor_ct = ContentType.objects.get_for_model(Visitor)
        
        # Get all permissions for each model
        service_user_perms = Permission.objects.filter(content_type=service_user_ct)
        activity_perms = Permission.objects.filter(content_type=activity_ct)
        medication_perms = Permission.objects.filter(content_type=medication_ct)
        incident_perms = Permission.objects.filter(content_type=incident_ct)
        appointment_perms = Permission.objects.filter(content_type=appointment_ct)
        visitor_perms = Permission.objects.filter(content_type=visitor_ct)
        
        # Assign all permissions to Management group
        for perm in service_user_perms:
            management_group.permissions.add(perm)
        for perm in activity_perms:
            management_group.permissions.add(perm)
        for perm in medication_perms:
            management_group.permissions.add(perm)
        for perm in incident_perms:
            management_group.permissions.add(perm)
        for perm in appointment_perms:
            management_group.permissions.add(perm)
        for perm in visitor_perms:
            management_group.permissions.add(perm)
        
        # Assign limited permissions to Staff group
        staff_permissions = [
            'view_serviceuser', 'view_activity', 'add_activity', 'change_activity',
            'view_medication', 'add_medication', 'change_medication',
            'view_incident', 'add_incident', 'change_incident',
            'view_appointment', 'add_appointment', 'change_appointment',
            'view_visitor', 'add_visitor', 'change_visitor',
            # Document-related permissions
            'view_document', 'download_document'
        ]
        
        for perm_codename in staff_permissions:
            try:
                perm = Permission.objects.get(codename=perm_codename)
                staff_group.permissions.add(perm)
            except Permission.DoesNotExist:
                # If the permission doesn't exist, skip it (might be for a different app)
                self.stdout.write(
                    self.style.WARNING(f'Permission {perm_codename} does not exist, skipping...')
                )
                pass
        
        # Assign CQC permissions (read-only access to most models)
        cqc_permissions = [
            'view_serviceuser', 'view_activity', 'view_medication',
            'view_incident', 'view_appointment', 'view_visitor',
            # Document-related permissions for CQC
            'view_document', 'download_document'
        ]
        
        for perm_codename in cqc_permissions:
            try:
                perm = Permission.objects.get(codename=perm_codename)
                cqc_group.permissions.add(perm)
            except Permission.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f'Permission {perm_codename} does not exist, skipping...')
                )
                pass
        
        # Create admin users
        admin_users = [
            ('admin1', 'admin1@carehome.com', 'admin123', 'System', 'Administrator'),
            ('admin2', 'admin2@carehome.com', 'admin123', 'Backup', 'Administrator')
        ]
        
        for username, email, password, first_name, last_name in admin_users:
            if not User.objects.filter(username=username).exists():
                admin_user = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                admin_user.groups.add(management_group)
                self.stdout.write(
                    self.style.SUCCESS(f'Created admin user: {username} / {password}')
                )
        
        # Create management users
        management_users = [
            ('manager1', 'manager1@carehome.com', 'manager123', 'Care', 'Manager'),
            ('manager2', 'manager2@carehome.com', 'manager123', 'Assistant', 'Manager')
        ]
        
        for username, email, password, first_name, last_name in management_users:
            if not User.objects.filter(username=username).exists():
                manager_user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_staff=True
                )
                manager_user.groups.add(management_group)
                self.stdout.write(
                    self.style.SUCCESS(f'Created manager user: {username} / {password}')
                )
        
        # Create staff users
        staff_users = [
            ('staff1', 'staff1@carehome.com', 'staff123', 'Care', 'Staff'),
            ('staff2', 'staff2@carehome.com', 'staff123', 'Support', 'Staff')
        ]
        
        for username, email, password, first_name, last_name in staff_users:
            if not User.objects.filter(username=username).exists():
                staff_user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                staff_user.groups.add(staff_group)
                self.stdout.write(
                    self.style.SUCCESS(f'Created staff user: {username} / {password}')
                )
        
        # Create CQC users and CQCMember records
        cqc_users = [
            ('cqc1', 'cqc1@cqc.org.uk', 'cqc123', 'CQC', 'Inspector 1'),
            ('cqc2', 'cqc2@cqc.org.uk', 'cqc123', 'CQC', 'Inspector 2')
        ]
        
        for username, email, password, first_name, last_name in cqc_users:
            if not User.objects.filter(username=username).exists():
                cqc_user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                cqc_user.groups.add(cqc_group)
                
                # Create CQCMember record
                cqc_member = CQCMember.objects.create(
                    user=cqc_user,
                    name=f"{first_name} {last_name}",
                    email=email,
                    phone_number="+441234567890",
                    can_view_incidents=True,
                    can_view_audit_logs=True,
                    can_view_care_plans=True,
                    can_download_reports=True
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f'Created CQC user: {username} / {password}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Successfully setup groups and users!')
        )

# python manage.py setup_groups