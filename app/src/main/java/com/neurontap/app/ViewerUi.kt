package com.neurontap.app

import android.app.Activity
import android.content.Intent
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.IntentSenderRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.positionChange
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
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
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

@Composable
fun ViewerScreen(
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
    val scope = rememberCoroutineScope()
    val initialIndex = remember(items, startMediaId) { items.indexOfFirst { it.id == startMediaId }.coerceAtLeast(0) }
    val pagerState = rememberPagerState(initialPage = initialIndex, pageCount = { items.size })
    var controlsVisible by remember { mutableStateOf(true) }
    var trackedPage by remember { mutableIntStateOf(-1) }
    var trackedStartMs by remember { mutableLongStateOf(0L) }
    var videoPositionMs by remember { mutableStateOf<Long?>(null) }
    var favoriteIds by remember(items) { mutableStateOf(items.filter { it.favorite }.map { it.id }.toSet()) }
    var dimensions by remember { mutableStateOf<String?>(null) }
    var showDeleteDialog by remember { mutableStateOf(false) }
    var showInfoDialog by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var pendingDeleteId by remember { mutableStateOf<Long?>(null) }

    val current = items[pagerState.currentPage]

    BackHandler { onClose() }

    LaunchedEffect(pagerState.currentPage) {
        val now = System.currentTimeMillis()
        if (trackedPage in items.indices && trackedStartMs > 0L) {
            controller.log(items[trackedPage].id, EventTypes.VIEW_DWELL, value = now - trackedStartMs, at = now)
        }
        trackedPage = pagerState.currentPage
        trackedStartMs = now
        videoPositionMs = null
        controller.log(current.id, EventTypes.VIEW_START, at = now)
        dimensions = mediaDimensions(context, current)
    }

    DisposableEffect(Unit) {
        onDispose {
            val now = System.currentTimeMillis()
            if (trackedPage in items.indices && trackedStartMs > 0L) {
                controller.log(items[trackedPage].id, EventTypes.VIEW_DWELL, value = now - trackedStartMs, at = now)
            }
        }
    }

    val deleteLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            pendingDeleteId?.let { controller.db.deleteMedia(it) }
            pendingDeleteId = null
            onLibraryChanged()
            onClose()
        } else {
            pendingDeleteId = null
            message = "Delete cancelled"
        }
    }

    fun share(item: MediaItem) {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = item.mime
            putExtra(Intent.EXTRA_STREAM, Uri.parse(item.uri))
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(intent, "Share media"))
    }

    fun delete(item: MediaItem) {
        val uri = Uri.parse(item.uri)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && item.uri.startsWith("content://media/")) {
            runCatching {
                pendingDeleteId = item.id
                val request = MediaStore.createDeleteRequest(context.contentResolver, listOf(uri))
                deleteLauncher.launch(IntentSenderRequest.Builder(request.intentSender).build())
            }.onFailure {
                pendingDeleteId = null
                message = "Android blocked deletion of this item"
            }
        } else {
            val deleted = runCatching { context.contentResolver.delete(uri, null, null) > 0 }.getOrDefault(false)
            if (deleted) {
                controller.db.deleteMedia(item.id)
                onLibraryChanged()
                onClose()
            } else {
                message = "Android blocked deletion of this item"
            }
        }
    }

    if (showDeleteDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteDialog = false },
            title = { Text("Delete this file?") },
            text = { Text(current.name) },
            confirmButton = { TextButton(onClick = { showDeleteDialog = false; delete(current) }) { Text("Delete") } },
            dismissButton = { TextButton(onClick = { showDeleteDialog = false }) { Text("Cancel") } }
        )
    }

    if (showInfoDialog) {
        AlertDialog(
            onDismissRequest = { showInfoDialog = false },
            title = { Text(current.name) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Album: ${albumLabel(current.rootUri)}")
                    Text("Type: ${current.mime}")
                    Text("Size: ${formatBytes(current.size)}")
                    dimensions?.let { Text("Dimensions: $it") }
                    Text("Modified: ${formatMediaDate(current.modified)}")
                    Text(current.uri, color = Color.Gray)
                    message?.let { Text(it) }
                }
            },
            confirmButton = { TextButton(onClick = { showInfoDialog = false }) { Text("Done") } },
            dismissButton = {
                TextButton(onClick = {
                    val (inference, item) = controller.confirmFinish()
                    message = item?.let { "Finish logged · likely ${it.name} (${(inference.confidence * 100).toInt()}%)" } ?: "Finish logged"
                }) { Text("Log finish") }
            }
        )
    }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        HorizontalPager(state = pagerState, modifier = Modifier.fillMaxSize(), beyondViewportPageCount = 1) { page ->
            val item = items[page]
            MediaViewerPane(
                item = item,
                controller = controller,
                onToggleUi = { controlsVisible = !controlsVisible },
                onVideoPosition = { pos -> if (page == pagerState.currentPage) videoPositionMs = pos }
            )
        }

        if (controlsVisible) {
            Column(
                Modifier.align(Alignment.TopCenter).fillMaxWidth().background(Color.Black.copy(alpha = 0.84f)).padding(horizontal = 8.dp, vertical = 8.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onClose) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") }
                    Text("${pagerState.currentPage + 1}/${items.size} · ${current.name}", maxLines = 1, modifier = Modifier.weight(1f))
                }
                Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(formatMediaDate(current.modified), color = Color.LightGray)
                    Text(dimensions ?: "", color = Color.LightGray)
                }
            }

            Row(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().background(Color.Black.copy(alpha = 0.86f)).padding(vertical = 16.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = {
                    val next = current.id !in favoriteIds
                    controller.db.setFavorite(current.id, next)
                    favoriteIds = if (next) favoriteIds + current.id else favoriteIds - current.id
                    onLibraryChanged()
                }) {
                    Icon(if (current.id in favoriteIds) Icons.Default.Favorite else Icons.Default.FavoriteBorder, contentDescription = "Favorite", tint = if (current.id in favoriteIds) Color(0xFFFF4D67) else Color.White, modifier = Modifier.size(32.dp))
                }
                IconButton(onClick = { share(current) }) { Icon(Icons.Default.Share, contentDescription = "Share", modifier = Modifier.size(30.dp)) }
                IconButton(onClick = { showDeleteDialog = true }) { Icon(Icons.Default.Delete, contentDescription = "Delete", modifier = Modifier.size(30.dp)) }
                IconButton(onClick = { showInfoDialog = true }) { Icon(Icons.Default.MoreVert, contentDescription = "More", modifier = Modifier.size(30.dp)) }
            }
        }

        FloatingReactionButton(
            controller = controller,
            item = current,
            viewStartMs = trackedStartMs,
            videoPositionMs = videoPositionMs
        )
    }
}

