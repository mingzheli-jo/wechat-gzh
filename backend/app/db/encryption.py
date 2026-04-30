from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import String, TypeDecorator

from app.config import get_settings


def generate_key() -> str:
    return Fernet.generate_key().decode("utf-8")


def _resolve_key(key: str | None) -> bytes:
    chosen = key or get_settings().encryption_key
    if not chosen:
        raise RuntimeError("ENCRYPTION_KEY not configured")
    return chosen.encode("utf-8")


def encrypt_value(plaintext: str, *, key: str | None = None) -> str:
    return Fernet(_resolve_key(key)).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(token: str, *, key: str | None = None) -> str:
    return Fernet(_resolve_key(key)).decrypt(token.encode("utf-8")).decode("utf-8")


class EncryptedString(TypeDecorator[str]):
    impl = String
    cache_ok = True

    def __init__(self, *, key: str | None = None, length: int = 1024) -> None:
        super().__init__(length=length)
        self._key = key

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        return None if value is None else encrypt_value(value, key=self._key)

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        return None if value is None else decrypt_value(value, key=self._key)
