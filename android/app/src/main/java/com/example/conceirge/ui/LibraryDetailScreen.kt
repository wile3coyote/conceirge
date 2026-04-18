package com.example.conceirge.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Snackbar
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import coil3.compose.AsyncImage
import com.example.conceirge.data.models.LibraryItem
import com.example.conceirge.data.models.ScoredRelease
import com.example.conceirge.ui.components.StatusBadge

// ---------------------------------------------------------------------------
// Screen entry-point
// ---------------------------------------------------------------------------

@Composable
fun LibraryDetailScreen(
    libraryItemId: Int,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val vm: LibraryDetailViewModel = viewModel(
        key = "library_detail_$libraryItemId",
        factory = LibraryDetailViewModel.Factory(
            libraryItemId = libraryItemId,
            application = context.applicationContext as android.app.Application,
        )
    )

    val item by vm.item.collectAsState()
    val releasesState by vm.releases.collectAsState()
    val actionState by vm.actionState.collectAsState()

    val snackbarHostState = remember { SnackbarHostState() }

    // Initial load — cache-first then network refresh.
    LaunchedEffect(libraryItemId) {
        vm.loadItem()
    }

    // Surface ActionState.Error in a Snackbar and auto-clear it.
    LaunchedEffect(actionState) {
        val state = actionState
        if (state is ActionState.Error) {
            snackbarHostState.showSnackbar(state.message)
            vm.clearActionError()
        }
    }

    LibraryDetailContent(
        item = item,
        releasesState = releasesState,
        actionState = actionState,
        snackbarHostState = snackbarHostState,
        onBack = onBack,
        onAutoGrab = vm::autoGrab,
        onLoadReleases = vm::loadReleases,
        onGrab = { guid, indexerId -> vm.grab(guid, indexerId, onSuccess = onBack) },
        onDelete = { vm.delete(onSuccess = onBack) },
    )
}

// ---------------------------------------------------------------------------
// Stateless content composable (easy to Preview)
// ---------------------------------------------------------------------------

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LibraryDetailContent(
    item: LibraryItem?,
    releasesState: ReleasesState,
    actionState: ActionState,
    snackbarHostState: SnackbarHostState,
    onBack: () -> Unit,
    onAutoGrab: () -> Unit,
    onLoadReleases: () -> Unit,
    onGrab: (guid: String, indexerId: Int) -> Unit,
    onDelete: () -> Unit,
) {
    // Delete confirmation dialog state.
    var showDeleteDialog by rememberSaveable { mutableStateOf(false) }

    val actionsEnabled = actionState !is ActionState.InFlight

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    item?.let { Text("${it.title} (${it.year})") } ?: Text("Loading...")
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back"
                        )
                    }
                }
            )
        },
        snackbarHost = {
            SnackbarHost(snackbarHostState) { data ->
                Snackbar(snackbarData = data)
            }
        }
    ) { innerPadding ->
        if (item == null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
        ) {
            // ----------------------------------------------------------------
            // Header pane
            // ----------------------------------------------------------------
            item {
                HeaderPane(item = item)
            }

            // ----------------------------------------------------------------
            // Action pane
            // ----------------------------------------------------------------
            item {
                ActionPane(
                    item = item,
                    actionsEnabled = actionsEnabled,
                    actionState = actionState,
                    onAutoGrab = onAutoGrab,
                    onLoadReleases = onLoadReleases,
                    onDeleteClick = { showDeleteDialog = true },
                )
            }

            // ----------------------------------------------------------------
            // Release list (Hidden → nothing; Loading → spinner; else rows)
            // ----------------------------------------------------------------
            when (val rs = releasesState) {
                is ReleasesState.Hidden -> { /* nothing to show */ }

                is ReleasesState.Loading -> {
                    item {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(32.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator()
                        }
                    }
                }

                is ReleasesState.Error -> {
                    item {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = rs.message,
                                color = MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.weight(1f)
                            )
                            IconButton(onClick = onLoadReleases) {
                                Icon(
                                    imageVector = Icons.Filled.Refresh,
                                    contentDescription = "Retry loading releases"
                                )
                            }
                        }
                    }
                }

                is ReleasesState.Success -> {
                    item {
                        Text(
                            text = "Available Releases (${rs.items.size})",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.SemiBold,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                        )
                    }
                    items(rs.items, key = { it.guid }) { release ->
                        ReleaseRow(
                            release = release,
                            onGrab = onGrab,
                        )
                    }
                    item { Spacer(modifier = Modifier.height(16.dp)) }
                }
            }
        }
    }

    // Delete confirmation dialog
    if (showDeleteDialog) {
        item?.let { safeItem ->
            AlertDialog(
                onDismissRequest = { showDeleteDialog = false },
                title = { Text("Delete ${safeItem.title} (${safeItem.year})?") },
                text = {
                    Text("This removes the movie and its files from Radarr.")
                },
                confirmButton = {
                    TextButton(
                        onClick = {
                            showDeleteDialog = false
                            onDelete()
                        },
                        colors = ButtonDefaults.textButtonColors(
                            contentColor = MaterialTheme.colorScheme.error
                        )
                    ) {
                        Text("Delete")
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showDeleteDialog = false }) {
                        Text("Cancel")
                    }
                }
            )
        }
    }
}

