# ======================================================================================
# tests/integration/test_api_endpoints.py
# ======================================================================================
# Purpose: Exercise the live HTTP API end to end against the running FastAPI server and a
#          real Postgres database. Covers user registration, login, and the full
#          calculation BREAD cycle (Browse, Read, Edit, Add, Delete), plus the error
#          paths the rubric asks for (invalid data, unauthorized access, not found).
#
# These tests use the `fastapi_server` fixture from conftest.py, which boots uvicorn in a
# subprocess and returns its base URL. Every request goes over real HTTP, so a pass here
# proves the wiring between routes, schemas, auth, and the database actually works.
# ======================================================================================

import uuid
import requests

from tests.conftest import create_fake_user


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def build_registration_payload() -> dict:
    """Return a registration body that satisfies UserCreate validation.

    create_fake_user() gives us name/email/username, but the register endpoint needs a
    password that passes the strength rules (upper, lower, digit, special) plus a matching
    confirm_password field.
    """
    data = create_fake_user()
    strong_password = "SecurePass123!"
    data["password"] = strong_password
    data["confirm_password"] = strong_password
    return data


def register_user(base_url: str) -> dict:
    """Register a fresh user and return the payload that was sent (for later login)."""
    payload = build_registration_payload()
    response = requests.post(f"{base_url}auth/register", json=payload)
    assert response.status_code == 201, f"Registration failed: {response.text}"
    return payload


