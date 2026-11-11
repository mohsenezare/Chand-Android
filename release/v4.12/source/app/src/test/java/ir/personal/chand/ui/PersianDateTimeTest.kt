package ir.personal.chand.ui

import java.time.LocalDateTime
import java.time.ZoneId
import org.junit.Assert.assertEquals
import org.junit.Test

class PersianDateTimeTest {
    @Test
    fun gregorianDateIsConvertedToJalali() {
        assertEquals(
            PersianDateTime.JalaliDate(1405, 6, 9),
            PersianDateTime.fromGregorian(2026, 8, 31)
        )
    }

    @Test
    fun headerFormatFollowsChandReference() {
        val zone = ZoneId.of("Asia/Tehran")
        val instant = LocalDateTime.of(2026, 8, 31, 22, 2)
            .atZone(zone).toInstant().toEpochMilli()
        assertEquals("6/9/1405, 10:02 PM", PersianDateTime.format(instant, zone))
    }
}
