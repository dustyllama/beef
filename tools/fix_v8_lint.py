from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app/src/main/java/com/neurontap/app"

# Media3's UnstableApi is an AndroidX experimental marker, not Kotlin's
# RequiresOptIn marker. Using kotlin.OptIn compiles but lint correctly rejects
# it. Opt the app package in with androidx.annotation.OptIn, exactly as Media3
# documents, so every custom viewer/player usage is covered without disabling
# UnsafeOptInUsageError or hiding unrelated lint findings.
wrong = "@file:OptIn(androidx.media3.common.util.UnstableApi::class)\n\n"
for p in SRC.glob("*.kt"):
    if p.name == "package-info.kt":
        continue
    s = p.read_text()
    if s.startswith(wrong):
        p.write_text(s[len(wrong):])

package_info = SRC / "package-info.kt"
package_info.write_text('''@OptIn(UnstableApi::class)\npackage com.neurontap.app\n\nimport androidx.annotation.OptIn\nimport androidx.media3.common.util.UnstableApi\n''')

print("Applied AndroidX Media3 package opt-in for v8 lint")
