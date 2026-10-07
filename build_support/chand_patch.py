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


# ---------------- Investing.com global provider migration ----------------
# The UI still uses the verified v4 model IDs for backwards compatibility,
# but all global search/current-quote network traffic is moved to Investing.com.

# Investing live poller: one grouped quotes request about once per second.
stream = root / "data/TradingViewStreamClient.kt"
stream.write_text(r'''package ir.personal.chand.data

import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.io.Closeable
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.Locale
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit

/**
 * Investing.com quote client for global markets.
 *
 * Uses Investing.com's tvc6 service. Symbols are resolved once through the
 * Investing search endpoint and all visible globals are then polled together.
 */
class TradingViewStreamClient(
    private val httpClient: OkHttpClient,
    symbols: List<String>,
    private val onState: (LiveConnectionState) -> Unit,
    private val onTicks: (List<StreamTick>) -> Unit
) : Closeable {
    private val requestedSymbols = symbols.map(String::trim).filter(String::isNotBlank).distinct()
    private val scheduler = Executors.newSingleThreadScheduledExecutor { task ->
        Thread(task, "chand-investing-live").apply { isDaemon = true }
    }
    private val resolved = linkedMapOf<String, String>()

    @Volatile private var closed = false
    private var future: ScheduledFuture<*>? = null
    private var consecutiveFailures = 0

    fun start() {
        if (requestedSymbols.isEmpty() || closed) return
        onState(LiveConnectionState.CONNECTING)
        future = scheduler.scheduleWithFixedDelay(
            { pollSafely() },
            0L,
            POLL_INTERVAL_MS,
            TimeUnit.MILLISECONDS
        )
    }

    private fun pollSafely() {
        if (closed) return
        try {
            resolveMissingSymbols()
            if (resolved.isEmpty()) {
                onState(LiveConnectionState.POLLING)
                return
            }

            val url = endpoint("quotes") +
                "?symbols=" + encode(resolved.values.distinct().joinToString(","))
            val root = JSONObject(get(url))
            val rows = root.optJSONArray("d") ?: JSONArray()
            val sourceByInvesting = resolved.entries.associate { it.value to it.key }
            val receivedAt = System.currentTimeMillis()

            val ticks = buildList {
                for (index in 0 until rows.length()) {
                    val row = rows.optJSONObject(index) ?: continue
                    val status = row.optString("s")
                    if (status.isNotBlank() && !status.equals("ok", ignoreCase = true)) continue

                    val investingName = row.optString("n").trim()
                    val sourceKey = sourceByInvesting[investingName]
                        ?: resolved.entries.firstOrNull {
                            it.value.equals(investingName, ignoreCase = true)
                        }?.key
                        ?: continue
                    val value = row.optJSONObject("v") ?: continue
                    val price = number(value.opt("lp"))
                        ?: number(value.opt("last"))
                        ?: number(value.opt("close"))
                        ?: continue
                    if (!price.isFinite() || price <= 0.0) continue

                    val change = number(value.opt("ch")) ?: number(value.opt("rch")) ?: 0.0
                    val percent = number(value.opt("chp")) ?: number(value.opt("rchp")) ?: 0.0
                    val high = number(value.opt("high_price")) ?: number(value.opt("high")) ?: price
                    val low = number(value.opt("low_price")) ?: number(value.opt("low")) ?: price
                    val open = number(value.opt("open_price")) ?: number(value.opt("open")) ?: price
                    val timestamp = sourceTimestamp(value) ?: receivedAt

                    add(
                        StreamTick(
                            sourceKey = sourceKey,
                            itemId = "tv:$sourceKey",
                            price = price,
                            high = high.takeIf { it > 0.0 } ?: price,
                            low = low.takeIf { it > 0.0 } ?: price,
                            open = open.takeIf { it > 0.0 } ?: price,
                            change = change,
                            changePercent = percent,
                            direction = when {
                                change > 0.0 -> "high"
                                change < 0.0 -> "low"
                                else -> "same"
                            },
                            sourceUpdatedAtMillis = timestamp,
                            bid = number(value.opt("bid")),
                            ask = number(value.opt("ask"))
                        )
                    )
                }
            }

            if (ticks.isNotEmpty()) {
                consecutiveFailures = 0
                onTicks(ticks)
                onState(LiveConnectionState.LIVE)
            } else {
                consecutiveFailures++
                onState(LiveConnectionState.POLLING)
                if (consecutiveFailures % 5 == 0) resolved.clear()
            }
        } catch (_: Throwable) {
            consecutiveFailures++
            onState(LiveConnectionState.POLLING)
            if (consecutiveFailures % 5 == 0) resolved.clear()
        }
    }

    private fun resolveMissingSymbols() {
        requestedSymbols.forEach { sourceKey ->
            if (resolved.containsKey(sourceKey)) return@forEach

            directInvestingName(sourceKey)?.let { direct ->
                resolved[sourceKey] = direct
                return@forEach
            }

            val target = queryFor(sourceKey)
            val preferredExchange = sourceKey.substringBefore(':', "").uppercase(Locale.US)
            val expectedToken = normalize(sourceKey.substringAfterLast(':'))
            val url = endpoint("search") +
                "?query=" + encode(target) + "&limit=12&type=&exchange="
            val rows = runCatching { JSONArray(get(url)) }.getOrNull()

            val best = if (rows != null) {
                (0 until rows.length())
                    .mapNotNull(rows::optJSONObject)
                    .maxByOrNull { score(it, target, preferredExchange, expectedToken) }
            } else null

            val fullName = best?.optString("full_name")?.trim().orEmpty()
            val exchange = best?.optString("exchange")?.trim().orEmpty()
            val symbol = best?.optString("symbol")?.trim().orEmpty()

            resolved[sourceKey] = when {
                fullName.isNotBlank() -> fullName
                exchange.isNotBlank() && symbol.isNotBlank() -> "$exchange:$symbol"
                else -> sourceKey
            }
        }
    }

    private fun score(
        row: JSONObject,
        target: String,
        preferredExchange: String,
        expectedToken: String
    ): Int {
        val symbol = row.optString("symbol").trim()
        val fullName = row.optString("full_name").trim()
        val description = row.optString("description").trim()
        val exchange = row.optString("exchange").trim().uppercase(Locale.US)
        val type = row.optString("type").trim().lowercase(Locale.US)

        val symbolToken = normalize(symbol)
        val fullToken = normalize(fullName.substringAfterLast(':'))
        val targetToken = normalize(target)
        var score = 0
        if (symbolToken == expectedToken) score += 160
        if (fullToken == expectedToken) score += 150
        if (symbolToken == targetToken) score += 130
        if (fullToken == targetToken) score += 120
        if (description.contains(target, ignoreCase = true)) score += 70
        if (preferredExchange.isNotBlank() && exchange == preferredExchange) score += 35
        if (expectedToken in setOf("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY") &&
            (type.contains("fx") || type.contains("currency"))) score += 40
        if (expectedToken in setOf("BTCUSD", "ETHUSD") && type.contains("crypto")) score += 40
        if (expectedToken == "UKOIL" && description.contains("brent", true)) score += 80
        if (expectedToken == "USOIL" &&
            (description.contains("wti", true) || description.contains("crude oil", true))) score += 80
        return score
    }

    private fun directInvestingName(sourceKey: String): String? {
        val token = normalize(sourceKey.substringAfterLast(':'))
        val direct = when (token) {
            "BTCUSD" -> ":BTC/USD"
            "ETHUSD" -> ":ETH/USD"
            "EURUSD" -> ":EUR/USD"
            "GBPUSD" -> ":GBP/USD"
            "USDJPY" -> ":USD/JPY"
            "XAUUSD" -> ":XAU/USD"
            "XAGUSD" -> ":XAG/USD"
            else -> null
        }
        if (direct != null) return direct

        val prefix = sourceKey.substringBefore(':', "").uppercase(Locale.US)
        return if (sourceKey.startsWith(":") ||
            (sourceKey.contains(':') && prefix !in setOf("BITSTAMP", "FX", "FX_IDC", "OANDA", "FOREXCOM", "TVC"))
        ) sourceKey else null
    }

    private fun queryFor(sourceKey: String): String =
        when (normalize(sourceKey.substringAfterLast(':'))) {
            "BTCUSD" -> "BTC/USD"
            "ETHUSD" -> "ETH/USD"
            "EURUSD" -> "EUR/USD"
            "GBPUSD" -> "GBP/USD"
            "USDJPY" -> "USD/JPY"
            "XAUUSD" -> "XAU/USD"
            "XAGUSD" -> "XAG/USD"
            "UKOIL" -> "Brent Oil"
            "USOIL" -> "Crude Oil WTI"
            else -> sourceKey.substringAfterLast(':')
        }

    private fun get(url: String): String {
        val request = Request.Builder()
            .url(url)
            .header("Accept", "application/json,text/plain,*/*")
            .header("Cache-Control", "no-cache")
            .header("Pragma", "no-cache")
            .header("Referer", "https://tvc-invdn-com.investing.com/")
            .header("User-Agent", USER_AGENT)
            .build()

        return httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) error("Investing HTTP ${response.code}")
            response.body?.string()?.takeIf(String::isNotBlank)
                ?: error("Empty Investing response")
        }
    }

    private fun endpoint(name: String): String =
        "$BASE/${UUID.randomUUID().toString().replace("-", "")}/0/0/0/0/$name"

    override fun close() {
        closed = true
        future?.cancel(true)
        future = null
        scheduler.shutdownNow()
    }

    companion object {
        private const val BASE = "https://tvc6.investing.com"
        private const val POLL_INTERVAL_MS = 1_000L
        private const val USER_AGENT =
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Mobile Safari/537.36"

        private fun encode(value: String): String =
            URLEncoder.encode(value, StandardCharsets.UTF_8.toString())

        private fun normalize(value: String): String =
            value.uppercase(Locale.US).filter(Char::isLetterOrDigit)

        private fun sourceTimestamp(value: JSONObject): Long? {
            val raw = sequenceOf(
                value.opt("lp_time"),
                value.opt("trade_time"),
                value.opt("rtc"),
                value.opt("timestamp")
            ).mapNotNull(::number).firstOrNull { it > 0.0 } ?: return null
            val millis = if (raw < 10_000_000_000L) (raw * 1000.0).toLong() else raw.toLong()
            return millis.takeIf { it in 946684800000L..4102444800000L }
        }

        private fun number(raw: Any?): Double? = when (raw) {
            null, JSONObject.NULL -> null
            is Number -> raw.toDouble()
            else -> raw.toString().replace(",", "").trim().toDoubleOrNull()
        }
    }
}
''')

repo = root / "data/MarketRepository.kt"
r = repo.read_text()

if "import java.util.UUID\n" not in r:
    r = r.replace("import java.util.Locale\n", "import java.util.Locale\nimport java.util.UUID\n", 1)

field_anchor = "    private val retiredIds = linkedSetOf<String>()\n"
if "private val investingSymbolCache" not in r:
    if field_anchor not in r:
        raise SystemExit("retiredIds anchor not found")
    r = r.replace(
        field_anchor,
        field_anchor + "    private val investingSymbolCache = mutableMapOf<String, String>()\n",
        1
    )

