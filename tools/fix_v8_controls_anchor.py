from pathlib import Path

p = Path(__file__).resolve().parent / "apply_v8_controls.py"
s = p.read_text()
old = '''box_anchor = '    BoxWithConstraints(Modifier.fillMaxSize().background(Color.Black)) {\\n'\n'''
if old not in s:
    raise RuntimeError('expected anchor declaration missing')
s = s.replace(old, "", 1)
old_call = "rep(box_anchor, confirm_dialog + box_anchor, 'confirmed nut guard')\n"
if old_call not in s:
    raise RuntimeError('expected anchor replacement call missing')
new_call = '''box_at = s.find('    BoxWithConstraints(')\nif box_at < 0:\n    raise RuntimeError('v8 controls insertion point missing')\ns = s[:box_at] + confirm_dialog + s[box_at:]\n'''
s = s.replace(old_call, new_call, 1)
p.write_text(s)

# v0.8.3 reaction-clearance repair targets the generated v0.6 viewer, whose
# two-finger resize keeps the button's top-left fixed. Correct the later repair
# script's stale center-anchored seekbar-overlap patch before CI applies it.
p = Path(__file__).resolve().parent / "apply_v8_repair.py"
s = p.read_text()
old_resize = "reactionYPx = (centerY - nextSize / 2f).coerceIn(0f, (maxH - nextSize).coerceAtLeast(0f))"
new_resize = "reactionYPx = reactionYPx.coerceIn(0f, (maxH - nextSize).coerceAtLeast(0f))"
old_resize_fixed = "reactionYPx = (centerY - nextSize / 2f).coerceIn(0f, reactionMaxY(nextSize))"
new_resize_fixed = "reactionYPx = reactionYPx.coerceIn(0f, reactionMaxY(nextSize))"
if old_resize not in s or old_resize_fixed not in s:
    raise RuntimeError('v8 repair reaction resize anchor source missing')
s = s.replace(old_resize, new_resize, 1)
s = s.replace(old_resize_fixed, new_resize_fixed, 1)
p.write_text(s)

print('Fixed v8 controls and reaction-repair insertion anchors')
