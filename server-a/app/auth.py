from fastapi import Header, HTTPException, Request, status
from typing import Annotated
import logging

from app.config import get_settings, ClientConfig

logger = logging.getLogger(__name__)
settings = get_settings()

class ClientContext(ClientConfig):
    api_key: str

async def get_client_context(
    request: Request,
    api_key: Annotated[str | None, Header(alias="API-Key")] = None
) -> ClientContext:
    if not api_key:
        logger.warning("Authentication failed: API-Key header missing.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "UNAUTHORIZED", "message": "API-Key header missing"}
        )

    client_config = settings.clients.get(api_key)

    if not client_config:
        logger.warning("Authentication failed: Invalid API key.", extra={"client_api_key": api_key})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "UNAUTHORIZED", "message": "Invalid API key"}
        )

    if not client_config.is_active:
        logger.warning("Authentication failed: Client is inactive.", extra={"client_api_key": api_key})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "UNAUTHORIZED", "message": "Client is inactive"}
        )

    client_context = ClientContext(api_key=api_key, **client_config.model_dump())
    request.state.client = client_context
    logger.info("Client authenticated successfully.", extra={"client_api_key": api_key, "client_name": client_context.name})
    return client_context