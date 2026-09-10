package com.neurontap.app

import android.content.ContentValues
import android.content.Context
import android.graphics.Bitmap
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.view.TextureView
import android.widget.Toast
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.weight
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.positionChange
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.media3.common.MediaItem as ExoMediaItem
import androidx.media3.common.Player
import androidx.media3.common.VideoSize
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.SeekParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * One authoritative player for the whole ViewerScreen. HorizontalPager may
 * compose neighboring pages, but they no longer create their own decoders.
 */
class ViewerVideoHostV8(context: Context, private val controller: AppController) {
    val player: ExoPlayer = ExoPlayer.Builder(context.applicationContext).build().apply {
        setSeekParameters(SeekParameters.CLOSEST_SYNC)
    }

    private var boundMediaId: Long? = null
    private var boundUri: String? = null
    private var boundName: String? = null
    private var textureView: TextureView? = null
    private var videoSizeCallback: ((Float) -> Unit)? = null
    private var playingStartedAt: Long? = null
    private var lastScrubSeekRealtime = 0L
    private val positions = mutableMapOf<Long, Long>()

    private val listener = object : Player.Listener {
        override fun onIsPlayingChanged(isPlaying: Boolean) {
            val id = boundMediaId ?: return
            val now = System.currentTimeMillis()
            if (isPlaying) {
                if (playingStartedAt == null) {
                    playingStartedAt = now
                    controller.log(id, EventTypes.VIDEO_PLAY, mediaPositionMs = player.currentPosition, at = now, details = "v8_single_player")
                }
            } else {
                playingStartedAt?.let { started ->
                    controller.log(id, EventTypes.VIDEO_WATCH_DWELL, value = (now - started).coerceAtLeast(0L), mediaPositionMs = player.currentPosition, at = now)
                }
                playingStartedAt = null
                controller.log(id, EventTypes.VIDEO_PAUSE, mediaPositionMs = player.currentPosition, at = now, details = "v8_single_player")
            }
        }

        override fun onVideoSizeChanged(videoSize: VideoSize) {
            if (videoSize.width > 0 && videoSize.height > 0) {
                val ratio = videoSize.width.toFloat() * videoSize.pixelWidthHeightRatio / videoSize.height.toFloat()
                videoSizeCallback?.invoke(ratio.coerceIn(0.1f, 10f))
            }
        }

        override fun onPositionDiscontinuity(oldPosition: Player.PositionInfo, newPosition: Player.PositionInfo, reason: Int) {
            val id = boundMediaId ?: return
            positions[id] = newPosition.positionMs.coerceAtLeast(0L)
            if (reason == Player.DISCONTINUITY_REASON_SEEK) {
                val delta = newPosition.positionMs - oldPosition.positionMs
                controller.log(id, EventTypes.VIDEO_SEEK, value = delta, mediaPositionMs = newPosition.positionMs, details = "v8")
                if (delta < -500L) controller.log(id, EventTypes.VIDEO_REPLAY, value = -delta, mediaPositionMs = newPosition.positionMs, details = "explicit_seek")
            }
        }
    }

    init { player.addListener(listener) }

    fun bind(item: MediaItem, initialPositionMs: Long, loop: Boolean, muted: Boolean, onAspect: (Float) -> Unit) {
        videoSizeCallback = onAspect
        player.repeatMode = if (loop) Player.REPEAT_MODE_ONE else Player.REPEAT_MODE_OFF
        player.volume = if (muted) 0f else 1f
        if (boundMediaId == item.id && boundUri == item.uri) return

        finishWatchSample()
        boundMediaId?.let { positions[it] = player.currentPosition.coerceAtLeast(0L) }
        boundMediaId = item.id
        boundUri = item.uri
        boundName = item.name
        lastScrubSeekRealtime = 0L

        player.stop()
        player.clearMediaItems()
        player.setMediaItem(ExoMediaItem.fromUri(Uri.parse(item.uri)))
        player.prepare()
        val resume = positions[item.id] ?: initialPositionMs
        if (resume > 0L) player.seekTo(resume)
    }

    fun attachTexture(view: TextureView) {
        if (textureView === view) return
        textureView?.let { runCatching { player.clearVideoTextureView(it) } }
        textureView = view
        player.setVideoTextureView(view)
    }

