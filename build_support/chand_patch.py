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


# --- LOCKED v4.8.4 LIGHT MODE CARD POLISH ---
# Only LIGHT mode card/background colors and shadow are changed.
ui_file = root / "MainActivity.kt"
u = ui_file.read_text()

if "import androidx.compose.ui.graphics.luminance\n" not in u:
    anchor = "import androidx.compose.ui.graphics.Color\n"
    if anchor not in u:
        raise SystemExit("v4.8.4 light: Color import anchor not found")
    u = u.replace(anchor, anchor + "import androidx.compose.ui.graphics.luminance\n", 1)

grid_start = u.find("@Composable\nprivate fun MarketGrid(")
card_start = u.find("@Composable\nprivate fun MarketCard(", grid_start + 1)
if grid_start < 0 or card_start <= grid_start:
    raise SystemExit("v4.8.4 light: MarketGrid/MarketCard not found")

grid = u[grid_start:card_start]
if "0xFFE7E6E3" not in grid:
    grid = grid.replace(
        "modifier = Modifier.fillMaxSize()",
        """modifier = Modifier
            .fillMaxSize()
            .background(
                if (MaterialTheme.colorScheme.background.luminance() > 0.5f)
                    Color(0xFFE7E6E3)
                else
                    Color.Transparent
            )""",
        1
    )
u = u[:grid_start] + grid + u[card_start:]

card_start = u.find("@Composable\nprivate fun MarketCard(")
trend_start = u.find("private fun trendColor(", card_start + 1)
if card_start < 0 or trend_start <= card_start:
    raise SystemExit("v4.8.4 light: MarketCard range not found")
card = u[card_start:trend_start]

if "val lightMode = MaterialTheme.colorScheme.background.luminance() > 0.5f" not in card:
    sig_end = card.find(") {")
    if sig_end < 0:
        raise SystemExit("v4.8.4 light: MarketCard signature end not found")
    sig_end += 3
    card = card[:sig_end] + "\n    val lightMode = MaterialTheme.colorScheme.background.luminance() > 0.5f" + card[sig_end:]

card = card.replace(
    "colors = CardDefaults.cardColors(containerColor = ChandCard),",
    """colors = CardDefaults.cardColors(
            containerColor = if (lightMode) Color(0xFFFDFDFC) else ChandCard
        ),""",
    1
)
card = card.replace(
    "elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),",
    "elevation = CardDefaults.cardElevation(defaultElevation = if (lightMode) 6.dp else 0.dp),",
    1
)

name_pos = card.find("text = item.name,")
if name_pos < 0:
    raise SystemExit("v4.8.4 light: item.name not found")
before = card[:name_pos]
after = card[name_pos:]
after = after.replace(
    "color = Color.White,",
    "color = if (lightMode) Color(0xFF111111) else Color.White,",
    1
)
after = after.replace(
    "color = ChandMuted,",
    "color = if (lightMode) Color(0xFF8D8D92) else ChandMuted,",
    1
)
after = after.replace(
    "color = if (item.isAvailable) Color.White else ChandMuted,",
    """color = if (item.isAvailable) {
                        if (lightMode) Color(0xFF050505) else Color.White
                    } else {
                        if (lightMode) Color(0xFF9A9A9E) else ChandMuted
                    },""",
    1
)
card = before + after
u = u[:card_start] + card + u[trend_start:]
ui_file.write_text(u)


# --- LOCKED v4.8.4 SEPARATED CATALOG REFRESH REPOSITORY ---
repo_file = root / "data/MarketRepository.kt"
r = repo_file.read_text()

if "suspend fun refreshIranMarketCatalogStrict(" not in r:
    insertion = r.find("    private suspend fun loadTsetmcCatalog(")
    if insertion < 0:
        raise SystemExit("v4.8.4 updater: loadTsetmcCatalog anchor not found")

    methods = r'''    suspend fun refreshIranMarketCatalogStrict(
        onProgress: (Int) -> Unit = {}
    ): List<MarketDescriptor> = withContext(Dispatchers.IO) {
        val all = linkedMapOf<String, MarketDescriptor>()
        var page = 1
        var finished = false

        while (!finished && page <= 60) {
            val result = fetchTgjuCatalogModule("markets.internal", "", page)
            result.items
                .filterNot(::isTgjuStockDescriptor)
                .filterNot { descriptor ->
                    descriptor.category.contains("جهانی") ||
                        descriptor.category.contains("global", ignoreCase = true)
                }
                .filterNot { it.id in retiredIds }
                .forEach { all[it.id] = it }

            onProgress(
                if (result.hasMore) (page * 12).coerceAtMost(92) else 100
            )
            finished = !result.hasMore
            page += 1
        }

        if (all.isEmpty()) {
            throw IllegalStateException("TGJU فهرست معتبری برای بازار ایران برنگرداند")
        }

        val items = all.values
            .distinctBy(MarketDescriptor::id)
            .sortedWith(compareBy<MarketDescriptor> { it.code }.thenBy { it.name })

        synchronized(knownDescriptors) {
            items.forEach { knownDescriptors[it.id] = it }
        }
        items
    }

    suspend fun refreshIranStockCatalogStrict(
        onProgress: (Int) -> Unit = {}
    ): List<MarketDescriptor> = withContext(Dispatchers.IO) {
        onProgress(12)
        var lastFailure: Throwable? = null

        val cdnQuotes = runCatching {
            TsetmcProtocol.parseCdnMarketWatch(httpGet(TSETMC_MARKET_WATCH, 15_000))
        }.onFailure { lastFailure = it }.getOrNull().orEmpty()

        onProgress(52)
        val quotes = if (cdnQuotes.isNotEmpty()) {
            cdnQuotes
        } else {
            runCatching {
                TsetmcProtocol.parseLegacyInit(httpGet(TSETMC_LEGACY_INIT, 15_000)).quotes
            }.onFailure { lastFailure = it }.getOrNull().orEmpty()
        }

        if (quotes.isEmpty()) {
            throw IllegalStateException(
                "TSETMC پاسخ معتبر برای فهرست بورس ایران نداد",
                lastFailure
            )
        }

        onProgress(82)
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
        onProgress(100)
        descriptors
    }

    suspend fun refreshGlobalInvestingCatalogStrict(
        onProgress: (Int) -> Unit = {}
    ): List<MarketDescriptor> = withContext(Dispatchers.IO) {
        val seeds = (
            ('A'..'Z').map { it.toString() } +
            ('0'..'9').map { it.toString() } +
            listOf(
                "USD", "EUR", "GBP", "JPY", "CHF",
                "BTC", "ETH", "XAU", "XAG",
                "OIL", "BRENT", "INDEX", "ETF"
            )
        ).distinct()

        val found = linkedMapOf<String, MarketDescriptor>()
        TRADINGVIEW_MARKET_DESCRIPTORS.forEach { found[it.id] = it }

        var successes = 0
        var lastFailure: Throwable? = null

        seeds.forEachIndexed { index, seed ->
            runCatching {
                searchTradingViewCatalog(seed)
            }.onSuccess { page ->
                successes += 1
                page
                    .filter { it.source == MarketSource.TRADINGVIEW }
                    .forEach { found[it.id] = it }
            }.onFailure {
                lastFailure = it
            }
            onProgress(
                (((index + 1) * 100.0) / seeds.size)
                    .toInt()
                    .coerceIn(0, 100)
            )
        }

        if (successes == 0) {
            throw IllegalStateException(
                "Investing پاسخ معتبر برای بازار جهانی نداد",
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
    r = r[:insertion] + methods + r[insertion:]

repo_file.write_text(r)


# --- LOCKED v4.8.4 CATALOG UPDATE VIEWMODEL ---
vm_file = root / "MainViewModel.kt"
v = vm_file.read_text()

if "import org.json.JSONArray\n" not in v:
    import_anchor = "import kotlinx.coroutines.withTimeoutOrNull\n"
    if import_anchor not in v:
        raise SystemExit("v4.8.4 updater VM: import anchor not found")
    v = v.replace(
        import_anchor,
        import_anchor + "import org.json.JSONArray\nimport org.json.JSONObject\n",
        1
    )

if "data class CatalogUpdateUiState(" not in v:
    chand_state = v.find("data class ChandUiState(")
    if chand_state < 0:
        raise SystemExit("v4.8.4 updater VM: ChandUiState not found")
    update_state = '''data class CatalogUpdateUiState(
val running: Boolean = false,
val progress: Int = 0,
val success: Boolean? = null,
val message: String? = null
)

