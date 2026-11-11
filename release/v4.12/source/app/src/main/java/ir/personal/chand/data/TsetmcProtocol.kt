package ir.personal.chand.data

import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime

internal data class TsetmcQuoteState(
    val insCode: String,
    val isin: String = "",
    val symbol: String = "",
    val name: String = "",
    val dEven: Int = 0,
    val hEven: Int = 0,
    val first: Double = 0.0,
    val closing: Double = 0.0,
    val last: Double = 0.0,
    val trades: Double = 0.0,
    val volume: Double = 0.0,
    val value: Double = 0.0,
    val low: Double = 0.0,
    val high: Double = 0.0,
    val yesterday: Double = 0.0,
    val flow: Int = 0,
    val bid: Double? = null,
    val ask: Double? = null
) {
    val hasRealTrade: Boolean get() = last > 0.0 && trades > 0.0

    fun merge(update: TsetmcQuoteState): TsetmcQuoteState = copy(
        isin = update.isin.ifBlank { isin },
        symbol = update.symbol.ifBlank { symbol },
        name = update.name.ifBlank { name },
        dEven = update.dEven.takeIf { it > 0 } ?: dEven,
        hEven = update.hEven.takeIf { it > 0 } ?: hEven,
        first = update.first.takeIf { it > 0.0 } ?: first,
        closing = update.closing.takeIf { it > 0.0 } ?: closing,
        last = update.last.takeIf { it > 0.0 } ?: last,
        trades = update.trades.takeIf { it > 0.0 } ?: trades,
        volume = update.volume.takeIf { it > 0.0 } ?: volume,
        value = update.value.takeIf { it > 0.0 } ?: value,
        low = update.low.takeIf { it > 0.0 } ?: low,
        high = update.high.takeIf { it > 0.0 } ?: high,
        yesterday = update.yesterday.takeIf { it > 0.0 } ?: yesterday,
        flow = update.flow.takeIf { it > 0 } ?: flow,
        bid = update.bid?.takeIf { it > 0.0 } ?: bid,
        ask = update.ask?.takeIf { it > 0.0 } ?: ask
    )
}

internal data class TsetmcLegacyInit(
    val quotes: List<TsetmcQuoteState>,
    val refId: Long,
    val maxHEven: Int
)

internal data class TsetmcLegacyPlus(
    val updates: List<TsetmcQuoteState>,
    val refId: Long,
    val maxHEven: Int
)

internal object TsetmcProtocol {
    private val tehranZone = ZoneId.of("Asia/Tehran")

    fun parseLegacyInit(body: String): TsetmcLegacyInit {
        require(!looksBlocked(body)) { "TSETMC legacy endpoint is blocked" }
        val parts = body.split('@')
        require(parts.size >= 5) { "Invalid TSETMC MarketWatchInit response" }
        val quotes = parseLegacyRows(parts[2], allowDeltaRows = false)
        require(quotes.isNotEmpty()) { "Empty TSETMC MarketWatchInit" }
        val refId = parts[4].trim().toLongOrNull() ?: 0L
        return TsetmcLegacyInit(quotes, refId, quotes.maxOfOrNull { it.hEven } ?: 0)
    }

    fun parseLegacyPlus(body: String): TsetmcLegacyPlus {
        require(!looksBlocked(body)) { "TSETMC legacy endpoint is blocked" }
        val parts = body.split('@')
        require(parts.size >= 5) { "Invalid TSETMC MarketWatchPlus response" }
        val updates = parseLegacyRows(parts[2], allowDeltaRows = true)
        val refId = parts[4].trim().toLongOrNull() ?: 0L
        return TsetmcLegacyPlus(updates, refId, updates.maxOfOrNull { it.hEven } ?: 0)
    }

    private fun parseLegacyRows(raw: String, allowDeltaRows: Boolean): List<TsetmcQuoteState> = buildList {
        raw.split(';').forEach { row ->
            if (row.isBlank()) return@forEach
            val f = row.split(',')
            when {
                f.size >= 23 -> {
                    val ins = f[0].trim()
                    if (ins.isBlank()) return@forEach
                    add(
                        TsetmcQuoteState(
                            insCode = ins,
                            isin = f.getOrNull(1).orEmpty().trim(),
                            symbol = f.getOrNull(2).orEmpty().trim(),
                            name = f.getOrNull(3).orEmpty().trim(),
                            hEven = f.intAt(4),
                            first = f.doubleAt(5),
                            closing = f.doubleAt(6),
                            last = f.doubleAt(7),
                            trades = f.doubleAt(8),
                            volume = f.doubleAt(9),
                            value = f.doubleAt(10),
                            low = f.doubleAt(11),
                            high = f.doubleAt(12),
                            yesterday = f.doubleAt(13),
                            flow = f.intAt(17)
                        )
                    )
                }
                allowDeltaRows && f.size == 10 -> {
                    val ins = f[0].trim()
                    if (ins.isBlank()) return@forEach
                    add(
                        TsetmcQuoteState(
                            insCode = ins,
                            hEven = f.intAt(1),
                            first = f.doubleAt(2),
                            closing = f.doubleAt(3),
                            last = f.doubleAt(4),
                            trades = f.doubleAt(5),
                            volume = f.doubleAt(6),
                            value = f.doubleAt(7),
                            low = f.doubleAt(8),
                            high = f.doubleAt(9)
                        )
                    )
                }
            }
        }
    }

