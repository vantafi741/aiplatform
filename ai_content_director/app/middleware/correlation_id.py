# Correlation-ID middleware: doc X-Correlation-ID tu header hoac tao moi, gan vao context va response header.
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import get_logger

logger = get_logger(__name__)

HEADER_CORRELATION_ID = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Gan correlation_id vao request context va response header."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = request.headers.get(HEADER_CORRELATION_ID, "").strip()
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        import structlog.contextvars
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        response = await call_next(request)
        response.headers[HEADER_CORRELATION_ID] = correlation_id
        return response