@Composable
private fun MediaViewerPane(item: MediaItem, controller: AppController, onToggleUi: () -> Unit, onVideoPosition: (Long?) -> Unit) {
    if (item.isVideo) ViewerVideo(item, controller, onToggleUi, onVideoPosition)
    else ZoomableImage(item, onToggleUi) { onVideoPosition(null) }
}

@Composable
private fun ZoomableImage(item: MediaItem, onToggleUi: () -> Unit, onReady: () -> Unit) {
    var scale by remember(item.id) { mutableFloatStateOf(1f) }
    var offset by remember(item.id) { mutableStateOf(Offset.Zero) }
    var boxSize by remember(item.id) { mutableStateOf(IntSize.Zero) }
    LaunchedEffect(item.id) { onReady() }

    fun clampOffset(candidate: Offset, scaleValue: Float): Offset {
        if (scaleValue <= 1f || boxSize == IntSize.Zero) return Offset.Zero
        val maxX = boxSize.width * (scaleValue - 1f) / 2f
        val maxY = boxSize.height * (scaleValue - 1f) / 2f
        return Offset(candidate.x.coerceIn(-maxX, maxX), candidate.y.coerceIn(-maxY, maxY))
    }

    val gestureModifier = Modifier.pointerInput(item.id) {
        awaitEachGesture {
            awaitFirstDown(requireUnconsumed = false)
            var lastDistance: Float? = null
            var lastCentroid: Offset? = null
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
                        scale = nextScale
                        offset = clampOffset(offset + pan, nextScale)
                    }
                    lastDistance = distance
                    lastCentroid = centroid
                    pressed.forEach { it.consume() }
                } else if (scale > 1f && pressed.size == 1) {
                    val delta = pressed[0].positionChange()
                    offset = clampOffset(offset + delta, scale)
                    pressed[0].consume()
                    lastDistance = null
                    lastCentroid = null
                } else {
                    lastDistance = null
                    lastCentroid = null
                }
            }
        }
    }

    Box(
        Modifier.fillMaxSize().onSizeChanged { boxSize = it }
            .pointerInput(item.id) {
                detectTapGestures(
                    onTap = { onToggleUi() },
                    onDoubleTap = {
                        if (scale > 1f) { scale = 1f; offset = Offset.Zero }
                        else scale = 2.5f
                    }
                )
            }
            .then(gestureModifier),
        contentAlignment = Alignment.Center
    ) {
        AsyncImage(
            model = Uri.parse(item.uri),
            contentDescription = item.name,
            modifier = Modifier.fillMaxSize().graphicsLayer(scaleX = scale, scaleY = scale, translationX = offset.x, translationY = offset.y),
            contentScale = ContentScale.Fit
        )
    }
}