old_start = """        val streamHttpClient = httpClient.newBuilder()
            .callTimeout(0, TimeUnit.MILLISECONDS)
            .readTimeout(0, TimeUnit.MILLISECONDS)
            .pingInterval(20, TimeUnit.SECONDS)
            .build()
"""
new_start = """        val streamHttpClient = httpClient.newBuilder()
            .callTimeout(6, TimeUnit.SECONDS)
            .connectTimeout(4, TimeUnit.SECONDS)
            .readTimeout(5, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()
"""
if old_start in r:
    r = r.replace(old_start, new_start, 1)

search_pattern = re.compile(
    r"    private suspend fun searchTradingViewCatalog\(query: String\): List<MarketDescriptor> \{.*?\n    \}\n\n    private suspend fun fetchTradingViewItems\(",
    re.S,
)
search_replacement = r'''    private suspend fun searchTradingViewCatalog(query: String): List<MarketDescriptor> {
        if (query.isBlank()) return emptyList()
        val url = investingEndpoint("search") +
            "?query=" + encode(query) + "&limit=$TRADINGVIEW_SEARCH_LIMIT&type=&exchange="
        val rows = JSONArray(httpGetTradingView(url, 10_000))
        return buildList {
            for (i in 0 until rows.length()) {
                val row = rows.optJSONObject(i) ?: continue
                val rawSymbol = row.optString("symbol").trim()
                val fullName = row.optString("full_name").trim()
                val exchange = row.optString("exchange").trim()
                val sourceKey = when {
                    fullName.isNotBlank() -> fullName
                    exchange.isNotBlank() && rawSymbol.isNotBlank() -> "$exchange:$rawSymbol"
                    else -> continue
                }
                if (exchange.equals("TSE", true) || exchange.contains("TEHRAN", true)) continue

                synchronized(investingSymbolCache) { investingSymbolCache[sourceKey] = sourceKey }

                val description = row.optString("description").trim().ifBlank { rawSymbol }
                val type = row.optString("type").trim().lowercase(Locale.ROOT)
                val currency = row.optString("currency").trim()
                    .ifBlank { row.optString("currency_code").trim() }
                    .uppercase(Locale.US)
                val category = when {
                    type.contains("crypto") -> "ارز دیجیتال جهانی"
                    type.contains("fx") || type.contains("currency") -> "فارکس جهانی"
                    type.contains("future") -> "آتی جهانی"
                    type.contains("commodity") -> "کالا جهانی"
                    type.contains("index") -> "شاخص جهانی"
                    type.contains("stock") || type.contains("fund") || type.contains("etf") -> "سهام جهانی"
                    else -> "بازار جهانی"
                }
                val symbol = when {
                    type.contains("crypto") -> "CRYPTO"
                    type.contains("fx") || type.contains("currency") -> "FX"
                    type.contains("index") -> "INDEX"
                    type.contains("stock") || type.contains("fund") || type.contains("etf") -> "STOCK"
                    else -> "MARKET"
                }
                val unit = when (currency) {
                    "USD" -> "دلار"; "EUR" -> "یورو"; "GBP" -> "پوند"
                    "JPY" -> "ین"; "CHF" -> "فرانک"; "" -> ""; else -> currency
                }
                add(
                    MarketDescriptor(
                        "tv:$sourceKey",
                        sourceKey,
                        description,
                        rawSymbol.ifBlank { sourceKey.substringAfterLast(':') },
                        symbol,
                        MarketSource.TRADINGVIEW,
                        category,
                        unit,
                        1.0
                    )
                )
            }
        }.distinctBy(MarketDescriptor::id).take(TRADINGVIEW_SEARCH_LIMIT)
    }

    private suspend fun fetchTradingViewItems('''
if not search_pattern.search(r):
    raise SystemExit("searchTradingViewCatalog block not found")
r = search_pattern.sub(search_replacement, r, count=1)

fetch_pattern = re.compile(
    r"    private suspend fun fetchTradingViewItems\(\n        descriptors: List<MarketDescriptor>,\n        previousItems: Map<String, MarketItem>,\n        receivedAtMillis: Long\n    \): List<MarketItem> \{.*?\n    \}\n\n    private fun tradingViewMarketFor\(sourceKey: String\): String \{.*?\n    \}\n",
    re.S,
)
fetch_replacement = r'''    private suspend fun fetchTradingViewItems(
        descriptors: List<MarketDescriptor>,
        previousItems: Map<String, MarketItem>,
        receivedAtMillis: Long
    ): List<MarketItem> {
        if (descriptors.isEmpty()) return emptyList()

        val resolvedPairs = coroutineScope {
            descriptors.distinctBy(MarketDescriptor::sourceKey).map { descriptor ->
                async { descriptor.sourceKey to resolveInvestingSymbol(descriptor) }
            }.map { it.await() }
        }
        val resolved = resolvedPairs.mapNotNull { (sourceKey, investingName) ->
            investingName?.let { sourceKey to it }
        }.toMap()
        if (resolved.isEmpty()) return emptyList()

        val url = investingEndpoint("quotes") +
            "?symbols=" + encode(resolved.values.distinct().joinToString(","))
        val root = JSONObject(httpGetTradingView(url, 8_000))
        val rows = root.optJSONArray("d") ?: JSONArray()
        val rowByName = linkedMapOf<String, JSONObject>()
        for (index in 0 until rows.length()) {
            val row = rows.optJSONObject(index) ?: continue
            val name = row.optString("n").trim()
            if (name.isNotBlank()) rowByName[name] = row
        }

        return descriptors.mapNotNull { descriptor ->
            val investingName = resolved[descriptor.sourceKey] ?: return@mapNotNull null
            val row = rowByName[investingName]
                ?: rowByName.entries.firstOrNull { it.key.equals(investingName, true) }?.value
                ?: return@mapNotNull null
            val status = row.optString("s")
            if (status.isNotBlank() && !status.equals("ok", true)) return@mapNotNull null
            val values = row.optJSONObject("v") ?: return@mapNotNull null
            val price = investingNumber(values.opt("lp"))
                ?: investingNumber(values.opt("last"))
                ?: investingNumber(values.opt("close"))
                ?: return@mapNotNull null
            if (!price.isFinite() || price <= 0.0) return@mapNotNull null

            val previous = previousItems[descriptor.id]
            val percent = investingNumber(values.opt("chp"))
                ?: investingNumber(values.opt("rchp"))
                ?: 0.0
            val change = investingNumber(values.opt("ch"))
                ?: investingNumber(values.opt("rch"))
                ?: if (percent != 0.0) price * percent / 100.0 else 0.0
            val high = investingNumber(values.opt("high_price"))
                ?: investingNumber(values.opt("high"))
                ?: previous?.high?.takeIf { it > 0.0 } ?: price
            val low = investingNumber(values.opt("low_price"))
                ?: investingNumber(values.opt("low"))
                ?: previous?.low?.takeIf { it > 0.0 } ?: price
            val buy = investingNumber(values.opt("bid"))?.takeIf { it > 0.0 }
                ?: previous?.buy?.takeIf { it > 0.0 } ?: price
            val sell = investingNumber(values.opt("ask"))?.takeIf { it > 0.0 }
                ?: previous?.sell?.takeIf { it > 0.0 } ?: price
            val sourceTime = investingSourceTimestamp(values) ?: receivedAtMillis

            MarketItem(
                id = descriptor.id,
                name = descriptor.name,
                code = descriptor.code,
                symbol = descriptor.symbol,
                price = price,
                change = change,
                changePercent = percent,
                high = high,
                low = low,
                buy = buy,
                sell = sell,
                history = if (previous?.price == price) previous?.history.orEmpty()
                    else MarketParsers.appendPoint(previous?.history.orEmpty(), sourceTime, price),
                sourceUpdatedAtMillis = sourceTime,
                receivedAtMillis = receivedAtMillis,
                origin = DataOrigin.NETWORK,
                isAvailable = true,
                source = MarketSource.TRADINGVIEW,
                category = descriptor.category,
                unit = descriptor.unit
            )
        }
    }

    private suspend fun resolveInvestingSymbol(descriptor: MarketDescriptor): String? {
        synchronized(investingSymbolCache) {
            investingSymbolCache[descriptor.sourceKey]?.let { return it }
        }

        directInvestingNameForSourceKey(descriptor.sourceKey)?.let { direct ->
            synchronized(investingSymbolCache) { investingSymbolCache[descriptor.sourceKey] = direct }
            return direct
        }

        val query = investingQueryFor(descriptor.sourceKey)
        val url = investingEndpoint("search") +
            "?query=" + encode(query) + "&limit=12&type=&exchange="
        val rows = runCatching { JSONArray(httpGetTradingView(url, 8_000)) }.getOrNull()
        val preferredExchange = descriptor.sourceKey.substringBefore(':', "").uppercase(Locale.US)
        val expected = normalizeInvestingToken(descriptor.sourceKey.substringAfterLast(':'))

        val best = if (rows != null) {
            (0 until rows.length()).mapNotNull(rows::optJSONObject)
                .maxByOrNull { row ->
                    val symbol = row.optString("symbol").trim()
                    val fullName = row.optString("full_name").trim()
                    val description = row.optString("description").trim()
                    val exchange = row.optString("exchange").trim().uppercase(Locale.US)
                    val type = row.optString("type").trim().lowercase(Locale.US)
                    val symbolToken = normalizeInvestingToken(symbol)
                    val fullToken = normalizeInvestingToken(fullName.substringAfterLast(':'))
                    val queryToken = normalizeInvestingToken(query)
                    var score = 0
                    if (symbolToken == expected) score += 160
                    if (fullToken == expected) score += 150
                    if (symbolToken == queryToken) score += 130
                    if (fullToken == queryToken) score += 120
                    if (description.contains(query, true)) score += 70
                    if (preferredExchange.isNotBlank() && exchange == preferredExchange) score += 35
                    if (expected in setOf("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY") &&
                        (type.contains("fx") || type.contains("currency"))) score += 40
                    if (expected in setOf("BTCUSD", "ETHUSD") && type.contains("crypto")) score += 40
                    if (expected == "UKOIL" && description.contains("brent", true)) score += 80
                    if (expected == "USOIL" &&
                        (description.contains("wti", true) || description.contains("crude oil", true))) score += 80
                    score
                }
        } else null

        val fullName = best?.optString("full_name")?.trim().orEmpty()
        val exchange = best?.optString("exchange")?.trim().orEmpty()
        val symbol = best?.optString("symbol")?.trim().orEmpty()
        val resolved = when {
            fullName.isNotBlank() -> fullName
            exchange.isNotBlank() && symbol.isNotBlank() -> "$exchange:$symbol"
            descriptor.sourceKey.isNotBlank() -> descriptor.sourceKey
            else -> return null
        }
        synchronized(investingSymbolCache) { investingSymbolCache[descriptor.sourceKey] = resolved }
        return resolved
    }

    private fun directInvestingNameForSourceKey(sourceKey: String): String? {
        val token = normalizeInvestingToken(sourceKey.substringAfterLast(':'))
        val direct = when (token) {
            "BTCUSD" -> ":BTC/USD"
            "ETHUSD" -> ":ETH/USD"
            "EURUSD" -> ":EUR/USD"
            "GBPUSD" -> ":GBP/USD"
            "USDJPY" -> ":USD/JPY"
            "XAUUSD" -> ":XAU/USD"
            "XAGUSD" -> ":XAG/USD"
            else -> null
        }
        if (direct != null) return direct

        val prefix = sourceKey.substringBefore(':', "").uppercase(Locale.US)
        return if (sourceKey.startsWith(":") ||
            (sourceKey.contains(':') && prefix !in setOf("BITSTAMP", "FX", "FX_IDC", "OANDA", "FOREXCOM", "TVC"))
        ) sourceKey else null
    }

    private fun investingQueryFor(sourceKey: String): String =
        when (normalizeInvestingToken(sourceKey.substringAfterLast(':'))) {
            "BTCUSD" -> "BTC/USD"
            "ETHUSD" -> "ETH/USD"
            "EURUSD" -> "EUR/USD"
            "GBPUSD" -> "GBP/USD"
            "USDJPY" -> "USD/JPY"
            "XAUUSD" -> "XAU/USD"
            "XAGUSD" -> "XAG/USD"
            "UKOIL" -> "Brent Oil"
            "USOIL" -> "Crude Oil WTI"
            else -> sourceKey.substringAfterLast(':')
        }

    private fun normalizeInvestingToken(value: String): String =
        value.uppercase(Locale.US).filter(Char::isLetterOrDigit)

    private fun investingEndpoint(name: String): String =
        "$INVESTING_TVC_BASE/${UUID.randomUUID().toString().replace("-", "")}/0/0/0/0/$name"

    private fun investingSourceTimestamp(value: JSONObject): Long? {
        val raw = sequenceOf(
            value.opt("lp_time"), value.opt("trade_time"), value.opt("rtc"), value.opt("timestamp")
        ).mapNotNull(::investingNumber).firstOrNull { it > 0.0 } ?: return null
        val millis = if (raw < 10_000_000_000L) (raw * 1000.0).toLong() else raw.toLong()
        return millis.takeIf { it in 946684800000L..4102444800000L }
    }

    private fun investingNumber(raw: Any?): Double? = when (raw) {
        null, JSONObject.NULL -> null
        is Number -> raw.toDouble()
        else -> raw.toString().replace(",", "").trim().toDoubleOrNull()
    }

'''
if not fetch_pattern.search(r):
    raise SystemExit("fetchTradingViewItems block not found")
