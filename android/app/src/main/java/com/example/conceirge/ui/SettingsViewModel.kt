package com.example.conceirge.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.conceirge.data.ConciergeRepository
import com.example.conceirge.data.models.AppSettings
import com.example.conceirge.data.models.AppSettingsUpdate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsUiState(
    val isLoading: Boolean = true,
    val isSaving: Boolean = false,
    val maxSizeGb: String = "40",
    val preferredQuality: String = "2160p",
    val avoidKeywords: String = "BRRip, CAM, TS, HDCAM",
    val saveError: String? = null,
    val saveSuccess: Boolean = false
)

class SettingsViewModel(private val repo: ConciergeRepository) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState = _uiState.asStateFlow()

    init {
        loadSettings()
    }

    private fun loadSettings() {
        viewModelScope.launch {
            repo.getSettings()
                .onSuccess { s ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            maxSizeGb = s.max_size_gb.toInt().toString(),
                            preferredQuality = s.preferred_quality,
                            avoidKeywords = s.avoid_keywords.joinToString(", ")
                        )
                    }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(isLoading = false, saveError = e.message ?: "Failed to load settings") }
                }
        }
    }

    fun onMaxSizeChange(v: String) = _uiState.update { it.copy(maxSizeGb = v) }
    fun onQualityChange(v: String) = _uiState.update { it.copy(preferredQuality = v) }
    fun onKeywordsChange(v: String) = _uiState.update { it.copy(avoidKeywords = v) }
    fun clearError() = _uiState.update { it.copy(saveError = null) }
    fun clearSuccess() = _uiState.update { it.copy(saveSuccess = false) }

    fun save() {
        val state = _uiState.value
        val maxSize = state.maxSizeGb.toDoubleOrNull()
        if (maxSize == null || maxSize <= 0) {
            _uiState.update { it.copy(saveError = "Max size must be a positive number") }
            return
        }
        val keywords = state.avoidKeywords
            .split(",")
            .map { it.trim() }
            .filter { it.isNotEmpty() }

        viewModelScope.launch {
            _uiState.update { it.copy(isSaving = true, saveError = null) }
            repo.updateSettings(
                AppSettingsUpdate(
                    max_size_gb = maxSize,
                    preferred_quality = state.preferredQuality,
                    avoid_keywords = keywords
                )
            )
                .onSuccess { saved ->
                    _uiState.update {
                        it.copy(
                            isSaving = false,
                            saveSuccess = true,
                            maxSizeGb = saved.max_size_gb.toInt().toString(),
                            preferredQuality = saved.preferred_quality,
                            avoidKeywords = saved.avoid_keywords.joinToString(", ")
                        )
                    }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(isSaving = false, saveError = e.message ?: "Failed to save") }
                }
        }
    }
}