def login_and_get_token(base_url: str, username: str, password: str) -> str:
    """Log in with JSON credentials and return the bearer access token."""
    response = requests.post(
        f"{base_url}auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ======================================================================================
# User Endpoint Tests
# ======================================================================================
def test_register_returns_created_user(fastapi_server):
    """POST /auth/register creates a user and echoes back the public fields."""
    payload = build_registration_payload()
    response = requests.post(f"{fastapi_server}auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == payload["username"]
    assert body["email"] == payload["email"]
    # The password must never come back in the response.
    assert "password" not in body
    assert body["is_active"] is True


def test_register_rejects_mismatched_passwords(fastapi_server):
    """UserCreate validation should reject a body where the passwords do not match."""
    payload = build_registration_payload()
    payload["confirm_password"] = "DifferentPass123!"
    response = requests.post(f"{fastapi_server}auth/register", json=payload)

    # Pydantic validation failures surface as 422 Unprocessable Entity.
    assert response.status_code == 422


def test_register_rejects_weak_password(fastapi_server):
    """A password with no digit/uppercase/special character should be rejected."""
    payload = build_registration_payload()
    payload["password"] = "alllowercase"
    payload["confirm_password"] = "alllowercase"
    response = requests.post(f"{fastapi_server}auth/register", json=payload)

    assert response.status_code == 422


def test_register_duplicate_username_or_email(fastapi_server):
    """Registering the same user twice should fail with a 400 from User.register."""
    payload = build_registration_payload()
    first = requests.post(f"{fastapi_server}auth/register", json=payload)
    assert first.status_code == 201

    second = requests.post(f"{fastapi_server}auth/register", json=payload)
    assert second.status_code == 400
    assert "already exists" in second.json()["detail"].lower()


def test_login_success_returns_token(fastapi_server):
    """A registered user can log in and receive a bearer access token."""
    payload = register_user(fastapi_server)
    response = requests.post(
        f"{fastapi_server}auth/login",
        json={"username": payload["username"], "password": payload["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["username"] == payload["username"]


def test_login_wrong_password_is_unauthorized(fastapi_server):
    """Logging in with the wrong password returns 401."""
    payload = register_user(fastapi_server)
    response = requests.post(
        f"{fastapi_server}auth/login",
        json={"username": payload["username"], "password": "WrongPass123!"},
    )
    assert response.status_code == 401


def test_login_unknown_user_is_unauthorized(fastapi_server):
    """Logging in as a user that does not exist returns 401."""
    response = requests.post(
        f"{fastapi_server}auth/login",
        json={"username": "nobody_here", "password": "SecurePass123!"},
    )
    assert response.status_code == 401


# ======================================================================================
# Calculation BREAD Tests (full happy-path lifecycle)
# ======================================================================================
def test_calculation_full_lifecycle(fastapi_server):
    """Add -> Read -> Browse -> Edit -> Delete against the live API for one user."""
    payload = register_user(fastapi_server)
    token = login_and_get_token(fastapi_server, payload["username"], payload["password"])
    headers = auth_header(token)

    # ---- Add (POST /calculations) ----
    create_resp = requests.post(
        f"{fastapi_server}calculations",
        json={"type": "addition", "inputs": [10, 5, 3]},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    calc_id = created["id"]
    assert created["result"] == 18
    assert created["type"] == "addition"

    # ---- Read (GET /calculations/{id}) ----
    read_resp = requests.get(f"{fastapi_server}calculations/{calc_id}", headers=headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["id"] == calc_id

    # ---- Browse (GET /calculations) ----
    browse_resp = requests.get(f"{fastapi_server}calculations", headers=headers)
    assert browse_resp.status_code == 200
    ids = [c["id"] for c in browse_resp.json()]
    assert calc_id in ids

    # ---- Edit (PUT /calculations/{id}) ----
    update_resp = requests.put(
        f"{fastapi_server}calculations/{calc_id}",
        json={"inputs": [100, 25]},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["result"] == 125

    # ---- Delete (DELETE /calculations/{id}) ----
    delete_resp = requests.delete(f"{fastapi_server}calculations/{calc_id}", headers=headers)
    assert delete_resp.status_code == 204

    # Confirm it is gone.
    gone_resp = requests.get(f"{fastapi_server}calculations/{calc_id}", headers=headers)
    assert gone_resp.status_code == 404


def test_division_calculation_result(fastapi_server):
    """Division should compute left-to-right across all inputs."""
    payload = register_user(fastapi_server)
    token = login_and_get_token(fastapi_server, payload["username"], payload["password"])

    resp = requests.post(
        f"{fastapi_server}calculations",
        json={"type": "division", "inputs": [100, 2, 5]},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["result"] == 10


# ======================================================================================
# Calculation Error / Validation Tests
# ======================================================================================
def test_create_calculation_requires_auth(fastapi_server):
    """Creating a calculation without a token returns 401."""
    resp = requests.post(
        f"{fastapi_server}calculations",
        json={"type": "addition", "inputs": [1, 2]},
    )
    assert resp.status_code == 401


def test_create_calculation_invalid_type(fastapi_server):
    """An unsupported calculation type fails schema validation with 422."""
    payload = register_user(fastapi_server)
    token = login_and_get_token(fastapi_server, payload["username"], payload["password"])

    resp = requests.post(
        f"{fastapi_server}calculations",
        json={"type": "modulus", "inputs": [10, 3]},
        headers=auth_header(token),
    )
    assert resp.status_code == 422


def test_create_calculation_too_few_inputs(fastapi_server):
    """A single input violates the min_items=2 rule and returns 422."""
    payload = register_user(fastapi_server)
    token = login_and_get_token(fastapi_server, payload["username"], payload["password"])

    resp = requests.post(
        f"{fastapi_server}calculations",
        json={"type": "addition", "inputs": [5]},
        headers=auth_header(token),
    )
    assert resp.status_code == 422


def test_create_calculation_division_by_zero(fastapi_server):
    """Division by zero is caught by schema validation and returns 422."""
    payload = register_user(fastapi_server)
    token = login_and_get_token(fastapi_server, payload["username"], payload["password"])

    resp = requests.post(
        f"{fastapi_server}calculations",
        json={"type": "division", "inputs": [10, 0]},
        headers=auth_header(token),
    )
    assert resp.status_code == 422


def test_read_nonexistent_calculation(fastapi_server):
    """Reading a valid-but-missing UUID returns 404."""
    payload = register_user(fastapi_server)
    token = login_and_get_token(fastapi_server, payload["username"], payload["password"])

    random_id = uuid.uuid4()
    resp = requests.get(f"{fastapi_server}calculations/{random_id}", headers=auth_header(token))
    assert resp.status_code == 404


def test_read_malformed_calculation_id(fastapi_server):
    """A non-UUID id string returns 400 (bad id format)."""
    payload = register_user(fastapi_server)
    token = login_and_get_token(fastapi_server, payload["username"], payload["password"])

    resp = requests.get(f"{fastapi_server}calculations/not-a-uuid", headers=auth_header(token))
    assert resp.status_code == 400
