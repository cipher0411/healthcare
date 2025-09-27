from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def split(value, arg):
    return value.split(arg)

@register.filter
def morning_count(schedule_dict):
    count = 0
    for user_data in schedule_dict.values():
        count += len(user_data.get('morning', []))
    return count

@register.filter
def afternoon_count(schedule_dict):
    count = 0
    for user_data in schedule_dict.values():
        count += len(user_data.get('afternoon', []))
    return count

@register.filter
def evening_count(schedule_dict):
    count = 0
    for user_data in schedule_dict.values():
        count += len(user_data.get('evening', []))
    return count

@register.filter
def night_count(schedule_dict):
    count = 0
    for user_data in schedule_dict.values():
        count += len(user_data.get('night', []))
    return count

@register.filter
def prn_count(schedule_dict):
    count = 0
    for user_data in schedule_dict.values():
        count += len(user_data.get('prn', []))
    return count



