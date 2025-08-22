from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from . import models


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_message(self, data: models.Message) -> None:
        self.session.add(data)
        await self.session.commit()

    async def update_message_status(self, tracking_id: str, status: models.MessageStatus, provider_final: str | None = None) -> None:
        await self.session.execute(
            update(models.Message)
            .where(models.Message.tracking_id == tracking_id)
            .values(status=status, provider_final=provider_final)
        )
        await self.session.commit()

    async def add_event(
        self, tracking_id: str, event_type: models.EventType, provider: str | None = None, details: dict | None = None
    ) -> None:
        evt = models.MessageEvent(
            tracking_id=tracking_id, event_type=event_type, provider=provider, details=details or {}
        )
        self.session.add(evt)
        await self.session.commit()

    async def get_message_with_events(self, tracking_id: str) -> models.Message | None:
        result = await self.session.execute(
            select(models.Message).where(models.Message.tracking_id == tracking_id).options(
                selectinload(models.Message.events)
            )
        )
        return result.scalars().first()
