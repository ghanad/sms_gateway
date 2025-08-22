from . import policy_engine, models, metrics, utils
from .repositories import MessageRepository
from .provider_registry import ProviderRegistry
from .providers.base import SendStatus
from .schemas import MessageIn


async def process_message(
    message: MessageIn,
    repo: MessageRepository,
    registry: ProviderRegistry,
    strategy: str,
) -> dict:
    providers = policy_engine.select_providers(
        providers=message.providers,
        policy=message.policy,
        registry=registry,
        created_at=message.created_at,
        ttl_seconds=message.ttl_seconds,
        send_attempts=message.send_attempts,
        strategy=strategy,
    )

    for name in providers:
        provider = registry.get(name)
        await repo.add_event(message.tracking_id, models.EventType.PROCESSING, name)
        result = await provider.send_sms(message.to, message.text)
        if result.status == SendStatus.SUCCESS:
            await repo.update_message_status(message.tracking_id, models.MessageStatus.SENT, name)
            await repo.add_event(message.tracking_id, models.EventType.SENT, name, result.details)
            metrics.sms_sent_total.inc()
            return {"status": "sent"}
        if result.status == SendStatus.TEMP_FAILURE:
            await repo.add_event(message.tracking_id, models.EventType.FAILED, name, result.details)
            await repo.add_event(
                message.tracking_id,
                models.EventType.RETRY_SCHEDULED,
                name,
                {"attempt": message.send_attempts + 1},
            )
            metrics.sms_retry_scheduled_total.inc()
            delay = utils.compute_backoff(message.send_attempts + 1)
            return {"status": "retry", "delay": delay}
        await repo.add_event(message.tracking_id, models.EventType.FAILED, name, result.details)
        metrics.sms_failed_total.inc()
    await repo.update_message_status(message.tracking_id, models.MessageStatus.FAILED)
    return {"status": "failed"}
