from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app/src/main/java/com/neurontap/app/ViewerUi.kt"
s = p.read_text()

def rep(old, new, label):
    global s
    if old not in s:
        raise RuntimeError(f"v7 controls anchor missing: {label}")
    s = s.replace(old, new, 1)

anchor = '    var reactionGestureActive by remember { mutableStateOf(false) }\n'
rep(anchor, anchor + '''    var showSignalSettings by remember { mutableStateOf(false) }
    var showConfirmed by remember { mutableStateOf(prefs.getBoolean("hc_confirmed", true)) }
    var showInstant by remember { mutableStateOf(prefs.getBoolean("hc_instant", true)) }
    var showSpiritual by remember { mutableStateOf(prefs.getBoolean("hc_spiritual", true)) }
    var showFullStroke by remember { mutableStateOf(prefs.getBoolean("hc_fullstroke", true)) }
    var showGoon by remember { mutableStateOf(prefs.getBoolean("hc_goon", false)) }
    var showEdge by remember { mutableStateOf(prefs.getBoolean("hc_edge", false)) }
    var fullStrokeActive by remember { mutableStateOf(false) }
    var fullStrokeMediaId by remember { mutableStateOf<Long?>(null) }
    var goonActive by remember { mutableStateOf(false) }
''', "state")

# Carry Full Stroke attribution across media changes while the state is active.
anchor = '''            val previous = items[trackedPage]
            controller.log(previous.id, EventTypes.VIEW_DWELL, value = now - trackedStartMs, at = now)
'''
rep(anchor, '''            val previous = items[trackedPage]
            if (fullStrokeActive && previous.id != current.id) {
                controller.endFullStroke(previous.id, videoPositionMs, "media_change")
                controller.startFullStroke(current.id, null, "continued")
                fullStrokeMediaId = current.id
            }
            controller.log(previous.id, EventTypes.VIEW_DWELL, value = now - trackedStartMs, at = now)
''', "media transfer")

# Explicit active states end when the app leaves the foreground.
anchor = '''                Lifecycle.Event.ON_STOP -> {
                    if (trackedPage in items.indices && trackedStartMs > 0L) {
'''
rep(anchor, '''                Lifecycle.Event.ON_STOP -> {
                    if (fullStrokeActive) {
                        controller.endFullStroke(fullStrokeMediaId ?: current.id, videoPositionMs, "app_background")
                        fullStrokeActive = false; fullStrokeMediaId = null
                    }
                    if (goonActive) {
                        controller.endGooning(current.id, videoPositionMs, "app_background")
                        goonActive = false
                    }
                    if (trackedPage in items.indices && trackedStartMs > 0L) {
''', "background states")

# Replace the v0.6 drawer instance with the configurable v0.7 drawer.
start = s.find('            AnimatedVisibility(\n                visible = declarationDrawerOpen,')
end = s.find('            if (reactionVisible) {', start)
if start < 0 or end < 0:
    raise RuntimeError("v7 controls drawer block missing")
