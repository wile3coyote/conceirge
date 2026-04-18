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

## Architecture

Concierge is a local-network app that replaces the manual Radarr UI for movie downloads. The Android app is the sole client — all integration logic lives in the FastAPI backend.

### Request flows

**Search:** UI → `POST /movies/search` → backend calls Radarr to find/add the movie, triggers a release search, fetches releases, scores them → returns `ScoredRelease[]` ranked list.

**Grab:** UI → `POST /movies/grab` → backend tells Radarr to grab the chosen release → creates a `Download` record (status: `grabbed`).

**Completion:** Radarr fires `On Download` webhook → `POST /webhooks/radarr` → backend calls Jellyfin to refresh the library item → marks `Download` as `complete`.

### Backend structure

- **`backend/main.py`** — FastAPI app entry, CORS (no browser origins; the Android app does not use CORS), lifespan calls `create_db_and_tables()`, exception handler maps `ConciergeError` → HTTP 502 with `{"detail", "code"}`.
- **`backend/config.py`** — `get_settings()` with `@lru_cache`. Never use a module-level `Settings()` instance; always use `get_settings()` or inject via `Depends(get_settings)`. API keys are `SecretStr` — call `.get_secret_value()` at the HTTP call site.
- **`backend/database.py`** — async SQLite via `aiosqlite`. Use `Depends(get_session)` in route handlers. DB file is `concierge.db` at project root.
- **`backend/models/__init__.py`** — must import all SQLModel table classes so they register on `SQLModel.metadata` before `create_db_and_tables()` runs. Always add new table models here.
- **`backend/services/`** — pure service layer; raise `RadarrError`, `JellyfinError`, or `ScoringError` (never `HTTPException`). The exception handler in `main.py` converts them to HTTP responses.
- **`backend/services/scorer.py`** — pure function, no I/O. Scoring rules: 2160p > 1080p, 720p rejected; max 40 GB; blocklist keywords in title → rejected.

### Key invariants

- `avoid_keywords` in `.env` accepts either JSON (`["BRRip","CAM"]`) or comma-separated (`BRRip,CAM`).
- `Download.status` is a `Literal` — only the five values `pending | searching | grabbed | complete | failed` are valid.
- The backend runs from the **project root** (`uvicorn backend.main:app`), not from inside `backend/`. Imports use `from backend.X import Y` throughout.
- SQLite DB path is resolved relative to `database.py`'s location, so it always lands at the project root regardless of CWD.

## Commit Message Standard

Format: `<type>(<scope>): <short summary>`

**Types**
- `feat` — new feature or capability
- `fix` — bug fix
- `chore` — tooling, deps, config (no production code)
- `docs` — documentation only
- `refactor` — code restructure, no behavior change
- `test` — adding or updating tests
- `style` — formatting, linting (no logic change)

**Scopes** (optional): `backend`, `frontend`, `db`, `api`, `scorer`, `webhook`, `config`, `deps`

**Rules**
- Summary is lowercase, imperative mood, no trailing period, max ~72 chars
- No HEREDOC, no EOF markers, no `Co-Authored-By` trailer
- Use plain `git commit -m "..."` inline string
- Split commits by concern — backend, frontend, docs, config as separate commits

**Examples**
```
feat(scorer): add 2160p preference and 720p rejection
fix(backend): handle missing radarr api key gracefully
chore(deps): pin aiosqlite to 0.19.0
test(scorer): add cases for blocklist keyword rejection
docs: update PLAN.md with phase 2 milestones
```
