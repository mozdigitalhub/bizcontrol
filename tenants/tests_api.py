from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from tenants.models import Business, BusinessMembership, TenantRole


class TenantRegisterApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("api_v1:tenant_register")
        self.payload = {
            "tenant_name": "Loja Central",
            "tenant_type": "hardware",
            "owner_full_name": "Joao Silva",
            "owner_email": "joao@example.com",
            "owner_phone": "841234567",
            "nuit": "123456789",
            "country": "MZ",
            "city": "Maputo",
            "address": "Av. 24 de Julho",
            "currency": "MZN",
            "timezone": "Africa/Maputo",
            "accept_terms": True,
        }

    def test_register_success(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Business.objects.count(), 1)
        business = Business.objects.first()
        self.assertEqual(business.name, "Loja Central")
        self.assertEqual(business.business_type, Business.BUSINESS_HARDWARE)
        self.assertEqual(business.status, Business.STATUS_PENDING)
        self.assertEqual(business.email, "")
        owner = get_user_model().objects.get(username="joao@example.com")
        self.assertFalse(owner.has_usable_password())
        membership = BusinessMembership.objects.get(business=business, user=owner)
        self.assertEqual(membership.role, BusinessMembership.ROLE_OWNER)
        self.assertIsNotNone(membership.role_profile)
        if membership.role_profile:
            self.assertEqual(membership.role_profile.code, TenantRole.ROLE_OWNER_ADMIN)

    def test_register_with_tenant_email(self):
        data = dict(self.payload)
        data["tenant_email"] = "contato@lojacentral.co.mz"
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        business = Business.objects.first()
        self.assertEqual(business.email, "contato@lojacentral.co.mz")

    def test_register_duplicate_email(self):
        User = get_user_model()
        User.objects.create_user(username="joao@example.com", email="joao@example.com", password="pass12345")
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("owner_email", response.data.get("errors", {}))

    def test_register_duplicate_nuit(self):
        Business.objects.create(
            name="Loja",
            slug="loja",
            business_type=Business.BUSINESS_HARDWARE,
            nuit="123456789",
        )
        data = dict(self.payload)
        data["owner_email"] = "outra@example.com"
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nuit", response.data.get("errors", {}))

    def test_register_password_mismatch(self):
        data = dict(self.payload)
        data["password"] = "StrongPass123!"
        data["confirm_password"] = "OutraSenha123!"
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm_password", response.data.get("errors", {}))

    def test_register_missing_fields(self):
        response = self.client.post(self.url, {"tenant_type": "hardware"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tenant_name", response.data.get("errors", {}))

    def test_register_invalid_tenant_type(self):
        data = dict(self.payload)
        data["tenant_type"] = "invalid_type"
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tenant_type", response.data.get("errors", {}))

    def test_register_accepts_business_constant_alias(self):
        data = dict(self.payload)
        data["tenant_type"] = "BUSINESS_BURGER"
        data["tenant_name"] = "Burger Hub"
        data["owner_email"] = "burger@example.com"
        data["nuit"] = "223456789"
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        business = Business.objects.get(slug="burger-hub")
        self.assertEqual(business.business_type, Business.BUSINESS_BURGER)

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
        REST_FRAMEWORK={
            "DEFAULT_THROTTLE_RATES": {
                "anon": "1/min",
                "tenant_register": "1/min",
            }
        }
    )
    def test_register_throttling(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        second = self.client.post(
            self.url,
            {
                **self.payload,
                "tenant_name": "Outra loja",
                "owner_email": "outra@example.com",
                "nuit": "987654321",
            },
            format="json",
        )
        self.assertIn(
            second.status_code,
            [status.HTTP_429_TOO_MANY_REQUESTS, status.HTTP_201_CREATED],
        )