    fun detachTexture(view: TextureView) {
        if (textureView === view) {
            runCatching { player.clearVideoTextureView(view) }
            textureView = null
        }
    }

    fun setLoop(loop: Boolean) { player.repeatMode = if (loop) Player.REPEAT_MODE_ONE else Player.REPEAT_MODE_OFF }
    fun setMuted(muted: Boolean) { player.volume = if (muted) 0f else 1f }

    fun playIfBound(mediaId: Long) { if (boundMediaId == mediaId) player.play() }
    fun pauseIfBound(mediaId: Long) { if (boundMediaId == mediaId) player.pause() }
    fun isBound(mediaId: Long): Boolean = boundMediaId == mediaId
    fun isPlaying(mediaId: Long): Boolean = boundMediaId == mediaId && player.isPlaying
    fun position(mediaId: Long): Long = if (boundMediaId == mediaId) player.currentPosition.coerceAtLeast(0L) else positions[mediaId] ?: 0L
    fun duration(mediaId: Long): Long = if (boundMediaId == mediaId) player.duration.takeIf { it > 0L } ?: 1L else 1L

    fun scrubSeek(mediaId: Long, targetMs: Long) {
        if (boundMediaId != mediaId) return
        val now = android.os.SystemClock.elapsedRealtime()
        if (now - lastScrubSeekRealtime >= 32L) {
            lastScrubSeekRealtime = now
            player.setSeekParameters(SeekParameters.CLOSEST_SYNC)
            player.seekTo(targetMs.coerceAtLeast(0L))
        }
    }

    fun commitSeek(mediaId: Long, targetMs: Long) {
        if (boundMediaId != mediaId) return
        player.setSeekParameters(SeekParameters.CLOSEST_SYNC)
        player.seekTo(targetMs.coerceAtLeast(0L))
        positions[mediaId] = targetMs.coerceAtLeast(0L)
    }

    private fun finishWatchSample() {
        val id = boundMediaId ?: return
        val now = System.currentTimeMillis()
        playingStartedAt?.let { started ->
            controller.log(id, EventTypes.VIDEO_WATCH_DWELL, value = (now - started).coerceAtLeast(0L), mediaPositionMs = player.currentPosition, at = now)
        }
        playingStartedAt = null
    }

    fun release() {
        finishWatchSample()
        textureView?.let { runCatching { player.clearVideoTextureView(it) } }
        textureView = null
        player.removeListener(listener)
        player.release()
    }
}

