package com.example.conceirge.data.models

data class ScoredRelease(
    val guid: String,
    val indexer_id: Int,
    val title: String,
    val quality: String,
    val size_bytes: Long,
    val size_gb: Double,
    val seeders: Int,
    val score: Int,
    val rejected: Boolean,
    val rejection_reason: String?,
    val age_hours: Double,
    val indexer: String,
)
