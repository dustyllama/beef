from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Patch anchor not found: {label}")
    return text.replace(old, new, 1)

def replace_between(text: str, start: str, end: str, new: str, label: str) -> str:
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"Patch start not found: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"Patch end not found: {label}")
    return text[:a] + new + text[b:]

# -------------------------------------------------------------------------
# Versioning
# -------------------------------------------------------------------------
build = ROOT / "app/build.gradle.kts"
s = build.read_text()
s = replace_once(s, 'versionCode = 4', 'versionCode = 6', 'versionCode')
s = replace_once(s, 'versionName = "0.4.0"', 'versionName = "0.6.0"', 'versionName')
build.write_text(s)

# -------------------------------------------------------------------------
# Models / event vocabulary / actionable archive insights
# -------------------------------------------------------------------------
models = ROOT / "app/src/main/java/com/neurontap/app/Models.kt"
s = models.read_text()
s = replace_once(
    s,
    'data class SmartGallery(\n    val id: String,\n    val title: String,\n    val subtitle: String,\n    val mediaIds: List<Long>\n)\n',
    'data class SmartGallery(\n    val id: String,\n    val title: String,\n    val subtitle: String,\n    val mediaIds: List<Long>\n)\n\ndata class ArchiveInsight(\n    val title: String,\n    val body: String,\n    val mediaId: Long? = null,\n    val galleryId: String? = null\n)\n',
    'ArchiveInsight model'
)
s = replace_once(s, 'val insights: List<String> = emptyList()', 'val insights: List<ArchiveInsight> = emptyList()', 'insight type')
s = replace_once(
    s,
    '    const val PAN_POINT = "PAN_POINT"       // x/y = final translation\n',
    '    const val PAN_POINT = "PAN_POINT"       // x/y = final translation\n    const val DOUBLE_TAP_FOCUS = "DOUBLE_TAP_FOCUS" // raw x/y focal coordinate\n',
    'double tap event'
)
s = replace_once(
    s,
    '    const val VIDEO_SCRUB_END = "VIDEO_SCRUB_END"\n',
    '    const val VIDEO_SCRUB_END = "VIDEO_SCRUB_END"\n    const val VIDEO_FRAME_EXPORT = "VIDEO_FRAME_EXPORT"\n',
    'frame export event'
)
s = replace_once(
    s,
    '    const val FAVORITE_UNSET = "FAVORITE_UNSET"\n',
    '    const val FAVORITE_UNSET = "FAVORITE_UNSET"\n    const val MEDIA_TRASH = "MEDIA_TRASH"\n    const val MEDIA_NOTE_SET = "MEDIA_NOTE_SET"\n    const val EXTERNAL_PICK = "EXTERNAL_PICK"\n',
    'media metadata events'
)
models.write_text(s)

