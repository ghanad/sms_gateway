import json
import uuid
import os
import django
from unittest.mock import MagicMock, patch, call

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sms_gateway_project.settings")
django.setup()

from celery.exceptions import Retry
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from messaging.models import Message, MessageStatus, MessageAttemptLog, AttemptStatus
from messaging.tasks import (
    process_outbound_sms,
    dispatch_pending_messages,
    send_sms_with_failover,
)
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
        self.assertEqual(list(response.context["message_list"]), [])

    def test_awaiting_retry_shows_error_message(self):
        self.client.login(username="user", password="pass")
        self.msg1.status = MessageStatus.AWAITING_RETRY
        self.msg1.error_message = "temporary failure"
        self.msg1.save(update_fields=["status", "error_message"])
        url = reverse("messaging:my_messages_list")
        response = self.client.get(url)
        self.assertContains(response, "Awaiting Retry")
        self.assertContains(response, "temporary failure")

    def test_message_links_to_detail_view(self):
        self.client.login(username="user", password="pass")
        url = reverse("messaging:my_messages_list")
        response = self.client.get(url)
        detail_url = reverse("messaging:message_detail", args=[self.msg1.tracking_id])
        self.assertContains(response, detail_url)


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
        adapter.send_sms.return_value = {
            "status": "success",
            "message_id": "abc123",
            "raw_response": {},
        }
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
        adapter.send_sms.return_value = {
            "status": "failure",
            "type": "permanent",
            "reason": "oops",
            "raw_response": {},
        }
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
    def setUp(self):
        self.user = User.objects.create_user("user", password="pass")

    @patch("messaging.management.commands.consume_sms_queue.pika.BlockingConnection")
    def test_message_persisted_and_acked(self, mock_conn):
        channel = MagicMock()
        callback_holder = {}

        def basic_consume(queue, on_message_callback, auto_ack=False):
            callback_holder["cb"] = on_message_callback

        def start_consuming():
            envelope = {
                "tracking_id": str(uuid.uuid4()),
                "user_id": self.user.id,
                "to": "+123",
                "text": "hello",
            }
            body = json.dumps(envelope).encode()
            method = MagicMock()
            method.delivery_tag = 1
            callback_holder["cb"](channel, method, None, body)
            raise KeyboardInterrupt

        channel.basic_consume.side_effect = basic_consume
        channel.start_consuming.side_effect = start_consuming
        mock_conn.return_value.channel.return_value = channel

        call_command("consume_sms_queue")

        self.assertEqual(Message.objects.count(), 1)
        channel.basic_ack.assert_called_once_with(delivery_tag=1)
        channel.basic_nack.assert_not_called()
        mock_conn.return_value.close.assert_called_once()

    @patch("messaging.management.commands.consume_sms_queue.pika.BlockingConnection")
    def test_duplicate_message_is_acked(self, mock_conn):
        tracking = uuid.uuid4()
        Message.objects.create(
            user=self.user,
            tracking_id=tracking,
            recipient="123",
            text="hello",
            initial_envelope={},
        )

        channel = MagicMock()
        callback_holder = {}

        def basic_consume(queue, on_message_callback, auto_ack=False):
            callback_holder["cb"] = on_message_callback

        def start_consuming():
            body = json.dumps(
                {
                    "tracking_id": str(tracking),
                    "user_id": self.user.id,
                    "to": "+123",
                    "text": "hello",
                }
            ).encode()
            method = MagicMock()
            method.delivery_tag = 1
            callback_holder["cb"](channel, method, None, body)
            raise KeyboardInterrupt

        channel.basic_consume.side_effect = basic_consume
        channel.start_consuming.side_effect = start_consuming
        mock_conn.return_value.channel.return_value = channel

        call_command("consume_sms_queue")

        self.assertEqual(Message.objects.count(), 1)
        channel.basic_ack.assert_called_once_with(delivery_tag=1)
        channel.basic_nack.assert_not_called()

    @patch("messaging.management.commands.consume_sms_queue.pika.BlockingConnection")
    @patch("messaging.management.commands.consume_sms_queue.User.objects.get")
    def test_db_error_nacks_and_requeues(self, mock_user_get, mock_conn):
        mock_user_get.side_effect = Exception("db down")
        channel = MagicMock()
        callback_holder = {}

        def basic_consume(queue, on_message_callback, auto_ack=False):
            callback_holder["cb"] = on_message_callback

        def start_consuming():
            envelope = {
                "tracking_id": str(uuid.uuid4()),
                "user_id": self.user.id,
                "to": "+123",
                "text": "hello",
            }
            body = json.dumps(envelope).encode()
            method = MagicMock()
            method.delivery_tag = 1
            callback_holder["cb"](channel, method, None, body)
            raise KeyboardInterrupt

        channel.basic_consume.side_effect = basic_consume
        channel.start_consuming.side_effect = start_consuming
        mock_conn.return_value.channel.return_value = channel

        call_command("consume_sms_queue")

        self.assertEqual(Message.objects.count(), 0)
        channel.basic_nack.assert_called_once_with(delivery_tag=1, requeue=True)
        channel.basic_ack.assert_not_called()


class DispatchPendingMessagesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user", password="pass")
        self.msg1 = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="111",
            text="hi1",
        )
        self.msg2 = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="222",
            text="hi2",
        )

    @patch("messaging.tasks.send_sms_with_failover.delay")
    def test_dispatch_claims_and_enqueues(self, mock_delay):
        dispatch_pending_messages.run(batch_size=10)

        self.msg1.refresh_from_db()
        self.msg2.refresh_from_db()
        self.assertEqual(self.msg1.status, MessageStatus.PROCESSING)
        self.assertEqual(self.msg2.status, MessageStatus.PROCESSING)
        mock_delay.assert_has_calls(
            [call(self.msg1.id), call(self.msg2.id)], any_order=True
        )


class SendSmsWithFailoverTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user", password="pass")
        self.provider1 = SmsProvider.objects.create(
            name="Provider1",
            slug="p1",
            send_url="http://example.com/send1",
            balance_url="http://example.com/bal1",
            default_sender="100",
            auth_type=AuthType.NONE,
            priority=100,
        )
        self.provider2 = SmsProvider.objects.create(
            name="Provider2",
            slug="p2",
            send_url="http://example.com/send2",
            balance_url="http://example.com/bal2",
            default_sender="200",
            auth_type=AuthType.NONE,
            priority=50,
        )
        self.message = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello",
            initial_envelope={},
        )

    @patch("messaging.tasks.get_provider_adapter")
    def test_failover_to_second_provider(self, mock_get_adapter):
        adapter1 = MagicMock()
        adapter1.send_sms.return_value = {
            "status": "failure",
            "type": "transient",
            "reason": "oops",
            "raw_response": {},
        }
        adapter2 = MagicMock()
        adapter2.send_sms.return_value = {
            "status": "success",
            "message_id": "xyz",
            "raw_response": {},
        }
        mock_get_adapter.side_effect = [adapter1, adapter2]

        send_sms_with_failover.run(self.message.id)

        self.message.refresh_from_db()
        self.assertEqual(self.message.status, MessageStatus.SENT_TO_PROVIDER)
        self.assertEqual(self.message.provider, self.provider2)
        self.assertEqual(self.message.provider_message_id, "xyz")
        adapter1.send_sms.assert_called_once()
        adapter2.send_sms.assert_called_once()

        logs = MessageAttemptLog.objects.filter(message=self.message).order_by('timestamp')
        self.assertEqual(logs.count(), 2)
        self.assertEqual(logs[0].provider, self.provider1)
        self.assertEqual(logs[0].status, AttemptStatus.FAILURE)
        self.assertEqual(logs[1].provider, self.provider2)
        self.assertEqual(logs[1].status, AttemptStatus.SUCCESS)

    @patch("messaging.tasks.publish_to_dlq")
    @patch("messaging.tasks.get_provider_adapter")
    def test_retry_on_transient_failure(self, mock_get_adapter, mock_publish):
        adapter1 = MagicMock()
        adapter1.send_sms.return_value = {
            "status": "failure",
            "type": "transient",
            "reason": "temp",
            "raw_response": {},
        }
        adapter2 = MagicMock()
        adapter2.send_sms.return_value = {
            "status": "failure",
            "type": "transient",
            "reason": "temp2",
            "raw_response": {},
        }
        mock_get_adapter.side_effect = [adapter1, adapter2]

        original_retries = send_sms_with_failover.request.retries
        send_sms_with_failover.request.retries = 0
        try:
            with patch.object(
                send_sms_with_failover, "retry", side_effect=Retry(), autospec=True
            ) as mock_retry:
                with self.assertRaises(Retry):
                    send_sms_with_failover.run(self.message.id)
        finally:
            send_sms_with_failover.request.retries = original_retries

        self.message.refresh_from_db()
        self.assertEqual(self.message.status, MessageStatus.AWAITING_RETRY)
        self.assertEqual(self.message.error_message, "temp2")
        mock_retry.assert_called_once()
        self.assertEqual(mock_retry.call_args.kwargs["countdown"], 60)
        mock_publish.assert_not_called()

    @patch("messaging.tasks.publish_to_dlq")
    @patch("messaging.tasks.get_provider_adapter")
    def test_permanent_failure_sends_to_dlq(self, mock_get_adapter, mock_publish):
        adapter1 = MagicMock()
        adapter1.send_sms.return_value = {
            "status": "failure",
            "type": "permanent",
            "reason": "fail1",
            "raw_response": {},
        }
        adapter2 = MagicMock()
        adapter2.send_sms.return_value = {
            "status": "failure",
            "type": "permanent",
            "reason": "fail2",
            "raw_response": {},
        }
        mock_get_adapter.side_effect = [adapter1, adapter2]

        original_retries = send_sms_with_failover.request.retries
        send_sms_with_failover.request.retries = 5
        try:
            send_sms_with_failover.run(self.message.id)
        finally:
            send_sms_with_failover.request.retries = original_retries

        self.message.refresh_from_db()
        self.assertEqual(self.message.status, MessageStatus.FAILED)
        self.assertEqual(self.message.error_message, "fail1")
        adapter2.send_sms.assert_not_called()
        mock_publish.assert_called_once_with(self.message)

    @patch("messaging.tasks.publish_to_dlq")
    @patch("messaging.tasks.get_provider_adapter")
    def test_respects_user_specified_provider_order(self, mock_get_adapter, mock_publish):
        self.message.initial_envelope = {"providers_effective": ["p2", "p1"]}
        self.message.save(update_fields=["initial_envelope"])

        call_order: list[str] = []

        adapter_p2 = MagicMock()
        adapter_p2.send_sms.return_value = {
            "status": "failure",
            "type": "permanent",
            "reason": "p2",
            "raw_response": {},
        }
        adapter_p1 = MagicMock()
        adapter_p1.send_sms.return_value = {
            "status": "failure",
            "type": "permanent",
            "reason": "p1",
            "raw_response": {},
        }

        def side_effect(provider):
            call_order.append(provider.slug)
            if provider.slug == "p2":
                return adapter_p2
            if provider.slug == "p1":
                return adapter_p1
            raise AssertionError("unexpected provider")

        mock_get_adapter.side_effect = side_effect

        send_sms_with_failover.run(self.message.id)

        self.assertEqual(call_order, ["p2"])
        adapter_p2.send_sms.assert_called_once()
        adapter_p1.send_sms.assert_not_called()
        mock_publish.assert_called_once_with(self.message)


class SmsSendFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user", password="pass")

    @patch("messaging.tasks.get_provider_adapter")
    def test_happy_path(self, mock_get_adapter):
        provider = SmsProvider.objects.create(
            name="ProviderA",
            slug="provider-a",
            send_url="http://example.com/send",
            balance_url="http://example.com/bal",
            default_sender="100",
            auth_type=AuthType.NONE,
            priority=100,
        )
        message = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello",
        )
        adapter = MagicMock()
        adapter.send_sms.return_value = {
            "status": "success",
            "message_id": "mid",
            "raw_response": {},
        }
        mock_get_adapter.return_value = adapter

        with patch("messaging.tasks.send_sms_with_failover.delay") as mock_delay:
            mock_delay.side_effect = lambda mid: send_sms_with_failover.run(mid)
            dispatch_pending_messages.run()

        message.refresh_from_db()
        self.assertEqual(message.status, MessageStatus.SENT_TO_PROVIDER)
        self.assertEqual(message.provider, provider)
        self.assertEqual(message.provider_message_id, "mid")
        adapter.send_sms.assert_called_once_with("12345", "hello")

    @patch("messaging.tasks.get_provider_adapter")
    def test_simple_failover(self, mock_get_adapter):
        provider_a = SmsProvider.objects.create(
            name="ProviderA",
            slug="provider-a",
            send_url="http://example.com/a",
            balance_url="http://example.com/bal",
            default_sender="100",
            auth_type=AuthType.NONE,
            priority=100,
        )
        provider_b = SmsProvider.objects.create(
            name="ProviderB",
            slug="provider-b",
            send_url="http://example.com/b",
            balance_url="http://example.com/bal",
            default_sender="200",
            auth_type=AuthType.NONE,
            priority=90,
        )
        message = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello",
        )
        adapter_a = MagicMock()
        adapter_a.send_sms.return_value = {
            "status": "failure",
            "type": "transient",
            "reason": "temp",
            "raw_response": {},
        }
        adapter_b = MagicMock()
        adapter_b.send_sms.return_value = {
            "status": "success",
            "message_id": "mid2",
            "raw_response": {},
        }
        mock_get_adapter.side_effect = [adapter_a, adapter_b]

        with patch("messaging.tasks.send_sms_with_failover.delay") as mock_delay:
            mock_delay.side_effect = lambda mid: send_sms_with_failover.run(mid)
            dispatch_pending_messages.run()

        message.refresh_from_db()
        self.assertEqual(message.status, MessageStatus.SENT_TO_PROVIDER)
        self.assertEqual(message.provider, provider_b)
        adapter_a.send_sms.assert_called_once()
        adapter_b.send_sms.assert_called_once()

    @patch("messaging.tasks.get_provider_adapter")
    def test_full_retry_cycle(self, mock_get_adapter):
        SmsProvider.objects.create(
            name="ProviderA",
            slug="provider-a",
            send_url="http://example.com/a",
            balance_url="http://example.com/bal",
            default_sender="100",
            auth_type=AuthType.NONE,
            priority=100,
        )
        SmsProvider.objects.create(
            name="ProviderB",
            slug="provider-b",
            send_url="http://example.com/b",
            balance_url="http://example.com/bal",
            default_sender="200",
            auth_type=AuthType.NONE,
            priority=90,
        )
        message = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello",
        )
        adapter_a = MagicMock()
        adapter_a.send_sms.return_value = {
            "status": "failure",
            "type": "transient",
            "reason": "temp1",
            "raw_response": {},
        }
        adapter_b = MagicMock()
        adapter_b.send_sms.return_value = {
            "status": "failure",
            "type": "transient",
            "reason": "temp2",
            "raw_response": {},
        }
        mock_get_adapter.side_effect = [adapter_a, adapter_b]

        with patch("messaging.tasks.send_sms_with_failover.delay"):
            dispatch_pending_messages.run()

        original = send_sms_with_failover.request.retries
        send_sms_with_failover.request.retries = 0
        try:
            with patch.object(
                send_sms_with_failover, "retry", side_effect=Retry(), autospec=True
            ) as mock_retry:
                with self.assertRaises(Retry):
                    send_sms_with_failover.run(message.id)
        finally:
            send_sms_with_failover.request.retries = original

        message.refresh_from_db()
        self.assertEqual(message.status, MessageStatus.AWAITING_RETRY)
        self.assertEqual(message.error_message, "temp2")

    @patch("messaging.tasks.publish_to_dlq")
    @patch("messaging.tasks.get_provider_adapter")
    def test_permanent_failure_fail_fast(self, mock_get_adapter, mock_publish):
        SmsProvider.objects.create(
            name="ProviderA",
            slug="provider-a",
            send_url="http://example.com/a",
            balance_url="http://example.com/bal",
            default_sender="100",
            auth_type=AuthType.NONE,
            priority=100,
        )
        SmsProvider.objects.create(
            name="ProviderB",
            slug="provider-b",
            send_url="http://example.com/b",
            balance_url="http://example.com/bal",
            default_sender="200",
            auth_type=AuthType.NONE,
            priority=90,
        )
        message = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello",
        )
        adapter_a = MagicMock()
        adapter_a.send_sms.return_value = {
            "status": "failure",
            "type": "permanent",
            "reason": "blacklisted",
            "raw_response": {},
        }
        adapter_b = MagicMock()
        adapter_b.send_sms.return_value = {
            "status": "success",
            "message_id": "mid",
            "raw_response": {},
        }
        mock_get_adapter.side_effect = [adapter_a, adapter_b]

        with patch("messaging.tasks.send_sms_with_failover.delay"):
            dispatch_pending_messages.run()
        send_sms_with_failover.run(message.id)

        message.refresh_from_db()
        self.assertEqual(message.status, MessageStatus.FAILED)
        self.assertEqual(message.error_message, "blacklisted")
        adapter_a.send_sms.assert_called_once()
        adapter_b.send_sms.assert_not_called()
        mock_publish.assert_called_once_with(message)

    @patch("messaging.tasks.get_provider_adapter")
    def test_user_specified_provider_logic(self, mock_get_adapter):
        provider_a = SmsProvider.objects.create(
            name="ProviderA",
            slug="provider-a",
            send_url="http://example.com/a",
            balance_url="http://example.com/bal",
            default_sender="100",
            auth_type=AuthType.NONE,
            priority=90,
        )
        provider_b = SmsProvider.objects.create(
            name="ProviderB",
            slug="provider-b",
            send_url="http://example.com/b",
            balance_url="http://example.com/bal",
            default_sender="200",
            auth_type=AuthType.NONE,
            priority=80,
        )
        provider_c = SmsProvider.objects.create(
            name="ProviderC",
            slug="provider-c",
            send_url="http://example.com/c",
            balance_url="http://example.com/bal",
            default_sender="300",
            auth_type=AuthType.NONE,
            priority=100,
        )
        message = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello",
            initial_envelope={"providers_effective": ["provider-c", "provider-a"]},
        )
        send_order: list[str] = []

        def make_result(name, result):
            def _side_effect(*args, **kwargs):
                send_order.append(name)
                return result

            return _side_effect

        adapter_c = MagicMock()
        adapter_c.send_sms.side_effect = make_result(
            "C",
            {"status": "failure", "type": "transient", "reason": "temp", "raw_response": {}},
        )
        adapter_a = MagicMock()
        adapter_a.send_sms.side_effect = make_result(
            "A", {"status": "success", "message_id": "mid", "raw_response": {}}
        )
        adapter_b = MagicMock()

        def fake_get_adapter(provider):
            if provider.slug == "provider-c":
                return adapter_c
            if provider.slug == "provider-a":
                return adapter_a
            if provider.slug == "provider-b":
                return adapter_b
            raise AssertionError("unexpected provider")

        mock_get_adapter.side_effect = fake_get_adapter

        with patch("messaging.tasks.send_sms_with_failover.delay") as mock_delay:
            mock_delay.side_effect = lambda mid: send_sms_with_failover.run(mid)
            dispatch_pending_messages.run()

        message.refresh_from_db()
        self.assertEqual(message.provider, provider_a)
        self.assertEqual(message.status, MessageStatus.SENT_TO_PROVIDER)
        self.assertEqual(send_order, ["C", "A"])
        adapter_b.send_sms.assert_not_called()

class MessageDetailViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user", password="pass")
        self.provider = SmsProvider.objects.create(
            name="Provider",
            slug="prov",
            send_url="http://example.com/send",
            balance_url="http://example.com/bal",
            default_sender="100",
            auth_type=AuthType.NONE,
        )
        self.message = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello",
            provider=self.provider,
        )
        MessageAttemptLog.objects.create(
            message=self.message,
            provider=self.provider,
            status=AttemptStatus.SUCCESS,
            provider_response={"status": 0, "messages": [{"id": 123, "status": 0}]},
        )

    def test_detail_view_displays_attempt_logs(self):
        self.client.login(username="user", password="pass")
        url = reverse("messaging:message_detail", args=[self.message.tracking_id])
        response = self.client.get(url)
        self.assertContains(response, self.message.recipient)
        self.assertContains(response, "Success (Provider ID: 123)")
        self.assertContains(response, self.provider.name)


class AdminMessageListViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="pass", is_staff=True)
        self.user = User.objects.create_user("user", password="pass")
        self.provider = SmsProvider.objects.create(
            name="Provider",
            slug="prov",
            send_url="http://example.com/send",
            balance_url="http://example.com/bal",
            default_sender="100",
            auth_type=AuthType.NONE,
        )
        self.message = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello",
            provider=self.provider,
        )

    def test_message_links_to_admin_detail(self):
        self.client.login(username="admin", password="pass")
        url = reverse("messaging:admin_messages_list")
        response = self.client.get(url)
        detail_url = reverse("messaging:admin_message_detail", args=[self.message.tracking_id])
        self.assertContains(response, detail_url)


class AdminMessageDetailViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="pass", is_staff=True)
        self.user = User.objects.create_user("user", password="pass")
        self.provider = SmsProvider.objects.create(
            name="Provider",
            slug="prov",
            send_url="http://example.com/send",
            balance_url="http://example.com/bal",
            default_sender="100",
            auth_type=AuthType.NONE,
        )
        self.message = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello",
            provider=self.provider,
        )

    def test_admin_can_view_message(self):
        self.client.login(username="admin", password="pass")
        url = reverse("messaging:admin_message_detail", args=[self.message.tracking_id])
        response = self.client.get(url)
        self.assertContains(response, self.message.recipient)
        self.assertContains(response, self.user.username)

    def test_non_admin_forbidden(self):
        self.client.login(username="user", password="pass")
        url = reverse("messaging:admin_message_detail", args=[self.message.tracking_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class MagfaStatusSummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user", password="pass")
        self.provider = SmsProvider.objects.create(
            name="Magfa",
            slug="magfa",
            send_url="http://example.com/send",
            balance_url="http://example.com/balance",
            default_sender="100",
            auth_type=AuthType.NONE,
        )
        self.message = Message.objects.create(
            user=self.user,
            tracking_id=uuid.uuid4(),
            recipient="12345",
            text="hello",
            provider=self.provider,
        )

    def _create_attempt(self, response, status=AttemptStatus.FAILURE):
        return MessageAttemptLog.objects.create(
            message=self.message,
            provider=self.provider,
            status=status,
            provider_response=response,
        )

    def test_parses_successful_response(self):
        resp = {"status": 0, "messages": [{"id": 111, "status": 0}]}
        attempt = self._create_attempt(resp, status=AttemptStatus.SUCCESS)
        self.assertEqual(
            attempt.get_magfa_status_summary(), "Success (Provider ID: 111)"
        )

    def test_maps_error_codes(self):
        cases = {
            1: "Invalid recipient number",
            14: "Insufficient credit",
            27: "Recipient is blacklisted",
            33: "Recipient has blocked messages from this sender",
            99: "Failed with provider code: 99",
        }
        for code, expected in cases.items():
            resp = {"status": 0, "messages": [{"id": 111, "status": code}]}
            attempt = self._create_attempt(resp)
            self.assertEqual(attempt.get_magfa_status_summary(), expected)

    def test_handles_overall_failure(self):
        resp = {"status": 18}
        attempt = self._create_attempt(resp)
        self.assertEqual(
            attempt.get_magfa_status_summary(),
            "Request Failed (Overall Status: 18)",
        )

    def test_handles_invalid_structure(self):
        attempt = self._create_attempt("not a dict")
        self.assertEqual(
            attempt.get_magfa_status_summary(), "Could not parse provider response."
        )
