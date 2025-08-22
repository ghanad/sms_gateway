from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas
from ..auth import require_role
from ..db import get_session
from ..repositories import (
    create_user,
    list_users,
    get_user,
    delete_user,
    add_user_provider,
)


def _to_user_out(u) -> schemas.UserOut:
    return schemas.UserOut(
        id=u.id, username=u.username, role=u.role, providers=[p.provider for p in u.providers]
    )

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_role("admin"))])


@router.get("/", response_model=list[schemas.UserOut])
async def list_users_endpoint(session: AsyncSession = Depends(get_session)):
    users = await list_users(session)
    return [_to_user_out(u) for u in users]


@router.post("/", response_model=schemas.UserOut, status_code=201)
async def create_user_endpoint(data: schemas.UserIn, session: AsyncSession = Depends(get_session)):
    user = await create_user(session, data.username, data.password, data.role)
    return _to_user_out(user)


@router.get("/{user_id}", response_model=schemas.UserOut)
async def get_user_endpoint(user_id: int, session: AsyncSession = Depends(get_session)):
    user = await get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_user_out(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user_endpoint(user_id: int, session: AsyncSession = Depends(get_session)):
    await delete_user(session, user_id)


@router.post("/{user_id}/associations", response_model=schemas.UserOut)
async def add_association_endpoint(
    user_id: int, data: schemas.AssociationIn, session: AsyncSession = Depends(get_session)
):
    user = await get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = await add_user_provider(session, user, data.provider)
    return _to_user_out(user)
