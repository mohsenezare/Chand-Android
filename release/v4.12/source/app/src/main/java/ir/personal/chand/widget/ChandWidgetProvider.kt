package ir.personal.chand.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import ir.personal.chand.MainActivity
import ir.personal.chand.R
import ir.personal.chand.data.DEFAULT_MARKET_DESCRIPTORS
import ir.personal.chand.data.DEFAULT_VISIBLE_IDS
import ir.personal.chand.data.DataOrigin
import ir.personal.chand.data.MarketItem
import ir.personal.chand.data.MarketRepository
import ir.personal.chand.data.MarketSource
import ir.personal.chand.ui.MarketFormatting
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

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

object WidgetUpdater {
    private const val ITEMS_KEY = "items_v3"
    private const val PERIODIC_WORK = "chand-widget-periodic-v3"
    private const val IMMEDIATE_WORK = "chand-widget-now-v3"
    private const val OLD_PERIODIC_WORK = "chand-widget-periodic-v2"
    private const val OLD_IMMEDIATE_WORK = "chand-widget-now-v2"
    private var lastWidgetCacheWriteAt = 0L

    fun schedule(context: Context) {
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
                            source = MarketSource.ARZDIGITAL,
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
