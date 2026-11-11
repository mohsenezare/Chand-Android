package ir.personal.chand

import ir.personal.chand.data.MarketSource

import coil.compose.SubcomposeAsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URLEncoder
import java.net.URL
import java.nio.charset.StandardCharsets
import java.util.concurrent.ConcurrentHashMap
import android.os.Bundle
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.GridView
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.ViewAgenda
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.produceState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ir.personal.chand.data.CatalogSource
import ir.personal.chand.data.DataOrigin
import ir.personal.chand.data.HistoryRange
import ir.personal.chand.data.LiveConnectionState
import ir.personal.chand.data.MarketDescriptor
import ir.personal.chand.data.MarketItem
import ir.personal.chand.data.PricePoint
import ir.personal.chand.data.ThemeMode
import ir.personal.chand.ui.ChandTheme
import ir.personal.chand.ui.MarketFormatting
import ir.personal.chand.ui.PersianDateTime
import java.time.ZoneId
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlinx.coroutines.delay

private val ChandCard = Color(0xFF1C1C1E)
private val ChandMuted = Color(0xFFA8A8AD)
private val ChandUp = Color(0xFF57B97D)
private val ChandDown = Color(0xFFE45C61)
private val TehranZone = ZoneId.of("Asia/Tehran")

class MainActivity : ComponentActivity() {
    private val viewModel by viewModels<MainViewModel>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val state by viewModel.uiState.collectAsStateWithLifecycle()
            ChandTheme(state.settings.themeMode) {
                ChandApp(state, viewModel)
            }
        }
    }

    override fun onStart() {
        super.onStart()
        viewModel.startPolling()
    }

    override fun onStop() {
        viewModel.stopPolling()
        super.onStop()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ChandApp(state: ChandUiState, viewModel: MainViewModel) {
    var settingsOpen by remember { mutableStateOf(false) }
    var manageOpen by remember { mutableStateOf(false) }

    Surface(color = MaterialTheme.colorScheme.background, modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
        ) {
            ChandHeader(state.connectionState)
            // Provider/status notes are intentionally hidden to match the clean Chand UI.

            Box(modifier = Modifier.weight(1f)) {
                when {
                    state.loading && state.snapshot == null -> CircularProgressIndicator(
                        color = ChandMuted,
                        strokeWidth = 2.dp,
                        modifier = Modifier.align(Alignment.Center)
                    )
                    state.visibleItems.isEmpty() -> EmptyState {
                        viewModel.loadCatalog(CatalogSource.MARKETS)
                        manageOpen = true
                    }
                    else -> MarketGrid(
                        items = state.visibleItems,
                        gridMode = state.settings.gridMode,
                        onItemClick = { viewModel.showChart(it.id) },
                        onMove = viewModel::moveVisibleItem,
                        isRefreshing = state.pullRefreshing,
                        onPullRefresh = viewModel::pullToRefresh
                    )
                }

                if (state.pullRefreshing) {
                    val refreshLightMode = MaterialTheme.colorScheme.background.luminance() > 0.5f
                    Surface(
                        color = if (refreshLightMode) Color(0xFFFDFDFC) else Color(0xFF252527),
                        contentColor = if (refreshLightMode) Color(0xFF111113) else Color.White,
                        shape = RoundedCornerShape(999.dp),
                        shadowElevation = 6.dp,
                        modifier = Modifier
                            .align(Alignment.TopCenter)
                            .padding(top = 10.dp)
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 9.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            CircularProgressIndicator(
                                color = if (refreshLightMode) Color(0xFF5E5E63) else Color(0xFFD0D0D4),
                                strokeWidth = 2.dp,
                                modifier = Modifier.size(17.dp)
                            )
                            Text(
                                text = "در حال بروزرسانی…",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold,
                                maxLines = 1
                            )
                        }
                    }
                }
            }

            ControlBar(
                gridMode = state.settings.gridMode,
                onAdd = {
                    viewModel.loadCatalog(CatalogSource.MARKETS)
                    manageOpen = true
                },
                onToggleLayout = { viewModel.setGridMode(!state.settings.gridMode) },
                onSettings = { settingsOpen = true }
            )
        }
    }

    val chartItem = state.chart.itemId?.let { id ->
        state.snapshot?.items?.firstOrNull { it.id == id }
    }
    if (chartItem != null) {
        PriceDetails(
            item = chartItem,
            chart = state.chart,
            onRange = viewModel::changeChartRange,
            onDismiss = viewModel::clearChart
        )
    }

    if (settingsOpen) {
        SettingsDialog(
            state = state,
            onDismiss = { settingsOpen = false },
            onTheme = viewModel::setTheme,
            onGrid = viewModel::setGridMode,
            onUpdateIranMarket = viewModel::updateIranMarketCatalog,
            onUpdateIranStock = viewModel::updateIranStockCatalog,
            onUpdateGlobalMarket = viewModel::updateGlobalMarketCatalog,
            onManage = {
                settingsOpen = false
                viewModel.loadCatalog(CatalogSource.MARKETS)
                manageOpen = true
            }
        )
    }

    if (manageOpen) {
        ManageItemsDialog(
            state = state,
            onSearch = viewModel::loadCatalog,
            onLoadMore = {
                viewModel.loadCatalog(
                    state.catalogSource,
                    state.catalogQuery,
                    loadMore = true
                )
            },
            onSave = {
                viewModel.setVisibleIds(it)
                manageOpen = false
            },
            onDismiss = { manageOpen = false }
        )
    }
}

@Composable
private fun ChandHeader(connectionState: LiveConnectionState) {
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) {
        while (true) {
            now = System.currentTimeMillis()
            delay(15_000L)
        }
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 18.dp, end = 20.dp, top = 12.dp, bottom = 14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = "Chand?!",
            color = MaterialTheme.colorScheme.onBackground,
            fontSize = 43.sp,
            lineHeight = 46.sp,
            fontWeight = FontWeight.Black,
            letterSpacing = (-1.8).sp
        )
        Spacer(Modifier.weight(1f))
        StatusDot(connectionState)
        Spacer(Modifier.width(8.dp))
        Text(
            text = PersianDateTime.format(now, TehranZone),
            color = ChandMuted,
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.End,
            maxLines = 1
        )
    }
}

