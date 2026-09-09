package com.neurontap.app

data class MediaItem(
    val id: Long,
    val rootUri: String,
    val uri: String,
    val name: String,
    val mime: String,
    val size: Long,
    val modified: Long,
    val favorite: Boolean = false
) {
    val isVideo: Boolean get() = mime.startsWith("video/")
}

data class EventRow(
    val id: Long,
    val sessionId: String,
    val mediaId: Long?,
    val type: String,
    val timestampMs: Long,
    val value: Long?,
    val mediaPositionMs: Long?,
    val x: Double? = null,
    val y: Double? = null,
    val details: String? = null
)

data class SessionRow(
    val id: String,
    val startedAt: Long,
    val endedAt: Long?,
    val confirmedNut: Boolean,
    val confirmedNutAt: Long?,
    val inferredPrimaryMediaId: Long?,
    val inferenceConfidence: Double?,
    val inferredWindowStart: Long?,
    val inferredWindowEnd: Long?
)

data class FinishInference(
    val mediaId: Long?,
    val confidence: Double,
    val windowStartMs: Long?,
    val windowEndMs: Long?
)

data class PotentialNutCandidate(
    val sessionId: String,
    val primaryMediaId: Long?,
    val primaryMediaName: String?,
    val confidence: Double,
    val windowStartMs: Long?,
    val windowEndMs: Long?,
    val evidence: String
)

data class MediaBehaviorSummary(
    val mediaId: Long,
    val name: String,
    val views: Int = 0,
    val taps: Int = 0,
    val dwellMs: Long = 0,
    val sessionCount: Int = 0,
    val confirmedNuts: Int = 0,
    val spiritualCooms: Int = 0,
    val instantHardMarks: Int = 0,
    val edgeMarks: Int = 0,
    val zoomStarts: Int = 0,
    val zoomSamples: Int = 0,
    val maxZoomMilli: Long = 1000,
    val zoomedDwellMs: Long = 0,
    val panDistancePx: Long = 0,
    val videoSeeks: Int = 0,
    val videoReplays: Int = 0,
    val videoWatchMs: Long = 0,
    val quickestTapMs: Long? = null,
    val firstSeenMs: Long? = null,
    val lastSeenMs: Long? = null
) {
    val returnCount: Int get() = (views - sessionCount).coerceAtLeast(0)
    val explorationScore: Double get() =
        zoomStarts * 2.0 + zoomedDwellMs / 12_000.0 + panDistancePx / 1800.0 + videoSeeks * 1.4 + videoReplays * 2.0
    val attractionScore: Double get() =
        taps * 2.8 + kotlin.math.ln(1.0 + dwellMs / 1000.0) * 2.2 + spiritualCooms * 8.0 + instantHardMarks * 7.0 + edgeMarks * 6.0 + returnCount * 2.5 + explorationScore * 0.7
    val blueBallsScore: Double get() =
        if (confirmedNuts > 0) 0.0 else spiritualCooms * 12.0 + edgeMarks * 7.0 + taps * 1.5 + returnCount * 3.0 + explorationScore
    val conversionRate: Double get() = if (views <= 0) 0.0 else confirmedNuts.toDouble() / views.toDouble()
}

data class SmartGallery(
    val id: String,
    val title: String,
    val subtitle: String,
    val mediaIds: List<Long>
)

data class WrappedStats(
    val taps: Int = 0,
    val sessions: Int = 0,
    val confirmedNuts: Int = 0,
    val potentialNuts: Int = 0,
    val spiritualCooms: Int = 0,
    val instantHardMarks: Int = 0,
    val edgeMarks: Int = 0,
    val totalDwellMs: Long = 0,
    val totalZoomedMs: Long = 0,
    val quickestFirstTapMs: Long? = null,
    val longestDwellMs: Long? = null,
    val mostActiveHour: Int? = null,
    val summaries: List<MediaBehaviorSummary> = emptyList(),
    val potentialNutCandidates: List<PotentialNutCandidate> = emptyList(),
    val smartGalleries: List<SmartGallery> = emptyList(),
    val insights: List<String> = emptyList()
)

object EventTypes {
    const val SESSION_START = "SESSION_START"
    const val SESSION_END = "SESSION_END"
    const val APP_FOREGROUND = "APP_FOREGROUND"
    const val APP_BACKGROUND = "APP_BACKGROUND"
    const val ORIENTATION = "ORIENTATION"

    const val GALLERY_OPEN = "GALLERY_OPEN"
    const val GALLERY_MODE = "GALLERY_MODE"
    const val GALLERY_SCROLL = "GALLERY_SCROLL"
    const val GRID_RESIZE = "GRID_RESIZE"
    const val ALBUM_OPEN = "ALBUM_OPEN"
    const val ALBUM_CLOSE = "ALBUM_CLOSE"
    const val ALBUM_GROUP_CREATE = "ALBUM_GROUP_CREATE"
    const val ALBUM_REORDER = "ALBUM_REORDER"

    const val VIEW_START = "VIEW_START"
    const val VIEW_END = "VIEW_END"
    const val VIEW_DWELL = "VIEW_DWELL"
    const val MEDIA_SWIPE = "MEDIA_SWIPE"
    const val UI_SHOWN = "UI_SHOWN"
    const val UI_HIDDEN = "UI_HIDDEN"
    const val DECLARATION_DRAWER_OPEN = "DECLARATION_DRAWER_OPEN"
    const val DECLARATION_DRAWER_CLOSE = "DECLARATION_DRAWER_CLOSE"

    const val REACTION_DOWN = "REACTION_DOWN"
    const val REACTION_UP = "REACTION_UP"
    const val FIRST_TAP_LATENCY = "FIRST_TAP_LATENCY"
    const val REACTION_BUTTON_MOVE = "REACTION_BUTTON_MOVE"
    const val REACTION_BUTTON_RESIZE = "REACTION_BUTTON_RESIZE"

    const val ZOOM_START = "ZOOM_START"
    const val ZOOM_SCALE = "ZOOM_SCALE" // value = scale * 1000
    const val ZOOM_END = "ZOOM_END"
    const val ZOOMED_DWELL = "ZOOMED_DWELL"
    const val PAN_DISTANCE = "PAN_DISTANCE" // value = movement in pixels
    const val PAN_POINT = "PAN_POINT"       // x/y = final translation

    const val VIDEO_PLAY = "VIDEO_PLAY"
    const val VIDEO_PAUSE = "VIDEO_PAUSE"
    const val VIDEO_WATCH_DWELL = "VIDEO_WATCH_DWELL"
    const val VIDEO_SEEK = "VIDEO_SEEK"
    const val VIDEO_REPLAY = "VIDEO_REPLAY"
    const val VIDEO_SCRUB_START = "VIDEO_SCRUB_START"
    const val VIDEO_SCRUB_END = "VIDEO_SCRUB_END"

    const val FAVORITE_SET = "FAVORITE_SET"
    const val FAVORITE_UNSET = "FAVORITE_UNSET"

    // Explicit ground truth. Never synthesized by the inference engine.
    const val CONFIRMED_NUT = "CONFIRMED_NUT"
    const val COMPLETION_CONFIRMED = CONFIRMED_NUT

    // Explicit subjective declarations.
    const val SPIRITUAL_COOM = "SPIRITUAL_COOM"
    const val INSTANT_HARD = "INSTANT_HARD"
    const val EDGE_MARK = "EDGE_MARK"
}
