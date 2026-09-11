from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Installability: v0.8 shipped as versionCode 8 and the rescue rollback is 9.
# Every repaired candidate must therefore be >9 or Android will reject it.
# ---------------------------------------------------------------------------
p = ROOT / "app/build.gradle.kts"
s = p.read_text()
if "versionCode = 8" not in s or 'versionName = "0.8.0"' not in s:
    raise RuntimeError("v8 repair version anchors missing")
s = s.replace("versionCode = 8", "versionCode = 10", 1)
s = s.replace('versionName = "0.8.0"', 'versionName = "0.8.1-repair"', 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# Rotation: do not destroy/recreate the entire viewer/player just because the
# device rotates. Compose receives the configuration change and lays out again
# while the single ViewerVideoHost keeps the same player, position and media.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/main/AndroidManifest.xml"
s = p.read_text()
activity_anchor = 'android:name=".MainActivity"\n            android:exported="true"'
if activity_anchor not in s:
    raise RuntimeError("v8 repair MainActivity manifest anchor missing")
s = s.replace(
    activity_anchor,
    'android:name=".MainActivity"\n            android:exported="true"\n            android:configChanges="orientation|screenSize|smallestScreenSize|keyboardHidden"',
    1,
)
p.write_text(s)

# ---------------------------------------------------------------------------
# Gallery navigation state: tab/sort/nested location survive any Activity
# recreation that still occurs for reasons other than ordinary rotation.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/main/java/com/neurontap/app/GalleryUi.kt"
s = p.read_text()
if "import androidx.compose.runtime.saveable.rememberSaveable\n" not in s:
    s = s.replace(
        "import androidx.compose.runtime.rememberCoroutineScope\n",
        "import androidx.compose.runtime.rememberCoroutineScope\nimport androidx.compose.runtime.saveable.rememberSaveable\n",
        1,
    )
for old, new in [
    ("    var mode by remember { mutableStateOf(CollectionMode.ALL) }", "    var mode by rememberSaveable { mutableStateOf(CollectionMode.ALL) }"),
    ("    var sortMode by remember { mutableStateOf(SortMode.NEWEST) }", "    var sortMode by rememberSaveable { mutableStateOf(SortMode.NEWEST) }"),
    ("    var albumRoot by remember { mutableStateOf<String?>(null) }", "    var albumRoot by rememberSaveable { mutableStateOf<String?>(null) }"),
    ("    var albumGroupId by remember { mutableStateOf<String?>(null) }", "    var albumGroupId by rememberSaveable { mutableStateOf<String?>(null) }"),
]:
    if old not in s:
        raise RuntimeError(f"v8 repair gallery state anchor missing: {old}")
    s = s.replace(old, new, 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# Video viewer: preserve native aspect ratio, make short-video timing readable,
# and use exact frame seeks during deliberate scrubbing instead of repeatedly
# snapping to the same keyframe.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/main/java/com/neurontap/app/ViewerVideoV8.kt"
s = p.read_text()
if "import androidx.compose.foundation.layout.aspectRatio\n" not in s:
    s = s.replace(
        "import androidx.compose.foundation.layout.Arrangement\n",
        "import androidx.compose.foundation.layout.Arrangement\nimport androidx.compose.foundation.layout.aspectRatio\n",
        1,
    )

old = "    fun duration(mediaId: Long): Long = if (boundMediaId == mediaId) player.duration.takeIf { it > 0L } ?: 1L else 1L\n"
new = "    fun duration(mediaId: Long): Long = if (boundMediaId == mediaId) player.duration.takeIf { it > 0L } ?: 0L else 0L\n"
if old not in s:
    raise RuntimeError("v8 repair duration anchor missing")
s = s.replace(old, new, 1)

s = s.replace("player.setSeekParameters(SeekParameters.CLOSEST_SYNC)\n            player.seekTo(targetMs.coerceAtLeast(0L))", "player.setSeekParameters(SeekParameters.EXACT)\n            player.seekTo(targetMs.coerceAtLeast(0L))", 1)
s = s.replace("player.setSeekParameters(SeekParameters.CLOSEST_SYNC)\n        player.seekTo(targetMs.coerceAtLeast(0L))", "player.setSeekParameters(SeekParameters.EXACT)\n        player.seekTo(targetMs.coerceAtLeast(0L))", 1)

if "var durationMs by remember(item.id) { mutableLongStateOf(1L) }" not in s:
    raise RuntimeError("v8 repair duration state anchor missing")
s = s.replace("var durationMs by remember(item.id) { mutableLongStateOf(1L) }", "var durationMs by remember(item.id) { mutableLongStateOf(0L) }", 1)
s = s.replace("durationMs = host.duration(item.id).coerceAtLeast(1L)", "durationMs = host.duration(item.id).coerceAtLeast(0L)", 1)

old_fit = '''            val containerAspect = if (maxHeight.value > 0f) maxWidth.value / maxHeight.value else aspect
            val fitModifier = if (aspect >= containerAspect) Modifier.fillMaxWidth() else Modifier.fillMaxHeight()
'''
new_fit = '''            val safeAspect = aspect.coerceIn(0.1f, 10f)
            val containerAspect = if (maxHeight.value > 0f) maxWidth.value / maxHeight.value else safeAspect
            // TextureView stretches its surface to its own bounds. The view itself
            // therefore MUST have the video's native aspect ratio. Filling only one
            // dimension without aspectRatio() was the cause of the grotesque stretch.
            val fitModifier = if (safeAspect >= containerAspect) {
                Modifier.fillMaxWidth().aspectRatio(safeAspect)
            } else {
                Modifier.fillMaxHeight().aspectRatio(safeAspect)
            }
'''
if old_fit not in s:
    raise RuntimeError("v8 repair video fit anchor missing")
s = s.replace(old_fit, new_fit, 1)

old_slider = '''                    valueRange = 0f..durationMs.toFloat().coerceAtLeast(1f),
                    modifier = Modifier.weight(1f)
                )
                Text("${formatClockV8(if (scrubbing) scrubValue.toLong() else positionMs)} / ${formatClockV8(durationMs)}", fontSize = 10.sp, color = Color.White)
'''
new_slider = '''                    valueRange = 0f..durationMs.toFloat().coerceAtLeast(1f),
                    enabled = durationMs > 0L,
                    modifier = Modifier.weight(1f)
                )
                val shownDuration = if (durationMs > 0L) formatClockV8(durationMs) else "--:--"
                Text("${formatClockV8(if (scrubbing) scrubValue.toLong() else positionMs)} / $shownDuration", fontSize = 10.sp, color = Color.White)
'''
if old_slider not in s:
    raise RuntimeError("v8 repair slider anchor missing")
s = s.replace(old_slider, new_slider, 1)

old_clock = '''private fun formatClockV8(ms: Long): String {
    val total = (ms.coerceAtLeast(0L) / 1000L)
    val m = total / 60L
    val s = total % 60L
    return String.format(Locale.US, "%d:%02d", m, s)
}
'''
new_clock = '''private fun formatClockV8(ms: Long): String {
    val safe = ms.coerceAtLeast(0L)
    if (safe < 10_000L) return String.format(Locale.US, "%.1fs", safe / 1000.0)
    val total = safe / 1000L
    val m = total / 60L
    val s = total % 60L
    return String.format(Locale.US, "%d:%02d", m, s)
}
'''
if old_clock not in s:
    raise RuntimeError("v8 repair clock anchor missing")
s = s.replace(old_clock, new_clock, 1)
p.write_text(s)

# ---------------------------------------------------------------------------
# Thumbnail requests: bound decode size and give Coil stable cache identities.
# Earlier version scripts also touch this function, so patch the model block by
# structural boundaries instead of assuming one exact historical string.
# ---------------------------------------------------------------------------
p = ROOT / "app/src/main/java/com/neurontap/app/MediaThumbnail.kt"
s = p.read_text()
if "import androidx.compose.runtime.remember\n" not in s:
    if "import androidx.compose.runtime.Composable\n" not in s:
        raise RuntimeError("v8 repair thumbnail composable import missing")
    s = s.replace("import androidx.compose.runtime.Composable\n", "import androidx.compose.runtime.Composable\nimport androidx.compose.runtime.remember\n", 1)
start = s.find("    val model: Any = ")
end = s.find("    AsyncImage(", start)
if start < 0 or end < 0:
    raise RuntimeError("v8 repair thumbnail model boundaries missing")
new_model = '''    val model: Any = remember(item.id, item.uri, item.modified, item.isVideo) {
        if (item.isVideo) {
            val cacheKey = "video-thumb:${item.id}:${item.modified}"
            ImageRequest.Builder(context)
                .data(Uri.parse(item.uri))
                .decoderFactory(VideoFrameDecoder.Factory())
                .size(384)
                .memoryCacheKey(cacheKey)
                .diskCacheKey(cacheKey)
                .crossfade(false)
                .build()
        } else {
            Uri.parse(item.uri)
        }
    }
'''
s = s[:start] + new_model + s[end:]
p.write_text(s)

print("Applied v0.8.1 catastrophic video/navigation repair")