// ---------------------------------------------------------------------------
// Header pane
// ---------------------------------------------------------------------------

@Composable
private fun HeaderPane(item: LibraryItem) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.Top
        ) {
            AsyncImage(
                model = item.poster_url,
                contentDescription = "${item.title} poster",
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(width = 90.dp, height = 135.dp)
                    .clip(RoundedCornerShape(6.dp))
            )
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = item.title,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = item.year.toString(),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(8.dp))
                StatusBadge(status = item.status)

                // Release info when available
                val releaseInfo = buildString {
                    item.chosen_release_quality?.let { append(it) }
                    item.chosen_release_size_gb?.let {
                        if (isNotEmpty()) append(" · ")
                        append("%.1f GB".format(it))
                    }
                }
                if (releaseInfo.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = releaseInfo,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }

        // Overview
        item.overview?.takeIf { it.isNotBlank() }?.let { overview ->
            Text(
                text = overview,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
            )
        }

        Spacer(modifier = Modifier.height(8.dp))
    }
}

// ---------------------------------------------------------------------------
// Action pane — branches on item.status
// ---------------------------------------------------------------------------

@Composable
private fun ActionPane(
    item: LibraryItem,
    actionsEnabled: Boolean,
    actionState: ActionState,
    onAutoGrab: () -> Unit,
    onLoadReleases: () -> Unit,
    onDeleteClick: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        when (item.status) {
            "idle" -> {
                // Two primary action buttons side by side
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Button(
                        onClick = onAutoGrab,
                        enabled = actionsEnabled,
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Auto-grab best")
                    }
                    Button(
                        onClick = onLoadReleases,
                        enabled = actionsEnabled,
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Interactive search")
                    }
                }
                OutlinedButton(
                    onClick = onDeleteClick,
                    enabled = actionsEnabled,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Delete")
                }
            }

            "searching", "grabbing", "downloading", "downloaded" -> {
                // Progress indicator with status label — no release browser
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 2.dp)
                    val label = when (item.status) {
                        "searching" -> "Searching for releases…"
                        "grabbing" -> "Grabbing release…"
                        "downloading" -> buildString {
                            append("Downloading")
                            item.download_progress?.let { append(" · ${"%.1f".format(it)}%") }
                            append("…")
                        }
                        "downloaded" -> "Download complete, waiting for Radarr…"
                        else -> item.status
                    }
                    Text(
                        text = label,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f)
                    )
                }
                OutlinedButton(
                    onClick = onDeleteClick,
                    enabled = actionsEnabled,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Delete")
                }
            }

            "in_library" -> {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Button(
                        onClick = onAutoGrab,
                        enabled = actionsEnabled,
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Auto-grab upgrade")
                    }
                    Button(
                        onClick = onLoadReleases,
                        enabled = actionsEnabled,
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Interactive search")
                    }
                }
                OutlinedButton(
                    onClick = onDeleteClick,
                    enabled = actionsEnabled,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Delete")
                }
            }

            "failed" -> {
                // Show fail reason if present
                item.fail_reason?.takeIf { it.isNotBlank() }?.let { reason ->
                    Text(
                        text = reason,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Button(
                        onClick = onAutoGrab,
                        enabled = actionsEnabled,
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Retry")
                    }
                    Button(
                        onClick = onLoadReleases,
                        enabled = actionsEnabled,
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Interactive search")
                    }
                }
                OutlinedButton(
                    onClick = onDeleteClick,
                    enabled = actionsEnabled,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Delete")
                }
            }

            else -> {
                // Catch-all for any future statuses: show release search + delete
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Button(
                        onClick = onAutoGrab,
                        enabled = actionsEnabled,
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Auto-grab best")
                    }
                    Button(
                        onClick = onLoadReleases,
                        enabled = actionsEnabled,
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Interactive search")
                    }
                }
                OutlinedButton(
                    onClick = onDeleteClick,
                    enabled = actionsEnabled,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Delete")
                }
            }
        }

        // Inline InFlight indicator below buttons
        if (actionState is ActionState.InFlight) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.padding(top = 4.dp)
            ) {
                CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                Text(
                    text = "Working…",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

// ---------------------------------------------------------------------------
// ReleaseRow
// ---------------------------------------------------------------------------

@Composable
private fun ReleaseRow(
    release: ScoredRelease,
    onGrab: (guid: String, indexerId: Int) -> Unit,
) {
    // Rejected-release confirmation dialog state — null means no dialog shown.
    var showRejectedDialog by remember { mutableStateOf(false) }

    val rowAlpha = if (release.rejected) 0.5f else 1f

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .alpha(rowAlpha)
            .clickable {
                if (release.rejected) {
                    showRejectedDialog = true
                } else {
                    onGrab(release.guid, release.indexer_id)
                }
            }
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // Title + rejection badge
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = release.title,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
            if (release.rejected) {
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = release.rejection_reason ?: "Rejected",
                    fontSize = 10.sp,
                    color = Color(0xFFC62828),
                    modifier = Modifier
                        .background(
                            color = Color(0xFFFDE8E8),
                            shape = RoundedCornerShape(3.dp)
                        )
                        .padding(horizontal = 4.dp, vertical = 1.dp)
                )
            }
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = release.indexer,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        // Right-side metadata column
        Column(
            horizontalAlignment = Alignment.End,
            verticalArrangement = Arrangement.spacedBy(3.dp)
        ) {
            // Quality pill
            QualityPill(quality = release.quality)

            // Size
            Text(
                text = "${"%.1f".format(release.size_gb)} GB",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            // Score + seeders on one line
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Text(
                    text = "S: ${release.score}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                SeederIndicator(seeders = release.seeders)
            }
        }
    }

    // Rejected release confirmation dialog
    if (showRejectedDialog) {
        AlertDialog(
            onDismissRequest = { showRejectedDialog = false },
            title = { Text("Release rejected") },
            text = {
                Text(
                    "This release is rejected (${release.rejection_reason ?: "unknown reason"}). " +
                        "Grab anyway?"
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        showRejectedDialog = false
                        onGrab(release.guid, release.indexer_id)
                    }
                ) {
                    Text("Grab")
                }
            },
            dismissButton = {
                TextButton(onClick = { showRejectedDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }
}

// ---------------------------------------------------------------------------
// Quality pill helper
// ---------------------------------------------------------------------------

@Composable
private fun QualityPill(quality: String) {
    val (bgColor, textColor) = when {
        quality.contains("2160", ignoreCase = true) ->
            Color(0xFF1B5E20) to Color.White
        quality.contains("1080", ignoreCase = true) ->
            Color(0xFF0D47A1) to Color.White
        quality.contains("720", ignoreCase = true) ->
            Color(0xFF616161) to Color.White
        else ->
            Color(0xFF616161) to Color.White
    }

    Text(
        text = quality,
        fontSize = 10.sp,
        fontWeight = FontWeight.SemiBold,
        color = textColor,
        modifier = Modifier
            .background(color = bgColor, shape = RoundedCornerShape(3.dp))
            .padding(horizontal = 5.dp, vertical = 2.dp)
    )
}

// ---------------------------------------------------------------------------
// Seeder indicator helper
// ---------------------------------------------------------------------------

@Composable
private fun SeederIndicator(seeders: Int) {
    val color = when {
        seeders >= 20 -> Color(0xFF2E7D32)
        seeders >= 5 -> Color(0xFFF57F17)
        else -> Color(0xFFC62828)
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(6.dp)
                .background(color = color, shape = RoundedCornerShape(3.dp))
        )
        Spacer(modifier = Modifier.width(3.dp))
        Text(
            text = "$seeders",
            fontSize = 10.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

// ---------------------------------------------------------------------------
// Previews
// ---------------------------------------------------------------------------

@Preview(showBackground = true)
@Composable
private fun LibraryDetailPreview_Idle() {
    MaterialTheme {
        LibraryDetailContent(
            item = previewItem("idle"),
            releasesState = ReleasesState.Hidden,
            actionState = ActionState.Idle,
            snackbarHostState = SnackbarHostState(),
            onBack = {},
            onAutoGrab = {},
            onLoadReleases = {},
            onGrab = { _, _ -> },
            onDelete = {},
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun LibraryDetailPreview_InLibrary_WithReleases() {
    MaterialTheme {
        LibraryDetailContent(
            item = previewItem("in_library"),
            releasesState = ReleasesState.Success(
                listOf(
                    ScoredRelease(
                        guid = "abc",
                        indexer_id = 1,
                        title = "The Movie 2024 2160p WEB-DL x265",
                        quality = "2160p",
                        size_bytes = 20_000_000_000L,
                        size_gb = 18.6,
                        seeders = 42,
                        score = 95,
                        rejected = false,
                        rejection_reason = null,
                        age_hours = 12.0,
                        indexer = "NZBgeek"
                    ),
                    ScoredRelease(
                        guid = "def",
                        indexer_id = 1,
                        title = "The Movie 2024 720p BRRip",
                        quality = "720p",
                        size_bytes = 2_000_000_000L,
                        size_gb = 1.9,
                        seeders = 2,
                        score = -10,
                        rejected = true,
                        rejection_reason = "720p not preferred",
                        age_hours = 24.0,
                        indexer = "NZBgeek"
                    )
                )
            ),
            actionState = ActionState.Idle,
            snackbarHostState = SnackbarHostState(),
            onBack = {},
            onAutoGrab = {},
            onLoadReleases = {},
            onGrab = { _, _ -> },
            onDelete = {},
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun LibraryDetailPreview_Downloading() {
    MaterialTheme {
        LibraryDetailContent(
            item = previewItem("downloading").copy(download_progress = 62.5),
            releasesState = ReleasesState.Hidden,
            actionState = ActionState.Idle,
            snackbarHostState = SnackbarHostState(),
            onBack = {},
            onAutoGrab = {},
            onLoadReleases = {},
            onGrab = { _, _ -> },
            onDelete = {},
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun LibraryDetailPreview_Failed() {
    MaterialTheme {
        LibraryDetailContent(
            item = previewItem("failed").copy(fail_reason = "No acceptable release found within size limits"),
            releasesState = ReleasesState.Hidden,
            actionState = ActionState.Idle,
            snackbarHostState = SnackbarHostState(),
            onBack = {},
            onAutoGrab = {},
            onLoadReleases = {},
            onGrab = { _, _ -> },
            onDelete = {},
        )
    }
}

private fun previewItem(status: String) = LibraryItem(
    id = 1,
    tmdb_id = 550,
    title = "Fight Club",
    year = 1999,
    overview = "A ticking-time-bomb insomniac and a slippery soap salesman channel primal male " +
        "aggression into a shocking new form of therapy.",
    poster_url = null,
    status = status,
    fail_reason = null,
    chosen_release_title = null,
    chosen_release_size_gb = null,
    chosen_release_quality = null,
    download_id = null,
    download_progress = null,
    radarr_has_file = false,
    created_at = "2024-01-01T00:00:00",
    updated_at = "2024-01-01T00:00:00"
)
