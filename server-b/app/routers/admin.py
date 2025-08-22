from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas
from ..auth import require_role
from ..db import get_session
from ..repositories import providers_summary, summary

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])


@router.get("/providers", response_model=schemas.ProvidersResponse)
async def providers_summary_endpoint(session: AsyncSession = Depends(get_session)):
    data = await providers_summary(session)
    providers = [schemas.ProviderInfo(name=name, message_count=count) for name, count in data]
    return schemas.ProvidersResponse(providers=providers)


@router.get("/summary", response_model=schemas.SummaryResponse)
async def summary_endpoint(session: AsyncSession = Depends(get_session)):
    msg_count, user_count = await summary(session)
    return schemas.SummaryResponse(total_messages=msg_count, total_users=user_count)
