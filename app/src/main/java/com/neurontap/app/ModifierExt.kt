package com.neurontap.app

import androidx.compose.foundation.layout.offset as layoutOffset
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.IntOffset

fun Modifier.offset(offset: () -> IntOffset): Modifier = this.layoutOffset(offset)
