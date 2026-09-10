from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/GalleryUi.kt"
s = p.read_text()

def rep(old, new, label):
    global s
    if old not in s:
        raise RuntimeError(f"v7 gallery anchor missing: {label}")
    s = s.replace(old, new, 1)

rep('private enum class SortMode { NEWEST, OLDEST, NAME }', 'private enum class SortMode { NEWEST, OLDEST, NAME, INTERACTION_DESC, INTERACTION_ASC }', 'sort enum')
rep('    var albumLayout by remember { mutableStateOf(AlbumLayoutState()) }\n', '    var albumLayout by remember { mutableStateOf(AlbumLayoutState()) }\n    var albumLayoutRevision by remember { mutableIntStateOf(0) }\n    var interactionScores by remember { mutableStateOf<Map<Long, Double>>(emptyMap()) }\n', 'layout revision')

# Force Compose invalidation after in-place organizer mutations and refresh scores
# whenever the library is reloaded after viewer activity.
old = '''    fun refreshAlbumLayout() {
        albumLayout = AlbumOrganizer.load(prefs, media.map { it.rootUri }.toSet())
    }
'''
new = '''    fun refreshAlbumLayout() {
        albumLayout = AlbumOrganizer.load(prefs, media.map { it.rootUri }.toSet())
        albumLayoutRevision += 1
    }
'''
rep(old, new, 'refresh layout')

needle = '        albumLayout = AlbumOrganizer.load(prefs, media.map { it.rootUri }.toSet())\n    }\n\n    suspend fun scanDevice()'
replacement = '        albumLayout = AlbumOrganizer.load(prefs, media.map { it.rootUri }.toSet())\n        interactionScores = withContext(Dispatchers.IO) { controller.db.behaviorSummaries().associate { it.mediaId to it.attractionScore } }\n        albumLayoutRevision += 1\n    }\n\n    suspend fun scanDevice()'
rep(needle, replacement, 'reload scores')

# Stable viewer argument name introduced by v7 viewer base.
s = s.replace('            items = visibleMedia,', '            incomingItems = visibleMedia,')

# Back from a nested Collection returns to its parent Collection, not straight to root.
s = s.replace('            albumGroupId != null -> albumGroupId = null', '            albumGroupId != null -> albumGroupId = AlbumOrganizer.findParent(albumLayout, "g:${albumGroupId!!}")')
s = s.replace('                                } else albumGroupId = null', '                                } else albumGroupId = AlbumOrganizer.findParent(albumLayout, "g:${albumGroupId!!}")')

# Interaction sorting.
old_sort = '''        when (sortMode) {
            SortMode.NEWEST -> searched.sortedByDescending { it.modified }
            SortMode.OLDEST -> searched.sortedBy { it.modified }
            SortMode.NAME -> searched.sortedBy { it.name.lowercase() }
        }
'''
new_sort = '''        when (sortMode) {
            SortMode.NEWEST -> searched.sortedByDescending { it.modified }
            SortMode.OLDEST -> searched.sortedBy { it.modified }
            SortMode.NAME -> searched.sortedBy { it.name.lowercase() }
            SortMode.INTERACTION_DESC -> searched.sortedWith(compareByDescending<MediaItem> { interactionScores[it.id] ?: 0.0 }.thenByDescending { it.modified })
            SortMode.INTERACTION_ASC -> searched.sortedWith(compareBy<MediaItem> { interactionScores[it.id] ?: 0.0 }.thenByDescending { it.modified })
        }
'''
rep(old_sort, new_sort, 'interaction sort')

sort_menu = '                                DropdownMenuItem(text = { Text("Sort: name") }, onClick = { sortMode = SortMode.NAME; menuOpen = false })\n'
rep(sort_menu, sort_menu + '                                DropdownMenuItem(text = { Text("Sort: most interacted") }, onClick = { sortMode = SortMode.INTERACTION_DESC; menuOpen = false })\n                                DropdownMenuItem(text = { Text("Sort: least interacted") }, onClick = { sortMode = SortMode.INTERACTION_ASC; menuOpen = false })\n', 'sort menu')

