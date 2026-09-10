from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/ViewerUi.kt"
s = p.read_text()
insert = s.find('\nprivate fun formatClock')
if insert < 0:
    raise RuntimeError('v7 video insertion point missing')

video = r'''
@Composable
private fun ViewerVideoV7(
    item: MediaItem,
    controller: AppController,
    active: Boolean,
    controlsVisible: Boolean,
    gesturesEnabled: Boolean,
    autoplayVideos: Boolean,
    loopVideos: Boolean,
    videosMuted: Boolean,
    onToggleUi: () -> Unit,
    onVideoPosition: (Long?) -> Unit,
    onZoomedChanged: (Boolean) -> Unit,
    onLibraryChanged: () -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    var appVisible by remember { mutableStateOf(lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) }
    val player = remember(item.uri) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(ExoMediaItem.fromUri(Uri.parse(item.uri)))
            repeatMode = if (loopVideos) Player.REPEAT_MODE_ONE else Player.REPEAT_MODE_OFF
            setSeekParameters(SeekParameters.CLOSEST_SYNC)
            volume = if (videosMuted) 0f else 1f
            prepare()
        }
    }
    var textureView by remember(item.id) { mutableStateOf<TextureView?>(null) }
    var aspectFrame by remember(item.id) { mutableStateOf<AspectRatioFrameLayout?>(null) }
    var positionMs by remember(item.id) { mutableLongStateOf(0L) }
    var durationMs by remember(item.id) { mutableLongStateOf(1L) }
    var scrubbing by remember(item.id) { mutableStateOf(false) }
    var scrubValue by remember(item.id) { mutableFloatStateOf(0f) }
    var isPlaying by remember(item.id) { mutableStateOf(false) }
    var wasPlayingBeforeScrub by remember(item.id) { mutableStateOf(false) }
    var previewBitmap by remember(item.id) { mutableStateOf<Bitmap?>(null) }
    var previewJob by remember(item.id) { mutableStateOf<Job?>(null) }
    val previewRetriever = remember(item.uri) {
        runCatching { MediaMetadataRetriever().apply { setDataSource(context, Uri.parse(item.uri)) } }.getOrNull()
    }

    var scale by remember(item.id) { mutableFloatStateOf(1f) }
    var offsetX by remember(item.id) { mutableFloatStateOf(0f) }
    var offsetY by remember(item.id) { mutableFloatStateOf(0f) }
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
            controller.log(item.id, EventTypes.ZOOM_START, mediaPositionMs = player.currentPosition, details = "video_v7", at = now)
            onZoomedChanged(true)
        }
    }
    fun endZoom(now: Long = System.currentTimeMillis()) {
        zoomSessionStart?.let { start ->
            controller.log(item.id, EventTypes.ZOOMED_DWELL, value = (now - start).coerceAtLeast(0L), mediaPositionMs = player.currentPosition, details = "video_v7", at = now)
            controller.log(item.id, EventTypes.ZOOM_END, mediaPositionMs = player.currentPosition, details = "video_v7", at = now)
        }
        zoomSessionStart = null
        onZoomedChanged(false)
    }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> appVisible = true
                Lifecycle.Event.ON_STOP -> appVisible = false
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    LaunchedEffect(loopVideos) { player.repeatMode = if (loopVideos) Player.REPEAT_MODE_ONE else Player.REPEAT_MODE_OFF }
    LaunchedEffect(videosMuted) { player.volume = if (videosMuted) 0f else 1f }
    LaunchedEffect(active, appVisible, autoplayVideos) {
        if (!active || !appVisible) player.pause() else if (autoplayVideos) player.play()
    }

    DisposableEffect(player, item.id) {
        var playingStartedAt: Long? = null
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(nowPlaying: Boolean) {
                isPlaying = nowPlaying
                val now = System.currentTimeMillis()
                if (nowPlaying) {
                    playingStartedAt = now
                    controller.log(item.id, EventTypes.VIDEO_PLAY, mediaPositionMs = player.currentPosition, at = now, details = "v7")
                } else {
                    playingStartedAt?.let { controller.log(item.id, EventTypes.VIDEO_WATCH_DWELL, value = now - it, mediaPositionMs = player.currentPosition, at = now) }
                    playingStartedAt = null
                    controller.log(item.id, EventTypes.VIDEO_PAUSE, mediaPositionMs = player.currentPosition, at = now, details = "v7")
                }
            }
            override fun onVideoSizeChanged(videoSize: androidx.media3.common.VideoSize) {
                if (videoSize.width > 0 && videoSize.height > 0) {
                    aspectFrame?.setAspectRatio(videoSize.width.toFloat() * videoSize.pixelWidthHeightRatio / videoSize.height.toFloat())
                }
            }
            override fun onPositionDiscontinuity(oldPosition: Player.PositionInfo, newPosition: Player.PositionInfo, reason: Int) {
                val delta = newPosition.positionMs - oldPosition.positionMs
                if (reason == Player.DISCONTINUITY_REASON_SEEK) controller.log(item.id, EventTypes.VIDEO_SEEK, value = delta, mediaPositionMs = newPosition.positionMs)
                if (delta < -1000L) controller.log(item.id, EventTypes.VIDEO_REPLAY, value = -delta, mediaPositionMs = newPosition.positionMs)
            }
        }
        player.addListener(listener)
        onDispose {
            val now = System.currentTimeMillis()
            playingStartedAt?.let { controller.log(item.id, EventTypes.VIDEO_WATCH_DWELL, value = now - it, mediaPositionMs = player.currentPosition, at = now) }
            zoomSessionStart?.let { start ->
                controller.log(item.id, EventTypes.ZOOMED_DWELL, value = (now - start).coerceAtLeast(0L), mediaPositionMs = player.currentPosition, details = "video_v7", at = now)
            }
            previewJob?.cancel()
            previewBitmap?.recycle(); previewBitmap = null
            runCatching { previewRetriever?.release() }
            textureView?.let { runCatching { player.clearVideoTextureView(it) } }
            player.removeListener(listener)
            player.release()
        }
    }

    LaunchedEffect(player, active) {
        while (true) {
            if (active) {
                positionMs = player.currentPosition.coerceAtLeast(0L)
                durationMs = player.duration.takeIf { it > 0L } ?: 1L
                onVideoPosition(if (scrubbing) scrubValue.toLong() else positionMs)
                if (!scrubbing) scrubValue = positionMs.toFloat()
            }
            delay(33)
        }
    }

    val zoomGesture = if (!gesturesEnabled) Modifier else Modifier.pointerInput(item.id) {
        awaitEachGesture {
            awaitFirstDown(requireUnconsumed = true)
            var lastDistance: Float? = null
            var lastCentroid: Offset? = null
            var totalPan = 0f
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
                        val next = clampOffset(Offset(offsetX + pan.x, offsetY + pan.y), nextScale)
                        scale = nextScale; offsetX = next.x; offsetY = next.y; totalPan += pan.getDistance()
                        controller.log(item.id, EventTypes.ZOOM_SCALE, value = (scale * 1000).roundToInt().toLong(), mediaPositionMs = player.currentPosition, x = centroid.x.toDouble(), y = centroid.y.toDouble(), details = "video_v7")
                        if (scale <= 1.02f) { scale = 1f; offsetX = 0f; offsetY = 0f; endZoom() }
                    }
                    lastDistance = distance; lastCentroid = centroid
                    pressed.forEach { it.consume() }
                } else if (scale > 1f && pressed.size == 1) {
                    val delta = pressed[0].positionChange()
                    val next = clampOffset(Offset(offsetX + delta.x, offsetY + delta.y), scale)
                    offsetX = next.x; offsetY = next.y; totalPan += delta.getDistance()
                    pressed[0].consume(); lastDistance = null; lastCentroid = null
                } else { lastDistance = null; lastCentroid = null }
            }
            if (totalPan > 0f) controller.log(item.id, EventTypes.PAN_DISTANCE, value = totalPan.roundToInt().toLong(), mediaPositionMs = player.currentPosition, details = "video_v7")
        }
    }

    Box(
        Modifier.fillMaxSize().onSizeChanged { boxSize = it }
            .pointerInput(item.id, gesturesEnabled) {
                if (gesturesEnabled) detectTapGestures(
                    onTap = { onToggleUi() },
                    onDoubleTap = { tap ->
                        val target = if (scale > 1.05f) 1f else 2.5f
                        val center = Offset(boxSize.width / 2f, boxSize.height / 2f)
                        val focal = if (target <= 1f) Offset.Zero else clampOffset((center - tap) * (target - 1f), target)
                        controller.log(item.id, EventTypes.DOUBLE_TAP_FOCUS, value = (target * 1000).roundToInt().toLong(), mediaPositionMs = player.currentPosition, x = tap.x.toDouble(), y = tap.y.toDouble(), details = "video_v7;w=${boxSize.width};h=${boxSize.height}")
                        if (target > 1f) beginZoom()
                        scope.launch {
                            val sx = offsetX; val sy = offsetY; val ss = scale; val progress = Animatable(0f)
                            progress.animateTo(1f, tween(190)) {
                                scale = ss + (target - ss) * value
                                offsetX = sx + (focal.x - sx) * value
                                offsetY = sy + (focal.y - sy) * value
                            }
                            scale = target; offsetX = focal.x; offsetY = focal.y
                            if (target <= 1f) endZoom()
                        }
                    }
                )
            }.then(zoomGesture)
    ) {
        AndroidView(
            factory = { ctx ->
                AspectRatioFrameLayout(ctx).also { frame ->
                    frame.resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT
                    val tv = TextureView(ctx)
                    frame.addView(tv, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
                    textureView = tv; aspectFrame = frame; player.setVideoTextureView(tv)
                }
            },
            modifier = Modifier.fillMaxSize().graphicsLayer(scaleX = scale, scaleY = scale, translationX = offsetX, translationY = offsetY)
        )

        if (scrubbing) previewBitmap?.let { bitmap ->
            Image(bitmap.asImageBitmap(), contentDescription = "Scrub preview", modifier = Modifier.fillMaxSize().graphicsLayer(scaleX = scale, scaleY = scale, translationX = offsetX, translationY = offsetY), contentScale = ContentScale.Fit)
        }

        if (controlsVisible && active) {
            Row(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().background(Color.Black.copy(alpha = 0.84f)).navigationBarsPadding().padding(start = 6.dp, end = 10.dp, bottom = 72.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(modifier = Modifier.size(50.dp), onClick = { if (player.isPlaying) player.pause() else player.play() }) {
                    Icon(if (isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow, if (isPlaying) "Pause" else "Play", tint = Color.White)
                }
                IconButton(modifier = Modifier.size(48.dp), onClick = {
                    val at = player.currentPosition.coerceAtLeast(0L)
                    val captured = textureView?.bitmap
                    scope.launch {
                        val exported = if (captured != null) saveBitmapFrameV7(context, item, at, captured) else exportVideoFrame(context, item, at)
                        if (exported != null) {
                            val (uri, name, savedAt) = exported
                            controller.db.upsertMedia("mediastore:Pictures/NeuronTap Frames", uri.toString(), name, "image/png", 0L, savedAt)
                            controller.log(item.id, EventTypes.VIDEO_FRAME_EXPORT, mediaPositionMs = at, details = "frame=$uri;display_capture=${captured != null}")
                            onLibraryChanged()
                            Toast.makeText(context, "Frame saved", Toast.LENGTH_SHORT).show()
                        } else Toast.makeText(context, "Frame export failed", Toast.LENGTH_SHORT).show()
                    }
                }) { Icon(Icons.Default.PhotoCamera, "Save current frame", tint = Color.White) }
                Slider(
                    value = scrubValue.coerceIn(0f, durationMs.toFloat().coerceAtLeast(1f)),
                    onValueChange = { value ->
                        val target = value.toLong().coerceIn(0L, durationMs)
                        if (!scrubbing) {
                            scrubbing = true; wasPlayingBeforeScrub = player.isPlaying; player.pause(); player.setSeekParameters(SeekParameters.CLOSEST_SYNC)
                            controller.log(item.id, EventTypes.VIDEO_SCRUB_START, mediaPositionMs = player.currentPosition)
                        }
                        scrubValue = target.toFloat(); positionMs = target; player.seekTo(target); onVideoPosition(target)
                        previewJob?.cancel()
                        val retriever = previewRetriever
                        if (retriever != null) previewJob = scope.launch {
                            val frame = withContext(Dispatchers.IO) {
                                runCatching { synchronized(retriever) { retriever.getFrameAtTime(target * 1000L, MediaMetadataRetriever.OPTION_CLOSEST_SYNC) } }.getOrNull()
                            }
                            if (scrubbing && kotlin.math.abs(scrubValue - target.toFloat()) < 700f && frame != null) {
                                val old = previewBitmap; previewBitmap = frame; if (old !== frame) old?.recycle()
                            } else frame?.recycle()
                        }
                    },
                    onValueChangeFinished = {
                        val target = scrubValue.toLong().coerceIn(0L, durationMs)
                        player.seekTo(target)
                        controller.log(item.id, EventTypes.VIDEO_SCRUB_END, mediaPositionMs = target)
                        scrubbing = false; previewJob?.cancel(); previewJob = null; previewBitmap?.recycle(); previewBitmap = null
                        if (wasPlayingBeforeScrub) player.play()
                    },
                    valueRange = 0f..durationMs.toFloat().coerceAtLeast(1f),
                    modifier = Modifier.weight(1f)
                )
                Text("${formatClock(if (scrubbing) scrubValue.toLong() else positionMs)} / ${formatClock(durationMs)}", fontSize = 10.sp, color = Color.White)
            }
        }
    }
}

private suspend fun saveBitmapFrameV7(context: android.content.Context, item: MediaItem, positionMs: Long, bitmap: Bitmap): Triple<Uri, String, Long>? = withContext(Dispatchers.IO) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return@withContext null
    runCatching {
        val now = System.currentTimeMillis()
        val base = item.name.substringBeforeLast('.').replace(Regex("[^A-Za-z0-9_-]+"), "_").take(42).ifBlank { "video" }
        val name = "${base}_frame_${positionMs}ms.png"
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, name)
            put(MediaStore.Images.Media.MIME_TYPE, "image/png")
            put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/NeuronTap Frames")
            put(MediaStore.Images.Media.IS_PENDING, 1)
        }
        val uri = context.contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values) ?: return@runCatching null
        val wrote = context.contentResolver.openOutputStream(uri)?.use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) } ?: false
        bitmap.recycle()
        if (!wrote) { context.contentResolver.delete(uri, null, null); return@runCatching null }
        context.contentResolver.update(uri, ContentValues().apply { put(MediaStore.Images.Media.IS_PENDING, 0) }, null, null)
        Triple(uri, name, now)
    }.getOrNull()
}

'''
s = s[:insert] + video + s[insert:]
p.write_text(s)
print('Applied v7 video')
