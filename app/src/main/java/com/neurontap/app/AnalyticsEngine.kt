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
            val zoomedMs = rows.filter { it.type == EventTypes.ZOOMED_DWELL }.sumOf { it.value ?: 0L }
            val seeks = rows.count { it.type == EventTypes.VIDEO_SEEK }
            val replays = rows.count { it.type == EventTypes.VIDEO_REPLAY }
            val edge = rows.count { it.type == EventTypes.EDGE_MARK }
            val spiritual = rows.count { it.type == EventTypes.SPIRITUAL_COOM }
            val hard = rows.count { it.type == EventTypes.INSTANT_HARD }
            val firstSignal = rows.firstOrNull { it.type == EventTypes.REACTION_DOWN || it.type == EventTypes.INSTANT_HARD || it.type == EventTypes.EDGE_MARK }?.timestampMs
                ?: rows.firstOrNull()?.timestampMs
            val lastSignal = rows.lastOrNull { it.type in setOf(EventTypes.REACTION_UP, EventTypes.SPIRITUAL_COOM, EventTypes.EDGE_MARK, EventTypes.VIDEO_SEEK) }?.timestampMs
                ?: rows.lastOrNull()?.timestampMs
            val secondsSinceLast = ((confirmedAt - (lastSignal ?: confirmedAt)).coerceAtLeast(0L)) / 1000.0
            val proximity = 10.0 * exp(-secondsSinceLast / 140.0)
            val score = taps * 3.0 + ln(1.0 + dwellMs / 1000.0) * 2.0 + ln(1.0 + zoomedMs / 1000.0) +
                seeks * 1.4 + replays * 2.1 + edge * 5.0 + spiritual * 7.0 + hard * 4.0 + proximity
            Candidate(mediaId, score, firstSignal, lastSignal)
        }.sortedByDescending { it.score }

        val best = candidates.first()
        val second = candidates.getOrNull(1)?.score ?: 0.0
        val margin = (best.score - second).coerceAtLeast(0.0)
        val confidence = (0.52 + 0.43 * (1.0 - exp(-margin / 9.0))).coerceIn(0.52, 0.95)
        return FinishInference(
            best.mediaId,
            confidence,
            best.firstSignal?.coerceAtLeast(confirmedAt - 45 * 60 * 1000L),
            best.lastSignal?.coerceAtMost(confirmedAt) ?: confirmedAt
        )
    }

    fun inferPotentialNuts(db: NeuronDb, limit: Int = 500, sinceMs: Long? = null): List<PotentialNutCandidate> =
        db.sessionsForInference(limit, sinceMs)
            .asSequence()
            .filter { !it.confirmedNut }
            .mapNotNull { inferPotentialNutForSession(db, it) }
            .sortedByDescending { it.confidence }
            .toList()

    private fun inferPotentialNutForSession(db: NeuronDb, session: SessionRow): PotentialNutCandidate? {
        val rows = db.eventsForSession(session.id)
        val mediaRows = rows.filter { it.mediaId != null }
        if (mediaRows.isEmpty()) return null
        val sessionEnd = session.endedAt ?: rows.lastOrNull { it.type == EventTypes.APP_BACKGROUND }?.timestampMs ?: return null

        data class Evidence(
            val id: Long,
            val raw: Double,
            val taps: Int,
            val burstPairs: Int,
            val dwellMs: Long,
            val zoomedMs: Long,
            val seeks: Int,
            val spiritual: Int,
            val hard: Int,
            val edge: Int,
            val lastSignal: Long,
            val firstSignal: Long
        )

        val evidence = mediaRows.groupBy { it.mediaId!! }.map { (mediaId, r) ->
            val tapRows = r.filter { it.type == EventTypes.REACTION_UP }.sortedBy { it.timestampMs }
            val taps = tapRows.size
            val burstPairs = tapRows.zipWithNext().count { (a, b) -> b.timestampMs - a.timestampMs <= 1100L }
            val dwellMs = r.filter { it.type == EventTypes.VIEW_DWELL }.sumOf { it.value ?: 0L }
            val zoomedMs = r.filter { it.type == EventTypes.ZOOMED_DWELL }.sumOf { it.value ?: 0L }
            val seeks = r.count { it.type == EventTypes.VIDEO_SEEK }
            val spiritual = r.count { it.type == EventTypes.SPIRITUAL_COOM }
            val hard = r.count { it.type == EventTypes.INSTANT_HARD }
            val edge = r.count { it.type == EventTypes.EDGE_MARK }
            val first = r.first().timestampMs
            val last = r.last().timestampMs
            val secondsFromEnd = ((sessionEnd - last).coerceAtLeast(0L)) / 1000.0
            val endProximity = 1.4 * exp(-secondsFromEnd / 90.0)
            val raw = taps * 0.08 + burstPairs * 0.12 + ln(1.0 + dwellMs / 1000.0) * 0.34 +
                ln(1.0 + zoomedMs / 1000.0) * 0.13 + seeks * 0.10 + spiritual * 1.0 + hard * 0.42 + edge * 0.88 + endProximity
            Evidence(mediaId, raw, taps, burstPairs, dwellMs, zoomedMs, seeks, spiritual, hard, edge, last, first)
        }.sortedByDescending { it.raw }

        val best = evidence.first()
        val enoughSignal = best.taps >= 8 || best.spiritual > 0 || best.edge > 0 || best.dwellMs >= 100_000L || (best.hard > 0 && best.taps >= 4)
        if (!enoughSignal) return null
        val confidence = logistic(best.raw - 2.65).coerceIn(0.05, 0.97)
        if (confidence < 0.60) return null

        val bits = buildList {
            if (best.taps > 0) add("${best.taps} reaction taps")
            if (best.burstPairs > 0) add("${best.burstPairs} rapid tap pairs")
            if (best.dwellMs >= 1000) add("${best.dwellMs / 1000}s viewed")
            if (best.zoomedMs >= 1000) add("${best.zoomedMs / 1000}s zoomed in")
            if (best.seeks > 0) add("${best.seeks} video seeks")
            if (best.spiritual > 0) add("${best.spiritual} Spiritual Coom")
            if (best.hard > 0) add("${best.hard} instant-hard mark")
            if (best.edge > 0) add("${best.edge} edge mark")
            val sec = ((sessionEnd - best.lastSignal).coerceAtLeast(0L)) / 1000
            if (sec <= 180) add("strong activity ended ${sec}s before the session stopped")
        }

        return PotentialNutCandidate(
            session.id,
            best.id,
            db.mediaById(best.id)?.name,
            confidence,
            best.firstSignal.coerceAtLeast(sessionEnd - 45 * 60 * 1000L),
            best.lastSignal.coerceAtMost(sessionEnd),
            bits.joinToString(" · ")
        )
    }

    fun smartGalleries(
        db: NeuronDb,
        summaries: List<MediaBehaviorSummary>,
        potential: List<PotentialNutCandidate>,
        sinceMs: Long? = null
    ): List<SmartGallery> {
        fun gallery(id: String, title: String, subtitle: String, sorted: List<MediaBehaviorSummary>, take: Int = 100): SmartGallery? {
            val ids = sorted.map { it.mediaId }.distinct().take(take)
            return if (ids.isEmpty()) null else SmartGallery(id, title, subtitle, ids)
        }

        val result = mutableListOf<SmartGallery>()
        gallery("blue_balls", "Biggest Blue Balls", "Huge signals, zero confirmed nut. The archive has questions.", summaries.filter { it.confirmedNuts == 0 && it.blueBallsScore > 0 }.sortedByDescending { it.blueBallsScore })?.let(result::add)
        gallery("confirmed", "Confirmed Nut Hall of Fame", "Ground truth only. No accusations allowed.", summaries.filter { it.confirmedNuts > 0 }.sortedWith(compareByDescending<MediaBehaviorSummary> { it.confirmedNuts }.thenByDescending { it.attractionScore }))?.let(result::add)
        gallery("spiritual", "Most Spiritually Coomed", "Images that crossed the 'I could bust right now' threshold.", summaries.filter { it.spiritualCooms > 0 }.sortedWith(compareByDescending<MediaBehaviorSummary> { it.spiritualCooms }.thenByDescending { it.attractionScore }))?.let(result::add)
        gallery("edge", "Edge Magnets", "Most associated with deliberate danger-zone declarations.", summaries.filter { it.edgeMarks > 0 }.sortedWith(compareByDescending<MediaBehaviorSummary> { it.edgeMarks }.thenByDescending { it.dwellMs }))?.let(result::add)
        gallery("explored", "Most Thoroughly Inspected", "Zooming, panning, replaying, scrubbing: doctoral-level appreciation.", summaries.filter { it.explorationScore > 0 }.sortedByDescending { it.explorationScore })?.let(result::add)
        gallery("returned", "Can't Stop Coming Back", "Most repeat openings beyond their first visit in a session.", summaries.filter { it.returnCount > 0 }.sortedWith(compareByDescending<MediaBehaviorSummary> { it.returnCount }.thenByDescending { it.attractionScore }))?.let(result::add)
        gallery("fastest", "Fastest Neuron Activation", "Lowest first-reaction latency.", summaries.filter { it.quickestTapMs != null }.sortedBy { it.quickestTapMs })?.let(result::add)
        gallery("longest", "Longest Stares", "Ranked by total dwell in the selected period.", summaries.filter { it.dwellMs > 0 }.sortedByDescending { it.dwellMs })?.let(result::add)
        gallery("taps", "Most Button Abuse", "The flaming heart took the most punishment here.", summaries.filter { it.taps > 0 }.sortedByDescending { it.taps })?.let(result::add)
        gallery("video", "Most Scrubbed & Replayed", "Video moments you kept going back to inspect.", summaries.filter { it.videoSeeks + it.videoReplays > 0 }.sortedByDescending { it.videoSeeks * 2 + it.videoReplays * 4 })?.let(result::add)
        gallery("reliable", "Reliable Nuclear Options", "High confirmed conversion with repeated use.", summaries.filter { it.confirmedNuts > 0 && it.views > 0 }.sortedWith(compareByDescending<MediaBehaviorSummary> { it.conversionRate }.thenByDescending { it.confirmedNuts }))?.let(result::add)

        val potentialIds = potential.mapNotNull { it.primaryMediaId }.distinct()
        if (potentialIds.isNotEmpty()) result += SmartGallery("potential", "Potential Nuts", "Unconfirmed accusations ranked by the calculator.", potentialIds)

        val now = System.currentTimeMillis()
        val recentStart = maxOf(sinceMs ?: 0L, now - 30L * 24 * 60 * 60 * 1000)
        val recent = db.behaviorSummaries(recentStart).associateBy { it.mediaId }
        val prior = db.behaviorSummaries(now - 60L * 24 * 60 * 60 * 1000, recentStart).associateBy { it.mediaId }
        val rising = summaries.mapNotNull { s ->
            val r = recent[s.mediaId]?.attractionScore ?: 0.0
            val p = prior[s.mediaId]?.attractionScore ?: 0.0
            if (r >= 5.0 && r > p * 1.35 + 2.0) s to (r - p) else null
        }.sortedByDescending { it.second }.map { it.first }
        gallery("rising", "Rising Lately", "Behavior that has heated up relative to the previous month.", rising)?.let(result::add)

        return result
    }

    fun generateInsights(summaries: List<MediaBehaviorSummary>, potential: List<PotentialNutCandidate>): List<String> {
        if (summaries.isEmpty()) return listOf("The archive is still empty. Go create evidence.")
        val top = summaries.maxByOrNull { it.attractionScore }
        val explorer = summaries.maxByOrNull { it.explorationScore }
        val returned = summaries.maxByOrNull { it.returnCount }
        val fastest = summaries.filter { it.quickestTapMs != null }.minByOrNull { it.quickestTapMs!! }
        val confirmed = summaries.sumOf { it.confirmedNuts }
        val spiritual = summaries.sumOf { it.spiritualCooms }
        val edge = summaries.sumOf { it.edgeMarks }
        return buildList {
            top?.let { add("Highest combined behavioral signal: ${it.name} — ${it.taps} taps, ${it.returnCount} returns, ${formatSeconds(it.dwellMs)} viewed.") }
            explorer?.takeIf { it.explorationScore > 0 }?.let { add("Most intensely explored: ${it.name} — max zoom ${"%.1f".format(it.maxZoomMilli / 1000.0)}×, ${formatSeconds(it.zoomedDwellMs)} zoomed, ${it.videoSeeks} seeks.") }
            returned?.takeIf { it.returnCount > 0 }?.let { add("Most persistent return magnet: ${it.name} — ${it.returnCount} repeat openings beyond session-first views.") }
            fastest?.let { add("Fastest recorded neuron activation: ${it.name} at ${it.quickestTapMs}ms.") }
            if (spiritual > confirmed && spiritual > 0) add("Spiritual Coom marks outnumber confirmed nuts $spiritual to $confirmed. Apparently 'could' and 'did' are meaningfully different states.")
            if (edge > 0) add("You explicitly marked the edge $edge time${if (edge == 1) "" else "s"}; those moments are now anchors for future automatic edge-pattern inference.")
            if (potential.isNotEmpty()) add("The potential-nut calculator currently has ${potential.size} unconfirmed accusation${if (potential.size == 1) "" else "s"}. Confirmed nuts remain a separate ground-truth category.")
        }.take(8)
    }

    private fun formatSeconds(ms: Long): String = if (ms < 60_000) "${ms / 1000}s" else "${ms / 60_000}m ${(ms / 1000) % 60}s"
    private fun logistic(x: Double): Double = 1.0 / (1.0 + exp(-x))
}
