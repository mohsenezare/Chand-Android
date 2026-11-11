# Chand v4.0 — معماری زنده

- بورس ایران: TSETMC با MarketWatch incremental حدود 650ms و InsCode.
- طلا/سکه/ارز داخلی: WebSocket TGJU.
- بازارهای جهانی: WebSocket TradingView با quote session و quote_fast_symbols.
- HTTP فقط برای مقدار اولیه، جست‌وجو، بازیابی و reconciliation است؛ نه برای جعل حالت Live.
- قیمت صفر/خالی جای آخرین معامله معتبر را نمی‌گیرد. برای نماد بورسی بدون معامله امروز، آخرین معامله واقعی از تاریخچه TSETMC بازیابی می‌شود.
- timestamp منبع تا جای ممکن از خود provider حفظ می‌شود.
- ترتیب انتخاب کاربر در صفحه اصلی ثابت می‌ماند و با refresh مرتب‌سازی مجدد نمی‌شود.
- فقط نمادهای انتخاب‌شده روی صفحه اصلی stream/poll سریع می‌شوند.
