from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Model used by the lightweight archive timeline query.
p = ROOT / "app/src/main/java/com/neurontap/app/Models.kt"
s = p.read_text()
anchor = 'object EventTypes {\n'
if anchor not in s:
    raise RuntimeError('v8 analytics EventTypes anchor missing')
s = s.replace(anchor, '''data class ActivityStormEvent(
    val type: String,
    val timestampMs: Long,
    val mediaId: Long?,
    val value: Long? = null
)

''' + anchor, 1)
p.write_text(s)

# Database timeline query. Keep it intentionally narrow: enough facts to draw
# the story and infer Full Stroke continuation without loading every telemetry row.
p = ROOT / "app/src/main/java/com/neurontap/app/NeuronDb.kt"
s = p.read_text()
anchor = '    fun activityHeatmap(types: Set<String>, sinceMs: Long? = null): Map<Pair<Int, Int>, Long> {\n'
if anchor not in s:
    raise RuntimeError('v8 analytics db heatmap anchor missing')
method = r'''    fun activityStormEvents(sinceMs: Long? = null): List<ActivityStormEvent> {
        val types = listOf(
            EventTypes.VIEW_START, EventTypes.VIEW_DWELL, EventTypes.MEDIA_SWIPE,
            EventTypes.REACTION_UP, EventTypes.FULL_STROKE_MARK, EventTypes.FULL_STROKE_START,
            EventTypes.INSTANT_HARD, EventTypes.SPIRITUAL_COOM, EventTypes.GOON_START,
            EventTypes.CONFIRMED_NUT, EventTypes.APP_BACKGROUND,
            EventTypes.VIDEO_PLAY, EventTypes.VIDEO_PAUSE
        )
        val placeholders = types.joinToString(",") { "?" }
        val args = buildList {
            addAll(types)
            if (sinceMs != null) add(sinceMs.toString())
        }.toTypedArray()
        val sinceClause = if (sinceMs != null) " AND timestamp_ms>=?" else ""
        return readableDatabase.rawQuery(
            "SELECT type,timestamp_ms,media_id,value FROM events WHERE type IN ($placeholders)$sinceClause ORDER BY timestamp_ms",
            args
        ).use { c ->
            buildList {
                while (c.moveToNext()) add(
                    ActivityStormEvent(
                        type = c.getString(0),
                        timestampMs = c.getLong(1),
                        mediaId = if (c.isNull(2)) null else c.getLong(2),
                        value = if (c.isNull(3)) null else c.getLong(3)
                    )
                )
            }
        }
    }

'''
s = s.replace(anchor, method + anchor, 1)
p.write_text(s)

# Analytics UI -------------------------------------------------------------
p = ROOT / "app/src/main/java/com/neurontap/app/AnalyticsUi.kt"
s = p.read_text()

# Imports.
s = s.replace('package com.neurontap.app\n\n', 'package com.neurontap.app\n\nimport android.graphics.Paint\n', 1)
s = s.replace('import androidx.compose.foundation.background\n', 'import androidx.compose.foundation.Canvas\nimport androidx.compose.foundation.background\nimport androidx.compose.foundation.gestures.detectTapGestures\n', 1)
s = s.replace('import androidx.compose.foundation.lazy.LazyColumn\n', 'import androidx.compose.foundation.lazy.LazyColumn\nimport androidx.compose.foundation.lazy.rememberLazyListState\n', 1)
s = s.replace('import androidx.compose.ui.Alignment\n', 'import androidx.compose.ui.Alignment\nimport androidx.compose.ui.geometry.Offset\nimport androidx.compose.ui.geometry.Size\n', 1)
s = s.replace('import androidx.compose.ui.graphics.Color\n', 'import androidx.compose.ui.graphics.Color\nimport androidx.compose.ui.graphics.nativeCanvas\nimport androidx.compose.ui.input.pointer.pointerInput\n', 1)
s = s.replace('import androidx.compose.ui.platform.LocalContext\n', 'import androidx.compose.ui.platform.LocalContext\nimport androidx.compose.ui.platform.LocalDensity\n', 1)
s = s.replace('import kotlin.math', 'import kotlin.math') if 'import kotlin.math' in s else s + ''

