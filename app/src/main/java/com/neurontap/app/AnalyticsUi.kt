package com.neurontap.app

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items as gridItems
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.DeleteForever
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.SaveAlt
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private enum class ArchivePeriod(val label: String, val days: Int?) {
    WEEK("7D", 7), MONTH("30D", 30), YEAR("1Y", 365), ALL("ALL", null)
}

@Composable
fun WrappedContent(controller: AppController) {
    val db = controller.db
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var period by remember { mutableStateOf(ArchivePeriod.ALL) }
    var stats by remember { mutableStateOf(WrappedStats()) }
    var csvToWrite by remember { mutableStateOf<String?>(null) }
    var confirmReset by remember { mutableStateOf(false) }
    var activeGallery by remember { mutableStateOf<SmartGallery?>(null) }
    var viewerStartId by remember { mutableStateOf<Long?>(null) }
    var viewerItems by remember { mutableStateOf<List<MediaItem>>(emptyList()) }

    fun sinceForPeriod(): Long? = period.days?.let { System.currentTimeMillis() - it * 24L * 60L * 60L * 1000L }
    suspend fun refresh() { stats = withContext(Dispatchers.IO) { db.wrappedStats(sinceForPeriod()) } }
    LaunchedEffect(period) { refresh() }

    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri ->
        val csv = csvToWrite
        if (uri != null && csv != null) context.contentResolver.openOutputStream(uri)?.bufferedWriter()?.use { it.write(csv) }
        csvToWrite = null
    }

    fun openMedia(mediaId: Long, ids: List<Long>) {
        viewerItems = db.loadMediaByIds(ids)
        if (viewerItems.any { it.id == mediaId }) viewerStartId = mediaId
    }

    viewerStartId?.let { startId ->
        ViewerScreen(
            controller = controller,
            items = viewerItems,
            startMediaId = startId,
            onClose = { viewerStartId = null },
            onLibraryChanged = { scope.launch { refresh() } }
        )
        return
    }

    activeGallery?.let { gallery ->
        SmartGalleryView(
            gallery = gallery,
            db = db,
            onBack = { activeGallery = null },
            onOpen = { mediaId -> openMedia(mediaId, gallery.mediaIds) }
        )
        return
    }

    if (confirmReset) {
        AlertDialog(
            onDismissRequest = { confirmReset = false },
            title = { Text("Reset Horny Archives?") },
            text = { Text("This permanently clears sessions and behavioral telemetry. Your files, favorites, tags, linked folders, and album organization stay intact.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmReset = false
                    scope.launch { withContext(Dispatchers.IO) { db.clearBehaviorHistory() }; refresh() }
                }) { Text("Reset") }
            },
            dismissButton = { TextButton(onClick = { confirmReset = false }) { Text("Cancel") } }
        )
    }

    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 14.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("Horny Archives", style = MaterialTheme.typography.headlineMedium)
                Row {
                    IconButton(onClick = { scope.launch { refresh() } }) { Icon(Icons.Default.Refresh, "Refresh") }
                    IconButton(onClick = { scope.launch { csvToWrite = withContext(Dispatchers.IO) { db.exportCsv() }; exportLauncher.launch("neurontap-events.csv") } }) { Icon(Icons.Default.SaveAlt, "Export metadata CSV") }
                    IconButton(onClick = { confirmReset = true }) { Icon(Icons.Default.DeleteForever, "Reset statistics") }
                }
            }
        }

        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                ArchivePeriod.entries.forEach { p ->
                    FilledTonalButton(onClick = { period = p }, modifier = Modifier.weight(1f)) {
                        Text(if (period == p) "• ${p.label}" else p.label)
                    }
                }
            }
        }

        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatCard("Taps", stats.taps.toString(), Modifier.weight(1f))
                StatCard("Sessions", stats.sessions.toString(), Modifier.weight(1f))
                StatCard("Confirmed nuts", stats.confirmedNuts.toString(), Modifier.weight(1f))
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
                StatCard("Zoomed time", formatMs(stats.totalZoomedMs), Modifier.weight(1f))
                StatCard("Total viewed", formatMs(stats.totalDwellMs), Modifier.weight(1f))
            }
        }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatCard("Fastest tap", stats.quickestFirstTapMs?.let(::formatMs) ?: "—", Modifier.weight(1f))
                StatCard("Longest stare", stats.longestDwellMs?.let(::formatMs) ?: "—", Modifier.weight(1f))
                StatCard("Active hour", stats.mostActiveHour?.let(::formatHour) ?: "—", Modifier.weight(1f))
            }
        }

        if (stats.insights.isNotEmpty()) {
            item { Text("Interpretations", style = MaterialTheme.typography.titleLarge) }
            items(stats.insights) { insight ->
                Surface(color = Color(0xFF141414), shape = MaterialTheme.shapes.medium) {
                    Text(insight, Modifier.padding(12.dp), style = MaterialTheme.typography.bodyMedium)
                }
            }
        }

        if (stats.smartGalleries.isNotEmpty()) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text("Live archive galleries", style = MaterialTheme.typography.titleLarge)
                    Text("Generated from the selected time period. These do not alter your normal gallery.", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                }
            }
            items(stats.smartGalleries) { gallery ->
                Card(onClick = { activeGallery = gallery }, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(gallery.title, style = MaterialTheme.typography.titleMedium)
                        Text(gallery.subtitle, style = MaterialTheme.typography.bodySmall)
                        Text("${gallery.mediaIds.size} ranked item${if (gallery.mediaIds.size == 1) "" else "s"}", color = Color.Gray)
                    }
                }
            }
        }

        if (stats.potentialNutCandidates.isNotEmpty()) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text("Potential-nut accusations", style = MaterialTheme.typography.titleLarge)
                    Text("Inference only. Nothing here counts as a confirmed nut unless you explicitly logged it.", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                }
            }
            items(stats.potentialNutCandidates) { candidate ->
                Card(
                    onClick = {
                        candidate.primaryMediaId?.let { id ->
                            val ids = stats.potentialNutCandidates.mapNotNull { it.primaryMediaId }.distinct()
                            openMedia(id, ids)
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(candidate.primaryMediaName ?: "Unknown media", style = MaterialTheme.typography.titleMedium, maxLines = 1)
                        Text("${(candidate.confidence * 100).toInt()}% confidence · ${formatDateTime(candidate.windowEndMs)}")
                        if (candidate.evidence.isNotBlank()) Text(candidate.evidence, style = MaterialTheme.typography.bodySmall)
                        if (candidate.windowStartMs != null && candidate.windowEndMs != null) Text("Estimated active window ${formatMs(candidate.windowEndMs - candidate.windowStartMs)}", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                    }
                }
            }
        }

        item { Text("Top behavioral files", style = MaterialTheme.typography.titleLarge) }
        items(stats.summaries.take(50)) { summary ->
            Card(
                onClick = { openMedia(summary.mediaId, stats.summaries.map { it.mediaId }) },
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(summary.name, style = MaterialTheme.typography.titleMedium, maxLines = 1)
                    Text("${summary.taps} taps · ${formatMs(summary.dwellMs)} viewed · ${summary.views} views · ${summary.returnCount} returns")
                    Text("${summary.confirmedNuts} confirmed · ${summary.spiritualCooms} spiritual · ${summary.edgeMarks} edge · ${summary.instantHardMarks} instant-hard", style = MaterialTheme.typography.bodySmall)
                    if (summary.explorationScore > 0) {
                        Text("Exploration ${String.format(Locale.US, "%.1f", summary.explorationScore)} · max zoom ${String.format(Locale.US, "%.1f", summary.maxZoomMilli / 1000.0)}× · ${formatMs(summary.zoomedDwellMs)} zoomed · ${summary.videoSeeks} seeks", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                    }
                    Text("Combined signal ${String.format(Locale.US, "%.1f", summary.attractionScore)}", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                }
            }
        }
    }
}