block = r'''            if (showSignalSettings) {
                SignalSettingsDialogV7(
                    confirmed = showConfirmed,
                    instant = showInstant,
                    spiritual = showSpiritual,
                    fullStroke = showFullStroke,
                    goon = showGoon,
                    edge = showEdge,
                    onSet = { key, enabled ->
                        when (key) {
                            "confirmed" -> showConfirmed = enabled
                            "instant" -> showInstant = enabled
                            "spiritual" -> showSpiritual = enabled
                            "fullstroke" -> showFullStroke = enabled
                            "goon" -> showGoon = enabled
                            "edge" -> showEdge = enabled
                        }
                        prefs.edit().putBoolean("hc_$key", enabled).apply()
                        controller.log(current.id, EventTypes.HORNY_CONTROL_CONFIG, details = "$key=$enabled")
                    },
                    onDismiss = { showSignalSettings = false }
                )
            }

            AnimatedVisibility(visible = declarationDrawerOpen, modifier = Modifier.align(Alignment.BottomCenter)) {
                DeclarationDrawerV7(
                    showConfirmed, showInstant, showSpiritual, showFullStroke, showGoon, showEdge,
                    fullStrokeActive, goonActive,
                    onCustomize = { showSignalSettings = true },
                    onConfirmedNut = {
                        val (_, item) = controller.confirmFinish(current.id, videoPositionMs)
                        if (fullStrokeActive) {
                            controller.endFullStroke(fullStrokeMediaId ?: current.id, videoPositionMs, "confirmed_finish")
                            fullStrokeActive = false; fullStrokeMediaId = null
                        }
                        if (goonActive) {
                            controller.endGooning(current.id, videoPositionMs, "confirmed_finish")
                            goonActive = false
                        }
                        toastMessage = "Confirmed nut locked to ${item?.name ?: current.name}"
                        declarationDrawerOpen = false
                    },
                    onInstantHard = {
                        val now = System.currentTimeMillis()
                        val key = "instant_hard_${current.id}"
                        val remain = 60_000L - (now - prefs.getLong(key, 0L))
                        if (remain > 0L) toastMessage = "Instant Hard cooldown · ${((remain + 999L) / 1000L)}s"
                        else {
                            controller.markInstantHard(current.id, videoPositionMs)
                            prefs.edit().putLong(key, now).apply()
                            toastMessage = "Instant Hard recorded"
                        }
                    },
                    onSpiritualCoom = {
                        val now = System.currentTimeMillis()
                        val key = "spiritual_${current.id}"
                        if (now - prefs.getLong(key, 0L) < 2_000L) toastMessage = "Already recorded"
                        else {
                            controller.markSpiritualCoom(current.id, videoPositionMs)
                            prefs.edit().putLong(key, now).apply()
                            toastMessage = "Spiritual Coom recorded"
                        }
                    },
                    onFullStroke = {
                        if (fullStrokeActive) {
                            controller.endFullStroke(fullStrokeMediaId ?: current.id, videoPositionMs, "manual")
                            fullStrokeActive = false; fullStrokeMediaId = null
                            toastMessage = "Full Stroke ended"
                        } else {
                            controller.startFullStroke(current.id, videoPositionMs, "manual")
                            fullStrokeActive = true; fullStrokeMediaId = current.id
                            toastMessage = "Full Stroke started"
                        }
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
s = s[:start] + block + s[end:]

insert = s.find('@Composable\nprivate fun DeclarationDrawer(')
if insert < 0:
    raise RuntimeError("v7 controls function insertion point missing")
addon = r'''@Composable
private fun DeclarationDrawerV7(
    showConfirmed: Boolean,
    showInstant: Boolean,
    showSpiritual: Boolean,
    showFullStroke: Boolean,
    showGoon: Boolean,
    showEdge: Boolean,
    fullStrokeActive: Boolean,
    goonActive: Boolean,
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
                if (showInstant) DeclarationButton("⚡", "Instant Hard", onInstantHard, Modifier.weight(1f)) else Spacer(Modifier.weight(1f))
            }
            if (showSpiritual || showFullStroke) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (showSpiritual) DeclarationButton("✨", "Spiritual Coom", onSpiritualCoom, Modifier.weight(1f)) else Spacer(Modifier.weight(1f))
                if (showFullStroke) DeclarationButton("🔥", if (fullStrokeActive) "End Full Stroke" else "Full Stroke", onFullStroke, Modifier.weight(1f)) else Spacer(Modifier.weight(1f))
            }
            if (showGoon || showEdge) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (showGoon) DeclarationButton("🌀", if (goonActive) "End Gooning" else "Gooning", onGoon, Modifier.weight(1f)) else Spacer(Modifier.weight(1f))
                if (showEdge) DeclarationButton("🌊", "Edging", onEdge, Modifier.weight(1f)) else Spacer(Modifier.weight(1f))
            }
            Text("Confirmed Nut is ground truth. Potential Nut remains inference only.", color = Color.Gray, fontSize = 11.sp)
        }
    }
}

@Composable
private fun SignalSettingsDialogV7(
    confirmed: Boolean,
    instant: Boolean,
    spiritual: Boolean,
    fullStroke: Boolean,
    goon: Boolean,
    edge: Boolean,
    onSet: (String, Boolean) -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Customize Horny Controls") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                SignalToggleV7("🥜 Confirmed Nut", confirmed) { onSet("confirmed", it) }
                SignalToggleV7("⚡ Instant Hard", instant) { onSet("instant", it) }
                SignalToggleV7("✨ Spiritual Coom", spiritual) { onSet("spiritual", it) }
                SignalToggleV7("🔥 Full Stroke", fullStroke) { onSet("fullstroke", it) }
                SignalToggleV7("🌀 Gooning", goon) { onSet("goon", it) }
                SignalToggleV7("🌊 Edging", edge) { onSet("edge", it) }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Done") } }
    )
}

@Composable
private fun SignalToggleV7(label: String, enabled: Boolean, onSet: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        Text(label)
        TextButton(onClick = { onSet(!enabled) }) { Text(if (enabled) "ON" else "OFF") }
    }
}

'''
s = s[:insert] + addon + s[insert:]
p.write_text(s)
print("Applied v7 controls")
