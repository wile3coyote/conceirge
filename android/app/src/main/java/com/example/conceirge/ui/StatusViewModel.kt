package com.example.conceirge.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.conceirge.data.ConciergeRepository
import com.example.conceirge.data.models.ServiceStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

sealed class ServiceCheckState {
    object Checking : ServiceCheckState()
    data class Ok(val version: String?, val latencyMs: Int) : ServiceCheckState()
    data class Err(val detail: String) : ServiceCheckState()
    object NotConfigured : ServiceCheckState()
}

private fun ServiceStatus.toCheckState(): ServiceCheckState = when {
    detail == "API key not configured" -> ServiceCheckState.NotConfigured
    ok -> ServiceCheckState.Ok(version = version, latencyMs = latency_ms ?: 0)
    else -> ServiceCheckState.Err(detail = detail ?: "Unknown error")
}

data class StatusUiState(
    val radarr: ServiceCheckState = ServiceCheckState.Checking,
    val sabnzbd: ServiceCheckState = ServiceCheckState.Checking,
    val jellyfin: ServiceCheckState = ServiceCheckState.Checking,
    val isRefreshing: Boolean = false
)

class StatusViewModel(private val repo: ConciergeRepository) : ViewModel() {

    private val _uiState = MutableStateFlow(StatusUiState())
    val uiState = _uiState.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    radarr = ServiceCheckState.Checking,
                    sabnzbd = ServiceCheckState.Checking,
                    jellyfin = ServiceCheckState.Checking,
                    isRefreshing = true
                )
            }
            repo.getStatus()
                .onSuccess { status ->
                    _uiState.update {
                        it.copy(
                            radarr = status.radarr.toCheckState(),
                            sabnzbd = status.sabnzbd.toCheckState(),
                            jellyfin = status.jellyfin.toCheckState(),
                            isRefreshing = false
                        )
                    }
                }
                .onFailure { e ->
                    val err = ServiceCheckState.Err(e.message ?: "Could not reach backend")
                    _uiState.update {
                        it.copy(
                            radarr = err,
                            sabnzbd = err,
                            jellyfin = err,
                            isRefreshing = false
                        )
                    }
                }
        }
    }
}
