from datetime import UTC, datetime, timedelta
from typing import Any, cast

from jose import jwt  # type: ignore[import-untyped]

from app.config import get_settings


def create_access_token(
    *,
    subject: str,
    secret: str | None = None,
    expires: timedelta | None = None,
    algorithm: str | None = None,
) -> str:
    s = get_settings()
    secret = secret or s.jwt_secret
    algorithm = algorithm or s.jwt_algorithm
    expires = expires or timedelta(minutes=s.jwt_expire_minutes)
    payload = {
        "sub": subject,
        "exp": datetime.now(UTC) + expires,
        "iat": datetime.now(UTC),
    }
    return cast(str, jwt.encode(payload, secret, algorithm=algorithm))


def decode_token(
    token: str,
    *,
    secret: str | None = None,
    algorithm: str | None = None,
) -> dict[str, Any]:
    s = get_settings()
    return cast(
        dict[str, Any],
        jwt.decode(
            token, secret or s.jwt_secret, algorithms=[algorithm or s.jwt_algorithm]
        ),
    )
