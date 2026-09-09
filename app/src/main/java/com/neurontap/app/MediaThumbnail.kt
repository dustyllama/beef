package com.neurontap.app

import android.net.Uri
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import coil.compose.AsyncImage
import coil.decode.VideoFrameDecoder
import coil.request.ImageRequest

@Composable
fun MediaThumbnail(
    item: MediaItem,
    modifier: Modifier = Modifier,
    contentScale: ContentScale = ContentScale.Crop,
    contentDescription: String? = item.name
) {
    val context = LocalContext.current
    val model: Any = if (item.isVideo) {
        ImageRequest.Builder(context)
            .data(Uri.parse(item.uri))
            .decoderFactory(VideoFrameDecoder.Factory())
            .crossfade(false)
            .build()
    } else {
        Uri.parse(item.uri)
    }
    AsyncImage(model = model, contentDescription = contentDescription, modifier = modifier, contentScale = contentScale)
}
