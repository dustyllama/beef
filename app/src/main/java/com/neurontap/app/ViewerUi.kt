package com.neurontap.app

import android.app.Activity
import android.content.Intent
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.IntentSenderRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Slider
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
import androidx.compose.runtime.rememberUpdatedState
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
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalViewConfiguration
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem as ExoMediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import coil.compose.AsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.abs
import kotlin.math.hypot
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
    val prefs = remember { context.getSharedPreferences("neurontap", 0) }
    val density = LocalDensity.current
    val touchSlop = LocalViewConfiguration.current.touchSlop
    val orientation = LocalConfiguration.current.orientation
    val initialIndex = remember(items, startMediaId) { items.indexOfFirst { it.id == startMediaId }.coerceAtLeast(0) }
    val pagerState = rememberPagerState(initialPage = initialIndex, pageCount = { items.size })

    var controlsVisible by remember { mutableStateOf(true) }
    var declarationDrawerOpen by remember { mutableStateOf(false) }
    var trackedPage by remember { mutableIntStateOf(-1) }
    var trackedStartMs by remember { mutableLongStateOf(0L) }
    var videoPositionMs by remember { mutableStateOf<Long?>(null) }
    var favoriteIds by remember(items) { mutableStateOf(items.filter { it.favorite }.map { it.id }.toSet()) }
    var dimensions by remember { mutableStateOf<String?>(null) }
    var currentZoomed by remember { mutableStateOf(false) }
    var showDeleteDialog by remember { mutableStateOf(false) }
    var showInfoDialog by remember { mutableStateOf(false) }
    var pendingDeleteId by remember { mutableStateOf<Long?>(null) }
    var toastMessage by remember { mutableStateOf<String?>(null) }
    var lastSpiritualMs by remember { mutableLongStateOf(prefs.getLong("last_spiritual_coom_ms", 0L)) }
    var spiritualRemainingMs by remember { mutableLongStateOf(0L) }

    val current = items[pagerState.currentPage.coerceIn(items.indices)]
    val latestVideoPosition by rememberUpdatedState(videoPositionMs)
    val latestViewStart by rememberUpdatedState(trackedStartMs)

    LaunchedEffect(toastMessage) {
        toastMessage?.let { Toast.makeText(context, it, Toast.LENGTH_SHORT).show(); toastMessage = null }
    }

    LaunchedEffect(declarationDrawerOpen, lastSpiritualMs) {
        while (declarationDrawerOpen) {
            spiritualRemainingMs = (180_000L - (System.currentTimeMillis() - lastSpiritualMs)).coerceAtLeast(0L)
            delay(500)
        }
    }

    BackHandler {
        if (declarationDrawerOpen) {
            declarationDrawerOpen = false
            controller.log(current.id, EventTypes.DECLARATION_DRAWER_CLOSE, mediaPositionMs = videoPositionMs)
        } else onClose()
    }

    LaunchedEffect(pagerState.currentPage) {
        val now = System.currentTimeMillis()
        if (trackedPage in items.indices && trackedStartMs > 0L) {
            val previous = items[trackedPage]
            controller.log(previous.id, EventTypes.VIEW_DWELL, value = now - trackedStartMs, at = now)
            controller.log(previous.id, EventTypes.VIEW_END, at = now)
            if (trackedPage != pagerState.currentPage) controller.log(current.id, EventTypes.MEDIA_SWIPE, details = "${previous.id}->${current.id}", at = now)
        }
        trackedPage = pagerState.currentPage
        trackedStartMs = now
        videoPositionMs = null
        currentZoomed = false
        declarationDrawerOpen = false
        controller.log(current.id, EventTypes.VIEW_START, details = "index=${pagerState.currentPage};count=${items.size}", at = now)
        dimensions = mediaDimensions(context, current)
    }

    LaunchedEffect(current.id, orientation) {
        controller.log(current.id, EventTypes.ORIENTATION, value = orientation.toLong(), details = if (orientation == 2) "landscape" else "portrait")
    }

    DisposableEffect(Unit) {
        onDispose {
            val now = System.currentTimeMillis()
            if (trackedPage in items.indices && trackedStartMs > 0L) {
                controller.log(items[trackedPage].id, EventTypes.VIEW_DWELL, value = now - trackedStartMs, at = now)
                controller.log(items[trackedPage].id, EventTypes.VIEW_END, at = now)
            }
        }
    }

    val deleteLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            pendingDeleteId?.let { controller.db.markMediaDeleted(it) }
            pendingDeleteId = null
            onLibraryChanged()
            onClose()
        } else {
            pendingDeleteId = null
            toastMessage = "Delete cancelled"
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
            }.onFailure { pendingDeleteId = null; toastMessage = "Android blocked deletion of this item" }
        } else {
            val deleted = runCatching { context.contentResolver.delete(uri, null, null) > 0 }.getOrDefault(false)
            if (deleted) {
                controller.db.markMediaDeleted(item.id)
                onLibraryChanged(); onClose()
            } else toastMessage = "Android blocked deletion of this item"
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
                }
            },
            confirmButton = { TextButton(onClick = { showInfoDialog = false }) { Text("Done") } }
        )
    }

    BoxWithConstraints(Modifier.fillMaxSize().background(Color.Black)) {
        val maxW = constraints.maxWidth.toFloat()
        val maxH = constraints.maxHeight.toFloat()
        val minButtonPx = with(density) { 48.dp.toPx() }
        val maxButtonPx = with(density) { 168.dp.toPx() }
        val defaultButtonPx = with(density) { 76.dp.toPx() }
        var reactionSizePx by remember { mutableFloatStateOf(prefs.getFloat("reaction_size_px", defaultButtonPx).coerceIn(minButtonPx, maxButtonPx)) }
        var reactionXPx by remember { mutableFloatStateOf(prefs.getFloat("reaction_x_px", Float.NaN)) }
        var reactionYPx by remember { mutableFloatStateOf(prefs.getFloat("reaction_y_px", Float.NaN)) }
        var firstReactionLogged by remember(current.id, trackedStartMs) { mutableStateOf(false) }

        if (reactionXPx.isNaN()) reactionXPx = ((maxW - reactionSizePx) / 2f).coerceAtLeast(0f)
        if (reactionYPx.isNaN()) reactionYPx = (maxH - reactionSizePx - with(density) { 112.dp.toPx() }).coerceAtLeast(0f)

        LaunchedEffect(maxW, maxH, reactionSizePx) {
            reactionXPx = reactionXPx.coerceIn(0f, (maxW - reactionSizePx).coerceAtLeast(0f))
            reactionYPx = reactionYPx.coerceIn(0f, (maxH - reactionSizePx).coerceAtLeast(0f))
        }

        fun insideButton(p: Offset): Boolean = p.x in reactionXPx..(reactionXPx + reactionSizePx) && p.y in reactionYPx..(reactionYPx + reactionSizePx)

        val reactionGesture = Modifier.pointerInput(current.id, maxW, maxH) {
            awaitEachGesture {
                val first = awaitFirstDown(requireUnconsumed = false)
                if (!insideButton(first.position)) {
                    while (true) {
                        val event = awaitPointerEvent()
                        if (event.changes.none { it.pressed }) break
                    }
                    return@awaitEachGesture
                }

                val downAt = System.currentTimeMillis()
                val downPosition = first.position
                var previousOneFinger = first.position
                var lastTwoFingerDistance: Float? = null
                var movedPx = 0f
                var resized = false
                var consumedMovement = false
                var finalPosition = first.position

                while (true) {
                    val event = awaitPointerEvent()
                    val pressed = event.changes.filter { it.pressed }
                    if (pressed.isEmpty()) break
                    finalPosition = pressed.first().position

                    if (pressed.size >= 2) {
                        resized = true
                        val p0 = pressed[0].position
                        val p1 = pressed[1].position
                        val distance = (p0 - p1).getDistance().coerceAtLeast(1f)
                        lastTwoFingerDistance?.let { previousDistance ->
                            val oldSize = reactionSizePx
                            val nextSize = (oldSize * (distance / previousDistance)).coerceIn(minButtonPx, maxButtonPx)
                            val centerX = reactionXPx + oldSize / 2f
                            val centerY = reactionYPx + oldSize / 2f
                            reactionSizePx = nextSize
                            reactionXPx = (centerX - nextSize / 2f).coerceIn(0f, (maxW - nextSize).coerceAtLeast(0f))
                            reactionYPx = (centerY - nextSize / 2f).coerceIn(0f, (maxH - nextSize).coerceAtLeast(0f))
                        }
                        lastTwoFingerDistance = distance
                        pressed.forEach { it.consume() }
                        consumedMovement = true
                    } else {
                        lastTwoFingerDistance = null
                        val change = pressed[0]
                        val delta = change.position - previousOneFinger
                        previousOneFinger = change.position
                        movedPx += delta.getDistance()
                        if (movedPx > touchSlop) {
                            reactionXPx = (reactionXPx + delta.x).coerceIn(0f, (maxW - reactionSizePx).coerceAtLeast(0f))
                            reactionYPx = (reactionYPx + delta.y).coerceIn(0f, (maxH - reactionSizePx).coerceAtLeast(0f))
                            change.consume()
                            consumedMovement = true
                        }
                    }
                }

                val upAt = System.currentTimeMillis()
                if (!resized && movedPx <= touchSlop * 1.5f && !consumedMovement) {
                    controller.log(current.id, EventTypes.REACTION_DOWN, mediaPositionMs = latestVideoPosition, x = downPosition.x.toDouble(), y = downPosition.y.toDouble(), at = downAt)
                    if (!firstReactionLogged && latestViewStart > 0L) {
                        firstReactionLogged = true
                        controller.log(current.id, EventTypes.FIRST_TAP_LATENCY, value = downAt - latestViewStart, mediaPositionMs = latestVideoPosition, at = downAt)
                    }
                    controller.log(current.id, EventTypes.REACTION_UP, value = upAt - downAt, mediaPositionMs = latestVideoPosition, x = finalPosition.x.toDouble(), y = finalPosition.y.toDouble(), at = upAt)
                } else {
                    prefs.edit().putFloat("reaction_size_px", reactionSizePx).putFloat("reaction_x_px", reactionXPx).putFloat("reaction_y_px", reactionYPx).apply()
                    if (resized) controller.log(current.id, EventTypes.REACTION_BUTTON_RESIZE, value = reactionSizePx.roundToInt().toLong(), x = reactionXPx.toDouble(), y = reactionYPx.toDouble())
                    else controller.log(current.id, EventTypes.REACTION_BUTTON_MOVE, value = movedPx.roundToInt().toLong(), x = reactionXPx.toDouble(), y = reactionYPx.toDouble())
                }
            }
        }

        val verticalViewerGesture = Modifier.pointerInput(current.id, currentZoomed, declarationDrawerOpen, reactionXPx, reactionYPx, reactionSizePx) {
            val threshold = with(density) { 92.dp.toPx() }
            awaitEachGesture {
                val first = awaitFirstDown(requireUnconsumed = false)
                if (insideButton(first.position)) {
                    while (true) { val e = awaitPointerEvent(); if (e.changes.none { it.pressed }) break }
                    return@awaitEachGesture
                }
                var dx = 0f
                var dy = 0f
                var previous = first.position
                while (true) {
                    val e = awaitPointerEvent()
                    val down = e.changes.firstOrNull { it.pressed } ?: break
                    val delta = down.position - previous
                    previous = down.position
                    dx += delta.x; dy += delta.y
                }
                if (!currentZoomed && abs(dy) > threshold && abs(dy) > abs(dx) * 1.25f) {
                    if (dy < 0f) {
                        if (!declarationDrawerOpen) {
                            declarationDrawerOpen = true
                            controller.log(current.id, EventTypes.DECLARATION_DRAWER_OPEN, mediaPositionMs = latestVideoPosition)
                        }
                    } else {
                        if (declarationDrawerOpen) {
                            declarationDrawerOpen = false
                            controller.log(current.id, EventTypes.DECLARATION_DRAWER_CLOSE, mediaPositionMs = latestVideoPosition)
                        } else onClose()
                    }
                }
            }
        }

        Box(Modifier.fillMaxSize().then(verticalViewerGesture).then(reactionGesture)) {
            HorizontalPager(
                state = pagerState,
                modifier = Modifier.fillMaxSize(),
                beyondViewportPageCount = 1,
                userScrollEnabled = !currentZoomed && !declarationDrawerOpen
            ) { page ->
                val item = items[page]
                MediaViewerPane(
                    item = item,
                    controller = controller,
                    active = page == pagerState.currentPage,
                    controlsVisible = controlsVisible,
                    onToggleUi = {
                        controlsVisible = !controlsVisible
                        controller.log(current.id, if (controlsVisible) EventTypes.UI_SHOWN else EventTypes.UI_HIDDEN, mediaPositionMs = videoPositionMs)
                    },
                    onVideoPosition = { pos -> if (page == pagerState.currentPage) videoPositionMs = pos },
                    onZoomedChanged = { zoomed -> if (page == pagerState.currentPage) currentZoomed = zoomed }
                )
            }

            if (controlsVisible) {
                Column(
                    Modifier.align(Alignment.TopCenter).fillMaxWidth().background(Color.Black.copy(alpha = 0.84f)).statusBarsPadding().padding(horizontal = 8.dp, vertical = 4.dp)
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
                    Modifier.align(Alignment.BottomCenter).fillMaxWidth().background(Color.Black.copy(alpha = 0.88f)).navigationBarsPadding().padding(vertical = 10.dp),
                    horizontalArrangement = Arrangement.SpaceEvenly,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(onClick = {
                        val next = current.id !in favoriteIds
                        controller.db.setFavorite(current.id, next)
                        controller.log(current.id, if (next) EventTypes.FAVORITE_SET else EventTypes.FAVORITE_UNSET, mediaPositionMs = videoPositionMs)
                        favoriteIds = if (next) favoriteIds + current.id else favoriteIds - current.id
                        onLibraryChanged()
                    }) {
                        Icon(if (current.id in favoriteIds) Icons.Default.Favorite else Icons.Default.FavoriteBorder, "Favorite", tint = if (current.id in favoriteIds) Color(0xFFFF4D67) else Color.White, modifier = Modifier.size(30.dp))
                    }
                    IconButton(onClick = { share(current) }) { Icon(Icons.Default.Share, "Share", modifier = Modifier.size(28.dp)) }
                    IconButton(onClick = { showDeleteDialog = true }) { Icon(Icons.Default.Delete, "Delete", modifier = Modifier.size(28.dp)) }
                    IconButton(onClick = { showInfoDialog = true }) { Icon(Icons.Default.MoreVert, "More", modifier = Modifier.size(28.dp)) }
                }
            }

            AnimatedVisibility(
                visible = declarationDrawerOpen,
                modifier = Modifier.align(Alignment.BottomCenter)
            ) {
                DeclarationDrawer(
                    spiritualRemainingMs = spiritualRemainingMs,
                    onConfirmedNut = {
                        val (_, item) = controller.confirmFinish(current.id, videoPositionMs)
                        toastMessage = "Confirmed nut locked to ${item?.name ?: current.name}"
                        declarationDrawerOpen = false
                    },
                    onInstantHard = {
                        controller.markInstantHard(current.id, videoPositionMs)
                        toastMessage = "Instant Hard recorded"
                    },
                    onSpiritualCoom = {
                        if (spiritualRemainingMs <= 0L) {
                            controller.markSpiritualCoom(current.id, videoPositionMs)
                            lastSpiritualMs = System.currentTimeMillis()
                            prefs.edit().putLong("last_spiritual_coom_ms", lastSpiritualMs).apply()
                            spiritualRemainingMs = 180_000L
                            toastMessage = "Spiritual Coom recorded"
                        }
                    },
                    onEdge = {
                        controller.markEdge(current.id, videoPositionMs)
                        toastMessage = "Edge mark recorded"
                    }
                )
            }

            Box(
                Modifier.offset { IntOffset(reactionXPx.roundToInt(), reactionYPx.roundToInt()) }.size(with(density) { reactionSizePx.toDp() }),
                contentAlignment = Alignment.Center
            ) {
                Surface(shape = CircleShape, color = Color(0xFFB3122B), shadowElevation = 12.dp, modifier = Modifier.fillMaxSize()) {
                    Box(contentAlignment = Alignment.Center) {
                        Text("❤️‍🔥", fontSize = with(density) { (reactionSizePx * 0.43f).toSp() })
                    }
                }
            }
        }
    }
}