@Composable
private fun ViewerVideo(item: MediaItem, controller: AppController, onToggleUi: () -> Unit, onVideoPosition: (Long?) -> Unit) {
    val context = LocalContext.current
    val player = remember(item.uri) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(ExoMediaItem.fromUri(Uri.parse(item.uri)))
            prepare()
        }
    }
    DisposableEffect(player, item.id) {
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                controller.log(item.id, if (isPlaying) EventTypes.VIDEO_PLAY else EventTypes.VIDEO_PAUSE, mediaPositionMs = player.currentPosition)
            }
            override fun onPositionDiscontinuity(oldPosition: Player.PositionInfo, newPosition: Player.PositionInfo, reason: Int) {
                if (reason == Player.DISCONTINUITY_REASON_SEEK) {
                    controller.log(item.id, EventTypes.VIDEO_SEEK, value = newPosition.positionMs - oldPosition.positionMs, mediaPositionMs = newPosition.positionMs)
                }
            }
        }
        player.addListener(listener)
        onDispose { player.removeListener(listener); player.release() }
    }
    LaunchedEffect(player) { while (true) { onVideoPosition(player.currentPosition); delay(250) } }
    Box(Modifier.fillMaxSize().pointerInput(item.id) { detectTapGestures(onTap = { onToggleUi() }) }) {
        AndroidView(factory = { ctx -> PlayerView(ctx).apply { this.player = player } }, update = { it.player = player }, modifier = Modifier.fillMaxSize())
    }
}

