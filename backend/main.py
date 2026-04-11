from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.database import create_db_and_tables
from backend.exceptions import ConciergeError
from backend.routers import downloads, movies, webhooks
import backend.models  # noqa: F401 — registers SQLModel table metadata


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize DB tables on startup; clean up on shutdown."""
    await create_db_and_tables()
    yield


app = FastAPI(
    title="Concierge",
    description="Automated movie download orchestration for Radarr, SABnzbd, and Jellyfin.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(movies.router)
app.include_router(downloads.router)
app.include_router(webhooks.router)


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
