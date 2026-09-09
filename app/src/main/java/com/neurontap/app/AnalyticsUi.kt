package com.neurontap.app

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DeleteForever
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.SaveAlt
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

@Composable
fun WrappedContent(db: NeuronDb) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var stats by remember { mutableStateOf(WrappedStats()) }
    var csvToWrite by remember { mutableStateOf<String?>(null) }
    var confirmReset by remember { mutableStateOf(false) }
    suspend fun refresh() { stats = withContext(Dispatchers.IO) { db.wrappedStats() } }
    LaunchedEffect(Unit) { refresh() }

    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri ->
        val csv = csvToWrite
        if (uri != null && csv != null) context.contentResolver.openOutputStream(uri)?.bufferedWriter()?.use { it.write(csv) }
        csvToWrite = null
    }

    if (confirmReset) {
        AlertDialog(
            onDismissRequest = { confirmReset = false },
            title = { Text("Reset Horny Archives?") },
            text = { Text("This permanently clears sessions and behavioral events. Your media and favorites stay intact.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmReset = false
                    scope.launch {
                        withContext(Dispatchers.IO) { db.clearBehaviorHistory() }
                        refresh()
                    }
                }) { Text("Reset") }
            },
            dismissButton = { TextButton(onClick = { confirmReset = false }) { Text("Cancel") } }
        )
    }

    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                IconButton(onClick = { scope.launch { refresh() } }) { Icon(Icons.Default.Refresh, "Refresh") }
                IconButton(onClick = { scope.launch { csvToWrite = withContext(Dispatchers.IO) { db.exportCsv() }; exportLauncher.launch("neurontap-events.csv") } }) {
                    Icon(Icons.Default.SaveAlt, "Export metadata CSV")
                }
                IconButton(onClick = { confirmReset = true }) { Icon(Icons.Default.DeleteForever, "Reset statistics") }
            }
        }
        item { Text("Horny Archives", style = MaterialTheme.typography.headlineMedium) }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatCard("Taps", stats.taps.toString(), Modifier.weight(1f))
                StatCard("Sessions", stats.sessions.toString(), Modifier.weight(1f))
                StatCard("Confirmed nuts", stats.finishes.toString(), Modifier.weight(1f))
            }
        }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatCard("Potential nuts", stats.potentialNuts.toString(), Modifier.weight(1f))
                StatCard("Spiritual Cooms", stats.spiritualCooms.toString(), Modifier.weight(1f))
                StatCard("Edge marks", stats.edgeMarks.toString(), Modifier.weight(1f))
            }
        }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatCard("Instant hard", stats.instantHardMarks.toString(), Modifier.weight(1f))
                StatCard("Fastest tap", stats.quickestFirstTapMs?.let(::formatMs) ?: "—", Modifier.weight(1f))
                StatCard("Longest stare", stats.longestDwellMs?.let(::formatMs) ?: "—", Modifier.weight(1f))
            }
        }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatCard("Active hour", stats.mostActiveHour?.let(::formatHour) ?: "—", Modifier.weight(1f))
            }
        }

        if (stats.potentialNutCandidates.isNotEmpty()) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Potential nuts", style = MaterialTheme.typography.titleLarge)
                    Text("These are calculator guesses only. They never become confirmed nuts unless you explicitly log one.", style = MaterialTheme.typography.bodySmall)
                }
            }
            items(stats.potentialNutCandidates) { candidate ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(candidate.primaryMediaName ?: "Unknown media", style = MaterialTheme.typography.titleMedium, maxLines = 1)
                        Text("${(candidate.confidence * 100).toInt()}% potential-nut confidence")
                        if (candidate.evidence.isNotBlank()) Text(candidate.evidence, style = MaterialTheme.typography.bodySmall)
                        if (candidate.windowStartMs != null && candidate.windowEndMs != null) {
                            Text("Estimated window ${formatMs(candidate.windowEndMs - candidate.windowStartMs)}", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }

        item { Text("Top behavioral hits", style = MaterialTheme.typography.titleLarge) }
        items(stats.topMedia) { score ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp)) {
                    Text(score.name, style = MaterialTheme.typography.titleMedium, maxLines = 1)
                    Text("${score.taps} taps · ${formatMs(score.dwellMs)} dwell · ${score.sessionCount} sessions · ${score.finishCount} inferred/linked finishes")
                    Text("Reaction score ${String.format(Locale.US, "%.1f", score.score)}")
                }
            }
        }
    }
}

@Composable
private fun StatCard(label: String, value: String, modifier: Modifier = Modifier) {
    Card(modifier) {
        Column(Modifier.padding(12.dp)) {
            Text(value, style = MaterialTheme.typography.titleLarge)
            Text(label, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
fun TagLabContent(db: NeuronDb) {
    var top by remember { mutableStateOf<List<MediaScore>>(emptyList()) }
    var selected by remember { mutableStateOf<MediaScore?>(null) }
    var tagText by remember { mutableStateOf("") }
    var tags by remember { mutableStateOf<List<String>>(emptyList()) }
    suspend fun refresh() { top = withContext(Dispatchers.IO) { db.topMedia(50) } }
    LaunchedEffect(Unit) { refresh() }

    selected?.let { score ->
        AlertDialog(
            onDismissRequest = { selected = null },
            title = { Text(score.name) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(if (tags.isEmpty()) "No tags yet." else "Tags: ${tags.joinToString()}")
                    TextField(value = tagText, onValueChange = { tagText = it }, label = { Text("Add a tag") })
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    if (tagText.isNotBlank()) {
                        db.addTag(score.mediaId, tagText)
                        tags = db.tagsForMedia(score.mediaId)
                        tagText = ""
                    }
                }) { Text("Add") }
            },
            dismissButton = { TextButton(onClick = { selected = null }) { Text("Done") } }
        )
    }

    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Text("Only label the interesting stuff after the fact. Raw reactions stay raw.") }
        items(top) { score ->
            Card(Modifier.fillMaxWidth()) {
                Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                    Column(Modifier.weight(1f)) {
                        Text(score.name, maxLines = 1)
                        Text("${score.taps} taps · score ${String.format(Locale.US, "%.1f", score.score)}")
                    }
                    FilledTonalButton(onClick = { selected = score; tags = db.tagsForMedia(score.mediaId) }) { Text("Tag") }
                }
            }
        }
    }
}

fun formatMs(ms: Long): String {
    if (ms < 1000) return "${ms}ms"
    val totalSeconds = ms / 1000
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return if (minutes > 0) "${minutes}m ${seconds}s" else "${seconds}s"
}

fun formatHour(hour: Int): String {
    val suffix = if (hour < 12) "AM" else "PM"
    val h = when (val x = hour % 12) { 0 -> 12; else -> x }
    return "$h $suffix"
}
