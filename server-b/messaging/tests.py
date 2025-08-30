from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from messaging.models import Message, MessageStatus
from providers.models import SmsProvider, AuthType
import uuid


class MessageModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user", password="pass")
        self.provider = SmsProvider.objects.create(
            name="Provider",
            slug="provider",
            send_url="http://example.com/send",
            balance_url="http://example.com/balance",
            default_sender="100",
            auth_type=AuthType.NONE,
        )

    def test_str_includes_provider_and_status(self):
        msg = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello",
            provider=self.provider,
        )
        self.assertEqual(str(msg), f"To: {msg.recipient} via {self.provider.name} [{msg.status}]")

    def test_default_status_and_no_provider(self):
        msg = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello",
        )
        self.assertEqual(msg.status, MessageStatus.PENDING)
        self.assertEqual(str(msg), f"To: {msg.recipient} via N/A [{msg.status}]")


class UserMessageListViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user", password="pass")
        self.provider = SmsProvider.objects.create(
            name="Provider",
            slug="provider",
            send_url="http://example.com/send",
            balance_url="http://example.com/balance",
            default_sender="100",
            auth_type=AuthType.NONE,
        )
        self.msg1 = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello1",
            provider=self.provider,
        )
        self.msg2 = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="67890",
            text="hello2",
            provider=self.provider,
        )

    def test_search_by_tracking_id_filters_messages(self):
        self.client.login(username="user", password="pass")
        url = reverse("messaging:my_messages_list")
        response = self.client.get(url, {"tracking_id": str(self.msg1.tracking_id)})
        self.assertContains(response, self.msg1.recipient)
        self.assertNotContains(response, self.msg2.recipient)
        self.assertEqual(response.context["tracking_id"], str(self.msg1.tracking_id))

    def test_invalid_tracking_id_returns_no_messages(self):
        self.client.login(username="user", password="pass")
        url = reverse("messaging:my_messages_list")
        response = self.client.get(url, {"tracking_id": "not-a-uuid"})
        self.assertEqual(list(response.context["messages"]), [])
