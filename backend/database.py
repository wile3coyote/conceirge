from pathlib import Path
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Place the DB file at the project root (one level above this file's directory)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _PROJECT_ROOT / "concierge.db"
_DATABASE_URL = f"sqlite+aiosqlite:///{_DB_PATH}"

engine = create_async_engine(
    _DATABASE_URL,
    echo=False,
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_db_and_tables() -> None:
    """Create all SQLModel tables. Called once on application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        for ddl in (
            "ALTER TABLE app_settings ADD COLUMN fcm_token TEXT",
            "ALTER TABLE app_settings ADD COLUMN auto_grab BOOLEAN NOT NULL DEFAULT 1",
            "ALTER TABLE libraryitem ADD COLUMN radarr_has_file BOOLEAN NOT NULL DEFAULT 0",
        ):
            try:
                await conn.execute(text(ddl))
            except Exception:
                pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    async with async_session() as session:
        yield session
