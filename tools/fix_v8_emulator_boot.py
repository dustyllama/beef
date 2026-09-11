from pathlib import Path

p = Path(__file__).resolve().parent / "v8_emulator_smoke.sh"
s = p.read_text()

old_create = '''printf 'no\\n' | avdmanager create avd --force -n "$AVD_NAME" -k "$IMAGE" >/dev/null

ACCEL="-accel off"
'''
new_create = '''# Keep avdmanager and the current emulator on the exact same AVD directory.
# New Android emulator builds do not reliably discover AVDs through the legacy
# SDK-home fallback used by older command-line tools.
export ANDROID_AVD_HOME="${RUNNER_TEMP:-/tmp}/neurontap-avd"
mkdir -p "$ANDROID_AVD_HOME"
rm -rf "$ANDROID_AVD_HOME/$AVD_NAME.avd" "$ANDROID_AVD_HOME/$AVD_NAME.ini"
printf 'no\\n' | avdmanager create avd --force -n "$AVD_NAME" -k "$IMAGE" >/dev/null

EMULATOR_BIN="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Android/Sdk}}/emulator/emulator"
[[ -x "$EMULATOR_BIN" ]] || fail "Android emulator binary missing at $EMULATOR_BIN"
if ! "$EMULATOR_BIN" -list-avds | grep -Fxq "$AVD_NAME"; then
  echo "---- AVD directory ----" >&2
  find "$ANDROID_AVD_HOME" -maxdepth 2 -type f -print >&2 || true
  echo "---- avdmanager list ----" >&2
  avdmanager list avd >&2 || true
  fail "created AVD is not visible to emulator"
fi

ACCEL="-accel off"
'''
if old_create not in s:
    raise SystemExit("AVD creation anchor not found")
s = s.replace(old_create, new_create, 1)

old_boot = '''emulator -avd "$AVD_NAME" -no-window -no-audio -no-boot-anim -no-snapshot -gpu swiftshader_indirect -no-metrics $ACCEL > /tmp/nt-emulator.log 2>&1 &
EMU_PID=$!
trap 'kill "$EMU_PID" 2>/dev/null || true' EXIT

adb wait-for-device
for _ in $(seq 1 180); do
  [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\\r')" == "1" ]] && break
  sleep 2
done
[[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\\r')" == "1" ]] || fail "emulator did not boot"
'''
new_boot = '''"$EMULATOR_BIN" -avd "$AVD_NAME" -no-window -no-audio -no-boot-anim -no-snapshot -gpu swiftshader -no-metrics $ACCEL > /tmp/nt-emulator.log 2>&1 &
EMU_PID=$!
trap 'kill "$EMU_PID" 2>/dev/null || true' EXIT

# Bound device discovery so emulator startup failures cannot strand the CI job.
DEVICE_READY=0
for _ in $(seq 1 90); do
  if ! kill -0 "$EMU_PID" 2>/dev/null; then
    echo "---- emulator startup log ----" >&2
    tail -200 /tmp/nt-emulator.log >&2 || true
    fail "emulator process exited before adb registration"
  fi
  if adb devices | awk 'NR > 1 && $2 == "device" { found=1 } END { exit(found ? 0 : 1) }'; then
    DEVICE_READY=1
    break
  fi
  sleep 2
done
if [[ "$DEVICE_READY" != "1" ]]; then
  echo "---- emulator startup log ----" >&2
  tail -200 /tmp/nt-emulator.log >&2 || true
  fail "emulator never registered with adb"
fi

BOOT_READY=0
for _ in $(seq 1 180); do
  if ! kill -0 "$EMU_PID" 2>/dev/null; then
    echo "---- emulator boot log ----" >&2
    tail -200 /tmp/nt-emulator.log >&2 || true
    fail "emulator process exited during Android boot"
  fi
  if [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\\r')" == "1" ]]; then
    BOOT_READY=1
    break
  fi
  sleep 2
done
if [[ "$BOOT_READY" != "1" ]]; then
  echo "---- emulator boot log ----" >&2
  tail -200 /tmp/nt-emulator.log >&2 || true
  fail "emulator did not complete Android boot"
fi
'''
if old_boot not in s:
    raise SystemExit("emulator boot block anchor not found")
s = s.replace(old_boot, new_boot, 1)

p.write_text(s)
print("Hardened v0.8.1 emulator boot detection and pinned AVD home")
