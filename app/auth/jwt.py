# app/auth/jwt.py
"""
Authentication utilities: password hashing and JWT token handling.

This module centralizes the security primitives for the app:
- Password hashing and verification using bcrypt (via passlib).
- JWT access/refresh token creation and decoding (via python-jose).

Keeping these in one place means the models and routes never touch raw
crypto directly; they call these helpers instead.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings
from app.schemas.token import TokenType

# bcrypt is the industry-standard password hashing algorithm. passlib wraps it
# with a clean interface and handles salting automatically.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hash a plain-text password for safe storage."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain-text password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_token(subject: str, token_type: TokenType) -> str:
    """
    Create a signed JWT for the given subject (usually the user id).

    Access tokens are short-lived; refresh tokens last longer. The token type
    is embedded in the payload so it can be checked on decode.
    """
    now = datetime.now(timezone.utc)
    if token_type == TokenType.ACCESS:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        secret = settings.JWT_SECRET_KEY
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        secret = settings.JWT_REFRESH_SECRET_KEY

    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "type": token_type.value,
    }
    return jwt.encode(payload, secret, algorithm=settings.ALGORITHM)


def decode_token(token: str, token_type: TokenType = TokenType.ACCESS) -> Optional[dict]:
    """
    Decode and verify a JWT. Returns the payload dict, or None if invalid.

    Uses the matching secret for the token type so an access token can't be
    verified with the refresh secret and vice versa.
    """
    secret = (
        settings.JWT_SECRET_KEY
        if token_type == TokenType.ACCESS
        else settings.JWT_REFRESH_SECRET_KEY
    )
    try:
        return jwt.decode(token, secret, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
