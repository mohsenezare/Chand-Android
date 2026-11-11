package ir.personal.chand.data

import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.Closeable
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit
import kotlin.math.min

/**
 * Near-real-time TSETMC feed.
 *
 * TSETMC does not expose a documented public websocket. The official market-watch
 * protocol is incremental: MarketWatchInit establishes a baseline and RefID/hEven,
 * then MarketWatchPlus returns only changes. We poll that delta endpoint quickly
 * while the app is foregrounded. If the legacy delta surface is unavailable, we
 * fall back to the current CDN JSON market watch and emit only changed selected rows.
 */
class TsetmcLiveClient(
    private val httpClient: OkHttpClient,
    requestedInsCodes: List<String>,
    private val onState: (LiveConnectionState) -> Unit,
    private val onTicks: (List<StreamTick>) -> Unit
) : Closeable {
    private val requested = requestedInsCodes.map(String::trim)
        .filter { it.matches(Regex("\\d{8,24}")) }
        .distinct()
        .toHashSet()
    private val scheduler = Executors.newSingleThreadScheduledExecutor { task ->
        Thread(task, "chand-tsetmc-live").apply { isDaemon = true }
    }
    private val states = linkedMapOf<String, TsetmcQuoteState>()

    @Volatile private var closed = false
    private var future: ScheduledFuture<*>? = null
    private var initialized = false
    private var useLegacy = true
    private var legacyHostIndex = 0
    private var refId = 0L
    private var hEven = 0
    private var consecutiveFailures = 0

    fun start() {
        if (requested.isEmpty() || closed || future != null) return
        onState(LiveConnectionState.CONNECTING)
        future = scheduler.scheduleWithFixedDelay(::cycle, 0L, POLL_INTERVAL_MS, TimeUnit.MILLISECONDS)
    }

    private fun cycle() {
        if (closed) return
        try {
            if (!initialized) initializeBaseline() else if (useLegacy) pollLegacyDelta() else pollCdnDiff()
            consecutiveFailures = 0
            onState(LiveConnectionState.POLLING)
        } catch (_: Exception) {
            consecutiveFailures++
            if (useLegacy && consecutiveFailures >= 2) {
                // Try the other legacy host once, then move to CDN JSON diff mode.
                if (legacyHostIndex + 1 < LEGACY_HOSTS.size) {
                    legacyHostIndex++
                    initialized = false
                } else {
                    useLegacy = false
                    initialized = false
                }
            } else if (!useLegacy && consecutiveFailures >= 8) {
                onState(LiveConnectionState.OFFLINE)
            }
        }
    }

    private fun initializeBaseline() {
        if (useLegacy) {
            val body = get("${LEGACY_HOSTS[legacyHostIndex]}/tsev2/data/MarketWatchInit.aspx?h=0&r=0")
            val init = TsetmcProtocol.parseLegacyInit(body)
            states.clear()
            init.quotes.forEach { states[it.insCode] = it }
            refId = init.refId
            hEven = init.maxHEven
            initialized = true
            return
        }

        val quotes = TsetmcProtocol.parseCdnMarketWatch(get(CDN_MARKET_WATCH))
        require(quotes.isNotEmpty()) { "Empty TSETMC CDN market watch" }
        states.clear()
        quotes.forEach { states[it.insCode] = it }
        hEven = quotes.maxOfOrNull { it.hEven } ?: 0
        initialized = true
    }

    private fun pollLegacyDelta() {
        val roundedH = 5 * (hEven / 5)
        val roundedR = 25L * (refId / 25L)
        val body = get("${LEGACY_HOSTS[legacyHostIndex]}/tsev2/data/MarketWatchPlus.aspx?h=$roundedH&r=$roundedR")
        val plus = TsetmcProtocol.parseLegacyPlus(body)
        if (plus.refId > 0L) refId = plus.refId
        if (plus.maxHEven > 0) hEven = maxOf(hEven, plus.maxHEven)
        emitChanged(plus.updates, sourceHasExactDate = false)
    }

    private fun pollCdnDiff() {
        // The CDN endpoint supports hEven/RefID parameters but deployments have not
        // always returned a usable RefID envelope. Fetching the market-watch snapshot
        // and diffing locally is the safest fallback and is still much lighter than
        // per-symbol polling.
        val quotes = TsetmcProtocol.parseCdnMarketWatch(get(CDN_MARKET_WATCH))
        require(quotes.isNotEmpty()) { "Empty TSETMC CDN market watch" }
        emitChanged(quotes, sourceHasExactDate = true)
        hEven = maxOf(hEven, quotes.maxOfOrNull { it.hEven } ?: 0)
    }

    private fun emitChanged(updates: List<TsetmcQuoteState>, sourceHasExactDate: Boolean) {
        if (updates.isEmpty()) return
        val ticks = mutableListOf<StreamTick>()
        updates.forEach { update ->
            val before = states[update.insCode]
            val merged = before?.merge(update) ?: update
            states[update.insCode] = merged
            if (update.insCode !in requested) return@forEach

            val changed = before == null || merged.last != before.last || merged.hEven != before.hEven ||
                merged.trades != before.trades || merged.volume != before.volume
            if (!changed || !merged.hasRealTrade) return@forEach

            val ts = TsetmcProtocol.toSourceTimestamp(
                dEven = if (sourceHasExactDate) merged.dEven else 0,
                hEven = merged.hEven,
                fallbackToToday = true
            )
            val change = if (merged.yesterday > 0.0) merged.last - merged.yesterday else 0.0
            val percent = if (merged.yesterday > 0.0) change / merged.yesterday * 100.0 else 0.0
            ticks += StreamTick(
                sourceKey = merged.insCode,
                itemId = "tsetmc:${merged.insCode}",
                price = merged.last,
                high = merged.high.takeIf { it > 0.0 } ?: merged.last,
                low = merged.low.takeIf { it > 0.0 } ?: merged.last,
                open = merged.first.takeIf { it > 0.0 } ?: merged.last,
                change = change,
                changePercent = percent,
                direction = when {
                    change > 0.0 -> "high"
                    change < 0.0 -> "low"
                    else -> "same"
                },
                sourceUpdatedAtMillis = ts,
                bid = merged.bid,
                ask = merged.ask
            )
        }
        if (ticks.isNotEmpty()) onTicks(ticks)
    }

    private fun get(url: String): String {
        val request = Request.Builder()
            .url(url)
            .header("Accept", "application/json,text/plain,*/*")
            .header("Cache-Control", "no-cache")
            .header("User-Agent", USER_AGENT)
            .build()
        return httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) error("HTTP ${response.code}")
            response.body?.string()?.takeIf(String::isNotBlank) ?: error("Empty response")
        }
    }

    override fun close() {
        closed = true
        future?.cancel(true)
        future = null
        scheduler.shutdownNow()
    }

    companion object {
        private const val POLL_INTERVAL_MS = 650L
        private val LEGACY_HOSTS = listOf("https://old.tsetmc.com", "https://www.tsetmc.com")
        private const val CDN_MARKET_WATCH =
            "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&industrialGroup=&" +
                "paperTypes%5B0%5D=1&paperTypes%5B1%5D=2&paperTypes%5B2%5D=3&" +
                "paperTypes%5B3%5D=4&paperTypes%5B4%5D=5&paperTypes%5B5%5D=6&" +
                "paperTypes%5B6%5D=7&paperTypes%5B7%5D=8&paperTypes%5B8%5D=9&" +
                "showTraded=false&withBestLimits=false&hEven=0&RefID=0"
        private const val USER_AGENT =
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Mobile Safari/537.36 Chand/4.0"
    }
}
