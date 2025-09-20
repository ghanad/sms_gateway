import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from providers.models import AuthType, ProviderType, SmsProvider


class UserToggleActiveViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin", "admin@example.com", "pass")
        self.staff.is_staff = True
        self.staff.save()
        self.user = User.objects.create_user("user", "user@example.com", "pass")
        self.client.force_login(self.staff)

    def test_toggle_user_active(self):
        self.assertTrue(self.user.is_active)
        response = self.client.post(reverse("user_toggle", args=[self.user.pk]))
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)


class UserUpdateViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin", "admin@example.com", "pass")
        self.staff.is_staff = True
        self.staff.save()
        self.user = User.objects.create_user("user", "user@example.com", "pass")
        self.client.force_login(self.staff)

    def test_edit_user_displays_form_with_user_data(self):
        response = self.client.get(reverse("user_update", args=[self.user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "user_management/user_form.html")
        form = response.context["form"]
        self.assertEqual(form.instance, self.user)


class ConfigExportViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin", "admin@example.com", "pass")
        self.staff.is_staff = True
        self.staff.save()
        self.staff.profile.api_key = "staff-key"
        self.staff.profile.daily_quota = 10
        self.staff.profile.save()

        self.user = User.objects.create_user("user", "user@example.com", "pass")
        self.user.profile.api_key = "user-key"
        self.user.profile.daily_quota = 5
        self.user.profile.save()

        self.provider = SmsProvider.objects.create(
            name="Magfa",
            slug="magfa",
            send_url="http://example.com/send",
            balance_url="http://example.com/balance",
            default_sender="100",
            auth_type=AuthType.NONE,
            provider_type=ProviderType.MAGFA,
        )

    def test_staff_can_download_config_file(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("config_export"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/json"))
        self.assertIn("config_cache.json", response["Content-Disposition"])

        payload = json.loads(response.content.decode("utf-8"))
        self.assertIn("users", payload)
        self.assertIn("providers", payload)
        self.assertIn("user-key", payload["users"])
        self.assertEqual(payload["users"]["user-key"]["user_id"], self.user.id)

        provider_data = payload["providers"].get(self.provider.name)
        self.assertIsNotNone(provider_data)
        self.assertTrue(provider_data["is_active"])
        self.assertIn(self.provider.slug, provider_data["aliases"])

    def test_non_staff_user_is_forbidden(self):
        non_staff = User.objects.create_user("viewer", "viewer@example.com", "pass")
        non_staff.profile.api_key = "viewer-key"
        non_staff.profile.save()
        self.client.force_login(non_staff)

        response = self.client.get(reverse("config_export"))
        self.assertEqual(response.status_code, 403)
