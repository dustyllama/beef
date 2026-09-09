package com.neurontap.app

import android.content.Context
import java.util.UUID

class AppController(private val context: Context, val db: NeuronDb) {
    private var sessionId: String? = null
    private var lastBackgroundAt: Long? = null
    private val sessionGapMs = 20 * 60 * 1000L

    fun currentSessionId(): String = ensureSession()

    fun onForeground() {
        val now = System.currentTimeMillis()
        val gap = lastBackgroundAt?.let { now - it } ?: Long.MAX_VALUE
        if (sessionId == null || gap >= sessionGapMs) {
            sessionId?.let { db.endSession(it, lastBackgroundAt ?: now) }
            sessionId = UUID.randomUUID().toString()
            db.startSession(sessionId!!, now)
            db.logEvent(sessionId!!, null, EventTypes.SESSION_START, now)
        }
        db.logEvent(sessionId!!, null, EventTypes.APP_FOREGROUND, now)
    }

    fun onBackground() {
        val now = System.currentTimeMillis()
        val id = ensureSession()
        db.logEvent(id, null, EventTypes.APP_BACKGROUND, now)
        lastBackgroundAt = now
    }

    fun log(mediaId: Long?, type: String, value: Long? = null, mediaPositionMs: Long? = null, at: Long = System.currentTimeMillis()) {
        db.logEvent(ensureSession(), mediaId, type, at, value, mediaPositionMs)
    }

    /**
     * A confirmed nut is ground truth supplied by the user. The optional mediaId records
     * what was actually on screen at confirmation time; the broader active window can
     * still be inferred separately from the raw event history.
     */
    fun confirmFinish(mediaId: Long? = null): Pair<FinishInference, MediaItem?> {
        val now = System.currentTimeMillis()
        val id = ensureSession()
        db.confirmFinish(id, now, mediaId)
        val inference = AnalyticsEngine.inferFinish(db.eventsForSession(id), now)
        db.saveInference(id, inference)
        val resolvedMediaId = mediaId ?: inference.mediaId
        return inference to resolvedMediaId?.let(db::mediaById)
    }

    fun markSpiritualCoom(mediaId: Long, mediaPositionMs: Long? = null) {
        log(mediaId, EventTypes.SPIRITUAL_COOM, mediaPositionMs = mediaPositionMs)
    }

    fun markInstantHard(mediaId: Long, mediaPositionMs: Long? = null) {
        log(mediaId, EventTypes.INSTANT_HARD, mediaPositionMs = mediaPositionMs)
    }

    fun markEdge(mediaId: Long, mediaPositionMs: Long? = null) {
        log(mediaId, EventTypes.EDGE_MARK, mediaPositionMs = mediaPositionMs)
    }

    private fun ensureSession(): String {
        if (sessionId == null) onForeground()
        return sessionId!!
    }
}
