package ir.personal.chand.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class ArzDigitalPageClientTest {
    private val parser = ArzDigitalPageClient()

    @Test fun parsesBrentPublicPagePriceAndChange() {
        val html = """
            <html><head><title>Brent Oil (Derivatives) - ارزدیجیتال</title></head>
            <body><h1>قیمت لحظه ای Brent Oil (Derivatives)</h1>
            <div>3.79%</div><div>$76.04</div><div>۱۳,۷۴۸,۲۶۶ ت</div></body></html>
        """.trimIndent()
        val quote = parser.parse("brent-oil-derivatives", html)
        assertEquals(76.04, quote.priceUsd!!, 0.0001)
        assertEquals(13748266.0, quote.priceToman!!, 0.1)
        assertEquals(3.79, quote.changePercent24h!!, 0.0001)
    }

    @Test fun rejectsPageWithoutPositiveQuote() {
        val html = "<html><title>Brent Oil</title><body>قیمت نامشخص</body></html>"
        assertThrows(java.io.IOException::class.java) {
            parser.parse("brent-oil-derivatives", html)
        }
    }
}
