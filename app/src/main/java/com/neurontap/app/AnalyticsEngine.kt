package com.neurontap.app

import kotlin.math.exp
import kotlin.math.ln

object AnalyticsEngine {
    fun inferFinish(events: List<EventRow>, confirmedAt: Long): FinishInference {
        val byMedia = events.filter { it.mediaId != null }.groupBy { it.mediaId!! }
        if (byMedia.isEmpty()) return FinishInference(null, 0.0, null, null)

        data class Candidate(val mediaId: Long, val score: Double, val firstSignal: Long?, val lastSignal: Long?)

        val candidates = byMedia.map { (mediaId, rows) ->
            val taps = rows.count { it.type == EventTypes.REACTION_UP }
            val dwellMs = rows.filter { it.type == EventTypes.VIEW_DWELL }.sumOf { it.value ?: 0L }
            val seeks = rows.count { it.type == EventTypes.VIDEO_SEEK }
            val firstReaction = rows.firstOrNull { it.type == EventTypes.REACTION_DOWN }?.timestampMs
            val lastReaction = rows.lastOrNull { it.type == EventTypes.REACTION_UP }?.timestampMs
            val lastAny = rows.lastOrNull()?.timestampMs
            val secondsSinceLast = ((confirmedAt - (lastReaction ?: lastAny ?: confirmedAt)).coerceAtLeast(0L)) / 1000.0
            val proximity = 8.0 * exp(-secondsSinceLast / 180.0)
            val score = taps * 3.0 + ln(1.0 + dwellMs / 1000.0) * 2.0 + seeks * 1.5 + proximity
            Candidate(mediaId, score, firstReaction ?: rows.firstOrNull()?.timestampMs, lastReaction ?: lastAny)
        }.sortedByDescending { it.score }

        val best = candidates.first()
        val second = candidates.getOrNull(1)?.score ?: 0.0
        val margin = (best.score - second).coerceAtLeast(0.0)
        val confidence = (0.50 + 0.45 * (1.0 - exp(-margin / 8.0))).coerceIn(0.50, 0.95)
        val windowStart = best.firstSignal?.coerceAtLeast(confirmedAt - 30 * 60 * 1000L)
        val windowEnd = best.lastSignal?.coerceAtMost(confirmedAt) ?: confirmedAt
        return FinishInference(best.mediaId, confidence, windowStart, windowEnd)
    }
}
