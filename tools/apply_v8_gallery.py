from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/GalleryUi.kt"
s = p.read_text()

def rep(old, new, label):
    global s
    if old not in s:
        raise RuntimeError(f"v8 gallery anchor missing: {label}")
    s = s.replace(old, new, 1)

# Imports used by the replacement grid/gesture code.
s = s.replace('import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress\n', 'import androidx.compose.foundation.gestures.detectDragGestures\nimport androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress\n', 1)
s = s.replace('import androidx.compose.foundation.layout.fillMaxSize\n', 'import androidx.compose.foundation.layout.fillMaxHeight\nimport androidx.compose.foundation.layout.fillMaxSize\n', 1)
s = s.replace('import androidx.compose.foundation.layout.padding\n', 'import androidx.compose.foundation.layout.height\nimport androidx.compose.foundation.layout.padding\n', 1)
s = s.replace('import androidx.compose.foundation.layout.size\n', 'import androidx.compose.foundation.layout.size\nimport androidx.compose.foundation.layout.width\n', 1)
s = s.replace('import androidx.compose.foundation.lazy.grid.GridCells\n', 'import androidx.compose.foundation.lazy.grid.GridCells\nimport androidx.compose.foundation.lazy.grid.LazyGridState\n', 1)
s = s.replace('import androidx.compose.runtime.Composable\n', 'import androidx.compose.runtime.Composable\nimport androidx.compose.runtime.derivedStateOf\n', 1)
s = s.replace('import androidx.compose.ui.layout.onGloballyPositioned\n', 'import androidx.compose.ui.layout.onGloballyPositioned\nimport androidx.compose.ui.layout.onSizeChanged\n', 1)
s = s.replace('import androidx.compose.ui.platform.LocalContext\n', 'import androidx.compose.ui.platform.LocalContext\nimport androidx.compose.ui.platform.LocalDensity\n', 1)

# Screen-level arbitration and deliberate sort reset.
anchor = '    var interactionScores by remember { mutableStateOf<Map<Long, Double>>(emptyMap()) }\n'
rep(anchor, anchor + '    var albumDragActive by remember { mutableStateOf(false) }\n    var sortResetNonce by remember { mutableIntStateOf(0) }\n', 'screen gesture state')

# Replace the permissive v0.7 tab detector. It remains forgiving, but only
# claims a gesture after horizontal intent is clear and never while an album
# card is being dragged.
start = s.find('    val modeSwipeModifier = Modifier.pointerInput(')
end = s.find('\n\n    Scaffold(', start)
if start < 0 or end < 0:
    raise RuntimeError('v8 gallery mode swipe block missing')
mode_swipe = r'''    val modeSwipeModifier = Modifier.pointerInput(mode, albumRoot, albumGroupId, albumDragActive) {
        if (albumRoot == null && albumGroupId == null && !albumDragActive) {
            val threshold = 54.dp.toPx()
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
                    if (!claimed && abs(dx) > 18.dp.toPx() && abs(dx) > abs(dy) * 1.18f) claimed = true
                    if (claimed) change.consume()
                }
                if (!multiTouch && claimed && abs(dx) > threshold && abs(dx) > abs(dy) * 1.05f) {
                    val modes = listOf(CollectionMode.ALL, CollectionMode.VIDEOS, CollectionMode.FAVORITES, CollectionMode.ALBUMS)
                    val currentMode = modes.indexOf(mode).coerceAtLeast(0)
                    val next = if (dx < 0) (currentMode + 1).coerceAtMost(modes.lastIndex) else (currentMode - 1).coerceAtLeast(0)
                    if (next != currentMode) {
                        mode = modes[next]
                        albumRoot = null; albumGroupId = null
                        controller.log(null, EventTypes.GALLERY_MODE, details = "gesture=${mode.name}")
                    }
                }
            }
        }
    }'''
s = s[:start] + mode_swipe + s[end:]

