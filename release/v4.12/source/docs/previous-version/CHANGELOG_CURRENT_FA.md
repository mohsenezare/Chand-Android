# Chand ?! — سورس نسخه 2.2 Live Clean

## موارد اعمال‌شده

- یکپارچه‌سازی فهرست «بازارها»: TGJU + نمادهای فعال بورس در یک صفحه.
- فیلتر سه‌مرحله‌ای نمادهای قدیمی TGJU: وضعیت/نوع رکورد، تاریخ انقضا و تازگی آخرین قیمت.
- پاک‌سازی نمادهای بورسی قدیمی فقط بعد از دریافت یک فهرست کامل و معتبر بازار، برای جلوگیری از حذف اشتباه هنگام خطای شبکه.
- رفع باگ تأخیر بورس: اگر نماد TSETMC روی صفحه باشد، polling حدود ۰٫۹ ثانیه؛ TGJU همچنان WebSocket زنده است.
- کاهش TTL کش TSETMC از ۱۰ ثانیه به ۶۵۰ میلی‌ثانیه.
- درخواست همه paper typeهای جاری TSETMC و استفاده از `hEven=0` و `RefID=0`.
- fallback به gateway رسمی `webgw.tse.ir` (Cash + ETF) در صورت خالی/مسدود بودن MarketWatch قدیمی.
- ترجیح موقت منبع سالم برای جلوگیری از معطلی تکراری روی endpoint خراب.
- User-Agent مرورگر برای درخواست‌های REST جهت سازگاری بهتر با TSETMC.
- حذف کامل bannerهای خطای منبع از صفحه اصلی.
- Badge متناسب برای همه کارت‌های صفحه اصلی؛ شامل طلا/سکه، نقره، نفت، رمزارز، ارز، شاخص، خودرو و سهام.
- نسخه: `2.2-live-clean`، versionCode: `7`.

## ساخت

پروژه با Android Gradle Plugin 8.7.3، Kotlin 2.0.21، JDK 17 و Android SDK 35 ساخته می‌شود.

```bash
./gradlew testDebugUnitTest lintDebug assembleDebug
```

خروجی Debug: `app/build/outputs/apk/debug/app-debug.apk`
