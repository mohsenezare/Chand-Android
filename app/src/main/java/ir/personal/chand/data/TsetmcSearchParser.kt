package ir.personal.chand.data

import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

/** Defensive decoder for TSETMC instrument search; walks nested response envelopes. */
internal object TsetmcSearchParser {
    fun parse(json: String, query: String): List<MarketDescriptor> {
        val root = runCatching { JSONObject(json) }.getOrNull() ?: return emptyList()
        val q = normalize(query)
        val found = linkedMapOf<String, MarketDescriptor>()
        fun text(row: JSONObject, vararg keys: String): String? {
            keys.forEach { key ->
                val v = row.opt(key)
                if (v != null && v != JSONObject.NULL) {
                    val s = v.toString().trim()
                    if (s.isNotEmpty() && s != "null") return s
                }
            }
            return null
        }
        fun walk(value: Any?, depth: Int) {
            if (depth > 9) return
            when (value) {
                is JSONArray -> for (i in 0 until value.length()) walk(value.opt(i), depth + 1)
                is JSONObject -> {
                    val ins = text(value, "insCode", "instrumentCode", "instrumentID", "inscode", "InsCode")
                    val ticker = text(value, "lVal18AFC", "lVal18", "symbol", "instrumentName", "ticker")
                    if (!ins.isNullOrBlank() && ins.all(Char::isDigit) && !ticker.isNullOrBlank()) {
                        val company = text(value, "lVal30", "lVal30AFC", "companyName",
                            "companyNamePersian", "name", "title").orEmpty()
                        val flow = sequenceOf("flow", "flowTitle", "marketType")
                            .mapNotNull { value.opt(it)?.toString()?.toIntOrNull() }.firstOrNull() ?: 0
                        val item = MarketDescriptor(
                            id = "tsetmc:$ins", sourceKey = ins,
                            name = company.ifBlank { ticker }, code = ticker, symbol = "TSE",
                            source = MarketSource.TSETMC,
                            category = when (flow) {
                                1 -> "بورس ایران · بورس تهران"
                                2 -> "بورس ایران · فرابورس"
                                4 -> "بورس ایران · پایه"
                                else -> "بورس ایران"
                            },
                            unit = "ریال", valueScale = 1.0
                        )
                        if (q.isBlank() || normalize(item.code + item.name).contains(q)) found.putIfAbsent(ins, item)
                    }
                    val keys = value.keys()
                    while (keys.hasNext()) {
                        val child = value.opt(keys.next())
                        if (child is JSONObject || child is JSONArray) walk(child, depth + 1)
                    }
                }
            }
        }
        walk(root, 0)
        return found.values.toList()
    }

    internal fun normalize(value: String): String = value.lowercase(Locale.ROOT)
        .replace('ي', 'ی').replace('ك', 'ک').replace('ۀ', 'ه').replace('ة', 'ه')
        .replace(Regex("[\\u200c\\u200f\\u200e\\s]+"), "")
}
