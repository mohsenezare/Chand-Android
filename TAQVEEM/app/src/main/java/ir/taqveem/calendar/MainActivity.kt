package ir.taqveem.calendar

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Today
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.time.LocalDate
import java.time.temporal.ChronoUnit

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { TaqveemApp() }
    }
}

private data class JalaliDate(val year: Int, val month: Int, val day: Int)

private fun toJalali(date: LocalDate): JalaliDate {
    val gdm = intArrayOf(0,31,if (date.isLeapYear) 29 else 28,31,30,31,30,31,31,30,31,30,31)
    val gy = date.year - 1600
    val gm = date.monthValue - 1
    val gd = date.dayOfMonth - 1
    var gDayNo = 365 * gy + (gy + 3) / 4 - (gy + 99) / 100 + (gy + 399) / 400
    for (i in 0 until gm) gDayNo += gdm[i + 1]
    gDayNo += gd
    var jDayNo = gDayNo - 79
    val jNp = jDayNo / 12053
    jDayNo %= 12053
    var jy = 979 + 33 * jNp + 4 * (jDayNo / 1461)
    jDayNo %= 1461
    if (jDayNo >= 366) {
        jy += (jDayNo - 1) / 365
        jDayNo = (jDayNo - 1) % 365
    }
    val jm: Int
    val jd: Int
    if (jDayNo < 186) {
        jm = 1 + jDayNo / 31
        jd = 1 + jDayNo % 31
    } else {
        jm = 7 + (jDayNo - 186) / 30
        jd = 1 + (jDayNo - 186) % 30
    }
    return JalaliDate(jy, jm, jd)
}

private fun jalaliToGregorian(jyInput: Int, jm: Int, jd: Int): LocalDate {
    val jy = jyInput - 979
    var jdn = 365 * jy + (jy / 33) * 8 + ((jy % 33 + 3) / 4)
    for (i in 1 until jm) jdn += if (i <= 6) 31 else 30
    jdn += jd - 1 + 79
    var gy = 1600 + 400 * (jdn / 146097)
    jdn %= 146097
    var leap = true
    if (jdn >= 36525) {
        jdn--
        gy += 100 * (jdn / 36524)
        jdn %= 36524
        if (jdn >= 365) jdn++ else leap = false
    }
    gy += 4 * (jdn / 1461)
    jdn %= 1461
    if (jdn >= 366) {
        leap = false
        jdn--
        gy += jdn / 365
        jdn %= 365
    }
    val monthDays = intArrayOf(31, if (leap) 29 else 28,31,30,31,30,31,31,30,31,30,31)
    var gm = 0
    while (gm < 12 && jdn >= monthDays[gm]) { jdn -= monthDays[gm]; gm++ }
    return LocalDate.of(gy, gm + 1, jdn + 1)
}

private val digits = "۰۱۲۳۴۵۶۷۸۹"
private fun fa(value: Int): String = value.toString().map { if (it in '0'..'9') digits[it - '0'] else it }.joinToString("")
private val months = listOf("فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند")
private val weekdays = listOf("ش","ی","د","س","چ","پ","ج")

