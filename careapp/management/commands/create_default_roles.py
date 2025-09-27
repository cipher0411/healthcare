from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from careapp.models import Role

class Command(BaseCommand):
    help = 'Create default roles for the system'
    
    def handle(self, *args, **options):
        # Create Management Role
        management_role, created = Role.objects.get_or_create(
            name="Management",
            defaults={
                'description': 'Full administrative access to all system features',
                'is_management': True,
                'can_manage_staff': True,
                'can_view_reports': True,
                'can_manage_care_plans': True,
                'can_manage_medications': True
            }
        )
        
        if created:
            # Add all permissions to management role
            all_permissions = Permission.objects.all()
            management_role.permissions.set(all_permissions)
            self.stdout.write(
                self.style.SUCCESS('Successfully created Management role')
            )
        else:
            self.stdout.write('Management role already exists')
        
        # Create Care Staff Role
        care_staff_role, created = Role.objects.get_or_create(
            name="Care Staff",
            defaults={
                'description': 'Standard care staff with limited permissions',
                'is_management': False,
                'can_manage_staff': False,
                'can_view_reports': False,
                'can_manage_care_plans': True,
                'can_manage_medications': True
            }
        )
        
        if created:
            # Add basic care permissions
            basic_permissions = Permission.objects.filter(
                codename__in=[
                    'view_serviceuser', 'change_serviceuser', 
                    'view_careplan', 'change_careplan',
                    'view_medication', 'change_medication'
                ]
            )
            care_staff_role.permissions.set(basic_permissions)
            self.stdout.write(
                self.style.SUCCESS('Successfully created Care Staff role')
            )
        else:
            self.stdout.write('Care Staff role already exists')
        
        self.stdout.write(
            self.style.SUCCESS('Default roles setup completed successfully')
        )