r = fetch_pattern.sub(fetch_replacement, r, count=1)

http_get_pattern = re.compile(
    r"    private suspend fun httpGetTradingView\(url: String, timeoutMillis: Long\): String \{.*?\n    \}\n",
    re.S,
)
http_get_replacement = r'''    private suspend fun httpGetTradingView(url: String, timeoutMillis: Long): String {
        val request = Request.Builder()
            .url(url)
            .header("Accept", "application/json,text/plain,*/*")
            .header("Cache-Control", "no-cache")
            .header("Pragma", "no-cache")
            .header("Referer", "https://tvc-invdn-com.investing.com/")
            .header("User-Agent", HTTP_USER_AGENT)
            .build()
        return withContext(Dispatchers.IO) {
            val call = httpClient.newCall(request)
            call.timeout().timeout(timeoutMillis, TimeUnit.MILLISECONDS)
            call.execute().use { response ->
                if (!response.isSuccessful) throw IOException("HTTP " + response.code)
                response.body?.string()?.takeIf(String::isNotBlank)
                    ?: throw IOException("Empty response")
            }
        }
    }
'''
if not http_get_pattern.search(r):
    raise SystemExit("httpGetTradingView helper not found")
r = http_get_pattern.sub(http_get_replacement, r, count=1)

r = r.replace(
    "برای TradingView فعلاً تغییرات زنده همین اجرا نمایش داده می‌شود",
    "برای Investing.com فعلاً تغییرات زنده همین اجرا نمایش داده می‌شود"
)

companion_anchor = '        private const val TRADINGVIEW_SCANNER_BASE = "https://scanner.tradingview.com"\n'
if "private const val INVESTING_TVC_BASE" not in r:
    if companion_anchor not in r:
        raise SystemExit("TradingView constant anchor not found")
    r = r.replace(
        companion_anchor,
        '        private const val INVESTING_TVC_BASE = "https://tvc6.investing.com"\n' + companion_anchor,
        1
    )

repo.write_text(r)

# The live Investing client polls itself; restore a slower reconciliation loop.
vm = root / "MainViewModel.kt"
v = vm.read_text()
v = v.replace("const val LIVE_RECONCILE_INTERVAL_MS = 1_000L", "const val LIVE_RECONCILE_INTERVAL_MS = 30_000L")
v = v.replace(
    "// TradingView is considered LIVE only after the websocket client has\n                    // received an actual qsd quote, not merely after socket subscription.",
    "// Investing.com is considered LIVE only after a valid quote payload is received."
)
vm.write_text(v)

gradle = Path("source/app/build.gradle.kts")
g = gradle.read_text()
m = re.search(r"versionCode\s*=\s*(\d+)", g)
if m:
    next_code = max(int(m.group(1)), 15)
    g = re.sub(r"versionCode\s*=\s*\d+", f"versionCode = {next_code}", g, count=1)
g = re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "4.2-investing-live"', g, count=1)
gradle.write_text(g)


# ---------------- Compact percent + market status labels ----------------
ui = root / "MainActivity.kt"
u = ui.read_text()

card_start = u.find("@Composable\nprivate fun MarketCard(")
trend_start = u.find("private fun trendColor(", card_start + 1)
if card_start < 0 or trend_start <= card_start:
    raise SystemExit("MarketCard function range not found")

new_card = """@Composable
private fun MarketCard(
    item: MarketItem,
    gridMode: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Card(
        onClick = onClick,
        shape = RoundedCornerShape(if (gridMode) 28.dp else 24.dp),
        colors = CardDefaults.cardColors(containerColor = ChandCard),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        modifier = modifier
    ) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val compact = maxWidth < 185.dp
            val priceText = MarketFormatting.price(item)
            val priceFontSize = when {
                compact && priceText.length >= 16 -> 21.sp
                compact && priceText.length >= 13 -> 24.sp
                compact && priceText.length >= 10 -> 27.sp
                compact -> 31.sp
                priceText.length >= 18 -> 31.sp
                priceText.length >= 15 -> 35.sp
                else -> 42.sp
            }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(if (compact) 14.dp else 18.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.Top
                ) {
                    MarketBadge(item, Modifier.size(if (compact) 45.dp else 54.dp))
                    Spacer(Modifier.weight(1f))
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            text = item.name,
                            color = Color.White,
                            fontSize = if (compact) 16.sp else 20.sp,
                            lineHeight = if (compact) 19.sp else 23.sp,
                            fontWeight = FontWeight.Bold,
                            textAlign = TextAlign.End,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Spacer(Modifier.height(4.dp))
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(if (compact) 4.dp else 6.dp)
                        ) {
                            Text(
                                text = item.code,
                                color = ChandMuted,
                                fontSize = if (compact) 12.sp else 14.sp,
                                fontWeight = FontWeight.SemiBold,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                            MarketStatusLabel(item, compact)
                            Text(
                                text = compactPercent(item),
                                color = percentColor(item),
                                fontSize = if (compact) 9.sp else 10.sp,
                                lineHeight = if (compact) 10.sp else 11.sp,
                                fontWeight = FontWeight.SemiBold,
                                maxLines = 1
                            )
                        }
                    }
                }

                Spacer(Modifier.weight(1f))

                Text(
                    text = MarketFormatting.change(item),
                    color = trendColor(item),
                    fontSize = if (compact) 17.sp else 22.sp,
                    lineHeight = if (compact) 20.sp else 25.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1
                )
                Spacer(Modifier.height(if (compact) 2.dp else 5.dp))
                Text(
                    text = priceText,
                    color = if (item.isAvailable) Color.White else ChandMuted,
                    fontSize = priceFontSize,
                    lineHeight = priceFontSize * 1.08f,
                    fontWeight = FontWeight.Black,
                    letterSpacing = (-0.8).sp,
                    maxLines = 1,
                    softWrap = false,
                    overflow = TextOverflow.Clip
                )
            }
        }
    }
}

"""
u = u[:card_start] + new_card + u[trend_start:]

helper_anchor = """private fun trendColor(item: MarketItem): Color = when {
    !item.isAvailable || item.change == 0.0 -> ChandMuted
    item.change > 0.0 -> ChandUp
    else -> ChandDown
}

"""

helpers = r'''private fun percentColor(item: MarketItem): Color = when {
    !item.isAvailable || item.changePercent == 0.0 -> ChandMuted
    item.changePercent > 0.0 -> ChandUp
    else -> ChandDown
}

private fun compactPercent(item: MarketItem): String {
    val value = item.changePercent
    if (!value.isFinite()) return "0.00%"
    return java.lang.String.format(
        java.util.Locale.US,
        if (value > 0.0) "+%.2f%%" else "%.2f%%",
        value
    )
}

@Composable
private fun MarketStatusLabel(item: MarketItem, compact: Boolean) {
    if (isMarketLive(item)) {
        Surface(
            color = Color(0xFF173A2C),
            shape = RoundedCornerShape(5.dp)
        ) {
            Text(
                text = "LIVE",
                color = ChandUp,
                fontSize = if (compact) 7.sp else 8.sp,
                lineHeight = if (compact) 8.sp else 9.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.35.sp,
                modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp)
            )
        }
    } else {
        Text(
            text = "CLOSED",
            color = ChandMuted,
            fontSize = if (compact) 7.sp else 8.sp,
            lineHeight = if (compact) 8.sp else 9.sp,
            fontWeight = FontWeight.Medium,
            letterSpacing = 0.25.sp,
            maxLines = 1
        )
    }
}

private fun isMarketLive(item: MarketItem): Boolean {
    if (!item.isAvailable || item.sourceUpdatedAtMillis <= 0L) return false
    val age = (System.currentTimeMillis() - item.sourceUpdatedAtMillis).coerceAtLeast(0L)

    return when (item.source) {
        ir.personal.chand.data.MarketSource.TRADINGVIEW -> age <= 5L * 60L * 1000L
        ir.personal.chand.data.MarketSource.TSETMC -> age <= 30L * 60L * 1000L
        ir.personal.chand.data.MarketSource.TGJU -> age <= 20L * 60L * 1000L
    }
}

'''

if helper_anchor not in u:
    raise SystemExit("trendColor helper anchor not found")
u = u.replace(helper_anchor, helper_anchor + helpers, 1)
ui.write_text(u)

gradle = Path("source/app/build.gradle.kts")
g = gradle.read_text()
m = re.search(r"versionCode\s*=\s*(\d+)", g)
if m:
    next_code = max(int(m.group(1)), 16)
    g = re.sub(r"versionCode\s*=\s*\d+", f"versionCode = {next_code}", g, count=1)
g = re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "4.3-status-percent"', g, count=1)
gradle.write_text(g)


# ---------------- Adaptive list-card text fix ----------------
ui = root / "MainActivity.kt"
u = ui.read_text()

# List mode must not inherit the short wide-card aspect ratio. Give it enough
# vertical room for the header, status, change and full price text.
if "import androidx.compose.foundation.layout.heightIn\n" not in u:
    import_anchor = "import androidx.compose.foundation.layout.height\n"
    if import_anchor in u:
        u = u.replace(import_anchor, import_anchor + "import androidx.compose.foundation.layout.heightIn\n", 1)
    else:
        u = u.replace(
            "import androidx.compose.foundation.layout.fillMaxWidth\n",
            "import androidx.compose.foundation.layout.fillMaxWidth\nimport androidx.compose.foundation.layout.heightIn\n",
            1
        )