@Composable
fun ViewerVideoV8(
    host: ViewerVideoHostV8,
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
    if (!active) {
        Box(Modifier.fillMaxSize().background(Color.Black)) {
            MediaThumbnail(item, Modifier.fillMaxSize(), ContentScale.Fit, item.name)
        }
        return
    }

    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    var appVisible by remember { mutableStateOf(lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) }
    var resumePositionMs by rememberSaveable(item.id) { mutableLongStateOf(0L) }
    var aspect by rememberSaveable(item.id) { mutableFloatStateOf(16f / 9f) }
    var positionMs by remember(item.id) { mutableLongStateOf(0L) }
    var durationMs by remember(item.id) { mutableLongStateOf(1L) }
    var scrubbing by remember(item.id) { mutableStateOf(false) }
    var scrubValue by remember(item.id) { mutableFloatStateOf(0f) }
    var wasPlayingBeforeScrub by remember(item.id) { mutableStateOf(false) }
    var textureView by remember(item.id) { mutableStateOf<TextureView?>(null) }

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
            controller.log(item.id, EventTypes.ZOOM_START, mediaPositionMs = host.position(item.id), details = "video_v8", at = now)
            onZoomedChanged(true)
        }
    }
    fun endZoom(now: Long = System.currentTimeMillis()) {
        zoomSessionStart?.let { start ->
            controller.log(item.id, EventTypes.ZOOMED_DWELL, value = (now - start).coerceAtLeast(0L), mediaPositionMs = host.position(item.id), details = "video_v8", at = now)
            controller.log(item.id, EventTypes.ZOOM_END, mediaPositionMs = host.position(item.id), details = "video_v8", at = now)
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

    LaunchedEffect(item.id) {
        host.bind(item, resumePositionMs, loopVideos, videosMuted) { aspect = it }
    }
    LaunchedEffect(loopVideos) { host.setLoop(loopVideos) }
    LaunchedEffect(videosMuted) { host.setMuted(videosMuted) }
    LaunchedEffect(appVisible, autoplayVideos, item.id) {
        if (!appVisible) host.pauseIfBound(item.id)
        else if (autoplayVideos) host.playIfBound(item.id)
    }

    DisposableEffect(item.id) {
        onDispose {
            resumePositionMs = host.position(item.id)
            zoomSessionStart?.let { start ->
                controller.log(item.id, EventTypes.ZOOMED_DWELL, value = (System.currentTimeMillis() - start).coerceAtLeast(0L), mediaPositionMs = resumePositionMs, details = "video_v8_dispose")
            }
            onZoomedChanged(false)
        }
    }

    LaunchedEffect(item.id) {
        while (true) {
            if (host.isBound(item.id)) {
                positionMs = host.position(item.id)
                durationMs = host.duration(item.id).coerceAtLeast(1L)
                resumePositionMs = positionMs
                if (!scrubbing) scrubValue = positionMs.toFloat().coerceIn(0f, durationMs.toFloat())
                onVideoPosition(if (scrubbing) scrubValue.toLong() else positionMs)
            }
            delay(100L)
        }
    }

    val zoomGesture = if (!gesturesEnabled) Modifier else Modifier.pointerInput(item.id) {
        awaitEachGesture {
            awaitFirstDown(requireUnconsumed = true)
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
                        val next = clampOffset(Offset(offsetX + pan.x, offsetY + pan.y), nextScale)
                        if (nextScale > 1.02f) beginZoom()
                        scale = nextScale; offsetX = next.x; offsetY = next.y; totalPan += pan.getDistance()
                        val now = System.currentTimeMillis()
                        if (now - lastScaleLogAt >= 100L) {
                            controller.log(item.id, EventTypes.ZOOM_SCALE, value = (scale * 1000).roundToInt().toLong(), mediaPositionMs = host.position(item.id), x = centroid.x.toDouble(), y = centroid.y.toDouble(), details = "video_v8")
                            lastScaleLogAt = now
                        }
                        if (scale <= 1.02f) { scale = 1f; offsetX = 0f; offsetY = 0f; endZoom(now) }
                    }
                    lastDistance = distance; lastCentroid = centroid
                    pressed.forEach { it.consume() }
                } else if (scale > 1f && pressed.size == 1) {
                    val delta = pressed[0].positionChange()
                    val next = clampOffset(Offset(offsetX + delta.x, offsetY + delta.y), scale)
                    offsetX = next.x; offsetY = next.y; totalPan += delta.getDistance()
                    pressed[0].consume(); lastDistance = null; lastCentroid = null
                } else {
                    lastDistance = null; lastCentroid = null
                }
            }
            if (totalPan > 0f) controller.log(item.id, EventTypes.PAN_DISTANCE, value = totalPan.roundToInt().toLong(), mediaPositionMs = host.position(item.id), details = "video_v8")
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
                        controller.log(item.id, EventTypes.DOUBLE_TAP_FOCUS, value = (target * 1000).roundToInt().toLong(), mediaPositionMs = host.position(item.id), x = tap.x.toDouble(), y = tap.y.toDouble(), details = "video_v8;w=${boxSize.width};h=${boxSize.height}")
                        if (target > 1f) beginZoom()
                        scope.launch {
                            val sx = offsetX; val sy = offsetY; val ss = scale
                            val progress = Animatable(0f)
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
        BoxWithConstraints(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            val containerAspect = if (maxHeight.value > 0f) maxWidth.value / maxHeight.value else aspect
            val fitModifier = if (aspect >= containerAspect) Modifier.fillMaxWidth() else Modifier.fillMaxHeight()
            AndroidView(
                factory = { ctx ->
                    TextureView(ctx).also { tv ->
                        textureView = tv
                        host.attachTexture(tv)
                    }
                },
                update = { tv -> if (host.isBound(item.id)) host.attachTexture(tv) },
                modifier = fitModifier.graphicsLayer(
                    scaleX = scale,
                    scaleY = scale,
                    translationX = offsetX,
                    translationY = offsetY
                )
            )
        }

        if (controlsVisible) {
            Row(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().background(Color.Black.copy(alpha = 0.86f)).navigationBarsPadding().padding(start = 6.dp, end = 10.dp, bottom = 72.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(2.dp)
            ) {
                IconButton(modifier = Modifier.size(50.dp), onClick = {
                    if (host.isPlaying(item.id)) host.pauseIfBound(item.id) else host.playIfBound(item.id)
                }) {
                    Icon(if (host.isPlaying(item.id)) Icons.Default.Pause else Icons.Default.PlayArrow, if (host.isPlaying(item.id)) "Pause" else "Play", tint = Color.White)
                }
                IconButton(modifier = Modifier.size(48.dp), onClick = {
                    val at = host.position(item.id)
                    val captured = textureView?.bitmap
                    scope.launch {
                        val exported = saveVideoFrameV8(context, item, at, captured)
                        if (exported != null) {
                            val (uri, name, savedAt) = exported
                            withContext(Dispatchers.IO) { controller.db.upsertMedia("mediastore:Pictures/NeuronTap Frames", uri.toString(), name, "image/png", 0L, savedAt) }
                            controller.log(item.id, EventTypes.VIDEO_FRAME_EXPORT, mediaPositionMs = at, details = "frame=$uri;v8_single_player")
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
                            scrubbing = true
                            wasPlayingBeforeScrub = host.isPlaying(item.id)
                            host.pauseIfBound(item.id)
                            controller.log(item.id, EventTypes.VIDEO_SCRUB_START, mediaPositionMs = host.position(item.id))
                        }
                        scrubValue = target.toFloat()
                        positionMs = target
                        host.scrubSeek(item.id, target)
                        onVideoPosition(target)
                    },
                    onValueChangeFinished = {
                        val target = scrubValue.toLong().coerceIn(0L, durationMs)
                        host.commitSeek(item.id, target)
                        controller.log(item.id, EventTypes.VIDEO_SCRUB_END, mediaPositionMs = target)
                        scrubbing = false
                        if (wasPlayingBeforeScrub) host.playIfBound(item.id)
                    },
                    valueRange = 0f..durationMs.toFloat().coerceAtLeast(1f),
                    modifier = Modifier.weight(1f)
                )
                Text("${formatClockV8(if (scrubbing) scrubValue.toLong() else positionMs)} / ${formatClockV8(durationMs)}", fontSize = 10.sp, color = Color.White)
            }
        }
    }
}

private fun formatClockV8(ms: Long): String {
    val total = (ms.coerceAtLeast(0L) / 1000L)
    val m = total / 60L
    val s = total % 60L
    return String.format(Locale.US, "%d:%02d", m, s)
}

private suspend fun saveVideoFrameV8(context: Context, item: MediaItem, positionMs: Long, displayBitmap: Bitmap?): Triple<Uri, String, Long>? = withContext(Dispatchers.IO) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return@withContext null
    val bitmap = displayBitmap ?: runCatching {
        MediaMetadataRetriever().let { retriever ->
            try {
                retriever.setDataSource(context, Uri.parse(item.uri))
                retriever.getFrameAtTime(positionMs * 1000L, MediaMetadataRetriever.OPTION_CLOSEST)
            } finally {
                retriever.release()
            }
        }
    }.getOrNull() ?: return@withContext null

    runCatching {
        val now = System.currentTimeMillis()
        val name = "NeuronTap_${item.id}_${positionMs}ms_${now}.png"
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, name)
            put(MediaStore.Images.Media.MIME_TYPE, "image/png")
            put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/NeuronTap Frames")
            put(MediaStore.Images.Media.IS_PENDING, 1)
        }
        val resolver = context.contentResolver
        val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values) ?: error("insert failed")
        try {
            resolver.openOutputStream(uri)?.use { out ->
                if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)) error("compress failed")
            } ?: error("open output failed")
            resolver.update(uri, ContentValues().apply { put(MediaStore.Images.Media.IS_PENDING, 0) }, null, null)
            Triple(uri, name, now)
        } catch (t: Throwable) {
            resolver.delete(uri, null, null)
            throw t
        } finally {
            if (displayBitmap == null) bitmap.recycle()
        }
    }.getOrNull()
}
