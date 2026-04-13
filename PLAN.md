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

## Android App — Phase 3 Plan

### Goal
Build the Android UI to match the web frontend: search for movies, add them to the library with one tap, and watch status update in real time. The app talks directly to the same FastAPI backend over the local network.

### Architecture Decisions

| Concern | Choice | Reason |
|---|---|---|
| Network client | Retrofit 2 + OkHttp | Industry standard, clean interface, easy mock for tests |
| JSON parsing | Gson | Zero extra config with Retrofit |
| Image loading | Coil 3 | Compose-native, async, disk cache |
| State management | ViewModel + StateFlow | Lifecycle-safe, first-class Compose integration |
| DI | Manual (no Hilt) | Single screen, no need for Hilt complexity |
| Coroutines | kotlinx-coroutines-android | Structured concurrency, `.repeatOnLifecycle` for polling |
| Architecture | Single-screen, one ViewModel, one Repository | Matches scope of the app |

### Network Notes

- Backend runs on the **local network**, not HTTPS — cleartext HTTP must be explicitly allowed in `AndroidManifest.xml` via `android:usesCleartextTraffic="true"` or a network security config.
- Base URL **cannot be `localhost`** from a real device — must be the host machine's LAN IP (e.g., `http://192.168.x.x:8000`). Store it in `local.properties` and inject via `BuildConfig` so it is not hardcoded.
- CORS: the backend currently only allows `localhost:5173`. A backend config change is needed (or `*`) to accept requests from the Android client.

---

### Step-by-Step Implementation

#### Step 1 — Add Dependencies

Add to `android/gradle/libs.versions.toml`:

```toml
[versions]
# add these
retrofit = "2.11.0"
okhttp = "4.12.0"
coil = "3.1.0"
lifecycleViewModel = "2.8.7"
coroutines = "1.8.0"

[libraries]
# add these
retrofit = { group = "com.squareup.retrofit2", name = "retrofit", version.ref = "retrofit" }
retrofit-converter-gson = { group = "com.squareup.retrofit2", name = "converter-gson", version.ref = "retrofit" }
okhttp-logging = { group = "com.squareup.okhttp3", name = "logging-interceptor", version.ref = "okhttp" }
coil-compose = { group = "io.coil-kt.coil3", name = "coil-compose", version.ref = "coil" }
coil-network-okhttp = { group = "io.coil-kt.coil3", name = "coil-network-okhttp", version.ref = "coil" }
lifecycle-viewmodel-compose = { group = "androidx.lifecycle", name = "lifecycle-viewmodel-compose", version.ref = "lifecycleViewModel" }
kotlinx-coroutines-android = { group = "org.jetbrains.kotlinx", name = "kotlinx-coroutines-android", version.ref = "coroutines" }
```

Add to `android/app/build.gradle.kts` → `dependencies {}`:
```kotlin
implementation(libs.retrofit)
implementation(libs.retrofit.converter.gson)
implementation(libs.okhttp.logging)
implementation(libs.coil.compose)
implementation(libs.coil.network.okhttp)
implementation(libs.lifecycle.viewmodel.compose)
implementation(libs.kotlinx.coroutines.android)
```

Add to `android/app/build.gradle.kts` → `android { defaultConfig {} }`:
```kotlin
buildConfigField("String", "BASE_URL", "\"${properties["concierge.base.url"] ?: "http://10.0.2.2:8000"}\"")
```
(reads `concierge.base.url` from `local.properties`; falls back to emulator localhost)

Enable `buildConfig = true` in `android { buildFeatures {} }`.

---

#### Step 2 — Network Security Config + Manifest

Create `android/app/src/main/res/xml/network_security_config.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">192.168.0.0/16</domain>
        <domain includeSubdomains="true">10.0.0.0/8</domain>
        <domain includeSubdomains="true">10.0.2.2</domain><!-- emulator localhost -->
    </domain-config>
</network-security-config>
```