@Composable
private fun StatusDot(state: LiveConnectionState) {
    val color = when (state) {
        LiveConnectionState.LIVE -> Color(0xFF56C98D)
        LiveConnectionState.CONNECTING -> Color(0xFFE9B44C)
        LiveConnectionState.POLLING -> Color(0xFFE9B44C)
        LiveConnectionState.OFFLINE -> ChandDown
    }
    Box(
        Modifier
            .size(7.dp)
            .background(color, CircleShape)
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MarketGrid(
    items: List<MarketItem>,
    gridMode: Boolean,
    onItemClick: (MarketItem) -> Unit,
    onMove: (String, Int) -> Unit,
    isRefreshing: Boolean,
    onPullRefresh: () -> Unit
) {
    val gridState = rememberLazyGridState()

    PullToRefreshBox(
        isRefreshing = isRefreshing,
        onRefresh = onPullRefresh,
        modifier = Modifier.fillMaxSize()
    ) {
        LazyVerticalGrid(
            columns = GridCells.Fixed(if (gridMode) 2 else 1),
            state = gridState,
            contentPadding = PaddingValues(start = 14.dp, end = 14.dp, top = 4.dp, bottom = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
            modifier = Modifier
                .fillMaxSize()
                .background(
                    if (MaterialTheme.colorScheme.background.luminance() > 0.5f)
                        Color(0xFFE7E6E3)
                    else
                        Color.Transparent
                )
        ) {
            items(items, key = MarketItem::id) { item ->
                var dragOffset by remember(item.id) { mutableStateOf(Offset.Zero) }
                MarketCard(
                    item = item,
                    gridMode = gridMode,
                    modifier = Modifier
                        .fillMaxWidth()
                        .then(
                            if (gridMode) Modifier.aspectRatio(1.04f)
                            else Modifier.heightIn(min = 220.dp)
                        )
                        .pointerInput(item.id, gridMode) {
                            detectDragGesturesAfterLongPress(
                                onDragStart = { dragOffset = Offset.Zero },
                                onDragCancel = { dragOffset = Offset.Zero },
                                onDragEnd = { dragOffset = Offset.Zero },
                                onDrag = { change, amount ->
                                    change.consume()
                                    dragOffset += amount

                                    val horizontalThreshold = size.width * 0.32f
                                    val verticalThreshold = size.height * 0.32f

                                    if (gridMode) {
                                        when {
                                            dragOffset.x > horizontalThreshold -> {
                                                onMove(item.id, 1)
                                                dragOffset = Offset.Zero
                                            }
                                            dragOffset.x < -horizontalThreshold -> {
                                                onMove(item.id, -1)
                                                dragOffset = Offset.Zero
                                            }
                                            dragOffset.y > verticalThreshold -> {
                                                onMove(item.id, 2)
                                                dragOffset = Offset.Zero
                                            }
                                            dragOffset.y < -verticalThreshold -> {
                                                onMove(item.id, -2)
                                                dragOffset = Offset.Zero
                                            }
                                        }
                                    } else {
                                        when {
                                            dragOffset.y > verticalThreshold -> {
                                                onMove(item.id, 1)
                                                dragOffset = Offset.Zero
                                            }
                                            dragOffset.y < -verticalThreshold -> {
                                                onMove(item.id, -1)
                                                dragOffset = Offset.Zero
                                            }
                                        }
                                    }
                                }
                            )
                        },
                    onClick = { onItemClick(item) }
                )
            }
        }
    }
}

@Composable
private fun MarketCard(
    item: MarketItem,
    gridMode: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    val lightMode = MaterialTheme.colorScheme.background.luminance() > 0.5f
    Card(
        onClick = onClick,
        shape = RoundedCornerShape(if (gridMode) 28.dp else 24.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (lightMode) Color(0xFFFDFDFC) else ChandCard
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = if (lightMode) 6.dp else 0.dp),
        modifier = modifier
    ) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val compact = maxWidth < 185.dp
            val priceText = MarketFormatting.price(item)
            val changeText = MarketFormatting.change(item)
            val longName = item.name.length > if (compact) 11 else 16
            val nameFontSize = when {
                compact && longName -> 13.sp
                compact -> 15.sp
                longName -> 17.sp
                else -> 20.sp
            }
            val priceFontSize = when {
                compact && priceText.length >= 16 -> 19.sp
                compact && priceText.length >= 13 -> 22.sp
                compact && priceText.length >= 10 -> 25.sp
                compact -> 29.sp
                priceText.length >= 18 -> 29.sp
                priceText.length >= 15 -> 33.sp
                priceText.length >= 12 -> 36.sp
                else -> 40.sp
            }
            val changeFontSize = when {
                compact && changeText.length >= 9 -> 14.sp
                compact -> 16.sp
                changeText.length >= 11 -> 18.sp
                else -> 21.sp
            }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(if (compact) 13.dp else 17.dp),
                verticalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.Top
                ) {
                    MarketCardBadge(item, Modifier.size(if (compact) 43.dp else 52.dp))
                    Spacer(Modifier.width(if (compact) 9.dp else 12.dp))
                    Column(
                        modifier = Modifier.weight(1f),
                        horizontalAlignment = Alignment.End
                    ) {
                        Text(
                            text = item.name,
                            color = if (lightMode) Color(0xFF111111) else Color.White,
                            fontSize = nameFontSize,
                            lineHeight = if (compact) 16.sp else 20.sp,
                            fontWeight = FontWeight.Bold,
                            textAlign = TextAlign.End,
                            maxLines = 1,
                            softWrap = false,
                            overflow = TextOverflow.Ellipsis
                        )
                        Spacer(Modifier.height(3.dp))
                        Text(
                            text = item.code,
                            color = if (lightMode) Color(0xFF8D8D92) else ChandMuted,
                            fontSize = if (compact) 11.sp else 13.sp,
                            fontWeight = FontWeight.SemiBold,
                            textAlign = TextAlign.End,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Spacer(Modifier.height(4.dp))
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(if (compact) 4.dp else 6.dp)
                        ) {
                            MarketStatusLabel(item, compact)
                            Text(
                                text = compactPercent(item),
                                color = percentColor(item),
                                fontSize = if (compact) 8.sp else 10.sp,
                                lineHeight = if (compact) 9.sp else 11.sp,
                                fontWeight = FontWeight.SemiBold,
                                maxLines = 1
                            )
                        }
                    }
                }

                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(
                            top = if (compact) 8.dp else 10.dp,
                            bottom = if (compact) 6.dp else 8.dp
                        )
                ) {
                    Text(
                        text = changeText,
                        color = trendColor(item),
                        fontSize = changeFontSize,
                        lineHeight = if (compact) 17.sp else 22.sp,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                        softWrap = false,
                        overflow = TextOverflow.Clip
                    )
                    Spacer(Modifier.height(if (compact) 4.dp else 6.dp))
                    Text(
                        text = priceText,
                        color = if (item.isAvailable) {
                        if (lightMode) Color(0xFF050505) else Color.White
                    } else {
                        if (lightMode) Color(0xFF9A9A9E) else ChandMuted
                    },
                        fontSize = priceFontSize,
                        lineHeight = priceFontSize * 1.14f,
                        fontWeight = FontWeight.Black,
                        letterSpacing = (-0.55).sp,
                        maxLines = 1,
                        softWrap = false,
                        overflow = TextOverflow.Clip
                    )
                }
            }
        }
    }
}

private fun trendColor(item: MarketItem): Color = when {
    !item.isAvailable || item.change == 0.0 -> ChandMuted
    item.change > 0.0 -> ChandUp
    else -> ChandDown
}

private fun percentColor(item: MarketItem): Color = when {
    !item.isAvailable || item.changePercent == 0.0 -> ChandMuted
    item.changePercent > 0.0 -> ChandUp
    else -> ChandDown
}

private fun compactPercent(item: MarketItem): String {
    val value = item.changePercent
    if (!value.isFinite()) return "0.00%"
    return java.lang.String.format(
        java.util.Locale.US,
        if (value > 0.0) "+%.2f%%" else "%.2f%%",
        value
    )
}

