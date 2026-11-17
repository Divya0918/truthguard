"""FastAPI application factory with lifespan DB init, seeding, and policy ingestion."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────
    await init_db()
    await _seed_defaults()
    await _ingest_policies()
    yield
    # ── Shutdown ─────────────────────────────────────────
    # (nothing to clean up for SQLite)


async def _seed_defaults() -> None:
    """Create admin and demo customer if they don't exist."""
    from app.core.database import AsyncSessionLocal
    from app.core.security import hash_password
    from app.models.user import User
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        async def _ensure(email: str, name: str, pwd: str, role: str) -> None:
            result = await db.execute(select(User).where(User.email == email))
            if not result.scalar_one_or_none():
                db.add(User(email=email, full_name=name, hashed_password=hash_password(pwd), role=role))

        await _ensure("admin@demo.com",    "Admin User",    "Admin@123456", "admin")
        await _ensure("customer@demo.com", "Demo Customer", "Customer@123", "customer")
        await db.commit()


async def _ingest_policies() -> None:
    """Ingest pre-loaded .txt policy files from data/policies/ (idempotent)."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.services.ingestion import ingest_all_policies
        async with AsyncSessionLocal() as db:
            await ingest_all_policies(db)
    except Exception as exc:
        print(f"[WARN] Policy ingestion failed: {exc}")


def create_app() -> FastAPI:
    app = FastAPI(
        title="TruthGuard API",
        description="Multi-Agent Banking Intelligence System",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api import router as api_router
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "TruthGuard", "version": "2.0.0"}

    return app


app = create_app()
