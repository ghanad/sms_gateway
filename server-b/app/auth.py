from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(payload: LoginRequest):
    if payload.username == "admin" and payload.password == "changeme":
        return {"message": "Login successful"}
    raise HTTPException(status_code=401, detail="Invalid credentials")
