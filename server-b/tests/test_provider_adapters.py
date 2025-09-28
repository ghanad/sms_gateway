import datetime
import os
import sys
from types import SimpleNamespace

import django
from django.apps import apps


TEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if TEST_ROOT not in sys.path:
    sys.path.insert(0, TEST_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sms_gateway_project.settings")

if not apps.ready:
    django.setup()


def test_magfa_check_status_converts_dates_to_naive_datetimes(monkeypatch):
    from providers.adapters import MagfaSmsProvider

    provider = SimpleNamespace(
        auth_type="basic",
        auth_config={"username": "user", "domain": "example", "password": "secret"},
        default_sender="ExampleSender",
        send_url="https://api.example.com/messages/send",
        timeout_seconds=30,
    )

    class DummyResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "dlrs": [
                    {
                        "mid": 123,
                        "status": 1,
                        "date": "2024-03-15 10:03:00",
                    }
                ]
            }

    captured = {}

    def fake_get(url, headers=None, auth=None, timeout=None):
        captured["url"] = url
        captured["auth"] = auth
        captured["timeout"] = timeout
        return DummyResponse()

    monkeypatch.setattr("providers.adapters.requests.get", fake_get)

    adapter = MagfaSmsProvider(provider)
    result = adapter.check_status([123])

    assert captured["url"].endswith("/statuses/123")
    assert captured["timeout"] == provider.timeout_seconds
    assert captured["auth"] == ("user/example", "secret")

    assert "123" in result
    entry = result["123"]
    delivered_at = entry["delivered_at"]

    assert isinstance(delivered_at, datetime.datetime)
    assert delivered_at.tzinfo is None
    assert delivered_at == datetime.datetime(2024, 3, 15, 10, 3, 0)
    assert entry["status"] == "DELIVERED"
