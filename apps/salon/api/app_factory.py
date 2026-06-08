"""
Composition root do produto salão.
Registra middleware, exception handlers e routers com prefixo /api/v1 consistente.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from packages.auth_core.config import settings
from packages.auth_core.exceptions import (
    BusinessLogicError,
    DoubleBookingError,
    FlowIAError,
    ResourceNotFoundError,
)
from packages.auth_core.limiter import limiter

_APP_START_TIME = time.monotonic()
_APP_VERSION = "1.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from packages.engine.checkpointer import init_checkpointer_async, shutdown_checkpointer_async

    logger = logging.getLogger("uvicorn")
    logger.info("[FlowIA] Aquecendo motores...")
    await init_checkpointer_async()
    try:
        from packages.auth_core.database import SupabaseHandler

        db = SupabaseHandler()
        if db.is_ready:
            db.client.table("conversation_metrics").select("id").limit(1).execute()
            logger.info("[FlowIA] Supabase conectado!")
        else:
            logger.error("[FlowIA] Supabase offline")
    except Exception as e:
        logger.error("[FlowIA] Erro no aquecimento: %s", e)

    from packages.scheduling.scheduler import get_scheduler, start_scheduler

    start_scheduler()
    if sched := get_scheduler():
        from packages.integrations.webhook.dedup import register_dedup_purge_job

        register_dedup_purge_job(sched)
    yield
    from packages.scheduling.scheduler import stop_scheduler

    stop_scheduler()
    await shutdown_checkpointer_async()
    logger.info("[FlowIA] Desligando...")


def _register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.exception_handler(DoubleBookingError)
    async def double_booking_handler(_request: Request, exc: DoubleBookingError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ResourceNotFoundError)
    async def not_found_handler(_request: Request, exc: ResourceNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(BusinessLogicError)
    async def business_logic_handler(_request: Request, exc: BusinessLogicError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(FlowIAError)
    async def flowia_error_handler(_request: Request, exc: FlowIAError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})


def _register_middleware(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


def _register_routers(app: FastAPI) -> None:
    from apps.salon.api.routers.dashboard import router as dashboard_router
    from apps.salon.domain.catalog.router import router as organization_router
    from apps.salon.domain.clients.router import router as patient_router
    from packages.auth_core.auth_router import router as auth_router
    from packages.engine.chat_router import router as chat_router
    from packages.engine.metrics_router import router as metrics_router
    from packages.integrations.payments.router import router as payments_router
    from packages.integrations.webhook.router import router as webhook_router
    from packages.lakehouse.router import router as lakehouse_router
    from packages.scheduling.router import router as scheduling_router

    api = "/api/v1"
    app.include_router(webhook_router, prefix=api)
    app.include_router(auth_router, prefix=api)
    app.include_router(chat_router, prefix=api)
    app.include_router(lakehouse_router, prefix=api)
    app.include_router(metrics_router, prefix=api)
    app.include_router(dashboard_router, prefix=api)
    app.include_router(scheduling_router, prefix=api)
    app.include_router(patient_router, prefix=api)
    app.include_router(organization_router, prefix=api)
    app.include_router(payments_router, prefix=api)


def create_salon_app() -> FastAPI:
    """Factory do app FastAPI para o produto salão."""
    from packages.engine.prompts.registry import register_salon_prompts

    register_salon_prompts()

    app = FastAPI(
        title="FlowIA Salon",
        description="Assistente e gestão para salões de beleza",
        version="1.1.0",
        lifespan=lifespan,
    )
    _register_exception_handlers(app)
    _register_middleware(app)
    _register_routers(app)

    @app.get("/health", tags=["System"])
    def health_check():
        uptime_seconds = round(time.monotonic() - _APP_START_TIME, 1)
        db_status = "unknown"
        try:
            from packages.auth_core.database import SupabaseHandler

            db = SupabaseHandler()
            if db.is_ready:
                db.client.table("conversation_metrics").select("id").limit(1).execute()
                db_status = "connected"
            else:
                db_status = "disconnected"
        except Exception:
            db_status = "error"
        return {
            "status": "ok",
            "version": _APP_VERSION,
            "model": settings.MODEL_NAME,
            "database": db_status,
            "uptime_seconds": uptime_seconds,
            "product_line": settings.PRODUCT_LINE,
        }

    return app