@Composable
private fun DeclarationDrawer(
    spiritualRemainingMs: Long,
    onConfirmedNut: () -> Unit,
    onInstantHard: () -> Unit,
    onSpiritualCoom: () -> Unit,
    onEdge: () -> Unit
) {
    Surface(color = Color(0xF20E0E0E), shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp), shadowElevation = 18.dp) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Lock in a high-value signal", color = Color.White)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                DeclarationButton("🍆💦", "Confirmed Nut", onConfirmedNut, Modifier.weight(1f))
                DeclarationButton("⚡", "Instant Hard", onInstantHard, Modifier.weight(1f))
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                val cooldownLabel = if (spiritualRemainingMs > 0) "${spiritualRemainingMs / 60_000}:${((spiritualRemainingMs / 1000) % 60).toString().padStart(2, '0')}" else "Spiritual Coom"
                DeclarationButton("✨", cooldownLabel, onSpiritualCoom, Modifier.weight(1f), enabled = spiritualRemainingMs <= 0L)
                DeclarationButton("🌊", "On The Edge", onEdge, Modifier.weight(1f))
            }
            Text("Swipe down to close · confirmed nuts are ground truth; potential nuts remain inference only.", color = Color.Gray, fontSize = 12.sp)
        }
    }
}

@Composable
private fun DeclarationButton(emoji: String, label: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.height(58.dp),
        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF2A171B), contentColor = Color.White, disabledContainerColor = Color(0xFF1A1A1A))
    ) {
        Text("$emoji  $label", maxLines = 1)
    }
}

