from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/ViewerUi.kt"
s = p.read_text()

# Pointer-input gesture scopes are restricted coroutines: Animatable.stop/snapTo
# cannot be called directly inside them. Keep live gesture state as plain Compose
# floats, then animate double-taps from a normal remembered coroutine scope.
s = s.replace('val scale = remember(item.id) { Animatable(1f) }', 'var scale by remember(item.id) { mutableFloatStateOf(1f) }')
s = s.replace('val offsetX = remember(item.id) { Animatable(0f) }', 'var offsetX by remember(item.id) { mutableFloatStateOf(0f) }')
s = s.replace('val offsetY = remember(item.id) { Animatable(0f) }', 'var offsetY by remember(item.id) { mutableFloatStateOf(0f) }')
s = s.replace('scale.value', 'scale')
s = s.replace('offsetX.value', 'offsetX')
s = s.replace('offsetY.value', 'offsetY')
s = s.replace('                    scale.stop(); offsetX.stop(); offsetY.stop()\n', '')
s = s.replace('                        scale.stop(); offsetX.stop(); offsetY.stop()\n', '')
s = s.replace('                        scale.snapTo(nextScale)\n                        offsetX.snapTo(nextOffset.x)\n                        offsetY.snapTo(nextOffset.y)', '                        scale = nextScale\n                        offsetX = nextOffset.x\n                        offsetY = nextOffset.y')
s = s.replace('                        scale.snapTo(nextScale); offsetX.snapTo(nextOffset.x); offsetY.snapTo(nextOffset.y)', '                        scale = nextScale; offsetX = nextOffset.x; offsetY = nextOffset.y')
s = s.replace('                            scale.snapTo(1f); offsetX.snapTo(0f); offsetY.snapTo(0f); endZoom(now)', '                            scale = 1f; offsetX = 0f; offsetY = 0f; endZoom(now)')
s = s.replace('                    offsetX.snapTo(next.x); offsetY.snapTo(next.y)', '                    offsetX = next.x; offsetY = next.y')

old = '''                        scope.launch {
                            coroutineScope {
                                launch { scale.animateTo(targetScale, tween(190)) }
                                launch { offsetX.animateTo(focalOffset.x, tween(190)) }
                                launch { offsetY.animateTo(focalOffset.y, tween(190)) }
                            }
                            if (targetScale <= 1f) endZoom(System.currentTimeMillis())
                            else controller.log(item.id, EventTypes.ZOOM_SCALE, value = (targetScale * 1000).roundToInt().toLong(), x = tap.x.toDouble(), y = tap.y.toDouble(), details = "double_tap")
                        }
'''
new = '''                        scope.launch {
                            val startScale = scale
                            val startX = offsetX
                            val startY = offsetY
                            val progress = Animatable(0f)
                            progress.animateTo(1f, tween(190)) {
                                scale = startScale + (targetScale - startScale) * value
                                offsetX = startX + (focalOffset.x - startX) * value
                                offsetY = startY + (focalOffset.y - startY) * value
                            }
                            scale = targetScale; offsetX = focalOffset.x; offsetY = focalOffset.y
                            if (targetScale <= 1f) endZoom(System.currentTimeMillis())
                            else controller.log(item.id, EventTypes.ZOOM_SCALE, value = (targetScale * 1000).roundToInt().toLong(), x = tap.x.toDouble(), y = tap.y.toDouble(), details = "double_tap")
                        }
'''
if old not in s:
    raise RuntimeError('image double-tap animation anchor missing')
s = s.replace(old, new, 1)

old2 = '''                        scope.launch {
                            coroutineScope {
                                launch { scale.animateTo(targetScale, tween(190)) }
                                launch { offsetX.animateTo(focalOffset.x, tween(190)) }
                                launch { offsetY.animateTo(focalOffset.y, tween(190)) }
                            }
                            if (targetScale <= 1f) endZoom(System.currentTimeMillis())
                            else controller.log(item.id, EventTypes.ZOOM_SCALE, value = (targetScale * 1000).roundToInt().toLong(), mediaPositionMs = player.currentPosition, x = tap.x.toDouble(), y = tap.y.toDouble(), details = "video;double_tap")
                        }
'''
new2 = '''                        scope.launch {
                            val startScale = scale
                            val startX = offsetX
                            val startY = offsetY
                            val progress = Animatable(0f)
                            progress.animateTo(1f, tween(190)) {
                                scale = startScale + (targetScale - startScale) * value
                                offsetX = startX + (focalOffset.x - startX) * value
                                offsetY = startY + (focalOffset.y - startY) * value
                            }
                            scale = targetScale; offsetX = focalOffset.x; offsetY = focalOffset.y
                            if (targetScale <= 1f) endZoom(System.currentTimeMillis())
                            else controller.log(item.id, EventTypes.ZOOM_SCALE, value = (targetScale * 1000).roundToInt().toLong(), mediaPositionMs = player.currentPosition, x = tap.x.toDouble(), y = tap.y.toDouble(), details = "video;double_tap")
                        }
'''
if old2 not in s:
    raise RuntimeError('video double-tap animation anchor missing')
s = s.replace(old2, new2, 1)

p.write_text(s)
print('Fixed v0.6 gesture animation state')
