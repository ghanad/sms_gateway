from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from .db import get_session
from .repositories import MessageRepository
from . import models

router = APIRouter()


class DeliveryUpdate(BaseModel):
    tracking_id: str


@router.post("/webhook/{provider}")
async def handle_webhook(provider: str, payload: DeliveryUpdate, session: AsyncSession = Depends(get_session)):
    repo = MessageRepository(session)
    await repo.update_message_status(payload.tracking_id, models.MessageStatus.DELIVERED, provider)
    await repo.add_event(payload.tracking_id, models.EventType.DELIVERED, provider, {})
    return {"status": "ok"}