old_modifier = """.fillMaxWidth()
                    .aspectRatio(if (gridMode) 1.12f else 2.25f)
                    .pointerInput(item.id, gridMode) {"""
new_modifier = """.fillMaxWidth()
                    .then(
                        if (gridMode) Modifier.aspectRatio(1.12f)
                        else Modifier.heightIn(min = 205.dp)
                    )
                    .pointerInput(item.id, gridMode) {"""
if old_modifier not in u:
    raise SystemExit("MarketGrid aspect-ratio anchor not found")
u = u.replace(old_modifier, new_modifier, 1)

# Let long names wrap in list mode instead of truncating after one line.
old_name = """                            textAlign = TextAlign.End,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
"""
new_name = """                            textAlign = TextAlign.End,
                            maxLines = if (gridMode) 2 else 3,
                            overflow = TextOverflow.Ellipsis
"""
name_pos = u.find("text = item.name")
if name_pos < 0:
    raise SystemExit("item.name anchor not found")
tail = u[name_pos:]
if old_name not in tail:
    raise SystemExit("item.name maxLines anchor not found")
tail = tail.replace(old_name, new_name, 1)
u = u[:name_pos] + tail

ui.write_text(u)

gradle = Path("source/app/build.gradle.kts")
g = gradle.read_text()
m = re.search(r"versionCode\s*=\s*(\d+)", g)
if m:
    next_code = max(int(m.group(1)), 18)
    g = re.sub(r"versionCode\s*=\s*\d+", f"versionCode = {next_code}", g, count=1)
g = re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "4.5-price-safe-info-row"', g, count=1)
gradle.write_text(g)


# ---------------- v4.6 final adaptive layout fix ----------------
ui = root / "MainActivity.kt"
u = ui.read_text()

# Give list cards enough vertical room so long names, source/status and prices never overlap.
u = u.replace("else Modifier.heightIn(min = 205.dp)", "else Modifier.heightIn(min = 220.dp)")
u = u.replace("else Modifier.heightIn(min = 210.dp)", "else Modifier.heightIn(min = 220.dp)")

card_start = u.find("@Composable\nprivate fun MarketCard(")
trend_start = u.find("private fun trendColor(", card_start + 1)
if card_start < 0 or trend_start <= card_start:
    raise SystemExit("v4.6 MarketCard function range not found")

final_card = """@Composable
private fun MarketCard(
    item: MarketItem,
    gridMode: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Card(
        onClick = onClick,
        shape = RoundedCornerShape(if (gridMode) 28.dp else 24.dp),
        colors = CardDefaults.cardColors(containerColor = ChandCard),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        modifier = modifier
    ) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val compact = maxWidth < 185.dp
            val priceText = MarketFormatting.price(item)
            val changeText = MarketFormatting.change(item)
            val longName = item.name.length > if (compact) 11 else 16
            val nameFontSize = when {
                compact && longName -> 13.sp
                compact -> 15.sp
                longName -> 17.sp
                else -> 20.sp
            }
            val priceFontSize = when {
                compact && priceText.length >= 16 -> 19.sp
                compact && priceText.length >= 13 -> 22.sp
                compact && priceText.length >= 10 -> 25.sp
                compact -> 29.sp
                priceText.length >= 18 -> 29.sp
                priceText.length >= 15 -> 33.sp
                priceText.length >= 12 -> 36.sp
                else -> 40.sp
            }
            val changeFontSize = when {
                compact && changeText.length >= 9 -> 14.sp
                compact -> 16.sp
                changeText.length >= 11 -> 18.sp
                else -> 21.sp
            }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(if (compact) 13.dp else 17.dp),
                verticalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.Top
                ) {
                    MarketBadge(item, Modifier.size(if (compact) 43.dp else 52.dp))
                    Spacer(Modifier.width(if (compact) 9.dp else 12.dp))
                    Column(
                        modifier = Modifier.weight(1f),
                        horizontalAlignment = Alignment.End
                    ) {
                        Text(
                            text = item.name,
                            color = Color.White,
                            fontSize = nameFontSize,
                            lineHeight = if (compact) 16.sp else 20.sp,
                            fontWeight = FontWeight.Bold,
                            textAlign = TextAlign.End,
                            maxLines = if (gridMode) 2 else 3,
                            overflow = TextOverflow.Ellipsis
                        )
                        Spacer(Modifier.height(3.dp))
                        Text(
                            text = item.code,
                            color = ChandMuted,
                            fontSize = if (compact) 11.sp else 13.sp,
                            fontWeight = FontWeight.SemiBold,
                            textAlign = TextAlign.End,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Spacer(Modifier.height(4.dp))
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(if (compact) 4.dp else 6.dp)
                        ) {
                            MarketStatusLabel(item, compact)
                            Text(
                                text = compactPercent(item),
                                color = percentColor(item),
                                fontSize = if (compact) 8.sp else 10.sp,
                                lineHeight = if (compact) 9.sp else 11.sp,
                                fontWeight = FontWeight.SemiBold,
                                maxLines = 1
                            )
                        }
                    }
                }

                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = if (compact) 8.dp else 10.dp, bottom = 1.dp)
                ) {
                    Text(
                        text = changeText,
                        color = trendColor(item),
                        fontSize = changeFontSize,
                        lineHeight = if (compact) 17.sp else 22.sp,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                        softWrap = false,
                        overflow = TextOverflow.Clip
                    )
                    Spacer(Modifier.height(if (compact) 4.dp else 6.dp))
                    Text(
                        text = priceText,
                        color = if (item.isAvailable) Color.White else ChandMuted,
                        fontSize = priceFontSize,
                        lineHeight = priceFontSize * 1.08f,
                        fontWeight = FontWeight.Black,
                        letterSpacing = (-0.55).sp,
                        maxLines = 1,
                        softWrap = false,
                        overflow = TextOverflow.Clip
                    )
                }
            }
        }
    }
}

"""
u = u[:card_start] + final_card + u[trend_start:]
ui.write_text(u)

gradle = Path("source/app/build.gradle.kts")
g = gradle.read_text()
m = re.search(r"versionCode\s*=\s*(\d+)", g)
if m:
    next_code = max(int(m.group(1)), 19)
    g = re.sub(r"versionCode\s*=\s*\d+", f"versionCode = {next_code}", g, count=1)
g = re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "4.6-layout-fix"', g, count=1)
gradle.write_text(g)


# ---------------- v4.8 final safe-card fix ----------------
# Keep the stable v4.6 card composition. Do not translate the price block upward:
# that was the regression which clipped the bottom of large prices.
ui = root / "MainActivity.kt"
u = ui.read_text()

# Slightly taller grid cards preserve the iOS-like proportions while giving
# large Persian/Latin price glyphs enough vertical room.
u = u.replace("Modifier.aspectRatio(1.12f)", "Modifier.aspectRatio(1.04f)", 1)

# Keep list cards at the already-safe v4.6 height.
u = u.replace("else Modifier.heightIn(min = 205.dp)", "else Modifier.heightIn(min = 220.dp)", 1)
u = u.replace("else Modifier.heightIn(min = 210.dp)", "else Modifier.heightIn(min = 220.dp)", 1)

# Add a small bottom safe area; do not use Modifier.offset here.
old = """.padding(top = if (compact) 8.dp else 10.dp, bottom = 1.dp)"""
new = """.padding(
                            top = if (compact) 8.dp else 10.dp,
                            bottom = if (compact) 6.dp else 8.dp
                        )"""
if old not in u:
    raise SystemExit("v4.8 bottom padding anchor not found")
u = u.replace(old, new, 1)

# Relax line height a little so heavy price glyphs are not cropped by their text box.
u = u.replace(
    "lineHeight = priceFontSize * 1.08f,",
    "lineHeight = priceFontSize * 1.14f,",
    1
)

ui.write_text(u)

gradle = Path("source/app/build.gradle.kts")
g = gradle.read_text()
m = re.search(r"versionCode\s*=\s*(\d+)", g)
if m:
    next_code = max(int(m.group(1)) + 1, 20)
    g = re.sub(r"versionCode\s*=\s*\d+", f"versionCode = {next_code}", g, count=1)
g = re.sub(
    r'versionName\s*=\s*"[^"]+"',
    'versionName = "4.8-final-safe-cards"',
    g,
    count=1
)
gradle.write_text(g)

# ---------------- v4.8.4 one-line names + card symbol logos ----------------
# LOCKED BASELINE: exact v4.8. Only card title overflow and card badge artwork
# are changed. Prices, live feeds, status logic, layout dimensions, formatting,
# settings, catalog behavior and all other screens stay untouched.

ui = root / "MainActivity.kt"
u = ui.read_text()

# 1) Never let a long instrument name consume a second row in a market card.
# Ellipsis keeps the bottom price block at the exact v4.8 vertical position.
old_title_lines = """                            maxLines = if (gridMode) 2 else 3,
                            overflow = TextOverflow.Ellipsis
"""
new_title_lines = """                            maxLines = 1,
                            softWrap = false,
                            overflow = TextOverflow.Ellipsis
"""
if old_title_lines not in u:
    raise SystemExit("v4.8.4 card title anchor not found")
u = u.replace(old_title_lines, new_title_lines, 1)

# 2) Only the badge used inside MarketCard changes. Other MarketBadge usages
# (details/chart/etc.) remain exactly as v4.8.
old_card_badge = """                    MarketBadge(item, Modifier.size(if (compact) 43.dp else 52.dp))"""
new_card_badge = """                    MarketCardBadge(item, Modifier.size(if (compact) 43.dp else 52.dp))"""
if old_card_badge not in u:
    raise SystemExit("v4.8.4 card badge anchor not found")
u = u.replace(old_card_badge, new_card_badge, 1)

# Imports required by the card-only async logo loader. No external image library
# is introduced; Android BitmapFactory + the existing coroutines stack are used.
imports = [
    (
        "import android.os.Bundle\n",
        "import android.os.Bundle\nimport android.graphics.Bitmap\nimport android.graphics.BitmapFactory\n"
    ),
    (
        "import androidx.compose.foundation.Canvas\n",
        "import androidx.compose.foundation.Canvas\nimport androidx.compose.foundation.Image\n"
    ),
    (
        "import androidx.compose.ui.graphics.Color\n",
        "import androidx.compose.ui.graphics.Color\nimport androidx.compose.ui.graphics.asImageBitmap\n"
    ),
    (
        "import androidx.compose.ui.text.font.FontWeight\n",
        "import androidx.compose.ui.text.font.FontWeight\nimport androidx.compose.ui.layout.ContentScale\n"
    ),
]
for anchor, replacement in imports:
    if replacement.splitlines()[-1] not in u and anchor in u:
        u = u.replace(anchor, replacement, 1)

badge_anchor = """@Composable
private fun MarketBadge(item: MarketItem, modifier: Modifier = Modifier) {
"""

