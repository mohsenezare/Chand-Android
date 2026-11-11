package ir.personal.chand.data

import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.abs
import kotlin.math.ceil

object MarketParsers {
    private val tehranZone = ZoneId.of("Asia/Tehran")
    private val sourceDateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss", Locale.US)
    private val sourceDateFormatter = DateTimeFormatter.ofPattern("yyyy/MM/dd", Locale.US)
    private val sourceTimeFormatter = DateTimeFormatter.ofPattern("HH:mm:ss", Locale.US)

    data class IndicatorResult(
        val items: List<MarketItem>,
        val missingSourceKeys: Set<String>
    )



    fun parseStreamMessage(message: String): List<StreamTick> = buildList {
        val roots = runCatching { listOf(JSONObject(message.trim())) }.getOrElse {
            message.lineSequence()
                .filter(String::isNotBlank)
                .mapNotNull { line -> runCatching { JSONObject(line) }.getOrNull() }
                .toList()
        }
        roots.forEach { root ->
            val values = root.optJSONObject("result")
                ?.optJSONObject("data")
                ?.optJSONArray("data") ?: return@forEach
            for (index in 0 until values.length()) {
                val raw = values.optString(index)
                val fields = raw.split('|')
                if (fields.size < 15 || fields[0] !in setOf("market", "crypto", "stock", "stocks")) continue
                val sourceKey = fields[2].trim()
                val price = number(fields[6]) ?: continue
                if (sourceKey.isBlank() || !price.isFinite() || price <= 0.0) continue
                val direction = fields[12].trim().lowercase(Locale.ROOT)
                val sourceTime = parseSourceDateTime(fields[14]) ?: continue
                add(
                    StreamTick(
                        sourceKey = sourceKey,
                        itemId = fields[1].trim(),
                        price = price,
                        high = number(fields[7]) ?: price,
                        low = number(fields[8]) ?: price,
                        open = number(fields[9]) ?: price,
                        change = signedValue(number(fields[10]) ?: 0.0, direction),
                        changePercent = signedValue(number(fields[11]) ?: 0.0, direction),
                        direction = direction,
                        sourceUpdatedAtMillis = sourceTime
                    )
                )
            }
        }
    }


    fun parseTodayHistory(body: String, marketDate: LocalDate, scale: Double): List<PricePoint> {
        val rows = JSONObject(body).optJSONArray("data") ?: JSONArray()
        val points = buildList {
            for (index in 0 until rows.length()) {
                val row = rows.optJSONArray(index) ?: continue
                val value = number(row.opt(0))?.times(scale) ?: continue
                val time = runCatching {
                    LocalTime.parse(normalizeDigits(row.optString(1)), sourceTimeFormatter)
                }.getOrNull() ?: continue
                add(
                    PricePoint(
                        timestampMillis = ZonedDateTime.of(marketDate, time, tehranZone)
                            .toInstant().toEpochMilli(),
                        value = value
                    )
                )
            }
        }
        return downsample(sanitize(points), 360)
    }

    fun parseHistoricalHistory(body: String, scale: Double): List<PricePoint> {
        val rows = JSONObject(body).optJSONArray("data") ?: JSONArray()
        val points = buildList {
            for (index in 0 until rows.length()) {
                val row = rows.optJSONArray(index) ?: continue
                val value = number(row.opt(3))?.times(scale) ?: continue
                val date = runCatching {
                    LocalDate.parse(normalizeDigits(row.optString(6)), sourceDateFormatter)
                }.getOrNull() ?: continue
                add(
                    PricePoint(
                        timestampMillis = date.atStartOfDay(tehranZone).toInstant().toEpochMilli(),
                        value = value
                    )
                )
            }
        }
        return sanitize(points)
    }

    fun filterAndDownsampleHistory(
        input: List<PricePoint>,
        range: HistoryRange,
        nowMillis: Long,
        maxPoints: Int = 360
    ): List<PricePoint> {
        val cutoff = when (range) {
            HistoryRange.DAY, HistoryRange.ALL -> Long.MIN_VALUE
            HistoryRange.WEEK -> nowMillis - 7L * 24 * 60 * 60 * 1000
            HistoryRange.MONTH -> nowMillis - 31L * 24 * 60 * 60 * 1000
            HistoryRange.YEAR -> Instant.ofEpochMilli(nowMillis).atZone(tehranZone)
                .minusYears(1).toInstant().toEpochMilli()
            HistoryRange.FIVE_YEARS -> Instant.ofEpochMilli(nowMillis).atZone(tehranZone)
                .minusYears(5).toInstant().toEpochMilli()
        }
        return downsample(input.filter { it.timestampMillis >= cutoff }, maxPoints)
    }

