package com.neurontap.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Label
import androidx.compose.material.icons.filled.PhotoLibrary
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.SaveAlt
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.media3.common.MediaItem as ExoMediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.compose.ui.viewinterop.AndroidView
import coil.compose.AsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

class MainActivity : ComponentActivity() {
    private lateinit var controller: AppController

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        controller = AppController(this, NeuronDb(this))
        setContent { MaterialTheme { NeuronTapApp(controller) } }
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

private enum class Tab { Gallery, Wrapped, Tags }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun NeuronTapApp(controller: AppController) {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("neurontap", 0) }
    val scope = rememberCoroutineScope()
    var tab by remember { mutableStateOf(Tab.Gallery) }
    var rootUriString by remember { mutableStateOf(prefs.getString("root_uri", null)) }
    var media by remember { mutableStateOf<List<MediaItem>>(emptyList()) }
    var status by remember { mutableStateOf<String?>(null) }
    var showFinishDialog by remember { mutableStateOf(false) }
    var finishResult by remember { mutableStateOf<String?>(null) }

    suspend fun reloadMedia() {
        val root = rootUriString ?: return
        media = withContext(Dispatchers.IO) { controller.db.loadMedia(root) }
    }

    LaunchedEffect(rootUriString) { reloadMedia() }

    val folderPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            runCatching { context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
            rootUriString = uri.toString()
            prefs.edit().putString("root_uri", uri.toString()).apply()
            status = "Indexing…"
            scope.launch {
                val count = MediaIndexer.index(context, controller.db, uri)
                reloadMedia()
                status = "$count media items indexed"
            }
        }
    }

    if (showFinishDialog) {
        AlertDialog(
            onDismissRequest = { showFinishDialog = false },
            title = { Text("Log a finish?") },
            text = { Text("This becomes ground truth for the current session. The likely media and active window are still estimates.") },
            confirmButton = {
                TextButton(onClick = {
                    showFinishDialog = false
                    scope.launch {
                        val (inference, item) = withContext(Dispatchers.IO) { controller.confirmFinish() }
                        finishResult = if (item != null) {
                            "Likely: ${item.name} · ${(inference.confidence * 100).toInt()}% confidence"
                        } else {
                            "Finish logged. Not enough signals to pick a likely item yet."
                        }
                    }
                }) { Text("Yep") }
            },
            dismissButton = { TextButton(onClick = { showFinishDialog = false }) { Text("Cancel") } }
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("NeuronTap") },
                actions = {
                    if (tab == Tab.Gallery) {
                        IconButton(onClick = { folderPicker.launch(null) }) { Icon(Icons.Default.FolderOpen, contentDescription = "Choose gallery folder") }
                        IconButton(onClick = { showFinishDialog = true }) { Icon(Icons.Default.CheckCircle, contentDescription = "Log a finish") }
                    }
                }
            )
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(selected = tab == Tab.Gallery, onClick = { tab = Tab.Gallery }, icon = { Icon(Icons.Default.PhotoLibrary, null) }, label = { Text("Gallery") })
                NavigationBarItem(selected = tab == Tab.Wrapped, onClick = { tab = Tab.Wrapped }, icon = { Icon(Icons.Default.BarChart, null) }, label = { Text("Wrapped") })
                NavigationBarItem(selected = tab == Tab.Tags, onClick = { tab = Tab.Tags }, icon = { Icon(Icons.Default.Label, null) }, label = { Text("Tag Lab") })
            }
        }
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            when (tab) {
                Tab.Gallery -> GalleryScreen(controller, media, rootUriString != null, status, finishResult) { folderPicker.launch(null) }
                Tab.Wrapped -> WrappedScreen(controller.db)
                Tab.Tags -> TagLabScreen(controller.db)
            }
        }
    }
}

