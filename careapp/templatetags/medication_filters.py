from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()

@register.filter
def medication_status(medication):
    """Determine the status badge color for a medication"""
    if not medication.is_active:
        return "secondary"
    
    balance_percentage = (medication.current_balance / medication.total_quantity) * 100
    if balance_percentage <= 10:
        return "danger"
    elif balance_percentage <= 25:
        return "warning"
    else:
        return "success"

@register.filter
def medication_balance(medication):
    """Calculate the percentage balance of medication"""
    if medication.total_quantity == 0:
        return 0
    return (medication.current_balance / medication.total_quantity) * 100

@register.filter
def next_due_date(medication):
    """Calculate the next due date for medication based on frequency"""
    if not medication.is_active or medication.current_balance <= 0:
        return None
    
    # Get the last administration for this medication
    last_admin = medication.administrations.filter(status='given').order_by('-administered_date', '-administered_time').first()
    
    if not last_admin:
        return "ASAP"
    
    last_date = last_admin.administered_date
    frequency = medication.frequency.lower()
    
    # Calculate next due date based on frequency
    if 'daily' in frequency or 'once daily' in frequency:
        next_due = last_date + timedelta(days=1)
    elif 'twice daily' in frequency or 'bid' in frequency:
        next_due = last_date  # Same day, next dose
    elif 'three times daily' in frequency or 'tid' in frequency:
        next_due = last_date  # Same day, next dose
    elif 'four times daily' in frequency or 'qid' in frequency:
        next_due = last_date  # Same day, next dose
    elif 'weekly' in frequency:
        next_due = last_date + timedelta(weeks=1)
    elif 'monthly' in frequency:
        next_due = last_date + timedelta(days=30)
    else:
        # Default to daily if frequency not recognized
        next_due = last_date + timedelta(days=1)
    
    return next_due

@register.filter
def is_due_soon(medication):
    """Check if medication is due soon (within 2 days)"""
    next_due = next_due_date(medication)
    if not next_due or next_due == "ASAP":
        return True
    
    if isinstance(next_due, str):
        return False
    
    today = timezone.now().date()
    return (next_due - today).days <= 2





@register.filter
def filter_low_stock(medications):
    """Filter medications with low stock (<= 25%)"""
    return [med for med in medications if medication.is_active and (med.current_balance / med.total_quantity) * 100 <= 25]

@register.filter
def filter_due_soon(medications):
    """Filter medications that are due soon"""
    return [med for med in medications if med.is_active and is_due_soon(med)]