In `AndroidManifest.xml`:
- Add `<uses-permission android:name="android.permission.INTERNET" />`
- Add `android:networkSecurityConfig="@xml/network_security_config"` to `<application>`

---

#### Step 3 — Data Models

Create `com/example/conceirge/data/models/`:

**`MovieSearchResult.kt`**
```kotlin
data class MovieSearchResult(
    val tmdb_id: Int,
    val title: String,
    val year: Int,
    val overview: String?,
    val poster_url: String?
)
```

**`LibraryItem.kt`**
```kotlin
data class LibraryItem(
    val id: Int,
    val tmdb_id: Int,
    val title: String,
    val year: Int,
    val overview: String?,
    val poster_url: String?,
    val status: String,               // "searching"|"grabbing"|"downloading"|"downloaded"|"in_library"|"failed"
    val fail_reason: String?,
    val chosen_release_title: String?,
    val chosen_release_size_gb: Double?,
    val chosen_release_quality: String?,
    val created_at: String,
    val updated_at: String
)
```

**`ApiRequests.kt`**
```kotlin
data class MovieSearchRequest(val query: String)
data class AddToLibraryRequest(
    val tmdb_id: Int,
    val title: String,
    val year: Int,
    val overview: String?,
    val poster_url: String?
)
```

---

#### Step 4 — Retrofit Service Interface

Create `com/example/conceirge/data/network/ConciergeApiService.kt`:
```kotlin
interface ConciergeApiService {
    @POST("movies/search")
    suspend fun searchMovies(@Body request: MovieSearchRequest): List<MovieSearchResult>

    @GET("library")
    suspend fun getLibrary(): List<LibraryItem>

    @POST("library")
    suspend fun addToLibrary(@Body request: AddToLibraryRequest): LibraryItem

    @POST("library/{id}/retry")
    suspend fun retryLibraryItem(@Path("id") id: Int): LibraryItem

    @DELETE("library/{id}")
    suspend fun deleteLibraryItem(@Path("id") id: Int): Response<Unit>
}
```

Create `com/example/conceirge/data/network/RetrofitInstance.kt`:
```kotlin
object RetrofitInstance {
    fun create(baseUrl: String): ConciergeApiService {
        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BODY }
        val client = OkHttpClient.Builder().addInterceptor(logging).build()
        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ConciergeApiService::class.java)
    }
}
```

---

#### Step 5 — Repository

Create `com/example/conceirge/data/ConciergeRepository.kt`:
```kotlin
class ConciergeRepository(private val api: ConciergeApiService) {
    suspend fun searchMovies(query: String): Result<List<MovieSearchResult>> =
        runCatching { api.searchMovies(MovieSearchRequest(query)) }

    suspend fun getLibrary(): Result<List<LibraryItem>> =
        runCatching { api.getLibrary() }

    suspend fun addToLibrary(movie: MovieSearchResult): Result<LibraryItem> =
        runCatching {
            api.addToLibrary(AddToLibraryRequest(movie.tmdb_id, movie.title, movie.year, movie.overview, movie.poster_url))
        }

    suspend fun retryItem(id: Int): Result<LibraryItem> =
        runCatching { api.retryLibraryItem(id) }

    suspend fun deleteItem(id: Int): Result<Unit> =
        runCatching { api.deleteLibraryItem(id); Unit }
}
```

---

#### Step 6 — ViewModel

Create `com/example/conceirge/ui/HomeViewModel.kt`:

