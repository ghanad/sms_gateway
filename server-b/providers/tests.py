from django.core.exceptions import ValidationError
from django.test import TestCase
from providers.models import SmsProvider, AuthType


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
