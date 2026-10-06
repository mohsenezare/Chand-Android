from pathlib import Path
root = Path("source/app/src/main/java/ir/personal/chand")

p = root / "MainActivity.kt"
s = p.read_text()
s = s.replace("""                    SourceButton(
                        text = "بازارهای جهانی",
                        selected = state.catalogSource == CatalogSource.TGJU,
                        onClick = { onSearch(CatalogSource.TGJU, "", false) }
                    )
""", "")
p.write_text(s)

p = root / "MainViewModel.kt"
s = p.read_text().replace("const val ACTIVE_REFRESH_INTERVAL_MS = 1_000L", "const val ACTIVE_REFRESH_INTERVAL_MS = 750L")
p.write_text(s)

p = root / "data/MarketRepository.kt"
s = p.read_text()

old = """        val fetched = coroutineScope {
            urls.map { url -> async { requestResult { parseTsetmcCatalogResponse(httpGet(url, 12_000)) } } }.map { it.await() }
        }.mapNotNull { it.getOrNull() }.flatten().distinctBy(MarketDescriptor::id)
        if (fetched.isNotEmpty()) {
            saveTsetmcCatalogCache(fetched)
            return fetched
        }
        return cached
"""
new = """        val fetched = coroutineScope {
            urls.map { url -> async { requestResult { parseTsetmcCatalogResponse(httpGet(url, 12_000)) } } }.map { it.await() }
        }.mapNotNull { it.getOrNull() }.flatten().distinctBy(MarketDescriptor::id).toMutableList()

        if (fetched.size < 1000) {
            requestResult { parseTsetmcCdnMarketWatch(httpGet(TSETMC_CDN_MARKET_WATCH, 15_000)) }
                .getOrNull()?.let { extra ->
                    val seen = fetched.asSequence().map(MarketDescriptor::id).toHashSet()
                    fetched += extra.filterNot { it.id in seen }
                }
        }
        if (fetched.isNotEmpty()) {
            saveTsetmcCatalogCache(fetched)
            return fetched
        }
        return cached
"""
if old not in s:
    raise SystemExit("catalog block not found")
s = s.replace(old, new)

anchor = "    private fun parseTsetmcCatalogResponse(body: String): List<MarketDescriptor> {\n"
helper = """    private fun parseTsetmcCdnMarketWatch(body: String): List<MarketDescriptor> {
        val root = JSONObject(body)
        val items = root.optJSONArray("marketwatch")
            ?: root.optJSONArray("marketWatch")
            ?: root.optJSONArray("items")
            ?: root.optJSONArray("Items")
            ?: JSONArray()
        return buildList {
            for (i in 0 until items.length()) {
                val value = items.optJSONObject(i) ?: continue
                val insCode = value.optStringAny("insCode", "inscode", "instrumentId", "instrumentID").trim()
                val symbol = value.optStringAny("lVal18AFC", "instrumentName", "symbol").trim()
                val name = value.optStringAny("lVal30", "companyName", "companyNamePersian", "instrument_Name").trim()
                if (insCode.isBlank() || symbol.isBlank()) continue
                val flow = value.optStringAny("flowTitle", "flow", "marketName").trim()
                add(MarketDescriptor(
                    id = "tsetmc:" + insCode,
                    sourceKey = insCode,
                    name = name.ifBlank { symbol },
                    code = symbol,
                    symbol = symbol,
                    source = MarketSource.TSETMC,
                    category = listOf("بورس ایران", flow).filter { it.isNotBlank() }.distinct().joinToString(" • "),
                    unit = "ریال",
                    valueScale = 0.1
                ))
            }
        }
    }

"""
if anchor not in s:
    raise SystemExit("parser anchor not found")
s = s.replace(anchor, helper + anchor)

anchor = '        private const val TSETMC_WEBGW = "https://webgw.tse.ir"\n'
replacement = anchor + '        private const val TSETMC_CDN_MARKET_WATCH = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&paperTypes[0]=1&paperTypes[1]=2&paperTypes[2]=3&paperTypes[3]=4&paperTypes[4]=5&paperTypes[5]=6&paperTypes[6]=7&paperTypes[7]=8&paperTypes[8]=9&withBestLimits=false&hEven=0&RefID=0"\n'
if anchor not in s:
    raise SystemExit("constant anchor not found")
s = s.replace(anchor, replacement)
p.write_text(s)
