# careapp/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q

class EmailOrUsernameModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Try to fetch user by username or email
            user = User.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
            
            # Check password
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            # No user found, return None
            return None
        except User.MultipleObjectsReturned:
            # Multiple users found (shouldn't happen with unique constraints)
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None