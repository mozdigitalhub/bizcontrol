from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    phone = models.CharField(max_length=30, blank=True)
    avatar = models.ImageField(upload_to="user_avatars/", blank=True, null=True)
    must_change_password = models.BooleanField(default=False)
    welcome_seen = models.BooleanField(default=False)
    onboarding_completed = models.BooleanField(default=False)
    temp_password_set_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.get_username()
