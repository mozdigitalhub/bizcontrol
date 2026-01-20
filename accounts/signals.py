from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver

OWNER_GROUP = "group_owner"
STAFF_GROUP = "group_staff"


@receiver(post_migrate)
def create_default_groups(sender, **kwargs):
    owner_group, _ = Group.objects.get_or_create(name=OWNER_GROUP)
    staff_group, _ = Group.objects.get_or_create(name=STAFF_GROUP)

    owner_group.permissions.set(Permission.objects.all())

    staff_full_apps = ["sales", "customers", "receivables", "billing"]
    staff_view_apps = ["catalog", "inventory", "finance"]

    staff_perms = Permission.objects.filter(
        content_type__app_label__in=staff_full_apps
    ).exclude(codename__startswith="delete_")
    staff_perms = staff_perms | Permission.objects.filter(
        content_type__app_label__in=staff_view_apps, codename__startswith="view_"
    )
    staff_group.permissions.set(staff_perms)