card_logo_code = r'''@Composable
private fun MarketCardBadge(item: MarketItem, modifier: Modifier = Modifier) {
    // Existing bespoke Chand icons for currencies, metals, crypto and global
    // instruments are already symbol-specific. Replace only the generic TSETMC
    // stock/fund badge with a real issuer/fund icon when one can be resolved.
    if (item.source != ir.personal.chand.data.MarketSource.TSETMC) {
        MarketBadge(item, modifier)
        return
    }

    val logoState = androidx.compose.runtime.produceState<Bitmap?>(
        initialValue = null,
        key1 = item.id,
        key2 = item.code
    ) {
        value = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
            TsetmcCardLogoResolver.load(item)
        }
    }

    val logo = logoState.value
    if (logo != null) {
        Surface(
            modifier = modifier,
            shape = CircleShape,
            color = Color(0xFF25262A),
            border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF555862))
        ) {
            Image(
                bitmap = logo.asImageBitmap(),
                contentDescription = item.name,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(3.dp),
                contentScale = ContentScale.Fit
            )
        }
    } else {
        // Symbol-specific fallback: never show the old generic stock/category
        // artwork on a market card when no remote issuer icon is available.
        val badgeText = item.code
            .trim()
            .ifBlank { item.name.trim() }
            .take(3)

        Surface(
            modifier = modifier,
            shape = CircleShape,
            color = Color(0xFF25262A),
            border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF5B5E66))
        ) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = badgeText,
                    color = Color(0xFFE7E8EA),
                    fontSize = when (badgeText.length) {
                        0, 1 -> 15.sp
                        2 -> 12.sp
                        else -> 10.sp
                    },
                    lineHeight = 13.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1
                )
            }
        }
    }
}

private object TsetmcCardLogoResolver {
    private val bitmapCache = java.util.concurrent.ConcurrentHashMap<String, Bitmap>()
    private val failed = java.util.concurrent.ConcurrentHashMap.newKeySet<String>()

    // A few high-confidence issuer domains make common symbols instant; every
    // other TSETMC symbol is resolved dynamically from Fund/Codal metadata.
    private val knownDomains = mapOf(
        "وپارس" to "parsian-bank.ir",
        "عیار" to "emofid.com",
        "وبملت" to "bankmellat.ir",
        "وتجارت" to "tejaratbank.ir",
        "وبصادر" to "bsi.ir",
        "وپاسار" to "bpi.ir",
        "فولاد" to "msc.ir",
        "فملی" to "nicico.com",
        "خودرو" to "ikco.ir",
        "خساپا" to "saipacorp.com"
    )

    fun load(item: MarketItem): Bitmap? {
        val key = item.id.ifBlank { item.code }
        bitmapCache[key]?.let { return it }
        if (key in failed) return null

        val domain = knownDomains[item.code.trim()]
            ?: resolveDomain(item)

        if (domain.isNullOrBlank()) {
            failed += key
            return null
        }

        val bitmap = loadDomainIcon(domain)
        if (bitmap != null) {
            bitmapCache[key] = bitmap
            return bitmap
        }

        failed += key
        return null
    }

    private fun resolveDomain(item: MarketItem): String? {
        val candidates = LinkedHashSet<String>()
        val code = item.code.trim()
        val insCode = item.id.substringAfter("tsetmc:", "")
            .takeIf { it.isNotBlank() && it.all(Char::isDigit) }

        // Funds/ETFs often expose their own web address here.
        if (insCode != null) {
            collectRemoteUrls(
                "https://cdn.tsetmc.com/api/Fund/GetETFByInsCode/$insCode",
                candidates
            )
        }

        // Companies and fund managers usually expose a publisher website in
        // Codal metadata. The parser intentionally scans the JSON recursively
        // so it remains compatible if the exact website field name changes.
        if (code.isNotBlank()) {
            val encoded = java.net.URLEncoder.encode(
                code,
                java.nio.charset.StandardCharsets.UTF_8.toString()
            )
            collectRemoteUrls(
                "https://cdn.tsetmc.com/api/Codal/GetCodalPublisherBySymbol/$encoded",
                candidates
            )
        }

        return candidates
            .asSequence()
            .mapNotNull(::domainFromCandidate)
            .firstOrNull { domain ->
                val d = domain.lowercase()
                d !in setOf(
                    "tsetmc.com",
                    "cdn.tsetmc.com",
                    "codal.ir",
                    "www.codal.ir",
                    "seo.ir",
                    "gmail.com",
                    "yahoo.com"
                ) &&
                    !d.endsWith(".tsetmc.com") &&
                    !d.endsWith(".codal.ir")
            }
    }

    private fun collectRemoteUrls(
        url: String,
        output: MutableSet<String>
    ) {
        val text = runCatching { httpText(url) }.getOrNull() ?: return
        val root = runCatching { org.json.JSONTokener(text).nextValue() }.getOrNull()
            ?: return
        collectStrings(root, output)
    }

    private fun collectStrings(
        value: Any?,
        output: MutableSet<String>
    ) {
        when (value) {
            is org.json.JSONObject -> {
                val keys = value.keys()
                while (keys.hasNext()) {
                    val key = keys.next()
                    collectStrings(value.opt(key), output)
                }
            }
            is org.json.JSONArray -> {
                for (index in 0 until value.length()) {
                    collectStrings(value.opt(index), output)
                }
            }
            is String -> {
                val raw = value.trim()
                if (raw.isBlank()) return

                val urlRegex = Regex(
                    """(?i)(?:https?://|www\.)[^\s"'<>]+"""
                )
                urlRegex.findAll(raw).forEach { output += it.value }

                // Also accept plain domains that commonly appear in publisher
                // fields such as Website without a scheme.
                val domainRegex = Regex(
                    """(?i)\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:ir|com|org|net|co)\b"""
                )
                domainRegex.findAll(raw).forEach { output += it.value }
            }
        }
    }

    private fun domainFromCandidate(candidate: String): String? {
        var value = candidate.trim()
            .trimEnd('.', ',', ';', '/', ')', ']', '}')
        if (value.isBlank()) return null

        if (!value.startsWith("http://", true) &&
            !value.startsWith("https://", true)
        ) {
            value = "https://" + value.removePrefix("www.")
        }

        return runCatching {
            java.net.URI(value).host
                ?.lowercase()
                ?.removePrefix("www.")
        }.getOrNull()?.takeIf { '.' in it }
    }

    private fun loadDomainIcon(domain: String): Bitmap? {
        // Prefer the site's own favicon first.
        val directCandidates = listOf(
            "https://$domain/favicon.ico",
            "https://www.$domain/favicon.ico"
        )
        for (url in directCandidates) {
            loadBitmap(url)?.let { return it }
        }

        // Google's favicon endpoint is a resilient fallback for issuer sites
        // whose icon lives at a non-standard path.
        val googleUrl =
            "https://www.google.com/s2/favicons?domain=$domain&sz=128"
        return loadBitmap(googleUrl)
    }

    private fun httpText(url: String): String {
        val connection = (java.net.URL(url).openConnection()
            as java.net.HttpURLConnection).apply {
            connectTimeout = 4_000
            readTimeout = 4_000
            instanceFollowRedirects = true
            setRequestProperty(
                "User-Agent",
                "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36"
            )
            setRequestProperty("Accept", "application/json,text/plain,*/*")
        }
        return try {
            connection.inputStream.bufferedReader().use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }

    private fun loadBitmap(url: String): Bitmap? {
        val connection = runCatching {
            (java.net.URL(url).openConnection()
                as java.net.HttpURLConnection).apply {
                connectTimeout = 4_000
                readTimeout = 4_000
                instanceFollowRedirects = true
                setRequestProperty(
                    "User-Agent",
                    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36"
                )
                setRequestProperty("Accept", "image/*,*/*;q=0.8")
            }
        }.getOrNull() ?: return null

        return try {
            if (connection.responseCode !in 200..299) return null
            connection.inputStream.use { BitmapFactory.decodeStream(it) }
        } catch (_: Throwable) {
            null
        } finally {
            connection.disconnect()
        }
    }
}

'''

if badge_anchor not in u:
    raise SystemExit("v4.8.4 MarketBadge insertion anchor not found")
u = u.replace(badge_anchor, card_logo_code + badge_anchor, 1)

ui.write_text(u)

# Patch build identity only. High versionCode allows installation over the user's
# later test builds without uninstalling; product behavior still equals v4.8.
gradle = Path("source/app/build.gradle.kts")
g = gradle.read_text()
g = re.sub(r"versionCode\s*=\s*\d+", "versionCode = 28", g, count=1)
g = re.sub(
    r'versionName\s*=\s*"[^"]+"',
    'versionName = "4.8.4-one-line-symbol-logos"',
    g,
    count=1
)
gradle.write_text(g)


# ---------------- v4.8.4 single-line names + symbol logos ----------------
# UI-only patch on the v4.8 line:
# 1) Market names stay on one line and ellipsize.
# 2) Card badges resolve a real symbol/company logo when available.
# All pricing, live feeds, layout dimensions and other behavior remain unchanged.

ui = root / "MainActivity.kt"
u = ui.read_text()

# Add imports for async logo loading/resolution.
import_pairs = [
    (
        "import androidx.compose.ui.text.style.TextOverflow\n",
        "import androidx.compose.ui.text.style.TextOverflow\nimport androidx.compose.ui.draw.clip\nimport androidx.compose.ui.layout.ContentScale\n"
    ),
    (
        "import androidx.compose.runtime.remember\n",
        "import androidx.compose.runtime.remember\nimport androidx.compose.runtime.produceState\n"
    ),
]
for anchor, replacement in import_pairs:
    if replacement.splitlines()[-1] not in u and anchor in u:
        u = u.replace(anchor, replacement, 1)

extra_imports = """import coil.compose.SubcomposeAsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URLEncoder
import java.net.URL
import java.nio.charset.StandardCharsets
import java.util.concurrent.ConcurrentHashMap
"""
if "import coil.compose.SubcomposeAsyncImage" not in u:
    package_end = u.find("\n\n", u.find("package "))
    # Insert after the existing import block's first import to preserve package placement.
    first_import = u.find("import ", package_end)
    if first_import < 0:
        raise SystemExit("v4.8.4 import block not found")
    u = u[:first_import] + extra_imports + u[first_import:]

# Locate only the MarketCard function so detail screens remain untouched.
card_start = u.find("@Composable\nprivate fun MarketCard(")
trend_start = u.find("private fun trendColor(", card_start + 1)
if card_start < 0 or trend_start <= card_start:
    raise SystemExit("v4.8.4 MarketCard range not found")
card = u[card_start:trend_start]

# Keep every card title to one line. Long names end with ellipsis instead of
# pushing code/status/price downward.
card = card.replace(
    "maxLines = if (gridMode) 2 else 3,\n                            overflow = TextOverflow.Ellipsis",
    "maxLines = 1,\n                            softWrap = false,\n                            overflow = TextOverflow.Ellipsis",
    1
)

# Also catch the exact v4.8 card variant if it used a fixed 2-line title.
name_anchor = "text = item.name,"
name_pos = card.find(name_anchor)
if name_pos < 0:
    raise SystemExit("v4.8.4 item.name not found")
name_tail = card[name_pos:]
if "maxLines = 1," not in name_tail[:900]:
    name_tail = name_tail.replace(
        "maxLines = 2,\n                            overflow = TextOverflow.Ellipsis",
        "maxLines = 1,\n                            softWrap = false,\n                            overflow = TextOverflow.Ellipsis",
        1
    )
    card = card[:name_pos] + name_tail

# Keep the card geometry untouched; only the one-line title behavior changes here.
u = u[:card_start] + card + u[trend_start:]

# Upgrade the existing MarketBadge renderer itself so every card gets its
# per-symbol logo regardless of the exact v4.8 call-site formatting.
badge_fn = "@Composable\nprivate fun MarketBadge("
badge_pos = u.find(badge_fn)
if badge_pos < 0:
    raise SystemExit("v4.8.4 MarketBadge function not found")

