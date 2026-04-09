from django.conf import settings
from django.db.models import Case, IntegerField, Value, When

from tenants.models import Business, BusinessMembership


def tenant_requires_business_selection():
    return bool(getattr(settings, "TENANT_REQUIRE_BUSINESS_SELECTION", False))


def get_default_business_membership(user):
    if not user or not user.is_authenticated or user.is_superuser:
        return None

    memberships = BusinessMembership.objects.filter(
        user=user,
        is_active=True,
        business__status=Business.STATUS_ACTIVE,
    ).select_related("business")

    if tenant_requires_business_selection():
        if memberships.count() != 1:
            return None
        return memberships.order_by("business__name", "id").first()

    return (
        memberships.annotate(
            owner_priority=Case(
                When(role=BusinessMembership.ROLE_OWNER, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("owner_priority", "business__name", "id")
        .first()
    )


def get_default_business_for_user(user):
    membership = get_default_business_membership(user)
    return membership.business if membership else None
