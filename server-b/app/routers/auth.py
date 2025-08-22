from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .. import schemas
from ..auth import create_access_token, verify_password
from ..db import get_session
from ..models import User
from ..repositories import get_user_by_username

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.LoginResponse)
async def login(data: schemas.LoginRequest, session: AsyncSession = Depends(get_session)):
    user = await get_user_by_username(session, data.username)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return schemas.LoginResponse(access_token=token)


@router.get("/admin")
async def builtin_admin_info():
    return {"username": "admin"}
