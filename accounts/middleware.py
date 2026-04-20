from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile


class SessionInactivityMiddleware:
    SESSION_KEY = "_last_activity_ts"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        timeout = int(getattr(settings, "SESSION_INACTIVITY_TIMEOUT", 0) or 0)
        user = getattr(request, "user", None)

        if (
            timeout <= 0
            or not user
            or not user.is_authenticated
            or self._is_allowed_path(request.path)
        ):
            return self.get_response(request)

        now_ts = int(timezone.now().timestamp())
        last_activity_ts = request.session.get(self.SESSION_KEY)
        if last_activity_ts is not None:
            try:
                inactive_seconds = now_ts - int(last_activity_ts)
            except (TypeError, ValueError):
                inactive_seconds = 0
            if inactive_seconds >= timeout:
                logout(request)
                login_url = reverse("login")
                if request.headers.get("HX-Request") == "true":
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = login_url
                    return response
                if request.path.startswith("/api/"):
                    return JsonResponse(
                        {"detail": "Sessao terminada por inatividade."},
                        status=401,
                    )
                timeout_minutes = max(timeout // 60, 1)
                if hasattr(request, "_messages"):
                    messages.warning(
                        request,
                        f"Sessao terminada apos {timeout_minutes} minutos de inatividade.",
                    )
                return redirect(login_url)

        request.session[self.SESSION_KEY] = now_ts
        return self.get_response(request)

    def _is_allowed_path(self, path):
        allowed_prefixes = [
            "/accounts/login/",
            "/accounts/logout/",
            "/accounts/forgot-password/",
            "/tenants/password/force/",
            "/tenants/onboarding/",
            "/static/",
            "/media/",
        ]
        return any(path.startswith(prefix) for prefix in allowed_prefixes)


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
            "/accounts/forgot-password/",
            "/tenants/password/force/",
            "/tenants/onboarding/",
            "/admin/",
            "/static/",
            "/media/",
        ]
        return any(path.startswith(prefix) for prefix in allowed)