# -------------------------------------------------------------------------
# Database: notes/search + conservative identity continuity across moves
# -------------------------------------------------------------------------
dbpath = ROOT / "app/src/main/java/com/neurontap/app/NeuronDb.kt"
s = dbpath.read_text()
s = replace_once(s, 'SQLiteOpenHelper(context, "neurontap.db", null, 4)', 'SQLiteOpenHelper(context, "neurontap.db", null, 5)', 'db version')
s = replace_once(
    s,
    '                favorite INTEGER NOT NULL DEFAULT 0,\n                deleted INTEGER NOT NULL DEFAULT 0\n',
    '                favorite INTEGER NOT NULL DEFAULT 0,\n                deleted INTEGER NOT NULL DEFAULT 0,\n                note TEXT NOT NULL DEFAULT \'\'\n',
    'media note schema'
)
s = replace_once(
    s,
    '        if (oldVersion < 4) {\n            db.execSQL("ALTER TABLE media ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0")\n            db.execSQL("CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(type, timestamp_ms)")\n        }\n',
    '        if (oldVersion < 4) {\n            db.execSQL("ALTER TABLE media ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0")\n            db.execSQL("CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(type, timestamp_ms)")\n        }\n        if (oldVersion < 5) {\n            db.execSQL("ALTER TABLE media ADD COLUMN note TEXT NOT NULL DEFAULT \'\'")\n        }\n',
    'db migration 5'
)
new_upsert = '''    fun upsertMedia(rootUri: String, uri: String, name: String, mime: String, size: Long, modified: Long): Long {
        val db = writableDatabase
        fun existingIdForUri(): Long? = db.rawQuery("SELECT id FROM media WHERE uri=?", arrayOf(uri)).use { c -> if (c.moveToFirst()) c.getLong(0) else null }

        val values = ContentValues().apply {
            put("root_uri", rootUri); put("uri", uri); put("display_name", name); put("mime", mime)
            put("size", size); put("modified", modified); put("indexed_at", System.currentTimeMillis()); put("deleted", 0)
        }

        existingIdForUri()?.let { id ->
            db.update("media", values, "id=?", arrayOf(id.toString()))
            return id
        }

        // A MediaStore URI can change when a file is moved between folders. Reuse a
        // unique same-file candidate so favorites, tags, notes and behavioral history
        // remain attached to the media instead of the old path.
        val moveCandidates = db.rawQuery(
            "SELECT id FROM media WHERE deleted=0 AND size=? AND modified=? AND mime=? ORDER BY indexed_at DESC LIMIT 2",
            arrayOf(size.toString(), modified.toString(), mime)
        ).use { c -> buildList { while (c.moveToNext()) add(c.getLong(0)) } }
        if (moveCandidates.size == 1) {
            val id = moveCandidates.first()
            db.update("media", values, "id=?", arrayOf(id.toString()))
            return id
        }

        db.insertWithOnConflict("media", null, values, SQLiteDatabase.CONFLICT_IGNORE)
        return existingIdForUri() ?: -1L
    }

'''
s = replace_between(s, '    fun upsertMedia(', '    fun loadAllMedia()', new_upsert, 'upsert media continuity')
s = replace_once(
    s,
    '    fun tagsForMedia(mediaId: Long): List<String> = readableDatabase.rawQuery(\n        "SELECT tag FROM media_tags WHERE media_id=? ORDER BY tag", arrayOf(mediaId.toString())\n    ).use { c -> buildList { while (c.moveToNext()) add(c.getString(0)) } }\n',
    '''    fun tagsForMedia(mediaId: Long): List<String> = readableDatabase.rawQuery(
        "SELECT tag FROM media_tags WHERE media_id=? ORDER BY tag", arrayOf(mediaId.toString())
    ).use { c -> buildList { while (c.moveToNext()) add(c.getString(0)) } }

    fun noteForMedia(mediaId: Long): String = readableDatabase.rawQuery(
        "SELECT note FROM media WHERE id=?", arrayOf(mediaId.toString())
    ).use { c -> if (c.moveToFirst()) c.getString(0).orEmpty() else "" }

    fun setNote(mediaId: Long, note: String) {
        writableDatabase.update("media", ContentValues().apply { put("note", note.trim()) }, "id=?", arrayOf(mediaId.toString()))
    }

    fun searchMediaIds(query: String): Set<Long> {
        val q = query.trim()
        if (q.isBlank()) return emptySet()
        val like = "%$q%"
        return readableDatabase.rawQuery(
            """SELECT DISTINCT m.id FROM media m LEFT JOIN media_tags t ON t.media_id=m.id
               WHERE m.deleted=0 AND (m.display_name LIKE ? COLLATE NOCASE OR m.note LIKE ? COLLATE NOCASE OR t.tag LIKE ? COLLATE NOCASE)""".trimIndent(),
            arrayOf(like, like, like)
        ).use { c -> buildSet { while (c.moveToNext()) add(c.getLong(0)) } }
    }
''',
    'notes and search'
)
dbpath.write_text(s)

# -------------------------------------------------------------------------
# Analytics: actionable interpretation cards
# -------------------------------------------------------------------------
engine = ROOT / "app/src/main/java/com/neurontap/app/AnalyticsEngine.kt"
s = engine.read_text()
start = '    fun generateInsights(summaries: List<MediaBehaviorSummary>, potential: List<PotentialNutCandidate>): List<String> {'
end = '    private fun formatSeconds(ms: Long): String'
new = '''    fun generateInsights(summaries: List<MediaBehaviorSummary>, potential: List<PotentialNutCandidate>): List<ArchiveInsight> {
        if (summaries.isEmpty()) return listOf(ArchiveInsight("Archive is still empty", "Go create evidence."))
        val top = summaries.maxByOrNull { it.attractionScore }
        val explorer = summaries.maxByOrNull { it.explorationScore }
        val returned = summaries.maxByOrNull { it.returnCount }
        val fastest = summaries.filter { it.quickestTapMs != null }.minByOrNull { it.quickestTapMs!! }
        val confirmed = summaries.sumOf { it.confirmedNuts }
        val spiritual = summaries.sumOf { it.spiritualCooms }
        val edge = summaries.sumOf { it.edgeMarks }
        return buildList {
            top?.let { add(ArchiveInsight("Highest combined behavioral signal", "${it.name} — ${it.taps} taps, ${it.returnCount} returns, ${formatSeconds(it.dwellMs)} viewed.", mediaId = it.mediaId)) }
            explorer?.takeIf { it.explorationScore > 0 }?.let { add(ArchiveInsight("Most intensely explored", "${it.name} — max zoom ${"%.1f".format(it.maxZoomMilli / 1000.0)}×, ${formatSeconds(it.zoomedDwellMs)} zoomed, ${it.videoSeeks} seeks.", mediaId = it.mediaId)) }
            returned?.takeIf { it.returnCount > 0 }?.let { add(ArchiveInsight("Most persistent return magnet", "${it.name} — ${it.returnCount} repeat openings beyond session-first views.", mediaId = it.mediaId)) }
            fastest?.let { add(ArchiveInsight("Fastest recorded neuron activation", "${it.name} at ${it.quickestTapMs}ms.", mediaId = it.mediaId)) }
            if (spiritual > confirmed && spiritual > 0) add(ArchiveInsight("Could and did are different states", "Spiritual Coom marks outnumber confirmed nuts $spiritual to $confirmed.", galleryId = "spiritual"))
            if (edge > 0) add(ArchiveInsight("Edge anchors accumulating", "You explicitly marked the edge $edge time${if (edge == 1) "" else "s"}; these are anchors for future automatic edge-pattern inference.", galleryId = "edge"))
            if (potential.isNotEmpty()) add(ArchiveInsight("Potential-nut calculator", "${potential.size} unconfirmed accusation${if (potential.size == 1) "" else "s"}. Confirmed nuts remain separate ground truth.", galleryId = "potential"))
        }.take(8)
    }

'''
s = replace_between(s, start, end, new, 'structured insights')
engine.write_text(s)

