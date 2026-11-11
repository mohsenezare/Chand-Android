package ir.personal.chand.data

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MarketParsersTest {
    private val usd = DEFAULT_MARKET_DESCRIPTORS.first { it.id == "usd" }
    private val euro = DEFAULT_MARKET_DESCRIPTORS.first { it.id == "euro" }

    @Test
    fun historyParsersNormalizeValuesAndDates() {
        val today = MarketParsers.parseTodayHistory(
            """{"data":[["2122000","10:01:00"],["2123000","10:02:00"]]}""",
            LocalDate.of(2026, 8, 31),
            0.1
        )
        assertEquals(listOf(212_200.0, 212_300.0), today.map(PricePoint::value))

        val historical = MarketParsers.parseHistoricalHistory(
            """{"data":[[0,0,0,"2100000",0,0,"2026/08/30"],[0,0,0,"2122000",0,0,"2026/08/31"]]}""",
            0.1
        )
        assertEquals(listOf(210_000.0, 212_200.0), historical.map(PricePoint::value))
        assertTrue(historical[0].timestampMillis < historical[1].timestampMillis)
    }

    @Test
    fun downsampleKeepsFirstAndLastObservations() {
        val input = (0 until 1_000).map { PricePoint(it.toLong() + 1L, (it % 37).toDouble() + 1.0) }
        val output = MarketParsers.downsample(input, 100)
        assertTrue(output.size <= 100)
        assertEquals(input.first(), output.first())
        assertEquals(input.last(), output.last())
    }
}
