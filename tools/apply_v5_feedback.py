from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
viewer_path = ROOT / "app/src/main/java/com/neurontap/app/ViewerUi.kt"
gallery_path = ROOT / "app/src/main/java/com/neurontap/app/GalleryUi.kt"
organizer_path = ROOT / "app/src/main/java/com/neurontap/app/AlbumOrganizer.kt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Patch anchor not found: {label}")
    return text.replace(old, new, 1)


# --- Viewer fixes ---------------------------------------------------------
v = viewer_path.read_text()

v = replace_once(
    v,
    "import androidx.compose.animation.AnimatedVisibility\n",
    "import androidx.compose.animation.AnimatedVisibility\nimport androidx.compose.animation.core.Animatable\nimport androidx.compose.animation.core.tween\n",
    "viewer animation imports",
)

v = replace_once(
    v,
    "import androidx.media3.exoplayer.ExoPlayer\n",
    "import androidx.media3.exoplayer.ExoPlayer\nimport androidx.media3.exoplayer.SeekParameters\n",
    "seek parameters import",
)

v = replace_once(
    v,
    "        var firstReactionLogged by remember(current.id, trackedStartMs) { mutableStateOf(false) }\n",
    "        var firstReactionLogged by remember(current.id, trackedStartMs) { mutableStateOf(false) }\n        val reactionPulse = remember { Animatable(1f) }\n        var reactionPulseTick by remember { mutableIntStateOf(0) }\n\n        LaunchedEffect(reactionPulseTick) {\n            if (reactionPulseTick > 0) {\n                reactionPulse.snapTo(1f)\n                reactionPulse.animateTo(1.18f, tween(65))\n                reactionPulse.animateTo(0.96f, tween(55))\n                reactionPulse.animateTo(1f, tween(75))\n            }\n        }\n",
    "reaction pulse state",
)

v = replace_once(
    v,
    "                    controller.log(current.id, EventTypes.REACTION_UP, value = upAt - downAt, mediaPositionMs = latestVideoPosition, x = finalPosition.x.toDouble(), y = finalPosition.y.toDouble(), at = upAt)\n",
    "                    controller.log(current.id, EventTypes.REACTION_UP, value = upAt - downAt, mediaPositionMs = latestVideoPosition, x = finalPosition.x.toDouble(), y = finalPosition.y.toDouble(), at = upAt)\n                    reactionPulseTick += 1\n",
    "reaction pulse trigger",
)

v = replace_once(
    v,
    "            val threshold = with(density) { 92.dp.toPx() }\n",
    "            val threshold = with(density) { 56.dp.toPx() }\n",
    "drawer swipe threshold",
)

v = replace_once(
    v,
    "                var dx = 0f\n                var dy = 0f\n                var previous = first.position\n",
    "                var dx = 0f\n                var dy = 0f\n                var verticalClaimed = false\n                var previous = first.position\n",
    "drawer swipe state",
)

v = replace_once(
    v,
    "                    dx += delta.x; dy += delta.y\n                }\n                if (!currentZoomed && abs(dy) > threshold && abs(dy) > abs(dx) * 1.25f) {\n",
    "                    dx += delta.x; dy += delta.y\n                    if (!verticalClaimed && abs(dy) > touchSlop * 1.15f && abs(dy) > abs(dx) * 0.65f) verticalClaimed = true\n                    if (verticalClaimed) down.consume()\n                }\n                if (!currentZoomed && verticalClaimed && abs(dy) > threshold && abs(dy) > abs(dx) * 0.65f) {\n",
    "drawer vertical gesture claiming",
)

v = replace_once(
    v,
    "                    IconButton(onClick = {\n                        val next = current.id !in favoriteIds\n",
    "                    IconButton(modifier = Modifier.size(66.dp), onClick = {\n                        val next = current.id !in favoriteIds\n",
    "favorite hit target",
)

v = replace_once(
    v,
    "                        Icon(if (current.id in favoriteIds) Icons.Default.Favorite else Icons.Default.FavoriteBorder, \"Favorite\", tint = if (current.id in favoriteIds) Color(0xFFFF4D67) else Color.White, modifier = Modifier.size(30.dp))\n",
    "                        Icon(if (current.id in favoriteIds) Icons.Default.Favorite else Icons.Default.FavoriteBorder, \"Favorite\", tint = if (current.id in favoriteIds) Color(0xFFFF4D67) else Color.White, modifier = Modifier.size(36.dp))\n",
    "favorite icon size",
)

