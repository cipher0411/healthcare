from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from careapp.models import SecurityLog
from careapp.utils import check_brute_force
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run security checks and report suspicious activities'
    
    def handle(self, *args, **options):
        self.stdout.write("Running security checks...")
        
        # Check for brute force attacks
        self.check_brute_force_attacks()
        
        # Check for inactive users with recent activity
        self.check_inactive_users()
        
        # Check for multiple failed login attempts
        self.check_failed_logins()
        
        self.stdout.write("Security checks completed.")
    
    def check_brute_force_attacks(self):
        """Check for brute force attacks from any IP address"""
        twenty_four_hours_ago = timezone.now() - timezone.timedelta(hours=24)
        
        # Get all unique IP addresses with failed logins in the last 24 hours
        suspicious_ips = SecurityLog.objects.filter(
            action__icontains='login',
            status='Failed',
            timestamp__gte=twenty_four_hours_ago
        ).values('ip_address').distinct()
        
        for ip_info in suspicious_ips:
            ip_address = ip_info['ip_address']
            if check_brute_force(ip_address):
                self.stdout.write(
                    self.style.WARNING(
                        f"Potential brute force attack detected from IP: {ip_address}"
                    )
                )
                
                # Log this as a security event
                SecurityLog.objects.create(
                    ip_address=ip_address,
                    action='Brute Force Attack Detected',
                    status='Suspicious',
                    details={'ip_address': ip_address, 'check': 'automated'}
                )
    
    def check_inactive_users(self):
        """Check for activity from inactive users"""
        twenty_four_hours_ago = timezone.now() - timezone.timedelta(hours=24)
        
        inactive_users = User.objects.filter(is_active=False)
        for user in inactive_users:
            # Check if there's been any activity from this user
            recent_activity = SecurityLog.objects.filter(
                user=user,
                timestamp__gte=twenty_four_hours_ago
            ).exists()
            
            if recent_activity:
                self.stdout.write(
                    self.style.WARNING(
                        f"Inactive user {user.username} has recent activity"
                    )
                )
                
                # Log this as a security event
                SecurityLog.objects.create(
                    user=user,
                    ip_address='127.0.0.1',  # Localhost for system events
                    action='Inactive User Activity',
                    status='Suspicious',
                    details={'username': user.username, 'check': 'automated'}
                )
    
    def check_failed_logins(self):
        """Check for multiple failed login attempts"""
        twenty_four_hours_ago = timezone.now() - timezone.timedelta(hours=24)
        
        # Get all failed login attempts in the last 24 hours
        failed_logins = SecurityLog.objects.filter(
            action__icontains='login',
            status='Failed',
            timestamp__gte=twenty_four_hours_ago
        )
        
        # Group by username and count attempts
        from django.db.models import Count
        username_attempts = failed_logins.exclude(user__isnull=True).values(
            'user__username'
        ).annotate(attempts=Count('id')).filter(attempts__gte=5)
        
        for attempt in username_attempts:
            username = attempt['user__username']
            count = attempt['attempts']
            
            self.stdout.write(
                self.style.WARNING(
                    f"User {username} has {count} failed login attempts in the last 24 hours"
                )
            )
            
            # Log this as a security event
            SecurityLog.objects.create(
                user=User.objects.get(username=username),
                ip_address='127.0.0.1',  # Localhost for system events
                action='Multiple Failed Login Attempts',
                status='Suspicious',
                details={'username': username, 'attempts': count, 'check': 'automated'}
            )