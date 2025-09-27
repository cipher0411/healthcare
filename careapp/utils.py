import requests
import logging
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from .models import SecurityLog, StaffMember
import geoip2.database
import geoip2.errors
from user_agents import parse

logger = logging.getLogger(__name__)

# Initialize GeoIP2 reader
try:
    geoip_reader = geoip2.database.Reader(settings.GEOIP_PATH)
except:
    geoip_reader = None
    logger.warning("GeoIP database not found. Location data will not be available.")


def is_management(user):
    """Check if user is in management group"""
    return user.groups.filter(name='Management').exists()


def is_staff(user):
    """Check if user is in staff group"""
    return user.groups.filter(name='Staff').exists()


def is_cqc(user):
    """Check if user is in CQC group"""
    return user.groups.filter(name='CQC_Members').exists()


def is_staff_or_management(user):
    """Check if user is in staff or management group"""
    return is_staff(user) or is_management(user)


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_location_from_ip(ip_address):
    """Get location information from IP address"""
    if not geoip_reader or ip_address == '127.0.0.1':
        return None
    
    try:
        response = geoip_reader.city(ip_address)
        return {
            'country': response.country.name,
            'city': response.city.name,
            'latitude': response.location.latitude,
            'longitude': response.location.longitude,
        }
    except geoip2.errors.AddressNotFoundError:
        return None
    except Exception as e:
        logger.error(f"Error getting location from IP: {e}")
        return None


def log_security_event(request, action, status, details=None):
    """Log security-related events"""
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Parse user agent
    ua = parse(user_agent)
    browser = f"{ua.browser.family} {ua.browser.version_string}"
    os = f"{ua.os.family} {ua.os.version_string}"
    device = ua.device.family
    
    # Get location from IP
    location = get_location_from_ip(ip_address)
    
    # Prepare details
    event_details = {
        'browser': browser,
        'os': os,
        'device': device,
        'location': location,
    }
    
    if details:
        event_details.update(details)
    
    # Create security log
    SecurityLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        ip_address=ip_address,
        user_agent=user_agent,
        action=action,
        status=status,
        details=event_details
    )


def check_brute_force(ip_address, threshold=5, time_window=300):
    """Check for brute force attacks from an IP address"""
    time_threshold = timezone.now() - timezone.timedelta(seconds=time_window)
    
    failed_attempts = SecurityLog.objects.filter(
        ip_address=ip_address,
        action__icontains='login',
        status='Failed',
        timestamp__gte=time_threshold
    ).count()
    
    return failed_attempts >= threshold


def detect_suspicious_activity(user, request):
    """Detect suspicious user activity"""
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Check if user agent has changed significantly
    last_log = SecurityLog.objects.filter(user=user).order_by('-timestamp').first()
    if last_log and last_log.user_agent != user_agent:
        # This could indicate session hijacking
        log_security_event(
            request, 
            "Suspicious User Agent Change", 
            "Suspicious", 
            {
                "previous_user_agent": last_log.user_agent,
                "current_user_agent": user_agent
            }
        )
        return True
    
    # Check if location has changed significantly
    current_location = get_location_from_ip(ip_address)
    if last_log and last_log.details.get('location') and current_location:
        previous_location = last_log.details.get('location')
        if (previous_location.get('country') != current_location.get('country') and
            previous_location.get('city') != current_location.get('city')):
            # This could indicate account sharing or compromise
            log_security_event(
                request, 
                "Suspicious Location Change", 
                "Suspicious", 
                {
                    "previous_location": previous_location,
                    "current_location": current_location
                }
            )
            return True
    
    return False


def sanitize_input(input_data):
    """Sanitize user input to prevent XSS attacks"""
    if isinstance(input_data, str):
        # Basic XSS prevention
        input_data = input_data.replace('<', '&lt;').replace('>', '&gt;')
        input_data = input_data.replace('(', '&#40;').replace(')', '&#41;')
        input_data = input_data.replace('{', '&#123;').replace('}', '&#125;')
        input_data = input_data.replace('[', '&#91;').replace(']', '&#93;')
    return input_data


def validate_file_upload(file, allowed_types=None, max_size=5242880):
    """Validate file uploads to prevent malicious files"""
    if allowed_types is None:
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']
    
    # Check file size
    if file.size > max_size:
        return False, "File size exceeds maximum allowed size"
    
    # Check file type
    if file.content_type not in allowed_types:
        return False, "File type not allowed"
    
    # Additional checks could be added here (e.g., virus scanning)
    
    return True, "File validated successfully"


from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied

class ManagementRequiredMixin(UserPassesTestMixin):
    """Mixin that requires user to be in Management group"""
    
    def test_func(self):
        return is_management(self.request.user)
    
    def handle_no_permission(self):
        if self.raise_exception:
            raise PermissionDenied(self.get_permission_denied_message())
        # Redirect to permission denied page or show message
        from django.shortcuts import render
        return render(self.request, '403.html', status=403)


