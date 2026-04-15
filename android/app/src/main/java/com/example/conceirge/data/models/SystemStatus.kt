package com.example.conceirge.data.models

data class ServiceStatus(
    val ok: Boolean,
    val version: String?,
    val latency_ms: Int?,
    val detail: String?
)

data class SystemStatus(
    val radarr: ServiceStatus,
    val sabnzbd: ServiceStatus,
    val jellyfin: ServiceStatus
)