# Less perfect/long swipes between Gallery, Videos, Favorites and Albums.
s = s.replace('val threshold = 92.dp.toPx()', 'val threshold = 58.dp.toPx()')
s = s.replace('abs(dx) > 24.dp.toPx() && abs(dx) > abs(dy) * 1.35f', 'abs(dx) > 14.dp.toPx() && abs(dx) > abs(dy) * 0.78f')
s = s.replace('abs(dx) > threshold && abs(dx) > abs(dy) * 1.35f', 'abs(dx) > threshold && abs(dx) > abs(dy) * 0.72f')

# Ensure models are recomputed even when an organizer mutation leaves the same
# data-class instance structurally equal.
call_anchor = '''                    layout = albumLayout,
                    groupId = albumGroupId,
'''
rep(call_anchor, '''                    layout = albumLayout,
                    layoutRevision = albumLayoutRevision,
                    groupId = albumGroupId,
''', 'organizer revision call')

# Replace the entire album/Collection browser with a nested token-aware version.
start = s.find('@OptIn(ExperimentalFoundationApi::class)\n@Composable\nprivate fun OrganizedAlbumGrid(')
end = s.find('\nfun albumLabel(root: String): String {', start)
if start < 0 or end < 0:
    raise RuntimeError('v7 gallery OrganizedAlbumGrid boundaries missing')
