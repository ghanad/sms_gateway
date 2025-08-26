# server-b/providers/adapters.py
import requests
from .models import SmsProvider, ProviderType

class BaseSmsProvider:
    def __init__(self, provider: SmsProvider):
        self.provider = provider

    def send_sms(self, recipient: str, message: str) -> dict:
        raise NotImplementedError

class MagfaSmsProvider(BaseSmsProvider):
    def send_sms(self, recipient: str, message: str) -> dict:
        headers = {
            'Content-Type': 'application/json',
        }
        if self.provider.auth_type == 'api_key_header':
            headers[self.provider.auth_config.get('header_name', 'Authorization')] = self.provider.auth_config.get('key')

        payload = {
            'messages': [
                {
                    'recipient': recipient,
                    'content': message,
                }
            ]
        }

        try:
            response = requests.post(self.provider.send_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}

def get_provider_adapter(provider: SmsProvider) -> BaseSmsProvider:
    if provider.provider_type == ProviderType.MAGFA:
        return MagfaSmsProvider(provider)
    else:
        raise NotImplementedError(f"Provider type {provider.provider_type} is not supported.")
