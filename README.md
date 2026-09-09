# NeuronTap

A private, local-first Android gallery that records one-button reaction behavior and turns it into personal longitudinal statistics.

## What the first MVP does

- Pick a gallery folder using Android's Storage Access Framework.
- Recursively index local images and videos.
- Swipe through media inside the app.
- Play local video with Media3.
- One large reaction button records raw down/up timestamps, press duration, first-tap latency, dwell, and video position.
- Records video play/pause/seek events.
- Records browsing sessions.
- A **Log a finish** action creates a confirmed finish and locally estimates the most likely media item and active window.
- Wrapped screen shows taps, sessions, confirmed finishes, fastest reaction, longest dwell, active hour, and top behavioral hits.
- Tag Lab supports post-hoc freeform tags.
- Metadata-only CSV export hashes media URIs into anonymous IDs.

## Privacy

The manifest intentionally has **no INTERNET permission**. There are no telemetry, ad, cloud analytics, or crash-reporting SDKs.

The app can see the local folder you explicitly grant through Android's folder picker. The behavioral database stays on the phone.

## Install without coding

GitHub Actions builds `app-debug.apk` from this repository. Open the latest successful **Android Debug APK** workflow run, download the `neurontap-debug-apk` artifact, unzip it, and install `app-debug.apk` on Android.

Android may ask you to allow installation from the app you used to open the APK.

## Development

Toolchain:

- Kotlin
- Jetpack Compose
- SQLiteOpenHelper
- Android Storage Access Framework / DocumentFile
- Coil
- Media3 / ExoPlayer

Build locally with Android Studio or Gradle 8.9 + JDK 17:

```bash
gradle :app:assembleDebug
```
