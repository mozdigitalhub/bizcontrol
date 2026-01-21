from django.contrib.auth.models import Group
from django.db.models.signals import post_delete, post_migrate, post_save
from django.dispatch import receiver

from accounts.signals import OWNER_GROUP, STAFF_GROUP
from tenants.models import Business, BusinessMembership
from tenants.rbac import ensure_custom_permissions, ensure_tenant_roles


def _sync_user_groups(user):
    owner_group, _ = Group.objects.get_or_create(name=OWNER_GROUP)
    staff_group, _ = Group.objects.get_or_create(name=STAFF_GROUP)

    has_owner = BusinessMembership.objects.filter(
        user=user, role=BusinessMembership.ROLE_OWNER, is_active=True
    ).exists()
    has_staff = BusinessMembership.objects.filter(
        user=user, role=BusinessMembership.ROLE_STAFF, is_active=True
    ).exists()

    if has_owner:
        user.groups.add(owner_group)
    else:
        user.groups.remove(owner_group)

    if has_staff:
        user.groups.add(staff_group)
    else:
        user.groups.remove(staff_group)


@receiver(post_save, sender=BusinessMembership)
def sync_groups_on_save(sender, instance, **kwargs):
    _sync_user_groups(instance.user)


@receiver(post_delete, sender=BusinessMembership)
def sync_groups_on_delete(sender, instance, **kwargs):
    _sync_user_groups(instance.user)


@receiver(post_migrate)
def ensure_role_defaults(sender, **kwargs):
    ensure_custom_permissions()
    for business in Business.objects.all():
        roles = ensure_tenant_roles(business)
        owner_role = next((role for role in roles if role.code == "owner_admin"), None)
        if owner_role:
            BusinessMembership.objects.filter(
                business=business,
                role=BusinessMembership.ROLE_OWNER,
                role_profile__isnull=True,
            ).update(role_profile=owner_role)
