import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import select

from backend.config import get_settings
from backend.database import async_session, create_db_and_tables
from backend.exceptions import ConciergeError
from backend.models.app_settings import AppSettings
from backend.routers import library, movies, status as status_router, webhooks
from backend.routers import settings as settings_router
from backend.services.sync import reconcile_with_radarr
import backend.models  # noqa: F401 — registers SQLModel table metadata

logger = logging.getLogger(__name__)

_RECONCILE_INTERVAL_SECONDS = 1800  # 30 minutes


async def _seed_app_settings() -> None:
    """Create the settings row from .env defaults if it doesn't exist yet."""
    env = get_settings()
    async with async_session() as session:
        existing = (await session.exec(select(AppSettings))).first()
        if existing is None:
            row = AppSettings(
                max_size_gb=env.max_size_gb,
                preferred_quality=env.preferred_quality,
                avoid_keywords_json=json.dumps(env.avoid_keywords),
            )
            session.add(row)
            await session.commit()


async def _reconcile_loop() -> None:
    """Background task: call reconcile_with_radarr every 30 minutes.

    Sleeps for the interval, then reconciles — so the first run is done
    eagerly in the lifespan before this loop starts.  Exits cleanly on
    CancelledError.
    """
    while True:
        try:
            await asyncio.sleep(_RECONCILE_INTERVAL_SECONDS)
            async with async_session() as session:
                await reconcile_with_radarr(session)
        except asyncio.CancelledError:
            logger.info("reconcile_loop: cancelled, shutting down")
            return
        except Exception:
            logger.exception("reconcile_loop: error during reconciliation — will retry next cycle")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize DB tables, seed settings, run initial sync, start periodic sync."""
    await create_db_and_tables()
    await _seed_app_settings()

    # One-shot reconcile at startup — best-effort (Radarr may be unavailable)
    try:
        async with async_session() as session:
            await reconcile_with_radarr(session)
    except Exception:
        logger.warning(
            "lifespan: startup reconciliation failed (Radarr may be offline) — continuing",
            exc_info=True,
        )

    # Spawn the periodic reconcile loop
    reconcile_task = asyncio.create_task(_reconcile_loop())

    yield

    # Shutdown: cancel the background loop and wait for it to finish
    reconcile_task.cancel()
    try:
        await reconcile_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Concierge",
    description="Automated movie download orchestration for Radarr, SABnzbd, and Jellyfin.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(movies.router)
app.include_router(library.router)
app.include_router(webhooks.router)
app.include_router(settings_router.router)
app.include_router(status_router.router)


@app.exception_handler(ConciergeError)
async def concierge_error_handler(request: Request, exc: ConciergeError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": exc.detail, "code": exc.code},
    )


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return service liveness status."""
    return {"status": "ok"}
