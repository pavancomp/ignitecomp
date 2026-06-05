"""
Ignite Compensation Engine — FastAPI application
India market — all amounts in INR (₹)
"""

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from config import get_settings
from db.connection import engine, AsyncSessionLocal
from db.models import Base
from db.seed import seed_all
from api.routes import auth, distributors, orders, cycles, compliance, config, sync

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    log.info("ignite_startup", version=settings.APP_VERSION)

    # Create tables (Alembic handles migrations in production; this covers dev)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed reference data
    async with AsyncSessionLocal() as db:
        await seed_all(db)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    await engine.dispose()
    log.info("ignite_shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Step-Binary compensation engine for India market. All amounts in INR (₹).",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request logging middleware ───────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    log.info("request", method=request.method, path=request.url.path)
    response = await call_next(request)
    log.info("response", status=response.status_code, path=request.url.path)
    return response


# ── Health check ──────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health():
    """Checks DB connectivity + reports version."""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        db_ok = False
        log.error("db_health_check_failed", error=str(e))
    return {
        "status": "ok" if db_ok else "degraded",
        "version": settings.APP_VERSION,
        "db": "connected" if db_ok else "unreachable",
        "market": "India (INR)",
    }


# ── Routers ───────────────────────────────────────────────────────────────

PREFIX = "/api/v1"
app.include_router(auth.router,          prefix=PREFIX)
app.include_router(distributors.router,  prefix=PREFIX)
app.include_router(orders.router,        prefix=PREFIX)
app.include_router(cycles.router,        prefix=PREFIX)
app.include_router(compliance.router,    prefix=PREFIX)
app.include_router(config.router,        prefix=PREFIX)
app.include_router(sync.router,          prefix=PREFIX)
