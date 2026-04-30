from fastapi import APIRouter

from app.accounts.routes import router as accounts_router
from app.auth.routes import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(accounts_router)
