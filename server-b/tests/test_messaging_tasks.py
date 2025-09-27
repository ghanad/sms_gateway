import datetime
import importlib
import os
import sys
import tempfile
from types import SimpleNamespace

import django
from django.apps import apps

import pytest
from prometheus_client import REGISTRY


TEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if TEST_ROOT not in sys.path:
    sys.path.insert(0, TEST_ROOT)

os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", tempfile.mkdtemp())


METRIC_NAMES = [
    "SMS_MESSAGES_PROCESSED_TOTAL",
    "SMS_MESSAGES_PENDING_GAUGE",
    "SMS_MESSAGE_FINAL_STATUS_TOTAL",
    "SMS_PROCESSING_DURATION_SECONDS",
    "SMS_PROVIDER_SEND_ATTEMPTS_TOTAL",
    "SMS_PROVIDER_SEND_LATENCY_SECONDS",
    "SMS_PROVIDER_FAILOVERS_TOTAL",
    "SMS_PROVIDER_BALANCE_GAUGE",
    "SMS_CELERY_TASK_RETRIES_TOTAL",
    "SMS_DLQ_MESSAGES_TOTAL",
]


def reset_histogram(metric):
    metrics_map = getattr(metric, "_metrics", None)
    if metrics_map is not None:
        metrics_map.clear()

    buckets = getattr(metric, "_buckets", None)
    if buckets is not None:
        for bucket in buckets:
            try:
                bucket.set(0)
            except AttributeError:
                continue

    sum_value = getattr(metric, "_sum", None)
    if sum_value is not None:
        sum_value.set(0)


def set_task_globals(task, monkeypatch, **overrides):
    wrapped = getattr(task, "__wrapped__", task)
    func = getattr(wrapped, "__func__", wrapped)
    globals_dict = func.__globals__
    for name, value in overrides.items():
        monkeypatch.setitem(globals_dict, name, value)


