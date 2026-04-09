from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from tenants.models import Business, BusinessMembership


class TenantProfileTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="pass12345",
            first_name="Owner",
        )
        self.business = Business.objects.create(
            name="Loja A",
            slug="loja-a",
            business_type=Business.BUSINESS_HARDWARE,
            nuit="111111111",
        )
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["business_id"] = self.business.id
        session.save()

    def test_duplicate_nuit_on_edit(self):
        Business.objects.create(
            name="Loja B",
            slug="loja-b",
            business_type=Business.BUSINESS_HARDWARE,
            nuit="222222222",
        )
        response = self.client.post(
            reverse("tenants:business_profile"),
            {
                "name": "Loja A",
                "nuit": "222222222",
                "commercial_registration": "",
                "phone": "",
                "email": "",
                "address": "",
                "country": "",
                "city": "",
            },
        )
        form = response.context["form"]
        self.assertTrue(form.errors.get("nuit"))

    def test_update_user_profile_without_email_change(self):
        UserProfile.objects.get_or_create(user=self.user)
        response = self.client.post(
            reverse("tenants:user_profile"),
            {
                "action": "profile",
                "first_name": "Novo",
                "last_name": "Nome",
                "phone": "841234567",
                "email": "owner@example.com",
                "username": "owner@example.com",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "owner@example.com")
        self.assertEqual(self.user.first_name, "Novo")

    def test_change_password_validation(self):
        response = self.client.post(
            reverse("tenants:user_profile"),
            {
                "action": "password",
                "old_password": "wrong",
                "new_password1": "NovaSenha123!",
                "new_password2": "NovaSenha123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password atual")

    def test_business_profile_hides_owner_email_in_company_email_field(self):
        self.business.email = "owner@example.com"
        self.business.save(update_fields=["email"])
        response = self.client.get(reverse("tenants:business_profile"))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial.get("email"), "")
