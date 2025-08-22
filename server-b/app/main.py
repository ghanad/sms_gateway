from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .config import settings
from .logging import configure_logging
from .status_api import router as status_router
from .webhooks import router as webhook_router
from .auth import router as auth_router
from .users import router as users_router

app = FastAPI(title=settings.service_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    configure_logging()


@app.get("/metrics")
async def metrics_endpoint() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(status_router)
app.include_router(webhook_router)
app.include_router(auth_router)
app.include_router(users_router)
