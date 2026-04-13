package com.example.conceirge.data.models

data class MovieSearchResult(
    val tmdb_id: Int,
    val title: String,
    val year: Int,
    val overview: String?,
    val poster_url: String?
)
