from pathlib import Path

p = Path(__file__).resolve().parent / "v8_emulator_smoke_v2.sh"
s = p.read_text()

# v0.8.3 already carries the hardened AVD boot flow in v2. Keep this helper
# focused on accessibility semantics used by the evidence-based smoke test.
gallery = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/GalleryUi.kt"
g = gallery.read_text()
import_anchor = 'import androidx.compose.ui.platform.LocalDensity\n'
semantics_imports = import_anchor + 'import androidx.compose.ui.semantics.contentDescription\nimport androidx.compose.ui.semantics.semantics\n'
if 'import androidx.compose.ui.semantics.semantics\n' not in g:
    if import_anchor not in g:
        raise SystemExit("GalleryUi semantics import anchor not found")
    g = g.replace(import_anchor, semantics_imports, 1)

tile_anchor = 'Modifier.aspectRatio(1f).combinedClickable(onClick = { onOpen(item) }, onLongClick = { onToggleFavorite(item) })'
tile_semantic = 'Modifier.aspectRatio(1f).semantics { contentDescription = item.name }.combinedClickable(onClick = { onOpen(item) }, onLongClick = { onToggleFavorite(item) })'
if tile_semantic not in g:
    if tile_anchor not in g:
        raise SystemExit("GalleryUi media tile semantics anchor not found")
    g = g.replace(tile_anchor, tile_semantic, 1)
gallery.write_text(g)

print("Exposed media names to accessibility services for v0.8.3 QA")
