from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/ViewerUi.kt"
s = p.read_text()

def rep(old: str, new: str, label: str):
    global s
    if old not in s:
        raise RuntimeError(f"v8 video integration anchor missing: {label}")
    s = s.replace(old, new, 1)

# One ViewerScreen-owned player host. Pager neighbors render thumbnails only;
# only the active video binds the decoder/surface.
scope_anchor = '    val scope = rememberCoroutineScope()\n'
rep(scope_anchor, scope_anchor + '''    val videoHost = remember { ViewerVideoHostV8(context, controller) }
    DisposableEffect(videoHost) {
        onDispose { videoHost.release() }
    }
''', 'viewer video host')

# Thread the shared host through the pager pane.
rep('''                    item = item,
                    controller = controller,
                    active = page == pagerState.currentPage,
''', '''                    item = item,
                    controller = controller,
                    videoHost = videoHost,
                    active = page == pagerState.currentPage,
''', 'pane call host')

rep('''private fun MediaViewerPane(
    item: MediaItem,
    controller: AppController,
    active: Boolean,
''', '''private fun MediaViewerPane(
    item: MediaItem,
    controller: AppController,
    videoHost: ViewerVideoHostV8,
    active: Boolean,
''', 'pane signature host')

# v0.7 routed videos to ViewerVideoV7. Replace that with the single-host v0.8
# implementation. Preserve all existing callbacks/settings.
needle = '''        ViewerVideoV7(
            item = item,
            controller = controller,
'''
if needle not in s:
    # Defensive fallback for source variants that still route to ViewerVideo.
    needle = '''        ViewerVideo(
            item = item,
            controller = controller,
'''
if needle not in s:
    raise RuntimeError('v8 video integration anchor missing: video pane route')
s = s.replace(needle, '''        ViewerVideoV8(
            host = videoHost,
            item = item,
            controller = controller,
''', 1)

p.write_text(s)
print('Applied v8 single-player video integration')