'''
    v = v[:chand_state] + update_state + v[chand_state:]

if "val iranMarketUpdate: CatalogUpdateUiState" not in v:
    anchor = "val catalogMessage: String? = null\n"
    if anchor not in v:
        raise SystemExit("v4.8.4 updater VM: catalogMessage anchor not found")
    v = v.replace(
        anchor,
        """val catalogMessage: String? = null,
val iranMarketUpdate: CatalogUpdateUiState = CatalogUpdateUiState(),
val iranStockUpdate: CatalogUpdateUiState = CatalogUpdateUiState(),
val globalMarketUpdate: CatalogUpdateUiState = CatalogUpdateUiState()
""",
        1
    )

if "private val catalogCachePrefs" not in v:
    anchor = "private val repository = MarketRepository(application)\n"
    if anchor not in v:
        raise SystemExit("v4.8.4 updater VM: repository anchor not found")
    v = v.replace(
        anchor,
        anchor + """private val catalogCachePrefs = application.getSharedPreferences("chand_catalog_updates_v484", 0)
private var savedIranMarketCatalog = loadSavedCatalog("iran_market", MarketSource.TGJU)
private var savedIranStockCatalog = loadSavedCatalog("iran_stock", MarketSource.TSETMC)
private var savedGlobalMarketCatalog = loadSavedCatalog("global_market", MarketSource.TRADINGVIEW)
""",
        1
    )

init_pattern = re.compile(
    r"""init\s*\{\s*
    WidgetUpdater\.schedule\(application\)\s*
    repository\.knownDescriptors\(\)\.forEach\s*\{\s*descriptorCache\[it\.id\]\s*=\s*it\s*\}\s*
    \}""",
    re.VERBOSE
)
if "savedIranMarketCatalog.forEach { descriptorCache[it.id] = it }" not in v:
    match = init_pattern.search(v)
    if not match:
        raise SystemExit("v4.8.4 updater VM: init block not found")
    new_init = """init {
WidgetUpdater.schedule(application)
repository.knownDescriptors().forEach { descriptorCache[it.id] = it }
savedIranMarketCatalog.forEach { descriptorCache[it.id] = it }
savedIranStockCatalog.forEach { descriptorCache[it.id] = it }
savedGlobalMarketCatalog.forEach { descriptorCache[it.id] = it }
}"""
    v = v[:match.start()] + new_init + v[match.end():]

if "val savedCatalogItems = when (source)" not in v:
    load_pattern = re.compile(
        r"""val\s+page\s*=\s*when\s*\(source\)\s*\{\s*
        CatalogSource\.MARKETS\s*->\s*repository\.searchMarkets\(normalizedQuery,\s*catalogPage\)\s*
        CatalogSource\.STOCKS\s*->\s*repository\.searchStocks\(normalizedQuery,\s*catalogPage\)\s*
        \}\s*
        page\.items\.forEach\s*\{\s*descriptorCache\[it\.id\]\s*=\s*it\s*\}\s*
        val\s+latest\s*=\s*_uiState\.value\s*
        if\s*\(latest\.catalogSource\s*!=\s*source\s*\|\|\s*latest\.catalogQuery\s*!=\s*normalizedQuery\)\s*return@launch\s*
        val\s+merged\s*=\s*if\s*\(loadMore\)\s*latest\.catalogItems\s*\+\s*page\.items\s*else\s*page\.items
        """,
        re.VERBOSE
    )
    match = load_pattern.search(v)
    if not match:
        raise SystemExit("v4.8.4 updater VM: loadCatalog block not found")
    replacement = """val page = when (source) {
CatalogSource.MARKETS -> repository.searchMarkets(normalizedQuery, catalogPage)
CatalogSource.STOCKS -> repository.searchStocks(normalizedQuery, catalogPage)
}
val savedCatalogItems = when (source) {
CatalogSource.MARKETS -> (savedIranMarketCatalog + savedGlobalMarketCatalog)
CatalogSource.STOCKS -> savedIranStockCatalog
}.filter { it.matchesCatalogQuery(normalizedQuery) }
val currentItems = (page.items + savedCatalogItems).distinctBy(MarketDescriptor::id)
currentItems.forEach { descriptorCache[it.id] = it }
val latest = _uiState.value
if (latest.catalogSource != source || latest.catalogQuery != normalizedQuery) return@launch
val merged = if (loadMore) latest.catalogItems + currentItems else currentItems"""
    v = v[:match.start()] + replacement + v[match.end():]

if "fun updateIranMarketCatalog()" not in v:
    anchor = "fun setGridMode(enabled: Boolean) = updateSettings { copy(gridMode = enabled) }\n"
    if anchor not in v:
        raise SystemExit("v4.8.4 updater VM: setGridMode anchor not found")

    methods = r'''fun updateIranMarketCatalog() {
runCatalogUpdate(
key = "iran_market",
label = "بازار ایران",
current = { _uiState.value.iranMarketUpdate },
set = { value -> _uiState.update { it.copy(iranMarketUpdate = value) } },
saved = { savedIranMarketCatalog },
save = { items ->
savedIranMarketCatalog = items
saveCatalog("iran_market", items)
},
fetch = { progress -> repository.refreshIranMarketCatalogStrict(progress) }
)
}

fun updateIranStockCatalog() {
runCatalogUpdate(
key = "iran_stock",
label = "بورس ایران",
current = { _uiState.value.iranStockUpdate },
set = { value -> _uiState.update { it.copy(iranStockUpdate = value) } },
saved = { savedIranStockCatalog },
save = { items ->
savedIranStockCatalog = items
saveCatalog("iran_stock", items)
},
fetch = { progress -> repository.refreshIranStockCatalogStrict(progress) }
)
}

fun updateGlobalMarketCatalog() {
runCatalogUpdate(
key = "global_market",
label = "بازار جهانی (Investing)",
current = { _uiState.value.globalMarketUpdate },
set = { value -> _uiState.update { it.copy(globalMarketUpdate = value) } },
saved = { savedGlobalMarketCatalog },
save = { items ->
savedGlobalMarketCatalog = items
saveCatalog("global_market", items)
},
fetch = { progress -> repository.refreshGlobalInvestingCatalogStrict(progress) }
)
}

