from app.auth.password import verify_password
from app.scripts.init_admin import build_password_hash


def test_build_password_hash_is_verifiable():
    assert verify_password("hunter2", build_password_hash("hunter2"))
