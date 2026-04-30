from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.dependencies import get_current_username
from app.auth.jwt_utils import create_access_token
from app.auth.password import verify_password
from app.auth.schemas import MeResponse, TokenResponse
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    s = get_settings()
    if form.username != s.admin_username:
        raise HTTPException(401, "Invalid credentials")
    if not s.admin_password_hash or not verify_password(
        form.password, s.admin_password_hash
    ):
        raise HTTPException(401, "Invalid credentials")
    return TokenResponse(access_token=create_access_token(subject=form.username))


@router.get("/me", response_model=MeResponse)
async def me(username: str = Depends(get_current_username)) -> MeResponse:
    return MeResponse(username=username)