private fun runCatalogUpdate(
key: String,
label: String,
current: () -> CatalogUpdateUiState,
set: (CatalogUpdateUiState) -> Unit,
saved: () -> List<MarketDescriptor>,
save: (List<MarketDescriptor>) -> Unit,
fetch: suspend ((Int) -> Unit) -> List<MarketDescriptor>
) {
if (current().running) return

set(
CatalogUpdateUiState(
running = true,
progress = 0,
success = null,
message = "در حال اتصال به منبع " + label + "…"
)
)

viewModelScope.launch {
try {
val oldItems = saved()
val oldIds = oldItems.map(MarketDescriptor::id).toSet()
val hadSync = catalogCachePrefs.getBoolean(key + "_synced", false)

val fresh = fetch { providerProgress ->
val progress = providerProgress.coerceIn(0, 100)
set(
current().copy(
running = true,
progress = progress,
success = null,
message = when {
progress < 25 -> "در حال دریافت فهرست " + label + "…"
progress < 75 -> "در حال بررسی نمادهای جدید…"
progress < 100 -> "در حال ثبت فهرست تازه…"
else -> "در حال نهایی‌سازی…"
}
)
)
}.distinctBy(MarketDescriptor::id)

if (fresh.isEmpty()) {
throw IllegalStateException("فهرست دریافتی خالی بود")
}

fresh.forEach { descriptorCache[it.id] = it }
save(fresh)
catalogCachePrefs.edit().putBoolean(key + "_synced", true).apply()

val newCount = if (hadSync) {
fresh.count { it.id !in oldIds }
} else 0

val message = if (!hadSync) {
"همگام‌سازی اولیه با موفقیت انجام شد؛ " + fresh.size + " نماد در دسترس قرار گرفت."
} else if (newCount > 0) {
"آپدیت موفق بود؛ " + newCount + " نماد جدید به لیست انتخابی اضافه شد."
} else {
"آپدیت موفق بود؛ نماد جدیدی پیدا نشد و فهرست شما به‌روز است."
}

set(
CatalogUpdateUiState(
running = false,
progress = 100,
success = true,
message = message
)
)
} catch (cancelled: CancellationException) {
throw cancelled
} catch (failure: Throwable) {
set(
current().copy(
running = false,
success = false,
message = catalogUpdateFailureMessage(label, failure)
)
)
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

private fun saveCatalog(key: String, items: List<MarketDescriptor>) {
val array = JSONArray()
items.forEach { descriptor ->
array.put(
JSONObject()
.put("id", descriptor.id)
.put("sourceKey", descriptor.sourceKey)
.put("name", descriptor.name)
.put("code", descriptor.code)
.put("symbol", descriptor.symbol)
.put("source", descriptor.source.name)
.put("category", descriptor.category)
.put("unit", descriptor.unit)
.put("valueScale", descriptor.valueScale)
)
}
catalogCachePrefs.edit().putString(key + "_json", array.toString()).apply()
}

private fun loadSavedCatalog(
key: String,
defaultSource: MarketSource
): List<MarketDescriptor> {
val raw = catalogCachePrefs.getString(key + "_json", null) ?: return emptyList()
return runCatching {
val array = JSONArray(raw)
buildList {
for (index in 0 until array.length()) {
val row = array.optJSONObject(index) ?: continue
val id = row.optString("id").trim()
val sourceKey = row.optString("sourceKey").trim()
if (id.isBlank() || sourceKey.isBlank()) continue
val source = runCatching {
MarketSource.valueOf(row.optString("source"))
}.getOrDefault(defaultSource)
add(
MarketDescriptor(
id = id,
sourceKey = sourceKey,
name = row.optString("name"),
code = row.optString("code"),
symbol = row.optString("symbol"),
source = source,
category = row.optString("category"),
unit = row.optString("unit"),
valueScale = row.optDouble("valueScale", 1.0)
)
)
}
}
}.getOrDefault(emptyList())
}

private fun catalogUpdateFailureMessage(label: String, failure: Throwable): String {
val raw = failure.message.orEmpty()
val kind = failure::class.java.simpleName
return when {
kind.contains("UnknownHost", ignoreCase = true) ||
raw.contains("Unable to resolve host", ignoreCase = true) ||
raw.contains("UnknownHost", ignoreCase = true) ->
"دلیل: اینترنت یا DNS به منبع " + label + " دسترسی ندارد. راه‌حل: اینترنت/VPN را بررسی کنید، DNS را تغییر دهید و دوباره «بررسی آپدیت» را بزنید."

kind.contains("Timeout", ignoreCase = true) ||
raw.contains("timeout", ignoreCase = true) ||
raw.contains("timed out", ignoreCase = true) ->
"دلیل: پاسخ " + label + " در زمان مقرر نرسید. راه‌حل: اتصال پایدارتر را امتحان کنید و چند لحظه بعد دوباره آپدیت بگیرید."

raw.contains("403") || raw.contains("429") ->
"دلیل: منبع " + label + " فعلاً درخواست را محدود کرده است. راه‌حل: چند دقیقه صبر کنید، شبکه را عوض کنید و دوباره تلاش کنید."

raw.contains("TSETMC", ignoreCase = true) ->
"دلیل: TSETMC فهرست معتبر بورس را برنگرداند. راه‌حل: اتصال اینترنت را بررسی کنید و بعد از باز شدن سرویس بورس دوباره آپدیت بگیرید."

raw.contains("TGJU", ignoreCase = true) ->
"دلیل: TGJU فهرست معتبر بازار ایران را برنگرداند. راه‌حل: اتصال اینترنت/VPN را بررسی کنید و دوباره تلاش کنید."

raw.contains("Investing", ignoreCase = true) ->
"دلیل: Investing پاسخ معتبر برای بازار جهانی نداد. راه‌حل: اینترنت/VPN را بررسی کنید و چند لحظه بعد دوباره تلاش کنید."

else ->
"دلیل: " + raw.ifBlank { "ارتباط معتبر با منبع برقرار نشد" }.take(150) +
". راه‌حل: اینترنت را بررسی کنید و دوباره آپدیت بگیرید."
}
}

'''
    v = v.replace(anchor, methods + anchor, 1)

vm_file.write_text(v)


# --- LOCKED v4.8.4 SETTINGS UPDATE UI ---
ui_file = root / "MainActivity.kt"
u = ui_file.read_text()

if "import androidx.compose.foundation.rememberScrollState\n" not in u:
    anchor = "import androidx.compose.foundation.clickable\n"
    if anchor not in u:
        raise SystemExit("v4.8.4 updater UI: clickable import anchor not found")
    u = u.replace(
        anchor,
        anchor + "import androidx.compose.foundation.rememberScrollState\nimport androidx.compose.foundation.verticalScroll\n",
        1
    )

call_start = u.find("SettingsDialog(", u.find("if (settingsOpen)"))
if call_start < 0:
    raise SystemExit("v4.8.4 updater UI: SettingsDialog call not found")
call_end = u.find("\n        )", call_start)
if call_end < 0:
    call_end = u.find("\n    )", call_start)
if call_end < 0:
    raise SystemExit("v4.8.4 updater UI: SettingsDialog call end not found")

call = u[call_start:call_end]
if "onUpdateIranMarket" not in call:
    match = re.search(r"\n\s*onManage\s*=", call)
    if not match:
        raise SystemExit("v4.8.4 updater UI: onManage named arg not found")
    addition = """
            onUpdateIranMarket = viewModel::updateIranMarketCatalog,
            onUpdateIranStock = viewModel::updateIranStockCatalog,
            onUpdateGlobalMarket = viewModel::updateGlobalMarketCatalog,"""
    call = call[:match.start()] + addition + call[match.start():]
    u = u[:call_start] + call + u[call_end:]

settings_start = u.find("@Composable\nprivate fun SettingsDialog(")
manage_start = u.find("@Composable\nprivate fun ManageItemsDialog(", settings_start)
if settings_start < 0 or manage_start <= settings_start:
    raise SystemExit("v4.8.4 updater UI: SettingsDialog range not found")

settings_new = r'''@Composable
private fun SettingsDialog(
state: ChandUiState,
onDismiss: () -> Unit,
onTheme: (ThemeMode) -> Unit,
onGrid: (Boolean) -> Unit,
onUpdateIranMarket: () -> Unit,
onUpdateIranStock: () -> Unit,
onUpdateGlobalMarket: () -> Unit,
onManage: () -> Unit
) {
val isLight = MaterialTheme.colorScheme.background.luminance() > 0.5f
AlertDialog(
onDismissRequest = onDismiss,
containerColor = if (isLight) Color(0xFFFDFDFC) else ChandCard,
title = {
Text(
"تنظیمات",
color = if (isLight) Color(0xFF111111) else Color.White
)
},
text = {
Column(
modifier = Modifier
.heightIn(max = 620.dp)
.verticalScroll(rememberScrollState())
) {
Row(
modifier = Modifier.fillMaxWidth(),
verticalAlignment = Alignment.CenterVertically
) {
Text("چیدمان دو ستونه", Modifier.weight(1f))
Switch(state.settings.gridMode, onGrid)
}
HorizontalDivider(
color = if (isLight) Color(0xFFD9D9DD) else Color(0xFF343438)
)
Text(
"ظاهر",
color = if (isLight) Color(0xFF77777C) else ChandMuted,
fontSize = 12.sp,
modifier = Modifier.padding(top = 12.dp)
)
ThemeMode.entries.forEach { mode ->
Row(
modifier = Modifier
.fillMaxWidth()
.clickable { onTheme(mode) }
.padding(vertical = 9.dp),
verticalAlignment = Alignment.CenterVertically
) {
Text(
when (mode) {
ThemeMode.DARK -> "تیره (مشابه Chand)"
ThemeMode.SYSTEM -> "مطابق دستگاه"
ThemeMode.LIGHT -> "روشن"
},
Modifier.weight(1f)
)
if (state.settings.themeMode == mode) Icon(Icons.Default.Check, null)
}
}

HorizontalDivider(
color = if (isLight) Color(0xFFD9D9DD) else Color(0xFF343438),
modifier = Modifier.padding(top = 8.dp)
)
Text(
"به‌روزرسانی فهرست نمادها",
fontWeight = FontWeight.Bold,
fontSize = 14.sp,
modifier = Modifier.padding(top = 14.dp, bottom = 4.dp)
)
Text(
"هر منبع جداگانه بررسی می‌شود و فقط فهرست نمادهای قابل انتخاب تازه می‌شود.",
color = if (isLight) Color(0xFF77777C) else ChandMuted,
fontSize = 11.sp,
lineHeight = 15.sp,
modifier = Modifier.padding(bottom = 10.dp)
)

CatalogUpdateCard(
title = "بازار ایران",
provider = "TGJU",
state = state.iranMarketUpdate,
onUpdate = onUpdateIranMarket
)
Spacer(Modifier.height(8.dp))
CatalogUpdateCard(
title = "بورس ایران",
provider = "TSETMC",
state = state.iranStockUpdate,
onUpdate = onUpdateIranStock
)
Spacer(Modifier.height(8.dp))
CatalogUpdateCard(
title = "بازار جهانی",
provider = "Investing",
state = state.globalMarketUpdate,
onUpdate = onUpdateGlobalMarket
)

Spacer(Modifier.height(8.dp))
TextButton(onClick = onManage, modifier = Modifier.fillMaxWidth()) {
Text("مدیریت قیمت‌ها")
}
}
},
confirmButton = { TextButton(onClick = onDismiss) { Text("تمام") } }
)
}

@Composable
private fun CatalogUpdateCard(
title: String,
provider: String,
state: CatalogUpdateUiState,
onUpdate: () -> Unit
) {
val isLight = MaterialTheme.colorScheme.background.luminance() > 0.5f
val accent = when {
state.success == false -> Color(0xFFE34E57)
state.running || state.success == true -> Color(0xFF36B979)
else -> if (isLight) Color(0xFF5C5C62) else ChandMuted
}
val surfaceColor = when {
state.success == false -> if (isLight) Color(0xFFFFEFF0) else Color(0xFF32191B)
state.running || state.success == true -> if (isLight) Color(0xFFEDFAF3) else Color(0xFF10291D)
else -> if (isLight) Color.White else Color(0xFF242428)
}
val progress = state.progress.coerceIn(0, 100)

Surface(
modifier = Modifier.fillMaxWidth(),
shape = RoundedCornerShape(16.dp),
color = surfaceColor,
border = androidx.compose.foundation.BorderStroke(
1.dp,
accent.copy(alpha = if (state.success == null && !state.running) .26f else .72f)
),
shadowElevation = if (isLight) 2.dp else 0.dp
) {
Column(Modifier.padding(12.dp)) {
Row(
modifier = Modifier.fillMaxWidth(),
verticalAlignment = Alignment.CenterVertically
) {
Column(Modifier.weight(1f)) {
Text(
title,
fontWeight = FontWeight.Bold,
fontSize = 14.sp,
color = if (isLight) Color(0xFF111111) else Color.White
)
Text(
provider,
fontSize = 11.sp,
color = if (isLight) Color(0xFF85858A) else ChandMuted
)
}
Text(
progress.toString() + "%",
color = accent,
fontWeight = FontWeight.Bold,
fontSize = 14.sp
)
}

Spacer(Modifier.height(9.dp))
Surface(
modifier = Modifier
.fillMaxWidth()
.height(9.dp),
shape = CircleShape,
color = if (isLight) Color(0xFFE1E1E4) else Color(0xFF3B3B40)
) {
Box(Modifier.fillMaxSize()) {
if (progress > 0) {
Surface(
modifier = Modifier
.fillMaxWidth(progress / 100f)
.height(9.dp),
shape = CircleShape,
color = accent
) {}
}
}
}

state.message?.let { message ->
Spacer(Modifier.height(8.dp))
Text(
message,
fontSize = 11.sp,
lineHeight = 16.sp,
color = when {
state.success == false -> if (isLight) Color(0xFFB4232D) else Color(0xFFFFA0A6)
isLight -> Color(0xFF4F4F54)
else -> Color(0xFFD6D6DA)
}
)
}

TextButton(
onClick = onUpdate,
enabled = !state.running,
modifier = Modifier.fillMaxWidth()
) {
Text(
if (state.running) "در حال دریافت…" else "بررسی آپدیت",
color = if (state.running) {
if (isLight) Color(0xFF99999E) else ChandMuted
} else accent,
fontWeight = FontWeight.Bold
)
}
}
}

'''
u = u[:settings_start] + settings_new + u[manage_start:]
ui_file.write_text(u)

# Installation-only versionCode bump; v4.8.4 behavior remains the baseline.
gradle = Path("source/app/build.gradle.kts")
g = gradle.read_text()
g = re.sub(r"versionCode\s*=\s*\d+", "versionCode = 40", g, count=1)
gradle.write_text(g)


# --- FIX LOCKED SETTINGS HELPER CLOSURE ---
# Close only the CatalogUpdateCard helper before the untouched ManageItemsDialog.
u = ui_file.read_text()
manage_marker = "@Composable\nprivate fun ManageItemsDialog("
manage_pos = u.find(manage_marker)
if manage_pos < 0:
    raise SystemExit("v4.8.4 updater UI: ManageItemsDialog marker not found")
prefix = u[:manage_pos]
if "private fun CatalogUpdateCard(" in prefix:
    # The updater helper intentionally lives immediately before ManageItemsDialog.
    u = u[:manage_pos] + "}\n\n" + u[manage_pos:]
ui_file.write_text(u)


# --- LOCKED v4.8.4 WIDGETS ONLY: premium day/night widget pack ---
# IMPORTANT: Everything above remains the verified app baseline.
# This block modifies ONLY widget provider / widget resources / widget receivers.
# Main app UI, pricing, live feeds, catalog updater, logos, ordering and settings stay untouched.

res = Path("source/app/src/main/res")
widget_file = root / "widget/ChandWidgetProvider.kt"

widget_file.write_text(r'''package ir.personal.chand.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import androidx.work.CoroutineWorker
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import ir.personal.chand.MainActivity
import ir.personal.chand.R
import ir.personal.chand.data.DEFAULT_MARKET_DESCRIPTORS
import ir.personal.chand.data.DEFAULT_VISIBLE_IDS
import ir.personal.chand.data.DataOrigin
import ir.personal.chand.data.MarketItem
import ir.personal.chand.data.MarketSource
import ir.personal.chand.ui.MarketFormatting
import org.json.JSONArray
import org.json.JSONObject

class ChandWidgetProvider : AppWidgetProvider() {
    override fun onEnabled(context: Context) {
        WidgetUpdater.schedule(context)
        WidgetUpdater.refreshNow(context)
    }

    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        WidgetUpdater.schedule(context)
        val items = WidgetUpdater.readItems(context)
        ids.forEach { id ->
            WidgetUpdater.updateSingle(context, manager, id, items.first())
        }
        WidgetUpdater.refreshNow(context)
    }
}

class ChandWideWidgetProvider : AppWidgetProvider() {
    override fun onEnabled(context: Context) {
        WidgetUpdater.schedule(context)
        WidgetUpdater.refreshNow(context)
    }

    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        WidgetUpdater.schedule(context)
        val items = WidgetUpdater.readItems(context)
        ids.forEach { id ->
            WidgetUpdater.updateWide(context, manager, id, items.first())
        }
        WidgetUpdater.refreshNow(context)
    }
}

class ChandTripleWidgetProvider : AppWidgetProvider() {
    override fun onEnabled(context: Context) {
        WidgetUpdater.schedule(context)
        WidgetUpdater.refreshNow(context)
    }

    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        WidgetUpdater.schedule(context)
        val items = WidgetUpdater.readItems(context)
        ids.forEach { id ->
            WidgetUpdater.updateTriple(context, manager, id, items)
        }
        WidgetUpdater.refreshNow(context)
    }
}

class ChandGridWidgetProvider : AppWidgetProvider() {
    override fun onEnabled(context: Context) {
        WidgetUpdater.schedule(context)
        WidgetUpdater.refreshNow(context)
    }

    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        WidgetUpdater.schedule(context)
        val items = WidgetUpdater.readItems(context)
        ids.forEach { id ->
            WidgetUpdater.updateGrid(context, manager, id, items)
        }
        WidgetUpdater.refreshNow(context)
    }
}

class WidgetRefreshWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        WidgetUpdater.updateAll(applicationContext, WidgetUpdater.readItems(applicationContext))
        return Result.success()
    }
}

object WidgetUpdater {
    private const val ITEMS_KEY = "items_v3"
    private const val PERIODIC_WORK = "chand-widget-periodic-v2"
    private const val IMMEDIATE_WORK = "chand-widget-now-v2"
    private var lastWidgetCacheWriteAt = 0L

    fun schedule(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(PERIODIC_WORK)
        WorkManager.getInstance(context).cancelUniqueWork(IMMEDIATE_WORK)
    }

    fun refreshNow(context: Context) {
        updateAll(context, readItems(context))
    }

    fun updateAll(context: Context, incoming: List<MarketItem>, forceCacheWrite: Boolean = false) {
        val validIncoming = incoming.filter {
            it.isAvailable && it.price.isFinite() && it.price > 0.0
        }
        val cached = readItems(context)
        val validById = validIncoming.associateBy(MarketItem::id)
        val displayItems = buildList {
            incoming.forEach { item ->
                validById[item.id]?.let(::add)
                    ?: cached.firstOrNull { it.id == item.id }?.let(::add)
            }
            cached.forEach { item ->
                if (none { it.id == item.id }) add(item)
            }
        }.ifEmpty { cached }

        if (validIncoming.isNotEmpty()) saveItems(context, displayItems, forceCacheWrite)

        val manager = AppWidgetManager.getInstance(context)

        manager.getAppWidgetIds(
            ComponentName(context, ChandWidgetProvider::class.java)
        ).forEach { id ->
            updateSingle(context, manager, id, displayItems.first())
        }

        manager.getAppWidgetIds(
            ComponentName(context, ChandWideWidgetProvider::class.java)
        ).forEach { id ->
            updateWide(context, manager, id, displayItems.first())
        }

        manager.getAppWidgetIds(
            ComponentName(context, ChandTripleWidgetProvider::class.java)
        ).forEach { id ->
            updateTriple(context, manager, id, displayItems)
        }

        manager.getAppWidgetIds(
            ComponentName(context, ChandGridWidgetProvider::class.java)
        ).forEach { id ->
            updateGrid(context, manager, id, displayItems)
        }
    }

    fun updateSingle(
        context: Context,
        manager: AppWidgetManager,
        id: Int,
        item: MarketItem
    ) {
        val views = RemoteViews(context.packageName, R.layout.widget_single).apply {
            setTextViewText(R.id.widget_symbol, widgetSymbol(item.id, item.symbol))
            setTextViewText(R.id.widget_code, item.code)
            setTextViewText(R.id.widget_price, MarketFormatting.price(item))
            setTextViewText(R.id.widget_change, MarketFormatting.change(item))
            setTextColor(R.id.widget_change, trendColor(context, item))
            setOnClickPendingIntent(R.id.widget_root, launchIntent(context))
        }
        manager.updateAppWidget(id, views)
    }

    fun updateWide(
        context: Context,
        manager: AppWidgetManager,
        id: Int,
        item: MarketItem
    ) {
        val views = RemoteViews(context.packageName, R.layout.widget_wide).apply {
            setTextViewText(R.id.wide_symbol, widgetSymbol(item.id, item.symbol))
            setTextViewText(R.id.wide_name, item.name)
            setTextViewText(R.id.wide_code, item.code)
            setTextViewText(R.id.wide_price, MarketFormatting.price(item))
            setTextViewText(R.id.wide_change, MarketFormatting.change(item))
            setTextColor(R.id.wide_change, trendColor(context, item))
            setOnClickPendingIntent(R.id.wide_root, launchIntent(context))
        }
        manager.updateAppWidget(id, views)
    }

    fun updateTriple(
        context: Context,
        manager: AppWidgetManager,
        id: Int,
        input: List<MarketItem>
    ) {
        val items = displaySet(input, 3)
        val views = RemoteViews(context.packageName, R.layout.widget_triple).apply {
            bindListRow(context, this, 1, items[0])
            bindListRow(context, this, 2, items[1])
            bindListRow(context, this, 3, items[2])
            setOnClickPendingIntent(R.id.triple_root, launchIntent(context))
        }
        manager.updateAppWidget(id, views)
    }

    fun updateGrid(
        context: Context,
        manager: AppWidgetManager,
        id: Int,
        input: List<MarketItem>
    ) {
        val items = displaySet(input, 4)
        val views = RemoteViews(context.packageName, R.layout.widget_grid).apply {
            bindGridCell(context, this, 1, items[0])
            bindGridCell(context, this, 2, items[1])
            bindGridCell(context, this, 3, items[2])
            bindGridCell(context, this, 4, items[3])
            setOnClickPendingIntent(R.id.grid_root, launchIntent(context))
        }
        manager.updateAppWidget(id, views)
    }

    private fun bindListRow(
        context: Context,
        views: RemoteViews,
        row: Int,
        item: MarketItem
    ) {
        val symbolId = when (row) {
            1 -> R.id.triple_symbol_1
            2 -> R.id.triple_symbol_2
            else -> R.id.triple_symbol_3
        }
        val codeId = when (row) {
            1 -> R.id.triple_code_1
            2 -> R.id.triple_code_2
            else -> R.id.triple_code_3
        }
        val priceId = when (row) {
            1 -> R.id.triple_price_1
            2 -> R.id.triple_price_2
            else -> R.id.triple_price_3
        }
        val changeId = when (row) {
            1 -> R.id.triple_change_1
            2 -> R.id.triple_change_2
            else -> R.id.triple_change_3
        }

        views.setTextViewText(symbolId, widgetSymbol(item.id, item.symbol))
        views.setTextViewText(codeId, item.code)
        views.setTextViewText(priceId, MarketFormatting.price(item))
        views.setTextViewText(changeId, MarketFormatting.change(item))
        views.setTextColor(changeId, trendColor(context, item))
    }

    private fun bindGridCell(
        context: Context,
        views: RemoteViews,
        cell: Int,
        item: MarketItem
    ) {
        val symbolId = when (cell) {
            1 -> R.id.grid_symbol_1
            2 -> R.id.grid_symbol_2
            3 -> R.id.grid_symbol_3
            else -> R.id.grid_symbol_4
        }
        val codeId = when (cell) {
            1 -> R.id.grid_code_1
            2 -> R.id.grid_code_2
            3 -> R.id.grid_code_3
            else -> R.id.grid_code_4
        }
        val priceId = when (cell) {
            1 -> R.id.grid_price_1
            2 -> R.id.grid_price_2
            3 -> R.id.grid_price_3
            else -> R.id.grid_price_4
        }
        val changeId = when (cell) {
            1 -> R.id.grid_change_1
            2 -> R.id.grid_change_2
            3 -> R.id.grid_change_3
            else -> R.id.grid_change_4
        }

        views.setTextViewText(symbolId, widgetSymbol(item.id, item.symbol))
        views.setTextViewText(codeId, item.code)
        views.setTextViewText(priceId, MarketFormatting.price(item))
        views.setTextViewText(changeId, MarketFormatting.change(item))
        views.setTextColor(changeId, trendColor(context, item))
    }

