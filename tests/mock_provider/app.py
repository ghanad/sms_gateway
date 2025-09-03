from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List

app = FastAPI()

MODE = "success"
REQUEST_LOGS: List[dict] = []

class ConfigMode(BaseModel):
    mode: str

@app.post("/config")
def set_mode(cfg: ConfigMode):
    global MODE, REQUEST_LOGS
    MODE = cfg.mode
    REQUEST_LOGS = []
    return {"mode": MODE}

@app.get("/logs")
def get_logs():
    return REQUEST_LOGS

@app.post("/send")
async def send(request: Request):
    payload = await request.json()
    REQUEST_LOGS.append(payload)
    if MODE == "success":
        return {"status": 0, "messages": [{"id": 1, "status": 0}]}
    if MODE == "transient":
        raise HTTPException(status_code=503, detail="temporary failure")
    if MODE == "permanent":
        return {"status": 1, "messages": [{"id": 1, "status": 1}]}
    return {"status": 0, "messages": [{"id": 1, "status": 0}]}