# Preserve the original hand-drawn badge as a fallback.
u = u[:badge_pos] + u[badge_pos:].replace(
    "@Composable\nprivate fun MarketBadge(",
    "@Composable\nprivate fun LegacyMarketBadge(",
    1
)
badge_pos = u.find("@Composable\nprivate fun LegacyMarketBadge(")

logo_helpers = r'''
private val SymbolLogoUrlCache = ConcurrentHashMap<String, String>()

@Composable
private fun MarketBadge(
    item: MarketItem,
    modifier: Modifier = Modifier
) {
    val cacheKey = item.source.name + "|" + item.code.trim() + "|" + item.name.trim()
    val logoUrlState = produceState<String?>(
        initialValue = SymbolLogoUrlCache[cacheKey]?.takeIf(String::isNotBlank),
        key1 = cacheKey
    ) {
        val resolved = SymbolLogoUrlCache[cacheKey]?.takeIf(String::isNotBlank)
            ?: withContext(Dispatchers.IO) {
                runCatching { resolveMarketLogoUrl(item) }.getOrNull()
            }
        if (!resolved.isNullOrBlank()) {
            SymbolLogoUrlCache[cacheKey] = resolved
        } else {
            SymbolLogoUrlCache.putIfAbsent(cacheKey, "")
        }
        value = resolved
    }

    val logoUrl = logoUrlState.value
    if (logoUrl.isNullOrBlank()) {
        SymbolSpecificFallbackBadge(item, modifier)
        return
    }

    SubcomposeAsyncImage(
        model = logoUrl,
        contentDescription = item.name,
        contentScale = ContentScale.Fit,
        modifier = modifier,
        loading = {
            SymbolSpecificFallbackBadge(item, Modifier.fillMaxSize())
        },
        error = {
            SymbolSpecificFallbackBadge(item, Modifier.fillMaxSize())
        }
    )
}

@Composable
private fun SymbolSpecificFallbackBadge(
    item: MarketItem,
    modifier: Modifier = Modifier
) {
    // Keep the polished built-in asset icons for FX/metals/energy/crypto.
    // Iranian equities/funds and unknown global tickers get their own symbol,
    // never the same generic category badge.
    val code = item.code.trim()
    val upper = code.uppercase(java.util.Locale.US)
    val knownAsset = item.source == ir.personal.chand.data.MarketSource.TGJU ||
        upper in setOf(
            "USD", "EUR", "USDT", "GRAM", "EMAMI", "XAU/USD", "XAUUSD",
            "BRENT", "UKOIL", "XAG/USD", "XAGUSD", "BTC", "BTCUSD", "ETH", "ETHUSD"
        )

    if (knownAsset) {
        LegacyMarketBadge(item, modifier)
        return
    }

    Surface(
        modifier = modifier,
        shape = CircleShape,
        color = Color(0xFF25272C),
        border = androidx.compose.foundation.BorderStroke(1.2.dp, Color(0xFF555A64))
    ) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            val label = when {
                code.isNotBlank() -> code.take(3)
                item.name.isNotBlank() -> item.name.take(2)
                else -> "•"
            }
            Text(
                text = label,
                color = Color(0xFFE7E8EB),
                fontWeight = FontWeight.Bold,
                fontSize = when {
                    label.length <= 2 -> 12.sp
                    else -> 9.sp
                },
                maxLines = 1,
                overflow = TextOverflow.Clip
            )
        }
    }
}

private fun resolveMarketLogoUrl(item: MarketItem): String? {
    return when (item.source) {
        ir.personal.chand.data.MarketSource.TSETMC -> resolveIranianSymbolLogo(item)
        ir.personal.chand.data.MarketSource.TRADINGVIEW -> resolveGlobalSymbolLogo(item)
        ir.personal.chand.data.MarketSource.TGJU -> resolveKnownAssetLogo(item)
    }
}

private fun resolveKnownAssetLogo(item: MarketItem): String? {
    val code = item.code.trim().uppercase(java.util.Locale.US)
    return when (code) {
        "USDT" -> "https://cryptologos.cc/logos/tether-usdt-logo.png"
        "BTC", "BTCUSD", "BTC/USD" -> "https://cryptologos.cc/logos/bitcoin-btc-logo.png"
        "ETH", "ETHUSD", "ETH/USD" -> "https://cryptologos.cc/logos/ethereum-eth-logo.png"
        else -> null
    }
}

private fun resolveGlobalSymbolLogo(item: MarketItem): String? {
    val rawCode = item.code.trim()
    if (rawCode.isBlank()) return null

    // TradingView symbol search exposes a logoid for most listed securities,
    // currencies and crypto assets. Coil's SVG module renders these directly.
    val query = rawCode
        .replace("/", "")
        .replace(" ", "")
        .ifBlank { item.name.trim() }

    val url = "https://symbol-search.tradingview.com/symbol_search/?" +
        "text=" + encodeUrl(query) +
        "&hl=1&exchange=&lang=en&search_type=undefined&domain=production"

    val body = httpText(url)
    val rows = parseTradingViewRows(body)

    val normalizedWanted = normalizeTicker(rawCode)
    val best = (0 until rows.length())
        .mapNotNull(rows::optJSONObject)
        .maxByOrNull { row ->
            val symbol = normalizeTicker(row.optString("symbol"))
            val desc = row.optString("description")
            var score = 0
            if (symbol == normalizedWanted) score += 120
            if (symbol.endsWith(normalizedWanted) || normalizedWanted.endsWith(symbol)) score += 40
            if (desc.contains(item.name, ignoreCase = true)) score += 20
            if (row.optString("logoid").isNotBlank()) score += 10
            score
        } ?: return financialModelingPrepLogo(rawCode)

    val logoId = sequenceOf(
        best.optString("logoid"),
        best.optString("base_currency_logoid"),
        best.optString("base-currency-logoid"),
        best.optString("currency_logoid"),
        best.optString("currency-logoid")
    ).firstOrNull { it.isNotBlank() }

    return if (!logoId.isNullOrBlank()) {
        "https://s3-symbol-logo.tradingview.com/" + logoId.trim() + "--big.svg"
    } else {
        financialModelingPrepLogo(best.optString("symbol").ifBlank { rawCode })
    }
}

private fun financialModelingPrepLogo(code: String): String? {
    val ticker = code.substringAfterLast(':')
        .replace("/", "")
        .replace("-", "")
        .trim()
        .uppercase(java.util.Locale.US)
    if (ticker.isBlank()) return null
    return "https://financialmodelingprep.com/image-stock/" + encodeUrl(ticker) + ".png"
}

private fun resolveIranianSymbolLogo(item: MarketItem): String? {
    val symbol = item.code.trim().ifBlank { item.name.trim() }
    if (symbol.isBlank()) return null

    // TSETMC's Codal publisher record usually includes the issuer website.
    // Using that website's favicon/brandmark gives every company/fund its own
    // identity while remaining fully dynamic for newly-added Iranian symbols.
    val publisherUrl =
        "https://cdn.tsetmc.com/api/Codal/GetCodalPublisherBySymbol/" + encodeUrl(symbol)

    val body = httpText(publisherUrl)
    val root = JSONObject(body)
    val publisher = root.optJSONObject("codalPublisher") ?: root
    val website = findWebsiteRecursively(publisher) ?: return null

    val clean = website
        .trim()
        .removePrefix("http://")
        .removePrefix("https://")
        .substringBefore('/')
        .removePrefix("www.")
        .trim()

    if (clean.isBlank() || !clean.contains('.')) return null

    return "https://www.google.com/s2/favicons?sz=128&domain_url=https://" + encodeUrl(clean)
}

private fun findWebsiteRecursively(value: Any?): String? {
    when (value) {
        is JSONObject -> {
            val keys = value.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                val raw = value.opt(key)
                val lowered = key.lowercase(java.util.Locale.US)
                if (raw is String &&
                    (lowered.contains("web") ||
                     lowered.contains("site") ||
                     lowered.contains("url") ||
                     lowered.contains("domain"))
                ) {
                    val candidate = raw.trim()
                    if (candidate.startsWith("http://") ||
                        candidate.startsWith("https://") ||
                        (candidate.contains('.') && !candidate.contains(' '))
                    ) {
                        return candidate
                    }
                }
            }
            val nestedKeys = value.keys()
            while (nestedKeys.hasNext()) {
                val nested = findWebsiteRecursively(value.opt(nestedKeys.next()))
                if (!nested.isNullOrBlank()) return nested
            }
        }
        is JSONArray -> {
            for (i in 0 until value.length()) {
                val nested = findWebsiteRecursively(value.opt(i))
                if (!nested.isNullOrBlank()) return nested
            }
        }
    }
    return null
}

private fun parseTradingViewRows(body: String): JSONArray {
    val trimmed = body.trim()
    if (trimmed.startsWith("[")) return JSONArray(trimmed)
    val root = JSONObject(trimmed)
    return root.optJSONArray("symbols")
        ?: root.optJSONArray("data")
        ?: root.optJSONArray("items")
        ?: JSONArray()
}

private fun normalizeTicker(value: String): String =
    value.uppercase(java.util.Locale.US)
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
        .substringAfterLast(':')

private fun encodeUrl(value: String): String =
    URLEncoder.encode(value, StandardCharsets.UTF_8.name())

private fun httpText(url: String): String {
    val connection = (URL(url).openConnection() as HttpURLConnection).apply {
        connectTimeout = 5_000
        readTimeout = 5_000
        instanceFollowRedirects = true
        setRequestProperty("Accept", "application/json,text/plain,*/*")
        setRequestProperty(
            "User-Agent",
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36"
        )
    }
    return try {
        connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
    } finally {
        connection.disconnect()
    }
}

'''
u = u[:badge_pos] + logo_helpers + u[badge_pos:]
ui.write_text(u)

# Add Coil image/SVG support without changing any other dependencies.
gradle = Path("source/app/build.gradle.kts")
g = gradle.read_text()
if 'io.coil-kt:coil-compose' not in g:
    dep_anchor = "dependencies {"
    if dep_anchor not in g:
        raise SystemExit("v4.8.4 dependencies block not found")
    g = g.replace(
        dep_anchor,
        dep_anchor + '''
    implementation("io.coil-kt:coil-compose:2.7.0")
    implementation("io.coil-kt:coil-svg:2.7.0")''',
        1
    )

g = re.sub(r"versionCode\s*=\s*\d+", "versionCode = 27", g, count=1)
g = re.sub(
    r'versionName\s*=\s*"[^"]+"',
    'versionName = "4.8.4-symbol-logos-single-line"',
    g,
    count=1
)
gradle.write_text(g)


# ---------------- LOCKED UI-ONLY POLISH ----------------
# Base is EXACTLY the last verified real-logo build (839c7f2).
# Only:
#   1) clip the already-resolved REAL logo into the existing circular badge bounds
#   2) make the market name one step larger
# Everything else stays byte-for-byte from that verified patch.

ui = root / "MainActivity.kt"
locked = ui.read_text()

# 1) Real logo source/resolution remains untouched; only its visual mask changes.
needle = """    SubcomposeAsyncImage(
        model = logoUrl,
        contentDescription = item.name,
        contentScale = ContentScale.Fit,
        modifier = modifier,
"""
replacement = """    SubcomposeAsyncImage(
        model = logoUrl,
        contentDescription = item.name,
        contentScale = ContentScale.Fit,
        modifier = modifier.clip(CircleShape),
"""
if needle not in locked:
    raise SystemExit("locked polish: real-logo renderer anchor not found")
