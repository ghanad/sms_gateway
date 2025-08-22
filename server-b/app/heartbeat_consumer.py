import json
from .metrics import server_a_heartbeat_last_ts
from .logging import get_logger

logger = get_logger(__name__)


def process_heartbeat(body: bytes) -> None:
    data = json.loads(body)
    server_a_heartbeat_last_ts.set_to_current_time()
    logger.info("heartbeat", extra=data)
