package com.example.conceirge.data.models

data class AppSettings(
    val max_size_gb: Double,
    val preferred_quality: String,
    val avoid_keywords: List<String>,
    val fcm_token: String? = null,
    val updated_at: String
)

data class AppSettingsUpdate(
    val max_size_gb: Double? = null,
    val preferred_quality: String? = null,
    val avoid_keywords: List<String>? = null,
    val fcm_token: String? = null
)
