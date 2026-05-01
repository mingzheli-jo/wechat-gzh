from fastapi import APIRouter

from app.accounts.routes import router as accounts_router
from app.ai_providers.routes import router as ai_providers_router
from app.auth.routes import router as auth_router
from app.drafts.routes import router as drafts_router
from app.library.routes import router as library_router

api_router = APIRouter()


@api_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


api_router.include_router(auth_router)
api_router.include_router(accounts_router)
api_router.include_router(library_router)
api_router.include_router(ai_providers_router)
api_router.include_router(drafts_router)
