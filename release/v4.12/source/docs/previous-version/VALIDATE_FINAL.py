from pathlib import Path
import re, sys
root=Path(__file__).resolve().parent
java=root/'app/src/main/java/ir/personal/chand'
repo=(java/'data/MarketRepository.kt').read_text()
models=(java/'data/MarketModels.kt').read_text()
vm=(java/'MainViewModel.kt').read_text()
act=(java/'MainActivity.kt').read_text()
build=(root/'app/build.gradle.kts').read_text()
checks=[]
def ck(name, cond, detail):
    checks.append((name,bool(cond),detail))

ck('1. کارت TGJU/TradingView یکسان', 'TradingViewCard' not in act and re.search(r'items\(items.*?MarketCard\(', act, re.S), 'MarketGrid برای همه MarketItemها فقط MarketCard را صدا می‌زند.')
ck('2. منابع فقط TGJU و TradingView', 'enum class MarketSource { TGJU, TRADINGVIEW }' in models and 'TSETMC_API' not in repo and 'cdn.tsetmc' not in repo and 'webgw.tse' not in repo, 'MarketSource فقط TGJU/TRADINGVIEW است و endpoint بورس دیگر وجود ندارد.')
ck('2b. بورس ایران از TradingView تعریف نشده', all(x not in models for x in ['TSE:', 'TSETMC:', 'TEHRAN:']), 'فهرست TradingView فقط بازارهای جهانی است؛ نماد داخلی از TGJU می‌آید.')
ck('3. هشدار منبع بالای صفحه حذف', 'StatusBanner(state.snapshot' not in act and 'snapshot.message' not in act and 'Provider/status notes are intentionally hidden' in act, 'پیام snapshot/source در صفحه اصلی render نمی‌شود.')
ck('4. لوگو/Badge متناسب', 'private fun MarketBadge' in act and all(x in act for x in ['isGold','isSilver','isBitcoin','isEthereum','isTether','isOil','isStock','isIndex','isCar','currencyBadge']), 'Badge بر اساس ارز/طلا/سکه/نقره/کریپتو/نفت/بورس/شاخص/خودرو انتخاب می‌شود.')
ck('5. فقط آیتم‌های صفحه اصلی قیمت می‌گیرند', 'val visibleIds = _uiState.value.settings.visibleIds' in vm and 'repository.fetch(visibleIds)' in vm and 'resolveVisibleDescriptors(visibleIds)' in repo and repo.count('fetchTgjuItems(')==2, 'تنها fetch(visibleIds) قیمت می‌گیرد؛ catalog دیگر quote validation ندارد.')
ck('5b. رفرش نزدیک لحظه‌ای', 'ACTIVE_REFRESH_INTERVAL_MS = 1_000L' in vm, 'چرخه foreground برابر 1000ms است.')
ck('6. حفظ آخرین قیمت در تعطیلی/خطای موقت', 'val previous = synchronized(lastItems) { lastItems.toMap() }' in repo and 'snapshotOf(visibleIds, message = null)' in repo and 'loadCached()?.items?.forEach' in repo, 'در صورت نبود quote جدید، lastItems/cache حذف نمی‌شود و snapshot همان مقدار معتبر قبلی را نگه می‌دارد.')
ck('Version', 'versionCode = 12' in build and 'versionName = "3.2-final"' in build, 'نسخه 3.2-final / code 12')

print('CHAND 3.2 FINAL SOURCE VALIDATION')
for n,ok,d in checks:
    print(('PASS' if ok else 'FAIL'), '-', n, '-', d)
if not all(x[1] for x in checks):
    sys.exit(1)
