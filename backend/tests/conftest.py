from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import backend.models  # noqa: F401 — registers all table models
from backend.config import Settings, get_settings
from backend.database import get_session
from backend.main import app

_TEST_ENGINE = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = async_sessionmaker(
    bind=_TEST_ENGINE, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with _TEST_ENGINE.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with _TestSessionLocal() as session:
        yield session
    async with _TEST_ENGINE.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("RADARR_API_KEY", "test-api-key")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-jellyfin-key")
    return Settings(
        radarr_url="http://radarr.test",
        jellyfin_url="http://jellyfin.test",
        max_size_gb=40.0,
        avoid_keywords=["CAM", "HDCAM"],
    )


@pytest.fixture
def override_settings(test_settings: Settings):
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield test_settings
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield db_session
    app.dependency_overrides.pop(get_session, None)


@pytest_asyncio.fixture
async def async_client(override_settings, override_db) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
