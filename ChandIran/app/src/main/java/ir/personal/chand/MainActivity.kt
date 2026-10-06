package ir.personal.chand

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.*
import okhttp3.*
import org.json.*
import java.text.NumberFormat
import java.util.Locale


fun defaultMarkets():List<MarketItem> = listOf(
    MarketItem("usd","USD","دلار آمریکا",MarketGroup.CURRENCY),
    MarketItem("eur","EUR","یورو",MarketGroup.CURRENCY),
    MarketItem("gold18","طلای ۱۸","طلای ۱۸ عیار",MarketGroup.GOLD),
    MarketItem("coin","سکه","سکه امامی",MarketGroup.GOLD),
    MarketItem("btc","BTC","بیت‌کوین",MarketGroup.CRYPTO),
    MarketItem("index","شاخص کل","شاخص کل بورس",MarketGroup.INDEX),
    MarketItem("khodro","خودرو","ایران خودرو",MarketGroup.STOCK),
    MarketItem("khsa","خساپا","سایپا",MarketGroup.STOCK),
    MarketItem("foolad","فولاد","فولاد مبارکه",MarketGroup.STOCK),
    MarketItem("femeli","فملی","ملی صنایع مس ایران",MarketGroup.STOCK)
)

class MainActivity:ComponentActivity(){
    override fun onCreate(state:Bundle?){
        super.onCreate(state)
        setContent{ChandApp()}
    }
}

class MarketStore{
    private val client=OkHttpClient()
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.IO)
    var items by mutableStateOf(defaultMarkets())
        private set
    var loading by mutableStateOf(false)
        private set

    fun refresh(){
        if(loading)return
        loading=true
        scope.launch{
            val result=mutableListOf<MarketItem>()
            result.addAll(fetchTgju())
            result.addAll(fetchTsetmc())
            withContext(Dispatchers.Main){
                if(result.isNotEmpty()) items=result.distinctBy{it.id}
                loading=false
            }
        }
    }

    private fun fetchTgju():List<MarketItem>{
        val keys=listOf("price_dollar_rl","price_eur","geram18","sekke","crypto-bitcoin-usd","index_bourse")
        val url="https://api.tgju.org/v1/market/indicator/today-table-data/?keys="+keys.joinToString(",")
        return try{
            val raw=client.newCall(Request.Builder().url(url).build()).execute().use{it.body?.string().orEmpty()}
            val root=JSONObject(raw).optJSONObject("data")?:JSONObject(raw)
            val out=mutableListOf<MarketItem>()
            root.keys().forEach{key->
                val o=root.optJSONObject(key)?:return@forEach
                val price=num(o.opt("price")?:o.opt("current"))
                val previous=num(o.opt("previous"))
                val change=num(o.opt("change"))
                val percent=num(o.opt("percent"))
                val meta=when(key){
                    "price_dollar_rl"->Triple("USD","دلار آمریکا",MarketGroup.CURRENCY)
                    "price_eur"->Triple("EUR","یورو",MarketGroup.CURRENCY)
                    "geram18"->Triple("طلای ۱۸","طلای ۱۸ عیار",MarketGroup.GOLD)
                    "sekke"->Triple("سکه","سکه امامی",MarketGroup.GOLD)
                    "crypto-bitcoin-usd"->Triple("BTC","بیت‌کوین",MarketGroup.CRYPTO)
                    else->Triple("شاخص کل","شاخص کل بورس",MarketGroup.INDEX)
                }
                out.add(MarketItem(key,meta.first,meta.second,meta.third,price,previous,change,percent,
                    num(o.opt("high")),num(o.opt("low")),num(o.opt("open")),null,"TGJU",true))
            }
            out
        }catch(_:Throwable){emptyList()}
    }

    private fun fetchTsetmc():List<MarketItem>{
        val url="https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&paperTypes%5B0%5D=1&paperTypes%5B1%5D=2&paperTypes%5B2%5D=3&paperTypes%5B3%5D=4&paperTypes%5B4%5D=5&paperTypes%5B5%5D=6&paperTypes%5B6%5D=7&paperTypes%5B7%5D=8&paperTypes%5B8%5D=9&withBestLimits=false&hEven=0&RefID=0"
        return try{
            val raw=client.newCall(Request.Builder().url(url).header("User-Agent","Mozilla/5.0").build()).execute().use{it.body?.string().orEmpty()}
            val a=JSONObject(raw).optJSONArray("marketwatch")?:JSONObject(raw).optJSONArray("data")?:JSONArray()
            val out=mutableListOf<MarketItem>()
            for(i in 0 until a.length()){
                val o=a.optJSONObject(i)?:continue
                val code=o.optString("insCode").ifBlank{o.optString("instrumentId")}
                val symbol=o.optString("lVal18AFC").ifBlank{o.optString("symbol")}
                if(code.isBlank()||symbol.isBlank())continue
                val title=o.optString("lVal30").ifBlank{symbol}
                val last=num(o.opt("pDrCotVal")?:o.opt("last"))
                val previous=num(o.opt("priceYesterday")?:o.opt("prev"))
                val change=if(last!=null&&previous!=null)last-previous else null
                val percent=if(change!=null&&previous!=null&&previous!=0.0)100.0*change/previous else null
                out.add(MarketItem("tse-"+code,symbol,title,MarketGroup.STOCK,last,previous,change,percent,
                    num(o.opt("priceMax")),num(o.opt("priceMin")),num(o.opt("pf")),long(o.opt("qTotTran5J")),"TSETMC",true))
            }
            out
        }catch(_:Throwable){emptyList()}
    }

    private fun num(v:Any?):Double?=v?.toString()?.replace(",","")?.replace("%","")?.toDoubleOrNull()
    private fun long(v:Any?):Long?=v?.toString()?.replace(",","")?.toLongOrNull()
}

