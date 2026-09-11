from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app/src/main/java/com/neurontap/app"

# MediaStore indexing -------------------------------------------------------
# Keep image/video failures isolated, but never make them invisible again.
# Explicitly ignore pending rows so an in-flight scanner record cannot be
# mistaken for usable media.
p = SRC / "MediaStoreIndexer.kt"
s = p.read_text()

if "import android.util.Log\n" not in s:
    s = s.replace("import android.provider.MediaStore\n", "import android.provider.MediaStore\nimport android.util.Log\n", 1)

old_index = '''object MediaStoreIndexer {
    suspend fun index(context: Context, db: NeuronDb): Int = withContext(Dispatchers.IO) {
        var count = 0
        db.runMediaBatch {
            count += runCatching { indexCollection(context, db, MediaStore.Images.Media.EXTERNAL_CONTENT_URI) }.getOrDefault(0)
            count += runCatching { indexCollection(context, db, MediaStore.Video.Media.EXTERNAL_CONTENT_URI) }.getOrDefault(0)
        }
        count
    }
'''
new_index = '''object MediaStoreIndexer {
    private const val TAG = "MediaStoreIndexer"

    suspend fun index(context: Context, db: NeuronDb): Int = withContext(Dispatchers.IO) {
        var count = 0
        db.runMediaBatch {
            listOf(
                MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                MediaStore.Video.Media.EXTERNAL_CONTENT_URI
            ).forEach { collection ->
                try {
                    count += indexCollection(context, db, collection)
                } catch (t: Throwable) {
                    // One broken provider/collection must not hide the other,
                    // but QA and bug reports need the actual exception.
                    Log.e(TAG, "Failed to index $collection", t)
                }
            }
        }
        count
    }
'''
if old_index not in s:
    raise RuntimeError("v8 indexing repair index anchor missing")
s = s.replace(old_index, new_index, 1)

old_query = '''        var count = 0
        context.contentResolver.query(collection, projection, null, null, "${MediaStore.MediaColumns.DATE_MODIFIED} DESC")?.use { cursor ->
'''
new_query = '''        var count = 0
        val selection = if (modern) "${MediaStore.MediaColumns.IS_PENDING}=0" else null
        context.contentResolver.query(collection, projection, selection, null, "${MediaStore.MediaColumns.DATE_MODIFIED} DESC")?.use { cursor ->
'''
if old_query not in s:
    raise RuntimeError("v8 indexing repair query anchor missing")
s = s.replace(old_query, new_query, 1)
p.write_text(s)

# Gallery live observation -------------------------------------------------
p = SRC / "GalleryUi.kt"
s = p.read_text()

for anchor, replacement in [
    ("import android.content.pm.PackageManager\n", "import android.content.pm.PackageManager\nimport android.database.ContentObserver\n"),
    ("import android.os.Build\n", "import android.os.Build\nimport android.os.Handler\nimport android.os.Looper\n"),
    ("import androidx.compose.runtime.Composable\n", "import androidx.compose.runtime.Composable\nimport androidx.compose.runtime.DisposableEffect\n"),
]:
    if replacement not in s:
        if anchor not in s:
            raise RuntimeError(f"v8 indexing repair import anchor missing: {anchor!r}")
        s = s.replace(anchor, replacement, 1)

if "import android.provider.MediaStore\n" not in s:
    anchor = "import android.os.Looper\n"
    if anchor not in s:
        raise RuntimeError("v8 indexing repair MediaStore import anchor missing")
    s = s.replace(anchor, anchor + "import android.provider.MediaStore\n", 1)

# fix_v8_scroll_churn normally adds delay before this repair. Keep this patch
# independently safe if the workflow order changes later.
if "import kotlinx.coroutines.delay\n" not in s:
    anchor = "import kotlinx.coroutines.Dispatchers\n"
    if anchor not in s:
        raise RuntimeError("v8 indexing repair coroutine import anchor missing")
    s = s.replace(anchor, anchor + "import kotlinx.coroutines.delay\n", 1)

state_anchor = '    var albumLayout by remember { mutableStateOf(AlbumLayoutState()) }\n'
if state_anchor not in s:
    raise RuntimeError("v8 indexing repair screen-state anchor missing")