v = replace_once(
    v,
    "                Surface(shape = CircleShape, color = Color(0xFFB3122B), shadowElevation = 12.dp, modifier = Modifier.fillMaxSize()) {\n",
    "                Surface(shape = CircleShape, color = Color(0xFFB3122B), shadowElevation = 12.dp, modifier = Modifier.fillMaxSize().graphicsLayer(scaleX = reactionPulse.value, scaleY = reactionPulse.value)) {\n",
    "reaction pulse rendering",
)

v = replace_once(
    v,
    "        ViewerVideo(item, controller, active, controlsVisible, onToggleUi, onVideoPosition)\n",
    "        ViewerVideo(item, controller, active, controlsVisible, onToggleUi, onVideoPosition, onZoomedChanged)\n",
    "viewer video zoom callback",
)

video_start = v.index("@Composable\nprivate fun ViewerVideo(")
video_end = v.index("\nprivate fun formatClock", video_start)
new_video = r'''@Composable
private fun ViewerVideo(
    item: MediaItem,
    controller: AppController,
    active: Boolean,
    controlsVisible: Boolean,
    onToggleUi: () -> Unit,
    onVideoPosition: (Long?) -> Unit,
    onZoomedChanged: (Boolean) -> Unit
) {
    val context = LocalContext.current
    val player = remember(item.uri) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(ExoMediaItem.fromUri(Uri.parse(item.uri)))
            repeatMode = Player.REPEAT_MODE_ONE
            setSeekParameters(SeekParameters.EXACT)
            prepare()
        }
    }
    var positionMs by remember(item.id) { mutableLongStateOf(0L) }
    var durationMs by remember(item.id) { mutableLongStateOf(1L) }
    var scrubbing by remember(item.id) { mutableStateOf(false) }
    var scrubValue by remember(item.id) { mutableFloatStateOf(0f) }
    var isPlaying by remember(item.id) { mutableStateOf(false) }
    var wasPlayingBeforeScrub by remember(item.id) { mutableStateOf(false) }
    var scale by remember(item.id) { mutableFloatStateOf(1f) }
    var offset by remember(item.id) { mutableStateOf(Offset.Zero) }
    var boxSize by remember(item.id) { mutableStateOf(IntSize.Zero) }
    var zoomSessionStart by remember(item.id) { mutableStateOf<Long?>(null) }

    fun clampOffset(candidate: Offset, scaleValue: Float): Offset {
        if (scaleValue <= 1f || boxSize == IntSize.Zero) return Offset.Zero
        val maxX = boxSize.width * (scaleValue - 1f) / 2f
        val maxY = boxSize.height * (scaleValue - 1f) / 2f
        return Offset(candidate.x.coerceIn(-maxX, maxX), candidate.y.coerceIn(-maxY, maxY))
    }

    fun beginZoom(now: Long = System.currentTimeMillis()) {
        if (zoomSessionStart == null) {
            zoomSessionStart = now
            controller.log(item.id, EventTypes.ZOOM_START, mediaPositionMs = player.currentPosition, at = now, details = "video")
            onZoomedChanged(true)
        }
    }

    fun endZoom(now: Long = System.currentTimeMillis()) {
        zoomSessionStart?.let { start ->
            controller.log(item.id, EventTypes.ZOOMED_DWELL, value = (now - start).coerceAtLeast(0L), mediaPositionMs = player.currentPosition, at = now, details = "video")
            controller.log(item.id, EventTypes.ZOOM_END, mediaPositionMs = player.currentPosition, at = now, details = "video")
        }
        zoomSessionStart = null
        onZoomedChanged(false)
    }

    LaunchedEffect(active) {
        if (active) player.play() else player.pause()
    }

    DisposableEffect(player, item.id) {
        var playingStartedAt: Long? = null
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(nowPlaying: Boolean) {
                isPlaying = nowPlaying
                val now = System.currentTimeMillis()
                if (nowPlaying) {
                    playingStartedAt = now
                    controller.log(item.id, EventTypes.VIDEO_PLAY, mediaPositionMs = player.currentPosition, at = now)
                } else {
                    playingStartedAt?.let { controller.log(item.id, EventTypes.VIDEO_WATCH_DWELL, value = now - it, mediaPositionMs = player.currentPosition, at = now) }
                    playingStartedAt = null
                    controller.log(item.id, EventTypes.VIDEO_PAUSE, mediaPositionMs = player.currentPosition, at = now)
                }
            }

            override fun onPositionDiscontinuity(oldPosition: Player.PositionInfo, newPosition: Player.PositionInfo, reason: Int) {
                val delta = newPosition.positionMs - oldPosition.positionMs
                if (reason == Player.DISCONTINUITY_REASON_SEEK) {
                    controller.log(item.id, EventTypes.VIDEO_SEEK, value = delta, mediaPositionMs = newPosition.positionMs)
                }
                if (delta < -1000L) controller.log(item.id, EventTypes.VIDEO_REPLAY, value = -delta, mediaPositionMs = newPosition.positionMs)
            }
        }
        player.addListener(listener)
        onDispose {
            val now = System.currentTimeMillis()
            playingStartedAt?.let { controller.log(item.id, EventTypes.VIDEO_WATCH_DWELL, value = now - it, mediaPositionMs = player.currentPosition, at = now) }
            zoomSessionStart?.let { start ->
                controller.log(item.id, EventTypes.ZOOMED_DWELL, value = (now - start).coerceAtLeast(0L), mediaPositionMs = player.currentPosition, at = now, details = "video")
                controller.log(item.id, EventTypes.ZOOM_END, mediaPositionMs = player.currentPosition, at = now, details = "video")
            }
            player.removeListener(listener)
            player.release()
        }
    }

    LaunchedEffect(player, active) {
        while (true) {
            if (active) {
                positionMs = player.currentPosition.coerceAtLeast(0L)
                durationMs = player.duration.takeIf { it > 0L } ?: 1L
                onVideoPosition(positionMs)
                if (!scrubbing) scrubValue = positionMs.toFloat()
            }
            delay(60)
        }
    }

    val zoomGesture = Modifier.pointerInput(item.id) {
        awaitEachGesture {
            awaitFirstDown(requireUnconsumed = false)
            var lastDistance: Float? = null
            var lastCentroid: Offset? = null
            var totalPan = 0f
            var lastScaleLogAt = 0L
            while (true) {
                val event = awaitPointerEvent()
                val pressed = event.changes.filter { it.pressed }
                if (pressed.isEmpty()) break
                if (pressed.size >= 2) {
                    val p0 = pressed[0].position
                    val p1 = pressed[1].position
                    val centroid = (p0 + p1) / 2f
                    val distance = (p0 - p1).getDistance().coerceAtLeast(1f)
                    if (lastDistance != null && lastCentroid != null) {
                        val nextScale = (scale * (distance / lastDistance!!)).coerceIn(1f, 8f)
                        val pan = centroid - lastCentroid!!
                        if (nextScale > 1.02f) beginZoom()
                        scale = nextScale
                        offset = clampOffset(offset + pan, nextScale)
                        totalPan += pan.getDistance()
                        val now = System.currentTimeMillis()
                        if (now - lastScaleLogAt >= 90L) {
                            controller.log(item.id, EventTypes.ZOOM_SCALE, value = (scale * 1000).roundToInt().toLong(), mediaPositionMs = player.currentPosition, x = centroid.x.toDouble(), y = centroid.y.toDouble(), at = now, details = "video")
                            lastScaleLogAt = now
                        }
                        if (scale <= 1.02f) {
                            scale = 1f
                            offset = Offset.Zero
                            endZoom(now)
                        }
                    }
                    lastDistance = distance
                    lastCentroid = centroid
                    pressed.forEach { it.consume() }
                } else if (scale > 1f && pressed.size == 1) {
                    val delta = pressed[0].positionChange()
                    offset = clampOffset(offset + delta, scale)
                    totalPan += delta.getDistance()
                    pressed[0].consume()
                    lastDistance = null
                    lastCentroid = null
                } else {
                    lastDistance = null
                    lastCentroid = null
                }
            }
            if (totalPan > 0f) {
                controller.log(item.id, EventTypes.PAN_DISTANCE, value = totalPan.roundToInt().toLong(), mediaPositionMs = player.currentPosition, details = "video")
                controller.log(item.id, EventTypes.PAN_POINT, mediaPositionMs = player.currentPosition, x = offset.x.toDouble(), y = offset.y.toDouble(), details = "video;scale=${"%.3f".format(Locale.US, scale)}")
            }
        }
    }

    Box(
        Modifier.fillMaxSize()
            .onSizeChanged { boxSize = it }
            .pointerInput(item.id) {
                detectTapGestures(
                    onTap = { onToggleUi() },
                    onDoubleTap = {
                        val now = System.currentTimeMillis()
                        if (scale > 1f) {
                            scale = 1f
                            offset = Offset.Zero
                            endZoom(now)
                        } else {
                            scale = 2.5f
                            beginZoom(now)
                            controller.log(item.id, EventTypes.ZOOM_SCALE, value = 2500L, mediaPositionMs = player.currentPosition, at = now, details = "video")
                        }
                    }
                )
            }
            .then(zoomGesture)
    ) {
        AndroidView(
            factory = { ctx ->
                PlayerView(ctx).apply {
                    useController = false
                    resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT
                    setShowBuffering(PlayerView.SHOW_BUFFERING_WHEN_PLAYING)
                    this.player = player
                }
            },
            update = { it.player = player; it.useController = false },
            modifier = Modifier.fillMaxSize().graphicsLayer(
                scaleX = scale,
                scaleY = scale,
                translationX = offset.x,
                translationY = offset.y
            )
        )

        if (controlsVisible && active) {
            Row(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().navigationBarsPadding().padding(start = 10.dp, end = 12.dp, bottom = 72.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(modifier = Modifier.size(58.dp), onClick = { if (player.isPlaying) player.pause() else player.play() }) {
                    Icon(if (isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow, contentDescription = if (isPlaying) "Pause" else "Play")
                }
                Slider(
                    value = scrubValue.coerceIn(0f, durationMs.toFloat().coerceAtLeast(1f)),
                    onValueChange = { value ->
                        val target = value.toLong().coerceIn(0L, durationMs)
                        if (!scrubbing) {
                            scrubbing = true
                            wasPlayingBeforeScrub = player.isPlaying
                            player.pause()
                            controller.log(item.id, EventTypes.VIDEO_SCRUB_START, mediaPositionMs = player.currentPosition)
                        }
                        scrubValue = value
                        positionMs = target
                        player.seekTo(target)
                        onVideoPosition(target)
                    },
                    onValueChangeFinished = {
                        val target = scrubValue.toLong().coerceIn(0L, durationMs)
                        player.seekTo(target)
                        controller.log(item.id, EventTypes.VIDEO_SCRUB_END, mediaPositionMs = target)
                        scrubbing = false
                        if (wasPlayingBeforeScrub) player.play()
                    },
                    valueRange = 0f..durationMs.toFloat().coerceAtLeast(1f),
                    modifier = Modifier.weight(1f)
                )
                Spacer(Modifier.width(8.dp))
                Text("${formatClock(if (scrubbing) scrubValue.toLong() else positionMs)} / ${formatClock(durationMs)}", fontSize = 11.sp, color = Color.White)
            }
        }
    }
}
'''
v = v[:video_start] + new_video + v[video_end:]
viewer_path.write_text(v)


