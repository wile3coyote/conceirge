# Project Plan — Concierge

## Overview
Concierge is a local-network web app that acts as a simplified Radarr interface for a non-technical user. Search for a movie, click "Add to Library," and the system auto-picks the best release, triggers the download via Radarr/SABnzbd, and refreshes Jellyfin when complete — all from a single page.

## Goals
- Search for a movie and add it to an internal library with one click
- Automatically pick the best available release based on quality, size, and format rules
- Track download status in real time: searching → downloading → in Jellyfin
- Automatically refresh Jellyfin when the download completes
- Allow retry (fresh search) or delete on failed items

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend language | Python 3.13 | Preferred, modern async support |
| Backend framework | FastAPI | Async-native, auto OpenAPI docs |
| HTTP client | httpx | Async-native, fits FastAPI's async model |
| Database | SQLite + SQLModel | Zero-config local deployment; Pydantic-native ORM |
| Config | pydantic-settings + .env | Type-safe config for API keys and URLs |
| Frontend framework | React 18 + Vite + TypeScript | Fast dev cycle, strict typing |
| Styling | Tailwind CSS | Utility-first, no separate CSS files |
| Data fetching | TanStack Query v5 | Polling for library status, cache invalidation |
| Testing (backend) | pytest + httpx + respx | FastAPI-native, mock Radarr/Jellyfin HTTP calls |
| Testing (frontend) | Vitest + React Testing Library | Component and flow testing |
| Deployment | Docker + docker-compose | Reproducible local server deployment |

## Architecture

- **Orchestrator pattern:** the backend is the sole integration point — the React UI never calls Radarr or Jellyfin directly; all calls go through our FastAPI backend which holds the API keys and scoring logic
- **Search flow:** UI sends query → backend calls Radarr lookup → returns movie info (poster, title, year, overview) to UI — no releases exposed to the user
- **Add-to-library flow:** User clicks "Add to Library" → backend creates a `LibraryItem` (status: `searching`), returns 202 immediately → a background task handles: Radarr release search → score releases → grab best release → status updates at each step
- **Webhook flow:** Radarr fires `On Grab` / `On Download` webhooks → backend updates library item status → on download complete, triggers Jellyfin library refresh → marks item as `in_library`
- **Retry flow:** User clicks "Retry" on a failed item → backend resets status to `searching`, kicks off background task again. Radarr's built-in blocklist avoids re-grabbing the same failed release.
- **State:** SQLite holds `LibraryItem` records with status lifecycle: `searching → grabbing → downloading → downloaded → in_library | failed`

## Folder Structure

```
concierge/
├── backend/
│   ├── main.py                  # FastAPI app entry point, router registration, lifespan
│   ├── config.py                # pydantic-settings: API keys, URLs, scoring thresholds
│   ├── database.py              # SQLite engine + async session dependency
│   ├── exceptions.py            # Domain exception hierarchy (RadarrError, JellyfinError, etc.)
│   ├── models/
│   │   ├── library_item.py      # SQLModel table: LibraryItem (status, release info, timestamps)
│   │   └── release.py           # Pydantic-only: ScoredRelease, MovieSearchResult, AddToLibraryRequest
│   ├── routers/
│   │   ├── movies.py            # POST /movies/search (movie lookup only, no releases)
│   │   ├── library.py           # POST /library, GET /library, POST /library/{id}/retry, DELETE /library/{id}
│   │   └── webhooks.py          # POST /webhooks/radarr (On Grab, On Download events)
│   ├── services/
│   │   ├── radarr.py            # All Radarr API calls (httpx client)
│   │   ├── jellyfin.py          # Jellyfin library refresh call
│   │   ├── scorer.py            # Release scoring logic — pure, no I/O
│   │   └── library.py           # Background task: search → score → grab pipeline
│   └── tests/
│       ├── conftest.py
│       ├── test_scorer.py
│       ├── test_movies.py
│       ├── test_library.py
│       ├── test_webhooks.py
│       └── test_jellyfin.py
├── frontend/
│   ├── src/
│   │   ├── components/          # SearchBar, MovieCard, LibraryCard, StatusBadge
│   │   ├── pages/
│   │   │   └── Home.tsx         # Single page: search bar + library grid
│   │   ├── api/                 # TanStack Query hooks + shared types
│   │   └── main.tsx             # App entry, QueryClient setup
│   ├── index.html
│   └── vite.config.ts
├── .env.example                 # Template for API keys and service URLs
├── docker-compose.yml
└── PLAN.md
```

