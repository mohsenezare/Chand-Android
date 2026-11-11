import base64,zlib
exec(compile(zlib.decompress(base64.b64decode("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")), __file__, "exec"))

# The old TradingView quote POST helper has no callers after provider migration.
from pathlib import Path
repo_file = Path("source/app/src/main/java/ir/personal/chand/data/MarketRepository.kt")
repo_text = repo_file.read_text()
start = repo_text.find("    private suspend fun httpPost(")
if start >= 0:
    end = repo_text.find("\n    private ", start + 10)
    if end < 0:
        raise SystemExit("Could not safely locate end of obsolete HTTP POST helper")
    repo_text = repo_text[:start] + repo_text[end:]
repo_file.write_text(repo_text)

# TSETMC-listed Iranian gold funds stay on TSETMC, not on a non-existent ArzDigital coin page.
models_file = Path("source/app/src/main/java/ir/personal/chand/data/MarketModels.kt")
models_text = models_file.read_text()
ayar = re.search(r'MarketDescriptor\(\s*id = "ayar".*?\n\s*\)', models_text, re.S)
if ayar:
    block = ayar.group(0)
    block = block.replace('sourceKey = "gc3"', 'sourceKey = "عیار"')
    block = block.replace('name = "عیار"', 'name = "عیار"')
    block = block.replace('code = "AYAR"', 'code = "عیار"')
    block = block.replace('symbol = "Au"', 'symbol = "TSE"')
    block = block.replace('source = MarketSource.ARZDIGITAL', 'source = MarketSource.TSETMC')
    block = block.replace('category = "صندوق طلا"', 'category = "بورس ایران · صندوق طلا"')
    models_text = models_text[:ayar.start()] + block + models_text[ayar.end():]
    models_file.write_text(models_text)

# ArzDigital reports JPY as USD per one yen; invert only the USD/JPY display quote.
repo_text = repo_file.read_text()
repo_text = repo_text.replace(
    '''val price = when (descriptor.unit) {
                        "تومان", "ریال" -> quote.priceToman
                        else -> quote.priceUsd
                    }?.takeIf { it.isFinite() && it > 0.0 }''',
    '''val price = when {
                        descriptor.code.equals("USD/JPY", ignoreCase = true) ->
                            quote.priceUsd?.takeIf { it > 0.0 }?.let { 1.0 / it }
                        descriptor.unit == "تومان" || descriptor.unit == "ریال" -> quote.priceToman
                        else -> quote.priceUsd
                    }?.takeIf { it.isFinite() && it > 0.0 }'''
)
repo_file.write_text(repo_text)

# v4.0 payload compatibility: replace the detached Investing catalogue body left by
# the old expression-bodied function with a real ArzDigital public-page catalogue.
repo_text = repo_file.read_text()
start_marker = '    ): List<MarketDescriptor> = withContext(Dispatchers.IO) {\n        val seeds = ('
start = repo_text.find(start_marker)
end = repo_text.find('    private suspend fun loadTsetmcCatalog(', start)
if start >= 0 and end > start:
    global_catalog = '''    suspend fun refreshGlobalArzDigitalCatalogStrict(
        onProgress: (Int) -> Unit = {}
    ): List<MarketDescriptor> = withContext(Dispatchers.IO) {
        onProgress(15)
        val entries = arzDigitalClient.searchCatalog("", 160)
        val remote = entries.map { entry ->
            MarketDescriptor(
                id = "arz:" + entry.slug, sourceKey = entry.slug, name = entry.title,
                code = entry.code.ifBlank { entry.slug.take(12).uppercase(Locale.US) },
                symbol = "ASSET", source = MarketSource.ARZDIGITAL,
                category = "بازار جهانی", unit = "دلار", valueScale = 1.0
            )
        }
        val items = (ARZDIGITAL_MARKET_DESCRIPTORS + remote).distinctBy(MarketDescriptor::id)
        require(items.isNotEmpty()) { "ArzDigital public catalogue is empty" }
        onProgress(100)
        synchronized(knownDescriptors) { items.forEach { knownDescriptors[it.id] = it } }
        items
    }

'''
    repo_text = repo_text[:start] + global_catalog + repo_text[end:]
repo_text = repo_text.replace('\n/0/0/0/0/$name"\n', '\n')
repo_file.write_text(repo_text)

# The v4.0 base has no repository-side TSETMC tick applier; use the repository's
# 5-second HTTP refresh loop for TSETMC and ArzDigital rather than calling a missing method.
vm_file = Path("source/app/src/main/java/ir/personal/chand/MainViewModel.kt")
vm_text = vm_file.read_text()
vm_text = re.sub(
    r"    private fun startProviderStreams\(\) \{.*?\n    \}",
    "    private fun startProviderStreams() { /* MarketRepository refreshes ArzDigital and TSETMC over HTTP. */ }",
    vm_text,
    count=1,
    flags=re.S
)
vm_file.write_text(vm_text)

# MainActivity needs the MarketSource enum import for the two-source freshness/logo switches.
activity_file = Path("source/app/src/main/java/ir/personal/chand/MainActivity.kt")
activity_text = activity_file.read_text()
if "import ir.personal.chand.data.MarketSource" not in activity_text:
    activity_text = activity_text.replace(
        "package ir.personal.chand\n",
        "package ir.personal.chand\n\nimport ir.personal.chand.data.MarketSource\n",
        1
    )
activity_file.write_text(activity_text)

# Correct the generated release metadata to 4.12.0.
gradle_file = Path("source/app/build.gradle.kts")
if gradle_file.exists():
    gradle_text = gradle_file.read_text()
    gradle_text = re.sub(r"versionCode\s*=\s*\\d+", "versionCode = 412", gradle_text, count=1)
    gradle_text = re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "4.12.0"', gradle_text, count=1)
    gradle_file.write_text(gradle_text)

# Use a valid receive-time fallback for the ArzDigital session history point.
repo_text = repo_file.read_text()
repo_text = repo_text.replace(
    "MarketParsers.appendPoint(previous?.history.orEmpty(), quote.sourceUpdatedAtMillis, price)",
    "MarketParsers.appendPoint(previous?.history.orEmpty(), quote.sourceUpdatedAtMillis.takeIf { it > 0L } ?: receivedAtMillis, price)"
)
repo_file.write_text(repo_text)
