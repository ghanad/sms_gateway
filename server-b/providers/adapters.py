# server-b/providers/adapters.py
import requests
from .models import SmsProvider, ProviderType

class BaseSmsProvider:
    def __init__(self, provider: SmsProvider):
        self.provider = provider

    def send_sms(self, recipient: str, message: str) -> dict:
        raise NotImplementedError

    def get_balance(self) -> dict:
        raise NotImplementedError

class MagfaSmsProvider(BaseSmsProvider):
    def send_sms(self, recipient: str, message: str) -> dict:
        headers = {
            'Content-Type': 'application/json',
            'accept': 'application/json',
        }
        auth = None
        if self.provider.auth_type == 'basic':
            username = f"{self.provider.auth_config.get('username')}/{self.provider.auth_config.get('domain')}"
            password = self.provider.auth_config.get('password')  # In a real app, get this from env
            auth = (username, password)

        payload = {
            'senders': [self.provider.default_sender],
            'messages': [message],
            'recipients': [recipient],
        }

        try:
            response = requests.post(
                self.provider.send_url,
                headers=headers,
                auth=auth,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout:
            return {
                'status': 'failure',
                'type': 'transient',
                'reason': 'Request timed out',
                'raw_response': None,
            }
        except requests.exceptions.RequestException as e:
            return {
                'status': 'failure',
                'type': 'transient',
                'reason': str(e),
                'raw_response': None,
            }
        except ValueError:
            return {
                'status': 'failure',
                'type': 'permanent',
                'reason': 'Invalid JSON response',
                'raw_response': None,
            }

        status_code = data.get('status')
        message_info = (data.get('messages') or [{}])[0]
        provider_message_id = message_info.get('id')

        if status_code == 0:
            return {
                'status': 'success',
                'message_id': provider_message_id,
                'raw_response': data,
            }
        if status_code in (1, 27, 33):
            reason = f"Permanent failure (Code {status_code})"
            return {
                'status': 'failure',
                'type': 'permanent',
                'reason': reason,
                'raw_response': data,
            }
        if status_code in (14, 15):
            reason = f"Transient failure (Code {status_code})"
            return {
                'status': 'failure',
                'type': 'transient',
                'reason': reason,
                'raw_response': data,
            }

        reason = f"Unknown error (Code {status_code})"
        return {
            'status': 'failure',
            'type': 'permanent',
            'reason': reason,
            'raw_response': data,
        }

    def get_balance(self) -> dict:
        headers = {
            'accept': 'application/json',
        }
        auth = None
        if self.provider.auth_type == 'basic':
            username = f"{self.provider.auth_config.get('username')}/{self.provider.auth_config.get('domain')}"
            password = self.provider.auth_config.get('password') # In a real app, get this from env
            auth = (username, password)

        try:
            response = requests.get(self.provider.balance_url, headers=headers, auth=auth, timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}

def get_provider_adapter(provider: SmsProvider) -> BaseSmsProvider:
    if provider.provider_type == ProviderType.MAGFA:
        return MagfaSmsProvider(provider)
    else:
        raise NotImplementedError(f"Provider type {provider.provider_type} is not supported.")
