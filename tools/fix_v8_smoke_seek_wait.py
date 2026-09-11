from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "tools/v8_emulator_smoke_v2.sh"
s = p.read_text()
old = """  sleep 0.35\n  adb exec-out screencap -p > /tmp/nt-scrub-early.png\n  swipe_seekbar forward || fail \"could not seek toward late frame\"\n  sleep 0.35\n  adb exec-out screencap -p > /tmp/nt-scrub-late.png\n"""
new = """  # EXACT seeks may need a few hundred ms to decode from the preceding\n  # keyframe on the software-decoded CI emulator. Give both committed frames\n  # enough time to render while still rejecting CLOSEST_SYNC/static-frame bugs.\n  sleep 0.8\n  adb exec-out screencap -p > /tmp/nt-scrub-early.png\n  swipe_seekbar forward || fail \"could not seek toward late frame\"\n  sleep 0.8\n  adb exec-out screencap -p > /tmp/nt-scrub-late.png\n"""
if old not in s:
    raise RuntimeError("v8 smoke seek timing anchor missing")
p.write_text(s.replace(old, new, 1))
print("Adjusted v0.8.3 exact-seek QA settle time")
