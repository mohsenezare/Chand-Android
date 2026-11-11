package ir.personal.chand.data

import android.content.Context
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import okhttp3.Call
import okhttp3.Callback
import okhttp3.Response
import java.io.IOException
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.Locale
import java.util.UUID
import java.util.concurrent.TimeUnit

class MarketRepository(
    private val context: Context,
    private val httpClient: OkHttpClient = defaultHttpClient()
) {
    private val prefs = context.getSharedPreferences("chand_personal", Context.MODE_PRIVATE)
    private val arzDigitalClient = ArzDigitalPageClient(httpClient)
    private val legacyGlobalAliases = listOf(
        MarketDescriptor("gold_world", "OANDA:XAUUSD", "Gold Spot", "XAU/USD", "GOLD", MarketSource.ARZDIGITAL, "طلای جهانی", "دلار"),
        MarketDescriptor("silver", "OANDA:XAGUSD", "Silver Spot", "XAG/USD", "SILVER", MarketSource.ARZDIGITAL, "نقره جهانی", "دلار"),
        MarketDescriptor("brent", "TVC:UKOIL", "Brent Oil", "BRENT", "OIL", MarketSource.ARZDIGITAL, "انرژی جهانی", "دلار")
    )
    private val builtInDescriptors = DEFAULT_MARKET_DESCRIPTORS + ARZDIGITAL_MARKET_DESCRIPTORS + legacyGlobalAliases
    private val defaultById = builtInDescriptors.associateBy { it.id }
    private val defaultByKey = builtInDescriptors.associateBy { it.sourceKey }
    private val knownDescriptors = linkedMapOf<String, MarketDescriptor>()
    private val lastItems = linkedMapOf<String, MarketItem>()
    private val historyMutex = Mutex()
    private val historyCache = mutableMapOf<String, HistoryCacheEntry>()
    private val stockCatalogMutex = Mutex()
    private var stockCatalogLoadedAt = 0L
    private var stockCatalogCache: List<MarketDescriptor> = emptyList()
    private val resolvedTsetmcInsCodes = mutableMapOf<String, String>()
    private var lastCacheWriteAt = 0L
    private val retiredIds = linkedSetOf<String>()

    init {
        builtInDescriptors.forEach { knownDescriptors[it.id] = it }
        loadSelectedDescriptors().forEach { descriptor ->
            if (descriptor.id !in defaultById) knownDescriptors[descriptor.id] = descriptor
        }
        loadCached()?.items?.forEach { lastItems[it.id] = it.copy(origin = DataOrigin.CACHE) }
    }

    fun loadSettings(): UserSettings {
        val savedVisible = prefs.getString("visible_order_v3", null)
            ?: prefs.getString("visible_order_v2", null)
        val visible = savedVisible?.let { raw ->
            runCatching {
                val array = JSONArray(raw)
                buildList {
                    for (index in 0 until array.length()) {
                        array.optString(index).takeIf(String::isNotBlank)?.let(::add)
                    }
                }
            }.getOrNull()
        }?.let { if (it == LEGACY_DEFAULT_VISIBLE_IDS) DEFAULT_VISIBLE_IDS else it }
            ?: DEFAULT_VISIBLE_IDS

        return UserSettings(
            themeMode = runCatching {
                ThemeMode.valueOf(prefs.getString("theme_mode_v3", ThemeMode.DARK.name)!!)
            }.getOrDefault(ThemeMode.DARK),
            gridMode = prefs.getBoolean("grid_mode", true),
            showBuyPrice = false,
            visibleIds = visible
        )
    }

    fun saveSettings(settings: UserSettings) {
        prefs.edit()
            .putString("theme_mode_v3", settings.themeMode.name)
            .putBoolean("grid_mode", settings.gridMode)
            .putBoolean("show_buy", false)
            .putString("visible_order_v3", JSONArray(settings.visibleIds).toString())
            .apply()
    }

    fun rememberSelection(ids: List<String>, descriptors: Collection<MarketDescriptor>): List<String> {
        synchronized(knownDescriptors) {
            descriptors.filterNot { it.id in retiredIds }.forEach {
                knownDescriptors[it.id] = defaultById[it.id] ?: it
            }
        }
        // The order chosen by the user is authoritative. Do not regroup defaults,
        // provider types, or alphabetically sort after a save.
        val ordered = ids.asSequence()
            .filterNot { it in retiredIds }
            .distinct()
            .filter { id ->
                synchronized(knownDescriptors) {
                    (defaultById[id] ?: knownDescriptors[id])?.let(::isAllowedDescriptor) == true
                }
            }
            .toList()
        saveSelectedDescriptors(ordered)
        return ordered
    }

    fun knownDescriptors(): List<MarketDescriptor> = synchronized(knownDescriptors) {
        knownDescriptors.values.toList()
    }


    fun startTsetmcLiveStream(
        insCodes: List<String>,
        onState: (LiveConnectionState) -> Unit,
        onTicks: (List<StreamTick>) -> Unit
    ): TsetmcLiveClient {
        val liveClient = httpClient.newBuilder()
            .callTimeout(5, TimeUnit.SECONDS)
            .connectTimeout(4, TimeUnit.SECONDS)
            .readTimeout(4, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()
        return TsetmcLiveClient(liveClient, insCodes, onState, onTicks).also(TsetmcLiveClient::start)
    }


    suspend fun fetch(visibleIds: List<String>): MarketSnapshot = withContext(Dispatchers.IO) {
        val descriptors = resolveVisibleDescriptors(visibleIds)
        if (descriptors.isEmpty()) return@withContext emptySnapshot()

        coroutineScope {
            val receivedAt = System.currentTimeMillis()
            val previous = synchronized(lastItems) { lastItems.toMap() }
            val arzDescriptors = descriptors.filter { it.source == MarketSource.ARZDIGITAL }
            val tsetmcDescriptors = descriptors.filter { it.source == MarketSource.TSETMC }

            val arzRequest = async {
                if (arzDescriptors.isEmpty()) Result.success(emptyList())
                else requestResult { fetchArzDigitalItems(arzDescriptors, previous, receivedAt) }
            }
            val tsetmcRequest = async {
                if (tsetmcDescriptors.isEmpty()) Result.success(emptyList())
                else requestResult { fetchTsetmcItems(tsetmcDescriptors, previous, receivedAt) }
            }

            val freshItems = buildList {
                arzRequest.await().getOrNull()?.let(::addAll)
                tsetmcRequest.await().getOrNull()?.let(::addAll)
            }

            currentCoroutineContext().ensureActive()
            synchronized(lastItems) {
                freshItems.forEach { incoming ->
                    val current = lastItems[incoming.id]
                    val liveIsRecent = current?.origin == DataOrigin.LIVE &&
                        receivedAt - current.receivedAtMillis < LIVE_NETWORK_GRACE_MS
                    val incomingTime = incoming.sourceUpdatedAtMillis.takeIf { it > 0L }
                    val currentTime = current?.sourceUpdatedAtMillis?.takeIf { it > 0L }
                    val incomingIsNewer = when {
                        incomingTime == null -> current?.origin != DataOrigin.LIVE
                        currentTime == null -> true
                        else -> incomingTime >= currentTime
                    }
                    if (current == null || (!liveIsRecent && incomingIsNewer)) {
                        lastItems[incoming.id] = incoming
                    }
                }
            }

            val snapshot = snapshotOf(visibleIds, message = null)
            if (freshItems.isNotEmpty()) cacheSnapshotThrottled(snapshot)
            snapshot
        }
    }


    suspend fun fetchHistory(itemId: String, range: HistoryRange): HistorySeries =
        withContext(Dispatchers.IO) {
            var descriptor = synchronized(knownDescriptors) {
                knownDescriptors[itemId] ?: defaultById[itemId]
            } ?: return@withContext HistorySeries(range, emptyList(), "اطلاعات این مورد پیدا نشد")
            val inSession = synchronized(lastItems) { lastItems[itemId]?.history.orEmpty() }

            if (descriptor.source == MarketSource.TSETMC) {
                descriptor = resolveTsetmcDescriptor(descriptor) ?: descriptor
                val insCode = descriptor.sourceKey.takeIf { it.all(Char::isDigit) }
                if (insCode == null) {
                    return@withContext HistorySeries(range, MarketParsers.downsample(inSession, 360), "تاریخچه بورس در دسترس نیست")
                }
                return@withContext requestResult {
                    val top = when (range) {
                        HistoryRange.DAY -> 5
                        HistoryRange.WEEK -> 15
                        HistoryRange.MONTH -> 45
                        HistoryRange.YEAR -> 380
                        HistoryRange.FIVE_YEARS, HistoryRange.ALL -> 0
                    }
                    val rows = TsetmcProtocol.parseDailyList(
                        httpGet("$TSETMC_API/api/ClosingPrice/GetClosingPriceDailyList/$insCode/$top", 12_000)
                    )
                    val points = rows.asSequence()
                        .filter(TsetmcQuoteState::hasRealTrade)
                        .mapNotNull { q ->
                            TsetmcProtocol.toSourceTimestamp(q.dEven, q.hEven, fallbackToToday = false)
                                .takeIf { it > 0L }
                                ?.let { PricePoint(it, q.last) }
                        }
                        .sortedBy(PricePoint::timestampMillis)
                        .toList()
                    val merged = mergeHistory(points, inSession, range)
                    HistorySeries(range, if (range == HistoryRange.DAY) MarketParsers.downsample(merged, 360) else merged,
                        if (merged.isEmpty()) "تاریخچه‌ای از TSETMC دریافت نشد" else null)
                }.getOrElse {
                    HistorySeries(range, MarketParsers.downsample(inSession, 360),
                        if (inSession.isEmpty()) "دریافت نمودار بورس انجام نشد" else "نمایش تغییرات ثبت‌شده در این اجرا")
                }
            }

            if (descriptor.source == MarketSource.ARZDIGITAL) {
                return@withContext HistorySeries(
                    range,
                    MarketParsers.downsample(inSession, 360),
                    "برای ArzDigital فعلاً تغییرات زنده همین اجرا نمایش داده می‌شود"
                )
            }

            HistorySeries(
                range,
                MarketParsers.downsample(inSession, 360),
                if (inSession.isEmpty()) "ArzDigital page does not publish historical candles; no history is available yet."
                else "نمایش تاریخچه ثبت‌شده در همین اجرا"
            )
        }

    suspend fun searchMarkets(query: String, page: Int): CatalogPage = withContext(Dispatchers.IO) {
        val defaults = if (page == 1)
            (DEFAULT_MARKET_DESCRIPTORS + ARZDIGITAL_MARKET_DESCRIPTORS).filter { it.matches(query) }
        else emptyList()
        val remote = if (query.isNotBlank() && page == 1) requestResult {
            arzDigitalClient.searchCatalog(query, 100).map { entry ->
                MarketDescriptor(
                    id = "arz:${entry.slug}", sourceKey = entry.slug, name = entry.title,
                    code = entry.code.ifBlank { entry.slug.take(12).uppercase(Locale.US) },
                    symbol = "ASSET", source = MarketSource.ARZDIGITAL,
                    category = "بازارهای ArzDigital", unit = "دلار", valueScale = 1.0
                )
            }
        }.getOrDefault(emptyList()) else emptyList()
        val items = (defaults + remote).distinctBy(MarketDescriptor::id).filterNot { it.id in retiredIds }
        synchronized(knownDescriptors) { items.forEach { knownDescriptors[it.id] = it } }
        CatalogPage(items, false, null)
    }

    suspend fun searchStocks(query: String, page: Int): CatalogPage = withContext(Dispatchers.IO) {
        val normalized = query.trim()
        val catalog = requestResult { loadTsetmcCatalog(force = page == 1 && normalized.isBlank()) }
            .getOrDefault(stockCatalogCache)
        val localMatches = if (normalized.isBlank()) catalog else catalog.filter { it.matches(normalized) }
        val remoteMatches = if (normalized.isNotBlank() && page == 1) {
            requestResult { searchTsetmcRemote(normalized) }.getOrDefault(emptyList())
        } else emptyList()
        val combined = (localMatches + remoteMatches)
            .distinctBy(MarketDescriptor::id)
            .sortedWith(compareBy<MarketDescriptor> { it.code }.thenBy { it.name })
        val from = ((page - 1).coerceAtLeast(0)) * STOCK_PAGE_SIZE
        val to = (from + STOCK_PAGE_SIZE).coerceAtMost(combined.size)
        val items = if (from < combined.size) combined.subList(from, to) else emptyList()
        synchronized(knownDescriptors) { (combined + items).forEach { knownDescriptors[it.id] = it } }
        CatalogPage(items, to < combined.size, null)
    }

    suspend fun refreshIranMarketCatalogStrict(
        onProgress: (Int) -> Unit = {}
    ): List<MarketDescriptor> = withContext(Dispatchers.IO) {
        onProgress(20)
        val items = DEFAULT_MARKET_DESCRIPTORS.filterNot { it.id in retiredIds }
        require(items.isNotEmpty()) { "ArzDigital domestic market catalogue is empty" }
        onProgress(100)
        synchronized(knownDescriptors) { items.forEach { knownDescriptors[it.id] = it } }
        items
    }

    suspend fun refreshGlobalArzDigitalCatalogStrict(
        onProgress: (Int) -> Unit = {}
    ): List<MarketDescriptor> = withContext(Dispatchers.IO) {
        onProgress(15)
        val entries = arzDigitalClient.searchCatalog("", 160)
        val remote = entries.map { entry ->
            MarketDescriptor(
                id = "arz:${entry.slug}", sourceKey = entry.slug, name = entry.title,
                code = entry.code.ifBlank { entry.slug.take(12).uppercase(Locale.US) },
                symbol = "ASSET", source = MarketSource.ARZDIGITAL,
                category = "بازار جهانی", unit = "دلار", valueScale = 1.0
            )
        }
        val items = (ARZDIGITAL_MARKET_DESCRIPTORS + remote).distinctBy(MarketDescriptor::id)
        require(items.isNotEmpty()) { "ArzDigital public catalogue is empty" }
        onProgress(100)
        synchronized(knownDescriptors) { items.forEach { knownDescriptors[it.id] = it } }
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

    private suspend fun loadTsetmcCatalog(force: Boolean = false): List<MarketDescriptor> = stockCatalogMutex.withLock {
        val now = System.currentTimeMillis()
        if (!force && stockCatalogCache.isNotEmpty() && now - stockCatalogLoadedAt < STOCK_CATALOG_TTL_MS) {
            return@withLock stockCatalogCache
        }
        val quotes = requestResult {
            TsetmcProtocol.parseCdnMarketWatch(httpGet(TSETMC_MARKET_WATCH, 15_000))
        }.getOrNull()?.takeIf { it.isNotEmpty() } ?: requestResult {
            TsetmcProtocol.parseLegacyInit(httpGet(TSETMC_LEGACY_INIT, 15_000)).quotes
        }.getOrNull().orEmpty()
        if (quotes.isEmpty()) {
            if (stockCatalogCache.isNotEmpty()) return@withLock stockCatalogCache
            error("TSETMC market catalog unavailable")
        }
        val descriptors = quotes.mapNotNull(::descriptorFromTsetmcQuote)
            .distinctBy(MarketDescriptor::id)
            .sortedWith(compareBy<MarketDescriptor> { it.code }.thenBy { it.name })
        require(descriptors.isNotEmpty()) { "TSETMC returned no instruments" }
        stockCatalogCache = descriptors
        stockCatalogLoadedAt = now
        synchronized(knownDescriptors) { descriptors.forEach { knownDescriptors[it.id] = it } }
        descriptors
    }

    private suspend fun searchTsetmcRemote(query: String): List<MarketDescriptor> {
        val body = httpGet("$TSETMC_API/api/Instrument/GetInstrumentSearch/${encode(query.trim())}", 12_000)
        return TsetmcSearchParser.parse(body, query)
    }

    private fun descriptorFromTsetmcQuote(q: TsetmcQuoteState): MarketDescriptor? {
        if (q.insCode.isBlank() || q.symbol.isBlank()) return null
        return stockDescriptorFromFields(q.insCode, q.symbol, q.name, q.flow)
    }

    private fun stockDescriptorFromFields(insCode: String, ticker: String, company: String, flow: Int): MarketDescriptor {
        val category = when (flow) {
            1 -> "بورس ایران · بورس تهران"
            2 -> "بورس ایران · فرابورس"
            4 -> "بورس ایران · پایه"
            else -> "بورس ایران"
        }
        return MarketDescriptor(
            id = "tsetmc:$insCode",
            sourceKey = insCode,
            name = company.ifBlank { ticker },
            code = ticker,
            symbol = "TSE",
            source = MarketSource.TSETMC,
            category = category,
            unit = "ریال",
            valueScale = 1.0
        )
    }

    private suspend fun fetchArzDigitalItems(
        descriptors: List<MarketDescriptor>,
        previousItems: Map<String, MarketItem>,
        receivedAtMillis: Long
    ): List<MarketItem> = coroutineScope {
        descriptors.distinctBy(MarketDescriptor::sourceKey).map { descriptor ->
            async {
                requestResult {
                    val quote = arzDigitalClient.fetch(descriptor.sourceKey)
                    val price = when {
                        descriptor.code.equals("USD/JPY", ignoreCase = true) ->
                            quote.priceUsd?.takeIf { it > 0.0 }?.let { 1.0 / it }
                        descriptor.unit == "تومان" || descriptor.unit == "ریال" -> quote.priceToman
                        else -> quote.priceUsd
                    }?.takeIf { it.isFinite() && it > 0.0 }
                        ?: error("ArzDigital quote missing for ${descriptor.sourceKey}")
                    val previous = previousItems[descriptor.id]
                    val changePercent = quote.changePercent24h ?: previous?.changePercent ?: 0.0
                    val change = if (previous != null && previous.price > 0.0 && changePercent != 0.0)
                        price * changePercent / (100.0 + changePercent) else previous?.change ?: 0.0
                    val changed = previous == null || previous.price != price
                    MarketItem(
                        id = descriptor.id, name = descriptor.name, code = descriptor.code, symbol = descriptor.symbol,
                        price = price, change = change, changePercent = changePercent,
                        high = previous?.high?.takeIf { it > 0.0 } ?: price,
                        low = previous?.low?.takeIf { it > 0.0 } ?: price,
                        buy = previous?.buy?.takeIf { it > 0.0 } ?: price,
                        sell = previous?.sell?.takeIf { it > 0.0 } ?: price,
                        history = if (changed) MarketParsers.appendPoint(previous?.history.orEmpty(), quote.sourceUpdatedAtMillis.takeIf { it > 0L } ?: receivedAtMillis, price)
                            else previous?.history.orEmpty(),
                        sourceUpdatedAtMillis = quote.sourceUpdatedAtMillis.takeIf { it > 0L } ?: receivedAtMillis,
                        receivedAtMillis = receivedAtMillis,
                        origin = DataOrigin.NETWORK, isAvailable = true, source = MarketSource.ARZDIGITAL,
                        category = descriptor.category, unit = descriptor.unit
                    )
                }.getOrNull()
            }
        }.mapNotNull { it.await() }
    }

    private suspend fun fetchTsetmcItems(
        descriptors: List<MarketDescriptor>,
        previousItems: Map<String, MarketItem>,
        receivedAtMillis: Long
    ): List<MarketItem> = coroutineScope {
        descriptors.map { descriptor ->
            async {
                requestResult {
                    val resolved = resolveTsetmcDescriptor(descriptor) ?: error("TSETMC instrument not resolved")
                    val insCode = resolved.sourceKey
                    val current = requestResult {
                        TsetmcProtocol.parseClosingPriceInfo(
                            httpGet("$TSETMC_API/api/ClosingPrice/GetClosingPriceInfo/$insCode", 8_000)
                        )
                    }.getOrNull()
                    val previous = previousItems[descriptor.id] ?: previousItems[resolved.id]
                    val quote = when {
                        current?.hasRealTrade == true -> current
                        previous?.price?.takeIf { it > 0.0 } != null -> null
                        else -> requestResult {
                            TsetmcProtocol.parseDailyList(
                                httpGet("$TSETMC_API/api/ClosingPrice/GetClosingPriceDailyList/$insCode/15", 10_000)
                            ).firstOrNull { it.hasRealTrade }
                        }.getOrNull()
                    }

                    if (quote == null && previous != null && previous.price > 0.0) {
                        return@requestResult previous.copy(
                            id = descriptor.id,
                            name = resolved.name,
                            code = resolved.code,
                            symbol = resolved.symbol,
                            receivedAtMillis = receivedAtMillis,
                            origin = DataOrigin.CACHE,
                            isAvailable = true,
                            source = MarketSource.TSETMC,
                            category = resolved.category,
                            unit = resolved.unit
                        )
                    }
                    val q = quote ?: error("No real TSETMC last trade")
                    val price = q.last.takeIf { it > 0.0 } ?: error("Invalid TSETMC last trade")
                    val timestamp = TsetmcProtocol.toSourceTimestamp(q.dEven, q.hEven, fallbackToToday = current?.hasRealTrade == true)
                        .takeIf { it > 0L }
                        ?: previous?.sourceUpdatedAtMillis?.takeIf { it > 0L }
                        ?: receivedAtMillis
                    val yesterday = q.yesterday.takeIf { it > 0.0 }
                    val change = yesterday?.let { price - it } ?: previous?.change ?: 0.0
                    val percent = yesterday?.let { if (it != 0.0) change / it * 100.0 else 0.0 }
                        ?: previous?.changePercent ?: 0.0
                    val high = q.high.takeIf { it > 0.0 } ?: previous?.high?.takeIf { it > 0.0 } ?: price
                    val low = q.low.takeIf { it > 0.0 } ?: previous?.low?.takeIf { it > 0.0 } ?: price
                    val changed = previous == null || previous.price != price || previous.sourceUpdatedAtMillis != timestamp
                    MarketItem(
                        id = descriptor.id,
                        name = resolved.name,
                        code = resolved.code,
                        symbol = resolved.symbol,
                        price = price,
                        change = change,
                        changePercent = percent,
                        high = high,
                        low = low,
                        buy = q.bid?.takeIf { it > 0.0 } ?: previous?.buy?.takeIf { it > 0.0 } ?: price,
                        sell = q.ask?.takeIf { it > 0.0 } ?: previous?.sell?.takeIf { it > 0.0 } ?: price,
                        history = if (changed) MarketParsers.appendPoint(previous?.history.orEmpty(), timestamp, price)
                            else previous?.history.orEmpty(),
                        sourceUpdatedAtMillis = timestamp,
                        receivedAtMillis = receivedAtMillis,
                        origin = DataOrigin.NETWORK,
                        isAvailable = true,
                        source = MarketSource.TSETMC,
                        category = resolved.category,
                        unit = resolved.unit
                    )
                }.getOrNull()
            }
        }.mapNotNull { it.await() }
    }

    private suspend fun resolveTsetmcDescriptor(input: MarketDescriptor): MarketDescriptor? {
        if (input.source == MarketSource.TSETMC && input.sourceKey.all(Char::isDigit)) return input
        resolvedTsetmcInsCodes[input.id]?.let { ins ->
            synchronized(knownDescriptors) { knownDescriptors[input.id] }?.takeIf { it.sourceKey == ins }?.let { return it }
        }
        val query = input.code.takeIf { it.isNotBlank() && it != "—" } ?: input.sourceKey.ifBlank { input.name }
        val candidates = searchTsetmcRemote(query)
        val exact = candidates.firstOrNull { it.code.equals(input.code, ignoreCase = true) }
            ?: candidates.firstOrNull { it.code.equals(input.sourceKey, ignoreCase = true) }
            ?: candidates.firstOrNull { it.name == input.name }
            ?: candidates.firstOrNull()
            ?: return null
        val migrated = exact.copy(id = input.id)
        resolvedTsetmcInsCodes[input.id] = exact.sourceKey
        synchronized(knownDescriptors) { knownDescriptors[input.id] = migrated }
        return migrated
    }


    private fun isExpiredByDate(value: JSONObject): Boolean {
        val expiryKeys = listOf(
            "expires_at", "expired_at", "expiration_date", "expiry_date",
            "end_at", "end_date", "active_to", "date_to", "maturity_date"
        )
        val today = LocalDate.now(TEHRAN_ZONE)
        expiryKeys.forEach { key ->
            val raw = value.optString(key).trim()
            if (raw.isBlank()) return@forEach
            parseCatalogDate(raw)?.let { date ->
                if (date.isBefore(today)) return true
            }
        }
        return false
    }

    private fun parseCatalogDate(raw: String): LocalDate? {
        val normalized = raw.take(10).replace('/', '-')
        // Do not interpret a Jalali year as a Gregorian expiration.
        if ((normalized.substringBefore('-').toIntOrNull() ?: 0) < 1900) return null
        return try {
            LocalDate.parse(normalized, DateTimeFormatter.ISO_LOCAL_DATE)
        } catch (_: DateTimeParseException) {
            null
        }
    }


    private fun snapshotOf(visibleIds: List<String>, message: String? = null): MarketSnapshot {
        val descriptors = resolveVisibleDescriptors(visibleIds)
        val items = synchronized(lastItems) {
            descriptors.map { descriptor ->
                lastItems[descriptor.id]?.copy(symbol = descriptor.symbol) ?: unavailableItem(descriptor)
            }
        }
        val available = items.filter(MarketItem::isAvailable)
        val latest = available.maxOfOrNull(MarketItem::sourceUpdatedAtMillis) ?: 0L
        return MarketSnapshot(
            updatedAt = if (latest > 0L) Instant.ofEpochMilli(latest).toString() else "",
            items = items,
            isDemo = available.isEmpty(),
            message = message
        )
    }

    private fun emptySnapshot() = MarketSnapshot("", emptyList(), false)

    private fun resolveVisibleDescriptors(ids: List<String>): List<MarketDescriptor> =
        synchronized(knownDescriptors) {
            ids.distinct()
                .filterNot { it in retiredIds }
                .mapNotNull { defaultById[it] ?: knownDescriptors[it] }
                .filter(::isAllowedDescriptor)
        }

    /** Returns only ids that are still active and come from the two allowed providers. */
    fun sanitizeVisibleIds(ids: List<String>): List<String> = synchronized(knownDescriptors) {
        ids.distinct().filter { id ->
            id !in retiredIds && (defaultById[id] ?: knownDescriptors[id])?.let(::isAllowedDescriptor) == true
        }
    }

    private fun isAllowedDescriptor(descriptor: MarketDescriptor): Boolean =
        descriptor.source == MarketSource.ARZDIGITAL ||
            descriptor.source == MarketSource.TSETMC ||
            descriptor.source == MarketSource.ARZDIGITAL

    private fun unavailableItem(descriptor: MarketDescriptor) = MarketItem(
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

    private fun mergeHistory(
        source: List<PricePoint>,
        live: List<PricePoint>,
        range: HistoryRange
    ): List<PricePoint> {
        if (live.isEmpty()) return source
        val merged = (source + live)
            .associateBy(PricePoint::timestampMillis)
            .values
            .sortedBy(PricePoint::timestampMillis)
        return if (range == HistoryRange.DAY) MarketParsers.downsample(merged, 360) else merged
    }

    private suspend fun httpGet(url: String, timeoutMillis: Long): String {
        val request = Request.Builder()
            .url(url)
            .header("Accept", "application/json,text/plain,*/*")
            .header("Cache-Control", "no-cache")
            .header("User-Agent", HTTP_USER_AGENT)
            .build()
        val call = httpClient.newCall(request)
        call.timeout().timeout(timeoutMillis, TimeUnit.MILLISECONDS)
        return executeCancellable(call)
    }



    private suspend fun executeCancellable(call: Call): String = suspendCancellableCoroutine { continuation ->
        continuation.invokeOnCancellation { call.cancel() }
        call.enqueue(object : Callback {
            override fun onFailure(call: Call, error: IOException) {
                continuation.resumeWithException(error)
            }
            override fun onResponse(call: Call, response: Response) {
                val result = runCatching {
                    response.use {
                        check(it.isSuccessful) { "HTTP ${it.code}" }
                        it.body?.string()?.takeIf(String::isNotBlank) ?: error("Empty response")
                    }
                }
                result.fold({ continuation.resume(it) }, { continuation.resumeWithException(it) })
            }
        })
    }

    private suspend fun <T> requestResult(block: suspend () -> T): Result<T> = try {
        Result.success(block())
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: Exception) {
        Result.failure(error)
    }

    fun flushCache() {
        val items = synchronized(lastItems) { lastItems.values.filter(MarketItem::isAvailable) }
        if (items.isNotEmpty()) prefs.edit().putString(
            "cached_snapshot_v3", snapshotToJson(MarketSnapshot("", items, false)).toString()
        ).apply()
    }

    private fun jsonNumber(value: Any?): Double? = when (value) {
        null, JSONObject.NULL -> null
        is Number -> value.toDouble()
        else -> value.toString().replace(",", "").trim().toDoubleOrNull()
    }

    private fun cacheSnapshotThrottled(snapshot: MarketSnapshot) {
        val validItems = snapshot.items.filter(MarketItem::isAvailable)
        if (validItems.isEmpty()) return
        val now = System.currentTimeMillis()
        if (now - lastCacheWriteAt < 30_000L) return
        lastCacheWriteAt = now
        flushCache()
    }

    private fun loadCached(): MarketSnapshot? = prefs.getString("cached_snapshot_v3", null)
        ?.let { runCatching { parseCachedSnapshot(it) }.getOrNull() }

    private fun parseCachedSnapshot(body: String): MarketSnapshot {
        val root = JSONObject(body)
        val items = objectList(root.opt("items")).mapNotNull { value ->
            val id = value.optString("id")
            val descriptor = defaultById[id] ?: synchronized(knownDescriptors) { knownDescriptors[id] }
            val price = number(value, "price") ?: return@mapNotNull null
            if (price <= 0.0) return@mapNotNull null
            val history = objectList(value.opt("history")).mapNotNull { point ->
                val timestamp = point.optLong("timestamp", 0L)
                val historyValue = number(point, "value")
                if (timestamp > 0L && historyValue != null) PricePoint(timestamp, historyValue) else null
            }.ifEmpty {
                listOf(PricePoint(value.optLong("sourceUpdatedAtMillis", 0L), price))
                    .filter { it.timestampMillis > 0L }
            }
            MarketItem(
                id = id,
                name = value.optString("name", descriptor?.name.orEmpty()),
                code = value.optString("code", descriptor?.code.orEmpty()),
                symbol = descriptor?.symbol ?: value.optString("symbol", "•"),
                price = price,
                change = number(value, "change") ?: 0.0,
                changePercent = number(value, "changePercent") ?: 0.0,
                high = number(value, "high") ?: price,
                low = number(value, "low") ?: price,
                buy = number(value, "buy") ?: price,
                sell = number(value, "sell") ?: price,
                history = history,
                sourceUpdatedAtMillis = value.optLong("sourceUpdatedAtMillis", 0L),
                receivedAtMillis = value.optLong("receivedAtMillis", 0L),
                origin = DataOrigin.CACHE,
                isAvailable = true,
                source = runCatching { MarketSource.valueOf(value.optString("source")) }
                    .getOrDefault(descriptor?.source ?: MarketSource.ARZDIGITAL),
                category = value.optString("category", descriptor?.category.orEmpty()),
                unit = value.optString("unit", descriptor?.unit ?: "تومان")
            )
        }
        require(items.isNotEmpty()) { "Price cache is empty" }
        return MarketSnapshot(root.optString("updatedAt"), items, false)
    }

    private fun snapshotToJson(snapshot: MarketSnapshot): JSONObject = JSONObject().apply {
        put("updatedAt", snapshot.updatedAt)
        put("items", JSONArray().apply {
            snapshot.items.forEach { item ->
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
                    put("buy", item.buy)
                    put("sell", item.sell)
                    put("sourceUpdatedAtMillis", item.sourceUpdatedAtMillis)
                    put("receivedAtMillis", item.receivedAtMillis)
                    put("source", item.source.name)
                    put("category", item.category)
                    put("unit", item.unit)
                    put("history", JSONArray().apply {
                        item.history.forEach { point ->
                            put(JSONObject().put("timestamp", point.timestampMillis).put("value", point.value))
                        }
                    })
                })
            }
        })
    }

    private fun saveSelectedDescriptors(ids: List<String>) {
        val selected = synchronized(knownDescriptors) {
            ids.mapNotNull(knownDescriptors::get).filter { it.id !in defaultById }
        }
        prefs.edit().putString(
            "selected_descriptors_v4",
            JSONArray().apply {
                selected.forEach { descriptor ->
                    put(JSONObject().apply {
                        put("id", descriptor.id)
                        put("sourceKey", descriptor.sourceKey)
                        put("name", descriptor.name)
                        put("code", descriptor.code)
                        put("symbol", descriptor.symbol)
                        put("source", descriptor.source.name)
                        put("category", descriptor.category)
                        put("unit", descriptor.unit)
                        put("valueScale", descriptor.valueScale)
                    })
                }
            }.toString()
        ).apply()
    }

    private fun loadSelectedDescriptors(): List<MarketDescriptor> {
        val raw = prefs.getString("selected_descriptors_v4", null)
            ?: prefs.getString("selected_descriptors_v3", null)
            ?: prefs.getString("selected_descriptors_v2", null)
            ?: return emptyList()
        return runCatching {
            objectList(JSONArray(raw)).mapNotNull { value ->
                val id = value.optString("id")
                val sourceKey = value.optString("sourceKey")
                val name = value.optString("name")
                if (id.isBlank() || sourceKey.isBlank() || name.isBlank()) return@mapNotNull null
                val oldUnit = value.optString("unit")
                val category = value.optString("category")
                val rawSource = value.optString("source")
                var source = runCatching { MarketSource.valueOf(rawSource) }.getOrDefault(MarketSource.ARZDIGITAL)
                var migratedSourceKey = sourceKey
                var migratedUnit = oldUnit
                var scale = value.optDouble("valueScale", 1.0)

                // v3 used ArzDigital for Tehran stocks. Keep the user's id/order but migrate
                // those descriptors to TSETMC; the InsCode is resolved on first refresh.
                if (source == MarketSource.ARZDIGITAL && (category.contains("بورس ایران") || category.contains("سهام"))) {
                    source = MarketSource.TSETMC
                    migratedSourceKey = value.optString("code").takeIf { it.isNotBlank() && it != "—" } ?: sourceKey
                    migratedUnit = "ریال"
                    scale = 1.0
                } else if (source == MarketSource.ARZDIGITAL && oldUnit == "ریال" && !category.contains("بورس")) {
                    migratedUnit = "تومان"
                    scale = 0.1
                }
                MarketDescriptor(
                    id = id,
                    sourceKey = migratedSourceKey,
                    name = name,
                    code = value.optString("code", "—"),
                    symbol = value.optString("symbol", if (source == MarketSource.TSETMC) "TSE" else "•"),
                    source = source,
                    category = if (source == MarketSource.TSETMC && category.isBlank()) "بورس ایران" else category,
                    unit = migratedUnit,
                    valueScale = scale
                )
            }
        }.getOrDefault(emptyList())
    }

    private fun MarketDescriptor.matches(raw: String): Boolean {
        val query = raw.trim().lowercase(Locale.ROOT)
        return query.isEmpty() || name.lowercase(Locale.ROOT).contains(query) ||
            code.lowercase(Locale.ROOT).contains(query) ||
            category.lowercase(Locale.ROOT).contains(query)
    }

    private fun symbolFor(type: String, category: String, title: String): String {
        val value = "$type $category $title"
        return when {
            title.contains("یورو") -> "EUR"
            title.contains("دلار آمریکا") -> "USD"
            title.contains("پوند") -> "GBP"
            title.contains("ین ژاپن") -> "JPY"
            title.contains("یوان") -> "CNY"
            title.contains("درهم") -> "AED"
            title.contains("لیر") -> "TRY"
            title.contains("روبل") -> "RUB"
            title.contains("روپیه") -> "INR"
            title.contains("بیت کوین") || title.contains("بیت‌کوین") -> "BTC"
            title.contains("اتریوم") -> "ETH"
            title.contains("تتر") -> "USDT"
            value.contains("ارز دیجیتال") || type.contains("crypto") -> "CRYPTO"
            value.contains("طلا") || value.contains("سکه") -> "GOLD"
            value.contains("نقره") -> "SILVER"
            value.contains("نفت") || value.contains("انرژی") -> "OIL"
            value.contains("ارز") -> "FX"
            value.contains("بورس") || value.contains("سهام") || value.contains("صندوق") -> "TSE"
            value.contains("خودرو") -> "CAR"
            else -> "MARKET"
        }
    }

    private fun number(value: JSONObject, key: String): Double? {
        val raw = value.opt(key) ?: return null
        return when (raw) {
            is Number -> raw.toDouble()
            is JSONObject -> number(raw, "value")
            else -> raw.toString().replace(",", "").trim().toDoubleOrNull()
        }
    }

    private fun firstString(objects: List<JSONObject>, vararg keys: String): String? {
        objects.forEach { value ->
            keys.forEach { key -> value.optString(key).takeIf(String::isNotBlank)?.let { return it } }
        }
        return null
    }

    private fun firstNumber(objects: List<JSONObject>, vararg keys: String): Double? {
        objects.forEach { value -> keys.forEach { key -> number(value, key)?.let { return it } } }
        return null
    }

    private fun objectList(value: Any?): List<JSONObject> = when (value) {
        is JSONArray -> buildList {
            for (index in 0 until value.length()) value.optJSONObject(index)?.let(::add)
        }
        is JSONObject -> {
            val isRecord = listOf("id", "name", "title", "instrument", "closingPrice", "sourceKey", "price")
                .any(value::has)
            if (isRecord) listOf(value) else buildList {
                val keys = value.keys()
                while (keys.hasNext()) value.optJSONObject(keys.next())?.let(::add)
            }
        }
        else -> emptyList()
    }

    private fun firstPresent(value: JSONObject, vararg keys: String): Any? {
        keys.forEach { key -> value.opt(key)?.takeUnless { it == JSONObject.NULL }?.let { return it } }
        return null
    }

    private fun encode(value: String): String = URLEncoder.encode(value, StandardCharsets.UTF_8.name())

    private data class CatalogModulePage(val items: List<MarketDescriptor>, val hasMore: Boolean)
    private data class HistoryCacheEntry(val loadedAtMillis: Long, val points: List<PricePoint>)

    companion object {
        private const val STOCK_CATALOG_TTL_MS = 2 * 60_000L
        private const val STOCK_PAGE_SIZE = 100
        private const val TSETMC_API = "https://cdn.tsetmc.com"
        private const val TSETMC_LEGACY_INIT = "https://old.tsetmc.com/tsev2/data/MarketWatchInit.aspx?h=0&r=0"
        private const val TSETMC_MARKET_WATCH =
            "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&industrialGroup=&" +
                "paperTypes%5B0%5D=1&paperTypes%5B1%5D=2&paperTypes%5B2%5D=3&" +
                "paperTypes%5B3%5D=4&paperTypes%5B4%5D=5&paperTypes%5B5%5D=6&" +
                "paperTypes%5B6%5D=7&paperTypes%5B7%5D=8&paperTypes%5B8%5D=9&" +
                "showTraded=false&withBestLimits=true&hEven=0&RefID=0"
        private const val LIVE_NETWORK_GRACE_MS = 5_000L
        private val TEHRAN_ZONE = ZoneId.of("Asia/Tehran")
        private const val HTTP_USER_AGENT =
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Mobile Safari/537.36 Chand/4.0"

        fun defaultHttpClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(8, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .writeTimeout(10, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()
    }
}