@Composable
private fun MarketStatusLabel(item: MarketItem, compact: Boolean) {
    if (isMarketLive(item)) {
        Surface(
            color = Color(0xFF173A2C),
            shape = RoundedCornerShape(5.dp)
        ) {
            Text(
                text = "LIVE",
                color = ChandUp,
                fontSize = if (compact) 7.sp else 8.sp,
                lineHeight = if (compact) 8.sp else 9.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.35.sp,
                modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp)
            )
        }
    } else {
        Text(
            text = "CLOSED",
            color = ChandMuted,
            fontSize = if (compact) 7.sp else 8.sp,
            lineHeight = if (compact) 8.sp else 9.sp,
            fontWeight = FontWeight.Medium,
            letterSpacing = 0.25.sp,
            maxLines = 1
        )
    }
}

private fun isMarketLive(item: MarketItem): Boolean {
    if (!item.isAvailable || item.sourceUpdatedAtMillis <= 0L) return false
    val age = (System.currentTimeMillis() - item.sourceUpdatedAtMillis).coerceAtLeast(0L)

    return when (item.source) {
        MarketSource.ARZDIGITAL -> age <= 5L * 60L * 1000L
        MarketSource.TSETMC -> age <= 30L * 60L * 1000L
    }
}

@Composable
private fun MarketCardBadge(item: MarketItem, modifier: Modifier = Modifier) {
    // Existing bespoke Chand icons for currencies, metals, crypto and global
    // instruments are already symbol-specific. Replace only the generic TSETMC
    // stock/fund badge with a real issuer/fund icon when one can be resolved.
    if (item.source != ir.personal.chand.data.MarketSource.TSETMC) {
        MarketBadge(item, modifier)
        return
    }

    val logoState = androidx.compose.runtime.produceState<Bitmap?>(
        initialValue = null,
        key1 = item.id,
        key2 = item.code
    ) {
        value = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
            TsetmcCardLogoResolver.load(item)
        }
    }

    val logo = logoState.value
    if (logo != null) {
        Surface(
            modifier = modifier,
            shape = CircleShape,
            color = Color(0xFF25262A),
            border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF555862))
        ) {
            Image(
                bitmap = logo.asImageBitmap(),
                contentDescription = item.name,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(3.dp),
                contentScale = ContentScale.Fit
            )
        }
    } else {
        // Symbol-specific fallback: never show the old generic stock/category
        // artwork on a market card when no remote issuer icon is available.
        val badgeText = item.code
            .trim()
            .ifBlank { item.name.trim() }
            .take(3)

        Surface(
            modifier = modifier,
            shape = CircleShape,
            color = Color(0xFF25262A),
            border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF5B5E66))
        ) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = badgeText,
                    color = Color(0xFFE7E8EA),
                    fontSize = when (badgeText.length) {
                        0, 1 -> 15.sp
                        2 -> 12.sp
                        else -> 10.sp
                    },
                    lineHeight = 13.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1
                )
            }
        }
    }
}

private object TsetmcCardLogoResolver {
    private val bitmapCache = java.util.concurrent.ConcurrentHashMap<String, Bitmap>()
    private val failed = java.util.concurrent.ConcurrentHashMap.newKeySet<String>()

    // A few high-confidence issuer domains make common symbols instant; every
    // other TSETMC symbol is resolved dynamically from Fund/Codal metadata.
    private val knownDomains = mapOf(
        "وپارس" to "parsian-bank.ir",
        "عیار" to "emofid.com",
        "وبملت" to "bankmellat.ir",
        "وتجارت" to "tejaratbank.ir",
        "وبصادر" to "bsi.ir",
        "وپاسار" to "bpi.ir",
        "فولاد" to "msc.ir",
        "فملی" to "nicico.com",
        "خودرو" to "ikco.ir",
        "خساپا" to "saipacorp.com"
    )

    fun load(item: MarketItem): Bitmap? {
        val key = item.id.ifBlank { item.code }
        bitmapCache[key]?.let { return it }
        if (key in failed) return null

        val domain = knownDomains[item.code.trim()]
            ?: resolveDomain(item)

        if (domain.isNullOrBlank()) {
            failed += key
            return null
        }

        val bitmap = loadDomainIcon(domain)
        if (bitmap != null) {
            bitmapCache[key] = bitmap
            return bitmap
        }

        failed += key
        return null
    }

    private fun resolveDomain(item: MarketItem): String? {
        val candidates = LinkedHashSet<String>()
        val code = item.code.trim()
        val insCode = item.id.substringAfter("tsetmc:", "")
            .takeIf { it.isNotBlank() && it.all(Char::isDigit) }

        // Funds/ETFs often expose their own web address here.
        if (insCode != null) {
            collectRemoteUrls(
                "https://cdn.tsetmc.com/api/Fund/GetETFByInsCode/$insCode",
                candidates
            )
        }

        // Companies and fund managers usually expose a publisher website in
        // Codal metadata. The parser intentionally scans the JSON recursively
        // so it remains compatible if the exact website field name changes.
        if (code.isNotBlank()) {
            val encoded = java.net.URLEncoder.encode(
                code,
                java.nio.charset.StandardCharsets.UTF_8.toString()
            )
            collectRemoteUrls(
                "https://cdn.tsetmc.com/api/Codal/GetCodalPublisherBySymbol/$encoded",
                candidates
            )
        }

        return candidates
            .asSequence()
            .mapNotNull(::domainFromCandidate)
            .firstOrNull { domain ->
                val d = domain.lowercase()
                d !in setOf(
                    "tsetmc.com",
                    "cdn.tsetmc.com",
                    "codal.ir",
                    "www.codal.ir",
                    "seo.ir",
                    "gmail.com",
                    "yahoo.com"
                ) &&
                    !d.endsWith(".tsetmc.com") &&
                    !d.endsWith(".codal.ir")
            }
    }

    private fun collectRemoteUrls(
        url: String,
        output: MutableSet<String>
    ) {
        val text = runCatching { httpText(url) }.getOrNull() ?: return
        val root = runCatching { org.json.JSONTokener(text).nextValue() }.getOrNull()
            ?: return
        collectStrings(root, output)
    }

    private fun collectStrings(
        value: Any?,
        output: MutableSet<String>
    ) {
        when (value) {
            is org.json.JSONObject -> {
                val keys = value.keys()
                while (keys.hasNext()) {
                    val key = keys.next()
                    collectStrings(value.opt(key), output)
                }
            }
            is org.json.JSONArray -> {
                for (index in 0 until value.length()) {
                    collectStrings(value.opt(index), output)
                }
            }
            is String -> {
                val raw = value.trim()
                if (raw.isBlank()) return

                val urlRegex = Regex(
                    """(?i)(?:https?://|www\.)[^\s"'<>]+"""
                )
                urlRegex.findAll(raw).forEach { output += it.value }

                // Also accept plain domains that commonly appear in publisher
                // fields such as Website without a scheme.
                val domainRegex = Regex(
                    """(?i)\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:ir|com|org|net|co)\b"""
                )
                domainRegex.findAll(raw).forEach { output += it.value }
            }
        }
    }

