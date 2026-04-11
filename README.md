# Concierge

A local-network web app that automates movie downloads by orchestrating Radarr, SABnzbd, and Jellyfin — replacing the manual Radarr UI with a single search-and-confirm interface.

## What it does

1. Search for a movie by title
2. Concierge fetches available releases from Radarr, scores them by quality and size, and returns a ranked list
3. Confirm the best release (or pick a different one) with one click
4. Radarr hands the download to SABnzbd automatically
5. When the download completes, Concierge refreshes your Jellyfin library

## Prerequisites

- Python 3.13+
- Node.js 20+
- A running [Radarr](https://radarr.video) instance with an API key
- A running [Jellyfin](https://jellyfin.org) instance with an API key

## Setup

**1. Clone and configure**

```bash
git clone <repo-url>
cd concierge
cp .env.example .env
```

Edit `.env` with your API keys and service URLs:

```env
RADARR_URL=http://your-radarr-host:7878
RADARR_API_KEY=your_radarr_api_key
JELLYFIN_URL=http://your-jellyfin-host:8096
JELLYFIN_API_KEY=your_jellyfin_api_key
```

**2. Install backend dependencies**

```bash
pip install -e ".[dev]"
```

**3. Install frontend dependencies**

```bash
cd frontend && npm install
```

## Running locally

```bash
# Terminal 1 — backend (from project root)
uvicorn backend.main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

## Configuration

All settings are loaded from `.env`. Defaults are listed in `.env.example`.

| Variable | Default | Description |
|---|---|---|
| `RADARR_URL` | `http://localhost:7878` | Radarr base URL |
| `RADARR_API_KEY` | — | Radarr API key |
| `JELLYFIN_URL` | `http://localhost:8096` | Jellyfin base URL |
| `JELLYFIN_API_KEY` | — | Jellyfin API key |
| `MAX_SIZE_GB` | `40` | Releases larger than this are rejected |
| `PREFERRED_QUALITY` | `2160p` | `2160p` or `1080p` |
| `AVOID_KEYWORDS` | `["BRRip","CAM","TS","HDCAM"]` | Releases containing these keywords are rejected |

`AVOID_KEYWORDS` accepts either a JSON array or a comma-separated string.

## Scoring rules

- **Quality:** 2160p (4K/UHD) ranked above 1080p; 720p always rejected
- **Size:** releases over `MAX_SIZE_GB` are rejected
- **Format blocklist:** any release whose title contains a keyword from `AVOID_KEYWORDS` is rejected

## Radarr webhook (completion flow)

To trigger automatic Jellyfin refreshes when a download completes, add a webhook in Radarr:

- **URL:** `http://<concierge-host>:8000/webhooks/radarr`
- **Events:** On Download

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, SQLModel, aiosqlite |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Database | SQLite (file: `concierge.db` at project root) |
| Config | pydantic-settings, `.env` file |

## Project status

Currently in active development. See `PLAN.md` for the phased roadmap.
