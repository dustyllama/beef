from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/ViewerUi.kt"
s = p.read_text()

def rep(old, new, label):
    global s
    if old not in s:
        raise RuntimeError(f"v8 controls anchor missing: {label}")
    s = s.replace(old, new, 1)

# Full Stroke is no longer an ongoing manual toggle. Remove v0.7's automatic
# media-transfer/end bookkeeping; the raw declaration point is enough.
rep('''            val previous = items[trackedPage]
            if (fullStrokeActive && previous.id != current.id) {
                controller.endFullStroke(previous.id, videoPositionMs, "media_change")
                controller.startFullStroke(current.id, null, "continued")
                fullStrokeMediaId = current.id
            }
            controller.log(previous.id, EventTypes.VIEW_DWELL, value = now - trackedStartMs, at = now)
''', '''            val previous = items[trackedPage]
            controller.log(previous.id, EventTypes.VIEW_DWELL, value = now - trackedStartMs, at = now)
''', 'remove full-stroke media transfer')

rep('''                Lifecycle.Event.ON_STOP -> {
                    if (fullStrokeActive) {
                        controller.endFullStroke(fullStrokeMediaId ?: current.id, videoPositionMs, "app_background")
                        fullStrokeActive = false; fullStrokeMediaId = null
                    }
                    if (goonActive) {
''', '''                Lifecycle.Event.ON_STOP -> {
                    if (goonActive) {
''', 'remove full-stroke background end')

state_anchor = '    var goonActive by remember { mutableStateOf(false) }\n'
rep(state_anchor, state_anchor + '''    var confirmNutPending by remember { mutableStateOf(false) }
    var instantRemainingMs by remember { mutableLongStateOf(0L) }
''', 'v8 control state')

# Per-media cooldown display updates automatically while the drawer is visible.
anchor = '    val latestVideoPosition by rememberUpdatedState(videoPositionMs)\n'
rep(anchor, anchor + '''
    LaunchedEffect(current.id, declarationDrawerOpen) {
        do {
            val last = prefs.getLong("instant_hard_${current.id}", 0L)
            instantRemainingMs = (60_000L - (System.currentTimeMillis() - last)).coerceAtLeast(0L)
            if (!declarationDrawerOpen || instantRemainingMs <= 0L) break
            delay(250)
        } while (true)
    }

''', 'instant cooldown ticker')

# Add an explicit yes/no guard before writing confirmed-nut ground truth.
box_anchor = '    BoxWithConstraints(Modifier.fillMaxSize().background(Color.Black)) {\n'
confirm_dialog = '''    if (confirmNutPending) {
        AlertDialog(
            onDismissRequest = { confirmNutPending = false },
            title = { Text("Confirm nut?") },
            text = { Text("Record a confirmed nut right now? This is ground truth, not an inference.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmNutPending = false
                    scope.launch {
                        val (_, item) = withContext(Dispatchers.IO) { controller.confirmFinish(current.id, videoPositionMs) }
                        toastMessage = "Confirmed nut locked to ${item?.name ?: current.name}"
                        declarationDrawerOpen = false
                    }
                }) { Text("Yes") }
            },
            dismissButton = { TextButton(onClick = { confirmNutPending = false }) { Text("No") } }
        )
    }

'''
rep(box_anchor, confirm_dialog + box_anchor, 'confirmed nut guard')

# Replace the v0.7 drawer call block with point-based Full Stroke and visible
# per-media Instant Hard cooldown. No cooldown toasts.
start = s.find('            AnimatedVisibility(visible = declarationDrawerOpen, modifier = Modifier.align(Alignment.BottomCenter)) {\n                DeclarationDrawerV7(')
end = s.find('\n            if (reactionVisible) {', start)
if start < 0 or end < 0:
    raise RuntimeError('v8 controls drawer call block missing')
