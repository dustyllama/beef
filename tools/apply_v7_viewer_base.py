from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/ViewerUi.kt"
s = p.read_text()

def rep(old, new, label):
    global s
    if old not in s:
        raise RuntimeError(f"v7 viewer anchor missing: {label}")
    s = s.replace(old, new, 1)

rep("import android.provider.MediaStore\n", "import android.provider.MediaStore\nimport android.view.TextureView\nimport android.widget.FrameLayout\n", "android views")
rep("import androidx.compose.foundation.background\n", "import androidx.compose.foundation.Image\nimport androidx.compose.foundation.background\n", "image import")
rep("import androidx.compose.ui.graphics.graphicsLayer\n", "import androidx.compose.ui.graphics.graphicsLayer\nimport androidx.compose.ui.graphics.asImageBitmap\n", "bitmap import")
rep("import kotlinx.coroutines.Dispatchers\n", "import kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.Job\n", "job import")

old = '''fun ViewerScreen(
    controller: AppController,
    items: List<MediaItem>,
    startMediaId: Long,
    onClose: () -> Unit,
    onLibraryChanged: () -> Unit
) {
    if (items.isEmpty()) {
        LaunchedEffect(Unit) { onClose() }
        return
    }

    val context = LocalContext.current
'''
new = '''fun ViewerScreen(
    controller: AppController,
    incomingItems: List<MediaItem>,
    startMediaId: Long,
    onClose: () -> Unit,
    onLibraryChanged: () -> Unit
) {
    if (incomingItems.isEmpty()) {
        LaunchedEffect(Unit) { onClose() }
        return
    }
    // Keep this viewer attached to media identities, not to positions in a
    // Gallery list that may reorder while the viewer is open.
    val items = remember(startMediaId) { incomingItems.toList() }

    val context = LocalContext.current
'''
rep(old, new, "stable viewer list")

# More tolerant vertical gesture recognition.
s = s.replace('val threshold = with(density) { 46.dp.toPx() }', 'val threshold = with(density) { 34.dp.toPx() }')
s = s.replace('abs(dy) > abs(dx) * 0.55f', 'abs(dy) > abs(dx) * 0.42f')

# Explicit contrast instead of depending on inherited Material colors.
s = s.replace('Text("${pagerState.currentPage + 1}/${items.size} · ${current.name}", maxLines = 1, modifier = Modifier.weight(1f))', 'Text("${pagerState.currentPage + 1}/${items.size} · ${current.name}", maxLines = 1, modifier = Modifier.weight(1f), color = Color.White)')
s = s.replace('Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")', 'Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Color.White)', 1)
s = s.replace('Icon(Icons.Default.Settings, "Video settings")', 'Icon(Icons.Default.Settings, "Video settings", tint = Color.White)')
s = s.replace('Icon(if (videosMuted) Icons.Default.VolumeOff else Icons.Default.VolumeUp, if (videosMuted) "Unmute videos" else "Mute videos")', 'Icon(if (videosMuted) Icons.Default.VolumeOff else Icons.Default.VolumeUp, if (videosMuted) "Unmute videos" else "Mute videos", tint = Color.White)')
s = s.replace('Icon(Icons.Default.Share, "Share", modifier = Modifier.size(28.dp))', 'Icon(Icons.Default.Share, "Share", tint = Color.White, modifier = Modifier.size(28.dp))')
s = s.replace('Icon(Icons.Default.Delete, "Trash", modifier = Modifier.size(30.dp))', 'Icon(Icons.Default.Delete, "Trash", tint = Color.White, modifier = Modifier.size(30.dp))')
s = s.replace('Icon(if (reactionVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility, if (reactionVisible) "Hide Neuron button" else "Show Neuron button", modifier = Modifier.size(28.dp))', 'Icon(if (reactionVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility, if (reactionVisible) "Hide Neuron button" else "Show Neuron button", tint = Color.White, modifier = Modifier.size(28.dp))')
s = s.replace('Icon(Icons.Default.MoreVert, "Info and note", modifier = Modifier.size(28.dp))', 'Icon(Icons.Default.MoreVert, "Info and note", tint = Color.White, modifier = Modifier.size(28.dp))')

# Route video pages to the v7 implementation appended by the next patch.
needle = '''        ViewerVideo(
            item = item,
'''
if needle not in s:
    raise RuntimeError("v7 viewer anchor missing: video call")
s = s.replace(needle, '''        ViewerVideoV7(
            item = item,
''', 1)

p.write_text(s)
print("Applied v7 viewer base")
