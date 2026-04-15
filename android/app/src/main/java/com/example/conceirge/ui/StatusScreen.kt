package com.example.conceirge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.SuggestionChipDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StatusScreen(
    viewModel: StatusViewModel,
    backendUrl: String,
    onBack: () -> Unit
) {
    val state by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Service Status") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(
                        onClick = viewModel::refresh,
                        enabled = !state.isRefreshing
                    ) {
                        if (state.isRefreshing) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                strokeWidth = 2.dp
                            )
                        } else {
                            Icon(Icons.Filled.Refresh, contentDescription = "Refresh")
                        }
                    }
                }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = backendUrl,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 4.dp)
            )

            ServiceCard(name = "Radarr",    state = state.radarr)
            ServiceCard(name = "SABnzbd",   state = state.sabnzbd)
            ServiceCard(name = "Jellyfin",  state = state.jellyfin)
        }
    }
}

@Composable
private fun ServiceCard(name: String, state: ServiceCheckState) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = name,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(4.dp))
                when (state) {
                    is ServiceCheckState.Ok -> {
                        val meta = buildString {
                            state.version?.let { append("v$it") }
                            if (isNotEmpty()) append("  ·  ")
                            append("${state.latencyMs} ms")
                        }
                        Text(
                            text = meta,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    is ServiceCheckState.Err -> Text(
                        text = state.detail,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                    ServiceCheckState.NotConfigured -> Text(
                        text = "Set API key in server .env",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    ServiceCheckState.Checking -> Unit
                }
            }

            Spacer(modifier = Modifier.width(12.dp))
            StatusChip(state)
        }
    }
}

@Composable
private fun StatusChip(state: ServiceCheckState) {
    when (state) {
        ServiceCheckState.Checking -> SuggestionChip(
            onClick = {},
            label = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(12.dp),
                        strokeWidth = 1.5.dp,
                        color = Color(0xFFB45309) // amber-700
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Checking")
                }
            },
            colors = SuggestionChipDefaults.suggestionChipColors(
                containerColor = Color(0xFFFEF3C7), // amber-100
                labelColor = Color(0xFF92400E)       // amber-800
            )
        )
        is ServiceCheckState.Ok -> SuggestionChip(
            onClick = {},
            label = { Text("Connected") },
            colors = SuggestionChipDefaults.suggestionChipColors(
                containerColor = Color(0xFFDCFCE7), // green-100
                labelColor = Color(0xFF166534)       // green-800
            )
        )
        is ServiceCheckState.Err -> SuggestionChip(
            onClick = {},
            label = { Text("Error") },
            colors = SuggestionChipDefaults.suggestionChipColors(
                containerColor = Color(0xFFFEE2E2), // red-100
                labelColor = Color(0xFF991B1B)       // red-800
            )
        )
        ServiceCheckState.NotConfigured -> SuggestionChip(
            onClick = {},
            label = { Text("Not set up") },
            colors = SuggestionChipDefaults.suggestionChipColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant,
                labelColor = MaterialTheme.colorScheme.onSurfaceVariant
            )
        )
    }
}
