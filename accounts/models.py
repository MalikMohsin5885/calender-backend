from datetime import timedelta
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils.timezone import now
import requests


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    permissions = models.ManyToManyField('Permission', related_name='roles')

    def __str__(self):
        return self.name


class Permission(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    supervisor = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # :small_blue_diamond: Google Calendar Integration fields
    google_linked = models.BooleanField(default=False)  # has user connected Google Calendar?
    # google_sub = models.CharField(max_length=255, blank=True, null=True)  # Google account unique ID
    google_refresh_token = models.TextField(blank=True, null=True)  # encrypted storage recommended
    google_access_token = models.TextField(blank=True, null=True)  # optional: store last access token
    google_access_token_expiry = models.DateTimeField(blank=True, null=True)  # when access token expires
    google_token_id = models.TextField(blank=True, null=True)
    # timezone = models.CharField(max_length=50, default="Asia/Karachi")  # used for event times
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    objects = UserManager()
    def __str__(self):
        return self.name
    @property
    def get_permissions(self):
        if self.role:
            return set(p.name for p in self.role.permissions.all())
        return set()
    def has_permission(self, perm_name):
        return perm_name in self.get_permissions
    # def mark_google_linked(self, sub, refresh_token, calendar_id="primary"):
    #     """Convenience method for saving Google connection."""
    #     self.google_linked = True
    #     self.google_sub = sub
    #     self.google_refresh_token = refresh_token
    #     self.google_calendar_id = calendar_id
    #     self.save(update_fields=["google_linked", "google_sub", "google_refresh_token", "google_calendar_id"])
    def save_google_tokens(self, access_token, refresh_token, expires_in,token_id):
        self.google_access_token = access_token
        self.google_refresh_token = refresh_token
        self.google_access_token_expiry = now() + timedelta(seconds=expires_in)
        self.google_linked = True
        self.google_token_id = token_id
        self.save()
    # def get_valid_access_token(self):
    #     if self.google_access_token and self.google_access_token_expiry > now():
    #         return self.google_access_token
    #     elif self.google_refresh_token:
    #         # Refresh the token
    #         refreshed_token = self.refresh_google_token()
    #         return refreshed_token
    #     return None
    def refresh_google_token(self):
        try:
            data = {
                'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
                'client_secret': settings.GOOGLE_OAUTH2_CLIENT_SECRET,
                'refresh_token': self.google_refresh_token,
                'grant_type': 'refresh_token'
            }
            response = requests.post('https://oauth2.googleapis.com/token', data=data)
            token_data = response.json()
            if 'access_token' in token_data:
                self.google_access_token = token_data['access_token']
                self.google_access_token_expiry = now() + timedelta(seconds=token_data.get('expires_in', 3600))
                self.save()
                return self.google_access_token
            else:
                # Handle error - maybe disconnect Google
                self.google_linked = False
                self.save()
                return None
        except Exception as e:
            # Handle token refresh error
            print(f"Error refreshing token: {e}")
            return None