# -------------------------------------------------------------------------
# Main activity: correct Gallery naming, no duplicate Archives scaffold,
# and expose NeuronTap as an Android image/video chooser.
# -------------------------------------------------------------------------
main = ROOT / "app/src/main/java/com/neurontap/app/MainActivity.kt"
main.write_text(r'''package com.neurontap.app

import android.content.ClipData
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.core.view.WindowCompat

class MainActivity : ComponentActivity() {
    private lateinit var controller: AppController

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, true)
        window.statusBarColor = android.graphics.Color.BLACK
        window.navigationBarColor = android.graphics.Color.BLACK
        controller = AppController(this, NeuronDb(this))

        val externalPick = intent?.action == Intent.ACTION_GET_CONTENT || intent?.action == Intent.ACTION_PICK
        val requestedMime = intent?.type
        setContent {
            NeuronTapTheme {
                NeuronTapApp(
                    controller = controller,
                    externalPick = externalPick,
                    requestedMime = requestedMime,
                    onPicked = { item ->
                        val uri = Uri.parse(item.uri)
                        controller.log(item.id, EventTypes.EXTERNAL_PICK)
                        val result = Intent().apply {
                            data = uri
                            clipData = ClipData.newRawUri(item.name, uri)
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }
                        setResult(RESULT_OK, result)
                        finish()
                    }
                )
            }
        }
    }

    override fun onStart() {
        super.onStart()
        controller.onForeground()
    }

    override fun onStop() {
        controller.onBackground()
        super.onStop()
    }
}

private enum class AppPage { GALLERY, WRAPPED, TAGS }

@Composable
private fun NeuronTapTheme(content: @Composable () -> Unit) {
    val colors = darkColorScheme(
        primary = Color(0xFFE53935),
        onPrimary = Color.White,
        background = Color.Black,
        onBackground = Color.White,
        surface = Color.Black,
        onSurface = Color.White,
        surfaceVariant = Color(0xFF151515),
        onSurfaceVariant = Color(0xFFE0E0E0),
        secondaryContainer = Color(0xFF2A1114),
        onSecondaryContainer = Color.White
    )
    MaterialTheme(colorScheme = colors, content = content)
}

@Composable
private fun NeuronTapApp(
    controller: AppController,
    externalPick: Boolean,
    requestedMime: String?,
    onPicked: (MediaItem) -> Unit
) {
    var page by remember { mutableStateOf(AppPage.GALLERY) }
    when (page) {
        AppPage.GALLERY -> CollectionScreen(
            controller = controller,
            onOpenWrapped = { page = AppPage.WRAPPED },
            onOpenTags = { page = AppPage.TAGS },
            pickMode = externalPick,
            pickMime = requestedMime,
            onPickMedia = onPicked
        )
        AppPage.WRAPPED -> WrappedContent(controller = controller, onExit = { page = AppPage.GALLERY })
        AppPage.TAGS -> AnalyticsScaffold("Tag Lab", onBack = { page = AppPage.GALLERY }) {
            TagLabContent(controller.db)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AnalyticsScaffold(title: String, onBack: () -> Unit, content: @Composable () -> Unit) {
    BackHandler { onBack() }
    Scaffold(
        containerColor = Color.Black,
        topBar = {
            TopAppBar(
                title = { Text(title) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Black)
            )
        }
    ) { padding ->
        androidx.compose.foundation.layout.Box(Modifier.fillMaxSize().padding(padding)) { content() }
    }
}
''')

