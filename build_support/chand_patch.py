from pathlib import Path
root = Path("source/app/src/main/java/ir/personal/chand")

# Keep the picker minimal: do not expose TGJU as a second source for Iranian symbols.
p = root / "MainActivity.kt"
s = p.read_text()
s = s.replace("""                    SourceButton(
                        text = "بازارهای جهانی",
                        selected = state.catalogSource == CatalogSource.TGJU,
                        onClick = { onSearch(CatalogSource.TGJU, "", false) }
                    )
""", "")
p.write_text(s)

# The reconstructed v4 source already has a real TradingView websocket client and
# a TSETMC live delta client. Keep the foreground reconciliation short so a dropped
# stream recovers quickly without changing the UI.
p = root / "MainViewModel.kt"
s = p.read_text()
s = s.replace("const val LIVE_RECONCILE_INTERVAL_MS = 5_000L", "const val LIVE_RECONCILE_INTERVAL_MS = 1_000L")
s = s.replace("const val ACTIVE_REFRESH_INTERVAL_MS = 1_000L", "const val ACTIVE_REFRESH_INTERVAL_MS = 750L")
p.write_text(s)
