package com.example.conceirge.ui

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.conceirge.data.ConciergeRepository
import com.example.conceirge.data.cache.LibraryCache
import com.example.conceirge.data.models.LibraryItem
import com.example.conceirge.data.models.MovieSearchResult
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

// ---------------------------------------------------------------------------
// Library load state — replaces the ad-hoc isLoading / error / items trio.
// ---------------------------------------------------------------------------

sealed interface LoadState {
    data object Loading : LoadState
    data class Success(val items: List<LibraryItem>, val stale: Boolean) : LoadState
    data class Error(val message: String) : LoadState
}

// ---------------------------------------------------------------------------
// Search / action UI state (unchanged shape, kept separate from LoadState).
// ---------------------------------------------------------------------------

data class HomeUiState(
    val searchQuery: String = "",
    val searchResults: List<MovieSearchResult> = emptyList(),
    val isSearching: Boolean = false,
    val searchError: String? = null,
    val actionError: String? = null,
    // Derived convenience set — kept so callers that read libraryItemIds don't break.
    // It is recomputed whenever loadState transitions to Success.
    val libraryItemIds: Set<Int> = emptySet()
)

// ---------------------------------------------------------------------------
// ViewModel
// ---------------------------------------------------------------------------

class HomeViewModel(
    private val repo: ConciergeRepository,
    // Nullable so the existing MainActivity `remember(repo) { HomeViewModel(repo) }`
    // keeps compiling until the sibling task updates that call site to use the
    // Factory (which passes the real cache via Application context).
    private val cache: LibraryCache? = null
) : ViewModel() {

    // -- Library load state --------------------------------------------------

    private val _loadState = MutableStateFlow<LoadState>(LoadState.Loading)
    val loadState: StateFlow<LoadState> = _loadState.asStateFlow()

    // -- Search / action state -----------------------------------------------

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState = _uiState.asStateFlow()

    // -- Polling job reference (kept so onCleared can cancel it explicitly) --

    private var pollingJob: Job? = null

    // -------------------------------------------------------------------------

    init {
        viewModelScope.launch {
            hydrateFromCache()
            startPolling()
        }
    }

    // ---------------------------------------------------------------------------
    // Cache hydration
    // ---------------------------------------------------------------------------

    /**
     * Loads the DataStore cache before the first network call fires so the user
     * sees their last-known library instantly rather than a loading spinner (or
     * worse, a flash of an error banner).
     */
    private suspend fun hydrateFromCache() {
        val cached = cache?.load() ?: emptyList()
        if (cached.isNotEmpty()) {
            _loadState.value = LoadState.Success(items = cached, stale = true)
            _uiState.update { it.copy(libraryItemIds = cached.map { i -> i.tmdb_id }.toSet()) }
        }
        // If cache is empty we leave _loadState at Loading — the polling loop will
        // resolve it as soon as the first network call completes.
    }

    // ---------------------------------------------------------------------------
    // Polling loop
    // ---------------------------------------------------------------------------

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (true) {
                fetchLibrary()
                delay(5_000)
            }
        }
    }

    /**
     * Single library fetch. Applies the "keep stale on error" rule:
     * - Success  → emit Success(stale = false), persist to cache.
     * - Failure  → if we already have items, stay at Success(stale = true).
     *              If we are still Loading or have no items, emit Error.
     */
    private suspend fun fetchLibrary() {
        repo.getLibrary()
            .onSuccess { items ->
                _loadState.value = LoadState.Success(items = items, stale = false)
                _uiState.update { it.copy(libraryItemIds = items.map { i -> i.tmdb_id }.toSet()) }
                cache?.save(items)
            }
            .onFailure { e ->
                val message = e.message ?: "Failed to load library"
                val current = _loadState.value
                if (current is LoadState.Success && current.items.isNotEmpty()) {
                    // Keep showing cached / previously-fetched data; just flip stale flag.
                    _loadState.value = current.copy(stale = true)
                } else {
                    _loadState.value = LoadState.Error(message)
                }
            }
    }

    // ---------------------------------------------------------------------------
    // Resume integration
    // ---------------------------------------------------------------------------

    /**
     * Called by MainActivity when the activity resumes (via its resumeEvents
     * SharedFlow).  Does two things:
     * 1. Fires an immediate fetch so the library refreshes without waiting for
     *    the next 5-second tick.
     * 2. If the current state is Error but the cache has items, optimistically
     *    transitions to Success(stale = true) to clear the stale error banner
     *    that was left from a previous backgrounded failure.
     */
    fun onResumed() {
        viewModelScope.launch {
            // Optimistic recovery: clear error if cache can show something.
            if (_loadState.value is LoadState.Error) {
                val cached = cache?.load() ?: emptyList()
                if (cached.isNotEmpty()) {
                    _loadState.value = LoadState.Success(items = cached, stale = true)
                    _uiState.update { it.copy(libraryItemIds = cached.map { i -> i.tmdb_id }.toSet()) }
                }
            }
            // Immediate out-of-band fetch (the polling delay is not reset — the
            // loop continues on its own schedule).
            fetchLibrary()
        }
    }

    // ---------------------------------------------------------------------------
    // Search actions (unchanged public API)
    // ---------------------------------------------------------------------------

    fun onQueryChange(q: String) {
        _uiState.update { it.copy(searchQuery = q) }
    }

    fun search() {
        val query = _uiState.value.searchQuery.trim()
        if (query.isEmpty()) return
        viewModelScope.launch {
            _uiState.update { it.copy(isSearching = true, searchError = null, searchResults = emptyList()) }
            repo.searchMovies(query)
                .onSuccess { results ->
                    _uiState.update { it.copy(searchResults = results, isSearching = false) }
                }
                .onFailure { e ->
                    _uiState.update {
                        it.copy(isSearching = false, searchError = e.message ?: "Search failed")
                    }
                }
        }
    }

    fun clearSearch() {
        _uiState.update { it.copy(searchQuery = "", searchResults = emptyList(), searchError = null) }
    }

    // ---------------------------------------------------------------------------
    // Library mutation actions (unchanged public API)
    // ---------------------------------------------------------------------------

    fun addToLibrary(movie: MovieSearchResult) {
        viewModelScope.launch {
            repo.addToLibrary(movie)
                .onSuccess { item ->
                    val current = _loadState.value
                    val existing = if (current is LoadState.Success) current.items else emptyList()
                    val updated = buildList {
                        add(item)
                        addAll(existing)
                    }
                    _loadState.value = LoadState.Success(items = updated, stale = false)
                    _uiState.update { it.copy(libraryItemIds = updated.map { it.tmdb_id }.toSet()) }
                    cache?.save(updated)
                }
                .onFailure { e ->
                    _uiState.update { it.copy(actionError = e.message ?: "Failed to add to library") }
                }
        }
    }

    fun retry(id: Int) {
        viewModelScope.launch {
            repo.retryItem(id)
                .onSuccess { updated ->
                    val current = _loadState.value
                    if (current is LoadState.Success) {
                        val newItems = current.items.map { if (it.id == id) updated else it }
                        _loadState.value = current.copy(items = newItems)
                        cache?.save(newItems)
                    }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(actionError = e.message ?: "Retry failed") }
                }
        }
    }

    fun delete(id: Int) {
        viewModelScope.launch {
            repo.deleteItem(id)
                .onSuccess {
                    val current = _loadState.value
                    if (current is LoadState.Success) {
                        val newItems = current.items.filter { it.id != id }
                        _loadState.value = current.copy(items = newItems)
                        _uiState.update { it.copy(libraryItemIds = newItems.map { it.tmdb_id }.toSet()) }
                        cache?.save(newItems)
                    }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(actionError = e.message ?: "Delete failed") }
                }
        }
    }

    fun clearActionError() {
        _uiState.update { it.copy(actionError = null) }
    }

    // ---------------------------------------------------------------------------
    // Lifecycle
    // ---------------------------------------------------------------------------

    override fun onCleared() {
        super.onCleared()
        pollingJob?.cancel()
    }

    // ---------------------------------------------------------------------------
    // Factory — use this when constructing via ViewModelProvider so that the
    // Application context is available for LibraryCache.
    //
    // Wiring in MainActivity (sibling task):
    //   val vm = remember(repo) {
    //       ViewModelProvider(
    //           LocalViewModelStoreOwner.current!!,
    //           HomeViewModel.Factory(application, repo)
    //       )[HomeViewModel::class.java]
    //   }
    //
    // Or, once Hilt is adopted, replace with @HiltViewModel injection.
    // ---------------------------------------------------------------------------

    class Factory(
        private val application: Application,
        private val repo: ConciergeRepository
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            require(modelClass == HomeViewModel::class.java) {
                "Factory only creates HomeViewModel"
            }
            return HomeViewModel(
                repo = repo,
                cache = LibraryCache(application.applicationContext)
            ) as T
        }
    }
}
