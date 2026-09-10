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
s = must_replace(
    s,
    '    val instantHardMarks: Int = 0,\n    val edgeMarks: Int = 0,\n',
    '    val instantHardMarks: Int = 0,\n    val fullStrokeMarks: Int = 0,\n    val edgeMarks: Int = 0,\n',
    'summary full-stroke field'
)
s = must_replace(
    s,
    '    val instantHardMarks: Int = 0,\n    val edgeMarks: Int = 0,\n    val totalDwellMs: Long = 0,\n',
    '    val instantHardMarks: Int = 0,\n    val fullStrokeMarks: Int = 0,\n    val edgeMarks: Int = 0,\n    val totalDwellMs: Long = 0,\n',
    'wrapped full-stroke field'
)
s = must_replace(
    s,
    '    val totalZoomedMs: Long = 0,\n',
    '    val totalZoomedMs: Long = 0,\n    val fullStrokeDurationMs: Long = 0,\n',
    'full-stroke duration field'
)
s = s.replace('instantHardMarks * 7.0 + edgeMarks * 6.0', 'instantHardMarks * 7.0 + fullStrokeMarks * 6.0 + edgeMarks * 5.0')
s = s.replace('spiritualCooms * 12.0 + edgeMarks * 7.0', 'spiritualCooms * 12.0 + fullStrokeMarks * 7.0 + edgeMarks * 5.0')
anchor = '    const val EDGE_MARK = "EDGE_MARK"\n'
if anchor not in s:
    raise RuntimeError("v0.7 core anchor missing: EDGE_MARK")
s = s.replace(anchor, anchor + '''    const val FULL_STROKE_MARK = "FULL_STROKE_MARK" // migrated historical Edge marks\n    const val FULL_STROKE_START = "FULL_STROKE_START"\n    const val FULL_STROKE_END = "FULL_STROKE_END"\n    const val GOON_START = "GOON_START"\n    const val GOON_END = "GOON_END"\n    const val HORNY_CONTROL_CONFIG = "HORNY_CONTROL_CONFIG"\n''', 1)
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
            // Requested one-time semantic migration: every historical Edge mark
            // is reclassified as Full Stroke while preserving all original rows,
            // timestamps, media IDs, sessions and provenance.
            db.execSQL("UPDATE events SET type='FULL_STROKE_MARK', details=CASE WHEN details IS NULL OR details='' THEN 'migrated_from_edge_v07' ELSE details || ';migrated_from_edge_v07' END WHERE type='EDGE_MARK'")
        }
'''
s = must_replace(s, upgrade_anchor, upgrade_new, "edge migration")
s = must_replace(
    s,
    "              SUM(CASE WHEN e.type='EDGE_MARK' THEN 1 ELSE 0 END),\n              SUM(CASE WHEN e.type='ZOOM_START' THEN 1 ELSE 0 END),",
    "              SUM(CASE WHEN e.type IN ('FULL_STROKE_MARK','FULL_STROKE_START') THEN 1 ELSE 0 END),\n              SUM(CASE WHEN e.type='EDGE_MARK' THEN 1 ELSE 0 END),\n              SUM(CASE WHEN e.type='ZOOM_START' THEN 1 ELSE 0 END),",
    "summary SQL full stroke + edge"
)
old_ctor = '''                confirmedNuts = c.getInt(6), spiritualCooms = c.getInt(7), instantHardMarks = c.getInt(8), edgeMarks = c.getInt(9),
                zoomStarts = c.getInt(10), zoomSamples = c.getInt(11), maxZoomMilli = c.getLong(12), zoomedDwellMs = c.getLong(13), panDistancePx = c.getLong(14),
                videoSeeks = c.getInt(15), videoReplays = c.getInt(16), videoWatchMs = c.getLong(17), quickestTapMs = if (c.isNull(18)) null else c.getLong(18),
                firstSeenMs = if (c.isNull(19)) null else c.getLong(19), lastSeenMs = if (c.isNull(20)) null else c.getLong(20)
