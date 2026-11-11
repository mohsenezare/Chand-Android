from pathlib import Path
p = Path("source/app/src/main/java/ir/personal/chand/data/MarketRepository.kt")
s = p.read_text()
start = s.index("    private suspend fun searchTsetmcRemote(query: String): List<MarketDescriptor> {")
end = s.index("    private fun descriptorFromTsetmcQuote", start)
replacement = """    private suspend fun searchTsetmcRemote(query: String): List<MarketDescriptor> {
        val body = httpGet("$TSETMC_API/api/Instrument/GetInstrumentSearch/${encode(query.trim())}", 12_000)
        return TsetmcSearchParser.parse(body, query)
    }

"""
p.write_text(s[:start] + replacement + s[end:])