locked = locked.replace(needle, replacement, 1)

# 2) Scope typography change ONLY to the primary card title.
card_start = locked.find("@Composable\nprivate fun MarketCard(")
trend_start = locked.find("private fun trendColor(", card_start + 1)
if card_start < 0 or trend_start <= card_start:
    raise SystemExit("locked polish: MarketCard range not found")
card = locked[card_start:trend_start]
name_pos = card.find("text = item.name,")
if name_pos < 0:
    raise SystemExit("locked polish: item.name not found")
head = card[:name_pos]
tail = card[name_pos:]
tail = tail.replace(
    "fontSize = if (compact) 16.sp else 20.sp",
    "fontSize = if (compact) 17.sp else 21.sp",
    1
)
tail = tail.replace(
    "lineHeight = if (compact) 19.sp else 23.sp",
    "lineHeight = if (compact) 20.sp else 24.sp",
    1
)
locked = locked[:card_start] + head + tail + locked[trend_start:]
# Required only for the circular visual mask; no behavior change.
if "import androidx.compose.ui.draw.clip\n" not in locked:
    import_anchor = "import androidx.compose.ui.Modifier\n"
    if import_anchor not in locked:
        raise SystemExit("locked polish: Modifier import anchor not found")
    locked = locked.replace(
        import_anchor,
        import_anchor + "import androidx.compose.ui.draw.clip\n",
        1
    )

ui.write_text(locked)

# Installation-only bump so it can install over the previous test APK.
gradle = Path("source/app/build.gradle.kts")
g = gradle.read_text()
g = re.sub(r"versionCode\s*=\s*\d+", "versionCode = 30", g, count=1)
gradle.write_text(g)


# ---------------- symbol catalog updater in Settings ----------------
# LOCKED CHANGE: adds only a Settings catalog-refresh workflow.
# Existing prices, live feeds, cards, logos, ordering, sizing and provider behavior stay untouched.

# 1) Repository: strict Iran-stock refresh + broad global-symbol discovery.
repo_file = root / "data/MarketRepository.kt"
rr = repo_file.read_text()

if "suspend fun refreshIranStockCatalogStrict()" not in rr:
    anchor = "    private suspend fun loadTsetmcCatalog(force: Boolean = false): List<MarketDescriptor> = stockCatalogMutex.withLock {\n"
    if anchor not in rr:
        raise SystemExit("symbol updater: TSETMC catalog anchor not found")
    methods = r'''    suspend fun refreshIranStockCatalogStrict(): List<MarketDescriptor> = withContext(Dispatchers.IO) {
        var lastFailure: Throwable? = null

        val cdnQuotes = runCatching {
            TsetmcProtocol.parseCdnMarketWatch(httpGet(TSETMC_MARKET_WATCH, 15_000))
        }.onFailure { lastFailure = it }.getOrNull().orEmpty()

        val quotes = if (cdnQuotes.isNotEmpty()) {
            cdnQuotes
        } else {
            runCatching {
                TsetmcProtocol.parseLegacyInit(httpGet(TSETMC_LEGACY_INIT, 15_000)).quotes
            }.onFailure { lastFailure = it }.getOrNull().orEmpty()
        }

        if (quotes.isEmpty()) {
            throw IllegalStateException(
                "TSETMC پاسخ معتبر برای فهرست نمادها نداد",
                lastFailure
            )
        }

        val descriptors = quotes
            .mapNotNull(::descriptorFromTsetmcQuote)
            .distinctBy(MarketDescriptor::id)
            .sortedWith(compareBy<MarketDescriptor> { it.code }.thenBy { it.name })

        if (descriptors.isEmpty()) {
            throw IllegalStateException("فهرست بورس ایران خالی دریافت شد")
        }

        stockCatalogMutex.withLock {
            stockCatalogCache = descriptors
            stockCatalogLoadedAt = System.currentTimeMillis()
        }
        synchronized(knownDescriptors) {
            descriptors.forEach { knownDescriptors[it.id] = it }
        }
        descriptors
    }

    suspend fun discoverGlobalCatalog(
        onProgress: (Int) -> Unit = {}
    ): List<MarketDescriptor> = withContext(Dispatchers.IO) {
        val seeds = (
            ('A'..'Z').map { it.toString() } +
            ('0'..'9').map { it.toString() } +
            listOf("USD", "EUR", "JPY", "BTC", "ETH", "XAU", "XAG", "OIL", "INDEX")
        ).distinct()

        val found = linkedMapOf<String, MarketDescriptor>()
        TRADINGVIEW_MARKET_DESCRIPTORS.forEach { found[it.id] = it }

        var successfulRequests = 0
        var lastFailure: Throwable? = null

        seeds.forEachIndexed { index, seed ->
            val result = runCatching { searchTradingViewCatalog(seed) }
            result.onSuccess { items ->
                successfulRequests += 1
                items
                    .filter { it.source == MarketSource.TRADINGVIEW }
                    .forEach { found[it.id] = it }
            }.onFailure {
                lastFailure = it
            }
            onProgress((((index + 1) * 100.0) / seeds.size).toInt().coerceIn(0, 100))
        }

        if (successfulRequests == 0) {
            throw IllegalStateException(
                "منبع بازار جهانی پاسخ نداد",
                lastFailure
            )
        }

        val items = found.values
            .distinctBy(MarketDescriptor::id)
            .sortedWith(compareBy<MarketDescriptor> { it.code }.thenBy { it.name })

        if (items.isEmpty()) {
            throw IllegalStateException("فهرست بازار جهانی خالی دریافت شد")
        }

        synchronized(knownDescriptors) {
            items.forEach { knownDescriptors[it.id] = it }
        }
        items
    }

'''
    rr = rr.replace(anchor, methods + anchor, 1)
    repo_file.write_text(rr)

# 2) ViewModel state + persistence + update action.
vm_file = root / "MainViewModel.kt"
vv = vm_file.read_text()

if "import org.json.JSONArray" not in vv:
    import_anchor = "import kotlinx.coroutines.withTimeoutOrNull\n"
    if import_anchor not in vv:
        raise SystemExit("symbol updater: VM import anchor not found")
    vv = vv.replace(
        import_anchor,
        import_anchor + "import org.json.JSONArray\nimport org.json.JSONObject\n",
        1
    )

state_anchor = "val catalogMessage: String? = null\n"
if "val symbolUpdateRunning: Boolean" not in vv:
    if state_anchor not in vv:
        raise SystemExit("symbol updater: ChandUiState anchor not found")
    vv = vv.replace(
        state_anchor,
        """val catalogMessage: String? = null,
val symbolUpdateRunning: Boolean = false,
val symbolUpdateProgress: Int = 0,
val symbolUpdateSucceeded: Boolean? = null,
val symbolUpdateMessage: String? = null
""",
        1
    )

field_anchor = "private var catalogPage = 1\n"
if "private val symbolCatalogPrefs" not in vv:
    if field_anchor not in vv:
        raise SystemExit("symbol updater: VM field anchor not found")
    vv = vv.replace(
        field_anchor,
        field_anchor + """private val symbolCatalogPrefs = application.getSharedPreferences("chand_symbol_catalog", 0)
private var savedGlobalCatalog: List<MarketDescriptor> = loadSavedGlobalCatalog()
""",
        1
    )

# Saved globals are merged into loadCatalog below. Selected descriptors are
# already persisted by the existing rememberSelection path, so startup behavior
# stays untouched.

if "val savedItems = if (source == CatalogSource.MARKETS)" not in vv:
    import re as _re
    catalog_pattern = _re.compile(
        r"""val\s+page\s*=\s*when\s*\(source\)\s*\{\s*
        CatalogSource\.MARKETS\s*->\s*repository\.searchMarkets\(normalizedQuery,\s*catalogPage\)\s*
        CatalogSource\.STOCKS\s*->\s*repository\.searchStocks\(normalizedQuery,\s*catalogPage\)\s*
        \}\s*
        page\.items\.forEach\s*\{\s*descriptorCache\[it\.id\]\s*=\s*it\s*\}\s*
        val\s+latest\s*=\s*_uiState\.value\s*
        if\s*\(latest\.catalogSource\s*!=\s*source\s*\|\|\s*latest\.catalogQuery\s*!=\s*normalizedQuery\)\s*return@launch\s*
        val\s+merged\s*=\s*if\s*\(loadMore\)\s*latest\.catalogItems\s*\+\s*page\.items\s*else\s*page\.items
        """,
        _re.VERBOSE
    )
    match = catalog_pattern.search(vv)
    if not match:
        raise SystemExit("symbol updater: loadCatalog flexible anchor not found")
    catalog_replacement = """val page = when (source) {
CatalogSource.MARKETS -> repository.searchMarkets(normalizedQuery, catalogPage)
CatalogSource.STOCKS -> repository.searchStocks(normalizedQuery, catalogPage)
}
val savedItems = if (source == CatalogSource.MARKETS) {
savedGlobalCatalog.filter { it.matchesCatalogQuery(normalizedQuery) }
} else {
emptyList()
}
val currentPageItems = (page.items + savedItems).distinctBy(MarketDescriptor::id)
currentPageItems.forEach { descriptorCache[it.id] = it }
val latest = _uiState.value
if (latest.catalogSource != source || latest.catalogQuery != normalizedQuery) return@launch
val merged = if (loadMore) latest.catalogItems + currentPageItems else currentPageItems"""
    vv = vv[:match.start()] + catalog_replacement + vv[match.end():]

