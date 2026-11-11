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
            <div>3.79%</div><div>$76.04</div><div>۱۳,۷۴۸,۲۶۶ ت</div>
            <div>${"market quote content ".repeat(140)}</div></body></html>
        """.trimIndent()
        val quote = parser.parse("brent-oil-derivatives", html)
        assertEquals(76.04, quote.priceUsd!!, 0.0001)
        assertEquals(13748266.0, quote.priceToman!!, 0.1)
        assertEquals(3.79, quote.changePercent24h!!, 0.0001)
    }

    @Test fun routesFiatAndGoldToArzDigitalConverterPages() {
        assertEquals(
            "https://arzdigital.com/convert/united-states-dollar/ir-toman/",
            parser.pageUrl("united-states-dollar")
        )
        assertEquals(
            "https://arzdigital.com/convert/euro/ir-toman/",
            parser.pageUrl("euro")
        )
        assertEquals(
            "https://arzdigital.com/convert/gold-gerami-18/ir-toman/",
            parser.pageUrl("gold-18-karat")
        )
        assertEquals(
            "https://arzdigital.com/convert/emami-gold/ir-toman/",
            parser.pageUrl("emami-coin")
        )
        assertEquals(
            "https://arzdigital.com/convert/pound-sterling/ir-toman/",
            parser.pageUrl("british-pound-sterling")
        )
        assertEquals(
            "https://arzdigital.com/convert/japanese-yen/ir-toman/",
            parser.pageUrl("japanese-yen")
        )
    }

    @Test fun parsesFiatConverterPageLabeledQuotes() {
        val html = """
            <html><head><title>تبدیل دلار آمریکا به تومان</title></head>
            <body>
            <h1>تبدیل دلار آمریکا به تومان</h1>
            <p>قیمت امروز دلار آمریکا به دلار:</p><p>0.00%</p><p>$1.00</p>
            <p>قیمت امروز دلار آمریکا به تومان:</p><p>1.25%</p><p>۲۲۲,۵۱۰ ت</p>
            <div>${"converter data ".repeat(180)}</div>
            </body></html>
        """.trimIndent()
        val quote = parser.parse("united-states-dollar", html)
        assertEquals(1.0, quote.priceUsd!!, 0.0001)
        assertEquals(222510.0, quote.priceToman!!, 0.1)
        assertEquals(1.25, quote.changePercent24h!!, 0.0001)
    }

    @Test fun rejectsPageWithoutPositiveQuote() {
        val html = "<html><title>Brent Oil</title><body>قیمت نامشخص</body></html>" + "x".repeat(2_100)
        assertThrows(java.io.IOException::class.java) {
            parser.parse("brent-oil-derivatives", html)
        }
    }
}
