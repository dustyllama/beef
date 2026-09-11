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

# Accessibility-first tap helper. Keeps the test independent of a particular
# emulator resolution and catches basic Compose navigation regressions.
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

assert_selected_tab() {
  local needle="$1"
  dump_ui
  python3 - "$needle" <<'PY' || exit 1
import sys, xml.etree.ElementTree as ET
needle=sys.argv[1].lower()
root=ET.parse('/tmp/nt-window.xml').getroot()
for n in root.iter('node'):
    text=(n.attrib.get('text','')+' '+n.attrib.get('content-desc','')).lower()
    if needle in text and n.attrib.get('selected','false') == 'true':
        sys.exit(0)
print(f'SMOKE FAILURE: {needle} tab was not selected', file=sys.stderr)
sys.exit(1)
PY
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
direction = sys.argv[1]
try:
    root = ET.parse('/tmp/nt-window.xml').getroot()
except Exception:
    sys.exit(1)
for node in root.iter('node'):
    cls = node.attrib.get('class','')
    if 'SeekBar' in cls:
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds',''))
        if not m: continue
        x1,y1,x2,y2 = map(int,m.groups())
        y=(y1+y2)//2
        a=x1 + (x2-x1)//5
        b=x1 + 4*(x2-x1)//5
        if direction == 'back': a,b=b,a
        print(a,y,b,y)
        sys.exit(0)
sys.exit(1)
PY
  ) || return 1
  read -r x1 y1 x2 y2 <<<"$coords"
  adb shell input swipe "$x1" "$y1" "$x2" "$y2" 220
}

assert_landscape_video_not_stretched() {
  # The test clip is solid lime, making its visible TextureView rectangle easy
  # to identify in a device screenshot. A 16:9 clip shown in portrait must stay
  # roughly 16:9 with black letterbox space; the old bug stretched it vertically.
  adb exec-out screencap -p > /tmp/nt-aspect.png
  read -r shot_w shot_h < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=' ' /tmp/nt-aspect.png)
  ffmpeg -hide_banner -loglevel error -y -i /tmp/nt-aspect.png -f rawvideo -pix_fmt rgb24 /tmp/nt-aspect.rgb
  python3 - "$shot_w" "$shot_h" <<'PY'
import sys
w,h=map(int,sys.argv[1:3])
data=open('/tmp/nt-aspect.rgb','rb').read()
if len(data) < w*h*3:
    raise SystemExit('SMOKE FAILURE: incomplete screenshot RGB data')
xs=[]; ys=[]
for y in range(h):
    row=y*w*3
    for x in range(w):
        i=row+x*3
        r,g,b=data[i:i+3]
        # H.264/YUV round-trip means lime is not necessarily exact #00ff00.
        if g > 150 and g > r*1.8 and g > b*1.8:
            xs.append(x); ys.append(y)
if len(xs) < w*h*0.03:
    raise SystemExit('SMOKE FAILURE: landscape test video was not visibly rendered')
bw=max(xs)-min(xs)+1
bh=max(ys)-min(ys)+1
ratio=bw/bh
print(f'Landscape video bbox: {bw}x{bh}, aspect={ratio:.3f}')
if not (1.60 <= ratio <= 1.95):
    raise SystemExit(f'SMOKE FAILURE: 16:9 video rendered stretched; visible aspect={ratio:.3f}')
PY
}

echo "Installing emulator image..."
sdkmanager --install "$IMAGE" >/dev/null
[[ -d "$IMAGE_DIR" ]] || fail "emulator image was not installed at $IMAGE_DIR"
printf 'no\n' | avdmanager create avd --force -n "$AVD_NAME" -k "$IMAGE" >/dev/null

ACCEL="-accel off"
if [[ -e /dev/kvm ]]; then
  sudo chmod 666 /dev/kvm || true
  ACCEL="-accel on"
fi

emulator -avd "$AVD_NAME" -no-window -no-audio -no-boot-anim -no-snapshot -gpu swiftshader_indirect -no-metrics $ACCEL > /tmp/nt-emulator.log 2>&1 &
EMU_PID=$!
trap 'kill "$EMU_PID" 2>/dev/null || true' EXIT

adb wait-for-device
for _ in $(seq 1 180); do
  [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]] && break
  sleep 2
done
[[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]] || fail "emulator did not boot"
adb shell input keyevent 82 || true
adb shell wm dismiss-keyguard || true

adb install -r "$APK" >/dev/null
adb shell pm grant com.neurontap.app android.permission.READ_MEDIA_VIDEO || true
adb shell pm grant com.neurontap.app android.permission.READ_MEDIA_IMAGES || true