```kotlin
data class HomeUiState(
    val searchQuery: String = "",
    val searchResults: List<MovieSearchResult> = emptyList(),
    val isSearching: Boolean = false,
    val searchError: String? = null,
    val library: List<LibraryItem> = emptyList(),
    val isLibraryLoading: Boolean = false,
    val libraryError: String? = null,
    val libraryItemIds: Set<Int> = emptySet(),   // tmdb_ids already in library
    val actionError: String? = null
)

class HomeViewModel(private val repo: ConciergeRepository) : ViewModel() {
    val uiState = MutableStateFlow(HomeUiState())

    init { startLibraryPolling() }

    fun onQueryChange(q: String) { uiState.update { it.copy(searchQuery = q) } }

    fun search() { /* launch coroutine, set isSearching, call repo.searchMovies */ }

    private fun startLibraryPolling() {
        viewModelScope.launch {
            while (true) {
                repo.getLibrary().onSuccess { items ->
                    uiState.update { it.copy(library = items, libraryItemIds = items.map { i -> i.tmdb_id }.toSet()) }
                }
                delay(5_000)
            }
        }
    }

    fun addToLibrary(movie: MovieSearchResult) { /* launch coroutine, call repo.addToLibrary */ }
    fun retry(id: Int) { /* launch coroutine, call repo.retryItem */ }
    fun delete(id: Int) { /* launch coroutine, call repo.deleteItem */ }
    fun clearActionError() { uiState.update { it.copy(actionError = null) } }
}
```

---

#### Step 7 — UI Composables

Create `com/example/conceirge/ui/components/`:

**`SearchBar.kt`** — Text input + Search button. Emits query on submit.

**`MovieCard.kt`** — Poster image (Coil `AsyncImage`), title, year, overview (1 line), "Add" button. Button is disabled if `movie.tmdb_id in libraryItemIds`.

**`LibraryCard.kt`** — Poster, title, year, `StatusBadge`, release info (quality/size) if available, fail reason if failed, "Retry" / "Delete" icon buttons.

**`StatusBadge.kt`** — Color-coded chip:
| Status | Color | Label |
|---|---|---|
| searching | Blue | Searching |
| grabbing | Orange | Grabbing |
| downloading | Amber | Downloading |
| downloaded | Teal | Downloaded |
| in_library | Green | In Library |
| failed | Red | Failed |

**`HomeScreen.kt`** — Two-section layout:
1. **Search section** — `SearchBar` + `LazyColumn` of `MovieCard`s (hidden when query is empty or no results)
2. **Library section** — Header + `LazyColumn` of `LibraryCard`s

---

#### Step 8 — Wire Up MainActivity

```kotlin
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val api = RetrofitInstance.create(BuildConfig.BASE_URL)
        val repo = ConciergeRepository(api)
        val viewModel = HomeViewModel(repo)
        setContent {
            ConciergeTheme {
                HomeScreen(viewModel = viewModel)
            }
        }
    }
}
```

---

#### Step 9 — Backend CORS Fix

The backend CORS currently only allows `http://localhost:5173`. Android requests come from a different origin. Update `backend/main.py`:

```python
allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "*",   # or restrict to LAN subnet
]
```

Or, for tighter security, read `ALLOWED_ORIGINS` from `.env` and allow the Android client's origin explicitly.

---

### File Map

```
android/app/src/main/java/com/example/conceirge/
├── MainActivity.kt                          # wire ViewModel → HomeScreen
├── data/
│   ├── models/
│   │   ├── MovieSearchResult.kt
│   │   ├── LibraryItem.kt
│   │   └── ApiRequests.kt
│   ├── network/
│   │   ├── ConciergeApiService.kt           # Retrofit interface
│   │   └── RetrofitInstance.kt              # OkHttp + Retrofit factory
│   └── ConciergeRepository.kt              # wraps API calls in Result<T>
└── ui/
    ├── HomeViewModel.kt                     # StateFlow UiState + coroutine actions
    ├── HomeScreen.kt                        # top-level composable
    └── components/
        ├── SearchBar.kt
        ├── MovieCard.kt
        ├── LibraryCard.kt
        └── StatusBadge.kt
android/app/src/main/res/xml/
└── network_security_config.xml             # allow cleartext to LAN IPs
```

### Out of Scope (Android v1)

- Authentication / settings screen for configuring the backend URL from within the app (use `local.properties` for now)
- Offline mode / local caching
- Push notifications on download completion
- Dark-mode-specific theming (Material3 handles this automatically)

---
*Last updated: 2026-04-13*