    private fun domainFromCandidate(candidate: String): String? {
        var value = candidate.trim()
            .trimEnd('.', ',', ';', '/', ')', ']', '}')
        if (value.isBlank()) return null

        if (!value.startsWith("http://", true) &&
            !value.startsWith("https://", true)
        ) {
            value = "https://" + value.removePrefix("www.")
        }

        return runCatching {
            java.net.URI(value).host
                ?.lowercase()
                ?.removePrefix("www.")
        }.getOrNull()?.takeIf { '.' in it }
    }

    private fun loadDomainIcon(domain: String): Bitmap? {
        // Prefer the site's own favicon first.
        val directCandidates = listOf(
            "https://$domain/favicon.ico",
            "https://www.$domain/favicon.ico"
        )
        for (url in directCandidates) {
            loadBitmap(url)?.let { return it }
        }

        // Google's favicon endpoint is a resilient fallback for issuer sites
        // whose icon lives at a non-standard path.
        val googleUrl =
            "https://www.google.com/s2/favicons?domain=$domain&sz=128"
        return loadBitmap(googleUrl)
    }

    private fun httpText(url: String): String {
        val connection = (java.net.URL(url).openConnection()
            as java.net.HttpURLConnection).apply {
            connectTimeout = 4_000
            readTimeout = 4_000
            instanceFollowRedirects = true
            setRequestProperty(
                "User-Agent",
                "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36"
            )
            setRequestProperty("Accept", "application/json,text/plain,*/*")
        }
        return try {
            connection.inputStream.bufferedReader().use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }

    private fun loadBitmap(url: String): Bitmap? {
        val connection = runCatching {
            (java.net.URL(url).openConnection()
                as java.net.HttpURLConnection).apply {
                connectTimeout = 4_000
                readTimeout = 4_000
                instanceFollowRedirects = true
                setRequestProperty(
                    "User-Agent",
                    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36"
                )
                setRequestProperty("Accept", "image/*,*/*;q=0.8")
            }
        }.getOrNull() ?: return null

        return try {
            if (connection.responseCode !in 200..299) return null
            connection.inputStream.use { BitmapFactory.decodeStream(it) }
        } catch (_: Throwable) {
            null
        } finally {
            connection.disconnect()
        }
    }
}


private val SymbolLogoUrlCache = ConcurrentHashMap<String, String>()

@Composable
private fun MarketBadge(
    item: MarketItem,
    modifier: Modifier = Modifier
) {
    val cacheKey = item.source.name + "|" + item.code.trim() + "|" + item.name.trim()
    val logoUrlState = produceState<String?>(
        initialValue = SymbolLogoUrlCache[cacheKey]?.takeIf(String::isNotBlank),
        key1 = cacheKey
    ) {
        val resolved = SymbolLogoUrlCache[cacheKey]?.takeIf(String::isNotBlank)
            ?: withContext(Dispatchers.IO) {
                runCatching { resolveMarketLogoUrl(item) }.getOrNull()
            }
        if (!resolved.isNullOrBlank()) {
            SymbolLogoUrlCache[cacheKey] = resolved
        } else {
            SymbolLogoUrlCache.putIfAbsent(cacheKey, "")
        }
        value = resolved
    }

    val logoUrl = logoUrlState.value
    if (logoUrl.isNullOrBlank()) {
        SymbolSpecificFallbackBadge(item, modifier)
        return
    }

    SubcomposeAsyncImage(
        model = logoUrl,
        contentDescription = item.name,
        contentScale = ContentScale.Fit,
        modifier = modifier,
        loading = {
            SymbolSpecificFallbackBadge(item, Modifier.fillMaxSize())
        },
        error = {
            SymbolSpecificFallbackBadge(item, Modifier.fillMaxSize())
        }
    )
}

@Composable
private fun SymbolSpecificFallbackBadge(
    item: MarketItem,
    modifier: Modifier = Modifier
) {
    // Keep the polished built-in asset icons for FX/metals/energy/crypto.
    // Iranian equities/funds and unknown global tickers get their own symbol,
    // never the same generic category badge.
    val code = item.code.trim()
    val upper = code.uppercase(java.util.Locale.US)
    val knownAsset = item.source == ir.personal.chand.data.MarketSource.ARZDIGITAL ||
        upper in setOf(
            "USD", "EUR", "USDT", "GRAM", "EMAMI", "XAU/USD", "XAUUSD",
            "BRENT", "UKOIL", "XAG/USD", "XAGUSD", "BTC", "BTCUSD", "ETH", "ETHUSD"
        )

    if (knownAsset) {
        LegacyMarketBadge(item, modifier)
        return
    }

    Surface(
        modifier = modifier,
        shape = CircleShape,
        color = Color(0xFF25272C),
        border = androidx.compose.foundation.BorderStroke(1.2.dp, Color(0xFF555A64))
    ) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            val label = when {
                code.isNotBlank() -> code.take(3)
                item.name.isNotBlank() -> item.name.take(2)
                else -> "•"
            }
            Text(
                text = label,
                color = Color(0xFFE7E8EB),
                fontWeight = FontWeight.Bold,
                fontSize = when {
                    label.length <= 2 -> 12.sp
                    else -> 9.sp
                },
                maxLines = 1,
                overflow = TextOverflow.Clip
            )
        }
    }
}

private fun resolveMarketLogoUrl(item: MarketItem): String? =
    if (item.source == MarketSource.TSETMC) resolveIranianSymbolLogo(item)
    else resolveKnownAssetLogo(item)

private fun resolveKnownAssetLogo(item: MarketItem): String? {
    val code = item.code.trim().uppercase(java.util.Locale.US)
    return when (code) {
        "USDT" -> "https://cryptologos.cc/logos/tether-usdt-logo.png"
        "BTC", "BTCUSD", "BTC/USD" -> "https://cryptologos.cc/logos/bitcoin-btc-logo.png"
        "ETH", "ETHUSD", "ETH/USD" -> "https://cryptologos.cc/logos/ethereum-eth-logo.png"
        else -> null
    }
}


private fun financialModelingPrepLogo(code: String): String? {
    val ticker = code.substringAfterLast(':')
        .replace("/", "")
        .replace("-", "")
        .trim()
        .uppercase(java.util.Locale.US)
    if (ticker.isBlank()) return null
    return "https://financialmodelingprep.com/image-stock/" + encodeUrl(ticker) + ".png"
}

private fun resolveIranianSymbolLogo(item: MarketItem): String? {
    val symbol = item.code.trim().ifBlank { item.name.trim() }
    if (symbol.isBlank()) return null

    // TSETMC's Codal publisher record usually includes the issuer website.
    // Using that website's favicon/brandmark gives every company/fund its own
    // identity while remaining fully dynamic for newly-added Iranian symbols.
    val publisherUrl =
        "https://cdn.tsetmc.com/api/Codal/GetCodalPublisherBySymbol/" + encodeUrl(symbol)

    val body = httpText(publisherUrl)
    val root = JSONObject(body)
    val publisher = root.optJSONObject("codalPublisher") ?: root
    val website = findWebsiteRecursively(publisher) ?: return null

    val clean = website
        .trim()
        .removePrefix("http://")
        .removePrefix("https://")
        .substringBefore('/')
        .removePrefix("www.")
        .trim()

    if (clean.isBlank() || !clean.contains('.')) return null

    return "https://www.google.com/s2/favicons?sz=128&domain_url=https://" + encodeUrl(clean)
}

