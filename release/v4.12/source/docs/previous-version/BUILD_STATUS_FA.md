# وضعیت Build

کد نهایی و چک‌لیست سیاست داده آماده است، اما در محیط فعلی Android SDK، Build Tools و Gradle distribution نصب نیستند. دسترسی DNS خط فرمان نیز برای دریافت آن‌ها مسدود است. به همین دلیل در این محیط APK واقعیِ حاصل از سورس 3.0 ساخته نشده است.

برای جلوگیری از تکرار خروجی‌های قبلی، هیچ APK قدیمی/patch‌شده‌ای به عنوان خروجی این سورس معرفی نشده است.

فرمان استاندارد ساخت پس از فراهم بودن Android SDK 35 و Gradle Wrapper:

./gradlew clean assembleDebug

خروجی قابل نصب:
app/build/outputs/apk/debug/app-debug.apk
