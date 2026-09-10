from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Version -----------------------------------------------------------------
p = ROOT / "app/build.gradle.kts"
s = p.read_text()
if "versionCode = 7" not in s or 'versionName = "0.7.0"' not in s:
    raise RuntimeError("v8 version anchors missing")
s = s.replace("versionCode = 7", "versionCode = 8", 1)
s = s.replace('versionName = "0.7.0"', 'versionName = "0.8.0"', 1)
p.write_text(s)

# Controller: all routine event persistence leaves the UI thread. A single
# channel consumer preserves event order without making Compose wait on SQLite.
p = ROOT / "app/src/main/java/com/neurontap/app/AppController.kt"
p.write_text(r'''package com.neurontap.app

import android.content.Context
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch

class AppController(private val context: Context, val db: NeuronDb) {
    private var sessionId: String? = null
    private var lastBackgroundAt: Long? = null
    private val sessionGapMs = 20 * 60 * 1000L

    private val ioScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val dbOps = Channel<() -> Unit>(Channel.UNLIMITED)

    init {
        ioScope.launch {
            for (op in dbOps) runCatching { op() }
        }
    }

    private fun enqueue(op: () -> Unit) {
        if (!dbOps.trySend(op).isSuccess) ioScope.launch { runCatching { op() } }
    }

    fun currentSessionId(): String = ensureSession()

    fun onForeground() {
        val now = System.currentTimeMillis()
        val gap = lastBackgroundAt?.let { now - it } ?: Long.MAX_VALUE
        if (sessionId == null || gap >= sessionGapMs) {
            val old = sessionId
            val oldEnd = lastBackgroundAt ?: now
            if (old != null) enqueue { db.endSession(old, oldEnd) }
            val fresh = UUID.randomUUID().toString()
            sessionId = fresh
            enqueue {
                db.startSession(fresh, now)
                db.logEvent(fresh, null, EventTypes.SESSION_START, now)
            }
        }
        val id = sessionId!!
        enqueue { db.logEvent(id, null, EventTypes.APP_FOREGROUND, now) }
    }

    fun onBackground() {
        val now = System.currentTimeMillis()
        val id = ensureSession()
        lastBackgroundAt = now
        enqueue { db.logEvent(id, null, EventTypes.APP_BACKGROUND, now) }
    }

    fun log(
        mediaId: Long?,
        type: String,
        value: Long? = null,
        mediaPositionMs: Long? = null,
        x: Double? = null,
        y: Double? = null,
        details: String? = null,
        at: Long = System.currentTimeMillis()
    ) {
        val id = ensureSession()
        enqueue { db.logEvent(id, mediaId, type, at, value, mediaPositionMs, x, y, details) }
    }

    /** Used only before operations that must immediately read their own event history. */
    private fun flushBlocking() {
        val latch = CountDownLatch(1)
        enqueue { latch.countDown() }
        latch.await(5, TimeUnit.SECONDS)
    }

    fun confirmFinish(mediaId: Long? = null, mediaPositionMs: Long? = null): Pair<FinishInference, MediaItem?> {
        flushBlocking()
        val now = System.currentTimeMillis()
        val id = ensureSession()
        db.confirmFinish(id, now, mediaId, mediaPositionMs)
        val inference = AnalyticsEngine.inferFinish(db.eventsForSession(id), now)
        db.saveInference(id, inference)
        val resolvedMediaId = mediaId ?: inference.mediaId
        return inference to resolvedMediaId?.let(db::mediaById)
    }

    fun markSpiritualCoom(mediaId: Long, mediaPositionMs: Long? = null) =
        log(mediaId, EventTypes.SPIRITUAL_COOM, mediaPositionMs = mediaPositionMs)

    fun markInstantHard(mediaId: Long, mediaPositionMs: Long? = null) =
        log(mediaId, EventTypes.INSTANT_HARD, mediaPositionMs = mediaPositionMs)

    fun markEdge(mediaId: Long, mediaPositionMs: Long? = null) =
        log(mediaId, EventTypes.EDGE_MARK, mediaPositionMs = mediaPositionMs)

    // Full Stroke is a declaration point, not homework that must be manually ended.
    fun startFullStroke(mediaId: Long, mediaPositionMs: Long? = null, details: String? = null) =
        log(mediaId, EventTypes.FULL_STROKE_MARK, mediaPositionMs = mediaPositionMs, details = details ?: "declared")

    // Kept for backwards compatibility with old event readers; v0.8 UI does not call it.
    fun endFullStroke(mediaId: Long?, mediaPositionMs: Long? = null, details: String? = null) =
        log(mediaId, EventTypes.FULL_STROKE_END, mediaPositionMs = mediaPositionMs, details = details)

    fun startGooning(mediaId: Long?, mediaPositionMs: Long? = null) =
        log(mediaId, EventTypes.GOON_START, mediaPositionMs = mediaPositionMs)

    fun endGooning(mediaId: Long?, mediaPositionMs: Long? = null, details: String? = null) =
        log(mediaId, EventTypes.GOON_END, mediaPositionMs = mediaPositionMs, details = details)

    private fun ensureSession(): String {
        if (sessionId == null) onForeground()
        return sessionId!!
    }
}
''')

# Move a couple of remaining direct viewer/gallery disk operations away from
# the main thread. UI state still updates immediately.
for rel in [
    "app/src/main/java/com/neurontap/app/GalleryUi.kt",
    "app/src/main/java/com/neurontap/app/ViewerUi.kt",
]:
    p = ROOT / rel
    s = p.read_text()
    s = s.replace("controller.db.setFavorite(item.id, next)", "scope.launch(Dispatchers.IO) { controller.db.setFavorite(item.id, next) }")
    s = s.replace("controller.db.setFavorite(current.id, next)", "scope.launch(Dispatchers.IO) { controller.db.setFavorite(current.id, next) }")
    if rel.endswith("ViewerUi.kt"):
        s = s.replace("dimensions = mediaDimensions(context, current)", "dimensions = withContext(Dispatchers.IO) { mediaDimensions(context, current) }")
    p.write_text(s)

print("Applied v8 performance pipeline")
