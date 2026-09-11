#!/usr/bin/env bash
set -euo pipefail

APK="${1:-app/build/outputs/apk/debug/app-debug.apk}"
AVD_NAME="neurontap_v8_smoke"
IMAGE="system-images;android-35;google_apis;x86_64"
IMAGE_DIR="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Android/Sdk}}/system-images/android-35/google_apis/x86_64"

fail() { echo "SMOKE FAILURE: $*" >&2; exit 1; }
app_alive() { adb shell pidof com.neurontap.app 2>/dev/null | grep -q '[0-9]'; }
assert_alive() { app_alive || fail "NeuronTap process died during $1"; }

dump_ui() {
  adb shell uiautomator dump /sdcard/nt-window.xml >/dev/null 2>&1 || true
  adb exec-out cat /sdcard/nt-window.xml > /tmp/nt-window.xml 2>/dev/null || true
}

tap_desc() {
  local needle="$1"
  dump_ui
  local xy
  xy=$(python3 - "$needle" <<'PY'
import re, sys, xml.etree.ElementTree as ET
needle = sys.argv[1].lower()
try:
    root = ET.parse('/tmp/nt-window.xml').getroot()
except Exception:
    sys.exit(1)
for node in root.iter('node'):
    desc = node.attrib.get('content-desc','').lower()
    text = node.attrib.get('text','').lower()
    if needle in desc or needle == text:
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds',''))
        if m:
            x1,y1,x2,y2 = map(int,m.groups())
            print((x1+x2)//2, (y1+y2)//2)
            sys.exit(0)
sys.exit(1)
PY
  ) || return 1
  read -r x y <<<"$xy"
  adb shell input tap "$x" "$y"
}

assert_ui_contains() {
  local needle="$1"
  dump_ui
  grep -Fq "$needle" /tmp/nt-window.xml || fail "UI did not contain expected text: $needle"
}

media_tile_coords() {
  dump_ui
  python3 <<'PY'
import re, xml.etree.ElementTree as ET
try:
    root = ET.parse('/tmp/nt-window.xml').getroot()
except Exception:
    raise SystemExit(1)
rx = re.compile(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')
nodes=[]
max_y=0
for n in root.iter('node'):
    m=rx.fullmatch(n.attrib.get('bounds',''))
    if not m: continue
    x1,y1,x2,y2=map(int,m.groups())
    max_y=max(max_y,y2)
    if n.attrib.get('clickable') != 'true': continue
    w=x2-x1; h=y2-y1
    if h <= 0: continue
    ratio=w/h
    if min(w,h) >= 56 and 0.76 <= ratio <= 1.32:
        nodes.append((x1,y1,x2,y2))
seen=set()
for x1,y1,x2,y2 in nodes:
    if y1 < 60 or y2 > max_y*0.82: continue
    center=((x1+x2)//2,(y1+y2)//2)
    if center in seen: continue
    seen.add(center)
    print(center[0], center[1])
PY
}

media_tile_bounds() {
  dump_ui
  python3 <<'PY'
import re, xml.etree.ElementTree as ET
root=ET.parse('/tmp/nt-window.xml').getroot()
rx=re.compile(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')
rows=[]; max_y=0
for n in root.iter('node'):
    m=rx.fullmatch(n.attrib.get('bounds',''))
    if not m: continue
    x1,y1,x2,y2=map(int,m.groups()); max_y=max(max_y,y2)
    if n.attrib.get('clickable') != 'true': continue
    w=x2-x1; h=y2-y1
    if h > 0 and min(w,h) >= 56 and 0.76 <= w/h <= 1.32:
        rows.append((x1,y1,x2,y2))
seen=set()
for row in rows:
    x1,y1,x2,y2=row
    if y1 < 60 or y2 > max_y*0.82: continue
    center=((x1+x2)//2,(y1+y2)//2)
    if center in seen: continue
    seen.add(center)
    print(x1,y1,x2,y2)
PY
}

print_media_diagnostics() {
  echo "---- MediaStore videos ----" >&2
  adb shell content query --uri content://media/external/video/media >&2 || true
  echo "---- MediaStore images ----" >&2
  adb shell content query --uri content://media/external/images/media >&2 || true
  echo "---- UI ----" >&2
  dump_ui
  cat /tmp/nt-window.xml >&2 || true
}

wait_media_tile_count() {
  local expected="$1"
  local label="$2"
  local count=0
  for _ in $(seq 1 25); do
    local coords
    coords="$(media_tile_coords || true)"
    if [[ -z "$coords" ]]; then count=0; else count=$(printf '%s\n' "$coords" | sed '/^$/d' | wc -l); fi
    if [[ "$count" -eq "$expected" ]]; then
      echo "$label: found $count media tile(s)"
      return 0
    fi
    sleep 1
  done
  print_media_diagnostics
  fail "$label expected $expected media tile(s), found $count"
}

tap_first_media_tile() {
  local xy
  xy="$(media_tile_coords | head -1)"
  [[ -n "$xy" ]] || fail "no media tile available to open"
  read -r x y <<<"$xy"
  adb shell input tap "$x" "$y"
}

wait_for_scanned_media() {
  local videos images
  for _ in $(seq 1 30); do
    videos="$(adb shell content query --uri content://media/external/video/media 2>/dev/null || true)"
    images="$(adb shell content query --uri content://media/external/images/media 2>/dev/null || true)"
    if grep -Fq 'nt_v8_loop.mp4' <<<"$videos" && grep -Fq 'nt_gallery_sentinel.png' <<<"$images"; then
      echo "Android MediaStore sees both QA seed files"
      return 0
    fi
    sleep 1
  done
  print_media_diagnostics
  fail "Android MediaStore never exposed both QA seed files"
}

screen_center_tap() {
  local size
  size=$(adb shell wm size | tr -d '\r' | tail -1 | grep -oE '[0-9]+x[0-9]+' | tail -1)
  local w=${size%x*}
  local h=${size#*x}
  adb shell input tap $((w/2)) $((h/2))
}

swipe_seekbar() {
  local direction="$1"
  dump_ui
  local coords
  coords=$(python3 - "$direction" <<'PY'
import re, sys, xml.etree.ElementTree as ET
direction=sys.argv[1]
root=ET.parse('/tmp/nt-window.xml').getroot()
for node in root.iter('node'):
    if 'SeekBar' not in node.attrib.get('class',''): continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds',''))
    if not m: continue
    x1,y1,x2,y2=map(int,m.groups()); y=(y1+y2)//2
    a=x1+(x2-x1)//5; b=x1+4*(x2-x1)//5
    if direction == 'back': a,b=b,a
    print(a,y,b,y); sys.exit(0)
sys.exit(1)
PY
  ) || return 1
  read -r x1 y1 x2 y2 <<<"$coords"
  adb shell input swipe "$x1" "$y1" "$x2" "$y2" 220
}

assert_video_thumbnail_visible() {
  local bounds
  bounds="$(media_tile_bounds | head -1)"
  [[ -n "$bounds" ]] || fail "video tile bounds unavailable for thumbnail check"
  read -r x1 y1 x2 y2 <<<"$bounds"
  for attempt in $(seq 1 15); do
    adb exec-out screencap -p > /tmp/nt-thumb.png
    read -r sw sh < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=' ' /tmp/nt-thumb.png)
    ffmpeg -hide_banner -loglevel error -y -i /tmp/nt-thumb.png -f rawvideo -pix_fmt rgb24 /tmp/nt-thumb.rgb
    if python3 - "$sw" "$sh" "$x1" "$y1" "$x2" "$y2" <<'PY'
import sys
sw,sh,x1,y1,x2,y2=map(int,sys.argv[1:])
data=open('/tmp/nt-thumb.rgb','rb').read()
x1=max(0,x1+4); y1=max(0,y1+4); x2=min(sw,x2-4); y2=min(sh,y2-4)
bright=0; total=0
for y in range(y1,y2):
    row=y*sw*3
    for x in range(x1,x2):
        i=row+x*3; r,g,b=data[i:i+3]; total+=1
        if max(r,g,b) >= 55: bright+=1
ratio=bright/max(total,1)
print(f'video thumbnail non-dark ratio={ratio:.3f}')
raise SystemExit(0 if ratio >= 0.22 else 1)
PY
    then
      return 0
    fi
    sleep 1
  done
  fail "video thumbnail stayed effectively black"
}

assert_landscape_video_not_stretched() {
  adb exec-out screencap -p > /tmp/nt-aspect.png
  read -r sw sh < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=' ' /tmp/nt-aspect.png)
  ffmpeg -hide_banner -loglevel error -y -i /tmp/nt-aspect.png -f rawvideo -pix_fmt rgb24 /tmp/nt-aspect.rgb
  python3 - "$sw" "$sh" <<'PY'
import sys
w,h=map(int,sys.argv[1:3]); data=open('/tmp/nt-aspect.rgb','rb').read()
pts=[]
for y in range(h):
    row=y*w*3
    for x in range(w):
        i=row+x*3; r,g,b=data[i:i+3]
        if max(r,g,b) > 60 and (max(r,g,b)-min(r,g,b) > 25): pts.append((x,y))
if len(pts) < w*h*0.025: raise SystemExit('SMOKE FAILURE: test video was not visibly rendered')
xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
bw=max(xs)-min(xs)+1; bh=max(ys)-min(ys)+1; ratio=bw/bh
print(f'video visible bbox={bw}x{bh}, aspect={ratio:.3f}')
if not (1.55 <= ratio <= 2.02): raise SystemExit(f'SMOKE FAILURE: 16:9 video rendered stretched; visible aspect={ratio:.3f}')
PY
}

assert_scrub_updates_frame() {
  if tap_desc "Pause"; then sleep 0.3; elif tap_desc "Play"; then tap_desc "Pause" || true; sleep 0.3; fi
  swipe_seekbar back || fail "could not seek toward early frame"
  sleep 0.35
  adb exec-out screencap -p > /tmp/nt-scrub-early.png
  swipe_seekbar forward || fail "could not seek toward late frame"
  sleep 0.35
  adb exec-out screencap -p > /tmp/nt-scrub-late.png
  read -r sw sh < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=' ' /tmp/nt-scrub-early.png)
  ffmpeg -hide_banner -loglevel error -y -i /tmp/nt-scrub-early.png -f rawvideo -pix_fmt rgb24 /tmp/nt-scrub-early.rgb
  ffmpeg -hide_banner -loglevel error -y -i /tmp/nt-scrub-late.png -f rawvideo -pix_fmt rgb24 /tmp/nt-scrub-late.rgb
  python3 - "$sw" "$sh" <<'PY'
import sys
w,h=map(int,sys.argv[1:3])
a=open('/tmp/nt-scrub-early.rgb','rb').read(); b=open('/tmp/nt-scrub-late.rgb','rb').read()
x1,x2=int(w*.05),int(w*.95); y1,y2=int(h*.20),int(h*.70)
total=0; count=0
for y in range(y1,y2):
    row=y*w*3
    for x in range(x1,x2):
        i=row+x*3
        total += abs(a[i]-b[i])+abs(a[i+1]-b[i+1])+abs(a[i+2]-b[i+2]); count += 3
mad=total/max(count,1)
print(f'paused scrub frame mean absolute RGB delta={mad:.2f}')
if mad < 5.0: raise SystemExit('SMOKE FAILURE: seekbar moved but displayed paused video frame did not materially update')
PY
}

echo "Installing emulator image..."
sdkmanager --install "$IMAGE" >/dev/null
[[ -d "$IMAGE_DIR" ]] || fail "emulator image was not installed at $IMAGE_DIR"
export ANDROID_AVD_HOME="${RUNNER_TEMP:-/tmp}/neurontap-avd-v2"
mkdir -p "$ANDROID_AVD_HOME"
rm -rf "$ANDROID_AVD_HOME/$AVD_NAME.avd" "$ANDROID_AVD_HOME/$AVD_NAME.ini"
printf 'no\n' | avdmanager create avd --force -n "$AVD_NAME" -k "$IMAGE" >/dev/null
EMULATOR_BIN="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Android/Sdk}}/emulator/emulator"
[[ -x "$EMULATOR_BIN" ]] || fail "Android emulator binary missing at $EMULATOR_BIN"
"$EMULATOR_BIN" -list-avds | grep -Fxq "$AVD_NAME" || fail "created AVD is not visible to emulator"

ACCEL="-accel off"
if [[ -e /dev/kvm ]]; then sudo chmod 666 /dev/kvm || true; ACCEL="-accel on"; fi
"$EMULATOR_BIN" -avd "$AVD_NAME" -no-window -no-audio -no-boot-anim -no-snapshot -gpu swiftshader -no-metrics $ACCEL > /tmp/nt-emulator.log 2>&1 &
EMU_PID=$!
trap 'kill "$EMU_PID" 2>/dev/null || true' EXIT

DEVICE_READY=0
for _ in $(seq 1 90); do
  kill -0 "$EMU_PID" 2>/dev/null || { tail -200 /tmp/nt-emulator.log >&2 || true; fail "emulator exited before adb registration"; }
  if adb devices | awk 'NR > 1 && $2 == "device" {found=1} END {exit(found?0:1)}'; then DEVICE_READY=1; break; fi
  sleep 2
done
[[ "$DEVICE_READY" == "1" ]] || { tail -200 /tmp/nt-emulator.log >&2 || true; fail "emulator never registered with adb"; }
BOOT_READY=0
for _ in $(seq 1 180); do
  kill -0 "$EMU_PID" 2>/dev/null || { tail -200 /tmp/nt-emulator.log >&2 || true; fail "emulator exited during Android boot"; }
  if [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then BOOT_READY=1; break; fi
  sleep 2
done
[[ "$BOOT_READY" == "1" ]] || { tail -200 /tmp/nt-emulator.log >&2 || true; fail "emulator did not complete Android boot"; }
adb shell input keyevent 82 || true
adb shell wm dismiss-keyguard || true

adb install -r "$APK" >/dev/null
adb shell pm grant com.neurontap.app android.permission.READ_MEDIA_VIDEO || true
adb shell pm grant com.neurontap.app android.permission.READ_MEDIA_IMAGES || true

if ! command -v ffmpeg >/dev/null 2>&1; then sudo apt-get update -qq; sudo apt-get install -y -qq ffmpeg; fi

ffmpeg -hide_banner -loglevel error -y -f lavfi -i testsrc2=size=640x360:rate=30 -t 0.80 -c:v libx264 -pix_fmt yuv420p /tmp/nt-loop.mp4
ffmpeg -hide_banner -loglevel error -y -f lavfi -i color=c=red:size=360x640:rate=1 -frames:v 1 -update 1 /tmp/nt-gallery-sentinel.png
adb shell mkdir -p /sdcard/Movies /sdcard/Pictures
adb push /tmp/nt-loop.mp4 /sdcard/Movies/nt_v8_loop.mp4 >/dev/null
adb push /tmp/nt-gallery-sentinel.png /sdcard/Pictures/nt_gallery_sentinel.png >/dev/null
adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Movies/nt_v8_loop.mp4 >/dev/null
adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Pictures/nt_gallery_sentinel.png >/dev/null
wait_for_scanned_media

adb shell am force-stop com.neurontap.app
adb shell am start -W -n com.neurontap.app/.MainActivity >/dev/null
sleep 3
assert_alive "cold start"
wait_media_tile_count 2 "All gallery indexing"

for desc in Videos Favorites Albums All Videos; do
  tap_desc "$desc" || fail "could not locate $desc tab"
  sleep 0.30
  assert_alive "tab navigation to $desc"
done
wait_media_tile_count 1 "Videos tab filtering"
assert_video_thumbnail_visible

tap_first_media_tile
sleep 2
assert_alive "opening short-loop video"
assert_ui_contains "0.8s"

screen_center_tap
sleep 0.5
assert_landscape_video_not_stretched
screen_center_tap
sleep 0.5

sleep 8
assert_alive "repeated sub-second looping"

for i in $(seq 1 24); do
  if tap_desc "Pause"; then :; elif tap_desc "Play"; then :; else fail "play/pause control disappeared at iteration $i"; fi
  sleep 0.10
  if tap_desc "Play"; then :; elif tap_desc "Pause"; then :; else fail "play/pause control disappeared after toggle $i"; fi
  sleep 0.10
  assert_alive "rapid pause/play iteration $i"
done

seek_seen=0
for i in $(seq 1 4); do
  if swipe_seekbar forward; then seek_seen=1; fi
  sleep 0.15
  assert_alive "forward scrub $i"
  if swipe_seekbar back; then seek_seen=1; fi
  sleep 0.15
  assert_alive "backward scrub $i"
done
[[ "$seek_seen" == "1" ]] || fail "video timeline SeekBar was not accessible"
assert_scrub_updates_frame

adb shell settings put system accelerometer_rotation 0
for i in $(seq 1 8); do
  adb shell settings put system user_rotation 1
  sleep 0.6
  assert_alive "landscape rotation $i"
  if ! tap_desc "Pause" && ! tap_desc "Play"; then fail "video controls vanished after landscape rotation $i"; fi
  adb shell settings put system user_rotation 0
  sleep 0.6
  assert_alive "portrait rotation $i"
  if ! tap_desc "Pause" && ! tap_desc "Play"; then fail "video controls vanished after portrait rotation $i"; fi
done

tap_desc "Back" || fail "viewer Back control disappeared"
sleep 1
wait_media_tile_count 1 "Back returns to Videos context"

tap_first_media_tile
sleep 1
adb shell input keyevent 3
sleep 2
assert_alive "backgrounding"
adb shell am start -W -n com.neurontap.app/.MainActivity >/dev/null
sleep 2
assert_alive "foreground return"
if ! tap_desc "Pause" && ! tap_desc "Play"; then fail "viewer/player context lost after foreground return"; fi

echo "NeuronTap v0.8.3 deterministic emulator torture test passed."
