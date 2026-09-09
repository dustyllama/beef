package com.neurontap.app

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape

@Composable
fun Surface(
    modifier: Modifier = Modifier,
    color: Color = Color.Transparent,
    shape: Shape,
    content: @Composable () -> Unit
) {
    androidx.compose.material3.Surface(
        modifier = modifier,
        color = color,
        shape = shape,
        content = content
    )
}
