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
    val download_id: String?,
    val download_progress: Double?, // 0–100, fetched live from SABnzbd; null when not downloading
    val radarr_has_file: Boolean = false,
    val created_at: String,
    val updated_at: String
)
