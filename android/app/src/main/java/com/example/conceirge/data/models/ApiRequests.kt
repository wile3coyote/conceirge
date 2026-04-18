package com.example.conceirge.data.models

data class MovieSearchRequest(val query: String)

data class AddToLibraryRequest(
    val tmdb_id: Int,
    val title: String,
    val year: Int,
    val overview: String?,
    val poster_url: String?
)

data class GrabReleaseRequest(val guid: String, val indexer_id: Int)
