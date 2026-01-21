from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


def user_has_tenant_permission(request, perm_key):
    if not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    membership = getattr(request, "membership", None)
    if not membership:
        return False
    return membership.has_permission(perm_key)


def tenant_permission_required(perm_key, message="Sem permissao para esta area."):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not getattr(request, "business", None):
                url = reverse("tenants:select_business")
                return redirect(f"{url}?next={request.path}")
            if user_has_tenant_permission(request, perm_key):
                return view_func(request, *args, **kwargs)
            messages.error(request, message)
            return redirect("reports:dashboard")

        return _wrapped

    return decorator
