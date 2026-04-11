# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend

```bash
# Install dependencies (from project root)
pip install -e ".[dev]"

# Run the dev server (must be run from project root, not from backend/)
uvicorn backend.main:app --reload

# Run all tests
pytest backend/tests/

# Run a single test file
pytest backend/tests/test_scorer.py

# Run a single test by name
pytest backend/tests/test_scorer.py::test_name -v
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run the dev server (http://localhost:5173)
npm run dev

# Type-check + build
npm run build
```

## Architecture

Concierge is a local-network web app that replaces the manual Radarr UI for movie downloads. The React frontend never calls Radarr or Jellyfin directly — all integration logic lives in the FastAPI backend.

### Request flows

**Search:** UI → `POST /movies/search` → backend calls Radarr to find/add the movie, triggers a release search, fetches releases, scores them → returns `ScoredRelease[]` ranked list.

**Grab:** UI → `POST /movies/grab` → backend tells Radarr to grab the chosen release → creates a `Download` record (status: `grabbed`).

**Completion:** Radarr fires `On Download` webhook → `POST /webhooks/radarr` → backend calls Jellyfin to refresh the library item → marks `Download` as `complete`.

### Backend structure

- **`backend/main.py`** — FastAPI app entry, CORS (localhost:5173 only), lifespan calls `create_db_and_tables()`, exception handler maps `ConciergeError` → HTTP 502 with `{"detail", "code"}`.
- **`backend/config.py`** — `get_settings()` with `@lru_cache`. Never use a module-level `Settings()` instance; always use `get_settings()` or inject via `Depends(get_settings)`. API keys are `SecretStr` — call `.get_secret_value()` at the HTTP call site.
- **`backend/database.py`** — async SQLite via `aiosqlite`. Use `Depends(get_session)` in route handlers. DB file is `concierge.db` at project root.
- **`backend/models/__init__.py`** — must import all SQLModel table classes so they register on `SQLModel.metadata` before `create_db_and_tables()` runs. Always add new table models here.
- **`backend/services/`** — pure service layer; raise `RadarrError`, `JellyfinError`, or `ScoringError` (never `HTTPException`). The exception handler in `main.py` converts them to HTTP responses.
- **`backend/services/scorer.py`** — pure function, no I/O. Scoring rules: 2160p > 1080p, 720p rejected; max 40 GB; blocklist keywords in title → rejected.

### Frontend structure

- All API calls go through `src/api/client.ts` — `get<T>()` and `post<T>()` helpers that hit `/api/*` (proxied to `http://localhost:8000` by Vite in dev, stripping the `/api` prefix).
- Catch `ApiError` (from `client.ts`) to branch on `status`, `detail`, and `code` in error handling.
- `src/api/types.ts` mirrors the backend Pydantic models exactly — keep them in sync.
- TanStack Query (`@tanstack/react-query`) handles all server state: fetching, caching, polling for active downloads.

### Key invariants

- `avoid_keywords` in `.env` accepts either JSON (`["BRRip","CAM"]`) or comma-separated (`BRRip,CAM`).
- `Download.status` is a `Literal` — only the five values `pending | searching | grabbed | complete | failed` are valid.
- The backend runs from the **project root** (`uvicorn backend.main:app`), not from inside `backend/`. Imports use `from backend.X import Y` throughout.
- SQLite DB path is resolved relative to `database.py`'s location, so it always lands at the project root regardless of CWD.
