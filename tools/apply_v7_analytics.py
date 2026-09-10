from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/AnalyticsUi.kt"
s = p.read_text()

def rep(old, new, label):
    global s
    if old not in s:
        raise RuntimeError(f"v7 analytics anchor missing: {label}")
    s = s.replace(old, new, 1)

rep('import androidx.compose.foundation.background\n', 'import androidx.compose.foundation.ExperimentalFoundationApi\nimport androidx.compose.foundation.background\nimport androidx.compose.foundation.combinedClickable\n', 'foundation imports')
rep('import androidx.compose.foundation.layout.fillMaxWidth\n', 'import androidx.compose.foundation.layout.fillMaxWidth\nimport androidx.compose.foundation.layout.height\n', 'height import')
rep('import androidx.compose.foundation.layout.size\n', 'import androidx.compose.foundation.layout.size\nimport androidx.compose.foundation.layout.width\n', 'width import')

# Viewer stable-list argument introduced by v0.7.
s = s.replace('            items = viewerItems,', '            incomingItems = viewerItems,')

# Archive state for a filterable day x hour heatmap.
anchor = '    val archiveListState = rememberLazyListState()\n'
rep(anchor, anchor + '    var heatmapMode by remember { mutableStateOf("Neuron") }\n    var heatmapData by remember { mutableStateOf<Map<Pair<Int, Int>, Long>>(emptyMap()) }\n', 'heatmap state')

anchor = '    LaunchedEffect(period) { refresh() }\n'
rep(anchor, anchor + '''    LaunchedEffect(period, heatmapMode) {
        val types = when (heatmapMode) {
            "Views" -> setOf(EventTypes.VIEW_START)
            "Full Stroke" -> setOf(EventTypes.FULL_STROKE_MARK, EventTypes.FULL_STROKE_START)
            "Explicit" -> setOf(EventTypes.SPIRITUAL_COOM, EventTypes.INSTANT_HARD, EventTypes.FULL_STROKE_MARK, EventTypes.FULL_STROKE_START, EventTypes.EDGE_MARK, EventTypes.GOON_START, EventTypes.CONFIRMED_NUT)
            else -> setOf(EventTypes.REACTION_UP)
        }
        heatmapData = withContext(Dispatchers.IO) { db.activityHeatmap(types, sinceForPeriod()) }
    }
''', 'heatmap load')

# Edge is now separate optional data; the historical v0.6 Edge slot was migrated
# to Full Stroke. Show the new metric prominently and remove Fastest Tap.
s = s.replace('StatCard("Edge marks", stats.edgeMarks.toString(), Modifier.weight(1f))', 'StatCard("Full Stroke", stats.fullStrokeMarks.toString(), Modifier.weight(1f))')
s = s.replace('${summary.edgeMarks} edge', '${summary.fullStrokeMarks} full-stroke')
old_row = '''        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatCard("Fastest tap", stats.quickestFirstTapMs?.let(::formatMs) ?: "—", Modifier.weight(1f))
                StatCard("Longest stare", stats.longestDwellMs?.let(::formatMs) ?: "—", Modifier.weight(1f))
                StatCard("Active hour", stats.mostActiveHour?.let(::formatHour) ?: "—", Modifier.weight(1f))
            }
        }
'''
new_row = '''        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatCard("Full Stroke time", formatMs(stats.fullStrokeDurationMs), Modifier.weight(1f))
                StatCard("Longest stare", stats.longestDwellMs?.let(::formatMs) ?: "—", Modifier.weight(1f))
                StatCard("Peak reaction hour", stats.mostActiveHour?.let(::formatHour) ?: "—", Modifier.weight(1f))
            }
        }

        item {
            ArchiveHeatmapV7(
                mode = heatmapMode,
                data = heatmapData,
                onMode = { heatmapMode = it }
            )
        }
'''
rep(old_row, new_row, 'headline metrics')

# Make the ranked section clearly purposeful and bounded instead of an endless
# raw-looking feed.
s = s.replace('item { Text("Top behavioral files", style = MaterialTheme.typography.titleLarge) }', '''item {
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text("Most interacted files", style = MaterialTheme.typography.titleLarge)
                Text("Top 12 by the combined behavioral signal for this period.", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
            }
        }''')
