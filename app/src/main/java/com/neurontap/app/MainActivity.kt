package com.neurontap.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.core.view.WindowCompat

class MainActivity : ComponentActivity() {
    private lateinit var controller: AppController

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, true)
        window.statusBarColor = android.graphics.Color.BLACK
        window.navigationBarColor = android.graphics.Color.BLACK
        controller = AppController(this, NeuronDb(this))
        setContent { NeuronTapTheme { NeuronTapApp(controller) } }
    }

    override fun onStart() {
        super.onStart()
        controller.onForeground()
    }

    override fun onStop() {
        controller.onBackground()
        super.onStop()
    }
}

private enum class AppPage { COLLECTION, WRAPPED, TAGS }

@Composable
private fun NeuronTapTheme(content: @Composable () -> Unit) {
    val colors = darkColorScheme(
        primary = Color(0xFFE53935),
        onPrimary = Color.White,
        background = Color.Black,
        onBackground = Color.White,
        surface = Color.Black,
        onSurface = Color.White,
        surfaceVariant = Color(0xFF151515),
        onSurfaceVariant = Color(0xFFE0E0E0),
        secondaryContainer = Color(0xFF2A1114),
        onSecondaryContainer = Color.White
    )
    MaterialTheme(colorScheme = colors, content = content)
}

@Composable
private fun NeuronTapApp(controller: AppController) {
    var page by remember { mutableStateOf(AppPage.COLLECTION) }
    when (page) {
        AppPage.COLLECTION -> CollectionScreen(
            controller = controller,
            onOpenWrapped = { page = AppPage.WRAPPED },
            onOpenTags = { page = AppPage.TAGS }
        )
        AppPage.WRAPPED -> AnalyticsScaffold("Horny Archives", onBack = { page = AppPage.COLLECTION }) {
            WrappedContent(controller)
        }
        AppPage.TAGS -> AnalyticsScaffold("Tag Lab", onBack = { page = AppPage.COLLECTION }) {
            TagLabContent(controller.db)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AnalyticsScaffold(title: String, onBack: () -> Unit, content: @Composable () -> Unit) {
    BackHandler { onBack() }
    Scaffold(
        containerColor = Color.Black,
        topBar = {
            TopAppBar(
                title = { Text(title) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Black)
            )
        }
    ) { padding ->
        androidx.compose.foundation.layout.Box(Modifier.fillMaxSize().padding(padding)) { content() }
    }
}