# Sort selection deliberately starts at the top of the newly sorted result.
for old, new in [
    ('sortMode = SortMode.NEWEST; menuOpen = false', 'sortMode = SortMode.NEWEST; sortResetNonce += 1; menuOpen = false'),
    ('sortMode = SortMode.OLDEST; menuOpen = false', 'sortMode = SortMode.OLDEST; sortResetNonce += 1; menuOpen = false'),
    ('sortMode = SortMode.NAME; menuOpen = false', 'sortMode = SortMode.NAME; sortResetNonce += 1; menuOpen = false'),
    ('sortMode = SortMode.INTERACTION_DESC; menuOpen = false', 'sortMode = SortMode.INTERACTION_DESC; sortResetNonce += 1; menuOpen = false'),
    ('sortMode = SortMode.INTERACTION_ASC; menuOpen = false', 'sortMode = SortMode.INTERACTION_ASC; sortResetNonce += 1; menuOpen = false'),
]:
    if old not in s:
        raise RuntimeError(f'v8 gallery sort action missing: {old}')
    s = s.replace(old, new, 1)

rep('''                    scrollKey = "${albumRoot ?: mode.name}",
                    onOpen = { item -> if (pickMode) onPickMedia?.invoke(item) else viewerStartId = item.id },
''', '''                    scrollKey = "${albumRoot ?: mode.name}",
                    scrollResetKey = sortResetNonce,
                    onOpen = { item -> if (pickMode) onPickMedia?.invoke(item) else viewerStartId = item.id },
''', 'media grid reset arg')

rep('''                    onOpenGroup = { albumGroupId = it },
                    onLayoutChanged = { refreshAlbumLayout() }
''', '''                    onOpenGroup = { albumGroupId = it },
                    onDragActiveChanged = { albumDragActive = it },
                    onLayoutChanged = { refreshAlbumLayout() }
''', 'album drag callback')

# Replace MediaGrid wholesale. Keying LazyGridState by logical location fixes
# stale-state contamination, and the side rail gives long galleries a proper
# fast scroller.
start = s.find('@OptIn(ExperimentalFoundationApi::class)\n@Composable\nprivate fun MediaGrid(')
end = s.find('\nprivate data class AlbumCardModel(', start)
if start < 0 or end < 0:
    raise RuntimeError('v8 gallery MediaGrid boundaries missing')
media_grid = r'''@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun MediaGrid(
    controller: AppController,
    media: List<MediaItem>,
    columns: Int,
    scrollKey: String,
    scrollResetKey: Int,
    onColumnsChanged: (Int) -> Unit,
    onOpen: (MediaItem) -> Unit,
    onToggleFavorite: (MediaItem) -> Unit
) {
    if (media.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Nothing here yet") }
        return
    }
    var currentColumns by remember(columns) { mutableIntStateOf(columns) }
    val localPrefs = LocalContext.current.getSharedPreferences("neurontap", 0)
    val savedIndex = remember(scrollKey) { localPrefs.getInt("grid_index_$scrollKey", 0).coerceIn(0, media.lastIndex) }
    val savedOffset = remember(scrollKey) { localPrefs.getInt("grid_offset_$scrollKey", 0).coerceAtLeast(0) }
    val gridState = remember(scrollKey) { LazyGridState(savedIndex, savedOffset) }
    val scope = rememberCoroutineScope()
    val density = LocalDensity.current
    var railHeightPx by remember { mutableIntStateOf(0) }
    val thumbHeightPx = with(density) { 52.dp.toPx() }
    val scrollFraction by remember(gridState, media.size) {
        derivedStateOf {
            if (media.size <= 1) 0f else (gridState.firstVisibleItemIndex.toFloat() / (media.size - 1).toFloat()).coerceIn(0f, 1f)
        }
    }

    LaunchedEffect(columns) { currentColumns = columns }
    LaunchedEffect(scrollResetKey) {
        if (scrollResetKey > 0) {
            gridState.scrollToItem(0)
            localPrefs.edit().putInt("grid_index_$scrollKey", 0).putInt("grid_offset_$scrollKey", 0).apply()
        }
    }
    LaunchedEffect(gridState, scrollKey) {
        var lastIndex = gridState.firstVisibleItemIndex
        snapshotFlow { gridState.firstVisibleItemIndex to gridState.firstVisibleItemScrollOffset }
            .distinctUntilChanged()
            .collect { (index, offset) ->
                val delta = index - lastIndex
                if (delta != 0) controller.log(null, EventTypes.GALLERY_SCROLL, value = delta.toLong(), details = "index=$index;columns=$currentColumns")
                localPrefs.edit().putInt("grid_index_$scrollKey", index).putInt("grid_offset_$scrollKey", offset).apply()
                lastIndex = index
            }
    }

    val pinchModifier = Modifier.pointerInput(scrollKey) {
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

    Box(Modifier.fillMaxSize()) {
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

        if (media.size > currentColumns * 8) {
            Box(
                Modifier.align(Alignment.CenterEnd).fillMaxHeight().width(28.dp)
                    .onSizeChanged { railHeightPx = it.height }
                    .pointerInput(media.size, currentColumns, railHeightPx) {
                        fun jump(y: Float) {
                            if (railHeightPx <= 0) return
                            val fraction = (y / railHeightPx.toFloat()).coerceIn(0f, 1f)
                            val target = ((media.size - 1) * fraction).roundToInt().coerceIn(0, media.lastIndex)
                            scope.launch { gridState.scrollToItem(target) }
                        }
                        detectDragGestures(
                            onDragStart = { jump(it.y) },
                            onDrag = { change, _ -> change.consume(); jump(change.position.y) }
                        )
                    }
            ) {
                Box(
                    Modifier.align(Alignment.TopCenter).width(6.dp).height(52.dp)
                        .graphicsLayer {
                            translationY = scrollFraction * (railHeightPx.toFloat() - thumbHeightPx).coerceAtLeast(0f)
                        }
                        .background(Color.White.copy(alpha = 0.72f), RoundedCornerShape(8.dp))
                )
            }
        }
    }
}
'''
s = s[:start] + media_grid + s[end:]

