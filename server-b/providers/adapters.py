# server-b/providers/adapters.py
from datetime import datetime
from decimal import Decimal, InvalidOperation

import logging
import requests

from .models import SmsProvider, ProviderType

logger = logging.getLogger(__name__)

class BaseSmsProvider:
    def __init__(self, provider: SmsProvider):
        self.provider = provider

    @property
    def supports_status_check(self) -> bool:
        return False

    def send_sms(self, recipient: str, message: str) -> dict:
        raise NotImplementedError

    def get_balance(self) -> dict:
        raise NotImplementedError

    def check_status(self, message_ids: list) -> dict:
        raise NotImplementedError

class MagfaSmsProvider(BaseSmsProvider):
    @property
    def supports_status_check(self) -> bool:
        return True

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
        tariff = message_info.get('tariff')
        parts = message_info.get('parts')
        total_cost = None
        if tariff is not None and parts is not None:
            try:
                total_cost = Decimal(str(tariff)) * Decimal(str(parts))
            except (InvalidOperation, TypeError):
                total_cost = None
            else:
                # Keep the cost in Iranian rials (IRR) so downstream logic persists a normalised value.
                if total_cost == total_cost.to_integral_value():
                    total_cost = int(total_cost)
                else:
                    total_cost = float(total_cost)

        if status_code == 0:
            return {
                'status': 'success',
                'message_id': provider_message_id,
                'raw_response': data,
                'cost': total_cost,
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


    def check_status(self, message_ids: list) -> dict:
        logger.info(f"Checking status for {len(message_ids)} message IDs.")
        if not message_ids:
            logger.warning("No message IDs provided for status check.")
            return {}

        headers = {
            'accept': 'application/json',
        }
        auth = None
        if self.provider.auth_type == 'basic':
            username = f"{self.provider.auth_config.get('username')}/{self.provider.auth_config.get('domain')}"
            password = self.provider.auth_config.get('password')
            auth = (username, password)

        base_url = self.provider.send_url.rsplit('/', 1)[0]
        results = {}
        status_map = {
            1: 'DELIVERED', 8: 'DELIVERED',
            2: 'FAILED', 16: 'FAILED',
        }

        # Iterating and sending one request per message ID
        for mid in message_ids:
            statuses_url = f"{base_url}/statuses/{mid}"
            logger.debug(f"Requesting status for mid {mid} from URL: {statuses_url}")
            
            try:
                response = requests.get(
                    statuses_url,
                    headers=headers,
                    auth=auth,
                    timeout=self.provider.timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
                logger.debug(f"Received status response for mid {mid}: {data}")
            except (requests.exceptions.Timeout, requests.exceptions.RequestException, ValueError) as e:
                logger.error(f"Error checking status for message ID {mid}: {e}")
                continue  # Continue to the next message ID

            # The response for a single status check is different.
            # Based on MAGFA.md, it should be like: {"status": 0, "dlrs": [...]}
            # but the response for a single ID might be simpler. Let's assume it's still in `dlrs`.
            for entry in data.get('dlrs', []):
                entry_mid = entry.get('mid')
                if str(entry_mid) != str(mid):
                    continue

                status_code = entry.get('status')
                mapped_status = status_map.get(status_code)
                if mapped_status is None:
                    logger.warning(f"Skipping entry for mid {mid} due to unmapped status: {entry}")
                    continue

                delivered_at = entry.get('date')
                if isinstance(delivered_at, str):
                    try:
                        delivered_at = datetime.strptime(delivered_at, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        delivered_at = None

                results[str(mid)] = {
                    'status': mapped_status,
                    'delivered_at': delivered_at,
                    'provider_status': status_code,
                }
                # Since we found the status for this mid, we can break the inner loop
                break

        logger.info(f"Status check completed. Found results for {len(results)} IDs. Results: {results}")
        return results

def get_provider_adapter(provider: SmsProvider) -> BaseSmsProvider:
    if provider.provider_type == ProviderType.MAGFA:
        return MagfaSmsProvider(provider)
    else:
        raise NotImplementedError(f"Provider type {provider.provider_type} is not supported.")