new_block = r'''            AnimatedVisibility(visible = declarationDrawerOpen, modifier = Modifier.align(Alignment.BottomCenter)) {
                DeclarationDrawerV8(
                    showConfirmed = showConfirmed,
                    showInstant = showInstant,
                    showSpiritual = showSpiritual,
                    showFullStroke = showFullStroke,
                    showGoon = showGoon,
                    showEdge = showEdge,
                    goonActive = goonActive,
                    instantRemainingMs = instantRemainingMs,
                    onCustomize = { showSignalSettings = true },
                    onConfirmedNut = { confirmNutPending = true },
                    onInstantHard = {
                        if (instantRemainingMs <= 0L) {
                            val now = System.currentTimeMillis()
                            controller.markInstantHard(current.id, videoPositionMs)
                            prefs.edit().putLong("instant_hard_${current.id}", now).apply()
                            instantRemainingMs = 60_000L
                        }
                    },
                    onSpiritualCoom = {
                        val now = System.currentTimeMillis()
                        val key = "spiritual_${current.id}"
                        if (now - prefs.getLong(key, 0L) >= 2_000L) {
                            controller.markSpiritualCoom(current.id, videoPositionMs)
                            prefs.edit().putLong(key, now).apply()
                        }
                    },
                    onFullStroke = {
                        controller.startFullStroke(current.id, videoPositionMs, "declared_v08")
                        toastMessage = "Full Stroke marked"
                    },
                    onGoon = {
                        if (goonActive) {
                            controller.endGooning(current.id, videoPositionMs, "manual")
                            goonActive = false; toastMessage = "Gooning ended"
                        } else {
                            controller.startGooning(current.id, videoPositionMs)
                            goonActive = true; toastMessage = "Gooning started"
                        }
                    },
                    onEdge = {
                        controller.markEdge(current.id, videoPositionMs)
                        toastMessage = "Edge mark recorded"
                    }
                )
            }

'''
s = s[:start] + new_block + s[end:]

# Insert a new drawer implementation; keep v0.7's old helper unused so patch
# history remains easy to audit.
insert = s.find('@Composable\nprivate fun DeclarationDrawerV7(')
if insert < 0:
    raise RuntimeError('v8 controls drawer insertion point missing')
addon = r'''@Composable
private fun DeclarationDrawerV8(
    showConfirmed: Boolean,
    showInstant: Boolean,
    showSpiritual: Boolean,
    showFullStroke: Boolean,
    showGoon: Boolean,
    showEdge: Boolean,
    goonActive: Boolean,
    instantRemainingMs: Long,
    onCustomize: () -> Unit,
    onConfirmedNut: () -> Unit,
    onInstantHard: () -> Unit,
    onSpiritualCoom: () -> Unit,
    onFullStroke: () -> Unit,
    onGoon: () -> Unit,
    onEdge: () -> Unit
) {
    Surface(color = Color(0xF50B0B0B), shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp), shadowElevation = 18.dp) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("Horny Controls", color = Color.White)
                TextButton(onClick = onCustomize) { Text("Customize") }
            }
            if (showConfirmed || showInstant) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (showConfirmed) DeclarationButton("🥜", "Confirmed Nut", onConfirmedNut, Modifier.weight(1f)) else Spacer(Modifier.weight(1f))
                if (showInstant) {
                    val seconds = ((instantRemainingMs + 999L) / 1000L).coerceAtLeast(0L)
                    val label = if (instantRemainingMs > 0L) "Instant Hard · ${seconds}s" else "Instant Hard"
                    DeclarationButton("⚡", label, onInstantHard, Modifier.weight(1f), enabled = instantRemainingMs <= 0L)
                } else Spacer(Modifier.weight(1f))
            }
            if (showSpiritual || showFullStroke) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (showSpiritual) DeclarationButton("✨", "Spiritual Coom", onSpiritualCoom, Modifier.weight(1f)) else Spacer(Modifier.weight(1f))
                if (showFullStroke) DeclarationButton("🔥", "Full Stroke", onFullStroke, Modifier.weight(1f)) else Spacer(Modifier.weight(1f))
            }
            if (showGoon || showEdge) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (showGoon) DeclarationButton("🌀", if (goonActive) "End Gooning" else "Gooning", onGoon, Modifier.weight(1f)) else Spacer(Modifier.weight(1f))
                if (showEdge) DeclarationButton("🌊", "Edging", onEdge, Modifier.weight(1f)) else Spacer(Modifier.weight(1f))
            }
            Text("Full Stroke is a declaration point. Confirmed Nut requires confirmation and remains ground truth.", color = Color.Gray, fontSize = 11.sp)
        }
    }
}

'''
s = s[:insert] + addon + s[insert:]
p.write_text(s)
print('Applied v8 control semantics')
