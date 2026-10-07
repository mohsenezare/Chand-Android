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

# Normalize the older workflow-injected LIVE overlay first; this keeps the card clean
# and gives the new status component full control of LIVE/CLOSED rendering.
u = re.sub(
    r'''                    Box\(modifier = Modifier\.size\(if \(compact\) 45\.dp else 54\.dp\)\) \{\n
                        MarketBadge\(item, Modifier\.fillMaxSize\(\)\)\n
                        if \(item\.origin == DataOrigin\.LIVE\) \{.*?
                        \}\n
                    \}\n'''.replace("\n", ""),
    "                    MarketBadge(item, Modifier.size(if (compact) 45.dp else 54.dp))\n",
    u,
    count=1,
    flags=re.S,
)

badge_anchor = "                    MarketBadge(item, Modifier.size(if (compact) 45.dp else 54.dp))\n                    Spacer(Modifier.weight(1f))\n"
badge_replacement = """                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        MarketBadge(item, Modifier.size(if (compact) 45.dp else 54.dp))
                        Spacer(Modifier.width(if (compact) 4.dp else 6.dp))
                        Text(
                            text = compactPercent(item),
                            color = percentColor(item),
                            fontSize = if (compact) 9.sp else 10.sp,
                            lineHeight = if (compact) 10.sp else 11.sp,
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 1
                        )
                    }
                    Spacer(Modifier.weight(1f))
"""
if badge_anchor not in u:
    raise SystemExit("MarketBadge/Spacer anchor not found")
u = u.replace(badge_anchor, badge_replacement, 1)

code_block = """                        Text(
                            text = item.code,
                            color = ChandMuted,
                            fontSize = if (compact) 13.sp else 16.sp,
                            fontWeight = FontWeight.SemiBold,
                            textAlign = TextAlign.End,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
"""
code_replacement = """                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(5.dp)
                        ) {
                            MarketStatusLabel(item, compact)
                            Text(
                                text = item.code,
                                color = ChandMuted,
                                fontSize = if (compact) 13.sp else 16.sp,
                                fontWeight = FontWeight.SemiBold,
                                textAlign = TextAlign.End,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
"""
if code_block not in u:
    raise SystemExit("item.code block anchor not found")
u = u.replace(code_block, code_replacement, 1)

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
    val now = System.currentTimeMillis()
    val age = (now - item.sourceUpdatedAtMillis).coerceAtLeast(0L)

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
