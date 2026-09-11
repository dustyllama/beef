from pathlib import Path

p = Path(__file__).resolve().parent / "v8_emulator_smoke_v2.sh"
s = p.read_text()

old = "read -r sw sh < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=' ' "
new = "IFS=, read -r sw sh < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "
count = s.count(old)
if count != 3:
    raise RuntimeError(f"expected 3 ffprobe dimension readers, found {count}")
s = s.replace(old, new)
p.write_text(s)
print("Fixed 3 v0.8.1 smoke ffprobe dimension readers")
