from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from superadmin.permissions import is_platform_superadmin


def superadmin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if is_platform_superadmin(request.user):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Sem permissao para area SuperAdmin.")
        if request.user.is_authenticated:
            return redirect("reports:dashboard")
        return redirect(f"{reverse('login')}?next={request.path}")

    return _wrapped