new_grid = r'''@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun OrganizedAlbumGrid(
    media: List<MediaItem>,
    layout: AlbumLayoutState,
    layoutRevision: Int,
    groupId: String?,
    prefs: android.content.SharedPreferences,
    controller: AppController,
    onOpenAlbum: (String) -> Unit,
    onOpenGroup: (String) -> Unit,
    onLayoutChanged: () -> Unit
) {
    val byRoot = remember(media) { media.groupBy { it.rootUri } }
    val models = remember(media, layout, layoutRevision, groupId) {
        val tokens = groupId?.let(layout::childrenOf) ?: layout.order
        tokens.mapNotNull { token ->
            when {
                token.startsWith("a:") -> {
                    val root = token.removePrefix("a:")
                    byRoot[root]?.let { AlbumCardModel(token, albumLabel(root), listOf(root), it) }
                }
                token.startsWith("g:") -> {
                    val id = token.removePrefix("g:")
                    val group = layout.groups[id] ?: return@mapNotNull null
                    val roots = layout.rootsForGroup(id)
                    val items = roots.flatMap { byRoot[it].orEmpty() }
                    AlbumCardModel(token, group.name, roots, items, id)
                }
                else -> null
            }
        }
    }

    if (models.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("No albums or collections here") }
        return
    }

    val albumScrollKey = "album_grid_${groupId ?: "root"}"
    val albumGridState = rememberLazyGridState(
        prefs.getInt("${albumScrollKey}_index", 0).coerceAtLeast(0),
        prefs.getInt("${albumScrollKey}_offset", 0).coerceAtLeast(0)
    )
    LaunchedEffect(albumGridState, albumScrollKey) {
        snapshotFlow { albumGridState.firstVisibleItemIndex to albumGridState.firstVisibleItemScrollOffset }
            .distinctUntilChanged()
            .collect { (index, offset) ->
                prefs.edit().putInt("${albumScrollKey}_index", index).putInt("${albumScrollKey}_offset", offset).apply()
            }
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
            title = { Text("Rename collection") },
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
        val movedCenter = sourceBounds.center + offset
        val targetEntry = bounds.entries.filter { it.key != sourceToken }.minByOrNull { (_, rect) ->
            val dx = movedCenter.x - rect.center.x
            val dy = movedCenter.y - rect.center.y
            dx * dx + dy * dy
        } ?: return
        val targetToken = targetEntry.key
        val targetBounds = targetEntry.value
        val closeEnough = abs(movedCenter.x - targetBounds.center.x) < (sourceBounds.width + targetBounds.width) * 0.48f &&
            abs(movedCenter.y - targetBounds.center.y) < (sourceBounds.height + targetBounds.height) * 0.48f

        if (closeEnough) {
            if (targetToken.startsWith("g:")) {
                val targetGroup = targetToken.removePrefix("g:")
                if (AlbumOrganizer.addTokenToGroup(prefs, layout, sourceToken, targetGroup, groupId)) {
                    controller.log(null, EventTypes.ALBUM_GROUP_CREATE, details = "$sourceToken -> $targetToken")
                    onLayoutChanged()
                    return
                }
            } else {
                val id = AlbumOrganizer.createCollectionFromTokens(prefs, layout, groupId, sourceToken, targetToken)
                if (id.isNotBlank()) {
                    controller.log(null, EventTypes.ALBUM_GROUP_CREATE, details = "$sourceToken+$targetToken->$id")
                    onLayoutChanged()
                    return
                }
            }
        }

        val before = movedCenter.y < targetBounds.center.y ||
            (abs(movedCenter.y - targetBounds.center.y) < targetBounds.height * 0.35f && movedCenter.x < targetBounds.center.x)
        AlbumOrganizer.reorderInContainer(prefs, layout, groupId, sourceToken, targetToken, before)
        controller.log(null, EventTypes.ALBUM_REORDER, details = "parent=${groupId ?: "root"};$sourceToken->$targetToken;before=$before")
        onLayoutChanged()
    }

    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        state = albumGridState,
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
                            scaleX = 1.04f; scaleY = 1.04f; alpha = 0.90f
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
                        else Box(Modifier.fillMaxSize().background(Color(0xFF202020)))
                        if (model.groupId != null) {
                            Surface(
                                modifier = Modifier.align(Alignment.BottomStart).padding(7.dp),
                                color = Color.Black.copy(alpha = 0.76f),
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                val childCount = layout.childrenOf(model.groupId).size
                                Text("$childCount inside · ${model.roots.size} albums", Modifier.padding(horizontal = 8.dp, vertical = 4.dp), color = Color.White)
                            }
                        }
                        Box(Modifier.align(Alignment.TopEnd)) {
                            IconButton(onClick = { menuToken = model.token }) { Icon(Icons.Default.MoreVert, "Album or collection options", tint = Color.White) }
                            DropdownMenu(expanded = menuToken == model.token, onDismissRequest = { menuToken = null }) {
                                if (model.groupId != null) {
                                    DropdownMenuItem(text = { Text("Rename collection") }, onClick = {
                                        menuToken = null; renameGroupId = model.groupId; renameText = model.label
                                    })
                                    if (groupId != null) DropdownMenuItem(text = { Text("Move out of this collection") }, onClick = {
                                        menuToken = null
                                        AlbumOrganizer.removeTokenFromGroup(prefs, layout, groupId, model.token)
                                        onLayoutChanged()
                                    })
                                    DropdownMenuItem(text = { Text("Dissolve collection") }, onClick = {
                                        menuToken = null
                                        AlbumOrganizer.ungroup(prefs, layout, model.groupId)
                                        onLayoutChanged()
                                    })
                                } else if (groupId != null) {
                                    DropdownMenuItem(text = { Text("Move album out of this collection") }, onClick = {
                                        menuToken = null
                                        AlbumOrganizer.removeTokenFromGroup(prefs, layout, groupId, model.token)
                                        onLayoutChanged()
                                    })
                                }
                            }
                        }
                    }
                    Column(Modifier.padding(10.dp)) {
                        Text(model.label, maxLines = 1, color = Color.White)
                        Text("${model.items.size} items", color = Color.Gray)
                    }
                }
            }
        }
    }
}
'''
s = s[:start] + new_grid + s[end:]
p.write_text(s)
print('Applied v7 gallery')
