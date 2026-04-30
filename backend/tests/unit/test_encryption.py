import pytest
from cryptography.fernet import InvalidToken

from app.db.encryption import EncryptedString, decrypt_value, encrypt_value, generate_key


def test_generate_key_returns_44_char_urlsafe_b64():
    key = generate_key()
    assert isinstance(key, str)
    assert len(key) == 44


def test_encrypt_then_decrypt_roundtrip():
    key = generate_key()
    cipher = encrypt_value("secret-app-secret", key=key)
    assert cipher != "secret-app-secret"
    assert decrypt_value(cipher, key=key) == "secret-app-secret"


def test_decrypt_wrong_key_raises():
    cipher = encrypt_value("abc", key=generate_key())
    with pytest.raises(InvalidToken):
        decrypt_value(cipher, key=generate_key())


def test_encrypted_string_column_type_processes_bind_and_result():
    key = generate_key()
    col = EncryptedString(key=key)
    bound = col.process_bind_param("hello", dialect=None)
    assert bound != "hello"
    assert col.process_result_value(bound, dialect=None) == "hello"


def test_encrypted_string_handles_none():
    col = EncryptedString(key=generate_key())
    assert col.process_bind_param(None, dialect=None) is None
    assert col.process_result_value(None, dialect=None) is None
