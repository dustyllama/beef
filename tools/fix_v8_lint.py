from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app/src/main/java/com/neurontap/app"

# Media3's UnstableApi is an AndroidX experimental marker. Use the official
# project-level lint opt-in for exactly that marker. This does not baseline or
# disable unrelated lint checks; it only records that NeuronTap deliberately
# uses Media3's unstable APIs in its custom player stack.
package_info = SRC / "package-info.kt"
if package_info.exists():
    package_info.unlink()

wrong = "@file:OptIn(androidx.media3.common.util.UnstableApi::class)\n\n"
for p in SRC.glob("*.kt"):
    s = p.read_text()
    if s.startswith(wrong):
        p.write_text(s[len(wrong):])

(ROOT / "app/lint.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>\n<lint>\n    <issue id="UnsafeOptInUsageError">\n        <option name="opt-in" value="androidx.media3.common.util.UnstableApi" />\n    </issue>\n</lint>\n''')

print("Applied scoped Media3 UnstableApi lint opt-in for v8")
