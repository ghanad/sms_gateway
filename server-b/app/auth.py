from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from .db import get_session
from .repositories import UserRepository

router = APIRouter(prefix="/api/auth")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    repo = UserRepository(session)
    user = await repo.get_by_username(payload.username)
    if user and user.password == payload.password and user.active:
        return {"access_token": "fake-token", "token_type": "bearer"}

    raise HTTPException(status_code=401, detail="Invalid credentials")
