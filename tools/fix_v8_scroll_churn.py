from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/GalleryUi.kt"
s = p.read_text()
if 'import kotlinx.coroutines.delay\n' not in s:
    s = s.replace('import kotlinx.coroutines.Dispatchers\n', 'import kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.delay\n', 1)

old = '''    LaunchedEffect(gridState, scrollKey) {
        var lastIndex = gridState.firstVisibleItemIndex
        snapshotFlow { gridState.firstVisibleItemIndex to gridState.firstVisibleItemScrollOffset }
            .distinctUntilChanged()
            .collect { (index, offset) ->
                val delta = index - lastIndex
                if (delta != 0) controller.log(null, EventTypes.GALLERY_SCROLL, value = delta.toLong(), details = "index=$index;columns=$currentColumns")
                localPrefs.edit().putInt("grid_index_$scrollKey", index).putInt("grid_offset_$scrollKey", offset).apply()
                lastIndex = index
            }
    }
'''
new = '''    // Sample scroll state instead of doing SharedPreferences work on every
    // pixel/frame. This preserves useful scroll telemetry and restoration while
    // keeping the main thread out of a preference-write storm.
    LaunchedEffect(gridState, scrollKey) {
        var lastIndex = gridState.firstVisibleItemIndex
        var lastSavedIndex = -1
        var lastSavedOffset = -1
        while (true) {
            delay(250L)
            val index = gridState.firstVisibleItemIndex
            val offset = gridState.firstVisibleItemScrollOffset
            val delta = index - lastIndex
            if (delta != 0) {
                controller.log(null, EventTypes.GALLERY_SCROLL, value = delta.toLong(), details = "index=$index;columns=$currentColumns;sample_ms=250")
                lastIndex = index
            }
            if (index != lastSavedIndex || kotlin.math.abs(offset - lastSavedOffset) >= 24) {
                localPrefs.edit().putInt("grid_index_$scrollKey", index).putInt("grid_offset_$scrollKey", offset).apply()
                lastSavedIndex = index
                lastSavedOffset = offset
            }
        }
    }
'''
if old not in s:
    raise RuntimeError('v8 scroll churn media-grid anchor missing')
s = s.replace(old, new, 1)

old = '''    LaunchedEffect(albumGridState, albumScrollKey) {
        snapshotFlow { albumGridState.firstVisibleItemIndex to albumGridState.firstVisibleItemScrollOffset }
            .distinctUntilChanged()
            .collect { (index, offset) ->
                prefs.edit().putInt("${albumScrollKey}_index", index).putInt("${albumScrollKey}_offset", offset).apply()
            }
    }
'''
new = '''    LaunchedEffect(albumGridState, albumScrollKey) {
        var lastSavedIndex = -1
        var lastSavedOffset = -1
        while (true) {
            delay(250L)
            val index = albumGridState.firstVisibleItemIndex
            val offset = albumGridState.firstVisibleItemScrollOffset
            if (index != lastSavedIndex || kotlin.math.abs(offset - lastSavedOffset) >= 24) {
                prefs.edit().putInt("${albumScrollKey}_index", index).putInt("${albumScrollKey}_offset", offset).apply()
                lastSavedIndex = index
                lastSavedOffset = offset
            }
        }
    }
'''
if old not in s:
    raise RuntimeError('v8 scroll churn album-grid anchor missing')
s = s.replace(old, new, 1)

p.write_text(s)
print('Reduced v8 scroll telemetry/preference churn')
