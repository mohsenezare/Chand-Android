package ir.personal.chand.data

enum class MarketSource { ARZDIGITAL, TSETMC }

enum class CatalogSource { MARKETS, STOCKS }

enum class DataOrigin { LIVE, NETWORK, CACHE, UNAVAILABLE }

enum class LiveConnectionState { CONNECTING, LIVE, POLLING, OFFLINE }

enum class HistoryRange(val label: String) {
    DAY("1D"),
    WEEK("1W"),
    MONTH("1M"),
    YEAR("1Y"),
    FIVE_YEARS("5Y"),
    ALL("All")
}

data class PricePoint(val timestampMillis: Long, val value: Double)

data class MarketDescriptor(
    val id: String,
    val sourceKey: String,
    val name: String,
    val code: String,
    val symbol: String,
    val source: MarketSource,
    val category: String,
    val unit: String,
    val valueScale: Double = 1.0
)

data class MarketItem(
    val id: String,
    val name: String,
    val code: String,
    val symbol: String,
    val price: Double,
    val change: Double,
    val changePercent: Double,
    val high: Double,
    val low: Double,
    val buy: Double,
    val sell: Double,
    val history: List<PricePoint>,
    val sourceUpdatedAtMillis: Long,
    val receivedAtMillis: Long,
    val origin: DataOrigin,
    val isAvailable: Boolean,
    val source: MarketSource = MarketSource.ARZDIGITAL,
    val category: String = "",
    val unit: String = "تومان"
)

data class MarketSnapshot(
    val updatedAt: String,
    val items: List<MarketItem>,
    val isDemo: Boolean,
    val message: String? = null
)

data class CatalogPage(
    val items: List<MarketDescriptor>,
    val hasMore: Boolean,
    val message: String? = null
)

data class HistorySeries(
    val range: HistoryRange,
    val points: List<PricePoint>,
    val message: String? = null
)

data class StreamTick(
    val sourceKey: String,
    val itemId: String,
    val price: Double,
    val high: Double,
    val low: Double,
    val open: Double,
    val change: Double,
    val changePercent: Double,
    val direction: String,
    val sourceUpdatedAtMillis: Long,
    val bid: Double? = null,
    val ask: Double? = null
)


enum class ThemeMode { SYSTEM, LIGHT, DARK }

data class UserSettings(
    val themeMode: ThemeMode = ThemeMode.SYSTEM,
    val gridMode: Boolean = true,
    val showBuyPrice: Boolean = false,
    val visibleIds: List<String> = DEFAULT_VISIBLE_IDS
)

val DEFAULT_MARKET_DESCRIPTORS = listOf(
    MarketDescriptor(
        id = "usd",
        sourceKey = "united-states-dollar",
        name = "US Dollar",
        code = "USD",
        symbol = "USD",
        source = MarketSource.ARZDIGITAL,
        category = "ارز آزاد لحظه‌ای",
        unit = "تومان",
        valueScale = 0.1
    ),
    MarketDescriptor(
        id = "euro",
        sourceKey = "euro",
        name = "Euro",
        code = "EUR",
        symbol = "EUR",
        source = MarketSource.ARZDIGITAL,
        category = "ارز آزاد",
        unit = "تومان",
        valueScale = 0.1
    ),
    MarketDescriptor(
        id = "gold18",
        sourceKey = "gold-18-karat",
        name = "Gram",
        code = "GRAM",
        symbol = "GRAM",
        source = MarketSource.ARZDIGITAL,
        category = "طلای ۱۸ عیار",
        unit = "تومان",
        valueScale = 0.1
    ),
    MarketDescriptor(
        id = "emami",
        sourceKey = "emami-coin",
        name = "Emami",
        code = "EMAMI",
        symbol = "EMAMI",
        source = MarketSource.ARZDIGITAL,
        category = "سکه امامی",
        unit = "تومان",
        valueScale = 0.1
    ),
    MarketDescriptor(
        id = "usdt",
        sourceKey = "tether",
        name = "Tether USDT",
        code = "USDT",
        symbol = "USDT",
        source = MarketSource.ARZDIGITAL,
        category = "ارز دیجیتال داخلی",
        unit = "تومان",
        valueScale = 0.1
    ),
    MarketDescriptor(
        id = "ayar",
        sourceKey = "عیار",
        name = "عیار",
        code = "عیار",
        symbol = "TSE",
        source = MarketSource.TSETMC,
        category = "بورس ایران · صندوق طلا",
        unit = "ریال",
        valueScale = 1.0
    )
)


