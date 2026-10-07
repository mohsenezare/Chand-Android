from pathlib import Path
import re

root = Path("source/app/src/main/java/ir/personal/chand")

# iOS-parity UI + persistent card reordering, applied on top of the verified v4 live architecture.
p = root / "MainActivity.kt"
s = p.read_text()

# Keep the picker clean: do not expose TGJU as a duplicate/mislabelled global source.
s = s.replace("""                    SourceButton(
                        text = "بازارهای جهانی",
                        selected = state.catalogSource == CatalogSource.TGJU,
                        onClick = { onSearch(CatalogSource.TGJU, "", false) }
                    )
""", "")

# Match the official product spelling.
s = s.replace('text = "Chand ?!"', 'text = "Chand?!"')

# Imports needed for long-press drag reordering.
imports = [
    ("import androidx.compose.foundation.clickable\n",
     "import androidx.compose.foundation.clickable\nimport androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress\n"),
    ("import androidx.compose.ui.geometry.Offset\n",
     "import androidx.compose.ui.geometry.Offset\nimport androidx.compose.ui.input.pointer.pointerInput\n"),
]
for anchor, replacement in imports:
    if replacement.splitlines()[-1] not in s and anchor in s:
        s = s.replace(anchor, replacement, 1)

# Wire the grid to the ViewModel reorder operation.
old_call = """                    else -> MarketGrid(
                        items = state.visibleItems,
                        gridMode = state.settings.gridMode,
                        onItemClick = { viewModel.showChart(it.id) }
                    )
"""
new_call = """                    else -> MarketGrid(
                        items = state.visibleItems,
                        gridMode = state.settings.gridMode,
                        onItemClick = { viewModel.showChart(it.id) },
                        onMove = viewModel::moveVisibleItem
                    )
"""
if old_call in s:
    s = s.replace(old_call, new_call, 1)
elif "onMove = viewModel::moveVisibleItem" not in s:
    raise SystemExit("MarketGrid call anchor not found")

# Restore the compact iOS-like card grid after the workflow compatibility patch,
# and add long-press drag without changing the card appearance.
grid_start_marker = "@Composable\nprivate fun MarketGrid("
card_start_marker = "@Composable\nprivate fun MarketCard("
grid_start = s.find(grid_start_marker)
card_start = s.find(card_start_marker, grid_start + 1 if grid_start >= 0 else 0)
if grid_start < 0 or card_start <= grid_start:
    raise SystemExit("MarketGrid block not found")

new_grid = """@Composable
private fun MarketGrid(
    items: List<MarketItem>,
    gridMode: Boolean,
    onItemClick: (MarketItem) -> Unit,
    onMove: (String, Int) -> Unit
) {
    val gridState = rememberLazyGridState()
    LazyVerticalGrid(
        columns = GridCells.Fixed(if (gridMode) 2 else 1),
        state = gridState,
        contentPadding = PaddingValues(start = 14.dp, end = 14.dp, top = 4.dp, bottom = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
        modifier = Modifier.fillMaxSize()
    ) {
        items(items, key = MarketItem::id) { item ->
            var dragOffset by remember(item.id) { mutableStateOf(Offset.Zero) }
            MarketCard(
                item = item,
                gridMode = gridMode,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(if (gridMode) 1.12f else 2.25f)
                    .pointerInput(item.id, gridMode) {
                        detectDragGesturesAfterLongPress(
                            onDragStart = { dragOffset = Offset.Zero },
                            onDragCancel = { dragOffset = Offset.Zero },
                            onDragEnd = { dragOffset = Offset.Zero },
                            onDrag = { change, amount ->
                                change.consume()
                                dragOffset += amount

                                val horizontalThreshold = size.width * 0.32f
                                val verticalThreshold = size.height * 0.32f

                                if (gridMode) {
                                    when {
                                        dragOffset.x > horizontalThreshold -> {
                                            onMove(item.id, 1)
                                            dragOffset = Offset.Zero
                                        }
                                        dragOffset.x < -horizontalThreshold -> {
                                            onMove(item.id, -1)
                                            dragOffset = Offset.Zero
                                        }
                                        dragOffset.y > verticalThreshold -> {
                                            onMove(item.id, 2)
                                            dragOffset = Offset.Zero
                                        }
                                        dragOffset.y < -verticalThreshold -> {
                                            onMove(item.id, -2)
                                            dragOffset = Offset.Zero
                                        }
                                    }
                                } else {
                                    when {
                                        dragOffset.y > verticalThreshold -> {
                                            onMove(item.id, 1)
                                            dragOffset = Offset.Zero
                                        }
                                        dragOffset.y < -verticalThreshold -> {
                                            onMove(item.id, -1)
                                            dragOffset = Offset.Zero
                                        }
                                    }
                                }
                            }
                        )
                    },
                onClick = { onItemClick(item) }
            )
        }
    }
}

"""
s = s[:grid_start] + new_grid + s[card_start:]