# Collection browser: each logical Collection gets its own actual grid-state
# object. Also report drag ownership to the parent so tab swipes cannot steal it.
rep('''    onOpenAlbum: (String) -> Unit,
    onOpenGroup: (String) -> Unit,
    onLayoutChanged: () -> Unit
''', '''    onOpenAlbum: (String) -> Unit,
    onOpenGroup: (String) -> Unit,
    onDragActiveChanged: (Boolean) -> Unit,
    onLayoutChanged: () -> Unit
''', 'organized grid signature')

old_state = '''    val albumGridState = rememberLazyGridState(
        prefs.getInt("${albumScrollKey}_index", 0).coerceAtLeast(0),
        prefs.getInt("${albumScrollKey}_offset", 0).coerceAtLeast(0)
    )
'''
new_state = '''    val albumGridState = remember(albumScrollKey) {
        LazyGridState(
            prefs.getInt("${albumScrollKey}_index", 0).coerceAtLeast(0),
            prefs.getInt("${albumScrollKey}_offset", 0).coerceAtLeast(0)
        )
    }
'''
rep(old_state, new_state, 'collection keyed scroll state')

# Deliberate center drop nests/groups. Dropping toward an edge means reorder.
s = s.replace('''        val closeEnough = abs(movedCenter.x - targetBounds.center.x) < (sourceBounds.width + targetBounds.width) * 0.48f &&
            abs(movedCenter.y - targetBounds.center.y) < (sourceBounds.height + targetBounds.height) * 0.48f

        if (closeEnough) {
''', '''        val deliberateCenterDrop = abs(movedCenter.x - targetBounds.center.x) < targetBounds.width * 0.24f &&
            abs(movedCenter.y - targetBounds.center.y) < targetBounds.height * 0.24f

        if (deliberateCenterDrop) {
''', 1)

rep('''                            onDragStart = { dragging = model.token; dragOffset = Offset.Zero },
                            onDrag = { change, amount -> change.consume(); dragOffset += amount },
                            onDragEnd = {
                                dragging?.let { finishDrop(it, dragOffset) }
                                dragging = null; dragOffset = Offset.Zero
                            },
                            onDragCancel = { dragging = null; dragOffset = Offset.Zero }
''', '''                            onDragStart = { dragging = model.token; dragOffset = Offset.Zero; onDragActiveChanged(true) },
                            onDrag = { change, amount -> change.consume(); dragOffset += amount },
                            onDragEnd = {
                                dragging?.let { finishDrop(it, dragOffset) }
                                dragging = null; dragOffset = Offset.Zero; onDragActiveChanged(false)
                            },
                            onDragCancel = { dragging = null; dragOffset = Offset.Zero; onDragActiveChanged(false) }
''', 'album drag ownership')

p.write_text(s)
print('Applied v8 gallery and collection fixes')