@Composable
private fun TaqveemApp() {
    var dark by remember { mutableStateOf(false) }
    var tab by remember { mutableIntStateOf(0) }
    var monthOffset by remember { mutableIntStateOf(0) }
    var selected by remember { mutableStateOf(LocalDate.now()) }
    var showAdd by remember { mutableStateOf(false) }
    val today = LocalDate.now()
    val baseJ = toJalali(today)
    var year = baseJ.year
    var month = baseJ.month + monthOffset
    while (month > 12) { month -= 12; year++ }
    while (month < 1) { month += 12; year-- }
    val monthStart = JalaliDate(year, month, 1)
    val startDate = jalaliToGregorian(monthStart.year, monthStart.month, 1)
    val offset = startDate.dayOfWeek.value % 7
    val daysInMonth = if (month <= 6) 31 else if (month <= 11) 30 else {
        val next = jalaliToGregorian(year + 1, 1, 1)
        ChronoUnit.DAYS.between(startDate, next).toInt()
    }
    val bg = if (dark) Color(0xFF000000) else Color(0xFFF2F2F7)
    val surface = if (dark) Color(0xFF1C1C1E) else Color.White
    val primaryText = if (dark) Color.White else Color(0xFF111114)
    val secondary = if (dark) Color(0xFF98989F) else Color(0xFF8E8E93)
    val accent = Color(0xFFFF3B30)

    MaterialTheme(colorScheme = if (dark) darkColorScheme(primary=accent, background=bg, surface=surface) else lightColorScheme(primary=accent, background=bg, surface=surface)) {
        CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
            Scaffold(containerColor = bg, bottomBar = {
                NavigationBar(containerColor = surface, tonalElevation = 0.dp) {
                    NavigationBarItem(selected=tab==0, onClick={tab=0}, icon={ Icon(Icons.Default.CalendarMonth, null) }, label={ Text("تقویم") })
                    NavigationBarItem(selected=tab==1, onClick={tab=1}, icon={ Icon(Icons.Default.List, null) }, label={ Text("فهرست") })
                    NavigationBarItem(selected=tab==2, onClick={tab=2}, icon={ Icon(Icons.Default.Search, null) }, label={ Text("جست‌وجو") })
                }
            }) { padding ->
                LazyColumn(Modifier.fillMaxSize().padding(padding).padding(horizontal=18.dp), verticalArrangement=Arrangement.spacedBy(14.dp)) {
                    item {
                        Row(Modifier.fillMaxWidth().padding(top=10.dp), verticalAlignment=Alignment.CenterVertically, horizontalArrangement=Arrangement.SpaceBetween) {
                            Column {
                                Text("تقویم", color=primaryText, fontSize=30.sp, fontWeight=FontWeight.Bold)
                                Text("امروز، " + fa(toJalali(today).day) + " " + months[toJalali(today).month-1], color=secondary, fontSize=14.sp)
                            }
                            Row(verticalAlignment=Alignment.CenterVertically) {
                                TextButton(onClick={dark=!dark}) { Text(if(dark) "روشن" else "تاریک", color=accent) }
                                IconButton(onClick={showAdd=true}) { Icon(Icons.Default.Add, null, tint=accent) }
                            }
                        }
                    }
                    item {
                        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(surface).padding(horizontal=10.dp, vertical=8.dp), verticalAlignment=Alignment.CenterVertically, horizontalArrangement=Arrangement.SpaceBetween) {
                            IconButton(onClick={monthOffset--}) { Icon(Icons.Default.ChevronRight, null, tint=primaryText) }
                            Text(months[monthStart.month-1] + " " + fa(monthStart.year), color=primaryText, fontSize=19.sp, fontWeight=FontWeight.SemiBold)
                            IconButton(onClick={monthOffset++}) { Icon(Icons.Default.ChevronLeft, null, tint=primaryText) }
                        }
                    }
                    item {
                        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(surface).padding(12.dp)) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement=Arrangement.SpaceAround) {
                                weekdays.forEach { Text(it, modifier=Modifier.weight(1f), textAlign=TextAlign.Center, color=secondary, fontSize=13.sp, fontWeight=FontWeight.Medium) }
                            }
                            Spacer(Modifier.height(10.dp))
                            val cells = ((offset + daysInMonth + 6) / 7) * 7
                            for (week in 0 until cells/7) {
                                Row(Modifier.fillMaxWidth()) {
                                    for (col in 0..6) {
                                        val day = week*7+col-offset+1
                                        Box(Modifier.weight(1f).height(48.dp), contentAlignment=Alignment.Center) {
                                            if (day in 1..daysInMonth) {
                                                val date = startDate.plusDays((day-1).toLong())
                                                val isToday = date == today
                                                val isSelected = date == selected
                                                Column(horizontalAlignment=Alignment.CenterHorizontally, verticalArrangement=Arrangement.Center,
                                                    modifier=Modifier.size(36.dp).clip(CircleShape).background(if(isSelected) accent else Color.Transparent).clickable { selected=date }) {
                                                    Text(fa(day), color=if(isSelected) Color.White else if(isToday) accent else primaryText, fontSize=15.sp, fontWeight=if(isToday||isSelected) FontWeight.Bold else FontWeight.Normal)
                                                    if (day % 5 == 0 || day == 1) Box(Modifier.padding(top=1.dp).size(3.dp).clip(CircleShape).background(if(isSelected) Color.White else Color(0xFF34C759)))
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    item {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement=Arrangement.SpaceBetween, verticalAlignment=Alignment.CenterVertically) {
                            val j = toJalali(selected)
                            Text("رویدادهای " + fa(j.day) + " " + months[j.month-1], color=primaryText, fontSize=20.sp, fontWeight=FontWeight.Bold)
                            TextButton(onClick={selected=today; monthOffset=0}) { Icon(Icons.Default.Today, null, tint=accent); Spacer(Modifier.width(4.dp)); Text("امروز", color=accent) }
                        }
                    }
                    item {
                        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(surface).padding(16.dp)) {
                            Text(if(selected==today) "امروز" else fa(selected.dayOfMonth) + " / " + fa(selected.monthValue) + " / " + fa(selected.year), color=primaryText, fontWeight=FontWeight.SemiBold, fontSize=16.sp)
                            Spacer(Modifier.height(8.dp))
                            Text("مناسبتی برای این روز ثبت نشده است", color=secondary, fontSize=14.sp)
                        }
                    }
                    item {
                        Column(verticalArrangement=Arrangement.spacedBy(6.dp)) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement=Arrangement.SpaceBetween) {
                                Text("تقویم‌های دیگر", color=primaryText, fontWeight=FontWeight.SemiBold, fontSize=17.sp)
                                Text("شمسی  ·  میلادی  ·  قمری", color=secondary, fontSize=12.sp)
                            }
                            Text("میلادی: " + fa(selected.dayOfMonth) + "/" + fa(selected.monthValue) + "/" + fa(selected.year), color=secondary, fontSize=13.sp)
                            Text("تاریخ قمری در مرحله بعد با منبع معتبر افزوده می‌شود.", color=secondary, fontSize=12.sp)
                        }
                    }
                    item { Spacer(Modifier.height(8.dp)) }
                }
            }
            if (showAdd) AlertDialog(onDismissRequest={showAdd=false}, title={Text("رویداد جدید")}, text={Text("فرم ثبت رویداد در مرحله بعدی توسعه اضافه می‌شود.")}, confirmButton={TextButton(onClick={showAdd=false}) { Text("باشه") }})
        }
    }
}