# Remove any compatibility LIVE overlay injected over the badge; the official-style
# card stays clean while the header status dot still reflects live connectivity.
injected = """                    Box(modifier = Modifier.size(if (compact) 45.dp else 54.dp)) {
                        MarketBadge(item, Modifier.fillMaxSize())
                        if (item.origin == DataOrigin.LIVE) {
                            Surface(color = Color(0xFF245B43), shape = RoundedCornerShape(6.dp),
                                modifier = Modifier.align(Alignment.TopEnd)) {
                                Text("LIVE", color = Color.White, fontSize = 7.sp, fontWeight = FontWeight.Bold,
                                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp))
                            }
                        }
                    }
"""
s = s.replace(injected, "                    MarketBadge(item, Modifier.size(if (compact) 45.dp else 54.dp))\n")
s = s.replace("import androidx.compose.foundation.lazy.grid.GridItemSpan\n", "")
p.write_text(s)

# Persist reorder in UserSettings.visibleIds, so refreshes and relaunches keep the user's order.
vm = root / "MainViewModel.kt"
v = vm.read_text()
if "fun moveVisibleItem(itemId: String, delta: Int)" not in v:
    anchor = "    fun setGridMode(enabled: Boolean) = updateSettings { copy(gridMode = enabled) }\n"
    method = """    fun moveVisibleItem(itemId: String, delta: Int) {
        val ids = _uiState.value.settings.visibleIds
        val from = ids.indexOf(itemId)
        if (from < 0) return
        val to = (from + delta).coerceIn(0, ids.lastIndex)
        if (from == to) return
        val reordered = ids.toMutableList()
        val moved = reordered.removeAt(from)
        reordered.add(to, moved)
        updateSettings { copy(visibleIds = reordered) }
    }

"""
    if anchor not in v:
        raise SystemExit("setGridMode anchor not found")
    v = v.replace(anchor, anchor + "\n" + method, 1)

# Fast reconciliation recovers dropped streams without replacing valid live values.
v = v.replace("const val LIVE_RECONCILE_INTERVAL_MS = 30_000L", "const val LIVE_RECONCILE_INTERVAL_MS = 1_000L")
v = v.replace("const val LIVE_RECONCILE_INTERVAL_MS = 5_000L", "const val LIVE_RECONCILE_INTERVAL_MS = 1_000L")
v = v.replace("const val ACTIVE_REFRESH_INTERVAL_MS = 750L", "const val ACTIVE_REFRESH_INTERVAL_MS = 1_000L")
vm.write_text(v)

# Mark this build as the iOS-parity release candidate.
gradle = Path("source/app/build.gradle.kts")
g = gradle.read_text()
m = re.search(r"versionCode\s*=\s*(\d+)", g)
if m:
    next_code = max(int(m.group(1)), 14)
    g = re.sub(r"versionCode\s*=\s*\d+", f"versionCode = {next_code}", g, count=1)
g = re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "4.1-ios-parity"', g, count=1)
gradle.write_text(g)

strings = Path("source/app/src/main/res/values/strings.xml")
if strings.exists():
    x = strings.read_text()
    x = x.replace("Chand ?!", "Chand?!")
    strings.write_text(x)
