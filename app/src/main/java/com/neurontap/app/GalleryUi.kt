package com.neurontap.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
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
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.abs

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
        prefs.getString("root_uri", null)?.let(roots::add)
        roots.toSet()
    }

    var linkedRoots by remember { mutableStateOf(initialRoots) }
    var media by remember { mutableStateOf<List<MediaItem>>(emptyList()) }
    var mode by remember { mutableStateOf(CollectionMode.ALL) }
    var sortMode by remember { mutableStateOf(SortMode.NEWEST) }
    var albumRoot by remember { mutableStateOf<String?>(null) }
    var albumGroupId by remember { mutableStateOf<String?>(null) }
    var searchVisible by remember { mutableStateOf(false) }
    var searchText by remember { mutableStateOf("") }
    var gridColumns by remember { mutableIntStateOf(prefs.getInt("grid_columns", 4).coerceIn(2, 8)) }
    var menuOpen by remember { mutableStateOf(false) }
    var viewerStartId by remember { mutableStateOf<Long?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var showFinishDialog by remember { mutableStateOf(false) }
    var showFoldersDialog by remember { mutableStateOf(false) }
    var albumLayout by remember { mutableStateOf(AlbumLayoutState()) }

    val mediaPermissions = remember {
        if (Build.VERSION.SDK_INT >= 33) arrayOf(Manifest.permission.READ_MEDIA_IMAGES, Manifest.permission.READ_MEDIA_VIDEO)
        else arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE)
    }

    fun hasAnyMediaPermission(): Boolean = mediaPermissions.any {
        ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED
    }

    fun refreshAlbumLayout() {
        albumLayout = AlbumOrganizer.load(prefs, media.map { it.rootUri }.toSet())
    }

    suspend fun reload() {
        val raw = withContext(Dispatchers.IO) { controller.db.loadAllMedia() }
        media = raw.groupBy { "${it.name}|${it.size}|${it.modified / 1000L}" }
            .values
            .map { group -> group.firstOrNull { !it.rootUri.startsWith("mediastore:") } ?: group.first() }
            .sortedWith(compareByDescending<MediaItem> { it.modified }.thenBy { it.name.lowercase() })
        albumLayout = AlbumOrganizer.load(prefs, media.map { it.rootUri }.toSet())
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
        linkedRoots.forEach { root -> extra += withContext(Dispatchers.IO) { MediaIndexer.index(context, controller.db, Uri.parse(root)) } }
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
        controller.log(null, EventTypes.GALLERY_OPEN)
        prefs.edit().putStringSet("linked_roots", linkedRoots).apply()
        reload()
        if (!hasAnyMediaPermission()) permissionLauncher.launch(mediaPermissions)
        else if (System.currentTimeMillis() - prefs.getLong("last_device_scan", 0L) > 10 * 60 * 1000L) scanDevice()
    }

    LaunchedEffect(mode, albumRoot, albumGroupId) {
        controller.log(null, EventTypes.GALLERY_MODE, details = "mode=${mode.name};album=${albumRoot ?: ""};group=${albumGroupId ?: ""}")
    }

    LaunchedEffect(message) {
        message?.let { snackbar.showSnackbar(it); message = null }
    }

    if (showFinishDialog) {
        AlertDialog(
            onDismissRequest = { showFinishDialog = false },
            title = { Text("Confirmed nut?") },
            text = { Text("This records ground truth for the current session. If no media is open, the likely media remains inferred separately.") },
            confirmButton = {
                TextButton(onClick = {
                    showFinishDialog = false
                    scope.launch {
                        val (inference, item) = withContext(Dispatchers.IO) { controller.confirmFinish() }
                        message = item?.let { "Confirmed · likely ${it.name} (${(inference.confidence * 100).toInt()}%)" } ?: "Confirmed nut recorded"
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
                    Text("Android's media library is scanned automatically. Add any other accessible folder here.")
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

    BackHandler(enabled = albumRoot != null || albumGroupId != null || mode != CollectionMode.ALL) {
        when {
            albumRoot != null -> {
                controller.log(null, EventTypes.ALBUM_CLOSE, details = albumRoot)
                albumRoot = null
            }
            albumGroupId != null -> albumGroupId = null
            else -> mode = CollectionMode.ALL
        }
    }

    val groupName = albumGroupId?.let { albumLayout.groups[it]?.name }
    val title = albumRoot?.let(::albumLabel) ?: groupName ?: "COLLECTION"

    Scaffold(
        containerColor = Color.Black,
        snackbarHost = { SnackbarHost(snackbar) },
        topBar = {
            Column(Modifier.background(Color.Black)) {
                TopAppBar(
                    title = { Text(title) },
                    navigationIcon = {
                        if (albumRoot != null || albumGroupId != null) {
                            IconButton(onClick = {
                                if (albumRoot != null) {
                                    controller.log(null, EventTypes.ALBUM_CLOSE, details = albumRoot)
                                    albumRoot = null
                                } else albumGroupId = null
                            }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                        }
                    },
                    actions = {
                        if (albumRoot == null && albumGroupId == null && mode != CollectionMode.ALBUMS) {
                            IconButton(onClick = { searchVisible = !searchVisible }) { Icon(Icons.Default.Search, "Search") }
                        }
                        IconButton(onClick = { folderPicker.launch(null) }) { Icon(Icons.Default.FolderOpen, "Add folder") }
                        Box {
                            IconButton(onClick = { menuOpen = true }) { Icon(Icons.Default.MoreVert, "More") }
                            DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                                DropdownMenuItem(text = { Text("Refresh library") }, leadingIcon = { Icon(Icons.Default.Refresh, null) }, onClick = { menuOpen = false; scope.launch { rescanEverything() } })
                                DropdownMenuItem(text = { Text("Linked folders") }, leadingIcon = { Icon(Icons.Default.FolderOpen, null) }, onClick = { menuOpen = false; showFoldersDialog = true })
                                DropdownMenuItem(text = { Text("Horny Archives") }, leadingIcon = { Icon(Icons.Default.BarChart, null) }, onClick = { menuOpen = false; onOpenWrapped() })
                                DropdownMenuItem(text = { Text("Tag Lab") }, leadingIcon = { Icon(Icons.Default.Label, null) }, onClick = { menuOpen = false; onOpenTags() })
                                DropdownMenuItem(text = { Text("Log confirmed nut") }, leadingIcon = { Icon(Icons.Default.CheckCircle, null) }, onClick = { menuOpen = false; showFinishDialog = true })
                                DropdownMenuItem(text = { Text("Sort: newest first") }, onClick = { sortMode = SortMode.NEWEST; menuOpen = false })
                                DropdownMenuItem(text = { Text("Sort: oldest first") }, onClick = { sortMode = SortMode.OLDEST; menuOpen = false })
                                DropdownMenuItem(text = { Text("Sort: name") }, onClick = { sortMode = SortMode.NAME; menuOpen = false })
                                if (!hasAnyMediaPermission()) DropdownMenuItem(text = { Text("Grant device-library access") }, onClick = { menuOpen = false; permissionLauncher.launch(mediaPermissions) })
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
                NavigationBarItem(selected = mode == CollectionMode.ALL && albumRoot == null && albumGroupId == null, onClick = { mode = CollectionMode.ALL; albumRoot = null; albumGroupId = null }, icon = { Icon(Icons.Default.PhotoLibrary, "All") })
                NavigationBarItem(selected = mode == CollectionMode.VIDEOS && albumRoot == null, onClick = { mode = CollectionMode.VIDEOS; albumRoot = null; albumGroupId = null }, icon = { Icon(Icons.Default.Movie, "Videos") })
                NavigationBarItem(selected = mode == CollectionMode.FAVORITES && albumRoot == null, onClick = { mode = CollectionMode.FAVORITES; albumRoot = null; albumGroupId = null }, icon = { Icon(Icons.Default.Favorite, "Favorites") })
                NavigationBarItem(selected = mode == CollectionMode.ALBUMS || albumRoot != null || albumGroupId != null, onClick = { mode = CollectionMode.ALBUMS; albumRoot = null; albumGroupId = null }, icon = { Icon(Icons.Default.Collections, "Albums") })
            }
        }
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding).background(Color.Black)) {
            if (mode == CollectionMode.ALBUMS && albumRoot == null) {
                OrganizedAlbumGrid(
                    media = media,
                    layout = albumLayout,
                    groupId = albumGroupId,
                    prefs = prefs,
                    controller = controller,
                    onOpenAlbum = { root ->
                        albumRoot = root
                        controller.log(null, EventTypes.ALBUM_OPEN, details = root)
                    },
                    onOpenGroup = { albumGroupId = it },
                    onLayoutChanged = { refreshAlbumLayout() }
                )
            } else {
                MediaGrid(
                    controller = controller,
                    media = visibleMedia,
                    columns = gridColumns,
                    onColumnsChanged = { next ->
                        val clamped = next.coerceIn(2, 8)
                        if (clamped != gridColumns) {
                            gridColumns = clamped
                            prefs.edit().putInt("grid_columns", gridColumns).apply()
                            controller.log(null, EventTypes.GRID_RESIZE, value = gridColumns.toLong())
                        }
                    },
                    onOpen = { viewerStartId = it.id },
                    onToggleFavorite = { item ->
                        val next = !item.favorite
                        controller.db.setFavorite(item.id, next)
                        controller.log(item.id, if (next) EventTypes.FAVORITE_SET else EventTypes.FAVORITE_UNSET)
                        media = media.map { if (it.id == item.id) it.copy(favorite = next) else it }
                    }
                )
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun MediaGrid(
    controller: AppController,
    media: List<MediaItem>,
    columns: Int,
    onColumnsChanged: (Int) -> Unit,
    onOpen: (MediaItem) -> Unit,
    onToggleFavorite: (MediaItem) -> Unit
) {
    if (media.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Nothing here yet") }
        return
    }
    var currentColumns by remember(columns) { mutableIntStateOf(columns) }
    val gridState = rememberLazyGridState()
    LaunchedEffect(columns) { currentColumns = columns }
    LaunchedEffect(gridState) {
        var lastIndex = gridState.firstVisibleItemIndex
        snapshotFlow { gridState.firstVisibleItemIndex }.distinctUntilChanged().collect { index ->
            val delta = index - lastIndex
            if (delta != 0) controller.log(null, EventTypes.GALLERY_SCROLL, value = delta.toLong(), details = "index=$index;columns=$currentColumns")
            lastIndex = index
        }
    }

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
                            currentColumns -= 1; onColumnsChanged(currentColumns); accumulated = 1f
                        } else if (accumulated < 0.84f && currentColumns < 8) {
                            currentColumns += 1; onColumnsChanged(currentColumns); accumulated = 1f
                        }
                    }
                    lastDistance = distance
                    pressed.forEach { it.consume() }
                } else lastDistance = null
            }
        }
    }

    LazyVerticalGrid(
        columns = GridCells.Fixed(currentColumns),
        state = gridState,
        modifier = Modifier.fillMaxSize().then(pinchModifier),
        horizontalArrangement = Arrangement.spacedBy(2.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        items(media, key = { it.id }) { item ->
            Box(
                Modifier.aspectRatio(1f).combinedClickable(onClick = { onOpen(item) }, onLongClick = { onToggleFavorite(item) })
            ) {
                MediaThumbnail(item, Modifier.fillMaxSize(), ContentScale.Crop)
                if (item.isVideo) Icon(Icons.Default.Movie, null, modifier = Modifier.align(Alignment.BottomStart).padding(6.dp).size(22.dp), tint = Color.White)
                if (item.favorite) Icon(Icons.Default.Favorite, null, modifier = Modifier.align(Alignment.TopEnd).padding(5.dp).size(20.dp), tint = Color(0xFFFF4D67))
            }
        }
    }
}

private data class AlbumCardModel(
    val token: String,
    val label: String,
    val roots: List<String>,
    val items: List<MediaItem>,
    val groupId: String? = null
)

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun OrganizedAlbumGrid(
    media: List<MediaItem>,
    layout: AlbumLayoutState,
    groupId: String?,
    prefs: android.content.SharedPreferences,
    controller: AppController,
    onOpenAlbum: (String) -> Unit,
    onOpenGroup: (String) -> Unit,
    onLayoutChanged: () -> Unit
) {
    val byRoot = remember(media) { media.groupBy { it.rootUri } }
    val models = remember(media, layout, groupId) {
        if (groupId != null) {
            layout.groups[groupId]?.roots.orEmpty().mapNotNull { root ->
                byRoot[root]?.let { AlbumCardModel("a:$root", albumLabel(root), listOf(root), it) }
            }
        } else {
            layout.order.mapNotNull { token ->
                when {
                    token.startsWith("a:") -> {
                        val root = token.removePrefix("a:")
                        byRoot[root]?.let { AlbumCardModel(token, albumLabel(root), listOf(root), it) }
                    }
                    token.startsWith("g:") -> {
                        val id = token.removePrefix("g:")
                        val group = layout.groups[id] ?: return@mapNotNull null
                        val items = group.roots.flatMap { byRoot[it].orEmpty() }
                        if (items.isEmpty()) null else AlbumCardModel(token, group.name, group.roots.toList(), items, id)
                    }
                    else -> null
                }
            }
        }
    }

    if (models.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("No albums yet") }
        return
    }

    val bounds = remember { mutableStateMapOf<String, Rect>() }
    var dragging by remember { mutableStateOf<String?>(null) }
    var dragOffset by remember { mutableStateOf(Offset.Zero) }
    var menuToken by remember { mutableStateOf<String?>(null) }
    var renameGroupId by remember { mutableStateOf<String?>(null) }
    var renameText by remember { mutableStateOf("") }

    if (renameGroupId != null) {
        AlertDialog(
            onDismissRequest = { renameGroupId = null },
            title = { Text("Name this album group") },
            text = { OutlinedTextField(value = renameText, onValueChange = { renameText = it }, singleLine = true) },
            confirmButton = {
                TextButton(onClick = {
                    renameGroupId?.let { AlbumOrganizer.renameGroup(prefs, layout, it, renameText) }
                    renameGroupId = null
                    onLayoutChanged()
                }) { Text("Save") }
            },
            dismissButton = { TextButton(onClick = { renameGroupId = null }) { Text("Cancel") } }
        )
    }

    fun finishDrop(sourceToken: String, offset: Offset) {
        val sourceBounds = bounds[sourceToken] ?: return
        val dropPoint = sourceBounds.center + offset
        val targetEntry = bounds.entries.firstOrNull { it.key != sourceToken && it.value.contains(dropPoint) } ?: return
        val targetToken = targetEntry.key
        val targetBounds = targetEntry.value

        if (groupId != null) {
            val sourceRoot = sourceToken.removePrefix("a:")
            val targetRoot = targetToken.removePrefix("a:")
            AlbumOrganizer.reorderInsideGroup(prefs, layout, groupId, sourceRoot, targetRoot)
            controller.log(null, EventTypes.ALBUM_REORDER, details = "group=$groupId;$sourceRoot->$targetRoot")
            onLayoutChanged()
            return
        }

        val centralDrop = abs(dropPoint.x - targetBounds.center.x) < targetBounds.width * 0.34f && abs(dropPoint.y - targetBounds.center.y) < targetBounds.height * 0.34f
        val sourceIsAlbum = sourceToken.startsWith("a:")
        val targetIsAlbum = targetToken.startsWith("a:")
        val targetIsGroup = targetToken.startsWith("g:")

        when {
            centralDrop && sourceIsAlbum && targetIsAlbum -> {
                val sourceRoot = sourceToken.removePrefix("a:")
                val targetRoot = targetToken.removePrefix("a:")
                val id = AlbumOrganizer.createGroup(prefs, layout, sourceRoot, targetRoot)
                if (id.isNotBlank()) {
                    controller.log(null, EventTypes.ALBUM_GROUP_CREATE, details = "$sourceRoot+$targetRoot->$id")
                    renameGroupId = id
                    renameText = "New group"
                }
            }
            centralDrop && sourceIsAlbum && targetIsGroup -> {
                AlbumOrganizer.addToGroup(prefs, layout, sourceToken.removePrefix("a:"), targetToken.removePrefix("g:"))
                controller.log(null, EventTypes.ALBUM_GROUP_CREATE, details = "${sourceToken.removePrefix("a:")} -> ${targetToken.removePrefix("g:")}")
            }
            else -> {
                val before = dropPoint.y < targetBounds.center.y || (abs(dropPoint.y - targetBounds.center.y) < targetBounds.height * 0.35f && dropPoint.x < targetBounds.center.x)
                AlbumOrganizer.reorderTop(prefs, layout, sourceToken, targetToken, before)
                controller.log(null, EventTypes.ALBUM_REORDER, details = "$sourceToken->$targetToken;before=$before")
            }
        }
        onLayoutChanged()
    }

    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        modifier = Modifier.fillMaxSize(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        items(models, key = { it.token }) { model ->
            val isDragging = dragging == model.token
            Card(
                onClick = {
                    if (model.groupId != null) onOpenGroup(model.groupId)
                    else model.roots.firstOrNull()?.let(onOpenAlbum)
                },
                colors = CardDefaults.cardColors(containerColor = Color(0xFF141414)),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier
                    .onGloballyPositioned { bounds[model.token] = it.boundsInRoot() }
                    .graphicsLayer {
                        if (isDragging) {
                            translationX = dragOffset.x
                            translationY = dragOffset.y
                            scaleX = 1.04f; scaleY = 1.04f
                            alpha = 0.90f
                        }
                    }
                    .pointerInput(model.token, groupId) {
                        detectDragGesturesAfterLongPress(
                            onDragStart = { dragging = model.token; dragOffset = Offset.Zero },
                            onDrag = { change, amount -> change.consume(); dragOffset += amount },
                            onDragEnd = {
                                dragging?.let { finishDrop(it, dragOffset) }
                                dragging = null; dragOffset = Offset.Zero
                            },
                            onDragCancel = { dragging = null; dragOffset = Offset.Zero }
                        )
                    }
            ) {
                Column {
                    val cover = model.items.maxByOrNull { it.modified }
                    Box(Modifier.fillMaxWidth().aspectRatio(1.25f)) {
                        if (cover != null) MediaThumbnail(cover, Modifier.fillMaxSize(), ContentScale.Crop, model.label)
                        if (model.groupId != null) {
                            Surface(
                                modifier = Modifier.align(Alignment.BottomStart).padding(7.dp),
                                color = Color.Black.copy(alpha = 0.72f),
                                shape = RoundedCornerShape(12.dp)
                            ) { Text("${model.roots.size} albums", Modifier.padding(horizontal = 8.dp, vertical = 4.dp)) }
                        }
                        Box(Modifier.align(Alignment.TopEnd)) {
                            IconButton(onClick = { menuToken = model.token }) { Icon(Icons.Default.MoreVert, "Album options") }
                            DropdownMenu(expanded = menuToken == model.token, onDismissRequest = { menuToken = null }) {
                                if (model.groupId != null) {
                                    DropdownMenuItem(text = { Text("Rename group") }, onClick = {
                                        menuToken = null; renameGroupId = model.groupId; renameText = model.label
                                    })
                                    DropdownMenuItem(text = { Text("Ungroup") }, onClick = {
                                        menuToken = null
                                        AlbumOrganizer.ungroup(prefs, layout, model.groupId)
                                        onLayoutChanged()
                                    })
                                } else if (groupId != null) {
                                    DropdownMenuItem(text = { Text("Remove from group") }, onClick = {
                                        menuToken = null
                                        AlbumOrganizer.removeFromGroup(prefs, layout, groupId, model.roots.first())
                                        onLayoutChanged()
                                    })
                                }
                            }
                        }
                    }
                    Column(Modifier.padding(10.dp)) {
                        Text(model.label, maxLines = 1)
                        Text("${model.items.size} items", color = Color.Gray)
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