val ARZDIGITAL_MARKET_DESCRIPTORS = listOf(
    MarketDescriptor(
        id = "tv:BITSTAMP:BTCUSD",
        sourceKey = "bitcoin",
        name = "Bitcoin",
        code = "BTC/USD",
        symbol = "CRYPTO",
        source = MarketSource.ARZDIGITAL,
        category = "ارز دیجیتال جهانی",
        unit = "دلار"
    ),
    MarketDescriptor(
        id = "tv:BITSTAMP:ETHUSD",
        sourceKey = "ethereum",
        name = "Ethereum",
        code = "ETH/USD",
        symbol = "CRYPTO",
        source = MarketSource.ARZDIGITAL,
        category = "ارز دیجیتال جهانی",
        unit = "دلار"
    ),
    MarketDescriptor(
        id = "tv:FX:EURUSD",
        sourceKey = "euro",
        name = "EUR/USD",
        code = "EUR/USD",
        symbol = "FX",
        source = MarketSource.ARZDIGITAL,
        category = "فارکس جهانی",
        unit = "دلار"
    ),
    MarketDescriptor(
        id = "tv:FX:GBPUSD",
        sourceKey = "british-pound-sterling",
        name = "GBP/USD",
        code = "GBP/USD",
        symbol = "FX",
        source = MarketSource.ARZDIGITAL,
        category = "فارکس جهانی",
        unit = "دلار"
    ),
    MarketDescriptor(
        id = "tv:FX:USDJPY",
        sourceKey = "japanese-yen",
        name = "USD/JPY",
        code = "USD/JPY",
        symbol = "FX",
        source = MarketSource.ARZDIGITAL,
        category = "فارکس جهانی",
        unit = "ین"
    ),
    MarketDescriptor(
        id = "tv:OANDA:XAUUSD",
        sourceKey = "gold",
        name = "Gold Spot",
        code = "XAU/USD",
        symbol = "GOLD",
        source = MarketSource.ARZDIGITAL,
        category = "طلای جهانی",
        unit = "دلار"
    ),
    MarketDescriptor(
        id = "tv:OANDA:XAGUSD",
        sourceKey = "silver",
        name = "Silver Spot",
        code = "XAG/USD",
        symbol = "SILVER",
        source = MarketSource.ARZDIGITAL,
        category = "نقره جهانی",
        unit = "دلار"
    ),
    MarketDescriptor(
        id = "tv:TVC:UKOIL",
        sourceKey = "brent-oil-derivatives",
        name = "Brent Oil",
        code = "BRENT",
        symbol = "OIL",
        source = MarketSource.ARZDIGITAL,
        category = "انرژی جهانی",
        unit = "دلار"
    ),
    MarketDescriptor(
        id = "tv:TVC:USOIL",
        sourceKey = "crude-oil-derivatives",
        name = "WTI Oil",
        code = "WTI",
        symbol = "OIL",
        source = MarketSource.ARZDIGITAL,
        category = "انرژی جهانی",
        unit = "دلار"
    )
)

val DEFAULT_VISIBLE_IDS = listOf("usd", "euro", "gold18", "emami")

val LEGACY_DEFAULT_VISIBLE_IDS = listOf(
    "usd", "usdt", "gold_world", "gold18", "silver", "brent", "bourse"
)