def import_messaging_tasks(monkeypatch):
    module_name = "messaging.tasks"
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "sms_gateway_project.settings")
    if not apps.ready:
        django.setup()
    if module_name in sys.modules:
        existing_module = sys.modules[module_name]
        for metric_name in METRIC_NAMES:
            metric = getattr(existing_module, metric_name, None)
            if metric is None:
                continue
            try:
                REGISTRY.unregister(metric)
            except KeyError:
                pass
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def test_update_delivery_statuses_updates_recent_messages(monkeypatch):
    module = import_messaging_tasks(monkeypatch)

    module.SMS_MESSAGE_FINAL_STATUS_TOTAL.clear()
    reset_histogram(module.SMS_PROCESSING_DURATION_SECONDS)

    fake_now = datetime.datetime(2024, 1, 2, 12, 0, tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(module.timezone, "now", lambda: fake_now)

    provider = SimpleNamespace(pk=1)

    class DummyMessage:
        def __init__(self, pk, provider_message_id, updated_at, created_at, error_message=""):
            self.pk = pk
            self.provider = provider
            self.provider_message_id = provider_message_id
            self.updated_at = updated_at
            self.created_at = created_at
            self.status = module.MessageStatus.SENT_TO_PROVIDER
            self.error_message = error_message
            self.delivered_at = None
            self.saved = []

        def save(self, update_fields=None):
            self.saved.append(update_fields)

    recent_created = fake_now - datetime.timedelta(hours=5)
    delivered_message = DummyMessage(
        pk=101,
        provider_message_id="101",
        updated_at=fake_now - datetime.timedelta(hours=1),
        created_at=recent_created,
        error_message="will-clear",
    )
    failed_message = DummyMessage(
        pk=202,
        provider_message_id="202",
        updated_at=fake_now - datetime.timedelta(hours=2),
        created_at=fake_now - datetime.timedelta(hours=6),
    )
    stale_message = DummyMessage(
        pk=303,
        provider_message_id="303",
        updated_at=fake_now - datetime.timedelta(hours=90),
        created_at=fake_now - datetime.timedelta(hours=95),
    )

    class DummyQuerySet:
        def __init__(self, data):
            self._data = list(data)

        def select_related(self, *args, **kwargs):
            return self

        def filter(self, **kwargs):
            data = self._data
            for key, value in kwargs.items():
                if key == "status":
                    data = [item for item in data if item.status == value]
                elif key == "updated_at__gte":
                    data = [item for item in data if item.updated_at >= value]
                elif key == "provider__isnull":
                    if value:
                        data = [item for item in data if item.provider is None]
                    else:
                        data = [item for item in data if item.provider is not None]
                else:
                    raise AssertionError(f"Unhandled filter {key}")
            return DummyQuerySet(data)

        def exclude(self, **kwargs):
            data = self._data
            for key, value in kwargs.items():
                if key == "provider_message_id__isnull" and value:
                    data = [item for item in data if item.provider_message_id is not None]
                elif key == "provider_message_id__exact":
                    data = [
                        item
                        for item in data
                        if getattr(item, "provider_message_id", None) != value
                    ]
                else:
                    raise AssertionError(f"Unhandled exclude {key}")
            return DummyQuerySet(data)

        def __iter__(self):
            return iter(self._data)

    class DummyManager:
        def __init__(self, data):
            self._data = data

        def select_related(self, *args, **kwargs):
            return DummyQuerySet(self._data)

    captured_ids = []

    class DummyAdapter:
        supports_status_check = True

        def __init__(self, provider):
            self.provider = provider

        def check_status(self, message_ids):
            captured_ids.append(message_ids)
            return {
                "101": {
                    "status": module.MessageStatus.DELIVERED,
                    "delivered_at": "2024-01-02 10:30:00",
                    "provider_status": 1,
                },
                "202": {
                    "status": module.MessageStatus.FAILED,
                    "provider_status": 2,
                },
            }

    set_task_globals(
        module.update_delivery_statuses,
        monkeypatch,
        Message=SimpleNamespace(
            objects=DummyManager([delivered_message, failed_message, stale_message])
        ),
        get_provider_adapter=lambda prov: DummyAdapter(prov),
    )

    module.update_delivery_statuses.run()

    assert captured_ids == [["101", "202"]]

    assert delivered_message.status == module.MessageStatus.DELIVERED
    assert delivered_message.error_message == ""
    assert delivered_message.delivered_at is not None
    assert module.timezone.is_aware(delivered_message.delivered_at)
    assert delivered_message.saved[0] == ["status", "delivered_at", "error_message"]

    assert failed_message.status == module.MessageStatus.FAILED
    assert failed_message.delivered_at is None
    assert "provider status 2" in failed_message.error_message
    assert failed_message.saved
    saved_fields = failed_message.saved[0]
    assert "status" in saved_fields
    assert "error_message" in saved_fields

    assert stale_message.status == module.MessageStatus.SENT_TO_PROVIDER
    assert stale_message.saved == []

    delivered_total = (
        module.SMS_MESSAGE_FINAL_STATUS_TOTAL.labels(
            status=module.MessageStatus.DELIVERED
        )._value.get()
    )
    failed_total = (
        module.SMS_MESSAGE_FINAL_STATUS_TOTAL.labels(
            status=module.MessageStatus.FAILED
        )._value.get()
    )
    assert delivered_total == 1
    assert failed_total == 1

    duration_samples = module.SMS_PROCESSING_DURATION_SECONDS.collect()[0].samples
    duration_count = next(
        sample.value
        for sample in duration_samples
        if sample.name == "sms_processing_duration_seconds_count"
    )
    assert duration_count == pytest.approx(2.0)


def test_publish_to_dlq_uses_configured_virtual_host(monkeypatch):
    module = import_messaging_tasks(monkeypatch)

    module.SMS_DLQ_MESSAGES_TOTAL.reset()

    captured = {}

    def fake_plain_credentials(user, password):
        captured["credentials"] = (user, password)
        return SimpleNamespace(user=user, password=password)

    def fake_connection_parameters(*args, **kwargs):
        captured["connection_kwargs"] = kwargs
        return SimpleNamespace(**kwargs)

    class DummyChannel:
        def queue_declare(self, **kwargs):
            captured["queue_declared"] = kwargs

        def basic_publish(self, **kwargs):
            captured["published"] = kwargs

    class DummyConnection:
        def channel(self):
            return DummyChannel()

        def close(self):
            captured["closed"] = True

    def fake_blocking_connection(params):
        captured["params_obj"] = params
        return DummyConnection()

    monkeypatch.setattr(
        module,
        "pika",
        SimpleNamespace(
            PlainCredentials=fake_plain_credentials,
            ConnectionParameters=fake_connection_parameters,
            BlockingConnection=fake_blocking_connection,
        ),
    )

    monkeypatch.setattr(
        module,
        "settings",
        SimpleNamespace(
            RABBITMQ_USER="guest",
            RABBITMQ_PASS="guestpass",
            RABBITMQ_HOST="rabbitmq",
            RABBITMQ_VHOST="sms_pipeline_vhost",
        ),
    )

    message = SimpleNamespace(id=1, tracking_id="abc", error_message="oops")

    module.publish_to_dlq(message)

    assert captured["credentials"] == ("guest", "guestpass")
    assert captured["connection_kwargs"]["host"] == "rabbitmq"
    assert captured["connection_kwargs"]["virtual_host"] == "sms_pipeline_vhost"
    assert "queue_declared" in captured
    assert "published" in captured
    assert captured.get("closed") is True
    assert module.SMS_DLQ_MESSAGES_TOTAL._value.get() == 1


def test_send_sms_with_failover_records_success_metrics(monkeypatch):
    module = import_messaging_tasks(monkeypatch)

    module.SMS_PROVIDER_SEND_ATTEMPTS_TOTAL.clear()
    reset_histogram(module.SMS_PROVIDER_SEND_LATENCY_SECONDS)
    module.SMS_PROVIDER_FAILOVERS_TOTAL.clear()
    module.SMS_MESSAGE_FINAL_STATUS_TOTAL.clear()
    reset_histogram(module.SMS_PROCESSING_DURATION_SECONDS)
    module.SMS_CELERY_TASK_RETRIES_TOTAL.reset()
    module.SMS_DLQ_MESSAGES_TOTAL.reset()

    fake_now = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
    created_at = fake_now - datetime.timedelta(seconds=30)

    class DummyMessage:
        def __init__(self):
            self.id = 1
            self.recipient = "+15551234"
            self.text = "Hello"
            self.initial_envelope = {"providers_effective": ["alpha"]}
            self.send_attempts = 0
            self.status = module.MessageStatus.PENDING
            self.provider = None
            self.provider_message_id = None
            self.provider_response = None
            self.sent_at = None
            self.error_message = ""
            self.created_at = created_at
            self.saved = []

        def save(self, update_fields=None):
            self.saved.append(update_fields)

    message = DummyMessage()

    monkeypatch.setattr(
        module,
        "Message",
        SimpleNamespace(objects=SimpleNamespace(get=lambda pk: message)),
    )

    attempt_logs = []
    monkeypatch.setattr(
        module,
        "MessageAttemptLog",
        SimpleNamespace(
            objects=SimpleNamespace(create=lambda **kwargs: attempt_logs.append(kwargs))
        ),
    )

    class DummyProvider:
        def __init__(self, slug, name):
            self.slug = slug
            self.name = name
            self.is_active = True

    provider = DummyProvider("alpha", "AlphaSMS")

    class DummyProviderQuerySet(list):
        def first(self):
            return self[0] if self else None

        def order_by(self, *args, **kwargs):
            return self

    class DummyProviderManager:
        def __init__(self, providers):
            self._providers = providers

        def filter(self, **kwargs):
            providers = self._providers
            if "slug__iexact" in kwargs:
                slug = kwargs["slug__iexact"].lower()
                matched = [p for p in providers if p.slug.lower() == slug]
            elif "name__iexact" in kwargs:
                name = kwargs["name__iexact"].lower()
                matched = [p for p in providers if p.name.lower() == name]
            elif "is_active" in kwargs:
                if kwargs.get("is_active"):
                    matched = [p for p in providers if getattr(p, "is_active", True)]
                else:
                    matched = []
            else:
                matched = providers
            return DummyProviderQuerySet(matched)

    monkeypatch.setattr(
        module,
        "SmsProvider",
        SimpleNamespace(objects=DummyProviderManager([provider])),
    )

    send_calls = []

    class DummyAdapter:
        def send_sms(self, recipient, message_text):
            send_calls.append((recipient, message_text))
            return {
                "status": "success",
                "message_id": "mid-1",
                "raw_response": {"ok": True},
            }

    monkeypatch.setattr(module, "get_provider_adapter", lambda prov: DummyAdapter())

    perf_values = iter([100.0, 100.5])
    monkeypatch.setattr(module.time, "perf_counter", lambda: next(perf_values))
    monkeypatch.setattr(module.timezone, "now", lambda: fake_now)
    task_request = module.send_sms_with_failover.request
    monkeypatch.setattr(task_request, "retries", 0, raising=False)

    set_task_globals(
        module.send_sms_with_failover,
        monkeypatch,
        Message=module.Message,
        SmsProvider=module.SmsProvider,
        MessageAttemptLog=module.MessageAttemptLog,
        get_provider_adapter=module.get_provider_adapter,
        publish_to_dlq=module.publish_to_dlq,
        timezone=module.timezone,
    )

    module.send_sms_with_failover.run(message.id)

    assert message.status == module.MessageStatus.SENT_TO_PROVIDER
    assert message.provider is provider
    assert message.send_attempts == 1
    assert message.sent_at == fake_now
    assert send_calls == [(message.recipient, message.text)]

    success_label = module.MessageStatus.SENT_TO_PROVIDER
    assert (
        module.SMS_MESSAGE_FINAL_STATUS_TOTAL.labels(status=success_label)._value.get()
        == 1
    )
    duration_samples = module.SMS_PROCESSING_DURATION_SECONDS.collect()[0].samples
    duration_count = next(
        sample.value
        for sample in duration_samples
        if sample.name == "sms_processing_duration_seconds_count"
    )
    duration_sum = next(
        sample.value
        for sample in duration_samples
        if sample.name == "sms_processing_duration_seconds_sum"
    )
    assert duration_count == pytest.approx(1.0)
    assert duration_sum == pytest.approx(30.0)
    assert (
        module.SMS_PROVIDER_SEND_ATTEMPTS_TOTAL
        .labels(provider="alpha", outcome="success")
        ._value.get()
        == 1
    )
    assert (
        module.SMS_PROVIDER_SEND_LATENCY_SECONDS.labels(provider="alpha")._sum.get()
        == pytest.approx(0.5)
    )
    latency_samples = module.SMS_PROVIDER_SEND_LATENCY_SECONDS.collect()[0].samples
    latency_counts = [
        sample.value
        for sample in latency_samples
        if sample.name == "sms_provider_send_latency_seconds_count"
        and sample.labels.get("provider") == "alpha"
    ]
    assert len(latency_counts) == 1
    assert latency_counts[0] == pytest.approx(1.0)
    assert module.SMS_CELERY_TASK_RETRIES_TOTAL._value.get() == 0
    assert module.SMS_DLQ_MESSAGES_TOTAL._value.get() == 0


def test_send_sms_with_failover_records_failover_metric(monkeypatch):
    module = import_messaging_tasks(monkeypatch)

    module.SMS_PROVIDER_SEND_ATTEMPTS_TOTAL.clear()
    reset_histogram(module.SMS_PROVIDER_SEND_LATENCY_SECONDS)
    module.SMS_PROVIDER_FAILOVERS_TOTAL.clear()
    module.SMS_MESSAGE_FINAL_STATUS_TOTAL.clear()
    reset_histogram(module.SMS_PROCESSING_DURATION_SECONDS)
    module.SMS_CELERY_TASK_RETRIES_TOTAL.reset()
    module.SMS_DLQ_MESSAGES_TOTAL.reset()

    fake_now = datetime.datetime(2024, 1, 1, 12, 30, tzinfo=datetime.timezone.utc)
    created_at = fake_now - datetime.timedelta(seconds=40)

    class DummyMessage:
        def __init__(self):
            self.id = 2
            self.recipient = "+15555555"
            self.text = "Fail over"
            self.initial_envelope = {"providers_effective": ["alpha", "beta"]}
            self.send_attempts = 0
            self.status = module.MessageStatus.PENDING
            self.provider = None
            self.provider_message_id = None
            self.provider_response = None
            self.sent_at = None
            self.error_message = ""
            self.created_at = created_at
            self.saved = []

        def save(self, update_fields=None):
            self.saved.append(update_fields)

    message = DummyMessage()

    monkeypatch.setattr(
        module,
        "Message",
        SimpleNamespace(objects=SimpleNamespace(get=lambda pk: message)),
    )

    attempt_logs = []
    monkeypatch.setattr(
        module,
        "MessageAttemptLog",
        SimpleNamespace(
            objects=SimpleNamespace(create=lambda **kwargs: attempt_logs.append(kwargs))
        ),
    )

    class DummyProvider:
        def __init__(self, slug, name):
            self.slug = slug
            self.name = name
            self.is_active = True

    providers = [
        DummyProvider("alpha", "AlphaSMS"),
        DummyProvider("beta", "BetaSMS"),
    ]

    class DummyProviderQuerySet(list):
        def first(self):
            return self[0] if self else None

        def order_by(self, *args, **kwargs):
            return self

    class DummyProviderManager:
        def __init__(self, data):
            self._data = data

        def filter(self, **kwargs):
            data = self._data
            if "slug__iexact" in kwargs:
                slug = kwargs["slug__iexact"].lower()
                matched = [p for p in data if p.slug.lower() == slug]
            elif "name__iexact" in kwargs:
                name = kwargs["name__iexact"].lower()
                matched = [p for p in data if p.name.lower() == name]
            elif "is_active" in kwargs:
                if kwargs.get("is_active"):
                    matched = [p for p in data if getattr(p, "is_active", True)]
                else:
                    matched = []
            else:
                matched = data
            return DummyProviderQuerySet(matched)

    monkeypatch.setattr(
        module,
        "SmsProvider",
        SimpleNamespace(objects=DummyProviderManager(providers)),
    )

    def make_adapter(provider):
        if provider.slug == "alpha":
            return SimpleNamespace(
                send_sms=lambda recipient, message_text: {
                    "status": "failure",
                    "type": "transient",
                    "reason": "Temporary",
                    "raw_response": {"error": "temp"},
                }
            )

        return SimpleNamespace(
            send_sms=lambda recipient, message_text: {
                "status": "success",
                "message_id": "beta-1",
                "raw_response": {"ok": True},
            }
        )

    monkeypatch.setattr(module, "get_provider_adapter", make_adapter)

    perf_values = iter([10.0, 10.3, 20.0, 20.6])
    monkeypatch.setattr(module.time, "perf_counter", lambda: next(perf_values))
    monkeypatch.setattr(module.timezone, "now", lambda: fake_now)
    task_request = module.send_sms_with_failover.request
    monkeypatch.setattr(task_request, "retries", 0, raising=False)

    set_task_globals(
        module.send_sms_with_failover,
        monkeypatch,
        Message=module.Message,
        SmsProvider=module.SmsProvider,
        MessageAttemptLog=module.MessageAttemptLog,
        get_provider_adapter=module.get_provider_adapter,
        publish_to_dlq=module.publish_to_dlq,
        timezone=module.timezone,
    )

    module.send_sms_with_failover.run(message.id)

    assert message.status == module.MessageStatus.SENT_TO_PROVIDER
    assert message.provider is providers[1]
    assert message.send_attempts == 1
    assert len(attempt_logs) == 2

    failover_metric = module.SMS_PROVIDER_FAILOVERS_TOTAL.labels(
        from_provider="alpha", to_provider="beta"
    )._value.get()
    assert failover_metric == 1

    assert (
        module.SMS_PROVIDER_SEND_ATTEMPTS_TOTAL
        .labels(provider="alpha", outcome="transient_failure")
        ._value.get()
        == 1
    )
    assert (
        module.SMS_PROVIDER_SEND_ATTEMPTS_TOTAL
        .labels(provider="beta", outcome="success")
        ._value.get()
        == 1
    )
    assert (
        module.SMS_PROVIDER_SEND_LATENCY_SECONDS.labels(provider="alpha")._sum.get()
        == pytest.approx(0.3)
    )
    assert (
        module.SMS_PROVIDER_SEND_LATENCY_SECONDS.labels(provider="beta")._sum.get()
        == pytest.approx(0.6)
    )
    success_label = module.MessageStatus.SENT_TO_PROVIDER
    assert (
        module.SMS_MESSAGE_FINAL_STATUS_TOTAL.labels(status=success_label)._value.get()
        == 1
    )
    duration_samples = module.SMS_PROCESSING_DURATION_SECONDS.collect()[0].samples
    duration_sum = next(
        sample.value
        for sample in duration_samples
        if sample.name == "sms_processing_duration_seconds_sum"
    )
    assert duration_sum == pytest.approx(40.0)
    assert module.SMS_CELERY_TASK_RETRIES_TOTAL._value.get() == 0
    assert module.SMS_DLQ_MESSAGES_TOTAL._value.get() == 0


def test_send_sms_with_failover_transient_failure_increments_retry_metric(monkeypatch):
    module = import_messaging_tasks(monkeypatch)

    module.SMS_PROVIDER_SEND_ATTEMPTS_TOTAL.clear()
    reset_histogram(module.SMS_PROVIDER_SEND_LATENCY_SECONDS)
    module.SMS_PROVIDER_FAILOVERS_TOTAL.clear()
    module.SMS_MESSAGE_FINAL_STATUS_TOTAL.clear()
    reset_histogram(module.SMS_PROCESSING_DURATION_SECONDS)
    module.SMS_CELERY_TASK_RETRIES_TOTAL.reset()
    module.SMS_DLQ_MESSAGES_TOTAL.reset()

    fake_now = datetime.datetime(2024, 1, 1, 12, 5, tzinfo=datetime.timezone.utc)

    class DummyMessage:
        def __init__(self):
            self.id = 7
            self.recipient = "+15559876"
            self.text = "Retry please"
            self.initial_envelope = {"providers_effective": ["alpha"]}
            self.send_attempts = 0
            self.status = module.MessageStatus.PENDING
            self.error_message = ""
            self.created_at = fake_now - datetime.timedelta(seconds=10)
            self.saved = []

        def save(self, update_fields=None):
            self.saved.append(update_fields)

    message = DummyMessage()

    monkeypatch.setattr(
        module,
        "Message",
        SimpleNamespace(objects=SimpleNamespace(get=lambda pk: message)),
    )

    monkeypatch.setattr(
        module,
        "MessageAttemptLog",
        SimpleNamespace(objects=SimpleNamespace(create=lambda **kwargs: None)),
    )

    class DummyProvider:
        def __init__(self):
            self.slug = "alpha"
            self.name = "AlphaSMS"
            self.is_active = True

    provider = DummyProvider()

    class DummyProviderQuerySet(list):
        def first(self):
            return self[0] if self else None

        def order_by(self, *args, **kwargs):
            return self

    class DummyProviderManager:
        def filter(self, **kwargs):
            return DummyProviderQuerySet([provider])

    monkeypatch.setattr(
        module,
        "SmsProvider",
        SimpleNamespace(objects=DummyProviderManager()),
    )

    class DummyAdapter:
        def send_sms(self, recipient, message_text):
            return {
                "status": "failure",
                "type": "transient",
                "reason": "Temporary issue",
                "raw_response": {"error": "temp"},
            }

    monkeypatch.setattr(module, "get_provider_adapter", lambda prov: DummyAdapter())

    perf_values = iter([50.0, 50.2])
    monkeypatch.setattr(module.time, "perf_counter", lambda: next(perf_values))
    monkeypatch.setattr(module.timezone, "now", lambda: fake_now)
    task_request = module.send_sms_with_failover.request
    monkeypatch.setattr(task_request, "retries", 0, raising=False)

    retry_info = {}

    def fake_retry(*, countdown):
        retry_info["countdown"] = countdown
        raise RuntimeError("retry called")

    monkeypatch.setattr(module.send_sms_with_failover, "retry", fake_retry)

    set_task_globals(
        module.send_sms_with_failover,
        monkeypatch,
        Message=module.Message,
        SmsProvider=module.SmsProvider,
        MessageAttemptLog=module.MessageAttemptLog,
        get_provider_adapter=module.get_provider_adapter,
        publish_to_dlq=module.publish_to_dlq,
        timezone=module.timezone,
    )

    with pytest.raises(RuntimeError):
        module.send_sms_with_failover.run(message.id)

    assert retry_info["countdown"] == 60
    assert message.status == module.MessageStatus.AWAITING_RETRY
    assert message.error_message == "Temporary issue"
    assert module.SMS_CELERY_TASK_RETRIES_TOTAL._value.get() == 1
    assert (
        module.SMS_PROVIDER_SEND_ATTEMPTS_TOTAL
        .labels(provider="alpha", outcome="transient_failure")
        ._value.get()
        == 1
    )
    assert (
        module.SMS_PROVIDER_SEND_LATENCY_SECONDS.labels(provider="alpha")._sum.get()
        == pytest.approx(0.2)
    )
    duration_samples = module.SMS_PROCESSING_DURATION_SECONDS.collect()[0].samples
    duration_count = next(
        sample.value
        for sample in duration_samples
        if sample.name == "sms_processing_duration_seconds_count"
    )
    assert duration_count == pytest.approx(0.0)
    assert module.SMS_DLQ_MESSAGES_TOTAL._value.get() == 0


def test_dispatch_pending_messages_updates_pending_gauge(monkeypatch):
    module = import_messaging_tasks(monkeypatch)

    module.SMS_MESSAGES_PENDING_GAUGE.set(0)

    class DummyMessage:
        def __init__(self, mid, status):
            self.id = mid
            self.status = status

    pending_status = module.MessageStatus.PENDING
    processing_status = module.MessageStatus.PROCESSING

    messages = [
        DummyMessage(1, pending_status),
        DummyMessage(2, pending_status),
        DummyMessage(3, processing_status),
    ]

    class DummyQuerySet:
        def __init__(self, data):
            self._data = list(data)

        def filter(self, **kwargs):
            data = self._data
            if "status" in kwargs:
                status_value = kwargs["status"]
                data = [m for m in data if m.status == status_value]
            elif "id__in" in kwargs:
                ids = set(kwargs["id__in"])
                data = [m for m in data if m.id in ids]
            return DummyQuerySet(data)

        def update(self, **kwargs):
            for obj in self._data:
                for key, value in kwargs.items():
                    setattr(obj, key, value)
            return len(self._data)

        def __getitem__(self, item):
            return self._data[item]

        def __iter__(self):
            return iter(self._data)

        def count(self):
            return len(self._data)

    class DummyManager:
        def __init__(self, data):
            self._data = data

        def select_for_update(self, **kwargs):
            return DummyQuerySet(self._data)

        def filter(self, **kwargs):
            return DummyQuerySet(self._data).filter(**kwargs)

    monkeypatch.setattr(
        module,
        "Message",
        SimpleNamespace(objects=DummyManager(messages)),
    )

    class DummyAtomic:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(module.transaction, "atomic", lambda: DummyAtomic())

    dispatched = []
    monkeypatch.setattr(
        module.send_sms_with_failover, "delay", lambda mid: dispatched.append(mid)
    )

    set_task_globals(
        module.dispatch_pending_messages,
        monkeypatch,
        Message=module.Message,
        transaction=module.transaction,
        send_sms_with_failover=module.send_sms_with_failover,
    )

    module.dispatch_pending_messages.run(batch_size=1)

    assert dispatched == [1]
    assert messages[0].status == processing_status
    assert messages[1].status == pending_status
    assert module.SMS_MESSAGES_PENDING_GAUGE._value.get() == 1


def test_send_sms_with_failover_records_permanent_failure_metrics(monkeypatch):
    module = import_messaging_tasks(monkeypatch)

    module.SMS_PROVIDER_SEND_ATTEMPTS_TOTAL.clear()
    reset_histogram(module.SMS_PROVIDER_SEND_LATENCY_SECONDS)
    module.SMS_PROVIDER_FAILOVERS_TOTAL.clear()
    module.SMS_MESSAGE_FINAL_STATUS_TOTAL.clear()
    reset_histogram(module.SMS_PROCESSING_DURATION_SECONDS)
    module.SMS_CELERY_TASK_RETRIES_TOTAL.reset()
    module.SMS_DLQ_MESSAGES_TOTAL.reset()

    fake_now = datetime.datetime(2024, 1, 1, 13, 0, tzinfo=datetime.timezone.utc)
    created_at = fake_now - datetime.timedelta(seconds=45)

    class DummyMessage:
        def __init__(self):
            self.id = 3
            self.recipient = "+15550000"
            self.text = "Send once"
            self.initial_envelope = {"providers_effective": ["alpha"]}
            self.send_attempts = 0
            self.status = module.MessageStatus.PENDING
            self.error_message = ""
            self.tracking_id = "track-123"
            self.created_at = created_at
            self.saved = []

        def save(self, update_fields=None):
            self.saved.append(update_fields)

    message = DummyMessage()

    monkeypatch.setattr(
        module,
        "Message",
        SimpleNamespace(objects=SimpleNamespace(get=lambda pk: message)),
    )

    monkeypatch.setattr(
        module,
        "MessageAttemptLog",
        SimpleNamespace(objects=SimpleNamespace(create=lambda **kwargs: None)),
    )

    class DummyProvider:
        def __init__(self):
            self.slug = "alpha"
            self.name = "AlphaSMS"
            self.is_active = True

    provider = DummyProvider()

    class DummyProviderQuerySet(list):
        def first(self):
            return self[0] if self else None

        def order_by(self, *args, **kwargs):
            return self

    class DummyProviderManager:
        def filter(self, **kwargs):
            return DummyProviderQuerySet([provider])

    monkeypatch.setattr(
        module,
        "SmsProvider",
        SimpleNamespace(objects=DummyProviderManager()),
    )

    class DummyAdapter:
        def send_sms(self, recipient, message_text):
            return {
                "status": "failure",
                "type": "permanent",
                "reason": "Permanent issue",
                "raw_response": {"error": "perm"},
            }

    monkeypatch.setattr(module, "get_provider_adapter", lambda prov: DummyAdapter())

    perf_values = iter([70.0, 70.4])
    monkeypatch.setattr(module.time, "perf_counter", lambda: next(perf_values))
    monkeypatch.setattr(module.timezone, "now", lambda: fake_now)
    task_request = module.send_sms_with_failover.request
    monkeypatch.setattr(task_request, "retries", 0, raising=False)

    captured = {}

    def fake_plain_credentials(user, password):
        captured["credentials"] = (user, password)
        return SimpleNamespace(user=user, password=password)

    def fake_connection_parameters(*args, **kwargs):
        captured["connection_kwargs"] = kwargs
        return SimpleNamespace(**kwargs)

    class DummyChannel:
        def queue_declare(self, **kwargs):
            captured["queue_declared"] = kwargs

        def basic_publish(self, **kwargs):
            captured["published"] = kwargs

    class DummyConnection:
        def channel(self):
            return DummyChannel()

        def close(self):
            captured["closed"] = True

    def fake_blocking_connection(params):
        captured["params_obj"] = params
        return DummyConnection()

    monkeypatch.setattr(
        module,
        "pika",
        SimpleNamespace(
            PlainCredentials=fake_plain_credentials,
            ConnectionParameters=fake_connection_parameters,
            BlockingConnection=fake_blocking_connection,
        ),
    )

    monkeypatch.setattr(
        module,
        "settings",
        SimpleNamespace(
            RABBITMQ_USER="guest",
            RABBITMQ_PASS="guestpass",
            RABBITMQ_HOST="rabbitmq",
            RABBITMQ_VHOST="sms_pipeline_vhost",
        ),
    )

    set_task_globals(
        module.send_sms_with_failover,
        monkeypatch,
        Message=module.Message,
        SmsProvider=module.SmsProvider,
        MessageAttemptLog=module.MessageAttemptLog,
        get_provider_adapter=module.get_provider_adapter,
        publish_to_dlq=module.publish_to_dlq,
        timezone=module.timezone,
    )

    module.send_sms_with_failover.run(message.id)

    assert message.status == module.MessageStatus.FAILED
    assert message.error_message == "Permanent issue"
    assert module.SMS_DLQ_MESSAGES_TOTAL._value.get() == 1
    assert (
        module.SMS_PROVIDER_SEND_ATTEMPTS_TOTAL
        .labels(provider="alpha", outcome="permanent_failure")
        ._value.get()
        == 1
    )
    assert (
        module.SMS_PROVIDER_SEND_LATENCY_SECONDS.labels(provider="alpha")._sum.get()
        == pytest.approx(0.4)
    )
    assert (
        module.SMS_MESSAGE_FINAL_STATUS_TOTAL.labels(status=module.MessageStatus.FAILED)
        ._value.get()
        == 1
    )
    duration_samples = module.SMS_PROCESSING_DURATION_SECONDS.collect()[0].samples
    duration_count = next(
        sample.value
        for sample in duration_samples
        if sample.name == "sms_processing_duration_seconds_count"
    )
    duration_sum = next(
        sample.value
        for sample in duration_samples
        if sample.name == "sms_processing_duration_seconds_sum"
    )
    assert duration_count == pytest.approx(1.0)
    assert duration_sum == pytest.approx(45.0)
    assert captured["connection_kwargs"]["virtual_host"] == "sms_pipeline_vhost"