## Key Data Models

**LibraryItem** (persisted in SQLite)
- `id`, `tmdb_id` (indexed, dedup key), `radarr_movie_id` (nullable, set after Radarr lookup)
- `title`, `year`, `overview`, `poster_url`
- `status`: `searching | grabbing | downloading | downloaded | in_library | failed`
- `fail_reason` (nullable, set on failure)
- `chosen_release_title`, `chosen_release_size_gb`, `chosen_release_quality`
- `created_at`, `updated_at`

**MovieSearchResult** (in-memory, returned by `/movies/search`)
- `tmdb_id`, `title`, `year`, `overview`, `poster_url`

**ScoredRelease** (in-memory, used internally by scorer — never exposed to UI)
- `title`, `size_gb`, `quality`, `score`, `rejected`, `reject_reason`, `radarr_guid`, `indexer_id`

**Config** (pydantic-settings, from `.env`)
- `radarr_url`, `radarr_api_key`
- `jellyfin_url`, `jellyfin_api_key`
- `max_size_gb` (default: 40), `preferred_quality` (default: `2160p`)
- `avoid_keywords` (default: `["BRRip", "CAM", "TS", "HDCAM"]`)

## Phases

| Phase | Name | What's included | Done when... |
|---|---|---|---|
| 1 | Backend Data Model | Replace `Download` with `LibraryItem`, update status enum, update request/response models | New table schema creates, models import cleanly |
| 2 | Simplified Search | `POST /movies/search` returns movie info only (no releases), remove grab endpoint | Search returns list of movie cards with poster/title/year |
| 3 | Library Router + Background Task | `POST/GET/DELETE /library`, retry endpoint, async background task (search → score → grab) | Can add movie to library, status progresses through pipeline |
| 4 | Webhooks | Radarr webhook handler for On Grab and On Download events | Webhook payloads drive status transitions |
| 5 | Jellyfin Service | `refresh_library()` implementation, called from webhook on download complete | Movie reaches `in_library` status after Jellyfin refresh |
| 6 | Frontend Types + API | Updated TypeScript types, delete helper in API client | TypeScript compiles with new types |
| 7 | Frontend Components | MovieCard, LibraryCard, updated StatusBadge | Components render correctly |
| 8 | Frontend Single Page | Home.tsx with search bar + library grid, remove router/nav | Full flow usable from browser |
| 9 | Tests | Backend tests for all endpoints, background task, webhooks, Jellyfin | `pytest backend/tests/` passes |

## Scoring Rules

- **Quality preference:** 2160p > 1080p; 720p always rejected
- **Size limit:** max 40GB for movies
- **Format blocklist:** BRRip, CAM, TS, HDCAM — any release with these in the title is rejected
- **Quality keyword matching:** `2160p`, `2160`, `4K`, `UHD` count as 2160p; `1080p`, `1080` count as 1080p
- English keyword refinement deferred to post-v1

## Out of Scope (v1)

- TV shows / Sonarr integration (planned for v2)
- Authentication / user accounts (local network only)
- Configuring scoring rules from the UI (edit `.env` directly for now)
- Notifications (email, Slack, etc.) on download completion
- Multiple simultaneous grabs for the same movie
- Subtitle downloading
- Release selection UI (auto-picker only)

---
*Last updated: 2026-04-12*
