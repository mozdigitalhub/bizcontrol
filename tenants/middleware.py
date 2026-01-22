from tenants.models import Business, BusinessMembership


class BusinessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.business = None
        request.tenant = None
        request.membership = None
        request.tenant_permissions = set()
        if request.user.is_authenticated:
            business_id = request.session.get("business_id")
            if business_id:
                business = Business.objects.filter(id=business_id).first()
                if business and (
                    request.user.is_superuser
                    or (
                        business.status == Business.STATUS_ACTIVE
                        and BusinessMembership.objects.filter(
                            business=business, user=request.user, is_active=True
                        ).exists()
                    )
                ):
                    request.business = business
                    request.tenant = business
                    if not request.user.is_superuser:
                        membership = (
                            BusinessMembership.objects.filter(
                                business=business,
                                user=request.user,
                                is_active=True,
                            )
                            .select_related("role_profile")
                            .prefetch_related(
                                "role_profile__permissions",
                                "extra_permissions",
                                "revoked_permissions",
                            )
                            .first()
                        )
                        request.membership = membership
                        if membership:
                            request.tenant_permissions = membership.get_effective_permission_keys()
                    else:
                        request.tenant_permissions = {"*"}
                else:
                    request.session.pop("business_id", None)
        return self.get_response(request)
