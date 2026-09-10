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
print('Fixed v8 controls insertion anchor')