class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin that requires user to be in Staff group"""
    
    def test_func(self):
        return is_staff(self.request.user)
    
    def handle_no_permission(self):
        if self.raise_exception:
            raise PermissionDenied(self.get_permission_denied_message())
        from django.shortcuts import render
        return render(self.request, '403.html', status=403)


class CQCRequiredMixin(UserPassesTestMixin):
    """Mixin that requires user to be in CQC group"""
    
    def test_func(self):
        return is_cqc(self.request.user)
    
    def handle_no_permission(self):
        if self.raise_exception:
            raise PermissionDenied(self.get_permission_denied_message())
        from django.shortcuts import render
        return render(self.request, '403.html', status=403)


class StaffOrManagementRequiredMixin(UserPassesTestMixin):
    """Mixin that requires user to be in Staff or Management group"""
    
    def test_func(self):
        return is_staff_or_management(self.request.user)
    
    def handle_no_permission(self):
        if self.raise_exception:
            raise PermissionDenied(self.get_permission_denied_message())
        from django.shortcuts import render
        return render(self.request, '403.html', status=403)


import time
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.cache import cache

class SecurityMiddleware(MiddlewareMixin):
    """Middleware to handle security-related tasks"""
    
    def process_request(self, request):
        # Rate limiting
        ip_address = self.get_client_ip(request)
        self.check_rate_limit(ip_address, request)
        
        return None
    
    def process_response(self, request, response):
        # Log security events for certain responses
        if response.status_code == 403:
            log_security_event(
                request, 
                "Access Forbidden", 
                "Failed", 
                {"path": request.path, "status_code": 403}
            )
        elif response.status_code == 404:
            log_security_event(
                request, 
                "Page Not Found", 
                "Failed", 
                {"path": request.path, "status_code": 404}
            )
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def check_rate_limit(self, ip_address, request):
        """Implement rate limiting for requests"""
        now = time.time()
        window = getattr(settings, 'RATE_LIMIT_WINDOW', 60)  # 60 seconds window
        max_requests = getattr(settings, 'RATE_LIMIT_MAX_REQUESTS', 100)  # 100 requests per window
        
        # Use cache to track requests
        key = f"rate_limit_{ip_address}"
        requests = cache.get(key, [])
        
        # Remove requests outside the current window
        requests = [req_time for req_time in requests if req_time > now - window]
        
        # Check if limit exceeded
        if len(requests) >= max_requests:
            log_security_event(
                request, 
                "Rate Limit Exceeded", 
                "Suspicious", 
                {"ip_address": ip_address, "requests": len(requests)}
            )
            # You could return a 429 response here
        
        # Add current request
        requests.append(now)
        cache.set(key, requests, window)
        
        # Check for brute force attacks
        if request.path == '/login/' and request.method == 'POST':
            if check_brute_force(ip_address):
                log_security_event(
                    request, 
                    "Brute Force Attack Detected", 
                    "Suspicious", 
                    {"ip_address": ip_address}
                )


class XSSProtectionMiddleware(MiddlewareMixin):
    """Middleware to add XSS protection headers"""
    
    def process_response(self, request, response):
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Add CSP header if configured
        if hasattr(settings, 'CSP_HEADER'):
            response['Content-Security-Policy'] = settings.CSP_HEADER
        
        return response


class SQLInjectionProtectionMiddleware(MiddlewareMixin):
    """Middleware to detect potential SQL injection attempts"""
    
    sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'UNION', 'OR', 'AND', 'WHERE', 'FROM']
    
    def process_request(self, request):
        # Check GET parameters
        for param, value in request.GET.items():
            if self.check_sql_injection(value):
                log_security_event(
                    request, 
                    "Potential SQL Injection Attempt (GET)", 
                    "Suspicious", 
                    {"parameter": param, "value": value}
                )
        
        # Check POST parameters
        if request.method == 'POST':
            for param, value in request.POST.items():
                if self.check_sql_injection(value):
                    log_security_event(
                        request, 
                        "Potential SQL Injection Attempt (POST)", 
                        "Suspicious", 
                        {"parameter": param, "value": value}
                    )
        
        return None
    
    def check_sql_injection(self, value):
        """Check if a value contains potential SQL injection patterns"""
        if not isinstance(value, str):
            return False
        
        value_upper = value.upper()
        
        # Check for SQL keywords
        for keyword in self.sql_keywords:
            if keyword in value_upper:
                # Check if it's likely part of a SQL injection attempt
                if any(char in value for char in ['\'', '"', ';', '--', '/*', '*/']):
                    return True
        
        # Check for common SQL injection patterns
        patterns = [
            r'(\'|\"|%27|%22).*(\'|\"|%27|%22)',
            r';.*--',
            r'UNION.*SELECT',
            r'OR.*=.*',
            r'AND.*=.*',
        ]
        
        import re
        for pattern in patterns:
            if re.search(pattern, value_upper, re.IGNORECASE | re.DOTALL):
                return True
        
        return False