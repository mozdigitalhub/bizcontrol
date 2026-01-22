from django.shortcuts import redirect
from django.urls import reverse

from accounts.models import UserProfile


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and not user.is_superuser:
            if not self._is_allowed_path(request.path):
                profile, _ = UserProfile.objects.get_or_create(user=user)
                if profile.must_change_password:
                    return redirect(reverse("tenants:force_password_change"))
        return self.get_response(request)

    def _is_allowed_path(self, path):
        allowed = [
            "/accounts/login/",
            "/accounts/logout/",
            "/tenants/password/force/",
            "/tenants/onboarding/",
            "/admin/",
            "/static/",
            "/media/",
        ]
        return any(path.startswith(prefix) for prefix in allowed)