# v0.7 heatmap state -> storm timeline state.
old_state = '''    var heatmapMode by remember { mutableStateOf("Neuron") }
    var heatmapData by remember { mutableStateOf<Map<Pair<Int, Int>, Long>>(emptyMap()) }
'''
if old_state not in s:
    raise RuntimeError('v8 analytics heatmap state missing')
s = s.replace(old_state, '    var stormEvents by remember { mutableStateOf<List<ActivityStormEvent>>(emptyList()) }\n', 1)

start = s.find('    LaunchedEffect(period, heatmapMode) {')
end = s.find('\n    }\n', start)
if start < 0 or end < 0:
    raise RuntimeError('v8 analytics heatmap loader missing')
# The loader contains nested when braces, so find the exact tail installed by v7.
tail = '        heatmapData = withContext(Dispatchers.IO) { db.activityHeatmap(types, sinceForPeriod()) }\n    }'
tail_at = s.find(tail, start)
if tail_at < 0:
    raise RuntimeError('v8 analytics heatmap loader tail missing')
end = tail_at + len(tail)
s = s[:start] + '''    LaunchedEffect(period) {
        stormEvents = withContext(Dispatchers.IO) { db.activityStormEvents(sinceForPeriod()) }
    }''' + s[end:]

old_call = '''            ArchiveHeatmapV7(
                mode = heatmapMode,
                data = heatmapData,
                onMode = { heatmapMode = it }
            )
'''
if old_call not in s:
    raise RuntimeError('v8 analytics heatmap call missing')
s = s.replace(old_call, '''            ActivityStormMapV8(
                events = stormEvents,
                sinceMs = sinceForPeriod()
            )
''', 1)

# Full Stroke duration based on manual end events is obsolete. Do not headline it.
s = s.replace('StatCard("Full Stroke time", formatMs(stats.fullStrokeDurationMs), Modifier.weight(1f))', 'StatCard("Full Stroke anchors", stats.fullStrokeMarks.toString(), Modifier.weight(1f))', 1)

# Insert storm map implementation before the old heatmap helper (kept unused for
# migration readability).
insert = s.find('@Composable\nprivate fun ArchiveHeatmapV7(')
if insert < 0:
    raise RuntimeError('v8 analytics storm insertion point missing')
