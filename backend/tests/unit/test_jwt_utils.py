from datetime import timedelta

import pytest
from jose import JWTError

from app.auth.jwt_utils import create_access_token, decode_token


def test_create_decode_roundtrip():
    t = create_access_token(subject="admin", secret="s", expires=timedelta(minutes=5))
    p = decode_token(t, secret="s")
    assert p["sub"] == "admin" and "exp" in p


def test_wrong_secret_raises():
    t = create_access_token(subject="admin", secret="s", expires=timedelta(minutes=5))
    with pytest.raises(JWTError):
        decode_token(t, secret="other")


def test_expired_raises():
    t = create_access_token(subject="admin", secret="s", expires=timedelta(seconds=-1))
    with pytest.raises(JWTError):
        decode_token(t, secret="s")