    fun readItems(context: Context): List<MarketItem> {
        val prefs = context.getSharedPreferences("chand_widget", Context.MODE_PRIVATE)
        val raw = prefs.getString(ITEMS_KEY, null)
            ?: prefs.getString("items_v2", null)
            ?: return defaults()

        return runCatching {
            val array = JSONArray(raw)
            buildList {
                for (index in 0 until array.length()) {
                    val value = array.optJSONObject(index) ?: continue
                    val price = value.optDouble("price", Double.NaN)
                    if (!price.isFinite() || price <= 0.0) continue

                    add(
                        MarketItem(
                            id = value.optString("id"),
                            name = value.optString("name"),
                            code = value.optString("code"),
                            symbol = value.optString("symbol", "•"),
                            price = price,
                            change = value.optDouble("change", 0.0),
                            changePercent = value.optDouble("changePercent", 0.0),
                            high = value.optDouble("high", price),
                            low = value.optDouble("low", price),
                            buy = price,
                            sell = price,
                            history = emptyList(),
                            sourceUpdatedAtMillis = value.optLong("sourceUpdatedAt", 0L),
                            receivedAtMillis = value.optLong("receivedAt", 0L),
                            origin = DataOrigin.CACHE,
                            isAvailable = true,
                            source = MarketSource.TGJU,
                            unit = value.optString("unit", "تومان")
                        )
                    )
                }
            }
        }.getOrDefault(emptyList()).ifEmpty { defaults() }
    }

    private fun saveItems(context: Context, items: List<MarketItem>, force: Boolean) {
        val now = System.currentTimeMillis()
        if (!force && now - lastWidgetCacheWriteAt < 10_000L) return
        lastWidgetCacheWriteAt = now

        val array = JSONArray().apply {
            items.take(8).forEach { item ->
                if (!item.isAvailable || item.price <= 0.0) return@forEach
                put(JSONObject().apply {
                    put("id", item.id)
                    put("name", item.name)
                    put("code", item.code)
                    put("symbol", item.symbol)
                    put("price", item.price)
                    put("change", item.change)
                    put("changePercent", item.changePercent)
                    put("high", item.high)
                    put("low", item.low)
                    put("unit", item.unit)
                    put("sourceUpdatedAt", item.sourceUpdatedAtMillis)
                    put("receivedAt", item.receivedAtMillis)
                })
            }
        }

        context.getSharedPreferences("chand_widget", Context.MODE_PRIVATE)
            .edit()
            .putString(ITEMS_KEY, array.toString())
            .apply()
    }

    private fun displaySet(input: List<MarketItem>, count: Int): List<MarketItem> {
        val merged = (input + defaults()).distinctBy(MarketItem::id).toMutableList()
        val fallback = defaults()
        while (merged.size < count && fallback.isNotEmpty()) {
            merged.add(fallback[merged.size % fallback.size])
        }
        return merged.take(count)
    }

    private fun widgetSymbol(id: String, fallback: String): String = when (id) {
        "usd" -> "🇺🇸"
        "euro" -> "🇪🇺"
        "gold18", "emami" -> "🟡"
        else -> fallback.ifBlank { "•" }
    }

    private fun trendColor(context: Context, item: MarketItem): Int = context.getColor(
        when {
            !item.isAvailable || item.change == 0.0 -> R.color.widget_neutral
            item.change > 0.0 -> R.color.widget_up
            else -> R.color.widget_down
        }
    )

    private fun launchIntent(context: Context): PendingIntent = PendingIntent.getActivity(
        context,
        0,
        Intent(context, MainActivity::class.java),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
    )

    private fun defaults(): List<MarketItem> = DEFAULT_MARKET_DESCRIPTORS
        .filter { it.id in DEFAULT_VISIBLE_IDS }
        .map { descriptor ->
            MarketItem(
                id = descriptor.id,
                name = descriptor.name,
                code = descriptor.code,
                symbol = descriptor.symbol,
                price = 0.0,
                change = 0.0,
                changePercent = 0.0,
                high = 0.0,
                low = 0.0,
                buy = 0.0,
                sell = 0.0,
                history = emptyList(),
                sourceUpdatedAtMillis = 0L,
                receivedAtMillis = 0L,
                origin = DataOrigin.UNAVAILABLE,
                isAvailable = false,
                source = descriptor.source,
                category = descriptor.category,
                unit = descriptor.unit
            )
        }
}
''')

# Widget-only day colors.
(res / "values/colors.xml").write_text(r'''<resources>
    <color name="chand_icon_background">#FAF7F6</color>
    <color name="widget_background">#F2F1EE</color>
    <color name="widget_surface">#FEFEFD</color>
    <color name="widget_surface_alt">#F2F2F4</color>
    <color name="widget_text">#111113</color>
    <color name="widget_muted">#7D7D83</color>
    <color name="widget_up">#21A468</color>
    <color name="widget_down">#D94B55</color>
    <color name="widget_neutral">#8E8E93</color>
    <color name="widget_border">#D9D9DE</color>
    <color name="widget_divider">#E5E5E8</color>
    <color name="widget_chip">#ECECEF</color>
</resources>
''')

# Automatic night colors; no app-theme behavior is changed.
values_night = res / "values-night"
values_night.mkdir(parents=True, exist_ok=True)
(values_night / "colors.xml").write_text(r'''<resources>
    <color name="chand_icon_background">#FAF7F6</color>
    <color name="widget_background">#111113</color>
    <color name="widget_surface">#1C1C1E</color>
    <color name="widget_surface_alt">#28282C</color>
    <color name="widget_text">#FFFFFF</color>
    <color name="widget_muted">#A8A8AD</color>
    <color name="widget_up">#57B97D</color>
    <color name="widget_down">#E45C61</color>
    <color name="widget_neutral">#A8A8AD</color>
    <color name="widget_border">#35FFFFFF</color>
    <color name="widget_divider">#22FFFFFF</color>
    <color name="widget_chip">#2B2B2F</color>
</resources>
''')

drawable = res / "drawable"
drawable_night = res / "drawable-night"
drawable_night.mkdir(parents=True, exist_ok=True)

(drawable / "widget_background.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <gradient android:angle="270" android:startColor="#FFFFFF" android:endColor="#F7F7F5" />
    <corners android:radius="28dp" />
    <stroke android:width="1dp" android:color="@color/widget_border" />
</shape>
''')
(drawable_night / "widget_background.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <gradient android:angle="270" android:startColor="#222225" android:endColor="#171719" />
    <corners android:radius="28dp" />
    <stroke android:width="1dp" android:color="@color/widget_border" />
</shape>
''')

(drawable / "widget_cell_background.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="@color/widget_surface_alt" />
    <corners android:radius="20dp" />
    <stroke android:width="1dp" android:color="@color/widget_border" />
</shape>
''')
(drawable_night / "widget_cell_background.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="@color/widget_surface_alt" />
    <corners android:radius="20dp" />
    <stroke android:width="1dp" android:color="@color/widget_border" />
</shape>
''')

(drawable / "widget_chip_background.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="@color/widget_chip" />
    <corners android:radius="999dp" />
</shape>
''')
(drawable_night / "widget_chip_background.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="@color/widget_chip" />
    <corners android:radius="999dp" />
</shape>
''')

# Compact single-price widget.
(res / "layout/widget_single.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/widget_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@drawable/widget_background"
    android:gravity="center_vertical"
    android:orientation="vertical"
    android:padding="14dp">

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:gravity="center_vertical"
        android:orientation="horizontal">

        <TextView
            android:id="@+id/widget_symbol"
            android:layout_width="42dp"
            android:layout_height="42dp"
            android:background="@drawable/widget_chip_background"
            android:gravity="center"
            android:text="@string/widget_preview_symbol"
            android:textSize="21sp" />

        <TextView
            android:id="@+id/widget_code"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_marginStart="10dp"
            android:layout_weight="1"
            android:gravity="end"
            android:fontFamily="sans-serif-medium"
            android:maxLines="1"
            android:text="@string/widget_preview_code"
            android:textColor="@color/widget_text"
            android:textSize="15sp" />
    </LinearLayout>

    <TextView
        android:id="@+id/widget_change"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_marginTop="12dp"
        android:fontFamily="sans-serif-medium"
        android:text="@string/widget_preview_change"
        android:textColor="@color/widget_up"
        android:textSize="13sp" />

    <TextView
        android:id="@+id/widget_price"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:fontFamily="sans-serif-black"
        android:gravity="start"
        android:maxLines="1"
        android:text="@string/widget_preview_price"
        android:textColor="@color/widget_text"
        android:textSize="27sp" />
</LinearLayout>
''')

