from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Installability: v0.8 shipped as versionCode 8 and rescue rollback is 9.
p = ROOT / "app/build.gradle.kts"
s = p.read_text()
if "versionCode = 8" not in s or 'versionName = "0.8.0"' not in s:
    raise RuntimeError("v8 repair version anchors missing")
s = s.replace("versionCode = 8", "versionCode = 10", 1)
s = s.replace('versionName = "0.8.0"', 'versionName = "0.8.1-repair"', 1)
p.write_text(s)

# Rotation must not destroy/recreate the entire viewer/player.
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

# Preserve Gallery tab/sort/nested location through any remaining recreation.
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

# Video: native aspect ratio, honest short-video timing, exact scrubbing seeks.
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
            // TextureView stretches to its own bounds, so the view itself must
            // carry the video's aspect ratio. Otherwise landscape gets mangled.
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

# The draggable Neuron reaction button must never sit on top of the video
# timeline. The field recording and behavioral QA showed timeline swipes moving
# the reaction button instead of seeking. Keep its normal 112dp bottom margin,
# but reserve a deeper strip while video controls are visible. Apply the same
# bound to saved positions, resizing, and dragging so existing installs recover.
p = ROOT / "app/src/main/java/com/neurontap/app/ViewerUi.kt"
s = p.read_text()
old_default = '''        if (reactionXPx.isNaN()) reactionXPx = ((maxW - reactionSizePx) / 2f).coerceAtLeast(0f)
        if (reactionYPx.isNaN()) reactionYPx = (maxH - reactionSizePx - with(density) { 112.dp.toPx() }).coerceAtLeast(0f)

        LaunchedEffect(maxW, maxH, reactionSizePx) {
            reactionXPx = reactionXPx.coerceIn(0f, (maxW - reactionSizePx).coerceAtLeast(0f))
            reactionYPx = reactionYPx.coerceIn(0f, (maxH - reactionSizePx).coerceAtLeast(0f))
        }
'''
new_default = '''        val reactionBottomClearancePx = with(density) {
            (if (current.isVideo && controlsVisible) 184.dp else 112.dp).toPx()
        }
        fun reactionMaxY(sizePx: Float = reactionSizePx): Float =
            (maxH - sizePx - reactionBottomClearancePx).coerceAtLeast(0f)

        if (reactionXPx.isNaN()) reactionXPx = ((maxW - reactionSizePx) / 2f).coerceAtLeast(0f)
        if (reactionYPx.isNaN()) reactionYPx = reactionMaxY()

        LaunchedEffect(maxW, maxH, reactionSizePx, reactionBottomClearancePx) {
            reactionXPx = reactionXPx.coerceIn(0f, (maxW - reactionSizePx).coerceAtLeast(0f))
            reactionYPx = reactionYPx.coerceIn(0f, reactionMaxY())
        }
'''
if old_default not in s:
    raise RuntimeError("v8 repair reaction default/clamp anchor missing")
s = s.replace(old_default, new_default, 1)

old_resize_y = '                            reactionYPx = (centerY - nextSize / 2f).coerceIn(0f, (maxH - nextSize).coerceAtLeast(0f))\n'
new_resize_y = '                            reactionYPx = (centerY - nextSize / 2f).coerceIn(0f, reactionMaxY(nextSize))\n'
if old_resize_y not in s:
    raise RuntimeError("v8 repair reaction resize clamp anchor missing")
s = s.replace(old_resize_y, new_resize_y, 1)

old_drag_y = '                            reactionYPx = (reactionYPx + delta.y).coerceIn(0f, (maxH - reactionSizePx).coerceAtLeast(0f))\n'
new_drag_y = '                            reactionYPx = (reactionYPx + delta.y).coerceIn(0f, reactionMaxY())\n'
if old_drag_y not in s:
    raise RuntimeError("v8 repair reaction drag clamp anchor missing")
s = s.replace(old_drag_y, new_drag_y, 1)
p.write_text(s)

print("Applied v0.8.3 video/navigation/reaction-control repair")
