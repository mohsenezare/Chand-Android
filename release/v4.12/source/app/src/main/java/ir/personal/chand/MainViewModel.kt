package ir.personal.chand

import android.app.Application
import android.os.SystemClock
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import ir.personal.chand.data.CatalogSource
import ir.personal.chand.data.DEFAULT_MARKET_DESCRIPTORS
import ir.personal.chand.data.HistoryRange
import ir.personal.chand.data.LiveConnectionState
import ir.personal.chand.data.MarketDescriptor
import ir.personal.chand.data.MarketItem
import ir.personal.chand.data.MarketRepository
import ir.personal.chand.data.MarketSnapshot
import ir.personal.chand.data.MarketSource
import ir.personal.chand.data.PricePoint
import ir.personal.chand.data.ThemeMode
import ir.personal.chand.data.TsetmcLiveClient
import ir.personal.chand.data.UserSettings
import ir.personal.chand.widget.WidgetUpdater
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONArray
import org.json.JSONObject

data class ChartUiState(
    val itemId: String? = null,
    val range: HistoryRange = HistoryRange.DAY,
    val loading: Boolean = false,
    val points: List<PricePoint> = emptyList(),
    val message: String? = null
)

data class CatalogUpdateUiState(
val running: Boolean = false,
val progress: Int = 0,
val success: Boolean? = null,
val message: String? = null
)

