# app/schemas/token.py
"""
Token-related Pydantic schemas.

TokenType distinguishes access tokens (short-lived, sent with every request)
from refresh tokens (longer-lived, used to obtain new access tokens).

TokenResponse is the shape returned by the login endpoint. It bundles the
tokens together with basic user info so the client doesn't need a second call.
"""

from enum import Enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict


class TokenType(str, Enum):
    """The two kinds of JWT this app issues."""
    ACCESS = "access"
    REFRESH = "refresh"


class TokenResponse(BaseModel):
    """Response body returned after a successful login."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user_id: UUID
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    is_active: bool
    is_verified: bool

    model_config = ConfigDict(from_attributes=True)
