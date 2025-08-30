import json
import uuid
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from messaging.models import Message, MessageStatus
from messaging.tasks import process_outbound_sms
from providers.models import AuthType, SmsProvider


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


class ProcessOutboundSmsTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user", password="pass")
        self.provider = SmsProvider.objects.create(
            name="ProviderA",
            slug="provider-a",
            send_url="http://example.com/send",
            balance_url="http://example.com/balance",
            default_sender="100",
            auth_type=AuthType.NONE,
        )
        self.envelope = {
            "tracking_id": str(uuid.uuid4()),
            "user_id": self.user.id,
            "client_key": "key",
            "to": "+123456789",
            "text": "hello",
            "providers_original": ["provider-a"],
            "providers_effective": ["provider-a"],
            "created_at": "2023-10-27T10:00:00.000000",
        }

    @patch("messaging.tasks.get_provider_adapter")
    def test_successful_send_updates_message(self, mock_get_adapter):
        adapter = MagicMock()
        adapter.send_sms.return_value = {"message_id": "abc123"}
        mock_get_adapter.return_value = adapter

        process_outbound_sms.run(self.envelope)

        msg = Message.objects.get()
        self.assertEqual(msg.status, MessageStatus.SENT_TO_PROVIDER)
        self.assertEqual(msg.provider, self.provider)
        self.assertEqual(msg.provider_message_id, "abc123")
        self.assertIsNotNone(msg.sent_at)
        adapter.send_sms.assert_called_once_with(self.envelope["to"], self.envelope["text"])

    @patch("messaging.tasks.get_provider_adapter")
    def test_error_from_provider_sets_failed_status(self, mock_get_adapter):
        adapter = MagicMock()
        adapter.send_sms.return_value = {"error": "oops"}
        mock_get_adapter.return_value = adapter

        process_outbound_sms.run(self.envelope)

        msg = Message.objects.get()
        self.assertEqual(msg.status, MessageStatus.FAILED)
        self.assertEqual(msg.error_message, "oops")

    @patch("messaging.tasks.get_provider_adapter")
    def test_idempotency_check_prevents_duplicate(self, mock_get_adapter):
        Message.objects.create(
            user=self.user,
            tracking_id=uuid.UUID(self.envelope["tracking_id"]),
            recipient="12345",
            text="hello",
        )

        process_outbound_sms.run(self.envelope)

        self.assertEqual(Message.objects.count(), 1)
        mock_get_adapter.assert_not_called()


class ConsumeSmsQueueCommandTests(TestCase):
    @patch("messaging.management.commands.consume_sms_queue.pika.BlockingConnection")
    @patch("messaging.management.commands.consume_sms_queue.process_outbound_sms")
    def test_message_consumed_and_task_dispatched(self, mock_task, mock_conn):
        channel = MagicMock()
        callback_holder = {}

        def basic_consume(queue, on_message_callback):
            callback_holder["cb"] = on_message_callback

        def start_consuming():
            body = json.dumps({"tracking_id": "abc"}).encode()
            method = MagicMock()
            method.delivery_tag = 1
            callback_holder["cb"](channel, method, None, body)
            raise KeyboardInterrupt

        channel.basic_consume.side_effect = basic_consume
        channel.start_consuming.side_effect = start_consuming
        mock_conn.return_value.channel.return_value = channel

        call_command("consume_sms_queue")

        mock_task.delay.assert_called_once_with({"tracking_id": "abc"})
        channel.basic_ack.assert_called_once_with(delivery_tag=1)
        mock_conn.return_value.close.assert_called_once()

    @patch("messaging.management.commands.consume_sms_queue.pika.BlockingConnection")
    @patch("messaging.management.commands.consume_sms_queue.process_outbound_sms")
    def test_invalid_json_is_acked_and_not_dispatched(self, mock_task, mock_conn):
        channel = MagicMock()
        callback_holder = {}

        def basic_consume(queue, on_message_callback):
            callback_holder["cb"] = on_message_callback

        def start_consuming():
            body = b"{not-json}"
            method = MagicMock()
            method.delivery_tag = 2
            callback_holder["cb"](channel, method, None, body)
            raise KeyboardInterrupt

        channel.basic_consume.side_effect = basic_consume
        channel.start_consuming.side_effect = start_consuming
        mock_conn.return_value.channel.return_value = channel

        call_command("consume_sms_queue")

        mock_task.delay.assert_not_called()
        channel.basic_ack.assert_called_once_with(delivery_tag=2)
        mock_conn.return_value.close.assert_called_once()
