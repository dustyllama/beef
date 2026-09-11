#!/usr/bin/env bash
set -euo pipefail

APK="${1:-app/build/outputs/apk/debug/app-debug.apk}"
AVD_NAME="neurontap_v8_smoke"
IMAGE="system-images;android-35;google_apis;x86_64"
SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Android/Sdk}}"
IMAGE_DIR="$SDK_ROOT/system-images/android-35/google_apis/x86_64"
EMULATOR_BIN="$SDK_ROOT/emulator/emulator"
export ANDROID_AVD_HOME="${ANDROID_AVD_HOME:-$HOME/.android/avd}"

fail() { echo "SMOKE FAILURE: $*" >&2; exit 1; }
app_alive() { adb shell pidof com.neurontap.app 2>/dev/null | grep -q '[0-9]'; }
assert_alive() { app_alive || fail "NeuronTap process died during $1"; }
dump_emulator_log() {
  echo "----- emulator log -----" >&2
  tail -n 200 /tmp/nt-emulator.log >&2 2>/dev/null || true
  echo "------------------------" >&2
}
dump_accessibility() {
  adb shell uiautomator dump /sdcard/nt-window.xml >/dev/null 2>&1 || true
  adb exec-out cat /sdcard/nt-window.xml > /tmp/nt-window.xml 2>/dev/null || true
  echo "----- accessibility snapshot -----" >&2
  python3 - <<'PY' >&2 2>/dev/null || true
import xml.etree.ElementTree as ET
try:
    root = ET.parse('/tmp/nt-window.xml').getroot()
except Exception as exc:
    print(f"unable to parse UI XML: {exc}")
else:
    for node in root.iter('node'):
        desc = node.attrib.get('content-desc','').strip()
        text = node.attrib.get('text','').strip()
        cls = node.attrib.get('class','')
        bounds = node.attrib.get('bounds','')
        if desc or text:
            print(f"class={cls} text={text!r} desc={desc!r} bounds={bounds}")
PY
  echo "----------------------------------" >&2
}

