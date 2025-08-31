from django.core.exceptions import ValidationError
from django.test import TestCase
from unittest.mock import patch
import requests

from providers.adapters import MagfaSmsProvider
from providers.models import SmsProvider, AuthType, ProviderType


class SmsProviderModelTests(TestCase):
    def _base_provider_kwargs(self, **extra):
        data = {
            "name": "Provider",
            "slug": "provider",
            "send_url": "http://example.com/send",
            "balance_url": "http://example.com/balance",
            "default_sender": "100",
        }
        data.update(extra)
        return data

    def test_basic_auth_requires_password(self):
        provider = SmsProvider(**self._base_provider_kwargs(
            auth_type=AuthType.BASIC,
            auth_config={"username": "u"},
        ))
        with self.assertRaises(ValidationError) as ctx:
            provider.full_clean()
        self.assertIn("password", ctx.exception.message_dict["auth_config"][0])

    def test_api_key_header_requires_key(self):
        provider = SmsProvider(**self._base_provider_kwargs(
            auth_type=AuthType.API_KEY_HEADER,
            auth_config={},
        ))
        with self.assertRaises(ValidationError) as ctx:
            provider.full_clean()
        self.assertIn("Missing: key", ctx.exception.message_dict["auth_config"][0])

    def test_str_returns_name(self):
        provider = SmsProvider(**self._base_provider_kwargs(auth_type=AuthType.NONE))
        # full_clean should pass without raising
        provider.full_clean()
        self.assertEqual(str(provider), "Provider")


class MagfaSmsProviderAdapterTests(TestCase):
    def setUp(self):
        self.provider = SmsProvider.objects.create(
            name="Magfa",
            slug="magfa",
            send_url="http://example.com/send",
            balance_url="http://example.com/bal",
            default_sender="100",
            auth_type=AuthType.NONE,
            provider_type=ProviderType.MAGFA,
        )
        self.adapter = MagfaSmsProvider(self.provider)

    @patch("providers.adapters.requests.post")
    def test_success(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {
            "status": 0,
            "messages": [{"id": "1", "status": 0}],
        }

        result = self.adapter.send_sms("123", "hi")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["message_id"], "1")

    @patch("providers.adapters.requests.post")
    def test_permanent_failure(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"status": 27}

        result = self.adapter.send_sms("123", "hi")
        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["type"], "permanent")
        self.assertIn("27", result["reason"])

    @patch("providers.adapters.requests.post")
    def test_transient_failure(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"status": 15}

        result = self.adapter.send_sms("123", "hi")
        self.assertEqual(result["type"], "transient")

    @patch("providers.adapters.requests.post", side_effect=requests.exceptions.Timeout())
    def test_timeout(self, mock_post):
        result = self.adapter.send_sms("123", "hi")
        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["type"], "transient")
