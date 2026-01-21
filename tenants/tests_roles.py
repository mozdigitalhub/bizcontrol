from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from tenants.models import Business, BusinessMembership, TenantRole
from tenants.rbac import ensure_custom_permissions


class RolePermissionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staff@example.com", password="pass12345"
        )
        self.owner = get_user_model().objects.create_user(
            username="owner@example.com", password="pass12345"
        )
        self.business = Business.objects.create(name="Loja", slug="loja")
        ensure_custom_permissions()
        self.role = TenantRole.objects.create(
            business=self.business,
            code=TenantRole.ROLE_MANAGER,
            name="Gerente",
        )
        self.membership = BusinessMembership.objects.create(
            business=self.business,
            user=self.user,
            role=BusinessMembership.ROLE_STAFF,
            role_profile=self.role,
        )

    def test_effective_permissions(self):
        perm_view = Permission.objects.filter(
            content_type__app_label="sales", codename="view_sale"
        ).first()
        perm_add = Permission.objects.filter(
            content_type__app_label="sales", codename="add_sale"
        ).first()
        if not perm_view or not perm_add:
            perm_view = Permission.objects.first()
            perm_add = Permission.objects.last()
        self.role.permissions.add(perm_view)
        self.membership.extra_permissions.add(perm_add)
        self.membership.revoked_permissions.add(perm_view)
        keys = self.membership.get_effective_permission_keys()
        self.assertIn(
            f"{perm_add.content_type.app_label}.{perm_add.codename}", keys
        )
        self.assertNotIn(
            f"{perm_view.content_type.app_label}.{perm_view.codename}", keys
        )

    def test_staff_access_requires_permission(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["business_id"] = self.business.id
        session.save()
        response = self.client.get(reverse("tenants:staff_list"))
        self.assertEqual(response.status_code, 302)
        perm_manage = Permission.objects.get(
            content_type__app_label="tenants", codename="manage_staff"
        )
        self.role.permissions.add(perm_manage)
        response = self.client.get(reverse("tenants:staff_list"))
        self.assertEqual(response.status_code, 200)
