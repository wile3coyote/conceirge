# Project Plan — Concierge

## Overview
Concierge is a local-network web app that automates movie downloads by orchestrating Radarr (search + release selection), SABnzbd (via Radarr), and Jellyfin (library refresh) — replacing the manual Radarr UI workflow with a single search-and-confirm interface.

## Goals
- Search for a movie and automatically pick the best available release based on quality, size, and format rules
- Trigger the download via Radarr/SABnzbd with one click, without opening Radarr
- Automatically refresh Jellyfin when the download completes
- Track active downloads and history in a simple UI

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
| Data fetching | TanStack Query v5 | Polling for active downloads, cache invalidation |
| Testing (backend) | pytest + httpx + respx | FastAPI-native, mock Radarr/Jellyfin HTTP calls |
| Testing (frontend) | Vitest + React Testing Library | Component and flow testing |
| Deployment | Docker + docker-compose | Reproducible local server deployment |

## Architecture

- **Orchestrator pattern:** the backend is the sole integration point — the React UI never calls Radarr or Jellyfin directly; all calls go through our FastAPI backend which holds the API keys and scoring logic
- **Search flow:** UI sends query → backend calls Radarr to find/add the movie → triggers a release search → fetches releases → scores them → returns ranked list to UI
- **Grab flow:** user confirms (or overrides) → backend tells Radarr to grab the chosen release → Radarr hands it to SABnzbd automatically
- **Completion flow:** Radarr fires an `On Download` webhook to our server → backend calls Jellyfin to refresh that library item → marks the Download record as `complete`
- **State:** SQLite holds Download records with status lifecycle: `pending → searching → grabbed → complete / failed`

## Folder Structure

```
concierge/
├── backend/
│   ├── main.py                  # FastAPI app entry point, router registration, lifespan
│   ├── config.py                # pydantic-settings: API keys, URLs, scoring thresholds
│   ├── database.py              # SQLite engine + async session dependency
│   ├── exceptions.py            # Domain exception hierarchy (RadarrError, JellyfinError, etc.)
│   ├── models/
│   │   ├── download.py          # SQLModel table: Download (status, release info, timestamps)
│   │   └── release.py           # Pydantic-only: ScoredRelease (not persisted)
│   ├── routers/
│   │   ├── movies.py            # POST /movies/search, POST /movies/grab
│   │   ├── downloads.py         # GET /downloads
│   │   └── webhooks.py          # POST /webhooks/radarr (On Download events)
│   ├── services/
│   │   ├── radarr.py            # All Radarr API calls (httpx client)
│   │   ├── jellyfin.py          # Jellyfin library refresh call
│   │   └── scorer.py            # Release scoring logic — pure, no I/O
│   └── tests/
│       ├── conftest.py
│       ├── test_scorer.py
│       ├── test_movies.py
│       ├── test_downloads.py
│       └── test_webhooks.py
├── frontend/
│   ├── src/
│   │   ├── components/          # SearchBar, ReleaseCard, DownloadRow, StatusBadge
│   │   ├── pages/
│   │   │   ├── Search.tsx       # Search + scored release + override + confirm flow
│   │   │   └── Downloads.tsx    # Active downloads (polling) + history
│   │   ├── api/                 # TanStack Query hooks + shared types
│   │   └── main.tsx             # App entry, React Router, QueryClient setup
│   ├── index.html
│   └── vite.config.ts
├── .env.example                 # Template for API keys and service URLs
├── docker-compose.yml
└── PLAN.md
```

## Key Data Models

**Download** (persisted in SQLite)
- `id`, `radarr_movie_id`, `movie_title`, `year`
- `status`: `pending | searching | grabbed | complete | failed`
- `chosen_release_title`, `chosen_release_size_gb`, `chosen_release_quality`
- `created_at`, `completed_at`

**ScoredRelease** (in-memory, returned by `/movies/search`)
- `title`, `size_gb`, `quality` (e.g. `2160p`, `1080p`)
- `score` (integer ranking), `rejected` (bool), `reject_reason`
- `radarr_guid` (passed back to `/movies/grab`)

**Config** (pydantic-settings, from `.env`)
- `radarr_url`, `radarr_api_key`
- `jellyfin_url`, `jellyfin_api_key`
- `max_size_gb` (default: 40), `preferred_quality` (default: `2160p`)
- `avoid_keywords` (default: `["BRRip", "CAM", "TS", "HDCAM"]`)

## Phases

| Phase | Name | What's included | Done when… |
|---|---|---|---|
| 1 | Foundation | Project scaffold, folder structure, pydantic-settings config, SQLite + SQLModel setup, `.env.example`, health endpoint | `GET /health` returns 200, frontend loads, DB initializes on startup |
| 2 | Radarr Integration | Radarr service layer, scorer logic, `POST /movies/search` returning scored + ranked releases | Can search a movie and get back a ranked release list with rejections explained |
| 3 | Grab & Download Tracking | `POST /movies/grab`, Download record lifecycle, Radarr webhook receiver, Jellyfin refresh on completion | Full grab-to-complete flow works end-to-end via FastAPI `/docs` |
| 4 | Frontend UI | Search page, Downloads page, polling, status badges, error states | Full flow usable from browser without touching Radarr UI |
| 5 | Deployment | Dockerfiles, docker-compose, nginx proxy, SQLite volume, LAN IP wiring | `docker compose up` on the server brings the app up and survives a reboot |

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

---
*Last updated: 2026-04-11*
