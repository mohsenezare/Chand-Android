#!/usr/bin/env python3
"""Scoped v4.8.8 visual patch on top of the verified v4.8.7 source.

Only MainActivity.kt and app/build.gradle.kts are modified. No data, market,
widget, search, settings, or refresh callback logic is changed.
"""
from pathlib import Path
import re

ui_path = Path("source/app/src/main/java/ir/personal/chand/MainActivity.kt")
gradle_path = Path("source/app/build.gradle.kts")
s = ui_path.read_text(encoding="utf-8")
before = s

# Keep animations on the small indicator, not inside the prices/cards.
needle = "import androidx.compose.animation.animateContentSize\n"
assert s.count(needle) == 1, "v4.8.7 animation import missing"
s = s.replace(needle, needle + "import androidx.compose.animation.core.*\n", 1)

# Hide the old header's status dot only during startup; preserve its behavior after.
assert s.count("ChandHeader(state.connectionState)") == 1
s = s.replace(
    "ChandHeader(state.connectionState)",
    "ChandHeader(state.connectionState, startupLoading = state.loading && state.snapshot == null)",
    1
)
signature = "private fun ChandHeader(connectionState: LiveConnectionState) {"
assert s.count(signature) == 1, "header signature changed"
s = s.replace(
    signature,
    "private fun ChandHeader(connectionState: LiveConnectionState, startupLoading: Boolean) {",
    1
)
header_start = s.index("private fun ChandHeader(")
header_end = s.index("\n@Composable", header_start + 1)
header = s[header_start:header_end]
assert header.count("StatusDot(connectionState)") == 1, "unexpected header status dot"
header = header.replace(
    "StatusDot(connectionState)",
    "if (!startupLoading) StatusDot(connectionState)", 1
)
s = s[:header_start] + header + s[header_end:]

# The first-load spinner becomes a centered, gently pulsing Telegram wordmark.
old_loading = """state.loading && state.snapshot == null -> CircularProgressIndicator(
                        color = ChandMuted,
                        strokeWidth = 2.dp,
                        modifier = Modifier.align(Alignment.Center)
                    )"""
assert s.count(old_loading) == 1, "startup loading block not found"
s = s.replace(old_loading,
              "state.loading && state.snapshot == null -> TelegramStartupLabel(Modifier.align(Alignment.Center))",
              1)

# Keep real pull-to-refresh behavior intact. Translate the existing grid on a
# render layer, following the finger without recomposing the quote cards.
start = s.index("@Composable\nprivate fun MarketGrid(")
indicator = s.index("@Composable\nprivate fun IosPullRefreshIndicator(", start)
segment = s[start:indicator]
grid_modifier = "modifier = Modifier.fillMaxSize()\n    ) {"
grid_pos = segment.index("LazyVerticalGrid(")
grid_head, grid_body = segment[:grid_pos], segment[grid_pos:]
grid_anchor = """                onRefresh = onPullRefresh
            )
    ) {"""
assert grid_body.count(grid_anchor) == 1, "expected pull-to-refresh grid modifier missing"
grid_body = grid_body.replace(
    grid_anchor,
    """                onRefresh = onPullRefresh
            )
            .graphicsLayer {
                // Render-layer translation follows the pull without re-composing prices.
                translationY = pullState.distanceFraction.coerceIn(0f, 1.25f) * 52.dp.toPx()
            }
    ) {""", 1
)
segment = grid_head + grid_body
s = s[:start] + segment + s[indicator:]

# Replace the former frame-by-frame 12-tick spinner and large pill with a much
# quieter iOS-inspired spring/fade capsule, with drag progress and release text.
start = s.index("@Composable\nprivate fun IosPullRefreshIndicator(")
end = s.index("@Composable\nprivate fun MarketCard(", start)
replacement = """@Composable
private fun IosPullRefreshIndicator(
    distanceFraction: () -> Float,
    isRefreshing: Boolean,
    modifier: Modifier = Modifier
) {
    val progress = distanceFraction().coerceIn(0f, 1.2f)
    val visible by animateFloatAsState(
        targetValue = if (isRefreshing) 1f else (progress * 1.4f).coerceIn(0f, 1f),
        animationSpec = tween(durationMillis = 110),
        label = "refresh reveal"
    )
    if (visible <= 0.01f && !isRefreshing) return

    val light = MaterialTheme.colorScheme.background.luminance() > 0.5f
    val foreground = if (light) Color(0xFF2D3748) else Color(0xFFEDF1F8)
    val accent = if (light) Color(0xFF4B81F0) else Color(0xFF95B8FF)
    Surface(
        color = if (light) Color(0xFFF5F7FB) else Color(0xFF292D37),
        contentColor = foreground,
        shape = RoundedCornerShape(24.dp),
        shadowElevation = 3.dp,
        modifier = modifier.graphicsLayer {
            alpha = visible
            translationY = (1f - visible) * (-16.dp.toPx())
            scaleX = 0.9f + 0.1f * visible
            scaleY = scaleX
        }
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            if (isRefreshing) {
                CircularProgressIndicator(
                    modifier = Modifier.size(18.dp),
                    color = accent,
                    strokeWidth = 2.dp
                )
            } else {
                CircularProgressIndicator(
                    progress = { progress.coerceIn(0.02f, 1f) },
                    modifier = Modifier.size(18.dp),
                    color = accent,
                    trackColor = foreground.copy(alpha = 0.12f),
                    strokeWidth = 2.dp
                )
            }
            Text(
                text = when {
                    isRefreshing -> "در حال بروزرسانی…"
                    progress >= 1f -> "رها کنید تا بروزرسانی شود"
                    else -> "برای بروزرسانی پایین بکشید"
                },
                fontSize = 11.sp,
                fontWeight = FontWeight.Medium,
                maxLines = 1
            )
        }
    }
}

@Composable
private fun TelegramStartupLabel(modifier: Modifier = Modifier) {
    val transition = rememberInfiniteTransition(label = "telegram startup pulse")
    val pulse by transition.animateFloat(
        initialValue = 0.62f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 820, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "telegram startup opacity"
    )
    val light = MaterialTheme.colorScheme.background.luminance() > 0.5f
    Surface(
        color = if (light) Color(0xFFF2F5FC) else Color(0xFF282C36),
        shape = RoundedCornerShape(24.dp),
        shadowElevation = 2.dp,
        modifier = modifier.graphicsLayer { alpha = pulse }
    ) {
        Text(
            text = "telegram: @Mohsenezare",
            modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
            color = if (light) Color(0xFF3277C9) else Color(0xFF93C8FF),
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1
        )
    }
}

"""
s = s[:start] + replacement + s[end:]
assert s != before and "produceState(0f, isRefreshing)" not in s
assert s.count("TelegramStartupLabel(") == 2
assert s.count("IosPullRefreshIndicator(") == 2
ui_path.write_text(s, encoding="utf-8")

g = gradle_path.read_text(encoding="utf-8")
assert 'versionCode = 48' in g and 'versionName = "4.8.7-pull-animation"' in g
g = g.replace('versionCode = 48', 'versionCode = 49', 1)
g = g.replace('versionName = "4.8.7-pull-animation"',
              'versionName = "4.8.8-ios-refresh-telegram"', 1)
gradle_path.write_text(g, encoding="utf-8")
print("Scoped files changed: MainActivity.kt, app/build.gradle.kts")
print("Prior refresh callback, market and repository files untouched.")
