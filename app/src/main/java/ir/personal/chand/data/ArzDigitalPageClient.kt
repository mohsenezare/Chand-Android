package ir.personal.chand.data

import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Reads public ArzDigital pages only. Fiat and local gold quotes use the site's
 * public converter pages; crypto and tokenized global assets use their coin pages.
 */
internal class ArzDigitalPageClient(
    private val http: OkHttpClient = OkHttpClient.Builder()
        .callTimeout(18, TimeUnit.SECONDS)
        .connectTimeout(7, TimeUnit.SECONDS)
        .readTimeout(12, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()
) {
    data class CatalogEntry(val slug: String, val title: String, val code: String)
    data class Quote(
        val slug: String,
        val priceUsd: Double?,
        val priceToman: Double?,
        val changePercent24h: Double?,
        val sourceUpdatedAtMillis: Long = 0L
    )

    fun searchCatalog(query: String, limit: Int = 100): List<CatalogEntry> {
        val html = get("https://arzdigital.com/coins/")
        val link = Regex("""(?is)<a\b([^>]*href=["'](?:https?://arzdigital\.com)?/coins/([a-z0-9-]+)/?["'][^>]*)>(.*?)</a>""")
        val found = linkedMapOf<String, CatalogEntry>()
        link.findAll(html).forEach { m ->
            val slug = m.groupValues[2]
            if (slug.isBlank() || slug in setOf("coins", "historical-data")) return@forEach
            val title = clean(m.groupValues[3])
            if (title.isBlank()) return@forEach
            val code = title.split(Regex("\\s+")).firstOrNull().orEmpty()
                .replace(Regex("[^A-Za-z0-9./_-]"), "")
            if (query.isBlank() || title.contains(query, true) || slug.contains(query, true) || code.contains(query, true)) {
                found.putIfAbsent(slug, CatalogEntry(slug, title, code))
            }
        }
        return found.values.take(limit)
    }

    fun fetch(slug: String): Quote {
        require(slug.matches(Regex("[a-z0-9-]{2,100}"))) { "Invalid ArzDigital slug" }
        return parse(slug, get(pageUrl(slug)))
    }

    internal fun pageUrl(slug: String): String = when (slug) {
        "united-states-dollar" -> "$BASE/convert/united-states-dollar/ir-toman/"
        "euro" -> "$BASE/convert/euro/ir-toman/"
        "british-pound-sterling" -> "$BASE/convert/pound-sterling/ir-toman/"
        "japanese-yen" -> "$BASE/convert/japanese-yen/ir-toman/"
        "gold-18-karat" -> "$BASE/convert/gold-gerami-18/ir-toman/"
        "emami-coin" -> "$BASE/convert/emami-gold/ir-toman/"
        "gold" -> "$BASE/convert/gold-ounce/ir-toman/"
        "silver" -> "$BASE/convert/silver-ounce/ir-toman/"
        "azadi-gold-full" -> "$BASE/convert/azadi-gold-full/ir-toman/"
        "gerami-gold" -> "$BASE/convert/gerami-gold/ir-toman/"
        else -> "$BASE/coins/$slug/"
    }

    internal fun parse(slug: String, html: String): Quote {
        if (html.length < 2_000) throw IOException("ArzDigital page is too short")
        val plain = clean(html
            .replace(Regex("""(?is)<script\b[^>]*>.*?</script>"""), " ")
            .replace(Regex("""(?is)<style\b[^>]*>.*?</style>"""), " "))
        val identity = slug.replace('-', ' ')
        if (!plain.contains(identity, true) && !plain.contains("قیمت امروز", true) &&
            !plain.contains("قیمت لحظه", true)) {
            throw IOException("ArzDigital asset identity could not be verified: $slug")
        }

        val usdLabeled = Regex("""(?is)قیمت امروز.{0,100}?به دلار:\s*[+−-]?[۰-۹0-9.,]+\s*%\s*\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)""")
            .find(plain)?.groupValues?.get(1)?.let(::number)
        val usd = usdLabeled ?: Regex("""\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)""")
            .find(plain)?.groupValues?.get(1)?.let(::number)

        val tomanLabeled = Regex("""(?is)قیمت امروز.{0,100}?به تومان:\s*[+−-]?[۰-۹0-9.,]+\s*%\s*([۰-۹٠-٩0-9,٬٫]+)\s*(?:تومان|ت)""")
            .find(plain)?.groupValues?.get(1)?.let(::number)
        val toman = tomanLabeled ?: Regex("""([۰-۹٠-٩0-9][۰-۹٠-٩0-9,٬٫]*(?:[.٫][0-9]+)?)\s*(?:تومان|ت)""")
            .find(plain)?.groupValues?.get(1)?.let(::number)

        val change = Regex("""(?is)قیمت امروز.{0,100}?به تومان:\s*([+−-]?[۰-۹٠-٩0-9]+(?:[.٫][۰-۹٠-٩0-9]+)?)\s*%""")
            .find(plain)?.groupValues?.get(1)?.let(::number)
            ?: Regex("""(?is)قیمت امروز.{0,100}?به دلار:\s*([+−-]?[۰-۹٠-٩0-9]+(?:[.٫][۰-۹٠-٩0-9]+)?)\s*%""")
                .find(plain)?.groupValues?.get(1)?.let(::number)
            ?: Regex("""([+−-]?[۰-۹٠-٩0-9]+(?:[.٫][۰-۹٠-٩0-9]+)?)\s*%""")
                .find(plain)?.groupValues?.get(1)?.let(::number)

        val validUsd = usd?.takeIf { it.isFinite() && it > 0.0 }
        val validToman = toman?.takeIf { it.isFinite() && it > 0.0 }
        if (validUsd == null && validToman == null) {
            throw IOException("No valid positive ArzDigital quote found: $slug")
        }
        return Quote(slug, validUsd, validToman, change, 0L)
    }

    private fun get(url: String): String {
        val request = Request.Builder().url(url)
            .header("User-Agent", USER_AGENT)
            .header("Accept", "text/html,application/xhtml+xml")
            .header("Cache-Control", "no-cache")
            .build()
        return http.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IOException("ArzDigital HTTP ${response.code}")
            response.body?.string()?.takeIf { it.length > 2_000 }
                ?: throw IOException("ArzDigital returned an empty page")
        }
    }

    private fun clean(raw: String): String = raw
        .replace(Regex("""(?s)<[^>]+>"""), " ")
        .replace("&nbsp;", " ").replace("&#160;", " ")
        .replace("&quot;", "\"").replace("&amp;", "&")
        .replace(Regex("\\s+"), " ").trim()

    private fun number(raw: String): Double? {
        val normalized = raw.trim().map { ch ->
            when (ch) {
                in '۰'..'۹' -> ('0'.code + ch.code - '۰'.code).toChar()
                in '٠'..'٩' -> ('0'.code + ch.code - '٠'.code).toChar()
                '٫' -> '.'
                '٬', ',' -> ','
                '−', '–' -> '-'
                else -> ch
            }
        }.joinToString("").replace(",", "").replace(" ", "")
        return normalized.toDoubleOrNull()?.takeIf(Double::isFinite)
    }

    companion object {
        private const val BASE = "https://arzdigital.com"
        private const val USER_AGENT =
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36 Chand/4.12"
    }
}
