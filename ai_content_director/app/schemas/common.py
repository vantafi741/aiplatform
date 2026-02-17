"""Common schemas (errors, messages)."""
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Optional error code")
    extra: Optional[Dict[str, Any]] = Field(None, description="Extra context")


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str = Field(..., description="Message text")
