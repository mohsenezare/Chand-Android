package ir.personal.chand

enum class MarketGroup { CURRENCY, GOLD, CRYPTO, STOCK, INDEX }

data class MarketItem(
    val id:String,
    val symbol:String,
    val title:String,
    val group:MarketGroup,
    val price:Double?=null,
    val previous:Double?=null,
    val change:Double?=null,
    val percent:Double?=null,
    val high:Double?=null,
    val low:Double?=null,
    val open:Double?=null,
    val volume:Long?=null,
    val source:String="TGJU",
    val live:Boolean=false,
    val favorite:Boolean=false
)
