from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

p = ROOT / "app/src/main/java/com/neurontap/app/AnalyticsUi.kt"
s = p.read_text()
if "import androidx.compose.ui.unit.sp\n" not in s:
    s = s.replace("import androidx.compose.ui.unit.dp\n", "import androidx.compose.ui.unit.dp\nimport androidx.compose.ui.unit.sp\n", 1)
if "import kotlin.math.roundToInt\n" not in s:
    s = s.replace("import java.util.Locale\n", "import java.util.Locale\nimport kotlin.math.roundToInt\n", 1)
p.write_text(s)

p = ROOT / "app/src/main/java/com/neurontap/app/GalleryUi.kt"
s = p.read_text()
if "import kotlin.math.roundToInt\n" not in s:
    s = s.replace("import kotlin.math.abs\n", "import kotlin.math.abs\nimport kotlin.math.roundToInt\n", 1)
p.write_text(s)

p = ROOT / "app/src/main/java/com/neurontap/app/ViewerVideoV8.kt"
s = p.read_text().replace("import androidx.compose.foundation.layout.weight\n", "")
p.write_text(s)

print("Fixed first v0.8 compile errors")