# Premium wide focus widget.
(res / "layout/widget_wide.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/wide_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@drawable/widget_background"
    android:gravity="center_vertical"
    android:orientation="horizontal"
    android:padding="16dp">

    <TextView
        android:id="@+id/wide_symbol"
        android:layout_width="56dp"
        android:layout_height="56dp"
        android:background="@drawable/widget_chip_background"
        android:gravity="center"
        android:text="@string/widget_preview_symbol"
        android:textSize="28sp" />

    <LinearLayout
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:layout_marginStart="13dp"
        android:layout_weight="1"
        android:orientation="vertical">

        <TextView
            android:id="@+id/wide_name"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:ellipsize="end"
            android:fontFamily="sans-serif-medium"
            android:maxLines="1"
            android:text="@string/widget_preview_name"
            android:textColor="@color/widget_text"
            android:textSize="16sp" />

        <TextView
            android:id="@+id/wide_code"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:layout_marginTop="2dp"
            android:fontFamily="sans-serif"
            android:maxLines="1"
            android:text="@string/widget_preview_code"
            android:textColor="@color/widget_muted"
            android:textSize="11sp" />
    </LinearLayout>

    <LinearLayout
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:gravity="end"
        android:orientation="vertical">

        <TextView
            android:id="@+id/wide_price"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:fontFamily="sans-serif-black"
            android:gravity="end"
            android:maxLines="1"
            android:text="@string/widget_preview_price"
            android:textColor="@color/widget_text"
            android:textSize="27sp" />

        <TextView
            android:id="@+id/wide_change"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:layout_marginTop="1dp"
            android:fontFamily="sans-serif-medium"
            android:gravity="end"
            android:text="@string/widget_preview_change"
            android:textColor="@color/widget_up"
            android:textSize="12sp" />
    </LinearLayout>
</LinearLayout>
''')

# Three-price modern list.
(res / "layout/widget_triple.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/triple_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@drawable/widget_background"
    android:orientation="vertical"
    android:padding="12dp">

    <TextView
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:fontFamily="sans-serif-medium"
        android:text="@string/widget_market_title"
        android:textColor="@color/widget_muted"
        android:textSize="10sp" />

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_marginTop="5dp"
        android:layout_weight="1"
        android:gravity="center_vertical"
        android:orientation="horizontal">
        <TextView android:id="@+id/triple_symbol_1" android:layout_width="34dp" android:layout_height="34dp" android:background="@drawable/widget_chip_background" android:gravity="center" android:text="@string/widget_preview_symbol" android:textSize="17sp" />
        <TextView android:id="@+id/triple_code_1" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="9dp" android:layout_weight="1" android:fontFamily="sans-serif-medium" android:text="@string/widget_preview_code" android:textColor="@color/widget_text" android:textSize="13sp" />
        <LinearLayout android:layout_width="wrap_content" android:layout_height="wrap_content" android:gravity="end" android:orientation="vertical">
            <TextView android:id="@+id/triple_price_1" android:layout_width="wrap_content" android:layout_height="wrap_content" android:fontFamily="sans-serif-bold" android:gravity="end" android:maxLines="1" android:text="@string/widget_preview_price" android:textColor="@color/widget_text" android:textSize="16sp" />
            <TextView android:id="@+id/triple_change_1" android:layout_width="wrap_content" android:layout_height="wrap_content" android:fontFamily="sans-serif-medium" android:gravity="end" android:text="@string/widget_preview_change" android:textColor="@color/widget_up" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>

    <View android:layout_width="match_parent" android:layout_height="1dp" android:background="@color/widget_divider" />

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1"
        android:gravity="center_vertical"
        android:orientation="horizontal">
        <TextView android:id="@+id/triple_symbol_2" android:layout_width="34dp" android:layout_height="34dp" android:background="@drawable/widget_chip_background" android:gravity="center" android:text="🇪🇺" android:textSize="17sp" />
        <TextView android:id="@+id/triple_code_2" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="9dp" android:layout_weight="1" android:fontFamily="sans-serif-medium" android:text="EUR" android:textColor="@color/widget_text" android:textSize="13sp" />
        <LinearLayout android:layout_width="wrap_content" android:layout_height="wrap_content" android:gravity="end" android:orientation="vertical">
            <TextView android:id="@+id/triple_price_2" android:layout_width="wrap_content" android:layout_height="wrap_content" android:fontFamily="sans-serif-bold" android:gravity="end" android:maxLines="1" android:text="246,400" android:textColor="@color/widget_text" android:textSize="16sp" />
            <TextView android:id="@+id/triple_change_2" android:layout_width="wrap_content" android:layout_height="wrap_content" android:fontFamily="sans-serif-medium" android:gravity="end" android:text="↑7.4K" android:textColor="@color/widget_up" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>

    <View android:layout_width="match_parent" android:layout_height="1dp" android:background="@color/widget_divider" />

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1"
        android:gravity="center_vertical"
        android:orientation="horizontal">
        <TextView android:id="@+id/triple_symbol_3" android:layout_width="34dp" android:layout_height="34dp" android:background="@drawable/widget_chip_background" android:gravity="center" android:text="🟡" android:textSize="17sp" />
        <TextView android:id="@+id/triple_code_3" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="9dp" android:layout_weight="1" android:fontFamily="sans-serif-medium" android:text="GRAM" android:textColor="@color/widget_text" android:textSize="13sp" />
        <LinearLayout android:layout_width="wrap_content" android:layout_height="wrap_content" android:gravity="end" android:orientation="vertical">
            <TextView android:id="@+id/triple_price_3" android:layout_width="wrap_content" android:layout_height="wrap_content" android:fontFamily="sans-serif-bold" android:gravity="end" android:maxLines="1" android:text="22.323M" android:textColor="@color/widget_text" android:textSize="16sp" />
            <TextView android:id="@+id/triple_change_3" android:layout_width="wrap_content" android:layout_height="wrap_content" android:fontFamily="sans-serif-medium" android:gravity="end" android:text="↑558K" android:textColor="@color/widget_up" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>
</LinearLayout>
''')

# Four-price 2x2 market board.
(res / "layout/widget_grid.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/grid_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@drawable/widget_background"
    android:orientation="vertical"
    android:padding="9dp">

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1"
        android:orientation="horizontal">

        <LinearLayout
            android:layout_width="0dp"
            android:layout_height="match_parent"
            android:layout_margin="3dp"
            android:layout_weight="1"
            android:background="@drawable/widget_cell_background"
            android:orientation="vertical"
            android:padding="10dp">
            <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center_vertical" android:orientation="horizontal">
                <TextView android:id="@+id/grid_symbol_1" android:layout_width="30dp" android:layout_height="30dp" android:background="@drawable/widget_chip_background" android:gravity="center" android:text="@string/widget_preview_symbol" android:textSize="15sp" />
                <TextView android:id="@+id/grid_code_1" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="7dp" android:layout_weight="1" android:fontFamily="sans-serif-medium" android:gravity="end" android:text="@string/widget_preview_code" android:textColor="@color/widget_muted" android:textSize="10sp" />
            </LinearLayout>
            <TextView android:id="@+id/grid_price_1" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:fontFamily="sans-serif-black" android:gravity="bottom|start" android:maxLines="1" android:text="@string/widget_preview_price" android:textColor="@color/widget_text" android:textSize="18sp" />
            <TextView android:id="@+id/grid_change_1" android:layout_width="wrap_content" android:layout_height="wrap_content" android:fontFamily="sans-serif-medium" android:text="@string/widget_preview_change" android:textColor="@color/widget_up" android:textSize="10sp" />
        </LinearLayout>

        <LinearLayout
            android:layout_width="0dp"
            android:layout_height="match_parent"
            android:layout_margin="3dp"
            android:layout_weight="1"
            android:background="@drawable/widget_cell_background"
            android:orientation="vertical"
            android:padding="10dp">
            <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center_vertical" android:orientation="horizontal">
                <TextView android:id="@+id/grid_symbol_2" android:layout_width="30dp" android:layout_height="30dp" android:background="@drawable/widget_chip_background" android:gravity="center" android:text="🇪🇺" android:textSize="15sp" />
                <TextView android:id="@+id/grid_code_2" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="7dp" android:layout_weight="1" android:fontFamily="sans-serif-medium" android:gravity="end" android:text="EUR" android:textColor="@color/widget_muted" android:textSize="10sp" />
            </LinearLayout>
            <TextView android:id="@+id/grid_price_2" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:fontFamily="sans-serif-black" android:gravity="bottom|start" android:maxLines="1" android:text="246,400" android:textColor="@color/widget_text" android:textSize="18sp" />
            <TextView android:id="@+id/grid_change_2" android:layout_width="wrap_content" android:layout_height="wrap_content" android:fontFamily="sans-serif-medium" android:text="↑7.4K" android:textColor="@color/widget_up" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1"
        android:orientation="horizontal">

        <LinearLayout
            android:layout_width="0dp"
            android:layout_height="match_parent"
            android:layout_margin="3dp"
            android:layout_weight="1"
            android:background="@drawable/widget_cell_background"
            android:orientation="vertical"
            android:padding="10dp">
            <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center_vertical" android:orientation="horizontal">
                <TextView android:id="@+id/grid_symbol_3" android:layout_width="30dp" android:layout_height="30dp" android:background="@drawable/widget_chip_background" android:gravity="center" android:text="🟡" android:textSize="15sp" />
                <TextView android:id="@+id/grid_code_3" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="7dp" android:layout_weight="1" android:fontFamily="sans-serif-medium" android:gravity="end" android:text="GRAM" android:textColor="@color/widget_muted" android:textSize="10sp" />
            </LinearLayout>
            <TextView android:id="@+id/grid_price_3" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:fontFamily="sans-serif-black" android:gravity="bottom|start" android:maxLines="1" android:text="22.323M" android:textColor="@color/widget_text" android:textSize="18sp" />
            <TextView android:id="@+id/grid_change_3" android:layout_width="wrap_content" android:layout_height="wrap_content" android:fontFamily="sans-serif-medium" android:text="↑558K" android:textColor="@color/widget_up" android:textSize="10sp" />
        </LinearLayout>

        <LinearLayout
            android:layout_width="0dp"
            android:layout_height="match_parent"
            android:layout_margin="3dp"
            android:layout_weight="1"
            android:background="@drawable/widget_cell_background"
            android:orientation="vertical"
            android:padding="10dp">
            <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center_vertical" android:orientation="horizontal">
                <TextView android:id="@+id/grid_symbol_4" android:layout_width="30dp" android:layout_height="30dp" android:background="@drawable/widget_chip_background" android:gravity="center" android:text="🟡" android:textSize="15sp" />
                <TextView android:id="@+id/grid_code_4" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="7dp" android:layout_weight="1" android:fontFamily="sans-serif-medium" android:gravity="end" android:text="EMAMI" android:textColor="@color/widget_muted" android:textSize="10sp" />
            </LinearLayout>
            <TextView android:id="@+id/grid_price_4" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:fontFamily="sans-serif-black" android:gravity="bottom|start" android:maxLines="1" android:text="—" android:textColor="@color/widget_text" android:textSize="18sp" />
            <TextView android:id="@+id/grid_change_4" android:layout_width="wrap_content" android:layout_height="wrap_content" android:fontFamily="sans-serif-medium" android:text="—" android:textColor="@color/widget_neutral" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>
</LinearLayout>
''')

# Widget descriptions / previews.
strings = res / "values/strings.xml"
x = strings.read_text()
if 'name="wide_widget_name"' not in x:
    x = x.replace(
        "</resources>",
        """    <string name="wide_widget_name">Chand — کارت عریض</string>
    <string name="grid_widget_name">Chand — پنل چهارتایی</string>
    <string name="widget_preview_name" translatable="false">US Dollar</string>
    <string name="widget_market_title">Chand?! • Market</string>
</resources>"""
    )
strings.write_text(x)

(res / "xml/chand_wide_widget_info.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools"
    tools:targetApi="s"
    android:description="@string/wide_widget_name"
    android:initialLayout="@layout/widget_wide"
    android:minWidth="250dp"
    android:minHeight="82dp"
    android:previewLayout="@layout/widget_wide"
    android:resizeMode="horizontal|vertical"
    android:updatePeriodMillis="1800000"
    android:widgetCategory="home_screen" />
''')

