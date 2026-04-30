from app.auth.password import hash_password, verify_password


def test_hash_password_produces_bcrypt_hash():
    h = hash_password("hunter2")
    assert h.startswith("$2b$") and h != "hunter2"


def test_verify_password_accepts_correct():
    assert verify_password("hunter2", hash_password("hunter2")) is True


def test_verify_password_rejects_wrong():
    assert verify_password("wrong", hash_password("hunter2")) is False