@Composable
private fun SmartGalleryView(gallery: SmartGallery, db: NeuronDb, onBack: () -> Unit, onOpen: (Long) -> Unit) {
    val media = remember(gallery.mediaIds) { db.loadMediaByIds(gallery.mediaIds) }
    Column(Modifier.fillMaxSize().background(Color.Black)) {
        Row(Modifier.fillMaxWidth().padding(6.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
            Column(Modifier.weight(1f)) {
                Text(gallery.title, style = MaterialTheme.typography.titleLarge)
                Text(gallery.subtitle, style = MaterialTheme.typography.bodySmall, color = Color.Gray)
            }
        }
        LazyVerticalGrid(
            columns = GridCells.Fixed(3),
            modifier = Modifier.fillMaxSize(),
            horizontalArrangement = Arrangement.spacedBy(2.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            gridItems(media, key = { it.id }) { item ->
                Box(Modifier.aspectRatio(1f).background(Color(0xFF111111))) {
                    Card(onClick = { onOpen(item.id) }, modifier = Modifier.fillMaxSize()) {
                        Box(Modifier.fillMaxSize()) {
                            MediaThumbnail(item, Modifier.fillMaxSize(), ContentScale.Crop)
                            if (item.isVideo) Icon(Icons.Default.Movie, null, modifier = Modifier.align(Alignment.BottomStart).padding(5.dp).size(20.dp))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StatCard(label: String, value: String, modifier: Modifier = Modifier) {
    Card(modifier) {
        Column(Modifier.padding(10.dp)) {
            Text(value, style = MaterialTheme.typography.titleMedium)
            Text(label, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
fun TagLabContent(db: NeuronDb) {
    var top by remember { mutableStateOf<List<MediaBehaviorSummary>>(emptyList()) }
    var selected by remember { mutableStateOf<MediaBehaviorSummary?>(null) }
    var tagText by remember { mutableStateOf("") }
    var tags by remember { mutableStateOf<List<String>>(emptyList()) }
    suspend fun refresh() { top = withContext(Dispatchers.IO) { db.behaviorSummaries().sortedByDescending { it.attractionScore }.take(100) } }
    LaunchedEffect(Unit) { refresh() }

    selected?.let { summary ->
        AlertDialog(
            onDismissRequest = { selected = null },
            title = { Text(summary.name) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(if (tags.isEmpty()) "No tags yet." else "Tags: ${tags.joinToString()}")
                    TextField(value = tagText, onValueChange = { tagText = it }, label = { Text("Add a tag") })
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    if (tagText.isNotBlank()) {
                        db.addTag(summary.mediaId, tagText)
                        tags = db.tagsForMedia(summary.mediaId)
                        tagText = ""
                    }
                }) { Text("Add") }
            },
            dismissButton = { TextButton(onClick = { selected = null }) { Text("Done") } }
        )
    }

    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Text("Label interesting files after the fact. Raw behavior stays raw and can always be reinterpreted later.") }
        items(top) { summary ->
            Card(Modifier.fillMaxWidth()) {
                Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                    Column(Modifier.weight(1f)) {
                        Text(summary.name, maxLines = 1)
                        Text("${summary.taps} taps · signal ${String.format(Locale.US, "%.1f", summary.attractionScore)}")
                    }
                    FilledTonalButton(onClick = { selected = summary; tags = db.tagsForMedia(summary.mediaId) }) { Text("Tag") }
                }
            }
        }
    }
}

fun formatMs(ms: Long): String {
    if (ms < 1000) return "${ms}ms"
    val totalSeconds = ms / 1000
    val hours = totalSeconds / 3600
    val minutes = (totalSeconds % 3600) / 60
    val seconds = totalSeconds % 60
    return when {
        hours > 0 -> "${hours}h ${minutes}m"
        minutes > 0 -> "${minutes}m ${seconds}s"
        else -> "${seconds}s"
    }
}

fun formatHour(hour: Int): String {
    val suffix = if (hour < 12) "AM" else "PM"
    val h = when (val x = hour % 12) { 0 -> 12; else -> x }
    return "$h $suffix"
}

private fun formatDateTime(ms: Long?): String {
    if (ms == null) return "unknown time"
    return SimpleDateFormat("MMM d · h:mm a", Locale.getDefault()).format(Date(ms))
}
