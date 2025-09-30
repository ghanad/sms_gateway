import json
import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from messaging.models import Message, MessageStatus
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


class UserCreateViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin", "admin@example.com", "pass")
        self.staff.is_staff = True
        self.staff.save()
        self.client.force_login(self.staff)

    def test_staff_can_create_user_with_description(self):
        response = self.client.post(
            reverse("user_create"),
            {
                "username": "new_user",
                "password1": "complex-pass-123",
                "password2": "complex-pass-123",
                "api_key": "new-api-key",
                "daily_quota": "15",
                "description": "User created for integration tests.",
            },
        )

        self.assertEqual(response.status_code, 302)
        created_user = User.objects.get(username="new_user")
        self.assertEqual(
            created_user.profile.description,
            "User created for integration tests.",
        )


class UserUpdateViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin", "admin@example.com", "pass")
        self.staff.is_staff = True
        self.staff.save()
        self.user = User.objects.create_user("user", "user@example.com", "pass")
        self.user.profile.api_key = "existing-key"
        self.user.profile.daily_quota = 20
        self.user.profile.description = "Existing description"
        self.user.profile.save()
        self.client.force_login(self.staff)

    def test_edit_user_displays_form_with_user_data(self):
        response = self.client.get(reverse("user_update", args=[self.user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "user_management/user_form.html")
        form = response.context["form"]
        self.assertEqual(form.instance, self.user)

    def test_staff_can_update_user_description(self):
        response = self.client.post(
            reverse("user_update", args=[self.user.pk]),
            {
                "username": self.user.username,
                "email": self.user.email,
                "first_name": "",
                "last_name": "",
                "api_key": "existing-key",
                "daily_quota": "25",
                "description": "Updated internal note.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.description, "Updated internal note.")


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


class UserStatsViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin", "admin@example.com", "pass")
        self.staff.is_staff = True
        self.staff.save()
        self.client.force_login(self.staff)

        self.alice = User.objects.create_user("alice", "alice@example.com", "pass")
        self.bob = User.objects.create_user("bob", "bob@example.com", "pass")

        now = timezone.now()

        messages = [
            Message(
                user=self.alice,
                tracking_id=uuid.uuid4(),
                recipient="+1234567890",
                text="Test",
                status=MessageStatus.SENT_TO_PROVIDER,
            ),
            Message(
                user=self.alice,
                tracking_id=uuid.uuid4(),
                recipient="+1234567891",
                text="Test",
                status=MessageStatus.DELIVERED,
            ),
            Message(
                user=self.alice,
                tracking_id=uuid.uuid4(),
                recipient="+1234567892",
                text="Test",
                status=MessageStatus.FAILED,
            ),
            Message(
                user=self.bob,
                tracking_id=uuid.uuid4(),
                recipient="+1234567893",
                text="Test",
                status=MessageStatus.FAILED,
            ),
        ]

        Message.objects.bulk_create(messages)

        # Adjust timestamps for deterministic filtering checks
        Message.objects.filter(user=self.alice).update(created_at=now)
        Message.objects.filter(user=self.bob).update(created_at=now - timedelta(days=10))

    def test_staff_can_view_aggregated_user_stats(self):
        response = self.client.get(reverse("user_stats"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "user_management/user_stats.html")

        stats = {user.username: user for user in response.context["user_stats"]}

        alice_stats = stats["alice"]
        self.assertEqual(alice_stats.total_messages, 3)
        self.assertEqual(alice_stats.successful_messages, 2)
        self.assertEqual(alice_stats.failed_messages, 1)
        self.assertIsNotNone(alice_stats.last_sent)

        bob_stats = stats["bob"]
        self.assertEqual(bob_stats.total_messages, 1)
        self.assertEqual(bob_stats.successful_messages, 0)
        self.assertEqual(bob_stats.failed_messages, 1)
        self.assertIsNotNone(bob_stats.last_sent)

        # Staff user has not sent messages, but should still appear.
        admin_stats = stats["admin"]
        self.assertEqual(admin_stats.total_messages, 0)
        self.assertIsNone(admin_stats.last_sent)

    def test_date_filters_limit_results(self):
        target_date = (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        response = self.client.get(
            reverse("user_stats"),
            {"from": target_date, "to": target_date},
        )

        self.assertEqual(response.status_code, 200)
        stats = {user.username: user for user in response.context["user_stats"]}

        # Alice's messages are outside the filter window; they should not be counted.
        alice_stats = stats["alice"]
        self.assertEqual(alice_stats.total_messages, 0)
        self.assertIsNone(alice_stats.last_sent)

        # Bob has one message with a timestamp 10 days ago; still outside the window.
        bob_stats = stats["bob"]
        self.assertEqual(bob_stats.total_messages, 0)

        # Ensure filter values are echoed back in the context.
        self.assertEqual(response.context["filters"], {"from": target_date, "to": target_date})