@Composable
private fun GalleryScreen(controller: AppController, media: List<MediaItem>, rootChosen: Boolean, status: String?, finishResult: String?, onPickFolder: () -> Unit) {
    if (media.isEmpty()) {
        Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
            Text(if (rootChosen) "No indexed media yet." else "Choose a gallery folder to begin.")
            Spacer(Modifier.height(16.dp))
            Button(onClick = onPickFolder) { Icon(Icons.Default.FolderOpen, null); Spacer(Modifier.width(8.dp)); Text("Choose folder") }
            status?.let { Spacer(Modifier.height(12.dp)); Text(it) }
        }
        return
    }

    val pagerState = rememberPagerState(pageCount = { media.size })
    var trackedPage by remember(media) { mutableIntStateOf(-1) }
    var trackedStartMs by remember(media) { mutableLongStateOf(0L) }
    var videoPositionMs by remember { mutableStateOf<Long?>(null) }

    LaunchedEffect(pagerState.currentPage, media) {
        val now = System.currentTimeMillis()
        if (trackedPage in media.indices && trackedStartMs > 0) controller.log(media[trackedPage].id, EventTypes.VIEW_DWELL, value = now - trackedStartMs, at = now)
        trackedPage = pagerState.currentPage
        trackedStartMs = now
        controller.log(media[trackedPage].id, EventTypes.VIEW_START, at = now)
        videoPositionMs = null
    }

    DisposableEffect(media) {
        onDispose {
            val now = System.currentTimeMillis()
            if (trackedPage in media.indices && trackedStartMs > 0) controller.log(media[trackedPage].id, EventTypes.VIEW_DWELL, value = now - trackedStartMs, at = now)
        }
    }

    Box(Modifier.fillMaxSize()) {
        HorizontalPager(state = pagerState, modifier = Modifier.fillMaxSize()) { page ->
            val item = media[page]
            MediaPane(item, controller) { pos -> if (page == pagerState.currentPage) videoPositionMs = pos }
        }

        Column(Modifier.align(Alignment.TopCenter).padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Surface(shape = RoundedCornerShape(14.dp), tonalElevation = 4.dp) {
                Text("${pagerState.currentPage + 1}/${media.size} · ${media[pagerState.currentPage].name}", Modifier.padding(horizontal = 12.dp, vertical = 6.dp), maxLines = 1)
            }
            status?.let { Text(it, Modifier.padding(top = 4.dp)) }
            finishResult?.let { Text(it, Modifier.padding(top = 4.dp)) }
        }

        ReactionButton(Modifier.align(Alignment.BottomCenter).padding(bottom = 24.dp), controller, media[pagerState.currentPage], trackedStartMs, videoPositionMs)
    }
}

@Composable
private fun MediaPane(item: MediaItem, controller: AppController, onVideoPosition: (Long?) -> Unit) {
    if (item.isVideo) VideoPane(item, controller, onVideoPosition)
    else {
        LaunchedEffect(item.id) { onVideoPosition(null) }
        Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surfaceVariant)) {
            AsyncImage(model = Uri.parse(item.uri), contentDescription = item.name, modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Fit)
        }
    }
}

@Composable
private fun VideoPane(item: MediaItem, controller: AppController, onVideoPosition: (Long?) -> Unit) {
    val context = LocalContext.current
    val player = remember(item.uri) { ExoPlayer.Builder(context).build().apply { setMediaItem(ExoMediaItem.fromUri(Uri.parse(item.uri))); prepare() } }

    DisposableEffect(player, item.id) {
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                controller.log(item.id, if (isPlaying) EventTypes.VIDEO_PLAY else EventTypes.VIDEO_PAUSE, mediaPositionMs = player.currentPosition)
            }
            override fun onPositionDiscontinuity(oldPosition: Player.PositionInfo, newPosition: Player.PositionInfo, reason: Int) {
                if (reason == Player.DISCONTINUITY_REASON_SEEK) controller.log(item.id, EventTypes.VIDEO_SEEK, value = newPosition.positionMs - oldPosition.positionMs, mediaPositionMs = newPosition.positionMs)
            }
        }
        player.addListener(listener)
        onDispose { player.removeListener(listener); player.release() }
    }

    LaunchedEffect(player) { while (true) { onVideoPosition(player.currentPosition); delay(250) } }
    AndroidView(factory = { ctx -> PlayerView(ctx).apply { this.player = player } }, update = { it.player = player }, modifier = Modifier.fillMaxSize())
}

@Composable
private fun ReactionButton(modifier: Modifier, controller: AppController, item: MediaItem, viewStartMs: Long, videoPositionMs: Long?) {
    var firstReactionLogged by remember(item.id, viewStartMs) { mutableStateOf(false) }
    Box(
        modifier.size(96.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primary).pointerInput(item.id, viewStartMs, videoPositionMs) {
            detectTapGestures(onPress = {
                val down = System.currentTimeMillis()
                controller.log(item.id, EventTypes.REACTION_DOWN, mediaPositionMs = videoPositionMs, at = down)
                if (!firstReactionLogged && viewStartMs > 0L) {
                    firstReactionLogged = true
                    controller.log(item.id, EventTypes.FIRST_TAP_LATENCY, value = down - viewStartMs, mediaPositionMs = videoPositionMs, at = down)
                }
                tryAwaitRelease()
                val up = System.currentTimeMillis()
                controller.log(item.id, EventTypes.REACTION_UP, value = up - down, mediaPositionMs = videoPositionMs, at = up)
            })
        },
        contentAlignment = Alignment.Center
    ) { Icon(Icons.Default.Bolt, contentDescription = "Reaction", tint = MaterialTheme.colorScheme.onPrimary, modifier = Modifier.size(46.dp)) }
}

