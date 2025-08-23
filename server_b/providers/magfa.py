import base64
from typing import Any, Dict
import requests
from .base import ProviderInterface, SendResult
from .registry import register

MAGFA_TYPE = 'magfa'

class MagfaProvider(ProviderInterface):
    def send(self, message: Dict[str, Any], cfg: Dict[str, Any]) -> SendResult:
        url = cfg['base_url'].rstrip('/') + cfg['endpoint_send']
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Cache-Control': 'no-cache',
        }
        headers.update(cfg.get('extra_headers') or {})
        if cfg.get('basic_username'):
            auth_str = f"{cfg['basic_username']}/{cfg.get('domain','')}:{cfg['basic_password']}"
            headers['Authorization'] = 'Basic ' + base64.b64encode(auth_str.encode()).decode()
        payload = {
            'senders': [message['sender']] * len(message['recipients']),
            'recipients': message['recipients'],
            'messages': [message['message']] * len(message['recipients']),
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=cfg.get('timeout_ms',5000)/1000)
            retryable = resp.status_code in (408,429) or resp.status_code >=500
            data = resp.json() if resp.content else {}
            ok = resp.ok
            provider_msg_id = data.get('id') if isinstance(data, dict) else None
            return SendResult(ok=ok, http_status=resp.status_code, provider_message_id=provider_msg_id, retryable=retryable, raw=data, error=None if ok else str(data))
        except Exception as exc:
            return SendResult(ok=False, http_status=None, retryable=True, error=str(exc))

    def get_balance(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        url = cfg['base_url'].rstrip('/') + '/api/http/sms/v2/getBalance'
        try:
            resp = requests.get(url, auth=(cfg['basic_username'], cfg['basic_password']))
            data = resp.json()
            bal = data.get('balance') or data.get('credit')
            return {'ok': True, 'balance': bal, 'raw': data}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

register(MAGFA_TYPE, MagfaProvider)