private fun findWebsiteRecursively(value: Any?): String? {
    when (value) {
        is JSONObject -> {
            val keys = value.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                val raw = value.opt(key)
                val lowered = key.lowercase(java.util.Locale.US)
                if (raw is String &&
                    (lowered.contains("web") ||
                     lowered.contains("site") ||
                     lowered.contains("url") ||
                     lowered.contains("domain"))
                ) {
                    val candidate = raw.trim()
                    if (candidate.startsWith("http://") ||
                        candidate.startsWith("https://") ||
                        (candidate.contains('.') && !candidate.contains(' '))
                    ) {
                        return candidate
                    }
                }
            }
            val nestedKeys = value.keys()
            while (nestedKeys.hasNext()) {
                val nested = findWebsiteRecursively(value.opt(nestedKeys.next()))
                if (!nested.isNullOrBlank()) return nested
            }
        }
        is JSONArray -> {
            for (i in 0 until value.length()) {
                val nested = findWebsiteRecursively(value.opt(i))
                if (!nested.isNullOrBlank()) return nested
            }
        }
    }
    return null
}


private fun normalizeTicker(value: String): String =
    value.uppercase(java.util.Locale.US)
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
        .substringAfterLast(':')

private fun encodeUrl(value: String): String =
    URLEncoder.encode(value, StandardCharsets.UTF_8.name())

private fun httpText(url: String): String {
    val connection = (URL(url).openConnection() as HttpURLConnection).apply {
        connectTimeout = 5_000
        readTimeout = 5_000
        instanceFollowRedirects = true
        setRequestProperty("Accept", "application/json,text/plain,*/*")
        setRequestProperty(
            "User-Agent",
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36"
        )
    }
    return try {
        connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
    } finally {
        connection.disconnect()
    }
}

@Composable
private fun LegacyMarketBadge(item: MarketItem, modifier: Modifier = Modifier) {
    val id = item.id
    val category = item.category.lowercase()
    val code = item.code.trim()
    val symbol = item.symbol.trim()
    val name = item.name.trim()
    val isGold = id in setOf("gold18", "emami", "gold_world", "ayar") ||
        category.contains("طلا") || category.contains("سکه") || symbol.equals("GOLD", true)
    val isSilver = id == "silver" || category.contains("نقره") || symbol.equals("SILVER", true)
    val upperCode = code.uppercase()
    val isBitcoin = symbol == "BTC" || upperCode.startsWith("BTC") || name.contains("bitcoin", ignoreCase = true)
    val isEthereum = symbol == "ETH" || upperCode.startsWith("ETH") || name.contains("ethereum", ignoreCase = true)
    val isTether = symbol == "USDT" || id == "usdt" || upperCode.startsWith("USDT") || name.contains("tether", ignoreCase = true)
    val isCrypto = isBitcoin || isEthereum || isTether || category.contains("دیجیتال") || symbol.equals("CRYPTO", true)
    val isOil = id == "brent" || category.contains("نفت") || category.contains("انرژی") || symbol.equals("OIL", true)
    val isStock = category.contains("بورس") || category.contains("سهام") || category.contains("صندوق") ||
        symbol.equals("TSE", true)
    val isCurrencySymbol = symbol in setOf("USD", "EUR", "GBP", "JPY", "CNY", "AED", "TRY", "RUB", "INR")
    val isFx = isCurrencySymbol || category.contains("ارز") || symbol.equals("FX", true) ||
        code.uppercase().let { it.length == 3 && it.all(Char::isLetter) }
    val isIndex = category.contains("شاخص") || name.contains("شاخص")
    val isCar = category.contains("خودرو") || symbol.equals("CAR", true)

    Box(modifier, contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val radius = size.minDimension / 2f
            val center = Offset(size.width / 2f, size.height / 2f)
            when {
                (id == "usd" || symbol == "USD") -> {
                    val circle = Path().apply {
                        addOval(Rect(center - Offset(radius, radius), center + Offset(radius, radius)))
                    }
                    clipPath(circle) {
                        drawCircle(Color.White, radius, center)
                        val stripeHeight = size.height / 13f
                        repeat(7) { stripe ->
                            drawRect(
                                color = Color(0xFFCA3244),
                                topLeft = Offset(0f, stripe * stripeHeight * 2f),
                                size = androidx.compose.ui.geometry.Size(size.width, stripeHeight)
                            )
                        }
                        drawRect(
                            Color(0xFF24447A),
                            size = androidx.compose.ui.geometry.Size(size.width * .55f, size.height * .54f)
                        )
                        repeat(4) { row ->
                            repeat(4) { col ->
                                drawCircle(
                                    Color.White,
                                    radius = radius * .035f,
                                    center = Offset(
                                        size.width * (.09f + col * .12f),
                                        size.height * (.08f + row * .12f)
                                    )
                                )
                            }
                        }
                    }
                }
                (id == "euro" || symbol == "EUR") -> {
                    drawCircle(Color(0xFF1849A9), radius, center)
                    repeat(12) { index ->
                        val angle = 2.0 * PI * index / 12.0 - PI / 2.0
                        drawCircle(
                            Color(0xFFFFD83D),
                            radius * .055f,
                            Offset(
                                center.x + cos(angle).toFloat() * radius * .62f,
                                center.y + sin(angle).toFloat() * radius * .62f
                            )
                        )
                    }
                }
                isGold -> {
                    drawCircle(
                        brush = Brush.radialGradient(
                            listOf(Color(0xFFFFE24B), Color(0xFFF3B313), Color(0xFFD68C00)),
                            center = Offset(size.width * .35f, size.height * .28f),
                            radius = radius * 1.45f
                        ),
                        radius = radius,
                        center = center
                    )
                    drawCircle(Color(0x55A56B00), radius * .72f, center, style = Stroke(radius * .035f))
                    drawCircle(Color(0x44FFF3A0), radius * .55f, center, style = Stroke(radius * .025f))
                }
                isSilver -> {
                    drawCircle(Color(0xFFC9CDD4), radius, center)
                    drawCircle(Color(0xFF8D949F), radius * .74f, center, style = Stroke(radius * .05f))
                }
                isOil -> {
                    drawCircle(Color(0xFF202226), radius, center)
                    drawCircle(Color(0xFF4A4F57), radius, center, style = Stroke(radius * .06f))
                    val drop = Path().apply {
                        moveTo(center.x, center.y - radius * .55f)
                        cubicTo(
                            center.x - radius * .42f, center.y - radius * .08f,
                            center.x - radius * .45f, center.y + radius * .28f,
                            center.x, center.y + radius * .52f
                        )
                        cubicTo(
                            center.x + radius * .45f, center.y + radius * .28f,
                            center.x + radius * .42f, center.y - radius * .08f,
                            center.x, center.y - radius * .55f
                        )
                        close()
                    }
                    drawPath(drop, Color(0xFFE2E4E8))
                }
                isCrypto -> {
                    drawCircle(Color(0xFF25262A), radius, center)
                    drawCircle(Color(0xFF8A8E98), radius * .78f, center, style = Stroke(radius * .055f))
                }
                isIndex -> {
                    drawCircle(Color(0xFF202329), radius, center)
                    val p1 = Offset(size.width * .22f, size.height * .66f)
                    val p2 = Offset(size.width * .42f, size.height * .49f)
                    val p3 = Offset(size.width * .57f, size.height * .57f)
                    val p4 = Offset(size.width * .79f, size.height * .29f)
                    drawLine(Color(0xFFE8E9EB), p1, p2, strokeWidth = radius * .10f, cap = StrokeCap.Round)
                    drawLine(Color(0xFFE8E9EB), p2, p3, strokeWidth = radius * .10f, cap = StrokeCap.Round)
                    drawLine(Color(0xFFE8E9EB), p3, p4, strokeWidth = radius * .10f, cap = StrokeCap.Round)
                }
                isCar -> {
                    drawCircle(Color(0xFF25272C), radius, center)
                    drawCircle(Color(0xFFC7CAD1), radius * .48f, center, style = Stroke(radius * .12f))
                    drawCircle(Color(0xFF25272C), radius * .17f, center)
                }
                isStock -> {
                    drawCircle(Color(0xFF25262A), radius, center)
                    drawCircle(Color(0xFF5B5E66), radius, center, style = Stroke(radius * .06f))
                    drawLine(
                        Color(0x55FFFFFF),
                        Offset(size.width * .20f, size.height * .70f),
                        Offset(size.width * .80f, size.height * .34f),
                        strokeWidth = radius * .06f,
                        cap = StrokeCap.Round
                    )
                }
                isFx -> {
                    drawCircle(Color(0xFF24262B), radius, center)
                    drawCircle(Color(0xFF686C76), radius * .78f, center, style = Stroke(radius * .055f))
                }
                else -> {
                    drawCircle(Color(0xFF2D2D31), radius, center)
                    drawCircle(Color(0xFF5D5D65), radius, center, style = Stroke(radius * .06f))
                }
            }
        }

        val label = when {
            id == "gold18" || category.contains("۱۸") -> "18"
            id == "emami" -> "س"
            id == "ayar" || id == "gold_world" || isGold -> "Au"
            isSilver -> "Ag"
            isBitcoin -> "₿"
            isEthereum -> "Ξ"
            isTether -> "₮"
            isOil -> ""
            isIndex || isCar -> ""
            isCrypto -> code.ifBlank { name }.uppercase().substringBefore('/').take(3)
            isStock -> name.ifBlank { code }.take(3)
            id in setOf("usd", "euro") || symbol in setOf("USD", "EUR") -> ""
            isFx -> currencyBadge(if (isCurrencySymbol) symbol else code.ifBlank { name })
            else -> code.ifBlank { symbol.ifBlank { name } }.take(3)
        }
        if (label.isNotBlank()) {
            Text(
                text = label,
                color = if (isGold) Color(0xFF8D5D00) else Color.White,
                fontWeight = FontWeight.Bold,
                fontSize = if (label.length > 2) 11.sp else 16.sp,
                maxLines = 1
            )
        }
    }
}