'''
new_ctor = '''                confirmedNuts = c.getInt(6), spiritualCooms = c.getInt(7), instantHardMarks = c.getInt(8), fullStrokeMarks = c.getInt(9), edgeMarks = c.getInt(10),
                zoomStarts = c.getInt(11), zoomSamples = c.getInt(12), maxZoomMilli = c.getLong(13), zoomedDwellMs = c.getLong(14), panDistancePx = c.getLong(15),
                videoSeeks = c.getInt(16), videoReplays = c.getInt(17), videoWatchMs = c.getLong(18), quickestTapMs = if (c.isNull(19)) null else c.getLong(19),
                firstSeenMs = if (c.isNull(20)) null else c.getLong(20), lastSeenMs = if (c.isNull(21)) null else c.getLong(21)
'''
s = must_replace(s, old_ctor, new_ctor, 'summary constructor indexes')
s = must_replace(
    s,
    '            spiritualCooms = summaries.sumOf { it.spiritualCooms }, instantHardMarks = summaries.sumOf { it.instantHardMarks }, edgeMarks = summaries.sumOf { it.edgeMarks },\n            totalDwellMs = summaries.sumOf { it.dwellMs }, totalZoomedMs = summaries.sumOf { it.zoomedDwellMs }, quickestFirstTapMs = fastest,\n',
    '            spiritualCooms = summaries.sumOf { it.spiritualCooms }, instantHardMarks = summaries.sumOf { it.instantHardMarks }, fullStrokeMarks = summaries.sumOf { it.fullStrokeMarks }, edgeMarks = summaries.sumOf { it.edgeMarks },\n            totalDwellMs = summaries.sumOf { it.dwellMs }, totalZoomedMs = summaries.sumOf { it.zoomedDwellMs }, fullStrokeDurationMs = fullStrokeDurationMs(sinceMs), quickestFirstTapMs = fastest,\n',
    'wrapped full stroke stats'
)

insert_anchor = '''    fun clearBehaviorHistory() {
'''
helpers = '''    fun activityHeatmap(types: Set<String>, sinceMs: Long? = null): Map<Pair<Int, Int>, Long> {
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
s = s.replace(insert_anchor, helpers + insert_anchor, 1)
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

# Analytics engine: Full Stroke is now a strong signal; Edge remains separate.
p = ROOT / "app/src/main/java/com/neurontap/app/AnalyticsEngine.kt"
s = p.read_text()
s = s.replace('            val edge = rows.count { it.type == EventTypes.EDGE_MARK }\n', '            val stroke = rows.count { it.type == EventTypes.FULL_STROKE_MARK || it.type == EventTypes.FULL_STROKE_START }\n            val edge = rows.count { it.type == EventTypes.EDGE_MARK }\n', 1)
s = s.replace('it.type == EventTypes.REACTION_DOWN || it.type == EventTypes.INSTANT_HARD || it.type == EventTypes.EDGE_MARK', 'it.type == EventTypes.REACTION_DOWN || it.type == EventTypes.INSTANT_HARD || it.type == EventTypes.FULL_STROKE_START || it.type == EventTypes.FULL_STROKE_MARK || it.type == EventTypes.EDGE_MARK', 1)
s = s.replace('EventTypes.REACTION_UP, EventTypes.SPIRITUAL_COOM, EventTypes.EDGE_MARK, EventTypes.VIDEO_SEEK', 'EventTypes.REACTION_UP, EventTypes.SPIRITUAL_COOM, EventTypes.FULL_STROKE_START, EventTypes.FULL_STROKE_MARK, EventTypes.EDGE_MARK, EventTypes.VIDEO_SEEK', 1)
s = s.replace('seeks * 1.4 + replays * 2.1 + edge * 5.0 + spiritual * 7.0 + hard * 4.0 + proximity', 'seeks * 1.4 + replays * 2.1 + stroke * 5.5 + edge * 5.0 + spiritual * 7.0 + hard * 4.0 + proximity', 1)

s = s.replace('            val edge: Int,\n            val lastSignal: Long,', '            val stroke: Int,\n            val edge: Int,\n            val lastSignal: Long,', 1)
s = s.replace('            val edge = r.count { it.type == EventTypes.EDGE_MARK }\n', '            val stroke = r.count { it.type == EventTypes.FULL_STROKE_MARK || it.type == EventTypes.FULL_STROKE_START }\n            val edge = r.count { it.type == EventTypes.EDGE_MARK }\n', 1)
s = s.replace('spiritual * 1.0 + hard * 0.42 + edge * 0.88 + endProximity', 'spiritual * 1.0 + hard * 0.42 + stroke * 0.92 + edge * 0.88 + endProximity', 1)
s = s.replace('Evidence(mediaId, raw, taps, burstPairs, dwellMs, zoomedMs, seeks, spiritual, hard, edge, last, first)', 'Evidence(mediaId, raw, taps, burstPairs, dwellMs, zoomedMs, seeks, spiritual, hard, stroke, edge, last, first)', 1)
s = s.replace('best.spiritual > 0 || best.edge > 0 || best.dwellMs', 'best.spiritual > 0 || best.stroke > 0 || best.edge > 0 || best.dwellMs', 1)
s = s.replace('            if (best.edge > 0) add("${best.edge} edge mark")\n', '            if (best.stroke > 0) add("${best.stroke} Full Stroke mark")\n            if (best.edge > 0) add("${best.edge} Edge mark")\n', 1)

s = s.replace('gallery("edge", "Edge Magnets", "Most associated with deliberate danger-zone declarations.", summaries.filter { it.edgeMarks > 0 }.sortedWith(compareByDescending<MediaBehaviorSummary> { it.edgeMarks }.thenByDescending { it.dwellMs }))?.let(result::add)', 'gallery("full_stroke", "Full Stroke Hall", "Media most often explicitly marked as active high-intensity masturbation material.", summaries.filter { it.fullStrokeMarks > 0 }.sortedWith(compareByDescending<MediaBehaviorSummary> { it.fullStrokeMarks }.thenByDescending { it.dwellMs }))?.let(result::add)\n        gallery("edge", "Edge Magnets", "Optional deliberate near-orgasm declarations only.", summaries.filter { it.edgeMarks > 0 }.sortedWith(compareByDescending<MediaBehaviorSummary> { it.edgeMarks }.thenByDescending { it.dwellMs }))?.let(result::add)', 1)
# Keep raw first-reaction latency in storage but stop promoting it as a live album.
line = '        gallery("fastest", "Fastest Neuron Activation", "Lowest first-reaction latency.", summaries.filter { it.quickestTapMs != null }.sortedBy { it.quickestTapMs })?.let(result::add)\n'
s = s.replace(line, '')
# v0.6 structured insight generator is installed before this script.
s = s.replace('val edge = summaries.sumOf { it.edgeMarks }', 'val stroke = summaries.sumOf { it.fullStrokeMarks }\n        val edge = summaries.sumOf { it.edgeMarks }')
s = s.replace('if (edge > 0) add(ArchiveInsight("Full Stroke anchors accumulating", "You explicitly marked Full Stroke $edge time${if (edge == 1) "" else "s"}; these are anchors for future automatic high-intensity masturbation-pattern inference.", galleryId = "edge"))', 'if (stroke > 0) add(ArchiveInsight("Full Stroke anchors accumulating", "You explicitly marked Full Stroke $stroke time${if (stroke == 1) "" else "s"}; these are strong anchors for future high-intensity pattern inference.", galleryId = "full_stroke"))\n            if (edge > 0) add(ArchiveInsight("Edge anchors accumulating", "You explicitly marked Edge $edge time${if (edge == 1) "" else "s"}.", galleryId = "edge"))')
s = s.replace('"Images that crossed the \'I could bust right now\' threshold."', '"Media that triggered the primitive-brain \'you should finish to this right now\' signal."')
p.write_text(s)

print("Applied NeuronTap v0.7 core")