@Composable
private fun WrappedScreen(db: NeuronDb) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var stats by remember { mutableStateOf(WrappedStats()) }
    var csvToWrite by remember { mutableStateOf<String?>(null) }
    suspend fun refresh() { stats = withContext(Dispatchers.IO) { db.wrappedStats() } }
    LaunchedEffect(Unit) { refresh() }

    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri ->
        val csv = csvToWrite
        if (uri != null && csv != null) context.contentResolver.openOutputStream(uri)?.bufferedWriter()?.use { it.write(csv) }
        csvToWrite = null
    }

    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Wrapped", style = MaterialTheme.typography.headlineMedium)
                Row {
                    IconButton(onClick = { scope.launch { refresh() } }) { Icon(Icons.Default.Refresh, "Refresh") }
                    IconButton(onClick = { scope.launch { csvToWrite = withContext(Dispatchers.IO) { db.exportCsv() }; exportLauncher.launch("neurontap-events.csv") } }) { Icon(Icons.Default.SaveAlt, "Export metadata CSV") }
                }
            }
        }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatCard("Taps", stats.taps.toString(), Modifier.weight(1f)); StatCard("Sessions", stats.sessions.toString(), Modifier.weight(1f)); StatCard("Finishes", stats.finishes.toString(), Modifier.weight(1f))
            }
        }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatCard("Fastest tap", stats.quickestFirstTapMs?.let(::formatMs) ?: "—", Modifier.weight(1f)); StatCard("Longest stare", stats.longestDwellMs?.let(::formatMs) ?: "—", Modifier.weight(1f)); StatCard("Active hour", stats.mostActiveHour?.let(::formatHour) ?: "—", Modifier.weight(1f))
            }
        }
        item { Text("Top behavioral hits", style = MaterialTheme.typography.titleLarge) }
        items(stats.topMedia) { score ->
            Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(14.dp)) {
                Text(score.name, style = MaterialTheme.typography.titleMedium, maxLines = 1)
                Text("${score.taps} taps · ${formatMs(score.dwellMs)} dwell · ${score.sessionCount} sessions · ${score.finishCount} inferred finishes")
                Text("Reaction score ${String.format(Locale.US, "%.1f", score.score)}")
            } }
        }
    }
}

@Composable
private fun StatCard(label: String, value: String, modifier: Modifier = Modifier) {
    Card(modifier) { Column(Modifier.padding(12.dp)) { Text(value, style = MaterialTheme.typography.titleLarge); Text(label, style = MaterialTheme.typography.bodySmall) } }
}

@Composable
private fun TagLabScreen(db: NeuronDb) {
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
            text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { Text(if (tags.isEmpty()) "No tags yet." else "Tags: ${tags.joinToString()}"); TextField(value = tagText, onValueChange = { tagText = it }, label = { Text("Add a tag") }) } },
            confirmButton = { TextButton(onClick = { if (tagText.isNotBlank()) { db.addTag(score.mediaId, tagText); tags = db.tagsForMedia(score.mediaId); tagText = "" } }) { Text("Add") } },
            dismissButton = { TextButton(onClick = { selected = null }) { Text("Done") } }
        )
    }

    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Text("Tag Lab", style = MaterialTheme.typography.headlineMedium); Text("Only label the interesting stuff after the fact. Raw reactions stay raw.") }
        items(top) { score ->
            Card(Modifier.fillMaxWidth()) { Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                Column(Modifier.weight(1f)) { Text(score.name, maxLines = 1); Text("${score.taps} taps · score ${String.format(Locale.US, "%.1f", score.score)}") }
                FilledTonalButton(onClick = { selected = score; tags = db.tagsForMedia(score.mediaId) }) { Text("Tag") }
            } }
        }
    }
}

private fun formatMs(ms: Long): String {
    if (ms < 1000) return "${ms}ms"
    val totalSeconds = ms / 1000
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return if (minutes > 0) "${minutes}m ${seconds}s" else "${seconds}s"
}

private fun formatHour(hour: Int): String {
    val suffix = if (hour < 12) "AM" else "PM"
    val h = when (val x = hour % 12) { 0 -> 12; else -> x }
    return "$h $suffix"
}
