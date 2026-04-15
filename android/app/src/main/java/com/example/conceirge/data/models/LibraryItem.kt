package com.example.conceirge.data.models

data class LibraryItem(
    val id: Int,
    val tmdb_id: Int,
    val title: String,
    val year: Int,
    val overview: String?,
    val poster_url: String?,
    val status: String, // "searching"|"grabbing"|"downloading"|"downloaded"|"in_library"|"failed"
    val fail_reason: String?,
    val chosen_release_title: String?,
    val chosen_release_size_gb: Double?,
    val chosen_release_quality: String?,
    val created_at: String,
    val updated_at: String
)