(res / "xml/chand_grid_widget_info.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools"
    tools:targetApi="s"
    android:description="@string/grid_widget_name"
    android:initialLayout="@layout/widget_grid"
    android:minWidth="250dp"
    android:minHeight="220dp"
    android:previewLayout="@layout/widget_grid"
    android:resizeMode="horizontal|vertical"
    android:updatePeriodMillis="1800000"
    android:widgetCategory="home_screen" />
''')

# Refine existing widget size declarations only (widget-only metadata).
(res / "xml/chand_widget_info.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools"
    tools:targetApi="s"
    android:description="@string/widget_name"
    android:initialLayout="@layout/widget_single"
    android:minWidth="145dp"
    android:minHeight="120dp"
    android:previewLayout="@layout/widget_single"
    android:resizeMode="horizontal|vertical"
    android:updatePeriodMillis="1800000"
    android:widgetCategory="home_screen" />
''')

(res / "xml/chand_triple_widget_info.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools"
    tools:targetApi="s"
    android:description="@string/triple_widget_name"
    android:initialLayout="@layout/widget_triple"
    android:minWidth="250dp"
    android:minHeight="185dp"
    android:previewLayout="@layout/widget_triple"
    android:resizeMode="horizontal|vertical"
    android:updatePeriodMillis="1800000"
    android:widgetCategory="home_screen" />
''')

# Add ONLY the two new widget receivers to the manifest.
manifest = Path("source/app/src/main/AndroidManifest.xml")
m = manifest.read_text()
if ".widget.ChandWideWidgetProvider" not in m:
    receiver = r'''
        <receiver
            android:name=".widget.ChandWideWidgetProvider"
            android:exported="true">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/chand_wide_widget_info" />
        </receiver>

        <receiver
            android:name=".widget.ChandGridWidgetProvider"
            android:exported="true">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/chand_grid_widget_info" />
        </receiver>
'''
    m = m.replace("    </application>", receiver + "    </application>", 1)
manifest.write_text(m)

# Installation-only bump so this widget pack can install over the prior build.
gradle = Path("source/app/build.gradle.kts")
g = gradle.read_text()
g = re.sub(r"versionCode\s*=\s*\d+", "versionCode = 41", g, count=1)
gradle.write_text(g)


# --- LOCKED v4.8.4: widget background refresh + light market search + pull refresh ---
# Only these three scoped changes are applied:
# 1) Widget-only background network refresh via WorkManager.
# 2) Manage/search dialog light-mode colors.
# 3) Pull-to-refresh on the main market grid with an immediate serialized network fetch.
# All other app behavior remains untouched.

# 1) Widget background refresh.
widget_file = root / "widget/ChandWidgetProvider.kt"
w = widget_file.read_text()

widget_import_anchor = "import androidx.work.CoroutineWorker\n"
widget_imports = """import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
"""
if "import androidx.work.PeriodicWorkRequestBuilder" not in w:
    if widget_import_anchor not in w:
        raise SystemExit("locked refresh: widget CoroutineWorker import anchor not found")
    w = w.replace(widget_import_anchor, widget_imports, 1)

if "import ir.personal.chand.data.MarketRepository\n" not in w:
    anchor = "import ir.personal.chand.data.MarketItem\n"
    if anchor not in w:
        raise SystemExit("locked refresh: MarketItem import anchor not found")
    w = w.replace(anchor, anchor + "import ir.personal.chand.data.MarketRepository\n", 1)

if "import java.util.concurrent.TimeUnit\n" not in w:
    anchor = "import org.json.JSONObject\n"
    if anchor not in w:
        raise SystemExit("locked refresh: JSONObject import anchor not found")
    w = w.replace(anchor, anchor + "import java.util.concurrent.TimeUnit\n", 1)

old_worker = """class WidgetRefreshWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        WidgetUpdater.updateAll(applicationContext, WidgetUpdater.readItems(applicationContext))
        return Result.success()
    }
}
"""
new_worker = """class WidgetRefreshWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        return try {
            val repository = MarketRepository(applicationContext)
            val visibleIds = repository.loadSettings().visibleIds
            val snapshot = repository.fetch(visibleIds)
            val valid = snapshot.items.any {
                it.isAvailable && it.price.isFinite() && it.price > 0.0
            }
            if (valid) {
                WidgetUpdater.updateAll(
                    applicationContext,
                    snapshot.items,
                    forceCacheWrite = true
                )
                Result.success()
            } else {
                WidgetUpdater.updateAll(
                    applicationContext,
                    WidgetUpdater.readItems(applicationContext)
                )
                Result.retry()
            }
        } catch (_: Throwable) {
            WidgetUpdater.updateAll(
                applicationContext,
                WidgetUpdater.readItems(applicationContext)
            )
            Result.retry()
        }
    }
}
"""
if old_worker in w:
    w = w.replace(old_worker, new_worker, 1)
elif "val repository = MarketRepository(applicationContext)" not in w:
    raise SystemExit("locked refresh: WidgetRefreshWorker block not found")

old_constants = """    private const val PERIODIC_WORK = "chand-widget-periodic-v2"
    private const val IMMEDIATE_WORK = "chand-widget-now-v2"
"""
new_constants = """    private const val PERIODIC_WORK = "chand-widget-periodic-v3"
    private const val IMMEDIATE_WORK = "chand-widget-now-v3"
    private const val OLD_PERIODIC_WORK = "chand-widget-periodic-v2"
    private const val OLD_IMMEDIATE_WORK = "chand-widget-now-v2"
"""
if old_constants in w:
    w = w.replace(old_constants, new_constants, 1)

old_schedule = """    fun schedule(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(PERIODIC_WORK)
        WorkManager.getInstance(context).cancelUniqueWork(IMMEDIATE_WORK)
    }

    fun refreshNow(context: Context) {
        updateAll(context, readItems(context))
    }
"""
new_schedule = """    fun schedule(context: Context) {
        val workManager = WorkManager.getInstance(context)
        workManager.cancelUniqueWork(OLD_PERIODIC_WORK)
        workManager.cancelUniqueWork(OLD_IMMEDIATE_WORK)

        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val periodic = PeriodicWorkRequestBuilder<WidgetRefreshWorker>(
            15,
            TimeUnit.MINUTES
        )
            .setConstraints(constraints)
            .build()

        workManager.enqueueUniquePeriodicWork(
            PERIODIC_WORK,
            ExistingPeriodicWorkPolicy.KEEP,
            periodic
        )
    }

    fun refreshNow(context: Context) {
        updateAll(context, readItems(context))

        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val immediate = OneTimeWorkRequestBuilder<WidgetRefreshWorker>()
            .setConstraints(constraints)
            .build()

        WorkManager.getInstance(context).enqueueUniqueWork(
            IMMEDIATE_WORK,
            ExistingWorkPolicy.REPLACE,
            immediate
        )
    }
"""
if old_schedule in w:
    w = w.replace(old_schedule, new_schedule, 1)
elif "enqueueUniquePeriodicWork" not in w:
    raise SystemExit("locked refresh: WidgetUpdater schedule block not found")

widget_file.write_text(w)

# 2) Light mode for the market/search dialog only.
ui_file = root / "MainActivity.kt"
u = ui_file.read_text()

if "import androidx.compose.material3.pulltorefresh.PullToRefreshBox\n" not in u:
    anchor = "import androidx.compose.material3.TextButton\n"
    if anchor not in u:
        raise SystemExit("locked refresh: TextButton import anchor not found")
    u = u.replace(
        anchor,
        anchor + "import androidx.compose.material3.pulltorefresh.PullToRefreshBox\n",
        1
    )

manage_start = u.find("@Composable\nprivate fun ManageItemsDialog(")
source_start = u.find("@Composable\nprivate fun SourceButton(", manage_start)
if manage_start < 0 or source_start <= manage_start:
    raise SystemExit("locked refresh: ManageItemsDialog range not found")
manage = u[manage_start:source_start]

if "val manageLightMode = MaterialTheme.colorScheme.background.luminance() > 0.5f" not in manage:
    body_anchor = ") {\n    var query by remember(state.catalogSource)"
    if body_anchor not in manage:
        raise SystemExit("locked refresh: ManageItemsDialog body anchor not found")
    manage = manage.replace(
        body_anchor,
        """) {
    val manageLightMode = MaterialTheme.colorScheme.background.luminance() > 0.5f
    var query by remember(state.catalogSource)""",
        1
    )

manage = manage.replace(
    "containerColor = ChandCard,",
    "containerColor = if (manageLightMode) Color(0xFFFDFDFC) else ChandCard,",
    1
)
manage = manage.replace(
    "HorizontalDivider(color = Color(0xFF2C2C2E))",
    """HorizontalDivider(
                        color = if (manageLightMode) Color(0xFFD9D9DD) else Color(0xFF2C2C2E)
                    )""",
    1
)
u = u[:manage_start] + manage + u[source_start:]

# Make the source selector itself readable on the light search sheet.
source_start = u.find("@Composable\nprivate fun SourceButton(")
source_end = u.find("\n}", source_start)
if source_start < 0 or source_end <= source_start:
    raise SystemExit("locked refresh: SourceButton not found")
# Find the actual end of the small function via the next known function marker if present.
next_fun = u.find("\n@Composable", source_start + 12)
if next_fun > source_start:
    source_end = next_fun
source = u[source_start:source_end]
if "val light = MaterialTheme.colorScheme.background.luminance() > 0.5f" not in source:
    source = source.replace(
        ") {\nSurface(",
        """) {
val light = MaterialTheme.colorScheme.background.luminance() > 0.5f
Surface(""",
        1
    )
source = source.replace(
    "color = if (selected) Color.White else Color(0xFF2C2C2E),",
    """color = when {
selected && light -> Color(0xFF111113)
selected -> Color.White
light -> Color(0xFFF0F0F2)
else -> Color(0xFF2C2C2E)
},""",
    1
)
source = source.replace(
    "contentColor = if (selected) Color.Black else ChandMuted,",
    """contentColor = when {
selected && light -> Color.White
selected -> Color.Black
light -> Color(0xFF4A4A4F)
else -> ChandMuted
},""",
    1
)
u = u[:source_start] + source + u[source_end:]

# 3) Pull-to-refresh with an immediate serialized network refresh.
vm_file = root / "MainViewModel.kt"
v = vm_file.read_text()

if "import kotlinx.coroutines.sync.Mutex\n" not in v:
    anchor = "import kotlinx.coroutines.launch\n"
    if anchor not in v:
        raise SystemExit("locked refresh: VM launch import anchor not found")
    v = v.replace(
        anchor,
        anchor + "import kotlinx.coroutines.sync.Mutex\nimport kotlinx.coroutines.sync.withLock\n",
        1
    )

if "val pullRefreshing: Boolean = false" not in v:
    anchor = "val globalMarketUpdate: CatalogUpdateUiState = CatalogUpdateUiState()\n"
    if anchor not in v:
        raise SystemExit("locked refresh: globalMarketUpdate state anchor not found")
    v = v.replace(
        anchor,
        "val globalMarketUpdate: CatalogUpdateUiState = CatalogUpdateUiState(),\nval pullRefreshing: Boolean = false\n",
        1
    )

if "private val refreshMutex = Mutex()" not in v:
    anchor = "private var historyJob: Job? = null\n"
    if anchor not in v:
        raise SystemExit("locked refresh: historyJob anchor not found")
    v = v.replace(
        anchor,
        anchor + "    private var pullRefreshJob: Job? = null\n    private val refreshMutex = Mutex()\n",
        1
    )

if "fun pullToRefresh()" not in v:
    anchor = """    fun refresh() {
        refreshSignal.trySend(Unit)
        if (pollingJob?.isActive != true) startPolling()
    }

"""
    if anchor not in v:
        raise SystemExit("locked refresh: refresh method anchor not found")
    method = """    fun pullToRefresh() {
        if (pullRefreshJob?.isActive == true) return
        _uiState.update { it.copy(pullRefreshing = true) }
        pullRefreshJob = viewModelScope.launch {
            try {
                refreshOnce(showInitialLoading = false)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                // Existing snapshot stays visible; only the pull indicator stops.
            } finally {
                _uiState.update { it.copy(pullRefreshing = false) }
            }
        }
    }

"""
    v = v.replace(anchor, anchor + method, 1)

if "private suspend fun refreshOnceInternal(" not in v:
    old_sig = "    private suspend fun refreshOnce(showInitialLoading: Boolean) {\n"
    if old_sig not in v:
        raise SystemExit("locked refresh: refreshOnce signature not found")
    wrapper = """    private suspend fun refreshOnce(showInitialLoading: Boolean) {
        refreshMutex.withLock {
            refreshOnceInternal(showInitialLoading)
        }
    }

    private suspend fun refreshOnceInternal(showInitialLoading: Boolean) {
"""
    v = v.replace(old_sig, wrapper, 1)

vm_file.write_text(v)

# Wire PullToRefreshBox only around the existing main content box.
u = ui_file.read_text()

main_box = """            Box(modifier = Modifier.weight(1f)) {
                when {
                    state.loading && state.snapshot == null -> CircularProgressIndicator(
                        color = ChandMuted,
                        strokeWidth = 2.dp,
                        modifier = Modifier.align(Alignment.Center)
                    )
                    state.visibleItems.isEmpty() -> EmptyState {
                        viewModel.loadCatalog(CatalogSource.MARKETS)
                        manageOpen = true
                    }
                    else -> MarketGrid(
                        items = state.visibleItems,
                        gridMode = state.settings.gridMode,
                        onItemClick = { viewModel.showChart(it.id) },
                        onMove = viewModel::moveVisibleItem
                    )
                }
            }
"""
pull_box = """            PullToRefreshBox(
                isRefreshing = state.pullRefreshing,
                onRefresh = viewModel::pullToRefresh,
                modifier = Modifier.weight(1f)
            ) {
                Box(modifier = Modifier.fillMaxSize()) {
                    when {
                        state.loading && state.snapshot == null -> CircularProgressIndicator(
                            color = ChandMuted,
                            strokeWidth = 2.dp,
                            modifier = Modifier.align(Alignment.Center)
                        )
                        state.visibleItems.isEmpty() -> EmptyState {
                            viewModel.loadCatalog(CatalogSource.MARKETS)
                            manageOpen = true
                        }
                        else -> MarketGrid(
                            items = state.visibleItems,
                            gridMode = state.settings.gridMode,
                            onItemClick = { viewModel.showChart(it.id) },
                            onMove = viewModel::moveVisibleItem
                        )
                    }
                }
            }
"""
if main_box in u:
    u = u.replace(main_box, pull_box, 1)
elif "onRefresh = viewModel::pullToRefresh" not in u:
    raise SystemExit("locked refresh: main content Box anchor not found")

ui_file.write_text(u)

# Installation-only versionCode bump.
gradle = Path("source/app/build.gradle.kts")
g = gradle.read_text()
g = re.sub(r"versionCode\s*=\s*\d+", "versionCode = 42", g, count=1)
gradle.write_text(g)


# --- FIX v4.8.4 pull gesture without Material3 pull API ---
# Material3 in this project does not expose PullToRefreshBox.
# Implement a non-consuming pull gesture directly on the existing LazyVerticalGrid.

ui_file = root / "MainActivity.kt"
u = ui_file.read_text()

u = u.replace(
    "import androidx.compose.material3.pulltorefresh.PullToRefreshBox\n",
    ""
)

if "import androidx.compose.ui.input.pointer.awaitEachGesture\n" not in u:
    anchor = "import androidx.compose.ui.input.pointer.pointerInput\n"
    if anchor not in u:
        raise SystemExit("pull fix: pointerInput import anchor not found")
    u = u.replace(
        anchor,
        anchor +
        "import androidx.compose.ui.input.pointer.awaitEachGesture\n" +
        "import androidx.compose.ui.input.pointer.awaitFirstDown\n" +
        "import androidx.compose.ui.input.pointer.positionChange\n",
        1
    )

pull_box = """            PullToRefreshBox(
                isRefreshing = state.pullRefreshing,
                onRefresh = viewModel::pullToRefresh,
                modifier = Modifier.weight(1f)
            ) {
                Box(modifier = Modifier.fillMaxSize()) {
                    when {
                        state.loading && state.snapshot == null -> CircularProgressIndicator(
                            color = ChandMuted,
                            strokeWidth = 2.dp,
                            modifier = Modifier.align(Alignment.Center)
                        )
                        state.visibleItems.isEmpty() -> EmptyState {
                            viewModel.loadCatalog(CatalogSource.MARKETS)
                            manageOpen = true
                        }
                        else -> MarketGrid(
                            items = state.visibleItems,
                            gridMode = state.settings.gridMode,
                            onItemClick = { viewModel.showChart(it.id) },
                            onMove = viewModel::moveVisibleItem
                        )
                    }
                }
            }
"""
plain_box = """            Box(modifier = Modifier.weight(1f)) {
                when {
                    state.loading && state.snapshot == null -> CircularProgressIndicator(
                        color = ChandMuted,
                        strokeWidth = 2.dp,
                        modifier = Modifier.align(Alignment.Center)
                    )
                    state.visibleItems.isEmpty() -> EmptyState {
                        viewModel.loadCatalog(CatalogSource.MARKETS)
                        manageOpen = true
                    }
                    else -> MarketGrid(
                        items = state.visibleItems,
                        gridMode = state.settings.gridMode,
                        onItemClick = { viewModel.showChart(it.id) },
                        onMove = viewModel::moveVisibleItem,
                        onPullRefresh = viewModel::pullToRefresh
                    )
                }

                if (state.pullRefreshing) {
                    CircularProgressIndicator(
                        color = ChandMuted,
                        strokeWidth = 2.dp,
                        modifier = Modifier
                            .align(Alignment.TopCenter)
                            .padding(top = 8.dp)
                            .size(22.dp)
                    )
                }
            }
"""
if pull_box in u:
    u = u.replace(pull_box, plain_box, 1)
elif "onPullRefresh = viewModel::pullToRefresh" not in u:
    raise SystemExit("pull fix: PullToRefreshBox block not found")

# Add callback to MarketGrid only.
grid_start = u.find("@Composable\nprivate fun MarketGrid(")
card_start = u.find("@Composable\nprivate fun MarketCard(", grid_start + 1)
if grid_start < 0 or card_start <= grid_start:
    raise SystemExit("pull fix: MarketGrid range not found")
grid = u[grid_start:card_start]

if "onPullRefresh: () -> Unit" not in grid:
    grid = grid.replace(
        """    onItemClick: (MarketItem) -> Unit,
    onMove: (String, Int) -> Unit
) {""",
        """    onItemClick: (MarketItem) -> Unit,
    onMove: (String, Int) -> Unit,
    onPullRefresh: () -> Unit
) {""",
        1
    )

old_modifier = "        modifier = Modifier.fillMaxSize()\n"
new_modifier = """        modifier = Modifier
            .fillMaxSize()
            .pointerInput(gridState, onPullRefresh) {
                val triggerDistance = 84.dp.toPx()
                awaitEachGesture {
                    awaitFirstDown(requireUnconsumed = false)
                    var pullDistance = 0f
                    var fired = false

                    do {
                        val event = awaitPointerEvent()
                        val change = event.changes.firstOrNull() ?: break

                        if (!gridState.canScrollBackward && !fired) {
                            val dy = change.positionChange().y
                            pullDistance = if (dy > 0f) {
                                pullDistance + dy
                            } else {
                                (pullDistance + dy).coerceAtLeast(0f)
                            }

                            if (pullDistance >= triggerDistance) {
                                fired = true
                                onPullRefresh()
                            }
                        } else if (gridState.canScrollBackward) {
                            pullDistance = 0f
                        }
                    } while (event.changes.any { it.pressed })
                }
            }
"""
if old_modifier in grid and "triggerDistance = 84.dp.toPx()" not in grid:
    grid = grid.replace(old_modifier, new_modifier, 1)

u = u[:grid_start] + grid + u[card_start:]
ui_file.write_text(u)
