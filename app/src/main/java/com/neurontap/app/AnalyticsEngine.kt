package com.neurontap.app

import kotlin.math.exp
import kotlin.math.ln

object AnalyticsEngine {
    fun inferFinish(events: List<EventRow>, confirmedAt: Long): FinishInference {
        val byMedia = events.filter { it.mediaId != null && it.type != EventTypes.CONFIRMED_NUT }.groupBy { it.mediaId!! }
        if (byMedia.isEmpty()) return FinishInference(null, 0.0, null, null)

        data class Candidate(val mediaId: Long, val score: Double, val firstSignal: Long?, val lastSignal: Long?)

        val candidates = byMedia.map { (mediaId, rows) ->
            val taps = rows.count { it.type == EventTypes.REACTION_UP }
            val dwellMs = rows.filter { it.type == EventTypes.VIEW_DWELL }.sumOf { it.value ?: 0L }
            val seeks = rows.count { it.type == EventTypes.VIDEO_SEEK }
            val edgeMarks = rows.count { it.type == EventTypes.EDGE_MARK }
            val spiritual = rows.count { it.type == EventTypes.SPIRITUAL_COOM }
            val firstReaction = rows.firstOrNull { it.type == EventTypes.REACTION_DOWN }?.timestampMs
            val lastReaction = rows.lastOrNull { it.type == EventTypes.REACTION_UP }?.timestampMs
            val lastAny = rows.lastOrNull()?.timestampMs
            val secondsSinceLast = ((confirmedAt - (lastReaction ?: lastAny ?: confirmedAt)).coerceAtLeast(0L)) / 1000.0
            val proximity = 8.0 * exp(-secondsSinceLast / 180.0)
            val score = taps * 3.0 + ln(1.0 + dwellMs / 1000.0) * 2.0 + seeks * 1.5 + edgeMarks * 4.0 + spiritual * 5.0 + proximity
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

    /**
     * Potential nuts are hypotheses only. They are never persisted as CONFIRMED_NUT and
     * never increment the bespoke confirmed count. Re-running this method with a better
     * model can reinterpret the same raw history later.
     */
    fun inferPotentialNuts(db: NeuronDb, limit: Int = 250): List<PotentialNutCandidate> {
        return db.sessionsForInference(limit)
            .asSequence()
            .filter { !it.confirmedNut }
            .mapNotNull { session -> inferPotentialNutForSession(db, session) }
            .sortedByDescending { it.confidence }
            .toList()
    }

    private fun inferPotentialNutForSession(db: NeuronDb, session: SessionRow): PotentialNutCandidate? {
        val rows = db.eventsForSession(session.id)
        val mediaRows = rows.filter { it.mediaId != null }
        if (mediaRows.isEmpty()) return null

        val sessionEnd = session.endedAt
            ?: rows.lastOrNull { it.type == EventTypes.APP_BACKGROUND }?.timestampMs
            ?: return null

        data class MediaEvidence(
            val id: Long,
            val raw: Double,
            val taps: Int,
            val dwellMs: Long,
            val spiritual: Int,
            val hard: Int,
            val edge: Int,
            val burstPairs: Int,
            val lastSignal: Long,
            val firstSignal: Long
        )

        val evidence = mediaRows.groupBy { it.mediaId!! }.map { (mediaId, r) ->
            val tapsRows = r.filter { it.type == EventTypes.REACTION_UP }.sortedBy { it.timestampMs }
            val taps = tapsRows.size
            val dwellMs = r.filter { it.type == EventTypes.VIEW_DWELL }.sumOf { it.value ?: 0L }
            val spiritual = r.count { it.type == EventTypes.SPIRITUAL_COOM }
            val hard = r.count { it.type == EventTypes.INSTANT_HARD }
            val edge = r.count { it.type == EventTypes.EDGE_MARK }
            val seeks = r.count { it.type == EventTypes.VIDEO_SEEK }
            val zoomEvents = r.count { it.type == EventTypes.ZOOM_SCALE || it.type == EventTypes.PAN_DISTANCE }
            val burstPairs = tapsRows.zipWithNext().count { (a, b) -> b.timestampMs - a.timestampMs <= 1200L }
            val firstSignal = r.first().timestampMs
            val lastSignal = r.last().timestampMs
            val secondsFromEnd = ((sessionEnd - lastSignal).coerceAtLeast(0L)) / 1000.0
            val endProximity = 1.15 * exp(-secondsFromEnd / 100.0)

            val raw =
                taps * 0.075 +
                ln(1.0 + dwellMs / 1000.0) * 0.33 +
                burstPairs * 0.10 +
                seeks * 0.08 +
                zoomEvents.coerceAtMost(20) * 0.025 +
                spiritual * 0.95 +
                hard * 0.40 +
                edge * 0.80 +
                endProximity

            MediaEvidence(mediaId, raw, taps, dwellMs, spiritual, hard, edge, burstPairs, lastSignal, firstSignal)
        }.sortedByDescending { it.raw }

        val best = evidence.first()
        val overallSignals = best.taps >= 7 || best.spiritual > 0 || best.edge > 0 || best.dwellMs >= 90_000L
        if (!overallSignals) return null

        val confidence = logistic(best.raw - 2.55).coerceIn(0.05, 0.96)
        if (confidence < 0.58) return null

        val evidenceBits = buildList {
            if (best.taps > 0) add("${best.taps} taps")
            if (best.burstPairs > 0) add("${best.burstPairs} rapid tap pairs")
            if (best.dwellMs >= 1000L) add("${best.dwellMs / 1000}s dwell")
            if (best.spiritual > 0) add("${best.spiritual} Spiritual Coom")
            if (best.hard > 0) add("${best.hard} instant-hard mark")
            if (best.edge > 0) add("${best.edge} edge mark")
            val secondsFromEnd = ((sessionEnd - best.lastSignal).coerceAtLeast(0L)) / 1000
            if (secondsFromEnd <= 180) add("last strong activity ${secondsFromEnd}s before session end")
        }

        return PotentialNutCandidate(
            sessionId = session.id,
            primaryMediaId = best.id,
            primaryMediaName = db.mediaById(best.id)?.name,
            confidence = confidence,
            windowStartMs = best.firstSignal.coerceAtLeast(sessionEnd - 30 * 60 * 1000L),
            windowEndMs = best.lastSignal.coerceAtMost(sessionEnd),
            evidence = evidenceBits.joinToString(" · ")
        )
    }

    private fun logistic(x: Double): Double = 1.0 / (1.0 + exp(-x))
}
