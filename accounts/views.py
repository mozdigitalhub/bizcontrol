from django.contrib.auth.views import LoginView
from django.urls import reverse

from accounts.forms import TenantLoginForm
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
