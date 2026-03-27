"""
Shared fixtures for registry integration tests.

Uses an in-memory SQLite database and FastAPI TestClient so tests are
fast, isolated, and need no external services.
"""

import json
import hashlib
from base64 import b64encode

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import models so they register on Base.metadata
import app.models  # noqa: F401
from app.database import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# Database — in-memory SQLite, shared across all sessions via StaticPool
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_tables():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# RSA key pair for signing task results
# ---------------------------------------------------------------------------

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()

PUBLIC_KEY_B64 = b64encode(
    _public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
).decode()


def sign_output(output: dict) -> str:
    """Sign a task output dict the same way the protocol expects."""
    payload = json.dumps(output, sort_keys=True).encode()
    digest = hashlib.sha256(payload).digest()
    sig = _private_key.sign(digest, padding.PKCS1v15(), hashes.SHA256())
    return b64encode(sig).decode()


# ---------------------------------------------------------------------------
# Helper: register an agent and return (agent_id, token)
# ---------------------------------------------------------------------------

_agent_counter = 0


def register_agent(client: TestClient, *, agent_id: str | None = None, capabilities: list[str] | None = None) -> dict:
    """Register an agent and return the full response dict including token."""
    global _agent_counter
    _agent_counter += 1
    aid = agent_id or f"test-agent-{_agent_counter}"
    caps = capabilities or ["text/research", "code/generate"]

    resp = client.post("/v1/agents/register", json={
        "agent_id": aid,
        "name": f"Test Agent {_agent_counter}",
        "version": "1.0.0",
        "endpoint": "https://example.com/agent",
        "capabilities": caps,
        "public_key": PUBLIC_KEY_B64,
        "max_concurrent_tasks": 3,
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return {"agent_id": data["agent_id"], "token": data["token"], "cbt_balance": data["cbt_balance"]}


def auth_header(token: str) -> dict:
    """Return Authorization header for a given token."""
    return {"Authorization": f"Bearer {token}"}
