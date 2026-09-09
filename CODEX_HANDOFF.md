# Codex handoff — NeuronTap

## Product intent

Local-first Android app that learns a single user's attraction / media-engagement patterns from **behavioral metadata**, not mandatory media analysis.

The defining interaction is one reaction button. Do not turn it into a 1–10 rating system. Preserve raw press behavior and let analytics infer meaning later.

## Non-negotiables

1. No Internet permission in the base app.
2. No telemetry SDKs, ads, cloud analytics or crash reporters.
3. Raw observations and derived inferences stay separate.
4. A user-confirmed finish is ground truth; the inferred primary media and active window are explicitly estimates with confidence.
5. Keep the launcher/app name discreet (`NeuronTap`).
6. Media-content analysis, if ever added, is opt-in and on-device by default.

## Event vocabulary

- `SESSION_START`
- `SESSION_END`
- `VIEW_START`
- `VIEW_DWELL` (`value = ms`)
- `REACTION_DOWN`
- `REACTION_UP` (`value = press duration ms`)
- `FIRST_TAP_LATENCY` (`value = ms from view start`)
- `VIDEO_PLAY`
- `VIDEO_PAUSE`
- `VIDEO_SEEK`
- `APP_BACKGROUND`
- `APP_FOREGROUND`
- `COMPLETION_CONFIRMED`

`media_position_ms` is recorded where a meaningful video position exists.

## Immediate engineering priorities

### P0 — compile / device verification
- Sync with current stable Android Studio / AGP.
- Fix any API drift.
- Test SAF recursion against a large folder (20k+ items).
- Verify local image decoding across JPEG, PNG, WebP, GIF and HEIC.
- Verify ExoPlayer can open persisted SAF URIs after process death / reboot.

### P1 — event correctness
- Add database tests for event ordering.
- Add persistent session-state recovery after process death.
- Debounce duplicate `VIDEO_PAUSE` events caused by recomposition.
- Add explicit rewind-derived metrics.
- Record pager scroll direction and return-to-previous-item events.

### P1 — inference
Upgrade finish inference using confirmed sessions as labels while keeping it deterministic first:
- tap count,
- tap burst density,
- press-duration distribution,
- dwell,
- revisit count,
- time from last signal to confirmed finish,
- video replay / seek concentration,
- session-ending proximity.

Store algorithm version alongside every inference once inference changes begin.

### P1 — Wrapped
Add:
- highest taps/second burst,
- biggest sleeper hit,
- biggest tease,
- longest-lived favorite,
- month-over-month top-media churn,
- first-view-to-first-finish lag,
- average search time before final media,
- media switching count inside confirmed sessions,
- per-video reaction timeline heatmap.

### P2 — tag analytics
- Tag-pair interaction effects.
- Compare immediate-response tags vs revisit tags vs finish-conversion tags.
- Detect preference drift by rolling 30/90-day windows.
- Expose effect size and sample count so tiny samples are not presented as certainty.

### P2 — privacy / durability
- Optional encrypted backup.
- Database export/import with schema versioning.
- User-controlled removal of filenames from the local DB, retaining only hashed IDs if desired.

### P3 — Android overlay experiment
Do not start here. Gallery-first is the reliable data source.

For overlays:
- request `SYSTEM_ALERT_WINDOW` only in an opt-in experimental module,
- never use Accessibility merely to scrape unrelated private screen content without a precise user-facing explanation,
- first prototype an overlay that records app package + timing only,
- map content only when there is a robust explicit mechanism.