    fun parseCdnMarketWatch(body: String): List<TsetmcQuoteState> {
        require(!looksBlocked(body)) { "TSETMC CDN endpoint is blocked" }
        val root = JSONObject(body)
        val response = root.optJSONObject("response") ?: root
        val raw = sequenceOf(
            response.opt("marketwatch"), response.opt("marketWatch"), response.opt("marketWatchData"),
            root.opt("marketwatch"), root.opt("marketWatch"), root.opt("marketWatchData")
        ).firstOrNull { it != null && it != JSONObject.NULL }
        val rows = when (raw) {
            is JSONArray -> buildList { for (i in 0 until raw.length()) raw.optJSONObject(i)?.let(::add) }
            is JSONObject -> {
                val nested = raw.optJSONArray("marketwatch") ?: raw.optJSONArray("items") ?: raw.optJSONArray("data")
                if (nested != null) buildList { for (i in 0 until nested.length()) nested.optJSONObject(i)?.let(::add) }
                else buildList {
                    val keys = raw.keys()
                    while (keys.hasNext()) raw.optJSONObject(keys.next())?.let(::add)
                }
            }
            else -> emptyList()
        }
        return rows.mapNotNull(::parseMarketWatchObject)
    }

    fun parseClosingPriceInfo(body: String): TsetmcQuoteState? {
        require(!looksBlocked(body)) { "TSETMC closing price endpoint is blocked" }
        val root = JSONObject(body)
        val row = root.optJSONObject("closingPriceInfo")
            ?: root.optJSONObject("response")?.optJSONObject("closingPriceInfo")
            ?: return null
        return parseClosingObject(row)
    }

    fun parseDailyList(body: String): List<TsetmcQuoteState> {
        require(!looksBlocked(body)) { "TSETMC daily endpoint is blocked" }
        val root = JSONObject(body)
        val array = root.optJSONArray("closingPriceDaily")
            ?: root.optJSONObject("response")?.optJSONArray("closingPriceDaily")
            ?: JSONArray()
        return buildList {
            for (i in 0 until array.length()) {
                val row = array.optJSONObject(i) ?: continue
                parseClosingObject(row)?.let(::add)
            }
        }
    }

    private fun parseMarketWatchObject(row: JSONObject): TsetmcQuoteState? {
        val instrument = row.optJSONObject("instrument") ?: row.optJSONObject("instrumentInfo") ?: row
        val closing = row.optJSONObject("closingPrice") ?: row.optJSONObject("closingPriceInfo") ?: row
        val ins = firstString(instrument, closing, row, keys = arrayOf("insCode", "instrumentCode", "instrumentID"))
            ?: return null
        val best = when (val raw = row.opt("bestLimits")) {
            is JSONArray -> raw.optJSONObject(0)
            is JSONObject -> raw.optJSONObject("0") ?: raw.optJSONObject("1") ?: raw
            else -> null
        }
        return TsetmcQuoteState(
            insCode = ins,
            isin = firstString(instrument, row, keys = arrayOf("cIsin", "instrumentID", "isin")).orEmpty(),
            symbol = firstString(instrument, row, keys = arrayOf("lVal18AFC", "lVal18", "symbol")).orEmpty(),
            name = firstString(instrument, row, keys = arrayOf("lVal30", "lVal30AFC", "companyName")).orEmpty(),
            dEven = firstInt(closing, row, keys = arrayOf("dEven", "date")),
            hEven = firstInt(closing, row, keys = arrayOf("hEven", "lastHEven", "time")),
            first = firstDouble(closing, row, keys = arrayOf("priceFirst", "pf", "first")),
            closing = firstDouble(closing, row, keys = arrayOf("pClosing", "pc", "closingPrice", "close")),
            last = firstDouble(closing, row, keys = arrayOf("pDrCotVal", "pl", "lastPrice", "last")),
            trades = firstDouble(closing, row, keys = arrayOf("zTotTran", "tno", "trades")),
            volume = firstDouble(closing, row, keys = arrayOf("qTotTran5J", "tvol", "volume")),
            value = firstDouble(closing, row, keys = arrayOf("qTotCap", "tval", "value")),
            low = firstDouble(closing, row, keys = arrayOf("priceMin", "pmin", "low")),
            high = firstDouble(closing, row, keys = arrayOf("priceMax", "pmax", "high")),
            yesterday = firstDouble(closing, row, keys = arrayOf("priceYesterday", "py", "yClose", "yesterdayPrice")),
            flow = firstInt(instrument, row, keys = arrayOf("flow")),
            bid = best?.let { firstDouble(it, keys = arrayOf("pMeDem", "buyPrice")) },
            ask = best?.let { firstDouble(it, keys = arrayOf("pMeOf", "sellPrice")) }
        )
    }

