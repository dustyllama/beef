from pathlib import Path
p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/AnalyticsUi.kt"
s = p.read_text()
if "import androidx.compose.foundation.layout.Spacer\n" not in s:
    s = s.replace("import androidx.compose.foundation.layout.Row\n", "import androidx.compose.foundation.layout.Row\nimport androidx.compose.foundation.layout.Spacer\n", 1)
p.write_text(s)
print("Fixed v0.7 archive Spacer import")