storm = r'''private data class StormBucketV8(
    var viewMs: Long = 0L,
    var neurons: Int = 0,
    var fullStroke: Int = 0,
    var instantHard: Int = 0,
    var spiritual: Int = 0,
    var goon: Int = 0,
    var nuts: Int = 0,
    var inferredStroke: Boolean = false
)

@Composable
private fun ActivityStormMapV8(events: List<ActivityStormEvent>, sinceMs: Long?) {
    val density = LocalDensity.current
    val now = remember(events, sinceMs) { System.currentTimeMillis() }
    val start = remember(events, sinceMs, now) {
        sinceMs ?: events.minOfOrNull { it.timestampMs } ?: (now - 24L * 60L * 60L * 1000L)
    }
    val span = (now - start).coerceAtLeast(60L * 60L * 1000L)
    val bucketCount = 48
    var selected by remember(start, now) { mutableStateOf<Int?>(null) }

    val buckets = remember(events, start, span) {
        Array(bucketCount) { StormBucketV8() }.also { out ->
            fun bucketIndex(ts: Long): Int = (((ts - start).toDouble() / span.toDouble()) * bucketCount)
                .toInt().coerceIn(0, bucketCount - 1)
            val sorted = events.sortedBy { it.timestampMs }
            sorted.forEach { event ->
                val b = out[bucketIndex(event.timestampMs)]
                when (event.type) {
                    EventTypes.VIEW_DWELL -> b.viewMs += event.value?.coerceAtLeast(0L) ?: 0L
                    EventTypes.VIEW_START -> if (b.viewMs == 0L) b.viewMs += 750L
                    EventTypes.REACTION_UP -> b.neurons += 1
                    EventTypes.FULL_STROKE_MARK, EventTypes.FULL_STROKE_START -> b.fullStroke += 1
                    EventTypes.INSTANT_HARD -> b.instantHard += 1
                    EventTypes.SPIRITUAL_COOM -> b.spiritual += 1
                    EventTypes.GOON_START -> b.goon += 1
                    EventTypes.CONFIRMED_NUT -> b.nuts += 1
                }
            }

            // Full Stroke is one explicit declaration point. Build a clearly
            // inferred continuation band from subsequent activity, stopping at
            // a finish/background, a long quiet gap, or a conservative cap.
            sorted.filter { it.type == EventTypes.FULL_STROKE_MARK || it.type == EventTypes.FULL_STROKE_START }.forEach { mark ->
                val cap = mark.timestampMs + 10L * 60L * 1000L
                var inferredEnd = (mark.timestampMs + 90_000L).coerceAtMost(cap)
                var lastActivity = mark.timestampMs
                for (event in sorted) {
                    if (event.timestampMs <= mark.timestampMs) continue
                    if (event.timestampMs > cap) break
                    if (event.type == EventTypes.CONFIRMED_NUT || event.type == EventTypes.APP_BACKGROUND) {
                        inferredEnd = event.timestampMs
                        break
                    }
                    if (event.timestampMs - lastActivity > 2L * 60L * 1000L) {
                        inferredEnd = (lastActivity + 60_000L).coerceAtMost(cap)
                        break
                    }
                    if (event.type in setOf(EventTypes.VIEW_START, EventTypes.VIEW_DWELL, EventTypes.MEDIA_SWIPE, EventTypes.REACTION_UP, EventTypes.VIDEO_PLAY, EventTypes.VIDEO_PAUSE, EventTypes.INSTANT_HARD, EventTypes.SPIRITUAL_COOM)) {
                        lastActivity = event.timestampMs
                        inferredEnd = (lastActivity + 60_000L).coerceAtMost(cap)
                    }
                }
                val from = bucketIndex(mark.timestampMs)
                val to = bucketIndex(inferredEnd)
                for (i in from..to) out[i].inferredStroke = true
            }
        }
    }
    val positiveViews = remember(buckets) { buckets.map { it.viewMs }.filter { it > 0L }.sorted() }
    val adaptiveHigh = remember(positiveViews) {
        if (positiveViews.isEmpty()) 1L
        else positiveViews[((positiveViews.lastIndex) * 0.85f).roundToInt().coerceIn(0, positiveViews.lastIndex)].coerceAtLeast(1L)
    }
    val nutPaint = remember(density) {
        Paint(Paint.ANTI_ALIAS_FLAG).apply {
            textAlign = Paint.Align.CENTER
            textSize = with(density) { 21.sp.toPx() }
            color = android.graphics.Color.WHITE
        }
    }

    Surface(color = Color(0xFF111111), shape = MaterialTheme.shapes.medium) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Activity storm", style = MaterialTheme.typography.titleLarge)
            Text("Time runs left → right. Warmth is your own viewing intensity; symbols are exact declarations/events. Full Stroke haze is inferred, not ground truth.", style = MaterialTheme.typography.bodySmall, color = Color.Gray)

            Canvas(
                Modifier.fillMaxWidth().height(176.dp).background(Color(0xFF090909))
                    .pointerInput(start, span, events.size) {
                        detectTapGestures { tap ->
                            selected = ((tap.x / size.width.toFloat()) * bucketCount).toInt().coerceIn(0, bucketCount - 1)
                        }
                    }
            ) {
                val w = size.width / bucketCount.toFloat()
                val h = size.height
                buckets.forEachIndexed { i, bucket ->
                    val x = i * w
                    val strength = (bucket.viewMs.toFloat() / adaptiveHigh.toFloat()).coerceIn(0f, 1f)
                    if (strength > 0f) {
                        val hue = 52f * (1f - strength)
                        drawRect(
                            color = Color.hsv(hue, 0.92f, 0.96f).copy(alpha = 0.16f + strength * 0.74f),
                            topLeft = Offset(x, 0f),
                            size = Size(w + 1f, h)
                        )
                    }
                    if (bucket.inferredStroke) {
                        drawRect(Color(0xFFFF4D9D).copy(alpha = 0.16f), Offset(x, h * 0.18f), Size(w + 1f, h * 0.64f))
                    }
                    if (bucket.fullStroke > 0) {
                        drawRect(Color(0xFFFF4D9D), Offset(x + w * 0.42f, h * 0.16f), Size((w * 0.16f).coerceAtLeast(2f), h * 0.68f))
                    }
                    if (bucket.instantHard > 0) drawCircle(Color(0xFF58D7FF), radius = 4.5f, center = Offset(x + w * 0.5f, h * 0.22f))
                    if (bucket.spiritual > 0) drawCircle(Color(0xFFB985FF), radius = 5.5f, center = Offset(x + w * 0.5f, h * 0.36f))
                    if (bucket.goon > 0) drawCircle(Color(0xFF5CA8FF), radius = 5f, center = Offset(x + w * 0.5f, h * 0.50f))
                    val dots = bucket.neurons.coerceAtMost(8)
                    repeat(dots) { d ->
                        val px = x + w * (0.20f + (d % 4) * 0.20f)
                        val py = h * (0.72f + (d / 4) * 0.10f)
                        drawCircle(Color.White.copy(alpha = 0.42f), radius = 2.1f, center = Offset(px, py))
                    }
                    if (bucket.nuts > 0) {
                        drawLine(Color.White.copy(alpha = 0.7f), Offset(x + w * 0.5f, 0f), Offset(x + w * 0.5f, h), strokeWidth = 1.5f)
                        drawContext.canvas.nativeCanvas.drawText("🥜", x + w * 0.5f, h * 0.16f, nutPaint)
                    }
                    if (selected == i) {
                        drawRect(Color.White.copy(alpha = 0.72f), Offset(x, 0f), Size(w, h), style = androidx.compose.ui.graphics.drawscope.Stroke(width = 2f))
                    }
                }
            }

            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(formatStormTickV8(start), style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                Text(formatStormTickV8(start + span / 2L), style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                Text("Now", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
            }
            Text("Warm = viewed time   ·   · = Neuron   ·   pink line = Full Stroke   ·   cyan = Instant Hard   ·   purple = Spiritual Coom   ·   🥜 = confirmed", style = MaterialTheme.typography.labelSmall, color = Color.LightGray)

            selected?.let { index ->
                val bucket = buckets[index]
                val bucketStart = start + span * index / bucketCount
                val bucketEnd = start + span * (index + 1L) / bucketCount
                Text(
                    "${formatStormTickV8(bucketStart)}–${formatStormTickV8(bucketEnd)} · ${formatMs(bucket.viewMs)} viewed · ${bucket.neurons} Neuron · ${bucket.fullStroke} Full Stroke · ${bucket.instantHard} Instant Hard · ${bucket.spiritual} Spiritual · ${bucket.nuts} confirmed",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.White
                )
            }
        }
    }
}

private fun formatStormTickV8(ms: Long): String =
    SimpleDateFormat("MMM d · h:mm a", Locale.getDefault()).format(Date(ms))

'''
s = s[:insert] + storm + s[insert:]

