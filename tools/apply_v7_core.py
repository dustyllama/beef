from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"v0.7 core anchor missing: {label}")
    return text.replace(old, new, 1)

# Version -----------------------------------------------------------------
p = ROOT / "app/build.gradle.kts"
s = p.read_text()
s = must_replace(s, "versionCode = 6", "versionCode = 7", "version code")
s = must_replace(s, 'versionName = "0.6.0"', 'versionName = "0.7.0"', "version name")
p.write_text(s)

# Models / event vocabulary ------------------------------------------------
p = ROOT / "app/src/main/java/com/neurontap/app/Models.kt"
s = p.read_text()
# v0.6 used edgeMarks for the slot that now belongs to Full Stroke. Keep old
# Edge as a distinct optional declaration going forward.
s = s.replace("val edgeMarks: Int = 0,", "val fullStrokeMarks: Int = 0,", 1)
s = s.replace("edgeMarks * 6.0", "fullStrokeMarks * 6.0")
s = s.replace("spiritualCooms * 12.0 + edgeMarks * 7.0", "spiritualCooms * 12.0 + fullStrokeMarks * 7.0")
s = s.replace("val edgeMarks: Int = 0,", "val fullStrokeMarks: Int = 0,", 1)
anchor = '    const val EDGE_MARK = "EDGE_MARK"\n'
if anchor not in s:
    raise RuntimeError("v0.7 core anchor missing: EDGE_MARK")
s = s.replace(anchor, anchor + '''    const val FULL_STROKE_MARK = "FULL_STROKE_MARK" // migrated historical edge marks / one-shot compatibility\n    const val FULL_STROKE_START = "FULL_STROKE_START"\n    const val FULL_STROKE_END = "FULL_STROKE_END"\n    const val GOON_START = "GOON_START"\n    const val GOON_END = "GOON_END"\n    const val HORNY_CONTROL_CONFIG = "HORNY_CONTROL_CONFIG"\n''', 1)
p.write_text(s)

# Database migration + summary semantics ----------------------------------
p = ROOT / "app/src/main/java/com/neurontap/app/NeuronDb.kt"
s = p.read_text()
s = must_replace(s, 'SQLiteOpenHelper(context, "neurontap.db", null, 5)', 'SQLiteOpenHelper(context, "neurontap.db", null, 6)', "db version")
upgrade_anchor = '''        if (oldVersion < 5) {
            db.execSQL("ALTER TABLE media ADD COLUMN note TEXT NOT NULL DEFAULT ''")
        }
'''
upgrade_new = upgrade_anchor + '''        if (oldVersion < 6) {
            // One-time semantic correction requested for v0.7: every historical
            // Edge mark becomes Full Stroke evidence. Preserve provenance.
            db.execSQL("UPDATE events SET type='FULL_STROKE_MARK', details=CASE WHEN details IS NULL OR details='' THEN 'migrated_from_edge_v07' ELSE details || ';migrated_from_edge_v07' END WHERE type='EDGE_MARK'")
        }
'''
s = must_replace(s, upgrade_anchor, upgrade_new, "edge migration")
s = must_replace(
    s,
    "SUM(CASE WHEN e.type='EDGE_MARK' THEN 1 ELSE 0 END),",
    "SUM(CASE WHEN e.type IN ('FULL_STROKE_MARK','FULL_STROKE_START') THEN 1 ELSE 0 END),",
    "full stroke summary sql",
)
s = s.replace("edgeMarks = c.getInt(9)", "fullStrokeMarks = c.getInt(9)")
s = s.replace("edgeMarks = summaries.sumOf { it.edgeMarks }", "fullStrokeMarks = summaries.sumOf { it.fullStrokeMarks }")

