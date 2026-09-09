package com.neurontap.app

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import java.security.MessageDigest

class NeuronDb(context: Context) : SQLiteOpenHelper(context, "neurontap.db", null, 2) {
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
                favorite INTEGER NOT NULL DEFAULT 0
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
                media_position_ms INTEGER
            )""".trimIndent()
        )
        db.execSQL("CREATE INDEX idx_events_session_time ON events(session_id, timestamp_ms)")
        db.execSQL("CREATE INDEX idx_events_media_type ON events(media_id, type)")
        db.execSQL(
            """CREATE TABLE media_tags(
                media_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY(media_id, tag)
            )""".trimIndent()
        )
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) {
            db.execSQL("ALTER TABLE media ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0")
        }
    }

    fun runMediaBatch(block: () -> Unit) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            block()
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    fun upsertMedia(rootUri: String, uri: String, name: String, mime: String, size: Long, modified: Long): Long {
        val db = writableDatabase
        val values = ContentValues().apply {
            put("root_uri", rootUri)
            put("uri", uri)
            put("display_name", name)
            put("mime", mime)
            put("size", size)
            put("modified", modified)
            put("indexed_at", System.currentTimeMillis())
        }
        db.insertWithOnConflict("media", null, values, SQLiteDatabase.CONFLICT_IGNORE)
        db.update("media", values, "uri=?", arrayOf(uri))
        return db.rawQuery("SELECT id FROM media WHERE uri=?", arrayOf(uri)).use { c ->
            if (c.moveToFirst()) c.getLong(0) else -1L
        }
    }

    fun loadAllMedia(): List<MediaItem> = readableDatabase.rawQuery(
        "SELECT id,root_uri,uri,display_name,mime,size,modified,favorite FROM media ORDER BY modified DESC, display_name COLLATE NOCASE",
        null
    ).use { c -> buildList { while (c.moveToNext()) add(c.toMediaItem()) } }

    fun loadMedia(rootUri: String): List<MediaItem> = readableDatabase.rawQuery(
        "SELECT id,root_uri,uri,display_name,mime,size,modified,favorite FROM media WHERE root_uri=? ORDER BY modified DESC, display_name COLLATE NOCASE",
        arrayOf(rootUri)
    ).use { c -> buildList { while (c.moveToNext()) add(c.toMediaItem()) } }

    fun mediaById(id: Long): MediaItem? = readableDatabase.rawQuery(
        "SELECT id,root_uri,uri,display_name,mime,size,modified,favorite FROM media WHERE id=?", arrayOf(id.toString())
    ).use { c -> if (c.moveToFirst()) c.toMediaItem() else null }

    fun setFavorite(mediaId: Long, favorite: Boolean) {
        val values = ContentValues().apply { put("favorite", if (favorite) 1 else 0) }
        writableDatabase.update("media", values, "id=?", arrayOf(mediaId.toString()))
    }

    fun deleteMedia(mediaId: Long) {
        writableDatabase.delete("media", "id=?", arrayOf(mediaId.toString()))
    }

    fun deleteRoot(rootUri: String) {
        writableDatabase.delete("media", "root_uri=?", arrayOf(rootUri))
    }

    fun startSession(id: String, now: Long) {
        val values = ContentValues().apply { put("id", id); put("started_at", now) }
        writableDatabase.insertWithOnConflict("sessions", null, values, SQLiteDatabase.CONFLICT_IGNORE)
    }

    fun endSession(id: String, now: Long) {
        val values = ContentValues().apply { put("ended_at", now) }
        writableDatabase.update("sessions", values, "id=?", arrayOf(id))
    }

    fun logEvent(sessionId: String, mediaId: Long?, type: String, timestampMs: Long, value: Long? = null, mediaPositionMs: Long? = null) {
        val values = ContentValues().apply {
            put("session_id", sessionId)
            if (mediaId == null) putNull("media_id") else put("media_id", mediaId)
            put("type", type)
            put("timestamp_ms", timestampMs)
            if (value == null) putNull("value") else put("value", value)
            if (mediaPositionMs == null) putNull("media_position_ms") else put("media_position_ms", mediaPositionMs)
        }
        writableDatabase.insert("events", null, values)
    }

    fun confirmFinish(sessionId: String, now: Long) {
        val values = ContentValues().apply { put("finish_confirmed", 1); put("finish_confirmed_at", now) }
        writableDatabase.update("sessions", values, "id=?", arrayOf(sessionId))
        logEvent(sessionId, null, EventTypes.COMPLETION_CONFIRMED, now)
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
        "SELECT id,session_id,media_id,type,timestamp_ms,value,media_position_ms FROM events WHERE session_id=? ORDER BY timestamp_ms",
        arrayOf(sessionId)
    ).use { c ->
        buildList {
            while (c.moveToNext()) {
                add(EventRow(c.getLong(0), c.getString(1), if (c.isNull(2)) null else c.getLong(2), c.getString(3), c.getLong(4), if (c.isNull(5)) null else c.getLong(5), if (c.isNull(6)) null else c.getLong(6)))
            }
        }
    }

    fun addTag(mediaId: Long, tag: String) {
        val clean = tag.trim().lowercase()
        if (clean.isBlank()) return
        val values = ContentValues().apply { put("media_id", mediaId); put("tag", clean) }
        writableDatabase.insertWithOnConflict("media_tags", null, values, SQLiteDatabase.CONFLICT_IGNORE)
    }

    fun tagsForMedia(mediaId: Long): List<String> = readableDatabase.rawQuery(
        "SELECT tag FROM media_tags WHERE media_id=? ORDER BY tag", arrayOf(mediaId.toString())
    ).use { c -> buildList { while (c.moveToNext()) add(c.getString(0)) } }

    fun topMedia(limit: Int = 20): List<MediaScore> {
        val sql = """
            SELECT m.id, m.display_name,
              SUM(CASE WHEN e.type='REACTION_UP' THEN 1 ELSE 0 END) AS taps,
              SUM(CASE WHEN e.type='VIEW_DWELL' THEN COALESCE(e.value,0) ELSE 0 END) AS dwell,
              COUNT(DISTINCT e.session_id) AS session_count,
              (SELECT COUNT(*) FROM sessions s WHERE s.finish_confirmed=1 AND s.inferred_primary_media_id=m.id) AS finish_count
            FROM media m
            LEFT JOIN events e ON e.media_id=m.id
            GROUP BY m.id
            HAVING taps > 0 OR dwell > 0
            ORDER BY (taps * 3.0 + dwell/10000.0 + finish_count * 10.0 + session_count) DESC
            LIMIT ?
        """.trimIndent()
        return readableDatabase.rawQuery(sql, arrayOf(limit.toString())).use { c ->
            buildList {
                while (c.moveToNext()) {
                    val taps = c.getInt(2)
                    val dwell = c.getLong(3)
                    val sessions = c.getInt(4)
                    val finishes = c.getInt(5)
                    val score = taps * 3.0 + kotlin.math.ln(1.0 + dwell / 1000.0) * 2.0 + finishes * 10.0 + sessions
                    add(MediaScore(c.getLong(0), c.getString(1), taps, dwell, sessions, finishes, score))
                }
            }
        }
    }

    fun wrappedStats(): WrappedStats {
        val db = readableDatabase
        fun scalarLong(sql: String): Long? = db.rawQuery(sql, null).use { c -> if (c.moveToFirst() && !c.isNull(0)) c.getLong(0) else null }
        val taps = scalarLong("SELECT COUNT(*) FROM events WHERE type='REACTION_UP'")?.toInt() ?: 0
        val sessions = scalarLong("SELECT COUNT(*) FROM sessions")?.toInt() ?: 0
        val finishes = scalarLong("SELECT COUNT(*) FROM sessions WHERE finish_confirmed=1")?.toInt() ?: 0
        val fastest = scalarLong("SELECT MIN(value) FROM events WHERE type='FIRST_TAP_LATENCY'")
        val longest = scalarLong("SELECT MAX(value) FROM events WHERE type='VIEW_DWELL'")
        val activeHour = db.rawQuery(
            """SELECT CAST(strftime('%H', timestamp_ms/1000, 'unixepoch', 'localtime') AS INTEGER) h, COUNT(*) c
               FROM events WHERE type='REACTION_UP' GROUP BY h ORDER BY c DESC LIMIT 1""",
            null
        ).use { c -> if (c.moveToFirst()) c.getInt(0) else null }
        return WrappedStats(taps, sessions, finishes, fastest, longest, activeHour, topMedia(10))
    }

    fun clearBehaviorHistory() {
        writableDatabase.beginTransaction()
        try {
            writableDatabase.delete("events", null, null)
            writableDatabase.delete("sessions", null, null)
            writableDatabase.setTransactionSuccessful()
        } finally {
            writableDatabase.endTransaction()
        }
    }

    fun exportCsv(): String {
        val header = "event_id,session_id,media_id,type,timestamp_ms,value,media_position_ms\n"
        val rows = readableDatabase.rawQuery(
            """SELECT e.id,e.session_id,m.uri,e.type,e.timestamp_ms,e.value,e.media_position_ms
               FROM events e LEFT JOIN media m ON m.id=e.media_id ORDER BY e.timestamp_ms""", null
        ).use { c ->
            buildString {
                while (c.moveToNext()) {
                    append(c.getLong(0)).append(',')
                    append(csv(c.getString(1))).append(',')
                    append(if (c.isNull(2)) "" else "M" + shortHash(c.getString(2))).append(',')
                    append(c.getString(3)).append(',')
                    append(c.getLong(4)).append(',')
                    append(if (c.isNull(5)) "" else c.getLong(5)).append(',')
                    append(if (c.isNull(6)) "" else c.getLong(6)).append('\n')
                }
            }
        }
        return header + rows
    }

    private fun Cursor.toMediaItem() = MediaItem(
        id = getLong(0), rootUri = getString(1), uri = getString(2), name = getString(3), mime = getString(4), size = getLong(5), modified = getLong(6), favorite = getInt(7) != 0
    )

    private fun shortHash(value: String): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(value.toByteArray())
        return bytes.take(5).joinToString("") { "%02x".format(it) }
    }

    private fun csv(value: String): String = "\"" + value.replace("\"", "\"\"") + "\""
}