# Tag Lab should show media and let the user inspect it, not demand filename
# clairvoyance. Replace the whole function and keep scroll state through viewer.
start = s.find('@Composable\nfun TagLabContent(')
end = s.find('\nfun formatMs(', start)
if start < 0 or end < 0:
    raise RuntimeError('v8 Tag Lab boundaries missing')
taglab = r'''@Composable
fun TagLabContent(controller: AppController) {
    val db = controller.db
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()
    var top by remember { mutableStateOf<List<MediaBehaviorSummary>>(emptyList()) }
    var mediaById by remember { mutableStateOf<Map<Long, MediaItem>>(emptyMap()) }
    var selected by remember { mutableStateOf<MediaBehaviorSummary?>(null) }
    var tagText by remember { mutableStateOf("") }
    var tags by remember { mutableStateOf<List<String>>(emptyList()) }
    var viewerStartId by remember { mutableStateOf<Long?>(null) }
    var viewerItems by remember { mutableStateOf<List<MediaItem>>(emptyList()) }

    suspend fun refresh() {
        val summaries = withContext(Dispatchers.IO) { db.behaviorSummaries().sortedByDescending { it.attractionScore }.take(100) }
        val items = withContext(Dispatchers.IO) { db.loadMediaByIds(summaries.map { it.mediaId }) }
        top = summaries
        mediaById = items.associateBy { it.id }
    }
    LaunchedEffect(Unit) { refresh() }

    viewerStartId?.let { startId ->
        ViewerScreen(
            controller = controller,
            incomingItems = viewerItems,
            startMediaId = startId,
            onClose = { viewerStartId = null },
            onLibraryChanged = { scope.launch { refresh() } }
        )
        return
    }

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
                    if (tagText.isNotBlank()) scope.launch {
                        withContext(Dispatchers.IO) { db.addTag(summary.mediaId, tagText) }
                        tags = withContext(Dispatchers.IO) { db.tagsForMedia(summary.mediaId) }
                        tagText = ""
                    }
                }) { Text("Add") }
            },
            dismissButton = { TextButton(onClick = { selected = null }) { Text("Done") } }
        )
    }

    LazyColumn(state = listState, modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Text("Interesting media worth labeling. Tap a card to inspect it; Tag adds searchable meaning after the fact.") }
        items(top, key = { it.mediaId }) { summary ->
            val item = mediaById[summary.mediaId]
            Card(
                onClick = {
                    scope.launch {
                        viewerItems = withContext(Dispatchers.IO) { db.loadMediaByIds(top.map { it.mediaId }) }
                        if (viewerItems.any { it.id == summary.mediaId }) viewerStartId = summary.mediaId
                    }
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    if (item != null) MediaThumbnail(item, Modifier.size(78.dp), ContentScale.Crop, summary.name)
                    else Box(Modifier.size(78.dp).background(Color(0xFF202020)))
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                        Text(summary.name, maxLines = 2)
                        Text("${summary.taps} taps · signal ${String.format(Locale.US, "%.1f", summary.attractionScore)}", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                        Text("Tap to inspect", style = MaterialTheme.typography.labelSmall, color = Color.LightGray)
                    }
                    FilledTonalButton(onClick = {
                        selected = summary
                        scope.launch { tags = withContext(Dispatchers.IO) { db.tagsForMedia(summary.mediaId) } }
                    }) { Text("Tag") }
                }
            }
        }
    }
}
'''
s = s[:start] + taglab + s[end:]
p.write_text(s)

# MainActivity supplies the controller so Tag Lab can open the real viewer.
p = ROOT / "app/src/main/java/com/neurontap/app/MainActivity.kt"
s = p.read_text()
if 'TagLabContent(controller.db)' not in s:
    raise RuntimeError('v8 Tag Lab MainActivity anchor missing')
s = s.replace('TagLabContent(controller.db)', 'TagLabContent(controller)', 1)
p.write_text(s)

print('Applied v8 storm map and Tag Lab repair')
