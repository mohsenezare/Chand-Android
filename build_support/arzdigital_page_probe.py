#!/usr/bin/env python3
"""Smoke-test public ArzDigital pages; this does not claim app integration."""
import re
import sys
import urllib.request

BASE = "https://arzdigital.com"
URLS = {
    "home": BASE + "/",
    "brent": BASE + "/coins/brent-oil-derivatives/",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ChandArzDigitalProbe/1.0)",
    "Accept": "text/html,application/xhtml+xml",
}

def get(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"{url}: HTTP {response.status}")
        body = response.read().decode("utf-8", "replace")
        if len(body) < 5000:
            raise RuntimeError(f"{url}: unexpectedly short HTML ({len(body)} bytes)")
        return body

def main():
    home = get(URLS["home"])
    brent = get(URLS["brent"])
    checks = {
        "homepage contains USD quote label": bool(re.search(r"\bUSD\b|دلار", home, re.I)),
        "homepage contains crypto quote labels": bool(re.search(r"\bBTC\b|بیت.?کوین", home, re.I)),
        "homepage contains gold/coin quote labels": bool(re.search(r"طلای\s*۱۸|سکه", home)),
        "Brent page contains asset identity": "Brent Oil" in brent or "brent-oil" in brent.lower(),
        "Brent page contains BZ ticker": bool(re.search(r"\bBZ\b", brent)),
        "Brent page contains numeric dollar quote": bool(re.search(r"\$\s*[0-9][0-9,.]*", brent)),
    }
    for label, passed in checks.items():
        print(("PASS" if passed else "FAIL") + " | " + label)
    if not all(checks.values()):
        sys.exit(1)
    print("PASS | ArzDigital public-page connectivity/markup smoke test")

if __name__ == "__main__":
    main()
