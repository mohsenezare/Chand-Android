# Chand 4.12 — ArzDigital migration

This branch is the isolated migration workspace for the Android app.

## Locked requirements
- Public pages on https://arzdigital.com/ are the only source for non-TSETMC market quotes. No API key and no third-party quote provider.
- TSETMC remains the only source for Tehran Stock Exchange instruments.
- Preserve existing UI, widgets, watchlists, settings, and chart behavior.
- Fix manual TSETMC catalog refresh and stock-symbol search.
- Remove TGJU and Investing provider code, labels, tests, caches, and build probes after replacement paths are verified.

## Important implementation constraint
The ArzDigital pages are HTML pages, not a documented anonymous JSON API. Scraping must use stable, page-level selectors/embedded structured data, validate positive numeric prices and provider timestamps, and fail closed. A failed parse must not be shown as a live quote. Do not infer a quote from unrelated page text.

## Initial verified public-page coverage
- Homepage exposes currency, crypto, gold/coin quick-price rows.
- Brent derivatives has a dedicated page at /coins/brent-oil-derivatives/ and exposes a dollar quote and 24h change.
- The CI probe in this branch checks these public pages only; it is a connectivity/markup smoke test, not proof that the Android app has been migrated.

## Build and acceptance
1. Run the page probe.
2. Implement and unit-test the HTML/structured-data parser.
3. Integrate it in MarketRepository for every non-TSETMC descriptor.
4. Route TSETMC refresh/search independently and test catalog refresh, exact symbol lookup, and pagination.
5. Remove legacy provider paths and run Gradle unit tests + assembleDebug.
6. Attach APK, complete source archive, SHA-256, and a test report to the build run.

Do not label the branch release-ready until all six steps pass.