action_anchor = "fun setGridMode(enabled: Boolean) = updateSettings { copy(gridMode = enabled) }\n"
if "fun updateSymbolCatalog()" not in vv:
    if action_anchor not in vv:
        raise SystemExit("symbol updater: action insertion anchor not found")
    action = r'''fun updateSymbolCatalog() {
if (_uiState.value.symbolUpdateRunning) return

_uiState.update {
it.copy(
symbolUpdateRunning = true,
symbolUpdateProgress = 0,
symbolUpdateSucceeded = null,
symbolUpdateMessage = "در حال آماده‌سازی به‌روزرسانی…"
)
}

viewModelScope.launch {
try {
_uiState.update {
it.copy(
symbolUpdateProgress = 5,
symbolUpdateMessage = "در حال دریافت فهرست بورس ایران…"
)
}

val previousStockIds = symbolCatalogPrefs
.getStringSet("last_stock_ids", emptySet())
.orEmpty()
.toSet()
val previousGlobalIds = savedGlobalCatalog.map(MarketDescriptor::id).toSet()
val hadPreviousSync = symbolCatalogPrefs.getBoolean("has_completed_sync", false)

val stocks = repository.refreshIranStockCatalogStrict()
stocks.forEach { descriptorCache[it.id] = it }

_uiState.update {
it.copy(
symbolUpdateProgress = 50,
symbolUpdateMessage = "بورس ایران دریافت شد؛ در حال بررسی بازار جهانی…"
)
}

val globals = repository.discoverGlobalCatalog { providerProgress ->
val mapped = 50 + ((providerProgress.coerceIn(0, 100) * 45) / 100)
_uiState.update { current ->
if (!current.symbolUpdateRunning) current
else current.copy(
symbolUpdateProgress = mapped.coerceIn(50, 95),
symbolUpdateMessage = "در حال دریافت نمادهای بازار جهانی…"
)
}
}.filter { it.source == MarketSource.TRADINGVIEW }
.distinctBy(MarketDescriptor::id)

globals.forEach { descriptorCache[it.id] = it }
savedGlobalCatalog = globals
saveGlobalCatalog(globals)

val stockIds = stocks.map(MarketDescriptor::id).toSet()
symbolCatalogPrefs.edit()
.putStringSet("last_stock_ids", stockIds)
.putBoolean("has_completed_sync", true)
.apply()

val newStocks = if (hadPreviousSync) {
stockIds.count { it !in previousStockIds }
} else 0
val newGlobals = if (hadPreviousSync) {
globals.count { it.id !in previousGlobalIds }
} else 0
val newTotal = newStocks + newGlobals

val successMessage = if (!hadPreviousSync) {
"به‌روزرسانی اولیه با موفقیت انجام شد. " +
stocks.size + " نماد بورس ایران و " +
globals.size + " نماد بازار جهانی همگام شد."
} else if (newTotal > 0) {
"به‌روزرسانی موفق بود. " +
newTotal + " نماد جدید اضافه شد (" +
newStocks + " بورس ایران، " +
newGlobals + " بازار جهانی)."
} else {
"به‌روزرسانی موفق بود. فهرست نمادها از قبل به‌روز است."
}

_uiState.update {
it.copy(
symbolUpdateRunning = false,
symbolUpdateProgress = 100,
symbolUpdateSucceeded = true,
symbolUpdateMessage = successMessage
)
}
} catch (cancelled: CancellationException) {
throw cancelled
} catch (failure: Throwable) {
_uiState.update {
it.copy(
symbolUpdateRunning = false,
symbolUpdateSucceeded = false,
symbolUpdateMessage = friendlySymbolUpdateError(failure)
)
}
}
}
}

private fun MarketDescriptor.matchesCatalogQuery(query: String): Boolean {
if (query.isBlank()) return true
return name.contains(query, ignoreCase = true) ||
code.contains(query, ignoreCase = true) ||
symbol.contains(query, ignoreCase = true) ||
category.contains(query, ignoreCase = true)
}

private fun saveGlobalCatalog(items: List<MarketDescriptor>) {
val array = JSONArray()
items.forEach { descriptor ->
array.put(
JSONObject()
.put("id", descriptor.id)
.put("sourceKey", descriptor.sourceKey)
.put("name", descriptor.name)
.put("code", descriptor.code)
.put("symbol", descriptor.symbol)
.put("category", descriptor.category)
.put("unit", descriptor.unit)
.put("valueScale", descriptor.valueScale)
)
}
symbolCatalogPrefs.edit()
.putString("global_catalog_json", array.toString())
.apply()
}

private fun loadSavedGlobalCatalog(): List<MarketDescriptor> {
val raw = symbolCatalogPrefs.getString("global_catalog_json", null) ?: return emptyList()
return runCatching {
val array = JSONArray(raw)
buildList {
for (index in 0 until array.length()) {
val row = array.optJSONObject(index) ?: continue
val id = row.optString("id").trim()
val sourceKey = row.optString("sourceKey").trim()
if (id.isBlank() || sourceKey.isBlank()) continue
add(
MarketDescriptor(
id = id,
sourceKey = sourceKey,
name = row.optString("name"),
code = row.optString("code"),
symbol = row.optString("symbol"),
source = MarketSource.TRADINGVIEW,
category = row.optString("category"),
unit = row.optString("unit"),
valueScale = row.optDouble("valueScale", 1.0)
)
)
}
}
}.getOrDefault(emptyList())
}

private fun friendlySymbolUpdateError(failure: Throwable): String {
val raw = failure.message.orEmpty()
val kind = failure::class.java.simpleName
return when {
kind.contains("UnknownHost", ignoreCase = true) ||
raw.contains("UnknownHost", ignoreCase = true) ->
"به اینترنت یا DNS دسترسی نیست. اتصال را بررسی کنید و دوباره بزنید."
kind.contains("Timeout", ignoreCase = true) ||
raw.contains("timeout", ignoreCase = true) ||
raw.contains("timed out", ignoreCase = true) ->
"زمان دریافت اطلاعات تمام شد. اتصال اینترنت یا دسترسی به منبع داده کند است."
raw.contains("TSETMC", ignoreCase = true) ->
"دریافت فهرست بورس ایران از TSETMC ناموفق بود."
raw.contains("بازار جهانی", ignoreCase = true) ->
raw
raw.isNotBlank() ->
"به‌روزرسانی انجام نشد: " + raw.take(140)
else ->
"به‌روزرسانی انجام نشد چون ارتباط معتبر با منبع داده برقرار نشد."
}
}

'''
    vv = vv.replace(action_anchor, action + action_anchor, 1)

vm_file.write_text(vv)

# 3) Settings UI: green 0..100 progress card / red failure card with reason.
ui_file = root / "MainActivity.kt"
uu = ui_file.read_text()

# Wire callback at the existing SettingsDialog call without changing any other call behavior.
settings_call_start = uu.find("SettingsDialog(", uu.find("if (settingsOpen)"))
if settings_call_start < 0:
    raise SystemExit("symbol updater: SettingsDialog call not found")
settings_call_end = uu.find("\n        )", settings_call_start)
if settings_call_end < 0:
    settings_call_end = uu.find("\n    )", settings_call_start)
if settings_call_end < 0:
    raise SystemExit("symbol updater: SettingsDialog call end not found")
settings_call = uu[settings_call_start:settings_call_end]
if "onUpdateSymbols" not in settings_call:
    import re as _re
    settings_call_new, count = _re.subn(
        r"(\n\s*onManage\s*=)",
        "\n            onUpdateSymbols = viewModel::updateSymbolCatalog,\\1",
        settings_call,
        count=1
    )
    if count != 1:
        raise SystemExit("symbol updater: onManage call anchor not found")
    uu = uu[:settings_call_start] + settings_call_new + uu[settings_call_end:]

if "onUpdateSymbols: () -> Unit" not in uu:
    import re as _re
    sig_pattern = _re.compile(
        r"""private\s+fun\s+SettingsDialog\(\s*
        state\s*:\s*ChandUiState\s*,\s*
        onDismiss\s*:\s*\(\)\s*->\s*Unit\s*,\s*
        onTheme\s*:\s*\(ThemeMode\)\s*->\s*Unit\s*,\s*
        onGrid\s*:\s*\(Boolean\)\s*->\s*Unit\s*,\s*
        onManage\s*:\s*\(\)\s*->\s*Unit\s*
        \)\s*\{""",
        _re.VERBOSE
    )
    match = sig_pattern.search(uu)
    if not match:
        raise SystemExit("symbol updater: SettingsDialog flexible signature anchor not found")
    signature_new = """private fun SettingsDialog(
state: ChandUiState,
onDismiss: () -> Unit,
onTheme: (ThemeMode) -> Unit,
onGrid: (Boolean) -> Unit,
onUpdateSymbols: () -> Unit,
onManage: () -> Unit
) {"""
    uu = uu[:match.start()] + signature_new + uu[match.end():]

if "بررسی و به‌روزرسانی نمادها" not in uu:
    settings_start = uu.find("private fun SettingsDialog(")
    settings_end = uu.find("@Composable\nprivate fun ManageItemsDialog(", settings_start)
    if settings_start < 0 or settings_end < 0:
        raise SystemExit("symbol updater: SettingsDialog range not found")

    manage_click = uu.find("onClick = onManage", settings_start, settings_end)
    if manage_click < 0:
        raise SystemExit("symbol updater: onManage click not found")
    manage_button_start = uu.rfind("TextButton", settings_start, manage_click)
    if manage_button_start < 0:
        raise SystemExit("symbol updater: manage TextButton start not found")

    update_ui = r'''Spacer(Modifier.height(12.dp))
HorizontalDivider(color = Color(0xFF343438))
Text(
"به‌روزرسانی نمادها",
color = ChandMuted,
fontSize = 12.sp,
modifier = Modifier.padding(top = 12.dp, bottom = 8.dp)
)

val updateAccent = when {
state.symbolUpdateSucceeded == false -> Color(0xFFFF5C65)
state.symbolUpdateRunning || state.symbolUpdateSucceeded == true -> Color(0xFF43D18B)
else -> Color(0xFF8E8E93)
}
val updateSurface = when {
state.symbolUpdateSucceeded == false -> Color(0xFF301619)
state.symbolUpdateRunning || state.symbolUpdateSucceeded == true -> Color(0xFF10291D)
else -> Color(0xFF232428)
}
val progressFraction = state.symbolUpdateProgress.coerceIn(0, 100) / 100f

Surface(
modifier = Modifier.fillMaxWidth(),
shape = RoundedCornerShape(16.dp),
color = updateSurface,
border = androidx.compose.foundation.BorderStroke(
1.dp,
updateAccent.copy(alpha = .78f)
)
) {
Column(Modifier.padding(12.dp)) {
Row(
modifier = Modifier.fillMaxWidth(),
verticalAlignment = Alignment.CenterVertically
) {
Text(
when {
state.symbolUpdateRunning -> "در حال به‌روزرسانی"
state.symbolUpdateSucceeded == true -> "به‌روزرسانی موفق"
state.symbolUpdateSucceeded == false -> "به‌روزرسانی ناموفق"
else -> "دریافت آخرین فهرست نمادها"
},
color = if (
state.symbolUpdateSucceeded == null &&
!state.symbolUpdateRunning
) Color.White else updateAccent,
fontWeight = FontWeight.Bold,
modifier = Modifier.weight(1f)
)
Text(
state.symbolUpdateProgress.coerceIn(0, 100).toString() + "%",
color = updateAccent,
fontWeight = FontWeight.Bold
)
}

Spacer(Modifier.height(10.dp))
Surface(
modifier = Modifier.fillMaxWidth().height(8.dp),
shape = CircleShape,
color = Color(0xFF3A3B40)
) {
Box(Modifier.fillMaxSize()) {
if (progressFraction > 0f) {
Surface(
modifier = Modifier
.fillMaxWidth(progressFraction)
.height(8.dp),
shape = CircleShape,
color = updateAccent
) {}
}
}
}

state.symbolUpdateMessage?.let { message ->
Spacer(Modifier.height(9.dp))
Text(
message,
color = if (state.symbolUpdateSucceeded == false)
Color(0xFFFFA2A8) else Color(0xFFD7D7DA),
fontSize = 12.sp,
lineHeight = 17.sp
)
}

Spacer(Modifier.height(6.dp))
TextButton(
onClick = onUpdateSymbols,
enabled = !state.symbolUpdateRunning,
modifier = Modifier.fillMaxWidth()
) {
Text(
if (state.symbolUpdateRunning)
"در حال دریافت…"
else
"بررسی و به‌روزرسانی نمادها",
color = if (state.symbolUpdateRunning)
ChandMuted else updateAccent,
fontWeight = FontWeight.Bold
)
}
}
}

Spacer(Modifier.height(6.dp))
'''
    uu = uu[:manage_button_start] + update_ui + uu[manage_button_start:]

ui_file.write_text(uu)

# Installation-only versionCode bump; visible app behavior/version branding remains otherwise untouched.
gradle = Path("source/app/build.gradle.kts")
gg = gradle.read_text()
gg = re.sub(r"versionCode\s*=\s*\d+", "versionCode = 31", gg, count=1)
gradle.write_text(gg)