private fun currencyBadge(raw: String): String {
    val code = raw.uppercase().replace("/", "").take(3)
    return when (code) {
        "USD" -> "$"
        "EUR" -> "€"
        "GBP" -> "£"
        "JPY", "CNY" -> "¥"
        "KRW" -> "₩"
        "RUB" -> "₽"
        "TRY" -> "₺"
        "INR" -> "₹"
        "IRR" -> "﷼"
        else -> code.ifBlank { "FX" }
    }
}

@Composable
private fun ControlBar(
    gridMode: Boolean,
    onAdd: () -> Unit,
    onToggleLayout: () -> Unit,
    onSettings: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
        verticalAlignment = Alignment.CenterVertically
    ) {
        SmallControl(Icons.Default.Add, "افزودن", onAdd)
        SmallControl(
            if (gridMode) Icons.Default.ViewAgenda else Icons.Default.GridView,
            "چیدمان",
            onToggleLayout
        )
        SmallControl(Icons.Default.Settings, "تنظیمات", onSettings)
    }
}

@Composable
private fun SmallControl(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    description: String,
    onClick: () -> Unit
) {
    IconButton(onClick = onClick, modifier = Modifier.size(40.dp)) {
        Icon(icon, description, tint = ChandMuted, modifier = Modifier.size(21.dp))
    }
}

@Composable
private fun EmptyState(onAdd: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .clickable(onClick = onAdd),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text("موردی برای نمایش انتخاب نشده", color = ChandMuted)
        Text("افزودن قیمت", color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PriceDetails(
    item: MarketItem,
    chart: ChartUiState,
    onRange: (HistoryRange) -> Unit,
    onDismiss: () -> Unit
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = ChandCard,
        contentColor = Color.White,
        dragHandle = null
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(start = 20.dp, end = 20.dp, top = 16.dp, bottom = 18.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                MarketBadge(item, Modifier.size(48.dp))
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(item.name, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                    Text(item.code, color = ChandMuted, fontSize = 14.sp)
                }
                IconButton(onClick = onDismiss) { Icon(Icons.Default.Close, "بستن") }
            }
            Spacer(Modifier.height(18.dp))
            Text(
                MarketFormatting.price(item),
                fontSize = 40.sp,
                lineHeight = 43.sp,
                fontWeight = FontWeight.Black,
                letterSpacing = (-1).sp
            )
            Text(
                MarketFormatting.changeWithPercent(item),
                color = trendColor(item),
                fontSize = 18.sp,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(Modifier.height(14.dp))
            RangeSelector(chart.range, onRange)
            Spacer(Modifier.height(12.dp))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(190.dp)
            ) {
                if (chart.points.size >= 2) {
                    PriceChart(chart.points, trendColor(item), Modifier.fillMaxSize())
                } else if (chart.loading) {
                    CircularProgressIndicator(
                        modifier = Modifier
                            .size(26.dp)
                            .align(Alignment.Center),
                        strokeWidth = 2.dp,
                        color = ChandMuted
                    )
                } else {
                    Text(
                        chart.message ?: "داده‌ی کافی برای نمودار موجود نیست",
                        color = ChandMuted,
                        fontSize = 13.sp,
                        modifier = Modifier.align(Alignment.Center)
                    )
                }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("کمینه  ${MarketFormatting.value(item.low, item.unit)}", color = ChandMuted, fontSize = 12.sp)
                Text("بیشینه  ${MarketFormatting.value(item.high, item.unit)}", color = ChandMuted, fontSize = 12.sp)
            }
            Spacer(Modifier.height(7.dp))
            Text(
                text = sourceLabel(item),
                color = ChandMuted,
                fontSize = 11.sp,
                modifier = Modifier.fillMaxWidth(),
                textAlign = TextAlign.End
            )
        }
    }
}

