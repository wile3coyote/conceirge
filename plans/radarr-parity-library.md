# Radarr-parity library & manual release picker

## Context

Concierge today is a one-click "Add to Library" app: every add triggers an automatic pipeline that adds the movie to Radarr, scores releases, and grabs the best one. There is no way to review releases, override the scorer, or interact with movies once they exist. The library also drifts from Radarr — anything added directly in Radarr is invisible to Concierge.

This feature brings Concierge closer to Radarr's own interaction model while keeping its opinionated "one-tap" experience as the default:

- A **Settings toggle** disables automatic grabbing so users can review releases first.
- **Library items become tappable**, opening a detail screen with metadata, status-aware actions, and a manual release browser (Radarr's "interactive search" equivalent).
- **Delete from library** becomes a single destructive action that removes the movie and its files from Radarr/disk.
- **Radarr → Concierge library sync** (webhooks + periodic reconcile) so movies added elsewhere appear automatically.
- The **web frontend is retired**; the Android app becomes the sole client.

## Decisions (from brainstorming)

| # | Decision | Choice |
|---|---|---|
| 1 | Auto-grab OFF semantics | **B** — Add to Radarr only; release search on demand when user opens detail page |
| 2 | Radarr → Concierge sync | **C** — webhooks + 30-min periodic reconcile + manual "Sync now" |
| 3 | Delete behavior | **C** — destructive: delete movie + files, with confirmation dialog |
| 4 | Actions on already-downloaded movies | **C** — detail is view-only by default, "Search for upgrade" button reveals releases |
| 5 | Release list display | **B** — show all releases (rejected dimmed with reason), sort by score desc |
| 6 | Detail actions | Both **Auto-grab** and **Interactive search** are offered as primary buttons on the detail screen (not just interactive search). |

## Data model changes

### `AppSettings` (backend/models/app_settings.py)
Add one field; keep the single-row pattern.

- `auto_grab: bool` — default `True` (preserves current behavior on migration).
- Extend `AppSettingsRead` and `AppSettingsUpdate` DTOs.

### `LibraryItem` (backend/models/library_item.py)
Status enum gains one value; no new tables (releases remain ephemeral).

Current statuses: `searching | grabbing | downloading | downloaded | in_library | failed`

Add: **`idle`** — movie is in Radarr but no active release-search or download is happening. Used when:
- Auto-grab is OFF and user just added the movie (step before "Search releases").
- Movie was synced from Radarr but hasn't been downloaded yet (no file).
- A file was deleted in Radarr (`MovieFileDelete` event).

Optional new field: `radarr_has_file: bool` (derived from `GET /api/v3/movie` on sync). Lets the UI distinguish `idle` (no file) from `in_library` (file present) cleanly.

### No new tables
- Releases are **not persisted** — fetched on demand from Radarr every time the detail view opens them (they expire anyway).
- A `Download` table is not needed — `LibraryItem` continues to carry `download_id` / `chosen_release_*`.

## Backend changes

All service-layer functions raise `RadarrError` / `JellyfinError`; routers catch via the global `ConciergeError` handler.

### New endpoints (backend/routers/library.py)

- `GET /library/{id}/releases` — on-demand. Calls `radarr.fetch_releases(movie_id)` (reuses existing), passes results through `scorer.score_releases()`, returns **all** `ScoredRelease`s (rejected included) sorted by `score` desc. Response shape already exists — just expose it.
- `POST /library/{id}/grab` — body `{ guid: str, indexer_id: int }`. Calls `radarr.grab_release()` (reuses existing), transitions status → `grabbing`, stores `chosen_release_*` fields. Trusts the client's pick (does not block a "rejected" release — explicit override).
- `POST /library/{id}/auto-grab` — runs the grab-phase of `run_library_pipeline` on demand (fetch → score → pick best non-rejected → grab). Reuses the existing scorer + grab path. Returns `202` immediately; status transitions `idle`/`in_library`/`failed` → `searching` → `grabbing`. Used by the "Auto-grab best" / "Auto-grab upgrade" / "Retry" buttons.
- `POST /library/sync` — triggers a full reconcile in the background; returns `202` immediately.

### New endpoint (backend/routers/webhooks.py)

Extend `POST /webhooks/radarr` to handle three more eventTypes:
- `MovieAdded` → upsert a `LibraryItem` (status `idle` if no file, `in_library` if `hasFile`).
- `MovieDelete` → delete the matching `LibraryItem` (guard: skip if currently `grabbing`/`downloading` to avoid races with in-flight adds).
- `MovieFileDelete` → transition `in_library` → `idle`; clear `chosen_release_*` and `download_id`.

### Reconcile service (new: backend/services/sync.py)

- `async def reconcile_with_radarr(session)`:
  1. `GET /api/v3/movie` (new helper in `services/radarr.py`: `list_movies()`).
  2. Index both sides by `tmdb_id`.
  3. Radarr-only → insert `LibraryItem` (status from `hasFile`).
  4. Concierge-only with a `radarr_movie_id` → delete (Radarr is source of truth for "does this movie exist").
  5. Both-sides → update `radarr_has_file`, title/year/overview/poster if changed.
- Called from:
  - App startup (one-shot in lifespan after `create_db_and_tables`).
  - Background loop: `asyncio.create_task` sleeping 30 min between runs (spawned in lifespan).
  - `POST /library/sync` (on demand).

### Modified pipeline (backend/services/library.py)

`run_library_pipeline` currently always searches + grabs. Split into two phases:

1. **Add phase** (always runs): lookup → add to Radarr → commit `radarr_movie_id`.
2. **Grab phase** (only if `settings.auto_grab` is `True`): fetch releases → score → grab best.

When `auto_grab` is `False`, the item lands at status `idle` and the pipeline exits. The user initiates phase 2 manually via `GET /library/{id}/releases` + `POST /library/{id}/grab`, or via `POST /library/{id}/auto-grab` to re-run the auto path without changing the global setting.

### Modified delete (backend/routers/library.py)

`DELETE /library/{id}`:
1. If `radarr_movie_id` present → call new helper `radarr.delete_movie(movie_id, delete_files=True)` which hits `DELETE /api/v3/movie/{id}?deleteFiles=true&addImportExclusion=false`.
2. If status is `downloading` and `download_id` present → call SABnzbd to cancel the queue item (new helper in `services/sabnzbd.py`: `delete_queue_item`).
3. Delete the `LibraryItem` row.
4. Errors in steps 1/2 are logged but do not block row deletion (best-effort cleanup).

### New Radarr helpers (backend/services/radarr.py)

- `list_movies()` → `list[dict]` from `GET /api/v3/movie` (for reconcile).
- `delete_movie(movie_id, delete_files=True)` → `DELETE /api/v3/movie/{id}`.

## Android app changes

Package typo `conceirge` is kept as-is (out of scope).

### New dependency: Navigation-Compose

Gradle: add `androidx.navigation:navigation-compose` (latest stable for Compose BOM 2024.12.01). Replace the `enum Screen` + `when` switch in `MainActivity.kt` with a `NavHost`:

```
NavHost(startDestination = "home")
  composable("home")                  -> HomeScreen(onOpenDetail = { id -> navController.navigate("library/$id") })
  composable("library/{id}")          -> LibraryDetailScreen(id)
  composable("settings")              -> SettingsScreen
  composable("status")                -> StatusScreen
  composable("setup")                 -> SetupScreen
```

This also unblocks the FCM deep-link: `navigate_to=library/{id}` in the notification extras → `MainActivity.onNewIntent` reads it and calls `navController.navigate()`.

### New screen: `LibraryDetailScreen` (ui/LibraryDetailScreen.kt + LibraryDetailViewModel.kt)

Layout:
- **Header**: poster, title (year), overview, status badge.
- **Action pane** (status-dependent):
  - `idle` → two primary buttons side-by-side: **"Auto-grab best"** and **"Interactive search"**. Secondary: **"Delete"**.
    - "Auto-grab best" calls `POST /library/{id}/auto-grab` — same fetch → score → grab-best logic as auto_grab=True at add-time, just deferred and user-initiated.
    - "Interactive search" reveals the release list (see below).
  - `searching` / `grabbing` / `downloading` / `downloaded` → progress indicator + **"Delete"** (no release browser; grab in flight).
  - `in_library` → two primary buttons: **"Auto-grab upgrade"** and **"Interactive search"**. Secondary: **"Delete"**. Same two-button pattern — auto-grab here requests an upgrade candidate; interactive lets the user pick.
  - `failed` → **"Retry"** (= re-run auto-grab) + **"Interactive search"** + **"Delete"**.
- **Release list** (collapsed by default, expands when "Interactive search" tapped):
  - Calls `GET /library/{id}/releases`. While loading: spinner. On result: `LazyColumn` of `ReleaseRow`.
  - `ReleaseRow`: title, quality pill (2160p/1080p/720p), size, score, indexer, seeders. If `rejected`: whole row dimmed + small badge showing reason (e.g., "Too large: 52 GB").
  - Tap a row → confirmation (for rejected releases) → `POST /library/{id}/grab` → navigate back to Home (polling will surface the progress).

Delete everywhere shows a confirmation dialog: *"Delete <title> (<year>)? This removes the movie and its files from Radarr."*

### `HomeScreen` updates (ui/HomeScreen.kt)

- `LibraryCard.onClick` → `onOpenDetail(item.id)`. Inline `Retry`/`Remove` buttons are removed (actions move to detail).
- Add **pull-to-refresh** (Material3 `PullToRefreshBox`) on the library list; refresh calls `GET /library` eagerly (bypass 5s poll).

### `SettingsScreen` updates (ui/SettingsScreen.kt)

- Add a **"Automatically grab releases"** switch bound to `auto_grab`.
- Add a **"Sync with Radarr now"** button that calls `POST /library/sync` and snackbars the result.

### API + models (data/network + data/models)

- `ConciergeApiService.kt`: add
  - `@GET("library/{id}/releases") getReleases(id: Int): List<ScoredRelease>`
  - `@POST("library/{id}/grab") grabRelease(id: Int, @Body body: GrabReleaseRequest)`
  - `@POST("library/{id}/auto-grab") autoGrab(id: Int): Response<Unit>`
  - `@POST("library/sync") syncLibrary(): Response<Unit>`
- New data classes:
  - `ScoredRelease` (mirrors backend `ScoredRelease`: guid, indexer_id, title, quality, size_bytes, size_gb, seeders, score, rejected, rejection_reason, age_hours, indexer).
  - `GrabReleaseRequest(guid: String, indexer_id: Int)`.
- `AppSettings` + `AppSettingsUpdate`: add `auto_grab: Boolean`.
- `LibraryItem.status` union: add `"idle"`, and handle in `StatusBadge` (grey).

### FCM deep-link plumbing (MainActivity + ConciergeFirebaseMessagingService)

- Service: change `navigate_to` value from `library` to `library/{id}` using `libraryItemId` from the FCM data payload (backend already knows the id when it fires `fcm.send_download_complete` — pass it in the payload).
- `MainActivity.onCreate` / `onNewIntent`: read `navigate_to` extra and call `navController.navigate(it)`.

### Connectivity UX — fix "couldn't connect to server" flash on resume

**Problem:** On app launch and on resume from background, the UI briefly shows a "couldn't connect" error before the library loads. Root causes:
1. `HomeViewModel` polls `GET /library` in a bare `while(true) { delay(5_000) }`. A poll that failed while the app was backgrounded leaves the `error` state set. On resume the UI renders the stale error immediately, *before* the next poll fires.
2. No local cache — every launch starts with an empty library, nothing to show during the first in-flight request.
3. Retrofit/OkHttp has no retry. First call on resume often fails fast because the network stack / DNS is not ready yet; a 500 ms retry would have succeeded silently.

**Fix — three small complementary pieces:**

1. **OkHttp retry interceptor** (`data/network/RetryInterceptor.kt` — **new**).
   - 3 attempts with backoff: 500 ms / 1.5 s / 4.5 s.
   - Retries only on `IOException` (connect/read timeout, socket errors), not on HTTP 4xx/5xx.
   - Wired into `RetrofitInstance.kt` alongside the existing `HttpLoggingInterceptor`.

2. **Local library cache** (DataStore Preferences).
   - New Gradle dep: `androidx.datastore:datastore-preferences`.
   - New class `data/cache/LibraryCache.kt`: exposes `suspend fun load(): List<LibraryItem>` and `suspend fun save(items: List<LibraryItem>)`. Stores as a single JSON string via Gson.
   - `HomeViewModel` hydrates its `StateFlow<List<LibraryItem>>` from `LibraryCache.load()` on init (before the first network call), and calls `save(...)` after every successful `GET /library`.
   - `LibraryDetailViewModel` reads the individual item from the cached list instead of refetching the whole library — avoids a second empty-state flash when opening detail.

3. **`LoadState` in `HomeViewModel`.**
   - Replace the ad-hoc `isLoading` / `error` flags with a sealed class:
     ```kotlin
     sealed interface LoadState {
       data object Loading : LoadState
       data class Success(val items: List<LibraryItem>, val stale: Boolean) : LoadState
       data class Error(val message: String) : LoadState
     }
     ```
   - `Error` is only emitted after the retry interceptor has exhausted its attempts **and** the cache is empty. Otherwise emit `Success(cachedItems, stale = true)` and show a small non-blocking "Reconnecting…" banner at the top of `HomeScreen`.
   - On `Lifecycle.RESUMED` (observe via `DefaultLifecycleObserver` in `MainActivity`, pass a trigger to `HomeViewModel`), fire an immediate fetch and clear any stale `Error` optimistically — don't wait for the 5 s tick.

**Files touched (in addition to those already listed under Android changes):**
- `android/app/build.gradle.kts` — add `androidx.datastore:datastore-preferences`.
- `data/network/RetryInterceptor.kt` — **new**.
- `data/network/RetrofitInstance.kt` — install `RetryInterceptor`.
- `data/cache/LibraryCache.kt` — **new**.
- `ui/HomeViewModel.kt` — introduce `LoadState`, hydrate from cache, resume-trigger.
- `ui/HomeScreen.kt` — render "Reconnecting…" banner when `Success.stale == true`.
- `MainActivity.kt` — `DefaultLifecycleObserver` to signal resume to `HomeViewModel`.

**Verification:**
- Put the phone in airplane mode → open the app → library renders from cache instantly, banner shows "Reconnecting…", no error dialog.
- Turn airplane mode off → banner disappears on next successful poll, no UI flicker.
- Cold-start with backend down → after 3 retries (~7 s silent retries) UI shows the full error state only because cache is empty.
- Background the app for 10 minutes, then resume → library appears instantly from cache, refresh fires immediately, not after 5 s.

## Web frontend retirement

- Delete `frontend/` directory.
- Remove `localhost:5173` from CORS in `backend/main.py`.
- Update `CLAUDE.md` Development Commands section — drop the Frontend block.
- Update `README.md` if it references the web UI.

## Critical files to modify

**Backend**
- `backend/models/app_settings.py` — `auto_grab` field + DTOs.
- `backend/models/library_item.py` — extend status type; optional `radarr_has_file`.
- `backend/services/library.py` — split `run_library_pipeline` into add-phase / grab-phase.
- `backend/services/radarr.py` — add `list_movies`, `delete_movie`.
- `backend/services/sabnzbd.py` — add `delete_queue_item`.
- `backend/services/sync.py` — **new** — `reconcile_with_radarr`.
- `backend/routers/library.py` — add `/releases`, `/grab`, `/auto-grab`, `/sync`; modify `DELETE` to cascade.
- `backend/routers/webhooks.py` — handle `MovieAdded`, `MovieDelete`, `MovieFileDelete`.
- `backend/main.py` — lifespan starts sync task; CORS update.
- `backend/services/fcm.py` — include `library_item_id` in data payload.

**Android**
- `android/app/build.gradle.kts` — add `navigation-compose` dep.
- `MainActivity.kt` — replace enum nav with `NavHost`; wire `onNewIntent`.
- `ConciergeFirebaseMessagingService.kt` — put item id into deep-link.
- `data/network/ConciergeApiService.kt` — 4 new endpoints.
- `data/models/ScoredRelease.kt` — **new**.
- `data/models/AppSettings.kt` — `auto_grab`.
- `data/ConciergeRepository.kt` — wrap new calls.
- `ui/LibraryDetailScreen.kt` + `ui/LibraryDetailViewModel.kt` — **new**.
- `ui/HomeScreen.kt` — onClick → detail; pull-to-refresh; drop inline action buttons.
- `ui/SettingsScreen.kt` — auto-grab switch; sync-now button.
- `ui/components/LibraryCard.kt` — become tappable, simpler (no action buttons).
- `ui/components/StatusBadge.kt` — handle `idle`.

**Repo**
- Delete `frontend/`.
- `CLAUDE.md`, `README.md`.

## Reused existing code (do not rewrite)

- `radarr.fetch_releases(movie_id)` — used by new `/releases` endpoint.
- `radarr.grab_release(guid, indexer_id)` — used by new `/grab` endpoint.
- `scorer.score_releases(...)` — used by new `/releases` endpoint (pass its full output, including rejected).
- `jellyfin.refresh_library()` — already triggered from Download webhook; nothing to change.
- `fcm.send_download_complete(...)` — extended to carry item id in data payload (not the body).
- Android repository pattern in `ConciergeRepository.kt` — new endpoints follow the same `Result`-wrapping convention.

## Verification

**Backend**
- `pytest backend/tests/` — extend:
  - `test_library.py` — auto_grab=False leaves status `idle` after add; `GET /releases` returns scored + rejected; `POST /grab` transitions to `grabbing`; `POST /auto-grab` kicks off grab-phase; `DELETE` calls Radarr delete_movie.
  - `test_webhooks.py` — `MovieAdded`, `MovieDelete`, `MovieFileDelete` cases.
  - `test_sync.py` — **new** — Radarr-only → inserted; Concierge-only → deleted; hasFile flips.

**Manual end-to-end (from project root)**
1. `uvicorn backend.main:app --reload`.
2. Install the updated Android app on a device/emulator pointing at the backend.
3. Toggle "Automatically grab releases" OFF in Settings.
4. Search a new movie → Add → expect status `idle` in library.
5. Tap the item → verify both "Auto-grab best" and "Interactive search" buttons are visible.
   - First test "Auto-grab best" → expect status `searching` → `grabbing` → `downloading` → `in_library` with no further user input.
   - Add another movie (auto-grab still OFF) → tap "Interactive search" → verify list includes rejected (dimmed) rows with reasons → tap a non-rejected row → expect `grabbing` → `downloading` → `in_library`.
6. In Radarr's own UI, add a different movie → within 30 min (or hit "Sync with Radarr now") → new item appears in Concierge library.
7. In Radarr's UI, delete the movie → item disappears from Concierge on next webhook.
8. On an `in_library` item: tap → "Interactive search" → grab a different release → verify Radarr replaces the file → Jellyfin refresh fires.
9. Delete from detail → confirm dialog → movie vanishes from Concierge AND Radarr AND disk.
10. Trigger a test FCM push → tap notification → app opens to that movie's detail page.

**Rollout**
- `auto_grab` defaults `True`, so existing users are unaffected.
- First run after update: the lifespan reconcile may insert any Radarr movies missing from Concierge (expected; no destructive side effects).