# -------------------------------------------------------------------------
# Android picker integration
# -------------------------------------------------------------------------
manifest = ROOT / "app/src/main/AndroidManifest.xml"
manifest.write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />
    <uses-permission android:name="android.permission.READ_MEDIA_VIDEO" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" />

    <application
        android:allowBackup="true"
        android:label="NeuronTap"
        android:theme="@style/Theme.NeuronTap">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
            <intent-filter>
                <action android:name="android.intent.action.GET_CONTENT" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="android.intent.category.OPENABLE" />
                <data android:mimeType="image/*" />
                <data android:mimeType="video/*" />
            </intent-filter>
            <intent-filter>
                <action android:name="android.intent.action.PICK" />
                <category android:name="android.intent.category.DEFAULT" />
                <data android:mimeType="image/*" />
                <data android:mimeType="video/*" />
            </intent-filter>
        </activity>
    </application>
</manifest>
''')

# -------------------------------------------------------------------------
# Thumbnail cache tuning. Video thumbnails deliberately use a nonzero frame
# to avoid the common all-black first frame.
# -------------------------------------------------------------------------
thumb = ROOT / "app/src/main/java/com/neurontap/app/MediaThumbnail.kt"
thumb.write_text(r'''package com.neurontap.app

import android.net.Uri
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import coil.compose.AsyncImage
import coil.decode.VideoFrameDecoder
import coil.request.ImageRequest
import coil.request.videoFrameMillis
import coil.size.Precision

@Composable
fun MediaThumbnail(
    item: MediaItem,
    modifier: Modifier = Modifier,
    contentScale: ContentScale = ContentScale.Crop,
    contentDescription: String? = item.name
) {
    val context = LocalContext.current
    val key = "nt-thumb:${item.uri}:${item.modified}:${item.size}"
    val request = ImageRequest.Builder(context)
        .data(Uri.parse(item.uri))
        .size(512, 512)
        .precision(Precision.INEXACT)
        .memoryCacheKey(key)
        .diskCacheKey(key)
        .crossfade(false)
        .apply {
            if (item.isVideo) {
                decoderFactory(VideoFrameDecoder.Factory())
                videoFrameMillis(750)
            }
        }
        .build()
    AsyncImage(model = request, contentDescription = contentDescription, modifier = modifier, contentScale = contentScale)
}
''')

# -------------------------------------------------------------------------
# Gallery / Albums / Collections UX
# -------------------------------------------------------------------------
gallery = ROOT / "app/src/main/java/com/neurontap/app/GalleryUi.kt"
s = gallery.read_text()
s = replace_once(
    s,
    'fun CollectionScreen(controller: AppController, onOpenWrapped: () -> Unit, onOpenTags: () -> Unit) {',
    'fun CollectionScreen(controller: AppController, onOpenWrapped: () -> Unit, onOpenTags: () -> Unit, pickMode: Boolean = false, pickMime: String? = null, onPickMedia: ((MediaItem) -> Unit)? = null) {',
    'CollectionScreen picker args'
)
s = replace_once(
    s,
    '    suspend fun scanDevice() {\n        if (!hasAnyMediaPermission()) return\n        message = "Refreshing device library…"\n        val count = withContext(Dispatchers.IO) { MediaStoreIndexer.index(context, controller.db) }\n        prefs.edit().putLong("last_device_scan", System.currentTimeMillis()).apply()\n        reload()\n        message = "$count device media items indexed"\n    }\n\n    suspend fun rescanEverything() {\n        scanDevice()\n        var extra = 0\n        linkedRoots.forEach { root -> extra += withContext(Dispatchers.IO) { MediaIndexer.index(context, controller.db, Uri.parse(root)) } }\n        reload()\n        if (extra > 0) message = "Library refreshed · $extra linked-folder items checked"\n    }\n',
    '    suspend fun scanDevice() {\n        if (!hasAnyMediaPermission()) return\n        withContext(Dispatchers.IO) { MediaStoreIndexer.index(context, controller.db) }\n        prefs.edit().putLong("last_device_scan", System.currentTimeMillis()).apply()\n        reload()\n    }\n\n    suspend fun rescanEverything() {\n        scanDevice()\n        linkedRoots.forEach { root -> withContext(Dispatchers.IO) { MediaIndexer.index(context, controller.db, Uri.parse(root)) } }\n        reload()\n    }\n',
    'quiet indexing'
)
s = replace_once(
    s,
    '            scope.launch {\n                message = "Indexing linked folder…"\n                val count = withContext(Dispatchers.IO) { MediaIndexer.index(context, controller.db, uri) }\n                reload()\n                message = "$count items linked"\n            }\n',
    '            scope.launch {\n                withContext(Dispatchers.IO) { MediaIndexer.index(context, controller.db, uri) }\n                reload()\n            }\n',
    'quiet folder indexing'
)
s = replace_once(s, 'title = { Text("Linked folders") }', 'title = { Text("Linked folders & cloud") }', 'linked folder title')
s = replace_once(
    s,
    'Text("Android\'s media library is scanned automatically. Add any other accessible folder here.")',
    'Text("Android media is scanned automatically. You can also link accessible device folders or cloud/document-provider folders here.")',
    'cloud folder copy'
)
s = replace_once(s, 'Text("Add folder")', 'Text("Link folder / cloud")', 'folder action label')

old_lists = '''    val baseList = remember(media, mode, albumRoot) {
        when {
            albumRoot != null -> media.filter { it.rootUri == albumRoot }
            mode == CollectionMode.VIDEOS -> media.filter { it.isVideo }
            mode == CollectionMode.FAVORITES -> media.filter { it.favorite }
            else -> media
        }
    }
    val visibleMedia = remember(baseList, searchText, sortMode) {
        val searched = if (searchText.isBlank()) baseList else baseList.filter { it.name.contains(searchText, ignoreCase = true) }
        when (sortMode) {
            SortMode.NEWEST -> searched.sortedByDescending { it.modified }
            SortMode.OLDEST -> searched.sortedBy { it.modified }
            SortMode.NAME -> searched.sortedBy { it.name.lowercase() }
        }
    }