@Composable
private fun MediaViewerPane(
    item: MediaItem,
    controller: AppController,
    active: Boolean,
    controlsVisible: Boolean,
    onToggleUi: () -> Unit,
    onVideoPosition: (Long?) -> Unit,
    onZoomedChanged: (Boolean) -> Unit
) {
    if (item.isVideo) {
        onZoomedChanged(false)
        ViewerVideo(item, controller, active, controlsVisible, onToggleUi, onVideoPosition)
    } else {
        ZoomableImage(item, controller, onToggleUi, onZoomedChanged)
        LaunchedEffect(item.id) { onVideoPosition(null) }
    }
}

@Composable
private fun ZoomableImage(item: MediaItem, controller: AppController, onToggleUi: () -> Unit, onZoomedChanged: (Boolean) -> Unit) {
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
            controller.log(item.id, EventTypes.ZOOM_START, at = now)
            onZoomedChanged(true)
        }
    }

    fun endZoom(now: Long = System.currentTimeMillis()) {
        zoomSessionStart?.let { start ->
            controller.log(item.id, EventTypes.ZOOMED_DWELL, value = (now - start).coerceAtLeast(0L), at = now)
            controller.log(item.id, EventTypes.ZOOM_END, at = now)
        }
        zoomSessionStart = null
        onZoomedChanged(false)
    }

    DisposableEffect(item.id) {
        onDispose {
            val now = System.currentTimeMillis()
            zoomSessionStart?.let { start ->
                controller.log(item.id, EventTypes.ZOOMED_DWELL, value = (now - start).coerceAtLeast(0L), at = now)
                controller.log(item.id, EventTypes.ZOOM_END, at = now)
            }
        }
    }

    val gestureModifier = Modifier.pointerInput(item.id) {
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
                            controller.log(item.id, EventTypes.ZOOM_SCALE, value = (scale * 1000).roundToInt().toLong(), x = centroid.x.toDouble(), y = centroid.y.toDouble(), at = now)
                            lastScaleLogAt = now
                        }
                        if (scale <= 1.02f) {
                            scale = 1f; offset = Offset.Zero; endZoom(now)
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
                    lastDistance = null; lastCentroid = null
                } else {
                    lastDistance = null; lastCentroid = null
                }
            }
            if (totalPan > 0f) {
                controller.log(item.id, EventTypes.PAN_DISTANCE, value = totalPan.roundToInt().toLong())
                controller.log(item.id, EventTypes.PAN_POINT, x = offset.x.toDouble(), y = offset.y.toDouble(), details = "scale=${"%.3f".format(Locale.US, scale)}")
            }
        }
    }

    Box(
        Modifier.fillMaxSize().onSizeChanged { boxSize = it }
            .pointerInput(item.id) {
                detectTapGestures(
                    onTap = { onToggleUi() },
                    onDoubleTap = {
                        val now = System.currentTimeMillis()
                        if (scale > 1f) {
                            scale = 1f; offset = Offset.Zero; endZoom(now)
                        } else {
                            scale = 2.5f; beginZoom(now)
                            controller.log(item.id, EventTypes.ZOOM_SCALE, value = 2500L, at = now)
                        }
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
private fun ViewerVideo(
    item: MediaItem,
    controller: AppController,
    active: Boolean,
    controlsVisible: Boolean,
    onToggleUi: () -> Unit,
    onVideoPosition: (Long?) -> Unit
) {
    val context = LocalContext.current
    val player = remember(item.uri) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(ExoMediaItem.fromUri(Uri.parse(item.uri)))
            prepare()
        }
    }
    var positionMs by remember(item.id) { mutableLongStateOf(0L) }
    var durationMs by remember(item.id) { mutableLongStateOf(1L) }
    var scrubbing by remember(item.id) { mutableStateOf(false) }
    var scrubValue by remember(item.id) { mutableFloatStateOf(0f) }
    var isPlaying by remember(item.id) { mutableStateOf(false) }

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
                if (reason == Player.DISCONTINUITY_REASON_SEEK) {
                    val delta = newPosition.positionMs - oldPosition.positionMs
                    controller.log(item.id, EventTypes.VIDEO_SEEK, value = delta, mediaPositionMs = newPosition.positionMs)
                    if (delta < -1000L) controller.log(item.id, EventTypes.VIDEO_REPLAY, value = -delta, mediaPositionMs = newPosition.positionMs)
                }
            }
        }
        player.addListener(listener)
        onDispose {
            val now = System.currentTimeMillis()
            playingStartedAt?.let { controller.log(item.id, EventTypes.VIDEO_WATCH_DWELL, value = now - it, mediaPositionMs = player.currentPosition, at = now) }
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
            delay(100)
        }
    }

    Box(Modifier.fillMaxSize()) {
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
            modifier = Modifier.fillMaxSize()
        )
        Box(Modifier.fillMaxSize().pointerInput(item.id) { detectTapGestures(onTap = { onToggleUi() }) })

        if (controlsVisible && active) {
            Row(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().navigationBarsPadding().padding(start = 10.dp, end = 12.dp, bottom = 72.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = { if (player.isPlaying) player.pause() else player.play() }) {
                    Icon(if (isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow, contentDescription = if (isPlaying) "Pause" else "Play")
                }
                Slider(
                    value = scrubValue.coerceIn(0f, durationMs.toFloat().coerceAtLeast(1f)),
                    onValueChange = { value ->
                        if (!scrubbing) {
                            scrubbing = true
                            controller.log(item.id, EventTypes.VIDEO_SCRUB_START, mediaPositionMs = player.currentPosition)
                        }
                        scrubValue = value
                    },
                    onValueChangeFinished = {
                        val target = scrubValue.toLong().coerceIn(0L, durationMs)
                        player.seekTo(target)
                        controller.log(item.id, EventTypes.VIDEO_SCRUB_END, mediaPositionMs = target)
                        scrubbing = false
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

private fun formatClock(ms: Long): String {
    val total = (ms.coerceAtLeast(0L) / 1000L)
    val minutes = total / 60
    val seconds = total % 60
    return "$minutes:${seconds.toString().padStart(2, '0')}"
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
            } finally { retriever.release() }
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
