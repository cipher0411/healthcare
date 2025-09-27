# In careapp/context_processors.py
from .utils import is_management, is_staff, is_cqc

def user_roles(request):
    return {
        'is_management': is_management(request.user) if request.user.is_authenticated else False,
        'is_staff': is_staff(request.user) if request.user.is_authenticated else False,
        'is_cqc': is_cqc(request.user) if request.user.is_authenticated else False,
    }