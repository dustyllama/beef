from pathlib import Path

p = Path(__file__).resolve().parent / "v8_emulator_smoke.sh"
s = p.read_text()
old = '''emulator -avd "$AVD_NAME" -no-window -no-audio -no-boot-anim -no-snapshot -gpu swiftshader_indirect -no-metrics $ACCEL > /tmp/nt-emulator.log 2>&1 &
EMU_PID=$!
trap 'kill "$EMU_PID" 2>/dev/null || true' EXIT

adb wait-for-device
for _ in $(seq 1 180); do
  [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\\r')" == "1" ]] && break
  sleep 2
done
[[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\\r')" == "1" ]] || fail "emulator did not boot"
'''
new = '''emulator -avd "$AVD_NAME" -no-window -no-audio -no-boot-anim -no-snapshot -gpu swiftshader -no-metrics $ACCEL > /tmp/nt-emulator.log 2>&1 &
EMU_PID=$!
trap 'kill "$EMU_PID" 2>/dev/null || true' EXIT

# Never let adb wait-for-device hang the entire CI job. New emulator releases can
# fail before registering with adb, so bound discovery, verify the emulator is
# still alive, and surface its own log immediately when startup goes wrong.
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
if old not in s:
    raise SystemExit("emulator boot block anchor not found")
p.write_text(s.replace(old, new, 1))
print("Hardened v0.8.1 emulator boot detection")
