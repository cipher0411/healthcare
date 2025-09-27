from django import template
from django.utils import timezone
from django.contrib.humanize.templatetags.humanize import naturaltime

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get a value from a dictionary by key"""
    return dictionary.get(key)

@register.filter
def format_phone(phone_number):
    """Format a phone number for display"""
    if not phone_number:
        return ""
    
    # Simple formatting for UK numbers
    phone_str = str(phone_number)
    if phone_str.startswith('+44'):
        return f"{phone_str[0:3]} {phone_str[3:7]} {phone_str[7:]}"
    return phone_str

@register.filter
def age(birth_date):
    """Calculate age from birth date"""
    today = timezone.now().date()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

@register.filter
def time_since(value):
    """Return human-readable time since the given value"""
    return naturaltime(value)

@register.simple_tag
def current_time(format_string):
    """Return the current time formatted as specified"""
    return timezone.now().strftime(format_string)

@register.filter
def medication_balance(medication):
    """Calculate medication balance percentage"""
    if medication.total_quantity == 0:
        return 0
    return (medication.current_balance / medication.total_quantity) * 100

@register.filter
def medication_status(medication):
    """Return status class for medication based on balance"""
    balance_percent = medication_balance(medication)
    if balance_percent > 50:
        return "success"
    elif balance_percent > 25:
        return "warning"
    else:
        return "danger"