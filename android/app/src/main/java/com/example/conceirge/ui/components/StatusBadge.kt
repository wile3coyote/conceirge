package com.example.conceirge.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun StatusBadge(status: String) {
    val (label, color) = when (status) {
        "searching" -> "Searching" to Color(0xFF1565C0)
        "grabbing" -> "Grabbing" to Color(0xFFE65100)
        "downloading" -> "Downloading" to Color(0xFFF57F17)
        "downloaded" -> "Downloaded" to Color(0xFF00695C)
        "in_library" -> "In Library" to Color(0xFF2E7D32)
        "failed" -> "Failed" to Color(0xFFC62828)
        else -> status to Color.Gray
    }

    Text(
        text = label,
        color = Color.White,
        fontSize = 11.sp,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier
            .background(color = color, shape = RoundedCornerShape(4.dp))
            .padding(horizontal = 8.dp, vertical = 3.dp)
    )
}
