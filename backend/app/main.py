from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings, validate_security_settings


def _cors_origins(raw: str) -> list[str]:
    raw = raw.strip()
    if raw == "*" or not raw:
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 启动时校验安全配置（弱 JWT/缺密钥等），不安全则直接拒绝启动
    validate_security_settings(get_settings())
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="WeChat Batch Rewriter", version="0.1.0", lifespan=lifespan
    )
    origins = _cors_origins(get_settings().cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        # allow_origins=["*"] 与 allow_credentials=True 同用会把 Origin 原样回显，
        # 等于对所有站点放行凭证，存在 CSRF 风险。前端用 Bearer，凭证非必需，
        # 因此通配场景下关闭凭证回显；配置了具体来源时才允许携带凭证。
        allow_credentials=origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