# --- Album grouping/reordering fixes --------------------------------------
g = gallery_path.read_text()
g = replace_once(
    g,
    "        val centralDrop = abs(dropPoint.x - targetBounds.center.x) < targetBounds.width * 0.34f && abs(dropPoint.y - targetBounds.center.y) < targetBounds.height * 0.34f\n",
    "        val centralDrop = abs(dropPoint.x - targetBounds.center.x) < targetBounds.width * 0.46f && abs(dropPoint.y - targetBounds.center.y) < targetBounds.height * 0.46f\n",
    "album group drop target",
)
g = replace_once(
    g,
    "                if (id.isNotBlank()) {\n                    controller.log(null, EventTypes.ALBUM_GROUP_CREATE, details = \"$sourceRoot+$targetRoot->$id\")\n                    renameGroupId = id\n                    renameText = \"New group\"\n                }\n",
    "                if (id.isNotBlank()) {\n                    controller.log(null, EventTypes.ALBUM_GROUP_CREATE, details = \"$sourceRoot+$targetRoot->$id\")\n                }\n",
    "album grouping immediate commit",
)
gallery_path.write_text(g)


a = organizer_path.read_text()
old_create_group = '''    fun createGroup(prefs: SharedPreferences, state: AlbumLayoutState, a: String, b: String): String {
        if (a == b) return ""
        removeAlbumEverywhere(state, a)
        removeAlbumEverywhere(state, b)
        val id = UUID.randomUUID().toString().take(8)
        val group = AlbumGroup(id, "New group", mutableListOf(a, b))
        state.groups[id] = group
        state.order += "g:$id"
        save(prefs, state)
        return id
    }
'''
new_create_group = '''    fun createGroup(prefs: SharedPreferences, state: AlbumLayoutState, a: String, b: String): String {
        if (a == b) return ""
        val aIndex = state.order.indexOf("a:$a")
        val bIndex = state.order.indexOf("a:$b")
        val insertAt = listOf(aIndex, bIndex).filter { it >= 0 }.minOrNull() ?: state.order.size
        removeAlbumEverywhere(state, a)
        removeAlbumEverywhere(state, b)
        val id = UUID.randomUUID().toString().take(8)
        val group = AlbumGroup(id, "Group ${state.groups.size + 1}", mutableListOf(a, b))
        state.groups[id] = group
        state.order.add(insertAt.coerceIn(0, state.order.size), "g:$id")
        save(prefs, state)
        return id
    }
'''
a = replace_once(a, old_create_group, new_create_group, "album createGroup")
organizer_path.write_text(a)

print("Applied NeuronTap v0.5 field-test patch")
