package com.example.conceirge.data.network

import com.example.conceirge.data.models.AddToLibraryRequest
import com.example.conceirge.data.models.AppSettings
import com.example.conceirge.data.models.AppSettingsUpdate
import com.example.conceirge.data.models.GrabReleaseRequest
import com.example.conceirge.data.models.LibraryItem
import com.example.conceirge.data.models.MovieSearchRequest
import com.example.conceirge.data.models.MovieSearchResult
import com.example.conceirge.data.models.ScoredRelease
import com.example.conceirge.data.models.SystemStatus
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path

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

    @GET("settings")
    suspend fun getSettings(): AppSettings

    @PUT("settings")
    suspend fun updateSettings(@Body update: AppSettingsUpdate): AppSettings

    @GET("status")
    suspend fun getStatus(): SystemStatus

    @GET("library/{id}/releases")
    suspend fun getReleases(@Path("id") id: Int): List<ScoredRelease>

    @POST("library/{id}/grab")
    suspend fun grabRelease(@Path("id") id: Int, @Body body: GrabReleaseRequest): Response<Unit>

    @POST("library/{id}/auto-grab")
    suspend fun autoGrab(@Path("id") id: Int): Response<Unit>

    @POST("library/sync")
    suspend fun syncLibrary(): Response<Unit>
}