s = s.replace('items(stats.summaries.take(50))', 'items(stats.summaries.take(12))')

# Replace StatCard with a long-press explainer.
start = s.find('@Composable\nprivate fun StatCard(')
end = s.find('\n@Composable\nfun TagLabContent', start)
if start < 0 or end < 0:
    raise RuntimeError('v7 analytics StatCard boundaries missing')
replacement = r'''@Composable
private fun ArchiveHeatmapV7(mode: String, data: Map<Pair<Int, Int>, Long>, onMode: (String) -> Unit) {
    val max = data.values.maxOrNull()?.coerceAtLeast(1L) ?: 1L
    Surface(color = Color(0xFF111111), shape = MaterialTheme.shapes.medium) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            Text("When it happens", style = MaterialTheme.typography.titleLarge)
            Text("Day × hour activity heatmap. Switch what the cells count.", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                listOf("Neuron", "Views", "Full Stroke", "Explicit").forEach { key ->
                    TextButton(onClick = { onMode(key) }, modifier = Modifier.weight(1f)) {
                        Text(if (mode == key) "• $key" else key, maxLines = 1)
                    }
                }
            }
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Spacer(Modifier.width(30.dp))
                listOf("0", "6", "12", "18").forEach { hour -> Text(hour, Modifier.weight(1f), color = Color.Gray, style = MaterialTheme.typography.labelSmall) }
            }
            val days = listOf("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
            days.forEachIndexed { day, label ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(1.dp)) {
                    Text(label, Modifier.width(29.dp), color = Color.LightGray, style = MaterialTheme.typography.labelSmall)
                    for (hour in 0..23) {
                        val count = data[day to hour] ?: 0L
                        val strength = (count.toFloat() / max.toFloat()).coerceIn(0f, 1f)
                        Box(
                            Modifier.weight(1f).height(11.dp)
                                .background(Color(0xFFE53935).copy(alpha = 0.07f + strength * 0.93f), MaterialTheme.shapes.extraSmall)
                        )
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun StatCard(label: String, value: String, modifier: Modifier = Modifier) {
    var explain by remember(label) { mutableStateOf(false) }
    val explanation = when (label) {
        "Taps" -> "Successful Neuron-button reactions recorded in this period."
        "Sessions" -> "Distinct NeuronTap sessions. Long background gaps start a new session."
        "Confirmed nuts" -> "Only finishes you explicitly confirmed. This is ground truth and is never inferred."
        "Potential nuts" -> "Unconfirmed sessions the inference engine thinks may contain a finish. They never count as confirmed."
        "Spiritual Cooms" -> "Explicit moments where the media triggered a strong primitive 'you should finish to this right now' signal, without claiming that you actually did."
        "Full Stroke" -> "Explicit Full Stroke starts plus historical v0.6 Edge marks migrated into this metric for v0.7."
        "Instant hard" -> "Explicit rapid physical-arousal jumps, protected by a short per-media cooldown."
        "Zoomed time" -> "Time spent above normal zoom while the viewer was actually foregrounded."
        "Total viewed" -> "Foreground viewer dwell time. Time while NeuronTap is backgrounded or the screen is off is excluded."
        "Full Stroke time" -> "Time between explicit Full Stroke start and end events. Backgrounding or confirming a finish ends the active state."
        "Longest stare" -> "Largest total foreground dwell accumulated by one media item in this period."
        "Peak reaction hour" -> "Local clock hour containing the most successful Neuron-button reactions."
        else -> "A derived NeuronTap archive metric for the selected period."
    }
    if (explain) AlertDialog(
        onDismissRequest = { explain = false },
        title = { Text(label) },
        text = { Text(explanation) },
        confirmButton = { TextButton(onClick = { explain = false }) { Text("Got it") } }
    )
    Card(modifier = modifier.combinedClickable(onClick = {}, onLongClick = { explain = true })) {
        Column(Modifier.padding(10.dp)) {
            Text(value, style = MaterialTheme.typography.titleMedium)
            Text(label, style = MaterialTheme.typography.bodySmall)
        }
    }
}
'''
s = s[:start] + replacement + s[end:]
p.write_text(s)
print('Applied v7 analytics')
