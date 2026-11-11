package ir.personal.chand.ui

import java.time.Instant
import java.time.ZoneId
import java.util.Locale

object PersianDateTime {
    data class JalaliDate(val year: Int, val month: Int, val day: Int)

    fun format(epochMillis: Long, zoneId: ZoneId = ZoneId.systemDefault()): String {
        val local = Instant.ofEpochMilli(epochMillis).atZone(zoneId)
        val jalali = fromGregorian(local.year, local.monthValue, local.dayOfMonth)
        val hour = when (val value = local.hour % 12) { 0 -> 12 else -> value }
        val period = if (local.hour < 12) "AM" else "PM"
        return String.format(
            Locale.US,
            "%d/%d/%d, %d:%02d %s",
            jalali.month,
            jalali.day,
            jalali.year,
            hour,
            local.minute,
            period
        )
    }

    fun fromGregorian(year: Int, month: Int, day: Int): JalaliDate {
        val cumulativeGregorianDays = intArrayOf(0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
        val adjustedYear = if (month > 2) year + 1 else year
        var days = 355666L + 365L * year +
            (adjustedYear + 3) / 4 -
            (adjustedYear + 99) / 100 +
            (adjustedYear + 399) / 400 +
            day + cumulativeGregorianDays[month - 1]
        var jalaliYear = -1595 + 33 * (days / 12053).toInt()
        days %= 12053
        jalaliYear += 4 * (days / 1461).toInt()
        days %= 1461
        if (days > 365) {
            jalaliYear += ((days - 1) / 365).toInt()
            days = (days - 1) % 365
        }
        val jalaliMonth: Int
        val jalaliDay: Int
        if (days < 186) {
            jalaliMonth = 1 + (days / 31).toInt()
            jalaliDay = 1 + (days % 31).toInt()
        } else {
            jalaliMonth = 7 + ((days - 186) / 30).toInt()
            jalaliDay = 1 + ((days - 186) % 30).toInt()
        }
        return JalaliDate(jalaliYear, jalaliMonth, jalaliDay)
    }
}
