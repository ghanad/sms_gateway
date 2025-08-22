from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas
from ..auth import get_current_user
from ..db import get_session
from ..repositories import list_messages, get_message

router = APIRouter(prefix="/messages", tags=["messages"], dependencies=[Depends(get_current_user)])


@router.get("/", response_model=schemas.MessageListResponse)
async def list_messages_endpoint(
    to: str | None = None,
    provider: str | None = None,
    status: str | None = None,
    limit: int = 10,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    items, total = await list_messages(
        session, to=to, provider=provider, status=status, limit=limit, offset=offset
    )
    return schemas.MessageListResponse(items=items, total=total)


@router.get("/{message_id}", response_model=schemas.MessageOut)
async def get_message_endpoint(message_id: int, session: AsyncSession = Depends(get_session)):
    msg = await get_message(session, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return msg
