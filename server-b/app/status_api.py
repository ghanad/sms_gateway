from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from .db import get_session
from .repositories import MessageRepository
from . import models, schemas

router = APIRouter()


@router.get("/messages/{tracking_id}", response_model=schemas.MessageWithEventsOut)
async def get_message(tracking_id: str, session: AsyncSession = Depends(get_session)):
    repo = MessageRepository(session)
    msg = await repo.get_message_with_events(tracking_id)
    if not msg:
        raise HTTPException(status_code=404, detail="not found")
    events = [
        schemas.EventOut(
            event_type=e.event_type.value,
            provider=e.provider,
            details=e.details,
            created_at=e.created_at,
        )
        for e in sorted(msg.events, key=lambda x: x.created_at)
    ]
    return schemas.MessageWithEventsOut(
        tracking_id=msg.tracking_id,
        status=msg.status.value,
        provider_final=msg.provider_final,
        to=msg.to,
        text=msg.text,
        events=events,
    )
