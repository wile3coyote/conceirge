package com.example.conceirge.data.models

data class AppSettings(
    val max_size_gb: Double,
    val preferred_quality: String, // "2160p" | "1080p"
    val avoid_keywords: List<String>,
    val updated_at: String
)

data class AppSettingsUpdate(
    val max_size_gb: Double? = null,
    val preferred_quality: String? = null,
    val avoid_keywords: List<String>? = null
)
