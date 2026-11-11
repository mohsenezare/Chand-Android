package ir.personal.chand.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.ZoneId

class TsetmcProtocolTest {
    @Test
    fun legacyInitAndDeltaPreserveInstrumentAndUpdateTrade() {
        val full = listOf(
            "1234567890123456", "IRO1TEST0001", "فولاد", "فولاد مبارکه اصفهان",
            "101530", "3800", "3850", "3860", "12", "100000", "386000000",
            "3780", "3880", "3750", "0", "0", "0", "1", "0", "0", "0", "0", "0", "0", "0", "0"
        ).joinToString(",")
        val init = TsetmcProtocol.parseLegacyInit("x@y@$full@z@100")
        assertEquals(1, init.quotes.size)
        val base = init.quotes.first()
        assertEquals("فولاد", base.symbol)
        assertEquals(3860.0, base.last, 0.0)
        assertTrue(base.hasRealTrade)

        val delta = "1234567890123456,101531,3800,3851,3865,13,101000,390365000,3780,3880"
        val plus = TsetmcProtocol.parseLegacyPlus("x@y@$delta@z@125")
        val merged = base.merge(plus.updates.first())
        assertEquals("فولاد", merged.symbol)
        assertEquals(3865.0, merged.last, 0.0)
        assertEquals(13.0, merged.trades, 0.0)
    }

    @Test
    fun sourceTimestampUsesExactTehranDateAndTime() {
        val millis = TsetmcProtocol.toSourceTimestamp(20261006, 101530, fallbackToToday = false)
        val zoned = Instant.ofEpochMilli(millis).atZone(ZoneId.of("Asia/Tehran"))
        assertEquals(2026, zoned.year)
        assertEquals(10, zoned.monthValue)
        assertEquals(6, zoned.dayOfMonth)
        assertEquals(10, zoned.hour)
        assertEquals(15, zoned.minute)
        assertEquals(30, zoned.second)
    }
}
