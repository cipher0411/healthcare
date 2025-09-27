import time
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.cache import cache
from .utils import log_security_event, check_brute_force, detect_suspicious_activity


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