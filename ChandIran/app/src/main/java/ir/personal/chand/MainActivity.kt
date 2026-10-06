package ir.personal.chand

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.*
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.text.NumberFormat
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

fun defaultMarkets(): List<MarketItem> = listOf(
    MarketItem("usd", "USD", "دلار آمریکا", MarketGroup.CURRENCY),
    MarketItem("eur", "EUR", "یورو", MarketGroup.CURRENCY),
    MarketItem("gold18", "طلای ۱۸", "طلای ۱۸ عیار", MarketGroup.GOLD),
    MarketItem("coin", "سکه", "سکه امامی", MarketGroup.GOLD),
    MarketItem("btc", "BTC", "بیت‌کوین", MarketGroup.CRYPTO),
    MarketItem("index", "شاخص کل", "شاخص کل بورس", MarketGroup.INDEX)
)

class MainActivity : ComponentActivity() {
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        setContent { ChandApp(applicationContext) }
    }
}

enum class ConnectionState { LIVE, STALE, OFFLINE }

class MarketStore(context: Context) {
    private val client = OkHttpClient()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val prefs = context.getSharedPreferences("chand_market_order", Context.MODE_PRIVATE)
    var items by mutableStateOf(defaultMarkets())
        private set
    var loading by mutableStateOf(false)
        private set
    var lastUpdated by mutableStateOf<Long?>(null)
        private set
    var connectionState by mutableStateOf(ConnectionState.OFFLINE)
        private set
    private var liveJob: Job? = null

    init { startLive() }

    private fun startLive() {
        if (liveJob?.isActive == true) return
        liveJob = scope.launch {
            while (isActive) {
                syncOnce()
                delay(1500)
            }
        }
    }

    fun refreshNow() {
        if (loading) return
        scope.launch { syncOnce() }
    }

    fun moveItem(id: String, direction: Int) {
        val list = items.toMutableList()
        val from = list.indexOfFirst { it.id == id }
        val to = from + direction
        if (from < 0 || to !in list.indices) return
        val item = list.removeAt(from)
        list.add(to, item)
        items = list
        prefs.edit().putString("order", list.joinToString(",") { it.id }).apply()
    }

    private suspend fun syncOnce() {
        withContext(Dispatchers.Main) { loading = true }
        val result = coroutineScope {
            val a = async { fetchTgju() }
            val b = async { fetchTsetmc() }
            runCatching { a.await() + b.await() }.getOrElse { emptyList() }
        }
        withContext(Dispatchers.Main) {
            if (result.isNotEmpty()) {
                val fresh = result.associateBy { it.id }
                val saved = prefs.getString("order", "").orEmpty().split(",").filter { it.isNotBlank() }
                val ordered = mutableListOf<MarketItem>()
                saved.forEach { id -> fresh[id]?.let { ordered += it } }
                result.forEach { if (ordered.none { x -> x.id == it.id }) ordered += it }
                items = ordered
                lastUpdated = System.currentTimeMillis()
                connectionState = ConnectionState.LIVE
            } else if (lastUpdated == null) {
                connectionState = ConnectionState.OFFLINE
            } else if (System.currentTimeMillis() - lastUpdated!! > 7000) {
                connectionState = ConnectionState.STALE
            }
            loading = false
        }
    }

    private fun fetchTgju(): List<MarketItem> {
        val keys = listOf("price_dollar_rl","price_eur","geram18","sekke","crypto-bitcoin-usd","index_bourse")
        val url = "https://api.tgju.org/v1/market/indicator/today-table-data/?keys=" + keys.joinToString(",")
        return try {
            val raw = client.newCall(Request.Builder().url(url).build()).execute().use { it.body?.string().orEmpty() }
            val root = JSONObject(raw).optJSONObject("data") ?: JSONObject(raw)
            val out = mutableListOf<MarketItem>()
            root.keys().forEach { key ->
                val o = root.optJSONObject(key) ?: return@forEach
                val meta = when (key) {
                    "price_dollar_rl" -> Triple("USD","دلار آمریکا",MarketGroup.CURRENCY)
                    "price_eur" -> Triple("EUR","یورو",MarketGroup.CURRENCY)
                    "geram18" -> Triple("طلای ۱۸","طلای ۱۸ عیار",MarketGroup.GOLD)
                    "sekke" -> Triple("سکه","سکه امامی",MarketGroup.GOLD)
                    "crypto-bitcoin-usd" -> Triple("BTC","بیت‌کوین",MarketGroup.CRYPTO)
                    else -> Triple("شاخص کل","شاخص کل بورس",MarketGroup.INDEX)
                }
                val price = num(o.opt("price") ?: o.opt("current"))
                val prev = num(o.opt("previous"))
                val change = num(o.opt("change"))
                out += MarketItem(key,meta.first,meta.second,meta.third,price,prev,change,num(o.opt("percent")),num(o.opt("high")),num(o.opt("low")),num(o.opt("open")),null,"TGJU",true)
            }
            out
        } catch (_: Throwable) { emptyList() }
    }