'''
new_lists = '''    val purposeMedia = remember(media, pickMode, pickMime) {
        if (!pickMode) media else when {
            pickMime?.startsWith("image/") == true -> media.filter { !it.isVideo }
            pickMime?.startsWith("video/") == true -> media.filter { it.isVideo }
            else -> media
        }
    }
    val baseList = remember(purposeMedia, mode, albumRoot) {
        when {
            albumRoot != null -> purposeMedia.filter { it.rootUri == albumRoot }
            mode == CollectionMode.VIDEOS -> purposeMedia.filter { it.isVideo }
            mode == CollectionMode.FAVORITES -> purposeMedia.filter { it.favorite }
            else -> purposeMedia
        }
    }
    val searchIds = remember(searchText, media) {
        if (searchText.isBlank()) null else runCatching { controller.db.searchMediaIds(searchText) }.getOrDefault(emptySet())
    }
    val visibleMedia = remember(baseList, searchText, searchIds, sortMode) {
        val searched = if (searchText.isBlank()) baseList else baseList.filter { it.id in (searchIds ?: emptySet()) }
        when (sortMode) {
            SortMode.NEWEST -> searched.sortedByDescending { it.modified }
            SortMode.OLDEST -> searched.sortedBy { it.modified }
            SortMode.NAME -> searched.sortedBy { it.name.lowercase() }
        }
    }
