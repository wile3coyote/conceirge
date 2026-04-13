package com.example.conceirge.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.conceirge.data.ConciergeRepository
import com.example.conceirge.data.models.LibraryItem
import com.example.conceirge.data.models.MovieSearchResult
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class HomeUiState(
    val searchQuery: String = "",
    val searchResults: List<MovieSearchResult> = emptyList(),
    val isSearching: Boolean = false,
    val searchError: String? = null,
    val library: List<LibraryItem> = emptyList(),
    val libraryError: String? = null,
    val libraryItemIds: Set<Int> = emptySet(), // tmdb_ids already in library
    val actionError: String? = null
)

class HomeViewModel(private val repo: ConciergeRepository) : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState = _uiState.asStateFlow()

    init {
        startLibraryPolling()
    }

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

    private fun startLibraryPolling() {
        viewModelScope.launch {
            while (true) {
                repo.getLibrary()
                    .onSuccess { items ->
                        _uiState.update {
                            it.copy(
                                library = items,
                                libraryItemIds = items.map { i -> i.tmdb_id }.toSet(),
                                libraryError = null
                            )
                        }
                    }
                    .onFailure { e ->
                        _uiState.update { it.copy(libraryError = e.message ?: "Failed to load library") }
                    }
                delay(5_000)
            }
        }
    }

    fun addToLibrary(movie: MovieSearchResult) {
        viewModelScope.launch {
            repo.addToLibrary(movie)
                .onSuccess { item ->
                    _uiState.update { state ->
                        val updated = state.library.toMutableList().also { it.add(0, item) }
                        state.copy(
                            library = updated,
                            libraryItemIds = updated.map { it.tmdb_id }.toSet()
                        )
                    }
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
                    _uiState.update { state ->
                        state.copy(library = state.library.map { if (it.id == id) updated else it })
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
                    _uiState.update { state ->
                        val updated = state.library.filter { it.id != id }
                        state.copy(library = updated, libraryItemIds = updated.map { it.tmdb_id }.toSet())
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
}
