package ir.personal.chand.ui

import ir.personal.chand.data.DataOrigin
import ir.personal.chand.data.MarketItem
import org.junit.Assert.assertEquals
import org.junit.Test

class MarketFormattingTest {
    @Test
    fun cardValuesMatchChandCompactNotation() {
        val dollar = item("usd", "USD", 212_200.0, 5_900.0)
        val gram = item("gold18", "GRAM", 22_323_000.0, 558_660.0)
        assertEquals("212,200", MarketFormatting.price(dollar))
        assertEquals("↑5.9K", MarketFormatting.change(dollar))
        assertEquals("22.323M", MarketFormatting.price(gram))
        assertEquals("↑558.66K", MarketFormatting.change(gram))
        assertEquals("↓7.4K", MarketFormatting.change(item("euro", "EUR", 246_400.0, -7_400.0)))
    }

    private fun item(id: String, code: String, price: Double, change: Double) = MarketItem(
        id = id,
        name = code,
        code = code,
        symbol = code,
        price = price,
        change = change,
        changePercent = 0.0,
        high = price,
        low = price,
        buy = price,
        sell = price,
        history = emptyList(),
        sourceUpdatedAtMillis = 1L,
        receivedAtMillis = 1L,
        origin = DataOrigin.LIVE,
        isAvailable = true,
        unit = "تومان"
    )
}
