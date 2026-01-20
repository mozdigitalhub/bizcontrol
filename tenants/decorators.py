from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from tenants.models import BusinessMembership


def _is_owner(request):
    if request.user.is_superuser:
        return True
    if not getattr(request, "business", None):
        return False
    return BusinessMembership.objects.filter(
        business=request.business,
        user=request.user,
        role=BusinessMembership.ROLE_OWNER,
        is_active=True,
    ).exists()


def business_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not getattr(request, "business", None):
            url = reverse("tenants:select_business")
            return redirect(f"{url}?next={request.path}")
        return view_func(request, *args, **kwargs)

    return _wrapped


def owner_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not getattr(request, "business", None):
            url = reverse("tenants:select_business")
            return redirect(f"{url}?next={request.path}")
        is_owner = _is_owner(request)
        if is_owner:
            return view_func(request, *args, **kwargs)
        if not is_owner:
            messages.error(request, "Sem permissao para esta area.")
            return redirect("reports:dashboard")
        return view_func(request, *args, **kwargs)

    return _wrapped


def feature_required(feature_key, message="Funcionalidade indisponivel."):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not getattr(request, "business", None):
                url = reverse("tenants:select_business")
                return redirect(f"{url}?next={request.path}")
            if _is_owner(request):
                return view_func(request, *args, **kwargs)
            if not request.business.feature_enabled(feature_key):
                messages.error(request, message)
                return redirect("reports:dashboard")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def module_required(module_key, message="Modulo desativado."):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not getattr(request, "business", None):
                url = reverse("tenants:select_business")
                return redirect(f"{url}?next={request.path}")
            if _is_owner(request):
                return view_func(request, *args, **kwargs)
            if not request.business.get_module_flags().get(module_key, False):
                messages.error(request, message)
                return redirect("reports:dashboard")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