@Composable
fun ChandApp(){
    val store=remember{MarketStore()}
    var grid by remember{mutableStateOf(true)}
    var dark by remember{mutableStateOf(false)}
    var search by remember{mutableStateOf("")}
    var favorites by remember{mutableStateOf(false)}
    var selected by remember{mutableStateOf<MarketItem?>(null)}
    LaunchedEffect(Unit){store.refresh()}
    MaterialTheme(colorScheme=if(dark)darkColorScheme()else lightColorScheme()){
        Surface(Modifier.fillMaxSize()){
            Column(Modifier.fillMaxSize().padding(16.dp)){
                Row(verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text("Markets",fontSize=31.sp,fontWeight=FontWeight.SemiBold)
                        Text("IRAN · LIVE",fontSize=10.sp,letterSpacing=1.8.sp)
                    }
                    IconButton({favorites=!favorites}){Icon(if(favorites)Icons.Default.Star else Icons.Default.StarBorder,null)}
                    IconButton({store.refresh()}){Icon(Icons.Default.Refresh,null)}
                    IconButton({grid=!grid}){Icon(if(grid)Icons.Default.ViewList else Icons.Default.GridView,null)}
                    IconButton({dark=!dark}){Icon(if(dark)Icons.Default.LightMode else Icons.Default.DarkMode,null)}
                }
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(search,{search=it},Modifier.fillMaxWidth(),singleLine=true,
                    placeholder={Text("جست‌وجوی نماد، بازار یا ارز")},leadingIcon={Icon(Icons.Default.Search,null)},
                    shape=RoundedCornerShape(20.dp))
                Spacer(Modifier.height(10.dp))
                if(store.loading)LinearProgressIndicator(Modifier.fillMaxWidth())
                val shown=store.items.filter{(!favorites||it.favorite)&&(search.isBlank()||it.symbol.contains(search,true)||it.title.contains(search,true))}
                if(grid)LazyVerticalGrid(GridCells.Adaptive(155.dp),verticalArrangement=Arrangement.spacedBy(10.dp),horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=24.dp)){
                    items(items=shown,key={m -> m.id}) { m -> MarketCard(m){selected=m} }
                }else LazyColumn(verticalArrangement=Arrangement.spacedBy(8.dp),contentPadding=PaddingValues(bottom=24.dp)){
                    items(items=shown,key={m -> m.id}) { m -> MarketRow(m){selected=m} }
                }
            }
        }
    }
    selected?.let{MarketDetail(it){selected=null}}
}

@Composable
fun MarketCard(m:MarketItem,onClick:()->Unit){
    val up=(m.percent?:m.change?:0.0)>=0
    Card(Modifier.fillMaxWidth().clickable{onClick()},shape=RoundedCornerShape(22.dp)){
        Column(Modifier.padding(14.dp)){
            Text(m.symbol,fontWeight=FontWeight.Bold)
            Text(m.title,maxLines=1,overflow=TextOverflow.Ellipsis,fontSize=11.sp)
            Spacer(Modifier.height(13.dp))
            Text(format(m.price),fontSize=22.sp,fontWeight=FontWeight.SemiBold)
            Text(changeText(m),fontSize=12.sp,color=if(up)Color(0xFF2E8B57)else Color(0xFFD14B4B))
            Spacer(Modifier.height(10.dp))
            Text(if(m.live)"● LIVE · "+m.source else"○ —",fontSize=9.sp)
        }
    }
}

@Composable
fun MarketRow(m:MarketItem,onClick:()->Unit){
    ListItem(
        headlineContent={Text(m.symbol,fontWeight=FontWeight.Bold)},
        supportingContent={Text(m.title)},
        trailingContent={Column(horizontalAlignment=Alignment.End){Text(format(m.price),fontWeight=FontWeight.SemiBold);Text(changeText(m),fontSize=11.sp)}},
        modifier=Modifier.clickable{onClick()}
    )
}

@Composable
fun MarketDetail(m:MarketItem,close:()->Unit){
    AlertDialog(onDismissRequest=close,
        title={Column{Text(m.symbol,fontWeight=FontWeight.Bold);Text(m.title,fontSize=12.sp)}},
        text={Column{
            Text(format(m.price),fontSize=32.sp,fontWeight=FontWeight.SemiBold)
            Text(changeText(m))
            Spacer(Modifier.height(12.dp))
            DetailLine("اولین",format(m.open))
            DetailLine("کمترین",format(m.low))
            DetailLine("بیشترین",format(m.high))
            DetailLine("حجم",m.volume?.toString()?:"—")
            DetailLine("منبع",m.source)
        }},
        confirmButton={TextButton(close){Text("بستن")}})
}

@Composable
fun DetailLine(a:String,b:String){Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text(a,fontSize=12.sp);Text(b,fontWeight=FontWeight.Medium,fontSize=12.sp)}}

fun format(v:Double?):String=v?.let{NumberFormat.getNumberInstance(Locale.US).format(it)}?:"—"
fun changeText(m:MarketItem):String{
    val c=m.change?.let{format(it)}?:"—"
    val p=m.percent?.let{String.format(Locale.US,"%.2f",it)}?:"—"
    return c+"  ("+p+"%)"
}