@Composable
private fun RangeSelector(selected: HistoryRange, onRange: (HistoryRange) -> Unit) {
    LazyRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        items(HistoryRange.entries, key = HistoryRange::name) { range ->
            val active = range == selected
            Surface(
                color = if (active) Color.White else Color(0xFF2C2C2E),
                contentColor = if (active) Color.Black else ChandMuted,
                shape = RoundedCornerShape(10.dp),
                modifier = Modifier.clickable { onRange(range) }
            ) {
                Text(
                    range.label,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 13.dp, vertical = 7.dp)
                )
            }
        }
    }
}

@Composable
private fun PriceChart(points: List<PricePoint>, color: Color, modifier: Modifier = Modifier) {
    Canvas(modifier) {
        val values = points.map(PricePoint::value)
        val min = values.minOrNull() ?: return@Canvas
        val max = values.maxOrNull() ?: return@Canvas
        val range = (max - min).takeIf { it > 0.0 } ?: 1.0
        val lastIndex = points.lastIndex.coerceAtLeast(1)
        fun point(index: Int): Offset {
            val x = size.width * index / lastIndex
            val normalized = ((points[index].value - min) / range).toFloat()
            val y = size.height * (.9f - normalized * .8f)
            return Offset(x, y)
        }
        val line = Path().apply {
            moveTo(point(0).x, point(0).y)
            for (index in 1..points.lastIndex) lineTo(point(index).x, point(index).y)
        }
        val area = Path().apply {
            addPath(line)
            lineTo(size.width, size.height)
            lineTo(0f, size.height)
            close()
        }
        drawPath(
            area,
            brush = Brush.verticalGradient(listOf(color.copy(alpha = .28f), Color.Transparent))
        )
        drawPath(line, color = color, style = Stroke(width = 3.dp.toPx(), cap = StrokeCap.Round))
        drawCircle(color, radius = 4.dp.toPx(), center = point(points.lastIndex))
    }
}

private fun sourceLabel(item: MarketItem): String {
    val origin = when (item.origin) {
        DataOrigin.LIVE -> "زنده"
        DataOrigin.NETWORK -> "آنلاین"
        DataOrigin.CACHE -> "ذخیره‌شده"
        DataOrigin.UNAVAILABLE -> "ناموجود"
    }
    return "$origin • آخرین زمان منبع ${MarketFormatting.lastSourceTime(item, TehranZone)}"
}

@Composable
private fun SettingsDialog(
state: ChandUiState,
onDismiss: () -> Unit,
onTheme: (ThemeMode) -> Unit,
onGrid: (Boolean) -> Unit,
onUpdateIranMarket: () -> Unit,
onUpdateIranStock: () -> Unit,
onUpdateGlobalMarket: () -> Unit,
onManage: () -> Unit
) {
val isLight = MaterialTheme.colorScheme.background.luminance() > 0.5f
AlertDialog(
onDismissRequest = onDismiss,
containerColor = if (isLight) Color(0xFFFDFDFC) else ChandCard,
title = {
Text(
"تنظیمات",
color = if (isLight) Color(0xFF111111) else Color.White
)
},
text = {
Column(
modifier = Modifier
.heightIn(max = 620.dp)
.verticalScroll(rememberScrollState())
) {
Row(
modifier = Modifier.fillMaxWidth(),
verticalAlignment = Alignment.CenterVertically
) {
Text("چیدمان دو ستونه", Modifier.weight(1f))
Switch(state.settings.gridMode, onGrid)
}
HorizontalDivider(
color = if (isLight) Color(0xFFD9D9DD) else Color(0xFF343438)
)
Text(
"ظاهر",
color = if (isLight) Color(0xFF77777C) else ChandMuted,
fontSize = 12.sp,
modifier = Modifier.padding(top = 12.dp)
)
ThemeMode.entries.forEach { mode ->
Row(
modifier = Modifier
.fillMaxWidth()
.clickable { onTheme(mode) }
.padding(vertical = 9.dp),
verticalAlignment = Alignment.CenterVertically
) {
Text(
when (mode) {
ThemeMode.DARK -> "تیره (مشابه Chand)"
ThemeMode.SYSTEM -> "مطابق دستگاه"
ThemeMode.LIGHT -> "روشن"
},
Modifier.weight(1f)
)
if (state.settings.themeMode == mode) Icon(Icons.Default.Check, null)
}
}

HorizontalDivider(
color = if (isLight) Color(0xFFD9D9DD) else Color(0xFF343438),
modifier = Modifier.padding(top = 8.dp)
)
Text(
"به‌روزرسانی فهرست نمادها",
fontWeight = FontWeight.Bold,
fontSize = 14.sp,
modifier = Modifier.padding(top = 14.dp, bottom = 4.dp)
)
Text(
"هر منبع جداگانه بررسی می‌شود و فقط فهرست نمادهای قابل انتخاب تازه می‌شود.",
color = if (isLight) Color(0xFF77777C) else ChandMuted,
fontSize = 11.sp,
lineHeight = 15.sp,
modifier = Modifier.padding(bottom = 10.dp)
)

CatalogUpdateCard(
title = "بازار ایران",
provider = "ArzDigital",
state = state.iranMarketUpdate,
onUpdate = onUpdateIranMarket
)
Spacer(Modifier.height(8.dp))
CatalogUpdateCard(
title = "بورس ایران",
provider = "TSETMC",
state = state.iranStockUpdate,
onUpdate = onUpdateIranStock
)
Spacer(Modifier.height(8.dp))
CatalogUpdateCard(
title = "بازار جهانی",
provider = "ArzDigital",
state = state.globalMarketUpdate,
onUpdate = onUpdateGlobalMarket
)

Spacer(Modifier.height(8.dp))
TextButton(onClick = onManage, modifier = Modifier.fillMaxWidth()) {
Text("مدیریت قیمت‌ها")
}
}
},
confirmButton = { TextButton(onClick = onDismiss) { Text("تمام") } }
)
}

