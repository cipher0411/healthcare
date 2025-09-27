from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied

def is_management(user):
    return user.groups.filter(name='Management').exists() or user.is_superuser

def is_staff(user):
    return user.groups.filter(name='Staff').exists()

def is_cqc(user):
    return user.groups.filter(name='CQC_Members').exists()

class ManagementRequiredMixin(UserPassesTestMixin):
    """Mixin that requires user to be in Management group or admin"""
    
    def test_func(self):
        return is_management(self.request.user)
    
    def handle_no_permission(self):
        if self.raise_exception:
            raise PermissionDenied(self.get_permission_denied_message())
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
        return is_staff(self.request.user) or is_management(self.request.user)
    
    def handle_no_permission(self):
        if self.raise_exception:
            raise PermissionDenied(self.get_permission_denied_message())
        from django.shortcuts import render
        return render(self.request, '403.html', status=403)