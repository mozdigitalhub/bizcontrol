from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from tenants.models import Business, BusinessMembership, TenantEmailLog


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="BizControl <no-reply@bizcontrol.app>",
)
class SuperAdminAccessTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.superuser = get_user_model().objects.create_superuser(
            username="root",
            email="root@example.com",
            password=self.password,
        )
        self.group_superadmin = get_user_model().objects.create_user(
            username="platform.admin",
            email="platform.admin@example.com",
            password=self.password,
        )
        superadmin_group, _ = Group.objects.get_or_create(name="SuperAdmin")
        self.group_superadmin.groups.add(superadmin_group)

        self.tenant_user = get_user_model().objects.create_user(
            username="tenant.owner",
            email="tenant.owner@example.com",
            password=self.password,
        )
        self.business = Business.objects.create(
            name="Ferragem Alpha",
            slug="ferragem-alpha",
            business_type=Business.BUSINESS_HARDWARE,
            status=Business.STATUS_ACTIVE,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.tenant_user,
            role=BusinessMembership.ROLE_OWNER,
            is_active=True,
        )

    def test_superuser_redirects_to_superadmin_after_login(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.superuser.username, "password": self.password},
        )
        self.assertRedirects(response, reverse("superadmin:dashboard"), fetch_redirect_response=False)

    def test_superadmin_group_user_redirects_to_superadmin_after_login(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.group_superadmin.username, "password": self.password},
        )
        self.assertRedirects(response, reverse("superadmin:dashboard"), fetch_redirect_response=False)

    def test_tenant_user_cannot_access_superadmin(self):
        self.client.force_login(self.tenant_user)
        response = self.client.get(reverse("superadmin:dashboard"))
        self.assertRedirects(response, reverse("reports:dashboard"), fetch_redirect_response=False)

    def test_superadmin_can_create_pending_tenant(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("superadmin:tenant_create"),
            {
                "name": "Nova Ferragem",
                "legal_name": "Nova Ferragem Lda",
                "business_type": Business.BUSINESS_HARDWARE,
                "nuit": "123456789",
                "commercial_registration": "REG-123",
                "email": "negocio@example.com",
                "phone": "841111111",
                "country": "Mozambique",
                "city": "Maputo",
                "address": "Av. 1",
                "owner_full_name": "Owner Novo",
                "owner_email": "owner.novo@example.com",
                "owner_phone": "842222222",
                "send_pending_email": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        tenant = Business.objects.get(name="Nova Ferragem")
        self.assertEqual(tenant.status, Business.STATUS_PENDING)
        owner_membership = BusinessMembership.objects.filter(
            business=tenant,
            role=BusinessMembership.ROLE_OWNER,
            is_active=True,
        ).first()
        self.assertIsNotNone(owner_membership)
        self.assertTrue(
            TenantEmailLog.objects.filter(
                business=tenant,
                email_type=TenantEmailLog.TYPE_PENDING,
            ).exists()
        )

    def test_superadmin_create_tenant_without_business_email_keeps_empty(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("superadmin:tenant_create"),
            {
                "name": "Sem Email Lda",
                "legal_name": "",
                "business_type": Business.BUSINESS_HARDWARE,
                "nuit": "987654321",
                "commercial_registration": "",
                "phone": "841111111",
                "country": "Mozambique",
                "city": "Maputo",
                "address": "Av. 25 de Setembro",
                "owner_full_name": "Owner Sem Email",
                "owner_email": "owner.sem.email@example.com",
                "owner_phone": "842222222",
            },
        )
        self.assertEqual(response.status_code, 302)
        tenant = Business.objects.get(name="Sem Email Lda")
        self.assertEqual(tenant.email, "")

    def test_approval_queue_approve_changes_status(self):
        self.client.force_login(self.superuser)
        pending_tenant = Business.objects.create(
            name="Tenant Pendente",
            slug="tenant-pendente",
            business_type=Business.BUSINESS_HARDWARE,
            status=Business.STATUS_PENDING,
            email="tenant.pending@example.com",
        )
        pending_owner = get_user_model().objects.create_user(
            username="pending.owner@example.com",
            email="pending.owner@example.com",
            password=self.password,
        )
        BusinessMembership.objects.create(
            business=pending_tenant,
            user=pending_owner,
            role=BusinessMembership.ROLE_OWNER,
            is_active=True,
        )
        response = self.client.post(
            reverse("superadmin:tenant_status_action", args=[pending_tenant.id]),
            {
                "action": "approve",
                "reason": "Validado",
                "next": reverse("superadmin:tenant_approvals"),
            },
        )
        self.assertRedirects(response, reverse("superadmin:tenant_approvals"), fetch_redirect_response=False)
        pending_tenant.refresh_from_db()
        self.assertEqual(pending_tenant.status, Business.STATUS_ACTIVE)
        self.assertTrue(
            TenantEmailLog.objects.filter(
                business=pending_tenant,
                email_type=TenantEmailLog.TYPE_APPROVED,
                status=TenantEmailLog.STATUS_SENT,
            ).exists()
        )

    def test_resend_pending_email_logs_attempt(self):
        self.client.force_login(self.superuser)
        pending_tenant = Business.objects.create(
            name="Tenant Reenvio",
            slug="tenant-reenvio",
            business_type=Business.BUSINESS_HARDWARE,
            status=Business.STATUS_PENDING,
            email="tenant.reenvio@example.com",
        )
        pending_owner = get_user_model().objects.create_user(
            username="reenvio.owner@example.com",
            email="reenvio.owner@example.com",
            password=self.password,
        )
        BusinessMembership.objects.create(
            business=pending_tenant,
            user=pending_owner,
            role=BusinessMembership.ROLE_OWNER,
            is_active=True,
        )

        response = self.client.post(
            reverse("superadmin:tenant_resend_pending_email", args=[pending_tenant.id]),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            TenantEmailLog.objects.filter(
                business=pending_tenant,
                email_type=TenantEmailLog.TYPE_PENDING,
            ).exists()
        )

    def test_resend_email_for_active_tenant_sends_access_email(self):
        self.client.force_login(self.superuser)
        active_tenant = Business.objects.create(
            name="Tenant Ativo",
            slug="tenant-ativo",
            business_type=Business.BUSINESS_HARDWARE,
            status=Business.STATUS_ACTIVE,
            email="tenant.ativo@example.com",
        )
        active_owner = get_user_model().objects.create_user(
            username="ativo.owner@example.com",
            email="ativo.owner@example.com",
            password=self.password,
        )
        BusinessMembership.objects.create(
            business=active_tenant,
            user=active_owner,
            role=BusinessMembership.ROLE_OWNER,
            is_active=True,
        )

        response = self.client.post(
            reverse("superadmin:tenant_resend_pending_email", args=[active_tenant.id]),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            TenantEmailLog.objects.filter(
                business=active_tenant,
                email_type=TenantEmailLog.TYPE_APPROVED,
                status=TenantEmailLog.STATUS_SENT,
            ).exists()
        )
