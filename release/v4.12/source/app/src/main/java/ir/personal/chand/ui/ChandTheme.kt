package ir.personal.chand.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import ir.personal.chand.data.ThemeMode

private val DarkColors = darkColorScheme(
    primary = Color(0xFF61B98A),
    background = Color.Black,
    surface = Color(0xFF1C1C1E),
    surfaceVariant = Color(0xFF2C2C2E),
    onBackground = Color.White,
    onSurface = Color.White,
    onSurfaceVariant = Color(0xFFB5B5BA),
    error = Color(0xFFFF6262)
)

private val LightColors = lightColorScheme(
    primary = Color(0xFF307653),
    background = Color(0xFFE8E5E2),
    surface = Color(0xFFFAF9F7),
    surfaceVariant = Color(0xFFE2DFDC),
    onBackground = Color(0xFF111111),
    onSurface = Color(0xFF111111),
    onSurfaceVariant = Color(0xFF68666A),
    error = Color(0xFFD83B3B)
)

@Composable
fun ChandTheme(themeMode: ThemeMode, content: @Composable () -> Unit) {
    val dark = when (themeMode) {
        ThemeMode.SYSTEM -> isSystemInDarkTheme()
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
    }
    MaterialTheme(
        colorScheme = if (dark) DarkColors else LightColors,
        typography = MaterialTheme.typography,
        content = content
    )
}
