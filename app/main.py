# app/main.py
"""
FastAPI application: user auth + calculation BREAD.

Endpoints:
- /health                      simple readiness check (used by tests)
- POST /auth/register          create a user (UserCreate)
- POST /auth/login             log in with JSON, returns tokens (TokenResponse)
- POST /auth/token             log in with form data (for Swagger Authorize)
- GET  /calculations           Browse the current user's calculations
- GET  /calculations/{id}      Read one
- POST /calculations           Add one
- PUT  /calculations/{id}      Edit one
- DELETE /calculations/{id}    Delete one

Calculation routes are protected: they require a valid bearer token, and each
user only ever sees their own calculations.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import List
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.database import Base, engine, get_db
from app.models.calculation import Calculation
from app.models.user import User
from app.schemas.calculation import CalculationBase, CalculationResponse, CalculationUpdate
from app.schemas.token import TokenResponse
from app.schemas.user import UserCreate, UserResponse, UserLogin


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup so a fresh database is ready to use.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Calculations API",
    description="User authentication and calculation CRUD.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
def read_health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# User: register + login
# ---------------------------------------------------------------------------
@app.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
)
def register(user_create: UserCreate, db: Session = Depends(get_db)):
    """Register a new user. Excludes confirm_password before persisting."""
    user_data = user_create.model_dump(exclude={"confirm_password"})
    try:
        user = User.register(db, user_data)
        db.commit()
        db.refresh(user)
        return user
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login_json(user_login: UserLogin, db: Session = Depends(get_db)):
    """Log in with a JSON body and receive access + refresh tokens."""
    auth_result = User.authenticate(db, user_login.username, user_login.password)
    if auth_result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    db.commit()  # persist last_login

    user = auth_result["user"]
    expires_at = auth_result.get("expires_at")
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    elif not expires_at:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    return TokenResponse(
        access_token=auth_result["access_token"],
        refresh_token=auth_result["refresh_token"],
        token_type="bearer",
        expires_at=expires_at,
        user_id=user.id,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
    )


@app.post("/auth/token", tags=["auth"])
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Form-based login so the Swagger UI Authorize button works."""
    auth_result = User.authenticate(db, form_data.username, form_data.password)
    if auth_result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    db.commit()
    return {"access_token": auth_result["access_token"], "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Calculations: BREAD
# ---------------------------------------------------------------------------
def _parse_calc_id(calc_id: str) -> UUID:
    try:
        return UUID(calc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid calculation id format.")


# Add
@app.post(
    "/calculations",
    response_model=CalculationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["calculations"],
)
def create_calculation(
    calculation_data: CalculationBase,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Compute and store a calculation owned by the current user."""
    try:
        new_calculation = Calculation.create(
            calculation_type=calculation_data.type,
            user_id=current_user.id,
            inputs=calculation_data.inputs,
        )
        new_calculation.result = new_calculation.get_result()
        db.add(new_calculation)
        db.commit()
        db.refresh(new_calculation)
        return new_calculation
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Browse
@app.get("/calculations", response_model=List[CalculationResponse], tags=["calculations"])
def list_calculations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return db.query(Calculation).filter(Calculation.user_id == current_user.id).all()


# Read
@app.get("/calculations/{calc_id}", response_model=CalculationResponse, tags=["calculations"])
def get_calculation(
    calc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    calc_uuid = _parse_calc_id(calc_id)
    calculation = db.query(Calculation).filter(
        Calculation.id == calc_uuid,
        Calculation.user_id == current_user.id,
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found.")
    return calculation


# Edit
@app.put("/calculations/{calc_id}", response_model=CalculationResponse, tags=["calculations"])
def update_calculation(
    calc_id: str,
    calculation_update: CalculationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    calc_uuid = _parse_calc_id(calc_id)
    calculation = db.query(Calculation).filter(
        Calculation.id == calc_uuid,
        Calculation.user_id == current_user.id,
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found.")

    if calculation_update.inputs is not None:
        calculation.inputs = calculation_update.inputs
        calculation.result = calculation.get_result()
    calculation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(calculation)
    return calculation


# Delete
@app.delete(
    "/calculations/{calc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["calculations"],
)
def delete_calculation(
    calc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    calc_uuid = _parse_calc_id(calc_id)
    calculation = db.query(Calculation).filter(
        Calculation.id == calc_uuid,
        Calculation.user_id == current_user.id,
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found.")
    db.delete(calculation)
    db.commit()
    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="info")
