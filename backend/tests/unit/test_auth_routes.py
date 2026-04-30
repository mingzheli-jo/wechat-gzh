import pytest
from fastapi.testclient import TestClient

from app.auth.password import hash_password
from app.config import get_settings
from app.main import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password("hunter2"))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_login_correct_returns_token(client):
    r = client.post(
        "/api/auth/login", data={"username": "admin", "password": "hunter2"}
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_wrong_returns_401(client):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "WRONG"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_username_with_token(client):
    login = client.post(
        "/api/auth/login", data={"username": "admin", "password": "hunter2"}
    )
    token = login.json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"username": "admin"}
