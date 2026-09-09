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
    val mediaPositionMs: Long?
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

data class MediaScore(
    val mediaId: Long,
    val name: String,
    val taps: Int,
    val dwellMs: Long,
    val sessionCount: Int,
    val finishCount: Int,
    val score: Double
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

data class WrappedStats(
    val taps: Int = 0,
    val sessions: Int = 0,
    val finishes: Int = 0,
    val potentialNuts: Int = 0,
    val spiritualCooms: Int = 0,
    val instantHardMarks: Int = 0,
    val edgeMarks: Int = 0,
    val quickestFirstTapMs: Long? = null,
    val longestDwellMs: Long? = null,
    val mostActiveHour: Int? = null,
    val topMedia: List<MediaScore> = emptyList(),
    val potentialNutCandidates: List<PotentialNutCandidate> = emptyList()
)

object EventTypes {
    const val SESSION_START = "SESSION_START"
    const val SESSION_END = "SESSION_END"
    const val VIEW_START = "VIEW_START"
    const val VIEW_DWELL = "VIEW_DWELL"
    const val REACTION_DOWN = "REACTION_DOWN"
    const val REACTION_UP = "REACTION_UP"
    const val FIRST_TAP_LATENCY = "FIRST_TAP_LATENCY"
    const val VIDEO_PLAY = "VIDEO_PLAY"
    const val VIDEO_PAUSE = "VIDEO_PAUSE"
    const val VIDEO_SEEK = "VIDEO_SEEK"
    const val VIDEO_REPLAY = "VIDEO_REPLAY"
    const val APP_BACKGROUND = "APP_BACKGROUND"
    const val APP_FOREGROUND = "APP_FOREGROUND"

    // Explicit, user-declared ground truth. Never silently synthesize this event.
    const val CONFIRMED_NUT = "CONFIRMED_NUT"
    const val COMPLETION_CONFIRMED = CONFIRMED_NUT

    // High-value subjective markers.
    const val SPIRITUAL_COOM = "SPIRITUAL_COOM"
    const val INSTANT_HARD = "INSTANT_HARD"
    const val EDGE_MARK = "EDGE_MARK"

    // Viewer telemetry. Values are deliberately raw enough to reinterpret later.
    const val UI_SHOWN = "UI_SHOWN"
    const val UI_HIDDEN = "UI_HIDDEN"
    const val ZOOM_START = "ZOOM_START"
    const val ZOOM_SCALE = "ZOOM_SCALE"       // value = scale * 1000
    const val ZOOM_END = "ZOOM_END"
    const val PAN_DISTANCE = "PAN_DISTANCE"   // value = movement in pixels
    const val GALLERY_OPEN = "GALLERY_OPEN"
    const val GALLERY_SCROLL = "GALLERY_SCROLL"
    const val FAVORITE_SET = "FAVORITE_SET"
    const val FAVORITE_UNSET = "FAVORITE_UNSET"
}