    fun parseSourceDateTime(raw: String): Long? {
        val normalized = normalizeDigits(raw.trim())
        if (normalized.isBlank()) return null
        return runCatching { Instant.parse(normalized).toEpochMilli() }.getOrNull()
            ?: runCatching {
                LocalDateTime.parse(normalized, sourceDateTimeFormatter)
                    .atZone(tehranZone).toInstant().toEpochMilli()
            }.getOrNull()
    }

    fun appendPoint(
        input: List<PricePoint>,
        timestampMillis: Long,
        value: Double,
        limit: Int = 360
    ): List<PricePoint> {
        if (!value.isFinite() || value <= 0.0 || timestampMillis <= 0L) return input
        val points = input.toMutableList()
        val last = points.lastOrNull()
        when {
            last == null -> points += PricePoint(timestampMillis, value)
            timestampMillis < last.timestampMillis -> Unit
            timestampMillis == last.timestampMillis -> points[points.lastIndex] = PricePoint(timestampMillis, value)
            last.value != value -> points += PricePoint(timestampMillis, value)
            timestampMillis - last.timestampMillis >= 60_000L -> points += PricePoint(timestampMillis, value)
        }
        return points.takeLast(limit)
    }

    fun downsample(input: List<PricePoint>, maxPoints: Int): List<PricePoint> {
        if (maxPoints < 4 || input.size <= maxPoints) return input
        val bucketSize = ceil(input.size.toDouble() / (maxPoints / 2.0)).toInt().coerceAtLeast(2)
        val output = ArrayList<PricePoint>(maxPoints)
        input.chunked(bucketSize).forEach { bucket ->
            val low = bucket.minByOrNull(PricePoint::value)
            val high = bucket.maxByOrNull(PricePoint::value)
            listOfNotNull(low, high)
                .distinctBy(PricePoint::timestampMillis)
                .sortedBy(PricePoint::timestampMillis)
                .forEach(output::add)
        }
        if (output.firstOrNull()?.timestampMillis != input.first().timestampMillis) output.add(0, input.first())
        if (output.lastOrNull()?.timestampMillis != input.last().timestampMillis) output.add(input.last())
        if (output.size <= maxPoints) return output
        val lastIndex = output.lastIndex
        return List(maxPoints) { index ->
            output[(index.toDouble() * lastIndex / (maxPoints - 1)).toInt()]
        }.distinctBy(PricePoint::timestampMillis)
    }

    private fun sanitize(input: List<PricePoint>): List<PricePoint> = input
        .filter { it.value.isFinite() && it.value > 0.0 && it.timestampMillis > 0L }
        .sortedBy(PricePoint::timestampMillis)
        .distinctBy(PricePoint::timestampMillis)

    private fun signedValue(raw: Double, direction: String): Double = when (direction) {
        "low" -> -abs(raw)
        "high" -> abs(raw)
        else -> raw
    }

    private fun scaledNumber(value: JSONObject, key: String, scale: Double): Double? =
        number(value.opt(key))?.times(scale)

    private fun number(raw: Any?): Double? = when (raw) {
        null, JSONObject.NULL -> null
        is Number -> raw.toDouble()
        else -> normalizeDigits(raw.toString())
            .replace(",", "")
            .replace("٬", "")
            .trim()
            .toDoubleOrNull()
    }

    private fun normalizeDigits(value: String): String = buildString(value.length) {
        value.forEach { char ->
            append(
                when (char) {
                    '۰', '٠' -> '0'
                    '۱', '١' -> '1'
                    '۲', '٢' -> '2'
                    '۳', '٣' -> '3'
                    '۴', '٤' -> '4'
                    '۵', '٥' -> '5'
                    '۶', '٦' -> '6'
                    '۷', '٧' -> '7'
                    '۸', '٨' -> '8'
                    '۹', '٩' -> '9'
                    else -> char
                }
            )
        }
    }
}