    private fun parseClosingObject(row: JSONObject): TsetmcQuoteState? {
        val ins = firstString(row, keys = arrayOf("insCode", "instrumentCode")) ?: return null
        return TsetmcQuoteState(
            insCode = ins,
            dEven = firstInt(row, keys = arrayOf("dEven", "finalLastDate")),
            hEven = firstInt(row, keys = arrayOf("hEven", "lastHEven")),
            first = firstDouble(row, keys = arrayOf("priceFirst", "pf")),
            closing = firstDouble(row, keys = arrayOf("pClosing", "pc")),
            last = firstDouble(row, keys = arrayOf("pDrCotVal", "pl")),
            trades = firstDouble(row, keys = arrayOf("zTotTran", "tno")),
            volume = firstDouble(row, keys = arrayOf("qTotTran5J", "tvol")),
            value = firstDouble(row, keys = arrayOf("qTotCap", "tval")),
            low = firstDouble(row, keys = arrayOf("priceMin", "pmin")),
            high = firstDouble(row, keys = arrayOf("priceMax", "pmax")),
            yesterday = firstDouble(row, keys = arrayOf("priceYesterday", "py", "yClose"))
        )
    }

    fun toSourceTimestamp(dEven: Int, hEven: Int, fallbackToToday: Boolean = false): Long {
        val date = parseDate(dEven) ?: if (fallbackToToday) LocalDate.now(tehranZone) else return 0L
        val time = parseTime(hEven) ?: return date.atStartOfDay(tehranZone).toInstant().toEpochMilli()
        return ZonedDateTime.of(date, time, tehranZone).toInstant().toEpochMilli()
    }

    private fun parseDate(value: Int): LocalDate? {
        if (value <= 0) return null
        val s = value.toString().padStart(8, '0')
        return runCatching {
            LocalDate.of(s.substring(0, 4).toInt(), s.substring(4, 6).toInt(), s.substring(6, 8).toInt())
        }.getOrNull()
    }

    private fun parseTime(value: Int): LocalTime? {
        if (value <= 0) return null
        val hh = value / 10000
        val mm = (value / 100) % 100
        val ss = value % 100
        return runCatching { LocalTime.of(hh, mm, ss) }.getOrNull()
    }

    fun looksBlocked(body: String): Boolean {
        val t = body.trim()
        return t.isEmpty() || t.contains("دسترسی شما", ignoreCase = true) ||
            t.contains("مسدود", ignoreCase = true) || t.contains("General Error Detected", ignoreCase = true) ||
            t.startsWith("<!DOCTYPE", ignoreCase = true)
    }

    private fun firstString(vararg objects: JSONObject, keys: Array<String>): String? {
        objects.forEach { obj ->
            keys.forEach { key ->
                val raw = obj.opt(key)
                if (raw != null && raw != JSONObject.NULL) raw.toString().trim().takeIf { it.isNotEmpty() }?.let { return it }
            }
        }
        return null
    }

    private fun firstDouble(vararg objects: JSONObject, keys: Array<String>): Double {
        objects.forEach { obj ->
            keys.forEach { key -> jsonNumber(obj.opt(key))?.let { return it } }
        }
        return 0.0
    }

    private fun firstInt(vararg objects: JSONObject, keys: Array<String>): Int {
        objects.forEach { obj ->
            keys.forEach { key -> jsonNumber(obj.opt(key))?.toInt()?.let { return it } }
        }
        return 0
    }

    private fun jsonNumber(raw: Any?): Double? = when (raw) {
        null, JSONObject.NULL -> null
        is Number -> raw.toDouble()
        else -> raw.toString().replace(",", "").trim().toDoubleOrNull()
    }

    private fun List<String>.intAt(index: Int): Int = getOrNull(index)?.trim()?.toIntOrNull() ?: 0
    private fun List<String>.doubleAt(index: Int): Double = getOrNull(index)?.trim()?.toDoubleOrNull() ?: 0.0
}
