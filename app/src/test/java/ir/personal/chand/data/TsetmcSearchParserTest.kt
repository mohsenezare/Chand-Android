package ir.personal.chand.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TsetmcSearchParserTest {
    @Test fun parsesNestedEnvelopeAndFiltersQuery() {
        val json = """{"instrumentSearch":{"data":[
          {"insCode":"123456","lVal18AFC":"فولاد","lVal30":"فولاد مبارکه اصفهان","flow":1},
          {"insCode":"654321","lVal18AFC":"فملی","lVal30":"ملی صنایع مس ایران","flow":2}
        ]}}"""
        val rows = TsetmcSearchParser.parse(json, "فولاد")
        assertEquals(1, rows.size)
        assertEquals("123456", rows.single().sourceKey)
        assertEquals(MarketSource.TSETMC, rows.single().source)
    }
    @Test fun rejectsRowsWithoutValidInstrumentCode() {
        val json = """{"data":[{"lVal18AFC":"فولاد"},{"insCode":"abc","lVal18AFC":"فملی"}]}"""
        assertTrue(TsetmcSearchParser.parse(json, "فولاد").isEmpty())
    }
}