    private fun fetchTsetmc(): List<MarketItem> {
        val url = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&paperTypes%5B0%5D=1&paperTypes%5B1%5D=2&paperTypes%5B2%5D=3&paperTypes%5B3%5D=4&paperTypes%5B4%5D=5&paperTypes%5B5%5D=6&paperTypes%5B6%5D=7&paperTypes%5B7%5D=8&paperTypes%5B8%5D=9&withBestLimits=false&hEven=0&RefID=0"
        return try {
            val raw = client.newCall(Request.Builder().url(url).header("User-Agent","Mozilla/5.0").build()).execute().use { it.body?.string().orEmpty() }
            val root = JSONObject(raw)
            val a = root.optJSONArray("marketwatch") ?: root.optJSONArray("data") ?: JSONArray()
            val out = ArrayList<MarketItem>(a.length())
            for (i in 0 until a.length()) {
                val o = a.optJSONObject(i) ?: continue
                val code = o.optString("insCode").ifBlank { o.optString("instrumentId") }
                val symbol = o.optString("lVal18AFC").ifBlank { o.optString("symbol") }
                if (code.isBlank() || symbol.isBlank()) continue
                val title = o.optString("lVal30").ifBlank { symbol }
                val last = num(o.opt("pDrCotVal") ?: o.opt("last"))
                val prev = num(o.opt("priceYesterday") ?: o.opt("prev"))
                val change = if (last != null && prev != null) last - prev else null
                val pct = if (change != null && prev != null && prev != 0.0) 100.0 * change / prev else null
                out += MarketItem("tse-"+code,symbol,title,MarketGroup.STOCK,last,prev,change,pct,num(o.opt("priceMax")),num(o.opt("priceMin")),num(o.opt("pf")),long(o.opt("qTotTran5J")),"TSETMC",true)
            }
            out
        } catch (_: Throwable) { emptyList() }
    }

    private fun num(v: Any?): Double? = v?.toString()?.replace(",","")?.replace("%","")?.toDoubleOrNull()
    private fun long(v: Any?): Long? = v?.toString()?.replace(",","")?.toLongOrNull()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChandApp(context: Context) {
    val store = remember { MarketStore(context) }
    var dark by remember { mutableStateOf(false) }
    var search by remember { mutableStateOf("") }
    var selected by remember { mutableStateOf<MarketItem?>(null) }
    var draggingId by remember { mutableStateOf<String?>(null) }
    val pullState = rememberPullToRefreshState()
    val shown = store.items.filter { search.isBlank() || it.symbol.contains(search,true) || it.title.contains(search,true) }

    MaterialTheme(colorScheme = if (dark) darkColorScheme() else lightColorScheme()) {
        Surface(Modifier.fillMaxSize()) {
            Column(Modifier.fillMaxSize().padding(horizontal=16.dp)) {
                Spacer(Modifier.height(12.dp))
                Row(verticalAlignment=Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Markets",fontSize=31.sp,fontWeight=FontWeight.SemiBold)
                        Text(statusText(store.connectionState,store.lastUpdated),fontSize=10.sp,letterSpacing=1.1.sp)
                    }
                    IconButton({store.refreshNow()}) { Icon(Icons.Default.Refresh,null) }
                    IconButton({dark=!dark}) { Icon(if(dark) Icons.Default.LightMode else Icons.Default.DarkMode,null) }
                }
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(value=search,onValueChange={search=it},modifier=Modifier.fillMaxWidth(),singleLine=true,placeholder={Text("جست‌وجوی نماد، بازار یا ارز")},leadingIcon={Icon(Icons.Default.Search,null)},shape=RoundedCornerShape(20.dp))
                Spacer(Modifier.height(8.dp))
                PullToRefreshBox(isRefreshing=store.loading,onRefresh={store.refreshNow()},state=pullState,modifier=Modifier.fillMaxSize()) {
                    LazyColumn(verticalArrangement=Arrangement.spacedBy(8.dp),contentPadding=PaddingValues(top=4.dp,bottom=28.dp)) {
                        items(shown,key={it.id}) { m ->
                            var dragDistance by remember(m.id) { mutableFloatStateOf(0f) }
                            MarketCard(m,draggingId==m.id,Modifier.fillMaxWidth().pointerInput(m.id,shown.size) {
                                detectDragGesturesAfterLongPress(onDragStart={draggingId=m.id;dragDistance=0f},onDragCancel={draggingId=null;dragDistance=0f},onDragEnd={draggingId=null;dragDistance=0f},onDrag={change,amount ->
                                    change.consume(); dragDistance += amount.y
                                    if(dragDistance > 72f){store.moveItem(m.id,1);dragDistance=0f}
                                    else if(dragDistance < -72f){store.moveItem(m.id,-1);dragDistance=0f}
                                })
                            }) { selected=m }
                        }
                    }
                }
            }
        }
    }
    selected?.let { MarketDetail(it){selected=null} }
}

