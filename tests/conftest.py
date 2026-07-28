# tests/conftest.py
"""
Shared pytest fixtures.

Provides:
- A test database engine/sessionmaker bound to DATABASE_URL.
- setup_test_database: drops + recreates all tables once per session.
- db_session: a per-test session.
- create_fake_user / fake_user_data: Faker-based test data.
- fastapi_server: boots app.main:app in a subprocess and waits on /health,
  yielding the base URL for HTTP-level integration tests.
"""

import socket
import subprocess
import time
import logging
from typing import Generator, Dict

import pytest
import requests
from faker import Faker
from sqlalchemy.orm import Session

from app.database import Base, get_engine, get_sessionmaker
from app.core.config import settings
import app.models  # noqa: F401  (register models on Base.metadata)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

fake = Faker()
Faker.seed(12345)

test_engine = get_engine(database_url=settings.DATABASE_URL)
TestingSessionLocal = get_sessionmaker(engine=test_engine)


def create_fake_user() -> Dict[str, str]:
    """Fake user data with a password that passes UserCreate validation."""
    return {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email": fake.unique.email(),
        "username": fake.unique.user_name(),
        "password": "SecurePass123!",
    }


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create a clean schema for the test session, drop it afterwards."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def fake_user_data() -> Dict[str, str]:
    return create_fake_user()


def find_available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def wait_for_server(url: str, timeout: int = 30) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            if requests.get(url).status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            time.sleep(1)
    return False


@pytest.fixture(scope="session")
def fastapi_server():
    """Start uvicorn for app.main:app and yield its base URL."""
    port = 8000
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            port = find_available_port()
    base_url = f"http://127.0.0.1:{port}/"

    process = subprocess.Popen(
        ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if not wait_for_server(f"{base_url}health", timeout=30):
        err = process.stderr.read()
        process.terminate()
        raise RuntimeError(f"Test server failed to start: {err}")

    yield base_url

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
