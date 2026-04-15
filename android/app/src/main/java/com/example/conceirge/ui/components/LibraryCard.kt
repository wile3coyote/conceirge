package com.example.conceirge.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.example.conceirge.data.models.LibraryItem

@Composable
fun LibraryCard(
    item: LibraryItem,
    onRetry: () -> Unit,
    onDelete: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.Top
        ) {
            AsyncImage(
                model = item.poster_url,
                contentDescription = "${item.title} poster",
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(width = 60.dp, height = 90.dp)
                    .clip(RoundedCornerShape(4.dp))
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "${item.title} (${item.year})",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(4.dp))
                StatusBadge(status = item.status)

                // Release info
                val releaseInfo = buildString {
                    item.chosen_release_quality?.let { append(it) }
                    item.chosen_release_size_gb?.let {
                        if (isNotEmpty()) append(" · ")
                        append("%.1f GB".format(it))
                    }
                }
                if (releaseInfo.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = releaseInfo,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                // Download progress bar
                if (item.status == "downloading" && item.download_progress != null) {
                    Spacer(modifier = Modifier.height(6.dp))
                    val progress = (item.download_progress / 100.0).coerceIn(0.0, 1.0).toFloat()
                    Text(
                        text = "Downloading · ${"%.1f".format(item.download_progress)}%",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    LinearProgressIndicator(
                        progress = { progress },
                        modifier = Modifier.fillMaxWidth()
                    )
                }

                // Fail reason
                item.fail_reason?.let { reason ->
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = reason,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }

                // Action buttons
                if (item.status == "failed") {
                    Spacer(modifier = Modifier.height(4.dp))
                    Row {
                        TextButton(onClick = onRetry) { Text("Retry") }
                        Spacer(modifier = Modifier.width(4.dp))
                        TextButton(onClick = onDelete) { Text("Delete") }
                    }
                } else {
                    Spacer(modifier = Modifier.height(4.dp))
                    TextButton(onClick = onDelete) { Text("Remove") }
                }
            }
        }
    }
}
