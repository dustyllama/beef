package com.neurontap.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Collections
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Label
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.PhotoLibrary
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import coil.compose.AsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private enum class CollectionMode { ALL, VIDEOS, FAVORITES, ALBUMS }
private enum class SortMode { NEWEST, OLDEST, NAME }

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun CollectionScreen(controller: AppController, onOpenWrapped: () -> Unit, onOpenTags: () -> Unit) {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("neurontap", 0) }
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }

    val initialRoots = remember {
        val roots = prefs.getStringSet("linked_roots", emptySet())?.toMutableSet() ?: mutableSetOf()
        prefs.getString("root_uri", null)?.let { roots.add(it) }
        roots.toSet()
    }
    var linkedRoots by remember { mutableStateOf(initialRoots) }
    var media by remember { mutableStateOf<List<MediaItem>>(emptyList()) }
    var mode by remember { mutableStateOf(CollectionMode.ALL) }
    var sortMode by remember { mutableStateOf(SortMode.NEWEST) }
    var albumRoot by remember { mutableStateOf<String?>(null) }
    var searchVisible by remember { mutableStateOf(false) }
    var searchText by remember { mutableStateOf("") }
    var gridColumns by remember { mutableIntStateOf(prefs.getInt("grid_columns", 4).coerceIn(2, 8)) }
    var menuOpen by remember { mutableStateOf(false) }
    var viewerStartId by remember { mutableStateOf<Long?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var showFinishDialog by remember { mutableStateOf(false) }
    var showFoldersDialog by remember { mutableStateOf(false) }

    val mediaPermissions = remember {
        if (Build.VERSION.SDK_INT >= 33) arrayOf(Manifest.permission.READ_MEDIA_IMAGES, Manifest.permission.READ_MEDIA_VIDEO)
        else arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE)
    }

    fun hasAnyMediaPermission(): Boolean = mediaPermissions.any {
        ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED
    }

    suspend fun reload() {
        val raw = withContext(Dispatchers.IO) { controller.db.loadAllMedia() }
        media = raw.groupBy { "${it.name}|${it.size}|${it.modified / 1000L}" }
            .values
            .map { group -> group.firstOrNull { !it.rootUri.startsWith("mediastore:") } ?: group.first() }
            .sortedWith(compareByDescending<MediaItem> { it.modified }.thenBy { it.name.lowercase() })
    }

    suspend fun scanDevice() {
        if (!hasAnyMediaPermission()) return
        message = "Refreshing device library…"
        val count = withContext(Dispatchers.IO) { MediaStoreIndexer.index(context, controller.db) }
        prefs.edit().putLong("last_device_scan", System.currentTimeMillis()).apply()
        reload()
        message = "$count device media items indexed"
    }

    suspend fun rescanEverything() {
        scanDevice()
        var extra = 0
        linkedRoots.forEach { root ->
            extra += withContext(Dispatchers.IO) { MediaIndexer.index(context, controller.db, Uri.parse(root)) }
        }
        reload()
        if (extra > 0) message = "Library refreshed · $extra linked-folder items checked"
    }

    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        if (result.values.any { it }) scope.launch { scanDevice() }
        else message = "Device-library access was not granted. Linked folders still work."
    }

    val folderPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            runCatching {
                context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            }.recoverCatching {
                context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            linkedRoots = linkedRoots + uri.toString()
            prefs.edit().putStringSet("linked_roots", linkedRoots).apply()
            scope.launch {
                message = "Indexing linked folder…"
                val count = withContext(Dispatchers.IO) { MediaIndexer.index(context, controller.db, uri) }
                reload()
                message = "$count items linked"
            }
        }
    }

    LaunchedEffect(Unit) {
        prefs.edit().putStringSet("linked_roots", linkedRoots).apply()
        reload()
        if (!hasAnyMediaPermission()) {
            permissionLauncher.launch(mediaPermissions)
        } else {
            val last = prefs.getLong("last_device_scan", 0L)
            if (System.currentTimeMillis() - last > 10 * 60 * 1000L) scanDevice()
        }
    }

    LaunchedEffect(message) {
        message?.let {
            snackbar.showSnackbar(it)
            message = null
        }
    }

    if (showFinishDialog) {
        AlertDialog(
            onDismissRequest = { showFinishDialog = false },
            title = { Text("Log a finish?") },
            text = { Text("This marks the current session as confirmed; the likely media and active window remain inferred.") },
            confirmButton = {
                TextButton(onClick = {
                    showFinishDialog = false
                    scope.launch {
                        val (inference, item) = withContext(Dispatchers.IO) { controller.confirmFinish() }
                        message = item?.let { "Likely ${it.name} · ${(inference.confidence * 100).toInt()}% confidence" }
                            ?: "Finish logged"
                    }
                }) { Text("Yep") }
            },
            dismissButton = { TextButton(onClick = { showFinishDialog = false }) { Text("Cancel") } }
        )
    }

    if (showFoldersDialog) {
        AlertDialog(
            onDismissRequest = { showFoldersDialog = false },
            title = { Text("Linked folders") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Device media is indexed through Android's media library. These are extra folders you linked manually.")
                    if (linkedRoots.isEmpty()) Text("No extra folders linked.")
                    linkedRoots.sorted().forEach { root ->
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(albumLabel(root), Modifier.weight(1f), maxLines = 1)
                            TextButton(onClick = {
                                linkedRoots = linkedRoots - root
                                prefs.edit().putStringSet("linked_roots", linkedRoots).apply()
                                controller.db.deleteRoot(root)
                                scope.launch { reload() }
                            }) { Text("Remove") }
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showFoldersDialog = false; folderPicker.launch(null) }) { Text("Add folder") } },
            dismissButton = { TextButton(onClick = { showFoldersDialog = false }) { Text("Done") } }
        )
    }

    val baseList = remember(media, mode, albumRoot) {
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

    viewerStartId?.let { startId ->
        ViewerScreen(
            controller = controller,
            items = visibleMedia,
            startMediaId = startId,
            onClose = { viewerStartId = null; scope.launch { reload() } },
            onLibraryChanged = { scope.launch { reload() } }
        )
        return
    }

    Scaffold(
        containerColor = Color.Black,
        snackbarHost = { SnackbarHost(snackbar) },
        topBar = {
            Column(Modifier.background(Color.Black)) {
                TopAppBar(
                    title = { Text(albumRoot?.let(::albumLabel) ?: "COLLECTION") },
                    navigationIcon = {
                        if (albumRoot != null) {
                            IconButton(onClick = { albumRoot = null }) {
                                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                            }
                        }
                    },
                    actions = {
                        IconButton(onClick = { searchVisible = !searchVisible }) { Icon(Icons.Default.Search, contentDescription = "Search") }
                        IconButton(onClick = { folderPicker.launch(null) }) { Icon(Icons.Default.FolderOpen, contentDescription = "Add folder") }
                        Box {
                            IconButton(onClick = { menuOpen = true }) { Icon(Icons.Default.MoreVert, contentDescription = "More") }
                            DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                                DropdownMenuItem(text = { Text("Refresh library") }, leadingIcon = { Icon(Icons.Default.Refresh, null) }, onClick = { menuOpen = false; scope.launch { rescanEverything() } })
                                DropdownMenuItem(text = { Text("Linked folders") }, leadingIcon = { Icon(Icons.Default.FolderOpen, null) }, onClick = { menuOpen = false; showFoldersDialog = true })
                                DropdownMenuItem(text = { Text("Wrapped") }, leadingIcon = { Icon(Icons.Default.BarChart, null) }, onClick = { menuOpen = false; onOpenWrapped() })
                                DropdownMenuItem(text = { Text("Tag Lab") }, leadingIcon = { Icon(Icons.Default.Label, null) }, onClick = { menuOpen = false; onOpenTags() })
                                DropdownMenuItem(text = { Text("Log a finish") }, leadingIcon = { Icon(Icons.Default.CheckCircle, null) }, onClick = { menuOpen = false; showFinishDialog = true })
                                DropdownMenuItem(text = { Text("Sort: newest first") }, onClick = { sortMode = SortMode.NEWEST; menuOpen = false })
                                DropdownMenuItem(text = { Text("Sort: oldest first") }, onClick = { sortMode = SortMode.OLDEST; menuOpen = false })
                                DropdownMenuItem(text = { Text("Sort: name") }, onClick = { sortMode = SortMode.NAME; menuOpen = false })
                                if (!hasAnyMediaPermission()) {
                                    DropdownMenuItem(text = { Text("Grant device-library access") }, onClick = { menuOpen = false; permissionLauncher.launch(mediaPermissions) })
                                }
                            }
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Black)
                )
                if (searchVisible) {
                    OutlinedTextField(
                        value = searchText,
                        onValueChange = { searchText = it },
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                        singleLine = true,
                        placeholder = { Text("Search filenames") }
                    )
                }
            }
        },
        bottomBar = {
            NavigationBar(containerColor = Color(0xFF101010)) {
                NavigationBarItem(selected = mode == CollectionMode.ALL && albumRoot == null, onClick = { mode = CollectionMode.ALL; albumRoot = null }, icon = { Icon(Icons.Default.PhotoLibrary, "All") })
                NavigationBarItem(selected = mode == CollectionMode.VIDEOS && albumRoot == null, onClick = { mode = CollectionMode.VIDEOS; albumRoot = null }, icon = { Icon(Icons.Default.Movie, "Videos") })
                NavigationBarItem(selected = mode == CollectionMode.FAVORITES && albumRoot == null, onClick = { mode = CollectionMode.FAVORITES; albumRoot = null }, icon = { Icon(Icons.Default.Favorite, "Favorites") })
                NavigationBarItem(selected = mode == CollectionMode.ALBUMS || albumRoot != null, onClick = { mode = CollectionMode.ALBUMS; albumRoot = null }, icon = { Icon(Icons.Default.Collections, "Albums") })
            }
        }
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding).background(Color.Black)) {
            if (mode == CollectionMode.ALBUMS && albumRoot == null) {
                AlbumGrid(media = media, onOpenAlbum = { albumRoot = it })
            } else {
                MediaGrid(
                    media = visibleMedia,
                    columns = gridColumns,
                    onColumnsChanged = {
                        gridColumns = it.coerceIn(2, 8)
                        prefs.edit().putInt("grid_columns", gridColumns).apply()
                    },
                    onOpen = { viewerStartId = it.id },
                    onToggleFavorite = { item ->
                        val next = !item.favorite
                        controller.db.setFavorite(item.id, next)
                        media = media.map { if (it.id == item.id) it.copy(favorite = next) else it }
                    }
                )
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun MediaGrid(media: List<MediaItem>, columns: Int, onColumnsChanged: (Int) -> Unit, onOpen: (MediaItem) -> Unit, onToggleFavorite: (MediaItem) -> Unit) {
    if (media.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Nothing here yet") }
        return
    }
    var currentColumns by remember(columns) { mutableIntStateOf(columns) }
    LaunchedEffect(columns) { currentColumns = columns }

    val pinchModifier = Modifier.pointerInput(Unit) {
        awaitEachGesture {
            awaitFirstDown(requireUnconsumed = false)
            var lastDistance: Float? = null
            var accumulated = 1f
            while (true) {
                val event = awaitPointerEvent()
                val pressed = event.changes.filter { it.pressed }
                if (pressed.isEmpty()) break
                if (pressed.size >= 2) {
                    val distance = (pressed[0].position - pressed[1].position).getDistance().coerceAtLeast(1f)
                    lastDistance?.let { previous ->
                        accumulated *= distance / previous
                        if (accumulated > 1.18f && currentColumns > 2) {
                            currentColumns -= 1
                            onColumnsChanged(currentColumns)
                            accumulated = 1f
                        } else if (accumulated < 0.84f && currentColumns < 8) {
                            currentColumns += 1
                            onColumnsChanged(currentColumns)
                            accumulated = 1f
                        }
                    }
                    lastDistance = distance
                    pressed.forEach { it.consume() }
                } else {
                    lastDistance = null
                }
            }
        }
    }

    LazyVerticalGrid(
        columns = GridCells.Fixed(currentColumns),
        modifier = Modifier.fillMaxSize().then(pinchModifier),
        horizontalArrangement = Arrangement.spacedBy(2.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        items(media, key = { it.id }) { item ->
            Box(
                Modifier.aspectRatio(1f).combinedClickable(
                    onClick = { onOpen(item) },
                    onLongClick = { onToggleFavorite(item) }
                )
            ) {
                AsyncImage(model = Uri.parse(item.uri), contentDescription = item.name, modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                if (item.isVideo) {
                    Icon(Icons.Default.Movie, contentDescription = null, modifier = Modifier.align(Alignment.BottomStart).padding(6.dp).size(22.dp), tint = Color.White)
                }
                if (item.favorite) {
                    Icon(Icons.Default.Favorite, contentDescription = null, modifier = Modifier.align(Alignment.TopEnd).padding(5.dp).size(20.dp), tint = Color(0xFFFF4D67))
                }
            }
        }
    }
}

@Composable
private fun AlbumGrid(media: List<MediaItem>, onOpenAlbum: (String) -> Unit) {
    val albums = remember(media) { media.groupBy { it.rootUri }.entries.sortedBy { albumLabel(it.key).lowercase() } }
    if (albums.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("No albums yet") }
        return
    }
    LazyVerticalGrid(columns = GridCells.Fixed(2), modifier = Modifier.fillMaxSize(), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        items(albums, key = { it.key }) { entry ->
            Card(
                onClick = { onOpenAlbum(entry.key) },
                colors = CardDefaults.cardColors(containerColor = Color(0xFF141414)),
                shape = RoundedCornerShape(8.dp)
            ) {
                Column {
                    val cover = entry.value.maxByOrNull { it.modified }
                    if (cover != null) {
                        AsyncImage(model = Uri.parse(cover.uri), contentDescription = albumLabel(entry.key), modifier = Modifier.fillMaxWidth().aspectRatio(1.25f), contentScale = ContentScale.Crop)
                    }
                    Column(Modifier.padding(10.dp)) {
                        Text(albumLabel(entry.key), maxLines = 1)
                        Text("${entry.value.size} items", color = Color.Gray)
                    }
                }
            }
        }
    }
}

fun albumLabel(root: String): String {
    if (root.startsWith("mediastore:")) {
        return root.removePrefix("mediastore:").trim('/').substringAfterLast('/').ifBlank { "Device" }
    }
    return runCatching {
        Uri.decode(Uri.parse(root).lastPathSegment.orEmpty()).substringAfterLast(':').substringAfterLast('/').ifBlank { "Folder" }
    }.getOrDefault("Folder")
}
