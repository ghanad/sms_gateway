from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from .db import get_session
from .repositories import UserRepository
from . import schemas

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[schemas.UserOut])
async def list_users(session: AsyncSession = Depends(get_session)):
    repo = UserRepository(session)
    return await repo.list_users()


@router.post("", response_model=schemas.UserOut)
async def create_user(payload: schemas.UserCreate, session: AsyncSession = Depends(get_session)):
    repo = UserRepository(session)
    return await repo.create_user(**payload.model_dump())


@router.put("/{user_id}", response_model=schemas.UserOut)
async def update_user(user_id: int, payload: schemas.UserUpdate, session: AsyncSession = Depends(get_session)):
    repo = UserRepository(session)
    user = await repo.update_user(user_id, payload.model_dump(exclude_unset=True))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}")
async def delete_user(user_id: int, session: AsyncSession = Depends(get_session)):
    repo = UserRepository(session)
    deleted = await repo.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@router.post("/{user_id}/activate", response_model=schemas.UserOut)
async def activate_user(user_id: int, session: AsyncSession = Depends(get_session)):
    repo = UserRepository(session)
    user = await repo.update_user(user_id, {"active": True})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/{user_id}/deactivate", response_model=schemas.UserOut)
async def deactivate_user(user_id: int, session: AsyncSession = Depends(get_session)):
    repo = UserRepository(session)
    user = await repo.update_user(user_id, {"active": False})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/{username}/password")
async def change_password(username: str, payload: schemas.PasswordChange, session: AsyncSession = Depends(get_session)):
    repo = UserRepository(session)
    user = await repo.change_password(username, payload.password)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}