# General-purpose hour/day buckets for the archive heatmap. UTC conversion is
# deliberately done by SQLite using localtime so this follows the phone locale.
insert_anchor = '''    fun clearBehaviorHistory() {
'''
heatmap_fn = '''    fun activityHeatmap(types: Set<String>, sinceMs: Long? = null): Map<Pair<Int, Int>, Long> {
        if (types.isEmpty()) return emptyMap()
        val placeholders = types.joinToString(",") { "?" }
        val args = buildList {
            addAll(types)
            if (sinceMs != null) add(sinceMs.toString())
        }.toTypedArray()
        val sinceClause = if (sinceMs != null) " AND timestamp_ms>=?" else ""
        val sql = """SELECT CAST(strftime('%w',timestamp_ms/1000,'unixepoch','localtime') AS INTEGER),
                         CAST(strftime('%H',timestamp_ms/1000,'unixepoch','localtime') AS INTEGER),
                         COUNT(*)
                     FROM events WHERE type IN ($placeholders)$sinceClause
                     GROUP BY 1,2""".trimIndent()
        return readableDatabase.rawQuery(sql, args).use { c ->
            buildMap { while (c.moveToNext()) put(c.getInt(0) to c.getInt(1), c.getLong(2)) }
        }
    }

    fun fullStrokeDurationMs(sinceMs: Long? = null): Long {
        val sessions = if (sinceMs == null) sessionsForInference(5000) else sessionsForInference(5000, sinceMs)
        var total = 0L
        sessions.forEach { session ->
            val events = eventsForSession(session.id)
            var openAt: Long? = null
            for (event in events) {
                when (event.type) {
                    EventTypes.FULL_STROKE_START -> if (openAt == null) openAt = event.timestampMs
                    EventTypes.FULL_STROKE_END -> openAt?.let { total += (event.timestampMs - it).coerceAtLeast(0L); openAt = null }
                }
            }
            openAt?.let { start ->
                val end = session.endedAt ?: System.currentTimeMillis()
                total += (end - start).coerceIn(0L, 6L * 60L * 60L * 1000L)
            }
        }
        return total
    }

'''
if insert_anchor not in s:
    raise RuntimeError("v0.7 core anchor missing: clear history")
s = s.replace(insert_anchor, heatmap_fn + insert_anchor, 1)
p.write_text(s)

# Controller ---------------------------------------------------------------
p = ROOT / "app/src/main/java/com/neurontap/app/AppController.kt"
s = p.read_text()
edge_fn = '''    fun markEdge(mediaId: Long, mediaPositionMs: Long? = null) =
        log(mediaId, EventTypes.EDGE_MARK, mediaPositionMs = mediaPositionMs)
'''
replacement = edge_fn + '''
    fun startFullStroke(mediaId: Long, mediaPositionMs: Long? = null, details: String? = null) =
        log(mediaId, EventTypes.FULL_STROKE_START, mediaPositionMs = mediaPositionMs, details = details)

    fun endFullStroke(mediaId: Long?, mediaPositionMs: Long? = null, details: String? = null) =
        log(mediaId, EventTypes.FULL_STROKE_END, mediaPositionMs = mediaPositionMs, details = details)

    fun startGooning(mediaId: Long?, mediaPositionMs: Long? = null) =
        log(mediaId, EventTypes.GOON_START, mediaPositionMs = mediaPositionMs)

    fun endGooning(mediaId: Long?, mediaPositionMs: Long? = null, details: String? = null) =
        log(mediaId, EventTypes.GOON_END, mediaPositionMs = mediaPositionMs, details = details)
'''
s = must_replace(s, edge_fn, replacement, "controller state events")
p.write_text(s)

# Analytics engine references: the former edge slot now means Full Stroke.
p = ROOT / "app/src/main/java/com/neurontap/app/AnalyticsEngine.kt"
s = p.read_text()
s = s.replace("edgeMarks", "fullStrokeMarks")
s = s.replace("Edge anchors accumulating", "Full Stroke anchors accumulating")
s = s.replace("explicitly marked the edge", "explicitly marked Full Stroke")
s = s.replace("edge-pattern inference", "high-intensity masturbation-pattern inference")
p.write_text(s)

print("Applied NeuronTap v0.7 core")
