from pathlib import Path

p = Path(__file__).resolve().parent / "v8_emulator_smoke_v2.sh"
s = p.read_text()
start = s.find("assert_landscape_video_not_stretched() {")
end = s.find("\nassert_scrub_updates_frame() {", start)
if start < 0 or end < 0:
    raise RuntimeError("v0.8.3 aspect smoke function anchors missing")

replacement = r'''assert_landscape_video_not_stretched() {
  adb exec-out screencap -p > /tmp/nt-aspect.png
  IFS=, read -r sw sh < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 /tmp/nt-aspect.png)
  ffmpeg -hide_banner -loglevel error -y -i /tmp/nt-aspect.png -f rawvideo -pix_fmt rgb24 /tmp/nt-aspect.rgb
  python3 - "$sw" "$sh" <<'PY'
import sys
w, h = map(int, sys.argv[1:3])
data = open('/tmp/nt-aspect.rgb', 'rb').read()
def colorful(x, y):
    i = (y * w + x) * 3
    r, g, b = data[i:i+3]
    return max(r, g, b) > 60 and (max(r, g, b) - min(r, g, b) > 25)
row_counts = [sum(1 for x in range(w) if colorful(x, y)) for y in range(h)]
row_threshold = max(24, int(w * 0.35))
active = [count >= row_threshold for count in row_counts]
best_start = best_end = -1
run_start = None
for y, on in enumerate(active + [False]):
    if on and run_start is None:
        run_start = y
    elif not on and run_start is not None:
        if best_start < 0 or y - run_start > best_end - best_start:
            best_start, best_end = run_start, y
        run_start = None
if best_start < 0:
    raise SystemExit('SMOKE FAILURE: could not isolate a dense rendered video band')
band_h = best_end - best_start
col_counts = [sum(1 for y in range(best_start, best_end) if colorful(x, y)) for x in range(w)]
col_threshold = max(8, int(band_h * 0.30))
dense_cols = [x for x, count in enumerate(col_counts) if count >= col_threshold]
if not dense_cols:
    raise SystemExit('SMOKE FAILURE: rendered video band had no dense horizontal extent')
x1, x2 = min(dense_cols), max(dense_cols) + 1
band_w = x2 - x1
ratio = band_w / max(band_h, 1)
coverage = sum(row_counts[best_start:best_end]) / max(band_w * band_h, 1)
print(f'isolated video band x={x1}:{x2} y={best_start}:{best_end} size={band_w}x{band_h} aspect={ratio:.3f} colorful_coverage={coverage:.3f}')
if not (1.60 <= ratio <= 1.95):
    raise SystemExit(f'SMOKE FAILURE: isolated 16:9 video band is stretched; measured aspect={ratio:.3f}')
PY
}
'''

s = s[:start] + replacement + s[end:]
p.write_text(s)
print("Replaced v0.8.3 aspect smoke with dense video-band measurement")
