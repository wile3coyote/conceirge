package com.example.conceirge.ui

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.conceirge.data.ConciergeRepository
import com.example.conceirge.data.UrlStore
import com.example.conceirge.data.cache.LibraryCache
import com.example.conceirge.data.models.LibraryItem
import com.example.conceirge.data.models.ScoredRelease
import com.example.conceirge.data.network.RetrofitInstance
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

// ---------------------------------------------------------------------------
// State types
// ---------------------------------------------------------------------------

sealed interface ReleasesState {
    data object Hidden : ReleasesState
    data object Loading : ReleasesState
    data class Success(val items: List<ScoredRelease>) : ReleasesState
    data class Error(val message: String) : ReleasesState
}

sealed interface ActionState {
    data object Idle : ActionState
    data object InFlight : ActionState
    data class Error(val message: String) : ActionState
}

// ---------------------------------------------------------------------------
// ViewModel
// ---------------------------------------------------------------------------

class LibraryDetailViewModel(
    private val libraryItemId: Int,
    private val repository: ConciergeRepository,
    private val cache: LibraryCache,
) : ViewModel() {

    private val _item = MutableStateFlow<LibraryItem?>(null)
    val item: StateFlow<LibraryItem?> = _item.asStateFlow()

    private val _releases = MutableStateFlow<ReleasesState>(ReleasesState.Hidden)
    val releases: StateFlow<ReleasesState> = _releases.asStateFlow()

    private val _actionState = MutableStateFlow<ActionState>(ActionState.Idle)
    val actionState: StateFlow<ActionState> = _actionState.asStateFlow()

    /**
     * Reads from LibraryCache first for instant display, then fetches a fresh
     * list from the repository and plucks the matching item.
     */
    fun loadItem() {
        viewModelScope.launch {
            // Seed from cache immediately so the UI has something to show.
            val cached = cache.load()
            cached.firstOrNull { it.id == libraryItemId }?.let { cachedItem ->
                _item.value = cachedItem
            }

            // Background refresh from the network.
            repository.getLibrary()
                .onSuccess { items ->
                    cache.save(items)
                    items.firstOrNull { it.id == libraryItemId }?.let { fresh ->
                        _item.value = fresh
                    }
                }
                // Silently ignore network errors when we already have a cached value.
                .onFailure { e ->
                    if (_item.value == null) {
                        // No cache hit and network failed — surface the error via actionState
                        // so the screen can show something rather than an eternal spinner.
                        _actionState.value = ActionState.Error(
                            e.message ?: "Failed to load item"
                        )
                    }
                }
        }
    }

    /**
     * Fetches the scored release list on demand. Safe to call multiple times;
     * each call resets to Loading and then resolves to Success or Error.
     */
    fun loadReleases() {
        viewModelScope.launch {
            _releases.value = ReleasesState.Loading
            repository.getReleases(libraryItemId)
                .onSuccess { list ->
                    _releases.value = ReleasesState.Success(list)
                }
                .onFailure { e ->
                    _releases.value = ReleasesState.Error(e.message ?: "Failed to load releases")
                }
        }
    }

    /**
     * Grabs a specific release by GUID and indexer ID. Callers pass the
     * navigate-back callback directly so the screen can dismiss itself on success.
     */
    fun grab(guid: String, indexerId: Int, onSuccess: () -> Unit = {}) {
        viewModelScope.launch {
            _actionState.value = ActionState.InFlight
            repository.grabRelease(libraryItemId, guid, indexerId)
                .onSuccess {
                    _actionState.value = ActionState.Idle
                    onSuccess()
                }
                .onFailure { e ->
                    _actionState.value = ActionState.Error(e.message ?: "Grab failed")
                }
        }
    }

    /**
     * Triggers the backend's auto-grab logic (best-scored non-rejected release).
     */
    fun autoGrab() {
        viewModelScope.launch {
            _actionState.value = ActionState.InFlight
            repository.autoGrab(libraryItemId)
                .onSuccess {
                    _actionState.value = ActionState.Idle
                    // Refresh item so the status badge updates immediately.
                    loadItem()
                }
                .onFailure { e ->
                    _actionState.value = ActionState.Error(e.message ?: "Auto-grab failed")
                }
        }
    }

    /**
     * Deletes the library item (movie + files via Radarr). Invokes [onSuccess]
     * on the calling coroutine's thread after a successful DELETE so the screen
     * can navigate back.
     */
    fun delete(onSuccess: () -> Unit) {
        viewModelScope.launch {
            _actionState.value = ActionState.InFlight
            repository.deleteItem(libraryItemId)
                .onSuccess {
                    _actionState.value = ActionState.Idle
                    onSuccess()
                }
                .onFailure { e ->
                    _actionState.value = ActionState.Error(e.message ?: "Delete failed")
                }
        }
    }

    /** Clears a transient error so the UI stops showing it after acknowledgement. */
    fun clearActionError() {
        if (_actionState.value is ActionState.Error) {
            _actionState.value = ActionState.Idle
        }
    }

    // ---------------------------------------------------------------------------
    // Factory
    // ---------------------------------------------------------------------------

    class Factory(
        private val libraryItemId: Int,
        private val application: Application,
    ) : ViewModelProvider.Factory {

        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            require(modelClass.isAssignableFrom(LibraryDetailViewModel::class.java)) {
                "Unknown ViewModel class: ${modelClass.name}"
            }
            val baseUrl = UrlStore.getUrl(application)
                ?: "http://10.0.2.2:8000"
            val api = RetrofitInstance.create(baseUrl)
            val repository = ConciergeRepository(api)
            val cache = LibraryCache(application)
            return LibraryDetailViewModel(libraryItemId, repository, cache) as T
        }
    }
}
