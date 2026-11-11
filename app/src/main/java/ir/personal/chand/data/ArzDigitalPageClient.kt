package ir.personal.chand.data

import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.util.Locale
import java.util.concurrent.TimeUnit

/**
 * Public-page quote reader for ArzDigital.
 *
 * This intentionally does not call undocumented/private APIs. It reads the public
 * asset page and accepts a quote only when both a positive price and an explicit
 * asset identity are present. Page receipt time is not treated as source quote time.
 */
internal class ArzDigitalPageClient(
    private val http: OkHttpClient = OkHttpClient.Builder()
        .callTimeout(15, TimeUnit.SECONDS)
        .connectTimeout(7, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()
) {
    data class Quote(
        val slug: String,
        val priceUsd: Double?,
        val priceToman: Double?,
        val changePercent24h: Double?,
        val sourceUpdatedAtMillis: Long = 0L
    )

    fun fetch(slug: String): Quote {
        require(slug.matches(Regex("[a-z0-9-]{2,100}"))) { "Invalid ArzDigital asset slug" }
        val url = "https://arzdigital.com/coins/$slug/"
        val request = Request.Builder()
            .url(url)
            .header("User-Agent", USER_AGENT)
            .header("Accept", "text/html,application/xhtml+xml")
            .header("Cache-Control", "no-cache")
            .build()
        val html = http.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IOException("ArzDigital HTTP ${response.code}")
            response.body?.string()?.takeIf { it.length > 2_000 }
                ?: throw IOException("ArzDigital empty page")
        }
        return parse(slug, html)
    }

    internal fun parse(slug: String, html: String): Quote {
        val normalized = html
            .replace("&nbsp;", " ")
            .replace("&#160;", " ")
            .replace("&quot;", "\"")
        val plain = normalized
            .replace(Regex("(?is)<script[^>]*>.*?</script>"), " ")
            .replace(Regex("(?is)<style[^>]*>.*?</style>"), " ")
            .replace(Regex("(?s)<[^>]+>"), " ")
            .replace(Regex("\\s+"), " ")

        val title = first(
            Regex("(?is)<h1[^>]*>(.*?)</h1>").find(normalized)?.groupValues?.getOrNull(1)
                ?.replace(Regex("<[^>]+>"), " "),
            Regex("(?is)<title[^>]*>(.*?)</title>").find(normalized)?.groupValues?.getOrNull(1)
        ).orEmpty()
        if (!title.contains(slug.substringBefore("-derivatives").replace('-', ' '), true) &&
            !plain.contains("قیمت", true)) {
            throw IOException("ArzDigital asset identity not verified")
        }

        val dollar = Regex("""\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)""")
            .find(plain)?.groupValues?.getOrNull(1)?.toDoubleOrNull()
        val toman = Regex("""([۰-۹0-9][۰-۹0-9,]*(?:\.[۰-۹0-9]+)?)\s*تومان""")
            .find(plain)?.groupValues?.getOrNull(1)?.let(::parseLocalized)
            ?: Regex("""([۰-۹0-9][۰-۹0-9,]*(?:\.[۰-۹0-9]+)?)\s*ت""")
                .find(plain)?.groupValues?.getOrNull(1)?.let(::parseLocalized)
        val percent = Regex("""([+−-]?\s*[۰-۹0-9]+(?:\.[۰-۹0-9]+)?)\s*%""")
            .find(plain)?.groupValues?.getOrNull(1)?.let(::parseLocalized)
        if ((dollar == null || dollar <= 0.0) && (toman == null || toman <= 0.0)) {
            throw IOException("No valid positive ArzDigital quote found")
        }
        return Quote(slug, dollar?.takeIf { it > 0.0 }, toman?.takeIf { it > 0.0 }, percent)
    }

    private fun parseLocalized(raw: String): Double? {
        val latin = raw.trim()
            .replace('٬', ',')
            .replace('٫', '.')
            .map { ch -> when (ch) {
                in '۰'..'۹' -> ('0'.code + ch.code - '۰'.code).toChar()
                in '٠'..'٩' -> ('0'.code + ch.code - '٠'.code).toChar()
                '−' -> '-'
                else -> ch
            } }.joinToString("")
            .replace(",", "")
            .replace(" ", "")
        return latin.toDoubleOrNull()?.takeIf { it.isFinite() && it > 0.0 }
    }

    private fun first(vararg values: String?): String? = values.firstOrNull { !it.isNullOrBlank() }

    companion object {
        private const val USER_AGENT =
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36 Chand/4.12"
    }
}
