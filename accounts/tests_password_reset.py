from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserProfile


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ForgotPasswordFlowTests(TestCase):
    def setUp(self):
        self.old_password = "OldStrongPass123!"
        self.user = get_user_model().objects.create_user(
            username="user.reset",
            email="user.reset@example.com",
            password=self.old_password,
            first_name="Utilizador",
        )

    def test_forgot_password_generates_new_temp_password_and_sends_email(self):
        response = self.client.post(
            reverse("forgot_password"),
            {"identifier": self.user.email},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Se o utilizador existir")

        self.user.refresh_from_db()
        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.must_change_password)
        self.assertIsNotNone(profile.temp_password_set_at)
        self.assertFalse(self.user.check_password(self.old_password))
        self.assertEqual(len(mail.outbox), 1)

    def test_forgot_password_unknown_identifier_keeps_generic_response(self):
        response = self.client.post(
            reverse("forgot_password"),
            {"identifier": "nao.existe@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Se o utilizador existir")
        self.assertEqual(len(mail.outbox), 0)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdminPasswordResetActionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="AdminPass123!",
        )
        self.target_user = User.objects.create_user(
            username="staff.reset",
            email="staff.reset@example.com",
            password="StaffPass123!",
        )

    def test_admin_action_resets_password_and_sends_email(self):
        self.client.force_login(self.admin_user)
        changelist_url = reverse("admin:auth_user_changelist")
        response = self.client.post(
            changelist_url,
            {
                "action": "admin_reset_password_and_email",
                "_selected_action": [str(self.target_user.pk)],
                "index": "0",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nova palavra-passe enviada por email")
        self.assertEqual(len(mail.outbox), 1)
        profile = UserProfile.objects.get(user=self.target_user)
        self.assertTrue(profile.must_change_password)
