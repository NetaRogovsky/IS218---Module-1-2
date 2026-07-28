# app/schemas/user.py
"""
User Pydantic Schemas

These schemas define the data contracts for user-related API operations:
- UserBase: shared fields (name, email, username).
- UserCreate: registration input, with password + confirm_password and
  strength/match validation.
- UserResponse: the public shape returned to clients (never includes the
  password).
- UserLogin: login input.

The password rules here satisfy CLO13 (secure auth): the plain password never
leaves this boundary in a response, and creation enforces a strong password.
"""

from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator


class UserBase(BaseModel):
    """Fields common to user creation and display."""
    first_name: str = Field(min_length=1, max_length=50, examples=["John"])
    last_name: str = Field(min_length=1, max_length=50, examples=["Doe"])
    email: EmailStr = Field(examples=["john.doe@example.com"])
    username: str = Field(min_length=3, max_length=50, examples=["johndoe"])

    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserBase):
    """Registration input, with password confirmation and strength checks."""
    password: str = Field(min_length=8, max_length=128, examples=["SecurePass123!"])
    confirm_password: str = Field(min_length=8, max_length=128, examples=["SecurePass123!"])

    @model_validator(mode="after")
    def verify_password_match(self) -> "UserCreate":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

    @model_validator(mode="after")
    def validate_password_strength(self) -> "UserCreate":
        password = self.password
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            raise ValueError("Password must contain at least one special character")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "username": "johndoe",
                "password": "SecurePass123!",
                "confirm_password": "SecurePass123!",
            }
        }
    )


class UserResponse(BaseModel):
    """Public user data returned by the API. No password field, ever."""
    id: UUID
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    """Login input: username (or email) plus password."""
    username: str = Field(..., min_length=3, max_length=50, examples=["johndoe"])
    password: str = Field(..., min_length=8, max_length=128, examples=["SecurePass123!"])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"username": "johndoe", "password": "SecurePass123!"}
        }
    )