if ! command -v ffmpeg >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq ffmpeg
fi

# Exact class of media that exposed the catastrophic presentation bug: a
# sub-second LANDSCAPE 16:9 H.264 loop. Solid lime lets us assert visual aspect.
ffmpeg -hide_banner -loglevel error -y -f lavfi -i color=c=lime:size=640x360:rate=30 -t 0.80 -c:v libx264 -pix_fmt yuv420p /tmp/nt-loop.mp4
adb shell mkdir -p /sdcard/Movies
adb push /tmp/nt-loop.mp4 /sdcard/Movies/nt_v8_loop.mp4 >/dev/null
adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Movies/nt_v8_loop.mp4 >/dev/null
sleep 2

adb shell am force-stop com.neurontap.app
adb shell am start -W -n com.neurontap.app/.MainActivity >/dev/null
sleep 5
assert_alive "cold start"

# Exercise the exact cold-start tab path that previously queued multiple swipes.
for desc in Videos Favorites Albums Gallery Videos; do
  tap_desc "$desc" || fail "could not locate $desc tab"
  sleep 0.25
  assert_alive "tab navigation to $desc"
done
assert_selected_tab "Videos"

opened=0
for _ in $(seq 1 20); do
  if tap_desc "nt_v8_loop.mp4"; then opened=1; break; fi
  sleep 1
done
[[ "$opened" == "1" ]] || fail "could not locate pathological short-loop video"
sleep 2
assert_alive "opening short-loop video"

# Duration must no longer lie as 0:00 / 0:00 for sub-second clips.
assert_ui_contains "0.8s"

# Hide controls and verify the actual rendered video rectangle, not just that
# the process survived. This is the regression the previous QA completely missed.
screen_center_tap
sleep 0.5
assert_landscape_video_not_stretched
screen_center_tap
sleep 0.5

# Let it cross its repeat boundary many times before touching anything.
sleep 8
assert_alive "repeated sub-second looping"

# Hammer pause/play while the loop repeatedly crosses its end boundary.
for i in $(seq 1 24); do
  if tap_desc "Pause"; then :; elif tap_desc "Play"; then :; else fail "play/pause control disappeared at iteration $i"; fi
  sleep 0.10
  if tap_desc "Play"; then :; elif tap_desc "Pause"; then :; else fail "play/pause control disappeared after toggle $i"; fi
  sleep 0.10
  assert_alive "rapid pause/play iteration $i"
done

# Scrub both directions several times. Timeline interaction is release-blocking.
seek_seen=0
for i in $(seq 1 8); do
  if swipe_seekbar forward; then seek_seen=1; fi
  sleep 0.15
  assert_alive "forward scrub $i"
  if swipe_seekbar back; then seek_seen=1; fi
  sleep 0.15
  assert_alive "backward scrub $i"
done
[[ "$seek_seen" == "1" ]] || fail "video timeline SeekBar was not accessible"

# Rotation must preserve the viewer, controls and active media, not merely keep
# the process alive while dumping the user back into Gallery.
adb shell settings put system accelerometer_rotation 0
for i in $(seq 1 8); do
  adb shell settings put system user_rotation 1
  sleep 0.6
  assert_alive "landscape rotation $i"
  if tap_desc "Pause"; then tap_desc "Play" || true; elif tap_desc "Play"; then tap_desc "Pause" || true; else fail "video controls vanished after landscape rotation $i"; fi
  adb shell settings put system user_rotation 0
  sleep 0.6
  assert_alive "portrait rotation $i"
  if tap_desc "Pause"; then tap_desc "Play" || true; elif tap_desc "Play"; then tap_desc "Pause" || true; else fail "video controls vanished after portrait rotation $i"; fi
done

# Back out after rotation and verify origin context is still Videos.
tap_desc "Back" || fail "viewer Back control disappeared"
sleep 1
assert_selected_tab "Videos"

# Reopen and verify background/foreground does not poison player state.
tap_desc "nt_v8_loop.mp4" || fail "could not reopen loop video after navigation test"
sleep 1
adb shell input keyevent 3
sleep 2
assert_alive "backgrounding"
adb shell am start -W -n com.neurontap.app/.MainActivity >/dev/null
sleep 2
assert_alive "foreground return"
if ! tap_desc "Pause" && ! tap_desc "Play"; then fail "viewer/player context lost after foreground return"; fi

echo "NeuronTap v0.8.1 emulator smoke test passed."
