from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/ViewerUi.kt"
s = p.read_text()

def rep(old, new, label):
    global s
    if old not in s:
        raise RuntimeError(f"v8 viewer anchor missing: {label}")
    s = s.replace(old, new, 1)

# One player host lives for the entire viewer instead of one ExoPlayer per
# HorizontalPager page.
anchor = '    val scope = rememberCoroutineScope()\n'
rep(anchor, anchor + '''    val videoHost = remember { ViewerVideoHostV8(context.applicationContext, controller) }
    DisposableEffect(videoHost) { onDispose { videoHost.release() } }
''', 'viewer video host')

rep('''                MediaViewerPane(
                    item = item,
                    controller = controller,
''', '''                MediaViewerPane(
                    item = item,
                    controller = controller,
                    videoHost = videoHost,
''', 'pass video host')

rep('''private fun MediaViewerPane(
    item: MediaItem,
    controller: AppController,
''', '''private fun MediaViewerPane(
    item: MediaItem,
    controller: AppController,
    videoHost: ViewerVideoHostV8,
''', 'pane host signature')

rep('''        ViewerVideoV7(
            item = item,
''', '''        ViewerVideoV8(
            host = videoHost,
            item = item,
''', 'route to v8 video')

# v0.7 made vertical exit absurdly permissive. Only claim a touch stream once
# it is clearly vertical; until then HorizontalPager gets a fair chance.
start = s.find('        val verticalViewerGesture = Modifier.pointerInput(')
end = s.find('\n\n        Box(Modifier.fillMaxSize().then(verticalViewerGesture).then(reactionGesture))', start)
if start < 0 or end < 0:
    raise RuntimeError('v8 viewer vertical gesture block missing')
vertical = r'''        val verticalViewerGesture = Modifier.pointerInput(current.id, currentZoomed, declarationDrawerOpen, reactionXPx, reactionYPx, reactionSizePx, reactionVisible) {
            val threshold = with(density) { 72.dp.toPx() }
            awaitEachGesture {
                val first = awaitFirstDown(requireUnconsumed = false)
                if (insideButton(first.position)) {
                    while (true) { val e = awaitPointerEvent(); if (e.changes.none { it.pressed }) break }
                    return@awaitEachGesture
                }
                var dx = 0f
                var dy = 0f
                var intent = 0 // 0 undecided, 1 vertical, 2 horizontal
                var previous = first.position
                var multiTouch = false
                while (true) {
                    val e = awaitPointerEvent()
                    val pressed = e.changes.filter { it.pressed }
                    if (pressed.isEmpty()) break
                    if (pressed.size > 1) { multiTouch = true; break }
                    val down = pressed.first()
                    val delta = down.position - previous
                    previous = down.position
                    dx += delta.x; dy += delta.y
                    if (intent == 0 && (abs(dx) > touchSlop * 1.4f || abs(dy) > touchSlop * 1.4f)) {
                        intent = if (abs(dy) > abs(dx) * 1.35f) 1 else if (abs(dx) > abs(dy) * 1.10f) 2 else 0
                    }
                    if (intent == 1) down.consume()
                }
                if (!multiTouch && !currentZoomed && intent == 1 && abs(dy) > threshold && abs(dy) > abs(dx) * 1.35f) {
                    if (dy < 0f) {
                        if (!declarationDrawerOpen) {
                            declarationDrawerOpen = true
                            controller.log(current.id, EventTypes.DECLARATION_DRAWER_OPEN, mediaPositionMs = latestVideoPosition)
                        }
                    } else {
                        if (declarationDrawerOpen) {
                            declarationDrawerOpen = false
                            controller.log(current.id, EventTypes.DECLARATION_DRAWER_CLOSE, mediaPositionMs = latestVideoPosition)
                        } else onClose()
                    }
                }
            }
        }'''
s = s[:start] + vertical + s[end:]

p.write_text(s)
print('Applied v8 viewer/video wiring and gesture arbitration')
