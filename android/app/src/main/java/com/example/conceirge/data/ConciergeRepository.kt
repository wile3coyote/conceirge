package com.example.conceirge.data

import com.example.conceirge.data.models.AddToLibraryRequest
import com.example.conceirge.data.models.AppSettings
import com.example.conceirge.data.models.AppSettingsUpdate
import com.example.conceirge.data.models.GrabReleaseRequest
import com.example.conceirge.data.models.LibraryItem
import com.example.conceirge.data.models.MovieSearchRequest
import com.example.conceirge.data.models.MovieSearchResult
import com.example.conceirge.data.models.ScoredRelease
import com.example.conceirge.data.models.SystemStatus
import com.example.conceirge.data.network.ConciergeApiService

class ConciergeRepository(private val api: ConciergeApiService) {

    suspend fun searchMovies(query: String): Result<List<MovieSearchResult>> =
        runCatching { api.searchMovies(MovieSearchRequest(query)) }

    suspend fun getLibrary(): Result<List<LibraryItem>> =
        runCatching { api.getLibrary() }

    suspend fun addToLibrary(movie: MovieSearchResult): Result<LibraryItem> =
        runCatching {
            api.addToLibrary(
                AddToLibraryRequest(
                    tmdb_id = movie.tmdb_id,
                    title = movie.title,
                    year = movie.year,
                    overview = movie.overview,
                    poster_url = movie.poster_url
                )
            )
        }

    suspend fun retryItem(id: Int): Result<LibraryItem> =
        runCatching { api.retryLibraryItem(id) }

    suspend fun deleteItem(id: Int): Result<Unit> =
        runCatching { api.deleteLibraryItem(id); Unit }

    suspend fun getSettings(): Result<AppSettings> =
        runCatching { api.getSettings() }

    suspend fun updateSettings(update: AppSettingsUpdate): Result<AppSettings> =
        runCatching { api.updateSettings(update) }

    suspend fun getStatus(): Result<SystemStatus> =
        runCatching { api.getStatus() }

    suspend fun getReleases(id: Int): Result<List<ScoredRelease>> =
        runCatching { api.getReleases(id) }

    suspend fun grabRelease(id: Int, guid: String, indexerId: Int): Result<Unit> =
        runCatching {
            val response = api.grabRelease(id, GrabReleaseRequest(guid, indexerId))
            if (!response.isSuccessful) {
                throw RuntimeException("HTTP ${response.code()}")
            }
        }

    suspend fun autoGrab(id: Int): Result<Unit> =
        runCatching {
            val response = api.autoGrab(id)
            if (!response.isSuccessful) {
                throw RuntimeException("HTTP ${response.code()}")
            }
        }

    suspend fun syncLibrary(): Result<Unit> =
        runCatching {
            val response = api.syncLibrary()
            if (!response.isSuccessful) {
                throw RuntimeException("HTTP ${response.code()}")
            }
        }
}