@Composable
fun MarketCard(m:MarketItem,dragging:Boolean,modifier:Modifier=Modifier,onClick:()->Unit) {
    val up = (m.percent ?: m.change ?: 0.0) >= 0
    Card(modifier.clickable{onClick()},shape=RoundedCornerShape(22.dp),elevation=CardDefaults.cardElevation(if(dragging)8.dp else 2.dp)) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment=Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) { Text(m.symbol,fontWeight=FontWeight.Bold); Text(m.title,maxLines=1,overflow=TextOverflow.Ellipsis,fontSize=11.sp) }
                Icon(Icons.Default.DragHandle,"جابجایی",tint=MaterialTheme.colorScheme.outline)
            }
            Spacer(Modifier.height(13.dp)); Text(format(m.price),fontSize=22.sp,fontWeight=FontWeight.SemiBold)
            Text(changeText(m),fontSize=12.sp,color=if(up) Color(0xFF2E8B57) else Color(0xFFD14B4B))
            Spacer(Modifier.height(10.dp)); Text("● "+m.source+" · LIVE",fontSize=9.sp,color=MaterialTheme.colorScheme.primary)
        }
    }
}

@Composable
fun MarketDetail(m:MarketItem,close:()->Unit) {
    AlertDialog(onDismissRequest=close,title={Column{Text(m.symbol,fontWeight=FontWeight.Bold);Text(m.title,fontSize=12.sp)}},text={Column{Text(format(m.price),fontSize=32.sp,fontWeight=FontWeight.SemiBold);Text(changeText(m));Spacer(Modifier.height(12.dp));DetailLine("اولین",format(m.open));DetailLine("کمترین",format(m.low));DetailLine("بیشترین",format(m.high));DetailLine("حجم",m.volume?.toString() ?: "—");DetailLine("منبع",m.source)}},confirmButton={TextButton(close){Text("بستن")}})
}

@Composable
fun DetailLine(a:String,b:String){Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text(a,fontSize=12.sp);Text(b,fontWeight=FontWeight.Medium,fontSize=12.sp)}}
fun statusText(s:ConnectionState,t:Long?):String { val time=t?.let{SimpleDateFormat("HH:mm:ss",Locale.US).format(Date(it))} ?: "--:--:--"; return when(s){ConnectionState.LIVE->"IRAN · LIVE · "+time;ConnectionState.STALE->"IRAN · STALE · "+time;ConnectionState.OFFLINE->"IRAN · OFFLINE"} }
fun format(v:Double?):String=v?.let{NumberFormat.getNumberInstance(Locale.US).format(it)} ?: "—"
fun changeText(m:MarketItem):String { val c=m.change?.let{format(it)} ?: "—"; val p=m.percent?.let{String.format(Locale.US,"%.2f",it)} ?: "—"; return c+"  ("+p+"%)" }