if "mediaChangeGeneration" not in s:
    s = s.replace(state_anchor, state_anchor + '    var mediaChangeGeneration by remember { mutableIntStateOf(0) }\n', 1)

# Replace the generated scanDevice function by boundaries rather than an exact
# body. v7/v8 patches legitimately add bookkeeping to the neighboring reload
# path, and an exact text anchor made the repair itself fail before compilation.
scan_start = s.find("    suspend fun scanDevice(")
scan_end = s.find("\n\n    suspend fun rescanEverything()", scan_start)
if scan_start < 0 or scan_end < 0:
    raise RuntimeError("v8 indexing repair scanDevice boundaries missing")
new_scan = '''    suspend fun scanDevice(showStatus: Boolean = true) {
        if (!hasAnyMediaPermission()) return
        if (showStatus) message = "Refreshing device library…"
        val count = withContext(Dispatchers.IO) { MediaStoreIndexer.index(context, controller.db) }
        prefs.edit().putLong("last_device_scan", System.currentTimeMillis()).apply()
        reload()
        if (showStatus) message = "$count device media items indexed"
    }'''
s = s[:scan_start] + new_scan + s[scan_end:]

# Keep whatever ActivityResult plumbing preceding patches produced, changing
# only the successful permission path so initial indexing is quiet.
permission_start = s.find("    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions())")
permission_end = s.find("\n\n    val folderPicker", permission_start)
if permission_start < 0 or permission_end < 0:
    raise RuntimeError("v8 indexing repair permission callback boundaries missing")
permission_block = s[permission_start:permission_end]
if "scanDevice(showStatus = false)" not in permission_block:
    if "scanDevice()" not in permission_block:
        raise RuntimeError("v8 indexing repair permission scan call missing")
    permission_block = permission_block.replace("scanDevice()", "scanDevice(showStatus = false)", 1)
s = s[:permission_start] + permission_block + s[permission_end:]

# Replace startup by semantic boundaries. A gallery must reflect MediaStore at
# every cold start: the old ten-minute throttle could preserve an empty DB when
# Android's scanner finalized rows just after NeuronTap's first query.
startup_start = s.find("    LaunchedEffect(Unit) {\n        controller.log(null, EventTypes.GALLERY_OPEN)")
startup_end = s.find("\n\n    LaunchedEffect(mode,", startup_start)
if startup_start < 0 or startup_end < 0:
    raise RuntimeError("v8 indexing repair startup boundaries missing")
new_startup = '''    LaunchedEffect(Unit) {
        controller.log(null, EventTypes.GALLERY_OPEN)
        prefs.edit().putStringSet("linked_roots", linkedRoots).apply()
        reload()
        if (!hasAnyMediaPermission()) permissionLauncher.launch(mediaPermissions)
        else scanDevice(showStatus = false)
    }

    // MediaStore is a live source, not a one-shot import. Observe both provider
    // collections and debounce scanner bursts. The generation-keyed effect is
    // cancelled/restarted when more changes arrive, so only settled state is
    // indexed. This also closes the launch-while-scanner-is-pending race.
    DisposableEffect(hasAnyMediaPermission()) {
        if (!hasAnyMediaPermission()) {
            onDispose { }
        } else {
            val observer = object : ContentObserver(Handler(Looper.getMainLooper())) {
                override fun onChange(selfChange: Boolean) {
                    mediaChangeGeneration += 1
                }
            }
            context.contentResolver.registerContentObserver(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, true, observer)
            context.contentResolver.registerContentObserver(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, true, observer)
            onDispose { runCatching { context.contentResolver.unregisterContentObserver(observer) } }
        }
    }

    LaunchedEffect(mediaChangeGeneration) {
        if (mediaChangeGeneration == 0 || !hasAnyMediaPermission()) return@LaunchedEffect
        delay(500L)
        scanDevice(showStatus = false)
    }'''
s = s[:startup_start] + new_startup + s[startup_end:]

p.write_text(s)
print("Applied v0.8.1 live MediaStore indexing repair")