# Accessibility-first tap helper. Keeps the test independent of a particular
# emulator resolution and catches basic Compose navigation regressions.
tap_desc() {
  local needle="$1"
  adb shell uiautomator dump /sdcard/nt-window.xml >/dev/null 2>&1 || true
  adb exec-out cat /sdcard/nt-window.xml > /tmp/nt-window.xml 2>/dev/null || true
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

tap_desc_retry() {
  local needle="$1"
  local attempts="${2:-6}"
  for _ in $(seq 1 "$attempts"); do
    if tap_desc "$needle"; then return 0; fi
    sleep 0.35
  done
  dump_accessibility
  return 1
}

swipe_seekbar() {
  local direction="$1"
  adb shell uiautomator dump /sdcard/nt-window.xml >/dev/null 2>&1 || true
  adb exec-out cat /sdcard/nt-window.xml > /tmp/nt-window.xml 2>/dev/null || true
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

# The v0.8 patch pipeline must expose the product-facing Gallery label. Keep
# this separate from runtime navigation so an accessibility timing issue cannot
# accidentally hide a terminology regression.
grep -Fq 'Icon(Icons.Default.PhotoLibrary, "Gallery")' app/src/main/java/com/neurontap/app/GalleryUi.kt || fail "patched Gallery tab semantics are missing"

echo "Installing emulator image..."
# setup-android has already accepted licenses. Do not pipe infinite `yes` into
# sdkmanager under `pipefail`: sdkmanager can succeed, close stdin, and make
# `yes` die with SIGPIPE, falsely failing the release gate.
sdkmanager --install "$IMAGE" >/dev/null
[[ -d "$IMAGE_DIR" ]] || fail "emulator image was not installed at $IMAGE_DIR"
mkdir -p "$ANDROID_AVD_HOME"
printf 'no\n' | avdmanager create avd --force -n "$AVD_NAME" -k "$IMAGE" >/dev/null
[[ -f "$ANDROID_AVD_HOME/$AVD_NAME.ini" ]] || fail "AVD definition was not created at $ANDROID_AVD_HOME/$AVD_NAME.ini"
[[ -x "$EMULATOR_BIN" ]] || fail "Android emulator binary not found at $EMULATOR_BIN"

# GitHub hosted Linux runners normally expose KVM. Fall back to software
# acceleration rather than silently skipping runtime validation.
ACCEL="-accel off"
if [[ -e /dev/kvm ]]; then
  sudo chmod 666 /dev/kvm || true
  ACCEL="-accel on"
fi

"$EMULATOR_BIN" -avd "$AVD_NAME" -no-window -no-audio -no-boot-anim -no-snapshot -no-snapshot-save -wipe-data -gpu swiftshader_indirect -no-metrics $ACCEL > /tmp/nt-emulator.log 2>&1 &
EMU_PID=$!
trap 'kill "$EMU_PID" 2>/dev/null || true' EXIT

# Never allow adb wait-for-device to consume the entire CI timeout. If the
# emulator crashes before registering with adb, surface its log immediately.
DEVICE_READY=0
for _ in $(seq 1 120); do
  if ! kill -0 "$EMU_PID" 2>/dev/null; then
    dump_emulator_log
    fail "emulator process exited before registering with adb"
  fi
  if adb devices | awk '$1 ~ /^emulator-/ && $2 == "device" { found=1 } END { exit(found ? 0 : 1) }'; then
    DEVICE_READY=1
    break
  fi
  sleep 1
done
if [[ "$DEVICE_READY" != "1" ]]; then
  dump_emulator_log
  fail "emulator did not register with adb within 120 seconds"
fi

BOOT_READY=0
for _ in $(seq 1 180); do
  if ! kill -0 "$EMU_PID" 2>/dev/null; then
    dump_emulator_log
    fail "emulator process exited before Android finished booting"
  fi
  if [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then
    BOOT_READY=1
    break
  fi
  sleep 1
done
if [[ "$BOOT_READY" != "1" ]]; then
  dump_emulator_log
  fail "emulator did not finish booting within 180 seconds"
fi
adb shell input keyevent 82 || true
adb shell wm dismiss-keyguard || true

adb install -r "$APK" >/dev/null
adb shell pm grant com.neurontap.app android.permission.READ_MEDIA_VIDEO || true
adb shell pm grant com.neurontap.app android.permission.READ_MEDIA_IMAGES || true

# Generate the exact kind of pathological duration that exposed the v0.7
# player: a sub-second H.264 loop. Visual content is irrelevant to decoder/lifecycle stress.
if ! command -v ffmpeg >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq ffmpeg
fi
ffmpeg -hide_banner -loglevel error -y -f lavfi -i testsrc2=size=360x640:rate=30 -t 0.80 -c:v libx264 -pix_fmt yuv420p /tmp/nt-loop.mp4
adb shell mkdir -p /sdcard/Movies
adb push /tmp/nt-loop.mp4 /sdcard/Movies/nt_v8_loop.mp4 >/dev/null
adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Movies/nt_v8_loop.mp4 >/dev/null
sleep 2

adb shell am force-stop com.neurontap.app
adb shell am start -W -n com.neurontap.app/.MainActivity >/dev/null
sleep 5
assert_alive "cold start"

# Exercise the exact cold-start tab path that previously queued multiple swipes.
# Compose semantics can briefly disappear while a destination is recomposing, so
# retry each lookup instead of turning one transient UI dump into a false failure.
for desc in Videos Favorites Albums Gallery Videos; do
  tap_desc_retry "$desc" || fail "could not locate $desc tab"
  sleep 0.25
  assert_alive "tab navigation to $desc"
done

# Open the pathological short video by accessibility label.
opened=0
for _ in $(seq 1 20); do
  if tap_desc "nt_v8_loop.mp4"; then opened=1; break; fi
  sleep 1
done
[[ "$opened" == "1" ]] || { dump_accessibility; fail "could not locate pathological short-loop video"; }
sleep 2
assert_alive "opening short-loop video"

# Let it cross its repeat boundary many times before touching anything.
sleep 8
assert_alive "repeated sub-second looping"

# Hammer pause/play while the loop repeatedly crosses its end boundary.
for i in $(seq 1 24); do
  if tap_desc "Pause"; then :; elif tap_desc "Play"; then :; else dump_accessibility; fail "play/pause control disappeared at iteration $i"; fi
  sleep 0.10
  if tap_desc "Play"; then :; elif tap_desc "Pause"; then :; else dump_accessibility; fail "play/pause control disappeared after toggle $i"; fi
  sleep 0.10
  assert_alive "rapid pause/play iteration $i"
done

# Scrub both directions several times when Compose exposes Slider as SeekBar.
# Fail if it never appears: timeline interaction is a release-blocking video path.
seek_seen=0
for i in $(seq 1 8); do
  if swipe_seekbar forward; then seek_seen=1; fi
  sleep 0.15
  assert_alive "forward scrub $i"
  if swipe_seekbar back; then seek_seen=1; fi
  sleep 0.15
  assert_alive "backward scrub $i"
done
[[ "$seek_seen" == "1" ]] || { dump_accessibility; fail "video timeline SeekBar was not accessible"; }

# Repeated orientation recreation was a direct v0.7 crash reproducer.
adb shell settings put system accelerometer_rotation 0
for i in $(seq 1 8); do
  adb shell settings put system user_rotation 1
  sleep 0.6
  assert_alive "landscape rotation $i"
  adb shell settings put system user_rotation 0
  sleep 0.6
  assert_alive "portrait rotation $i"
  if tap_desc "Pause"; then tap_desc "Play" || true; elif tap_desc "Play"; then tap_desc "Pause" || true; fi
  assert_alive "post-rotation playback $i"
done

# Background/reopen must not poison the player or cold-start media state.
adb shell input keyevent 3
sleep 2
assert_alive "backgrounding"
adb shell am start -W -n com.neurontap.app/.MainActivity >/dev/null
sleep 2
assert_alive "foreground return"

echo "NeuronTap v0.8 emulator smoke test passed."
