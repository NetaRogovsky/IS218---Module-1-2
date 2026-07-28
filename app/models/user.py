# app/models/user.py
"""
User Model

Represents users in the system. Each user can own multiple calculations.

Module 12 additions on top of the original model:
- password column (stores a bcrypt hash, never plain text)
- is_active / is_verified status flags and last_login timestamp
- register() / authenticate() / verify_password() / hash_password() helpers
  so the routes can delegate all auth logic to the model.
"""

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import Column, String, Boolean, DateTime, or_
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.core.config import get_settings
from app.database import Base

settings = get_settings()


def utcnow():
    """Timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


class User(Base):
    """User model with authentication and token helpers."""

    __tablename__ = "users"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        index=True,
    )
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)

    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)

    calculations = relationship(
        "Calculation",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __init__(self, *args, **kwargs):
        # Allow passing hashed_password as an alias for the password column.
        if "hashed_password" in kwargs:
            kwargs["password"] = kwargs.pop("hashed_password")
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"<User(username={self.username}, email={self.email})>"

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------
    @property
    def hashed_password(self):
        return self.password

    def verify_password(self, plain_password: str) -> bool:
        """Verify a plain password against this user's stored hash."""
        from app.auth.jwt import verify_password
        return verify_password(plain_password, self.password)

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hash a plain password using the app's hashing utility."""
        from app.auth.jwt import get_password_hash
        return get_password_hash(password)

    # ------------------------------------------------------------------
    # Registration / authentication
    # ------------------------------------------------------------------
    @classmethod
    def register(cls, db, user_data: dict):
        """
        Create a new user from a dict of registration data.

        Raises ValueError if the username or email already exists. The caller
        is responsible for commit/rollback.
        """
        existing = db.query(cls).filter(
            or_(cls.email == user_data["email"], cls.username == user_data["username"])
        ).first()
        if existing:
            raise ValueError("Username or email already exists")

        user = cls(
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            email=user_data["email"],
            username=user_data["username"],
            password=cls.hash_password(user_data["password"]),
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        return user

    @classmethod
    def authenticate(cls, db, username_or_email: str, password: str):
        """
        Verify credentials and return a dict of tokens + the user, or None.

        Looks the user up by username OR email, checks the password, updates
        last_login, and issues access + refresh tokens.
        """
        user = db.query(cls).filter(
            or_(cls.username == username_or_email, cls.email == username_or_email)
        ).first()

        if not user or not user.verify_password(password):
            return None

        user.last_login = utcnow()
        db.flush()

        from app.auth.jwt import create_token
        from app.schemas.token import TokenType

        access_token = create_token(str(user.id), TokenType.ACCESS)
        refresh_token = create_token(str(user.id), TokenType.REFRESH)
        expires_at = utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_at": expires_at,
            "user": user,
        }

    @classmethod
    def verify_token(cls, token: str):
        """Decode an access token and return the user's UUID, or None."""
        from app.auth.jwt import decode_token
        from app.schemas.token import TokenType

        payload = decode_token(token, TokenType.ACCESS)
        if not payload:
            return None
        sub = payload.get("sub")
        if sub is None:
            return None
        try:
            return uuid.UUID(sub)
        except (ValueError, TypeError):
            return None