'''
s = replace_once(s, old_lists, new_lists, 'search notes/tags')

s = replace_once(
    s,
    '    val groupName = albumGroupId?.let { albumLayout.groups[it]?.name }\n    val title = albumRoot?.let(::albumLabel) ?: groupName ?: "COLLECTION"\n',
    '    val groupName = albumGroupId?.let { albumLayout.groups[it]?.name }\n    val title = albumRoot?.let(::albumLabel) ?: groupName ?: when (mode) {\n        CollectionMode.ALL -> if (pickMode) "PICK MEDIA" else "GALLERY"\n        CollectionMode.VIDEOS -> "VIDEOS"\n        CollectionMode.FAVORITES -> "FAVORITES"\n        CollectionMode.ALBUMS -> "ALBUMS"\n    }\n',
    'gallery title semantics'
)

s = replace_once(s, 'Text("Search filenames")', 'Text("Search filenames, tags, or notes")', 'search placeholder')
s = replace_once(s, 'Text("Linked folders")', 'Text("Linked folders & cloud")', 'linked folders menu')
s = replace_once(s, 'Text("Refresh library")', 'Text("Refresh library silently")', 'refresh menu wording')

# Add global default toggle for the Neuron button.
s = replace_once(
    s,
    '                                DropdownMenuItem(text = { Text("Log confirmed nut") }, leadingIcon = { Icon(Icons.Default.CheckCircle, null) }, onClick = { menuOpen = false; showFinishDialog = true })\n',
    '                                DropdownMenuItem(text = { Text("Log confirmed nut") }, leadingIcon = { Icon(Icons.Default.CheckCircle, null) }, onClick = { menuOpen = false; showFinishDialog = true })\n                                DropdownMenuItem(text = { Text(if (prefs.getBoolean("reaction_default_visible", true)) "Neuron button default: shown" else "Neuron button default: hidden") }, onClick = {\n                                    val next = !prefs.getBoolean("reaction_default_visible", true)\n                                    prefs.edit().putBoolean("reaction_default_visible", next).apply()\n                                    menuOpen = false\n                                })\n',
    'reaction default menu'
)

# Swipe horizontally between Gallery / Videos / Favorites / Albums.
s = replace_once(
    s,
    '    Scaffold(\n        containerColor = Color.Black,\n',
    '''    val modeSwipeModifier = Modifier.pointerInput(mode, albumRoot, albumGroupId) {
        if (albumRoot == null && albumGroupId == null) {
            val threshold = 92.dp.toPx()
            awaitEachGesture {
                val first = awaitFirstDown(requireUnconsumed = false)
                var previous = first.position
                var dx = 0f
                var dy = 0f
                var claimed = false
                var multiTouch = false
                while (true) {
                    val event = awaitPointerEvent()
                    val pressed = event.changes.filter { it.pressed }
                    if (pressed.isEmpty()) break
                    if (pressed.size > 1) { multiTouch = true; break }
                    val change = pressed.first()
                    val delta = change.position - previous
                    previous = change.position
                    dx += delta.x; dy += delta.y
                    if (!claimed && abs(dx) > 24.dp.toPx() && abs(dx) > abs(dy) * 1.35f) claimed = true
                    if (claimed) change.consume()
                }
                if (!multiTouch && claimed && abs(dx) > threshold && abs(dx) > abs(dy) * 1.35f) {
                    val modes = listOf(CollectionMode.ALL, CollectionMode.VIDEOS, CollectionMode.FAVORITES, CollectionMode.ALBUMS)
                    val current = modes.indexOf(mode).coerceAtLeast(0)
                    val next = if (dx < 0) (current + 1).coerceAtMost(modes.lastIndex) else (current - 1).coerceAtLeast(0)
                    if (next != current) {
                        mode = modes[next]
                        albumRoot = null; albumGroupId = null
                        controller.log(null, EventTypes.GALLERY_MODE, details = "gesture=${mode.name}")
                    }
                }
            }
        }
    }

    Scaffold(
        containerColor = Color.Black,
''',
    'gallery mode swipe'
)
s = replace_once(
    s,
    '        Box(Modifier.fillMaxSize().padding(padding).background(Color.Black)) {\n',
    '        Box(Modifier.fillMaxSize().padding(padding).background(Color.Black).then(modeSwipeModifier)) {\n',
    'apply mode swipe'
)

s = replace_once(
    s,
    '                    onOpen = { viewerStartId = it.id },\n',
    '                    scrollKey = "${albumRoot ?: mode.name}",\n                    onOpen = { item -> if (pickMode) onPickMedia?.invoke(item) else viewerStartId = item.id },\n',
    'picker open + scroll key'
)

# MediaGrid: restore exact scroll row/offset when returning from viewer.
s = replace_once(
    s,
    '    columns: Int,\n    onColumnsChanged: (Int) -> Unit,\n',
    '    columns: Int,\n    scrollKey: String,\n    onColumnsChanged: (Int) -> Unit,\n',
    'MediaGrid scroll key signature'
)
s = replace_once(
    s,
    '    var currentColumns by remember(columns) { mutableIntStateOf(columns) }\n    val gridState = rememberLazyGridState()\n',
    '''    var currentColumns by remember(columns) { mutableIntStateOf(columns) }
    val localPrefs = LocalContext.current.getSharedPreferences("neurontap", 0)
    val savedIndex = remember(scrollKey) { localPrefs.getInt("grid_index_$scrollKey", 0).coerceAtLeast(0) }
    val savedOffset = remember(scrollKey) { localPrefs.getInt("grid_offset_$scrollKey", 0).coerceAtLeast(0) }
    val gridState = rememberLazyGridState(savedIndex, savedOffset)
''',
    'grid scroll state'
)
s = replace_once(
    s,
    '            if (delta != 0) controller.log(null, EventTypes.GALLERY_SCROLL, value = delta.toLong(), details = "index=$index;columns=$currentColumns")\n            lastIndex = index\n',
    '            if (delta != 0) controller.log(null, EventTypes.GALLERY_SCROLL, value = delta.toLong(), details = "index=$index;columns=$currentColumns")\n            localPrefs.edit().putInt("grid_index_$scrollKey", gridState.firstVisibleItemIndex).putInt("grid_offset_$scrollKey", gridState.firstVisibleItemScrollOffset).apply()\n            lastIndex = index\n',
    'persist media grid scroll'
)

# Album/Collection grid exact scroll restoration.
s = replace_once(
    s,
    '    val bounds = remember { mutableStateMapOf<String, Rect>() }\n',
    '''    val albumScrollKey = "album_grid_${groupId ?: "root"}"
    val albumGridState = rememberLazyGridState(
        prefs.getInt("${albumScrollKey}_index", 0).coerceAtLeast(0),
        prefs.getInt("${albumScrollKey}_offset", 0).coerceAtLeast(0)
    )
    LaunchedEffect(albumGridState, albumScrollKey) {
        snapshotFlow { albumGridState.firstVisibleItemIndex to albumGridState.firstVisibleItemScrollOffset }
            .distinctUntilChanged()
            .collect { (index, offset) -> prefs.edit().putInt("${albumScrollKey}_index", index).putInt("${albumScrollKey}_offset", offset).apply() }
    }

    val bounds = remember { mutableStateMapOf<String, Rect>() }
''',
    'album scroll state'
)
s = replace_once(
    s,
    '        columns = GridCells.Fixed(2),\n        modifier = Modifier.fillMaxSize(),\n',
    '        columns = GridCells.Fixed(2),\n        state = albumGridState,\n        modifier = Modifier.fillMaxSize(),\n',
    'album grid state applied'
)

# Replace drag/drop with overlap-tolerant grouping. This is intentionally much
# more forgiving than the v0.5 center-only target.
new_drop = '''    fun finishDrop(sourceToken: String, offset: Offset) {
        val sourceBounds = bounds[sourceToken] ?: return
        val movedCenter = sourceBounds.center + offset
        val candidates = bounds.entries.filter { it.key != sourceToken }
        if (candidates.isEmpty()) return
        val targetEntry = candidates.minByOrNull { (_, rect) ->
            val dx = movedCenter.x - rect.center.x
            val dy = movedCenter.y - rect.center.y
            dx * dx + dy * dy
        } ?: return
        val targetToken = targetEntry.key
        val targetBounds = targetEntry.value
        val closeEnough = abs(movedCenter.x - targetBounds.center.x) < (sourceBounds.width + targetBounds.width) * 0.48f &&
            abs(movedCenter.y - targetBounds.center.y) < (sourceBounds.height + targetBounds.height) * 0.48f

        if (groupId != null) {
            if (!closeEnough) return
            val sourceRoot = sourceToken.removePrefix("a:")
            val targetRoot = targetToken.removePrefix("a:")
            AlbumOrganizer.reorderInsideGroup(prefs, layout, groupId, sourceRoot, targetRoot)
            controller.log(null, EventTypes.ALBUM_REORDER, details = "collection=$groupId;$sourceRoot->$targetRoot")
            onLayoutChanged()
            return
        }

        val sourceIsAlbum = sourceToken.startsWith("a:")
        val targetIsAlbum = targetToken.startsWith("a:")
        val targetIsCollection = targetToken.startsWith("g:")

        when {
            closeEnough && sourceIsAlbum && targetIsAlbum -> {
                val sourceRoot = sourceToken.removePrefix("a:")
                val targetRoot = targetToken.removePrefix("a:")
                val id = AlbumOrganizer.createGroup(prefs, layout, sourceRoot, targetRoot)
                if (id.isNotBlank()) controller.log(null, EventTypes.ALBUM_GROUP_CREATE, details = "$sourceRoot+$targetRoot->$id")
            }
            closeEnough && sourceIsAlbum && targetIsCollection -> {
                AlbumOrganizer.addToGroup(prefs, layout, sourceToken.removePrefix("a:"), targetToken.removePrefix("g:"))
                controller.log(null, EventTypes.ALBUM_GROUP_CREATE, details = "${sourceToken.removePrefix("a:")} -> ${targetToken.removePrefix("g:")}")
            }
            else -> {
                val distanceLimit = kotlin.math.hypot(targetBounds.width, targetBounds.height) * 1.15f
                val distance = kotlin.math.hypot(movedCenter.x - targetBounds.center.x, movedCenter.y - targetBounds.center.y)
                if (distance > distanceLimit) return
                val before = movedCenter.y < targetBounds.center.y || (abs(movedCenter.y - targetBounds.center.y) < targetBounds.height * 0.35f && movedCenter.x < targetBounds.center.x)
                AlbumOrganizer.reorderTop(prefs, layout, sourceToken, targetToken, before)
                controller.log(null, EventTypes.ALBUM_REORDER, details = "$sourceToken->$targetToken;before=$before")
            }
        }
        onLayoutChanged()
    }

'''
s = replace_between(s, '    fun finishDrop(sourceToken: String, offset: Offset) {', '    LazyVerticalGrid(', new_drop, 'collection drag/drop')

# Collection terminology in the UI.
s = s.replace('Name this album group', 'Name this collection')
s = s.replace('Rename group', 'Rename collection')
s = s.replace('Ungroup', 'Dissolve collection')
s = s.replace('Remove from group', 'Remove from collection')
gallery.write_text(s)

# v0.5's runtime organizer patch has already run before this script.
organizer = ROOT / "app/src/main/java/com/neurontap/app/AlbumOrganizer.kt"
s = organizer.read_text()
s = s.replace('"Group ${state.groups.size + 1}"', '"Collection ${state.groups.size + 1}"')
s = s.replace('ifBlank { "Group" }', 'ifBlank { "Collection" }')
organizer.write_text(s)

# -------------------------------------------------------------------------
# Horny Archives: one in-app back arrow, exact return position, actionable
# interpretations, and clearer "album" terminology for generated galleries.
# -------------------------------------------------------------------------
analytics = ROOT / "app/src/main/java/com/neurontap/app/AnalyticsUi.kt"
s = analytics.read_text()
s = replace_once(s, 'import androidx.activity.compose.rememberLauncherForActivityResult\n', 'import androidx.activity.compose.BackHandler\nimport androidx.activity.compose.rememberLauncherForActivityResult\n', 'analytics BackHandler import')
s = replace_once(s, 'import androidx.compose.foundation.lazy.LazyColumn\n', 'import androidx.compose.foundation.lazy.LazyColumn\nimport androidx.compose.foundation.lazy.rememberLazyListState\n', 'archive list state import')
s = replace_once(s, 'fun WrappedContent(controller: AppController) {', 'fun WrappedContent(controller: AppController, onExit: () -> Unit) {', 'WrappedContent exit callback')
s = replace_once(
    s,
    '    var viewerItems by remember { mutableStateOf<List<MediaItem>>(emptyList()) }\n',
    '    var viewerItems by remember { mutableStateOf<List<MediaItem>>(emptyList()) }\n    val archiveListState = rememberLazyListState()\n',
    'archive list state'
)
s = replace_once(
    s,
    '    fun openMedia(mediaId: Long, ids: List<Long>) {\n',
    '    BackHandler(enabled = activeGallery != null && viewerStartId == null) { activeGallery = null }\n    BackHandler(enabled = activeGallery == null && viewerStartId == null) { onExit() }\n\n    fun openMedia(mediaId: Long, ids: List<Long>) {\n',
    'archive back behavior'
)
s = replace_once(
    s,
    '    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 14.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {\n',
    '    LazyColumn(state = archiveListState, modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {\n',
    'archive list state applied'
)
s = replace_once(
    s,
    '            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {\n                Text("Horny Archives", style = MaterialTheme.typography.headlineMedium)\n                Row {\n',
    '            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {\n                Row(verticalAlignment = Alignment.CenterVertically) {\n                    IconButton(onClick = onExit) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }\n                    Text("Horny Archives", style = MaterialTheme.typography.headlineMedium)\n                }\n                Row {\n',
    'archive single back arrow'
)
old_insights = '''        if (stats.insights.isNotEmpty()) {
            item { Text("Interpretations", style = MaterialTheme.typography.titleLarge) }
            items(stats.insights) { insight ->
                Surface(color = Color(0xFF141414), shape = MaterialTheme.shapes.medium) {
                    Text(insight, Modifier.padding(12.dp), style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
'''
new_insights = '''        if (stats.insights.isNotEmpty()) {
            item { Text("Interpretations", style = MaterialTheme.typography.titleLarge) }
            items(stats.insights) { insight ->
                val action: (() -> Unit)? = when {
                    insight.mediaId != null -> ({ openMedia(insight.mediaId, stats.summaries.map { it.mediaId }) })
                    insight.galleryId != null -> stats.smartGalleries.firstOrNull { it.id == insight.galleryId }?.let { gallery -> ({ activeGallery = gallery }) }
                    else -> null
                }
                Card(onClick = { action?.invoke() }, enabled = action != null, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(insight.title, style = MaterialTheme.typography.titleMedium)
                        Text(insight.body, style = MaterialTheme.typography.bodyMedium)
                        if (action != null) Text("Tap to inspect", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                    }
                }
            }
        }
'''
s = replace_once(s, old_insights, new_insights, 'actionable insights')
s = s.replace('Text("Live archive galleries", style = MaterialTheme.typography.titleLarge)', 'Text("Live archive albums", style = MaterialTheme.typography.titleLarge)')
s = s.replace('Text("Generated from the selected time period. These do not alter your normal gallery."', 'Text("Generated from the selected time period. These are live statistical albums and do not alter your normal Gallery."')
analytics.write_text(s)

print("Applied NeuronTap v0.6 core patch")
