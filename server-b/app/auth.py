from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(payload: LoginRequest):
    if payload.username == "admin" and payload.password == "changeme":
        # In a real application this would return a JWT or session token.
        # Returning a static token keeps the example simple while allowing
        # the frontend to store something and treat the user as authenticated.
        return {"access_token": "fake-token", "token_type": "bearer"}

    raise HTTPException(status_code=401, detail="Invalid credentials")
