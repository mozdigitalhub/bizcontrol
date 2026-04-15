from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView

from accounts.forms import TenantLoginForm
from accounts.forms import ForgotPasswordForm
from accounts.services import reset_password_and_send_email
from superadmin.permissions import is_platform_superadmin
from tenants.utils import get_default_business_for_user


class BizControlLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = TenantLoginForm

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user
        if not is_platform_superadmin(user):
            business = get_default_business_for_user(user)
            if business:
                self.request.session["business_id"] = business.id
        return response

    def get_default_redirect_url(self):
        if is_platform_superadmin(self.request.user):
            return reverse("superadmin:dashboard")
        return reverse("reports:dashboard")


class ForgotPasswordView(FormView):
    template_name = "registration/forgot_password.html"
    form_class = ForgotPasswordForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("reports:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        identifier = (form.cleaned_data.get("identifier") or "").strip()
        User = get_user_model()
        user = (
            User.objects.filter(
                Q(email__iexact=identifier) | Q(username__iexact=identifier),
                is_active=True,
            )
            .order_by("id")
            .first()
        )
        if user and user.email:
            reset_password_and_send_email(user=user, request=self.request)
        messages.success(
            self.request,
            "Se o utilizador existir, enviamos uma nova palavra-passe para o email associado.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("login")
