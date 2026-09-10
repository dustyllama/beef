from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = ROOT / "app/src/main/AndroidManifest.xml"
s = manifest.read_text()
if 'android:allowBackup="true"' in s:
    s = s.replace('android:allowBackup="true"', 'android:allowBackup="false"', 1)
elif 'android:allowBackup="false"' not in s:
    s = s.replace('<application\n', '<application\n        android:allowBackup="false"\n', 1)
if 'android:usesCleartextTraffic=' not in s:
    s = s.replace('android:label="NeuronTap"', 'android:label="NeuronTap"\n        android:usesCleartextTraffic="false"', 1)
manifest.write_text(s)
print('Applied v8 local-first security defaults')
