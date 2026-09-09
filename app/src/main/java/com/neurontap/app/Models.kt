package com.neurontap.app

data class MediaItem(
    val id: Long,
    val rootUri: String,
    val uri: String,
    val name: String,
    val mime: String,
    val size: Long,
    val modified: Long
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

data class WrappedStats(
    val taps: Int = 0,
    val sessions: Int = 0,
    val finishes: Int = 0,
    val quickestFirstTapMs: Long? = null,
    val longestDwellMs: Long? = null,
    val mostActiveHour: Int? = null,
    val topMedia: List<MediaScore> = emptyList()
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
    const val APP_BACKGROUND = "APP_BACKGROUND"
    const val APP_FOREGROUND = "APP_FOREGROUND"
    const val COMPLETION_CONFIRMED = "COMPLETION_CONFIRMED"
}