@Composable
private fun CatalogUpdateCard(
title: String,
provider: String,
state: CatalogUpdateUiState,
onUpdate: () -> Unit
) {
val isLight = MaterialTheme.colorScheme.background.luminance() > 0.5f
val accent = when {
state.success == false -> Color(0xFFE34E57)
state.running || state.success == true -> Color(0xFF36B979)
else -> if (isLight) Color(0xFF5C5C62) else ChandMuted
}
val surfaceColor = when {
state.success == false -> if (isLight) Color(0xFFFFEFF0) else Color(0xFF32191B)
state.running || state.success == true -> if (isLight) Color(0xFFEDFAF3) else Color(0xFF10291D)
else -> if (isLight) Color.White else Color(0xFF242428)
}
val progress = state.progress.coerceIn(0, 100)

Surface(
modifier = Modifier.fillMaxWidth(),
shape = RoundedCornerShape(16.dp),
color = surfaceColor,
border = androidx.compose.foundation.BorderStroke(
1.dp,
accent.copy(alpha = if (state.success == null && !state.running) .26f else .72f)
),
shadowElevation = if (isLight) 2.dp else 0.dp
) {
Column(Modifier.padding(12.dp)) {
Row(
modifier = Modifier.fillMaxWidth(),
verticalAlignment = Alignment.CenterVertically
) {
Column(Modifier.weight(1f)) {
Text(
title,
fontWeight = FontWeight.Bold,
fontSize = 14.sp,
color = if (isLight) Color(0xFF111111) else Color.White
)
Text(
provider,
fontSize = 11.sp,
color = if (isLight) Color(0xFF85858A) else ChandMuted
)
}
Text(
progress.toString() + "%",
color = accent,
fontWeight = FontWeight.Bold,
fontSize = 14.sp
)
}

Spacer(Modifier.height(9.dp))
Surface(
modifier = Modifier
.fillMaxWidth()
.height(9.dp),
shape = CircleShape,
color = if (isLight) Color(0xFFE1E1E4) else Color(0xFF3B3B40)
) {
Box(Modifier.fillMaxSize()) {
if (progress > 0) {
Surface(
modifier = Modifier
.fillMaxWidth(progress / 100f)
.height(9.dp),
shape = CircleShape,
color = accent
) {}
}
}
}

state.message?.let { message ->
Spacer(Modifier.height(8.dp))
Text(
message,
fontSize = 11.sp,
lineHeight = 16.sp,
color = when {
state.success == false -> if (isLight) Color(0xFFB4232D) else Color(0xFFFFA0A6)
isLight -> Color(0xFF4F4F54)
else -> Color(0xFFD6D6DA)
}
)
}

TextButton(
onClick = onUpdate,
enabled = !state.running,
modifier = Modifier.fillMaxWidth()
) {
Text(
if (state.running) "در حال دریافت…" else "بررسی آپدیت",
color = if (state.running) {
if (isLight) Color(0xFF99999E) else ChandMuted
} else accent,
fontWeight = FontWeight.Bold
)
}
}
}

}

@Composable
private fun ManageItemsDialog(
    state: ChandUiState,
    onSearch: (CatalogSource, String, Boolean) -> Unit,
    onLoadMore: () -> Unit,
    onSave: (List<String>) -> Unit,
    onDismiss: () -> Unit
) {
    val manageLightMode = MaterialTheme.colorScheme.background.luminance() > 0.5f
    var query by remember(state.catalogSource) { mutableStateOf(state.catalogQuery) }
    var selected by remember(state.settings.visibleIds) {
        mutableStateOf(state.settings.visibleIds.distinct())
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = if (manageLightMode) Color(0xFFFDFDFC) else ChandCard,
        title = { Text("قیمت‌های من") },
        text = {
            Column(modifier = Modifier.height(470.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    SourceButton(
                        text = "بازارها",
                        selected = state.catalogSource == CatalogSource.MARKETS,
                        onClick = { onSearch(CatalogSource.MARKETS, "", false) }
                    )
                    SourceButton(
                        text = "بورس",
                        selected = state.catalogSource == CatalogSource.STOCKS,
                        onClick = { onSearch(CatalogSource.STOCKS, "", false) }
                    )
                }
                Spacer(Modifier.height(10.dp))
                if (selected.isNotEmpty()) {
                    Text("ترتیب صفحه اصلی", color = ChandMuted, fontSize = 12.sp)
                    Spacer(Modifier.height(4.dp))
                    val selectedLabels = remember(state.visibleItems, state.catalogItems) {
                        buildMap<String, String> {
                            state.visibleItems.forEach { put(it.id, it.name) }
                            state.catalogItems.forEach { put(it.id, it.name) }
                        }
                    }
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 138.dp)
                    ) {
                        itemsIndexed(selected, key = { _, id -> id }) { index, id ->
                            Row(
                                modifier = Modifier.fillMaxWidth().padding(vertical = 1.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = selectedLabels[id] ?: id,
                                    modifier = Modifier.weight(1f),
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                    fontSize = 12.sp
                                )
                                IconButton(
                                    enabled = index > 0,
                                    onClick = {
                                        if (index > 0) {
                                            val next = selected.toMutableList()
                                            val moved = next.removeAt(index)
                                            next.add(index - 1, moved)
                                            selected = next
                                        }
                                    }
                                ) { Icon(Icons.Default.KeyboardArrowUp, "زودتر") }
                                IconButton(
                                    enabled = index < selected.lastIndex,
                                    onClick = {
                                        if (index < selected.lastIndex) {
                                            val next = selected.toMutableList()
                                            val moved = next.removeAt(index)
                                            next.add(index + 1, moved)
                                            selected = next
                                        }
                                    }
                                ) { Icon(Icons.Default.KeyboardArrowDown, "دیرتر") }
                            }
                        }
                    }
                    HorizontalDivider(
                        color = if (manageLightMode) Color(0xFFD9D9DD) else Color(0xFF2C2C2E)
                    )
                    Spacer(Modifier.height(6.dp))
                }
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    placeholder = { Text("جست‌وجو") },
                    singleLine = true,
                    trailingIcon = {
                        IconButton(onClick = { onSearch(state.catalogSource, query, false) }) {
                            Icon(Icons.Default.Search, "جست‌وجو")
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(Modifier.height(8.dp))
                when {
                    state.catalogLoading && state.catalogItems.isEmpty() -> Box(
                        Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) { CircularProgressIndicator(strokeWidth = 2.dp) }
                    else -> LazyColumn(Modifier.weight(1f)) {
                        items(state.catalogItems, key = MarketDescriptor::id) { descriptor ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        selected = if (descriptor.id in selected) {
                                            selected.filterNot { it == descriptor.id }
                                        } else {
                                            selected + descriptor.id
                                        }
                                    }
                                    .padding(vertical = 5.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Checkbox(
                                    checked = descriptor.id in selected,
                                    onCheckedChange = {
                                        selected = if (it) {
                                            if (descriptor.id in selected) selected else selected + descriptor.id
                                        } else {
                                            selected.filterNot { id -> id == descriptor.id }
                                        }
                                    }
                                )
                                Column(Modifier.weight(1f)) {
                                    Text(descriptor.name, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                    Text(descriptor.code, color = ChandMuted, fontSize = 11.sp)
                                }
                            }
                        }
                        state.catalogMessage?.let { message ->
                            item { Text(message, color = ChandMuted, fontSize = 12.sp) }
                        }
                        if (state.catalogHasMore) {
                            item {
                                TextButton(onClick = onLoadMore, modifier = Modifier.fillMaxWidth()) {
                                    Text(if (state.catalogLoading) "در حال دریافت…" else "موارد بیشتر")
                                }
                            }
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = { onSave(selected) }) { Text("ذخیره") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("لغو") } }
    )
}

@Composable
private fun SourceButton(text: String, selected: Boolean, onClick: () -> Unit) {
    val sourceLightMode = MaterialTheme.colorScheme.background.luminance() > 0.5f
    Surface(
        color = when {
            selected && sourceLightMode -> Color(0xFF111113)
            selected -> Color.White
            sourceLightMode -> Color(0xFFF0F0F2)
            else -> Color(0xFF2C2C2E)
        },
        contentColor = when {
            selected && sourceLightMode -> Color.White
            selected -> Color.Black
            sourceLightMode -> Color(0xFF4A4A4F)
            else -> ChandMuted
        },
        shape = RoundedCornerShape(10.dp),
        modifier = Modifier.clickable(onClick = onClick)
    ) {
        Text(
            text,
            fontWeight = FontWeight.Bold,
            fontSize = 12.sp,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
        )
    }
}
