from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "app/src/main/java/com/neurontap/app/MediaThumbnail.kt"

# The field recording shows video-grid cells repeatedly going black while
# scrolling. The old implementation asks Coil/MediaMetadataRetriever to open
# the original video for every visible cell. Prefer Android's provider thumbnail
# path for MediaStore media, keep a bounded in-process bitmap cache, and use a
# bounded/stable Coil request only as a fallback for SAF/API 28 media.
p.write_text(r'''package com.neurontap.app

import android.content.Context
import android.graphics.Bitmap
import android.net.Uri
import android.os.Build
import android.util.LruCache
import android.util.Size
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import coil.compose.AsyncImage
import coil.decode.VideoFrameDecoder
import coil.request.ImageRequest
import coil.request.videoFramePercent
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext

private sealed interface VideoThumbState {
    data object Loading : VideoThumbState
    data class Ready(val bitmap: Bitmap) : VideoThumbState
    data object Fallback : VideoThumbState
}

private object VideoThumbCache {
    // Four provider thumbnail decodes at a time avoids stampeding the media
    // provider when a 4-8 column grid composes dozens of cells simultaneously.
    private val decodeSlots = Semaphore(4)
    private const val cacheKilobytes = 48 * 1024
    private val memory = object : LruCache<String, Bitmap>(cacheKilobytes) {
        override fun sizeOf(key: String, value: Bitmap): Int =
            (value.allocationByteCount / 1024).coerceAtLeast(1)
    }

    fun key(item: MediaItem): String = "video-thumb:${item.id}:${item.modified}:${item.uri}"

    suspend fun loadMediaStore(context: Context, item: MediaItem): Bitmap? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q || !item.rootUri.startsWith("mediastore:")) return null
        val key = key(item)
        memory.get(key)?.let { return it }
        return decodeSlots.withPermit {
            memory.get(key)?.let { return@withPermit it }
            val bitmap = withContext(Dispatchers.IO) {
                runCatching {
                    context.contentResolver.loadThumbnail(Uri.parse(item.uri), Size(512, 512), null)
                }.getOrNull()
            }
            if (bitmap != null) memory.put(key, bitmap)
            bitmap
        }
    }
}

@Composable
fun MediaThumbnail(
    item: MediaItem,
    modifier: Modifier = Modifier,
    contentScale: ContentScale = ContentScale.Crop,
    contentDescription: String? = item.name
) {
    val context = LocalContext.current
    if (!item.isVideo) {
        AsyncImage(
            model = Uri.parse(item.uri),
            contentDescription = contentDescription,
            modifier = modifier,
            contentScale = contentScale
        )
        return
    }

    val cacheKey = remember(item.id, item.modified, item.uri) { VideoThumbCache.key(item) }
    val state by produceState<VideoThumbState>(VideoThumbState.Loading, cacheKey) {
        val bitmap = VideoThumbCache.loadMediaStore(context, item)
        value = if (bitmap != null) VideoThumbState.Ready(bitmap) else VideoThumbState.Fallback
    }

    when (val current = state) {
        VideoThumbState.Loading -> Box(modifier.background(Color(0xFF111111)))
        is VideoThumbState.Ready -> Image(
            bitmap = current.bitmap.asImageBitmap(),
            contentDescription = contentDescription,
            modifier = modifier,
            contentScale = contentScale
        )
        VideoThumbState.Fallback -> {
            val request = remember(cacheKey) {
                ImageRequest.Builder(context)
                    .data(Uri.parse(item.uri))
                    .decoderFactory(VideoFrameDecoder.Factory())
                    .videoFramePercent(0.35)
                    .size(512)
                    .memoryCacheKey("fallback:$cacheKey")
                    .crossfade(false)
                    .build()
            }
            AsyncImage(
                model = request,
                contentDescription = contentDescription,
                modifier = modifier,
                contentScale = contentScale
            )
        }
    }
}
''')

print("Applied v0.8.1 provider-backed video thumbnail repair")
