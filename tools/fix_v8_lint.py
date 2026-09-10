from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app/src/main/java/com/neurontap/app"

# Media3 intentionally marks a number of APIs used by the custom viewer/player
# as unstable. We opt in at file scope only for files that actually reference
# Media3, instead of suppressing Android lint globally or creating a baseline.
changed = []
for p in SRC.glob("*.kt"):
    s = p.read_text()
    if "androidx.media3." not in s and "SeekParameters" not in s:
        continue
    marker = "@file:OptIn(androidx.media3.common.util.UnstableApi::class)"
    if marker not in s:
        s = marker + "\n\n" + s
        p.write_text(s)
        changed.append(p.name)

if not changed:
    print("v8 lint opt-ins already present or no Media3 files found")
else:
    print("Applied v8 Media3 lint opt-ins to: " + ", ".join(changed))
