from tenants.models import Business, BusinessMembership
from tenants.utils import get_default_business_membership


def _is_food_operation_business(business):
    if not business:
        return False
    return bool(
        business.feature_enabled(Business.FEATURE_USE_KITCHEN_DISPLAY)
        and business.feature_enabled(Business.FEATURE_USE_RECIPES)
    )


class BusinessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.business = None
        request.tenant = None
        request.membership = None
        request.tenant_permissions = set()
        if request.user.is_authenticated:
            membership = None
            business = None
            business_id = request.session.get("business_id")
            if business_id:
                business = Business.objects.filter(id=business_id).first()
                if not business:
                    request.session.pop("business_id", None)
                elif request.user.is_superuser:
                    pass
                else:
                    membership = (
                        BusinessMembership.objects.filter(
                            business=business,
                            user=request.user,
                            is_active=True,
                            business__status=Business.STATUS_ACTIVE,
                        )
                        .select_related("role_profile")
                        .prefetch_related(
                            "role_profile__permissions",
                            "extra_permissions",
                            "revoked_permissions",
                        )
                        .first()
                    )
                    if not membership:
                        business = None
                        request.session.pop("business_id", None)

            if not business and not request.user.is_superuser:
                membership = get_default_business_membership(request.user)
                if membership:
                    business = membership.business
                    request.session["business_id"] = business.id
                    membership = (
                        BusinessMembership.objects.filter(
                            id=membership.id,
                        )
                        .select_related("role_profile")
                        .prefetch_related(
                            "role_profile__permissions",
                            "extra_permissions",
                            "revoked_permissions",
                        )
                        .first()
                    )

            if business:
                request.business = business
                request.tenant = business
                if request.user.is_superuser:
                    request.tenant_permissions = {"*"}
                else:
                    request.membership = membership
                    if membership:
                        request.tenant_permissions = membership.get_effective_permission_keys()

        if _is_food_operation_business(request.business):
            path = request.path or "/"
            if path == "/":
                return self.get_response(request)
            allowed_prefixes = (
                "/food/",
                "/reports/",
                "/tenants/",
                "/accounts/",
                "/logout",
                "/login",
                "/static/",
                "/media/",
                "/api/",
            )
            if not path.startswith(allowed_prefixes):
                from django.shortcuts import redirect
                return redirect("food:order_list")
        return self.get_response(request)
