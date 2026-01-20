from django.contrib.auth.models import Group
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from accounts.signals import OWNER_GROUP, STAFF_GROUP
from tenants.models import BusinessMembership


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
