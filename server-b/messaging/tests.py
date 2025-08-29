from django.test import TestCase
from django.contrib.auth.models import User
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
