package com.example.conceirge.data.network

import com.example.conceirge.data.models.AddToLibraryRequest
import com.example.conceirge.data.models.LibraryItem
import com.example.conceirge.data.models.MovieSearchRequest
import com.example.conceirge.data.models.MovieSearchResult
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
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
}