@Composable
private fun FloatingReactionButton(controller: AppController, item: MediaItem, viewStartMs: Long, videoPositionMs: Long?) {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("neurontap", 0) }
    val density = LocalDensity.current
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val minPx = with(density) { 56.dp.toPx() }
        val maxPx = with(density) { 132.dp.toPx() }
        val defaultPx = with(density) { 82.dp.toPx() }
        var sizePx by remember { mutableFloatStateOf(prefs.getFloat("reaction_size_px", defaultPx).coerceIn(minPx, maxPx)) }
        var xPx by remember { mutableFloatStateOf(prefs.getFloat("reaction_x_px", Float.NaN)) }
        var yPx by remember { mutableFloatStateOf(prefs.getFloat("reaction_y_px", Float.NaN)) }
        var firstReactionLogged by remember(item.id, viewStartMs) { mutableStateOf(false) }

        val maxW = constraints.maxWidth.toFloat()
        val maxH = constraints.maxHeight.toFloat()
        if (xPx.isNaN()) xPx = ((maxW - sizePx) / 2f).coerceAtLeast(0f)
        if (yPx.isNaN()) yPx = (maxH - sizePx - with(density) { 90.dp.toPx() }).coerceAtLeast(0f)

        LaunchedEffect(maxW, maxH, sizePx) {
            xPx = xPx.coerceIn(0f, (maxW - sizePx).coerceAtLeast(0f))
            yPx = yPx.coerceIn(0f, (maxH - sizePx).coerceAtLeast(0f))
        }

        val transformState = rememberTransformableState { zoomChange, panChange, _ ->
            val nextSize = (sizePx * zoomChange).coerceIn(minPx, maxPx)
            sizePx = nextSize
            xPx = (xPx + panChange.x).coerceIn(0f, (maxW - nextSize).coerceAtLeast(0f))
            yPx = (yPx + panChange.y).coerceIn(0f, (maxH - nextSize).coerceAtLeast(0f))
            prefs.edit().putFloat("reaction_size_px", sizePx).putFloat("reaction_x_px", xPx).putFloat("reaction_y_px", yPx).apply()
        }

        Box(
            Modifier
                .offset { IntOffset(xPx.roundToInt(), yPx.roundToInt()) }
                .size(with(density) { sizePx.toDp() })
                .pointerInput(item.id, viewStartMs, videoPositionMs) {
                    detectTapGestures(onPress = {
                        val down = System.currentTimeMillis()
                        val released = tryAwaitRelease()
                        if (released) {
                            controller.log(item.id, EventTypes.REACTION_DOWN, mediaPositionMs = videoPositionMs, at = down)
                            if (!firstReactionLogged && viewStartMs > 0L) {
                                firstReactionLogged = true
                                controller.log(item.id, EventTypes.FIRST_TAP_LATENCY, value = down - viewStartMs, mediaPositionMs = videoPositionMs, at = down)
                            }
                            val up = System.currentTimeMillis()
                            controller.log(item.id, EventTypes.REACTION_UP, value = up - down, mediaPositionMs = videoPositionMs, at = up)
                        }
                    })
                }
                .transformable(transformState),
            contentAlignment = Alignment.Center
        ) {
            Surface(shape = CircleShape, color = Color(0xFFD31E35), shadowElevation = 10.dp, modifier = Modifier.fillMaxSize()) {
                Box(contentAlignment = Alignment.Center) {
                    Text("❤️‍🔥", fontSize = with(density) { (sizePx * 0.40f).toSp() })
                }
            }
        }
    }
}

private suspend fun mediaDimensions(context: android.content.Context, item: MediaItem): String? = withContext(Dispatchers.IO) {
    runCatching {
        val uri = Uri.parse(item.uri)
        if (item.isVideo) {
            val retriever = MediaMetadataRetriever()
            try {
                retriever.setDataSource(context, uri)
                val width = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)?.toIntOrNull()
                val height = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)?.toIntOrNull()
                if (width != null && height != null) "$width × $height" else null
            } finally {
                retriever.release()
            }
        } else {
            val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, options) }
            if (options.outWidth > 0 && options.outHeight > 0) "${options.outWidth} × ${options.outHeight}" else null
        }
    }.getOrNull()
}

private fun formatMediaDate(ms: Long): String {
    if (ms <= 0L) return "Unknown date"
    return SimpleDateFormat("MMM d, yyyy · h:mm a", Locale.getDefault()).format(Date(ms))
}

private fun formatBytes(bytes: Long): String {
    if (bytes < 1024L) return "$bytes B"
    val kb = bytes / 1024.0
    if (kb < 1024.0) return String.format(Locale.US, "%.1f KB", kb)
    val mb = kb / 1024.0
    if (mb < 1024.0) return String.format(Locale.US, "%.1f MB", mb)
    return String.format(Locale.US, "%.2f GB", mb / 1024.0)
}
