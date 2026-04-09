from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from tenants.models import Business, BusinessMembership

class TenantLoginFlowTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.user = get_user_model().objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password=self.password,
            first_name="Owner",
        )

    def _create_business(self, status):
        business = Business.objects.create(
            name=f"Negocio {status}",
            slug=f"negocio-{status}",
            business_type=Business.BUSINESS_HARDWARE,
            status=status,
        )
        BusinessMembership.objects.create(
            business=business,
            user=self.user,
            role=BusinessMembership.ROLE_OWNER,
        )
        return business

    def test_pending_tenant_cannot_login(self):
        self._create_business(Business.STATUS_PENDING)
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": self.password},
            follow=True,
        )
        self.assertContains(response, "pendente de aprovacao")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_active_tenant_can_login(self):
        business = self._create_business(Business.STATUS_ACTIVE)
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": self.password},
            follow=True,
        )
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.session.get("business_id"), business.id)
        self.assertEqual(response.status_code, 200)

    def test_select_business_auto_redirects_when_single_active_business(self):
        business = self._create_business(Business.STATUS_ACTIVE)
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.get(reverse("tenants:select_business"))
        self.assertRedirects(response, reverse("reports:dashboard"), fetch_redirect_response=False)
        self.assertEqual(self.client.session.get("business_id"), business.id)

    def test_force_password_change_on_first_login(self):
        self._create_business(Business.STATUS_ACTIVE)
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.must_change_password = True
        profile.save(update_fields=["must_change_password"])
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": self.password},
            follow=True,
        )
        force_url = reverse("tenants:force_password_change")
        self.assertTrue(
            any(force_url in redirect[0] for redirect in response.redirect_chain),
            response.redirect_chain,
        )

    def test_onboarding_completion_flag(self):
        self._create_business(Business.STATUS_ACTIVE)
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.post(reverse("tenants:onboarding_complete"))
        self.assertEqual(response.status_code, 302)
        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.onboarding_completed)
