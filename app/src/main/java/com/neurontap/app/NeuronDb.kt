package com.neurontap.app

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import java.security.MessageDigest

class NeuronDb(context: Context) : SQLiteOpenHelper(context, "neurontap.db", null, 4) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE media(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                root_uri TEXT NOT NULL,
                uri TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                mime TEXT NOT NULL,
                size INTEGER NOT NULL DEFAULT 0,
                modified INTEGER NOT NULL DEFAULT 0,
                indexed_at INTEGER NOT NULL,
                favorite INTEGER NOT NULL DEFAULT 0,
                deleted INTEGER NOT NULL DEFAULT 0
            )""".trimIndent()
        )
        db.execSQL(
            """CREATE TABLE sessions(
                id TEXT PRIMARY KEY,
                started_at INTEGER NOT NULL,
                ended_at INTEGER,
                finish_confirmed INTEGER NOT NULL DEFAULT 0,
                finish_confirmed_at INTEGER,
                inferred_primary_media_id INTEGER,
                inference_confidence REAL,
                inferred_window_start INTEGER,
                inferred_window_end INTEGER
            )""".trimIndent()
        )
        db.execSQL(
            """CREATE TABLE events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                media_id INTEGER,
                type TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                value INTEGER,
                media_position_ms INTEGER,
                x REAL,
                y REAL,
                details TEXT
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX idx_events_session_time ON events(session_id, timestamp_ms)")
        db.execSQL("CREATE INDEX idx_events_media_type ON events(media_id, type)")
        db.execSQL("CREATE INDEX idx_events_type_time ON events(type, timestamp_ms)")
        db.execSQL(
            """CREATE TABLE media_tags(
                media_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY(media_id, tag)
            )""".trimIndent()
        )
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) db.execSQL("ALTER TABLE media ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0")
        if (oldVersion < 3) {
            db.execSQL("ALTER TABLE events ADD COLUMN x REAL")
            db.execSQL("ALTER TABLE events ADD COLUMN y REAL")
            db.execSQL("ALTER TABLE events ADD COLUMN details TEXT")
        }
        if (oldVersion < 4) {
            db.execSQL("ALTER TABLE media ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0")
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(type, timestamp_ms)")
        }
    }

    fun runMediaBatch(block: () -> Unit) {
        val db = writableDatabase
        db.beginTransaction()
        try { block(); db.setTransactionSuccessful() } finally { db.endTransaction() }
    }

    fun upsertMedia(rootUri: String, uri: String, name: String, mime: String, size: Long, modified: Long): Long {
        val db = writableDatabase
        val values = ContentValues().apply {
            put("root_uri", rootUri); put("uri", uri); put("display_name", name); put("mime", mime)
            put("size", size); put("modified", modified); put("indexed_at", System.currentTimeMillis()); put("deleted", 0)
        }
        db.insertWithOnConflict("media", null, values, SQLiteDatabase.CONFLICT_IGNORE)
        db.update("media", values, "uri=?", arrayOf(uri))
        return db.rawQuery("SELECT id FROM media WHERE uri=?", arrayOf(uri)).use { c -> if (c.moveToFirst()) c.getLong(0) else -1L }
    }

    fun loadAllMedia(): List<MediaItem> = readableDatabase.rawQuery(
        "SELECT id,root_uri,uri,display_name,mime,size,modified,favorite FROM media WHERE deleted=0 ORDER BY modified DESC,display_name COLLATE NOCASE", null
    ).use { c -> buildList { while (c.moveToNext()) add(c.toMediaItem()) } }

    fun loadMedia(rootUri: String): List<MediaItem> = readableDatabase.rawQuery(
        "SELECT id,root_uri,uri,display_name,mime,size,modified,favorite FROM media WHERE deleted=0 AND root_uri=? ORDER BY modified DESC,display_name COLLATE NOCASE",
        arrayOf(rootUri)
    ).use { c -> buildList { while (c.moveToNext()) add(c.toMediaItem()) } }

    fun loadMediaByIds(ids: List<Long>): List<MediaItem> = ids.mapNotNull(::mediaById)

    fun mediaById(id: Long): MediaItem? = readableDatabase.rawQuery(
        "SELECT id,root_uri,uri,display_name,mime,size,modified,favorite FROM media WHERE id=?", arrayOf(id.toString())
    ).use { c -> if (c.moveToFirst()) c.toMediaItem() else null }

    fun setFavorite(mediaId: Long, favorite: Boolean) {
        writableDatabase.update("media", ContentValues().apply { put("favorite", if (favorite) 1 else 0) }, "id=?", arrayOf(mediaId.toString()))
    }

    fun markMediaDeleted(mediaId: Long) {
        writableDatabase.update("media", ContentValues().apply { put("deleted", 1) }, "id=?", arrayOf(mediaId.toString()))
    }

    fun deleteMedia(mediaId: Long) = markMediaDeleted(mediaId)
    fun deleteRoot(rootUri: String) { writableDatabase.delete("media", "root_uri=?", arrayOf(rootUri)) }

    fun startSession(id: String, now: Long) {
        writableDatabase.insertWithOnConflict("sessions", null, ContentValues().apply { put("id", id); put("started_at", now) }, SQLiteDatabase.CONFLICT_IGNORE)
    }

    fun endSession(id: String, now: Long) {
        writableDatabase.update("sessions", ContentValues().apply { put("ended_at", now) }, "id=?", arrayOf(id))
        logEvent(id, null, EventTypes.SESSION_END, now)
    }

    fun logEvent(
        sessionId: String,
        mediaId: Long?,
        type: String,
        timestampMs: Long,
        value: Long? = null,
        mediaPositionMs: Long? = null,
        x: Double? = null,
        y: Double? = null,
        details: String? = null
    ) {
        val values = ContentValues().apply {
            put("session_id", sessionId)
            if (mediaId == null) putNull("media_id") else put("media_id", mediaId)
            put("type", type); put("timestamp_ms", timestampMs)
            if (value == null) putNull("value") else put("value", value)
            if (mediaPositionMs == null) putNull("media_position_ms") else put("media_position_ms", mediaPositionMs)
            if (x == null) putNull("x") else put("x", x)
            if (y == null) putNull("y") else put("y", y)
            if (details == null) putNull("details") else put("details", details)
        }
        writableDatabase.insert("events", null, values)
    }

    fun confirmFinish(sessionId: String, now: Long, mediaId: Long? = null, mediaPositionMs: Long? = null) {
        writableDatabase.update(
            "sessions",
            ContentValues().apply { put("finish_confirmed", 1); put("finish_confirmed_at", now) },
            "id=?", arrayOf(sessionId)
        )
        logEvent(sessionId, mediaId, EventTypes.CONFIRMED_NUT, now, mediaPositionMs = mediaPositionMs)
    }

    fun saveInference(sessionId: String, inference: FinishInference) {
        val values = ContentValues().apply {
            if (inference.mediaId == null) putNull("inferred_primary_media_id") else put("inferred_primary_media_id", inference.mediaId)
            put("inference_confidence", inference.confidence)
            if (inference.windowStartMs == null) putNull("inferred_window_start") else put("inferred_window_start", inference.windowStartMs)
            if (inference.windowEndMs == null) putNull("inferred_window_end") else put("inferred_window_end", inference.windowEndMs)
        }
        writableDatabase.update("sessions", values, "id=?", arrayOf(sessionId))
    }

    fun eventsForSession(sessionId: String): List<EventRow> = readableDatabase.rawQuery(
        "SELECT id,session_id,media_id,type,timestamp_ms,value,media_position_ms,x,y,details FROM events WHERE session_id=? ORDER BY timestamp_ms,id",
        arrayOf(sessionId)
    ).use(::readEvents)

    fun eventsForMedia(mediaId: Long, sinceMs: Long? = null, limit: Int = 1000): List<EventRow> {
        val where = if (sinceMs != null) "media_id=? AND timestamp_ms>=?" else "media_id=?"
        val args = if (sinceMs != null) arrayOf(mediaId.toString(), sinceMs.toString(), limit.toString()) else arrayOf(mediaId.toString(), limit.toString())
        return readableDatabase.rawQuery(
            "SELECT id,session_id,media_id,type,timestamp_ms,value,media_position_ms,x,y,details FROM events WHERE $where ORDER BY timestamp_ms DESC,id DESC LIMIT ?",
            args
        ).use(::readEvents)
    }

    private fun readEvents(c: Cursor): List<EventRow> = buildList {
        while (c.moveToNext()) add(
            EventRow(
                id = c.getLong(0), sessionId = c.getString(1), mediaId = if (c.isNull(2)) null else c.getLong(2), type = c.getString(3),
                timestampMs = c.getLong(4), value = if (c.isNull(5)) null else c.getLong(5), mediaPositionMs = if (c.isNull(6)) null else c.getLong(6),
                x = if (c.isNull(7)) null else c.getDouble(7), y = if (c.isNull(8)) null else c.getDouble(8), details = if (c.isNull(9)) null else c.getString(9)
            )
        )
    }

    fun sessionsForInference(limit: Int = 500, sinceMs: Long? = null): List<SessionRow> {
        val where = if (sinceMs != null) "WHERE started_at>=?" else ""
        val args = if (sinceMs != null) arrayOf(sinceMs.toString(), limit.toString()) else arrayOf(limit.toString())
        return readableDatabase.rawQuery(
            """SELECT id,started_at,ended_at,finish_confirmed,finish_confirmed_at,inferred_primary_media_id,inference_confidence,inferred_window_start,inferred_window_end
               FROM sessions $where ORDER BY started_at DESC LIMIT ?""".trimIndent(), args
        ).use { c -> buildList {
            while (c.moveToNext()) add(SessionRow(
                c.getString(0), c.getLong(1), if (c.isNull(2)) null else c.getLong(2), c.getInt(3) != 0,
                if (c.isNull(4)) null else c.getLong(4), if (c.isNull(5)) null else c.getLong(5), if (c.isNull(6)) null else c.getDouble(6),
                if (c.isNull(7)) null else c.getLong(7), if (c.isNull(8)) null else c.getLong(8)
            ))
        } }
    }

    fun addTag(mediaId: Long, tag: String) {
        val clean = tag.trim().lowercase(); if (clean.isBlank()) return
        writableDatabase.insertWithOnConflict("media_tags", null, ContentValues().apply { put("media_id", mediaId); put("tag", clean) }, SQLiteDatabase.CONFLICT_IGNORE)
    }

    fun tagsForMedia(mediaId: Long): List<String> = readableDatabase.rawQuery(
        "SELECT tag FROM media_tags WHERE media_id=? ORDER BY tag", arrayOf(mediaId.toString())
    ).use { c -> buildList { while (c.moveToNext()) add(c.getString(0)) } }

    fun countEvents(type: String, sinceMs: Long? = null): Int {
        val sql = if (sinceMs == null) "SELECT COUNT(*) FROM events WHERE type=?" else "SELECT COUNT(*) FROM events WHERE type=? AND timestamp_ms>=?"
        val args = if (sinceMs == null) arrayOf(type) else arrayOf(type, sinceMs.toString())
        return readableDatabase.rawQuery(sql, args).use { c -> if (c.moveToFirst()) c.getInt(0) else 0 }
    }

    fun behaviorSummaries(sinceMs: Long? = null, untilMs: Long? = null): List<MediaBehaviorSummary> {
        val joinConditions = buildString {
            append("e.media_id=m.id")
            if (sinceMs != null) append(" AND e.timestamp_ms>=?")
            if (untilMs != null) append(" AND e.timestamp_ms<?")
        }
        val args = buildList {
            if (sinceMs != null) add(sinceMs.toString())
            if (untilMs != null) add(untilMs.toString())
        }.toTypedArray()
        val sql = """
            SELECT m.id,m.display_name,
              SUM(CASE WHEN e.type='VIEW_START' THEN 1 ELSE 0 END),
              SUM(CASE WHEN e.type='REACTION_UP' THEN 1 ELSE 0 END),
              SUM(CASE WHEN e.type='VIEW_DWELL' THEN COALESCE(e.value,0) ELSE 0 END),
              COUNT(DISTINCT CASE WHEN e.id IS NOT NULL THEN e.session_id END),
              SUM(CASE WHEN e.type='CONFIRMED_NUT' THEN 1 ELSE 0 END),
              SUM(CASE WHEN e.type='SPIRITUAL_COOM' THEN 1 ELSE 0 END),
              SUM(CASE WHEN e.type='INSTANT_HARD' THEN 1 ELSE 0 END),
              SUM(CASE WHEN e.type='EDGE_MARK' THEN 1 ELSE 0 END),
              SUM(CASE WHEN e.type='ZOOM_START' THEN 1 ELSE 0 END),
              SUM(CASE WHEN e.type='ZOOM_SCALE' THEN 1 ELSE 0 END),
              MAX(CASE WHEN e.type='ZOOM_SCALE' THEN COALESCE(e.value,1000) ELSE 1000 END),
              SUM(CASE WHEN e.type='ZOOMED_DWELL' THEN COALESCE(e.value,0) ELSE 0 END),
              SUM(CASE WHEN e.type='PAN_DISTANCE' THEN COALESCE(e.value,0) ELSE 0 END),
              SUM(CASE WHEN e.type='VIDEO_SEEK' THEN 1 ELSE 0 END),
              SUM(CASE WHEN e.type='VIDEO_REPLAY' THEN 1 ELSE 0 END),
              SUM(CASE WHEN e.type='VIDEO_WATCH_DWELL' THEN COALESCE(e.value,0) ELSE 0 END),
              MIN(CASE WHEN e.type='FIRST_TAP_LATENCY' THEN e.value ELSE NULL END),
              MIN(e.timestamp_ms),MAX(e.timestamp_ms)
            FROM media m LEFT JOIN events e ON $joinConditions
            GROUP BY m.id HAVING COUNT(e.id)>0
        """.trimIndent()
        return readableDatabase.rawQuery(sql, args).use { c -> buildList {
            while (c.moveToNext()) add(MediaBehaviorSummary(
                mediaId = c.getLong(0), name = c.getString(1), views = c.getInt(2), taps = c.getInt(3), dwellMs = c.getLong(4), sessionCount = c.getInt(5),
                confirmedNuts = c.getInt(6), spiritualCooms = c.getInt(7), instantHardMarks = c.getInt(8), edgeMarks = c.getInt(9),
                zoomStarts = c.getInt(10), zoomSamples = c.getInt(11), maxZoomMilli = c.getLong(12), zoomedDwellMs = c.getLong(13), panDistancePx = c.getLong(14),
                videoSeeks = c.getInt(15), videoReplays = c.getInt(16), videoWatchMs = c.getLong(17), quickestTapMs = if (c.isNull(18)) null else c.getLong(18),
                firstSeenMs = if (c.isNull(19)) null else c.getLong(19), lastSeenMs = if (c.isNull(20)) null else c.getLong(20)
            ))
        } }
    }

    fun wrappedStats(sinceMs: Long? = null): WrappedStats {
        val summaries = behaviorSummaries(sinceMs)
        val potential = AnalyticsEngine.inferPotentialNuts(this, 500, sinceMs)
        val db = readableDatabase
        val sessionSql = if (sinceMs == null) "SELECT COUNT(*) FROM sessions" else "SELECT COUNT(*) FROM sessions WHERE started_at>=?"
        val sessionArgs = if (sinceMs == null) null else arrayOf(sinceMs.toString())
        val sessionCount = db.rawQuery(sessionSql, sessionArgs).use { c -> if (c.moveToFirst()) c.getInt(0) else 0 }
        val activeWhere = if (sinceMs == null) "type='REACTION_UP'" else "type='REACTION_UP' AND timestamp_ms>=?"
        val activeArgs = if (sinceMs == null) null else arrayOf(sinceMs.toString())
        val activeHour = db.rawQuery(
            "SELECT CAST(strftime('%H',timestamp_ms/1000,'unixepoch','localtime') AS INTEGER),COUNT(*) FROM events WHERE $activeWhere GROUP BY 1 ORDER BY 2 DESC LIMIT 1",
            activeArgs
        ).use { c -> if (c.moveToFirst()) c.getInt(0) else null }
        val fastest = summaries.mapNotNull { it.quickestTapMs }.minOrNull()
        val longest = summaries.maxOfOrNull { it.dwellMs }
        val galleries = AnalyticsEngine.smartGalleries(this, summaries, potential, sinceMs)
        val insights = AnalyticsEngine.generateInsights(summaries, potential)
        return WrappedStats(
            taps = summaries.sumOf { it.taps }, sessions = sessionCount, confirmedNuts = summaries.sumOf { it.confirmedNuts }, potentialNuts = potential.size,
            spiritualCooms = summaries.sumOf { it.spiritualCooms }, instantHardMarks = summaries.sumOf { it.instantHardMarks }, edgeMarks = summaries.sumOf { it.edgeMarks },
            totalDwellMs = summaries.sumOf { it.dwellMs }, totalZoomedMs = summaries.sumOf { it.zoomedDwellMs }, quickestFirstTapMs = fastest,
            longestDwellMs = longest, mostActiveHour = activeHour, summaries = summaries.sortedByDescending { it.attractionScore },
            potentialNutCandidates = potential.take(50), smartGalleries = galleries, insights = insights
        )
    }

    fun clearBehaviorHistory() {
        val db = writableDatabase; db.beginTransaction()
        try { db.delete("events", null, null); db.delete("sessions", null, null); db.setTransactionSuccessful() } finally { db.endTransaction() }
    }

    fun exportCsv(): String {
        val header = "event_id,session_id,media_id,type,timestamp_ms,value,media_position_ms,x,y,details\n"
        val rows = readableDatabase.rawQuery(
            "SELECT e.id,e.session_id,m.uri,e.type,e.timestamp_ms,e.value,e.media_position_ms,e.x,e.y,e.details FROM events e LEFT JOIN media m ON m.id=e.media_id ORDER BY e.timestamp_ms,e.id", null
        ).use { c -> buildString {
            while (c.moveToNext()) {
                append(c.getLong(0)).append(',').append(csv(c.getString(1))).append(',')
                append(if (c.isNull(2)) "" else "M" + shortHash(c.getString(2))).append(',').append(c.getString(3)).append(',').append(c.getLong(4)).append(',')
                append(if (c.isNull(5)) "" else c.getLong(5)).append(',').append(if (c.isNull(6)) "" else c.getLong(6)).append(',')
                append(if (c.isNull(7)) "" else c.getDouble(7)).append(',').append(if (c.isNull(8)) "" else c.getDouble(8)).append(',')
                append(if (c.isNull(9)) "" else csv(c.getString(9))).append('\n')
            }
        } }
        return header + rows
    }

    private fun Cursor.toMediaItem() = MediaItem(getLong(0), getString(1), getString(2), getString(3), getString(4), getLong(5), getLong(6), getInt(7) != 0)
    private fun shortHash(value: String): String = MessageDigest.getInstance("SHA-256").digest(value.toByteArray()).take(5).joinToString("") { "%02x".format(it) }
    private fun csv(value: String): String = "\"" + value.replace("\"", "\"\"") + "\""
}
