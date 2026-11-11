package ir.personal.chand.ui

import ir.personal.chand.data.MarketItem
import java.text.NumberFormat
import java.time.Instant
import java.time.ZoneId
import java.util.Locale
import kotlin.math.abs

object MarketFormatting {
    private val formatters = (0..6).associateWith { digits ->
        NumberFormat.getNumberInstance(Locale.US).apply {
            minimumFractionDigits = 0
            maximumFractionDigits = digits
        }
    }

    fun price(item: MarketItem): String {
        if (!item.isAvailable || !item.price.isFinite() || item.price <= 0.0) return "—"
        val value = item.price
        val absolute = abs(value)
        return when {
            absolute >= 1_000_000_000 -> compact(value, 1_000_000_000.0, "B", true)
            absolute >= 10_000_000 -> compact(value, 1_000_000.0, "M", true)
            item.code == "TEDPIX" && absolute >= 1_000_000 -> compact(value, 1_000_000.0, "M", true)
            else -> regular(value, item.unit)
        }
    }

    fun value(value: Double, unit: String): String {
        if (!value.isFinite() || value <= 0.0) return "—"
        return regular(value, unit)
    }

    fun change(item: MarketItem): String {
        if (!item.isAvailable) return "—"
        if (item.change == 0.0) return "•0"
        val arrow = if (item.change > 0.0) "↑" else "↓"
        return arrow + compactChange(abs(item.change), item.unit)
    }

    fun changeWithPercent(item: MarketItem): String {
        val base = change(item)
        if (!item.isAvailable || item.changePercent == 0.0) return base
        return "$base  (${String.format(Locale.US, "%.2f", abs(item.changePercent))}%)"
    }

    fun lastSourceTime(item: MarketItem, zoneId: ZoneId = ZoneId.systemDefault()): String {
        if (item.sourceUpdatedAtMillis <= 0L) return "—"
        val value = Instant.ofEpochMilli(item.sourceUpdatedAtMillis).atZone(zoneId)
        return String.format(Locale.US, "%02d:%02d:%02d", value.hour, value.minute, value.second)
    }

    private fun compactChange(value: Double, unit: String): String = when {
        value >= 1_000_000_000 -> compact(value, 1_000_000_000.0, "B", false)
        value >= 1_000_000 -> compact(value, 1_000_000.0, "M", false)
        value >= 1_000 -> compact(value, 1_000.0, "K", false)
        else -> regular(value, unit)
    }

    private fun compact(value: Double, divisor: Double, suffix: String, priceMode: Boolean): String {
        val scaled = value / divisor
        val digits = when {
            priceMode && abs(scaled) < 100 -> 3
            priceMode -> 1
            abs(scaled) < 10 -> 1
            abs(scaled) < 100 -> 2
            else -> 2
        }
        return String.format(Locale.US, "%.${digits}f", scaled)
            .trimEnd('0').trimEnd('.') + suffix
    }

    private fun regular(value: Double, unit: String): String {
        val absolute = abs(value)
        val digits = when {
            unit == "تومان" || unit == "ریال" || unit == "واحد" || absolute >= 10_000 -> 0
            absolute >= 1_000 -> 2
            absolute >= 1 -> 3
            else -> 6
        }
        return formatters.getValue(digits).format(value)
    }
}