data class ChandUiState(
    val loading: Boolean = true,
    val snapshot: MarketSnapshot? = null,
    val settings: UserSettings = UserSettings(),
    val connectionState: LiveConnectionState = LiveConnectionState.CONNECTING,
    val chart: ChartUiState = ChartUiState(),
    val catalogItems: List<MarketDescriptor> = DEFAULT_MARKET_DESCRIPTORS,
    val catalogSource: CatalogSource = CatalogSource.MARKETS,
    val catalogQuery: String = "",
    val catalogLoading: Boolean = false,
    val catalogHasMore: Boolean = true,
    val catalogMessage: String? = null,
val iranMarketUpdate: CatalogUpdateUiState = CatalogUpdateUiState(),
val iranStockUpdate: CatalogUpdateUiState = CatalogUpdateUiState(),
val globalMarketUpdate: CatalogUpdateUiState = CatalogUpdateUiState(),
val pullRefreshing: Boolean = false
) {
    val visibleItems: List<MarketItem>
        get() {
            val byId = snapshot?.items.orEmpty().associateBy(MarketItem::id)
            return settings.visibleIds.mapNotNull(byId::get)
        }
}

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = MarketRepository(application)
private val catalogCachePrefs = application.getSharedPreferences("chand_catalog_updates_v484", 0)
private var savedIranMarketCatalog = loadSavedCatalog("iran_market", MarketSource.ARZDIGITAL)
private var savedIranStockCatalog = loadSavedCatalog("iran_stock", MarketSource.TSETMC)
private var savedGlobalMarketCatalog = loadSavedCatalog("global_market", MarketSource.ARZDIGITAL)
    private val _uiState = MutableStateFlow(ChandUiState(settings = repository.loadSettings()))
    val uiState: StateFlow<ChandUiState> = _uiState.asStateFlow()
    private val refreshSignal = Channel<Unit>(Channel.CONFLATED)
    private val descriptorCache = linkedMapOf<String, MarketDescriptor>()
    private var pollingJob: Job? = null
    private var catalogJob: Job? = null
    private var historyJob: Job? = null
    private var pullRefreshJob: Job? = null
    private val refreshMutex = Mutex()
    
    
    private var tsetmcLiveClient: TsetmcLiveClient? = null
    private var catalogPage = 1

    init {
WidgetUpdater.schedule(application)
repository.knownDescriptors().forEach { descriptorCache[it.id] = it }
savedIranMarketCatalog.forEach { descriptorCache[it.id] = it }
savedIranStockCatalog.forEach { descriptorCache[it.id] = it }
savedGlobalMarketCatalog.forEach { descriptorCache[it.id] = it }
}

    fun startPolling() {
        if (pollingJob?.isActive == true) return
        pollingJob = viewModelScope.launch {
            var firstLoad = _uiState.value.snapshot == null
            var streamsStarted = false
            while (isActive) {
                val startedAt = SystemClock.elapsedRealtime()
                try {
                    refreshOnce(showInitialLoading = firstLoad)
                    // A first network reconciliation resolves migrated TSETMC tickers to
                    // stable InsCodes. Start provider streams only after that resolution.
                    repository.knownDescriptors().forEach { descriptorCache[it.id] = it }
                    if (!streamsStarted) {
                        startProviderStreams()
                        streamsStarted = true
                    }
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (_: Exception) {
                    _uiState.update { current ->
                        current.copy(
                            loading = false,
                            connectionState = if (current.connectionState == LiveConnectionState.LIVE) {
                                LiveConnectionState.LIVE
                            } else LiveConnectionState.OFFLINE
                        )
                    }
                    if (!streamsStarted) {
                        startProviderStreams()
                        streamsStarted = true
                    }
                }
                firstLoad = false
                val interval = when {
                    hasVisibleTsetmc() -> TSETMC_RECONCILE_INTERVAL_MS
                    hasVisibleArzDigital() -> LIVE_RECONCILE_INTERVAL_MS
                    _uiState.value.connectionState == LiveConnectionState.CONNECTING -> CONNECTING_INTERVAL_MS
                    else -> FALLBACK_INTERVAL_MS
                }
                val remaining = (interval - (SystemClock.elapsedRealtime() - startedAt)).coerceAtLeast(0L)
                if (remaining > 0L) withTimeoutOrNull(remaining) { refreshSignal.receive() }
                else delay(25L)
            }
        }
    }

    fun stopPolling() {
        pollingJob?.cancel()
        pollingJob = null
                tsetmcLiveClient?.close()
        tsetmcLiveClient = null
        repository.flushCache()
    }

    fun refresh() {
        refreshSignal.trySend(Unit)
        if (pollingJob?.isActive != true) startPolling()
    }

    fun pullToRefresh() {
        if (pullRefreshJob?.isActive == true) return
        _uiState.update { it.copy(pullRefreshing = true) }
        pullRefreshJob = viewModelScope.launch {
            val startedAt = System.currentTimeMillis()
            try {
                refreshOnce(showInitialLoading = false)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                // Existing valid prices stay visible if the manual refresh fails.
            } finally {
                val elapsed = System.currentTimeMillis() - startedAt
                val minimumVisibleMs = 900L
                if (elapsed < minimumVisibleMs) {
                    delay(minimumVisibleMs - elapsed)
                }
                _uiState.update { it.copy(pullRefreshing = false) }
            }
        }
    }

    fun showChart(itemId: String, range: HistoryRange = HistoryRange.DAY) {
        loadHistory(itemId, range)
    }

    fun changeChartRange(range: HistoryRange) {
        val itemId = _uiState.value.chart.itemId ?: return
        loadHistory(itemId, range)
    }

    fun clearChart() {
        historyJob?.cancel()
        historyJob = null
        _uiState.update { it.copy(chart = ChartUiState()) }
    }

    fun loadCatalog(source: CatalogSource, query: String = "", loadMore: Boolean = false) {
        val normalizedQuery = query.trim()
        val current = _uiState.value
        val sameSearch = current.catalogSource == source && current.catalogQuery == normalizedQuery
        if (loadMore && (!sameSearch || !current.catalogHasMore || current.catalogLoading)) return
        catalogPage = if (loadMore) catalogPage + 1 else 1
        catalogJob?.cancel()
        _uiState.update {
            it.copy(
                catalogSource = source,
                catalogQuery = normalizedQuery,
                catalogLoading = true,
                catalogMessage = null,
                catalogItems = if (loadMore && sameSearch) it.catalogItems else emptyList()
            )
        }
        catalogJob = viewModelScope.launch {
            val page = when (source) {
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
val merged = if (loadMore) latest.catalogItems + currentItems else currentItems
            _uiState.update {
                it.copy(
                    catalogItems = merged.distinctBy(MarketDescriptor::id),
                    catalogLoading = false,
                    catalogHasMore = page.hasMore,
                    catalogMessage = page.message
                )
            }
        }
    }

    fun updateIranMarketCatalog() {
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
label = "بازار جهانی (ArzDigital)",
current = { _uiState.value.globalMarketUpdate },
set = { value -> _uiState.update { it.copy(globalMarketUpdate = value) } },
saved = { savedGlobalMarketCatalog },
save = { items ->
savedGlobalMarketCatalog = items
saveCatalog("global_market", items)
},
fetch = { progress -> repository.refreshGlobalArzDigitalCatalogStrict(progress) }
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

raw.contains("ArzDigital", ignoreCase = true) ->
"دلیل: ArzDigital فهرست معتبر بازار را برنگرداند. راه‌حل: اتصال اینترنت/VPN را بررسی کنید و دوباره تلاش کنید."

raw.contains("ArzDigital", ignoreCase = true) ->
"دلیل: ArzDigital پاسخ معتبر برای بازار جهانی نداد. راه‌حل: اینترنت/VPN را بررسی کنید و چند لحظه بعد دوباره تلاش کنید."

else ->
"دلیل: " + raw.ifBlank { "ارتباط معتبر با منبع برقرار نشد" }.take(150) +
". راه‌حل: اینترنت را بررسی کنید و دوباره آپدیت بگیرید."
}
}

fun setGridMode(enabled: Boolean) = updateSettings { copy(gridMode = enabled) }

    fun moveVisibleItem(itemId: String, delta: Int) {
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


    fun setTheme(mode: ThemeMode) = updateSettings { copy(themeMode = mode) }

    fun setVisibleIds(ids: List<String>) {
        val ordered = repository.rememberSelection(ids, descriptorCache.values)
        updateSettings { copy(visibleIds = ordered) }
        if (_uiState.value.chart.itemId !in ordered) clearChart()
        if (pollingJob?.isActive == true) {
            stopPolling()
            startPolling()
        }
    }


    private fun startProviderStreams() { /* MarketRepository refreshes ArzDigital and TSETMC over HTTP. */ }

    private fun publishLiveSnapshot(snapshot: MarketSnapshot, providerState: LiveConnectionState) {
        _uiState.update { current ->
            val selected = current.chart.itemId
            val item = selected?.let { id -> snapshot.items.firstOrNull { it.id == id } }
            val chart = if (current.chart.range == HistoryRange.DAY && item != null) {
                current.chart.copy(points = item.history, message = null)
            } else current.chart
            current.copy(
                loading = false,
                snapshot = snapshot,
                connectionState = if (providerState == LiveConnectionState.LIVE || current.connectionState == LiveConnectionState.LIVE) {
                    LiveConnectionState.LIVE
                } else providerState,
                chart = chart
            )
        }
        WidgetUpdater.updateAll(getApplication(), snapshot.items)
    }

    private fun loadHistory(itemId: String, range: HistoryRange) {
        if (itemId !in _uiState.value.settings.visibleIds) return
        historyJob?.cancel()
        val immediate = _uiState.value.snapshot?.items
            ?.firstOrNull { it.id == itemId }
            ?.history.orEmpty()
        _uiState.update {
            it.copy(
                chart = ChartUiState(
                    itemId = itemId,
                    range = range,
                    loading = true,
                    points = if (range == HistoryRange.DAY) immediate else emptyList()
                )
            )
        }
        historyJob = viewModelScope.launch {
            val series = repository.fetchHistory(itemId, range)
            if (_uiState.value.chart.itemId != itemId || _uiState.value.chart.range != range) return@launch
            _uiState.update {
                it.copy(
                    chart = it.chart.copy(
                        loading = false,
                        points = series.points,
                        message = series.message
                    )
                )
            }
        }
    }

    private suspend fun refreshOnce(showInitialLoading: Boolean) {
        refreshMutex.withLock {
            refreshOnceInternal(showInitialLoading)
        }
    }

    private suspend fun refreshOnceInternal(showInitialLoading: Boolean) {
        if (showInitialLoading) _uiState.update { it.copy(loading = true) }
        val visibleIds = _uiState.value.settings.visibleIds
        val refreshStartedAt = System.currentTimeMillis()
        val snapshot = repository.fetch(visibleIds)
        currentCoroutineContext().ensureActive()
        if (_uiState.value.settings.visibleIds != visibleIds) return
        val sanitizedVisibleIds = repository.sanitizeVisibleIds(visibleIds)
        if (sanitizedVisibleIds != visibleIds) {
            val cleaned = _uiState.value.settings.copy(visibleIds = sanitizedVisibleIds)
            repository.saveSettings(cleaned)
        }
        _uiState.update { current ->
            val selected = current.chart.itemId
            val selectedItem = selected?.let { id -> snapshot.items.firstOrNull { it.id == id } }
            val chart = if (current.chart.range == HistoryRange.DAY && selectedItem != null &&
                selectedItem.history.isNotEmpty()
            ) current.chart.copy(points = selectedItem.history) else current.chart
            current.copy(
                loading = false,
                snapshot = snapshot,
                connectionState = when {
                    current.connectionState == LiveConnectionState.LIVE -> LiveConnectionState.LIVE
                    snapshot.items.any { it.isAvailable && it.receivedAtMillis >= refreshStartedAt } -> LiveConnectionState.POLLING
                    else -> LiveConnectionState.OFFLINE
                },
                settings = if (sanitizedVisibleIds != visibleIds) {
                    current.settings.copy(visibleIds = sanitizedVisibleIds)
                } else current.settings,
                chart = chart
            )
        }
        WidgetUpdater.updateAll(getApplication(), snapshot.items)
    }


    private fun hasVisibleArzDigital(): Boolean {
        val ids = _uiState.value.settings.visibleIds.toHashSet()
        return descriptorCache.values.any { it.id in ids && it.source == MarketSource.ARZDIGITAL }
    }

    private fun hasVisibleTsetmc(): Boolean {
        val ids = _uiState.value.settings.visibleIds.toHashSet()
        return descriptorCache.values.any { it.id in ids && it.source == MarketSource.TSETMC }
    }

    private fun updateSettings(block: UserSettings.() -> UserSettings) {
        val settings = _uiState.value.settings.block()
        repository.saveSettings(settings)
        _uiState.update { it.copy(settings = settings) }
    }

    override fun onCleared() {
        stopPolling()
        super.onCleared()
    }

    private companion object {
        // Provider streams/deltas are primary. These intervals are only safety
        // reconciliations so HTTP snapshots cannot masquerade as live ticks.
        const val TSETMC_RECONCILE_INTERVAL_MS = 15_000L
        const val FALLBACK_INTERVAL_MS = 5_000L
        const val CONNECTING_INTERVAL_MS = 3_000L
        const val LIVE_RECONCILE_INTERVAL_MS = 30_000L
    }
}
