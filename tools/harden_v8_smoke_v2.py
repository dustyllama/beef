from pathlib import Path

p = Path(__file__).resolve().parent / "v8_emulator_smoke_v2.sh"
s = p.read_text()

old_wait = '''wait_for_scanned_media() {
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
'''
new_wait = '''wait_for_media_ready() {
  local uri="$1"
  local name="$2"
  local label="$3"
  local rows line
  for _ in $(seq 1 45); do
    rows="$(adb shell content query --uri "$uri" --projection _display_name:is_pending:_size 2>/dev/null || true)"
    line="$(grep -F "_display_name=$name" <<<"$rows" | head -1 || true)"
    if [[ "$line" == *"is_pending=0"* && "$line" =~ _size=([1-9][0-9]*) ]]; then
      echo "$label ready in MediaStore"
      return 0
    fi
    sleep 1
  done
  print_media_diagnostics
  fail "$label never reached finalized MediaStore state"
}

wait_for_scanned_media() {
  wait_for_media_ready content://media/external/video/media nt_v8_loop.mp4 "QA video"
  wait_for_media_ready content://media/external/images/media nt_gallery_sentinel.png "QA image"
  echo "Android MediaStore finalized both cold-start QA seed files"
}
'''
if old_wait not in s:
    raise RuntimeError("v8 smoke finalized-media wait anchor missing")
s = s.replace(old_wait, new_wait, 1)

old_initial = '''wait_media_tile_count 2 "All gallery indexing"

# Exercise the exact cold-start tab path that previously queued conflicting swipes.
'''
new_initial = '''wait_media_tile_count 2 "All gallery indexing"

# Production gallery behavior: adding media while NeuronTap is already open
# must appear automatically. No manual Refresh and no app restart are allowed.
ffmpeg -hide_banner -loglevel error -y -f lavfi -i color=c=blue:size=300x300:rate=1 -frames:v 1 -update 1 /tmp/nt-hot-add.png
adb push /tmp/nt-hot-add.png /sdcard/Pictures/nt_hot_add.png >/dev/null
adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Pictures/nt_hot_add.png >/dev/null
wait_for_media_ready content://media/external/images/media nt_hot_add.png "Hot-added QA image"
wait_media_tile_count 3 "Live MediaStore observation"

# Exercise the exact cold-start tab path that previously queued conflicting swipes.
'''
if old_initial not in s:
    raise RuntimeError("v8 smoke hot-add insertion anchor missing")
s = s.replace(old_initial, new_initial, 1)

p.write_text(s)
print("Hardened v0.8.3 smoke for finalized MediaStore rows and live additions")
