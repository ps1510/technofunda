"""
symbol_checker.py — Yahoo Finance Symbol Diagnostic Tool

Usage:
    python symbol_checker.py ^CNXFIN
    python symbol_checker.py ^CNXFIN ^CNXAUTO RELIANCE.NS
    python symbol_checker.py                      ← runs built-in test list

How to find the correct symbol:
    1. Go to https://finance.yahoo.com
    2. Search for the index/stock name
    3. Look at the URL or the symbol shown in brackets e.g. (^CNXFIN)
    4. Use that exact symbol here
"""

import sys
import time
import yfinance as yf
import pandas as pd
from datetime import date, timedelta

# ── Symbols to test if none given on command line ─────────────────────────────
DEFAULT_TEST_SYMBOLS = [
    # Known NSE indices that sometimes fail
    "^CNXFIN",
    "^CNXAUTO",
    "^CNXIT",
    "^CNXPHARMA",
    "^CNXFMCG",
    "^CNXMETAL",
    "^CNXREALTY",
    "^CNXENERGY",
    "^NSEMDCP100",
    "^CNXSC",
    "^CNXINFRA",
    "^CNXMEDIA",
    "^NSEI",
    "^NSEBANK",
    "^INDIAVIX",
    # Common US
    "^GSPC",
    "^VIX",
    "GC=F",
    "DX-Y.NYB",
]

# ─────────────────────────────────────────────────────────────────────────────

def test_symbol(sym: str) -> dict:
    """Run four tests on a single symbol and return a result dict."""
    result = {
        "symbol":       sym,
        "test_period":  None,   # yf.download with period=
        "test_dates":   None,   # yf.download with start/end
        "test_ticker":  None,   # yf.Ticker().history()
        "latest_date":  None,
        "latest_price": None,
        "rows":         0,
        "error":        None,
    }

    end_dt   = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    start_dt = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")

    # ── Test 1: period= style ─────────────────────────────────────────────────
    try:
        raw = yf.download(sym, period="5d", auto_adjust=True, progress=False)
        if not raw.empty and len(raw) >= 1:
            result["test_period"] = "OK"
            result["rows"]        = len(raw)
            close = raw["Close"] if "Close" in raw.columns else raw.iloc[:, 0]
            if hasattr(close, "iloc"):
                result["latest_price"] = round(float(close.dropna().iloc[-1]), 2)
                result["latest_date"]  = str(close.dropna().index[-1].date())
        else:
            result["test_period"] = "EMPTY"
    except Exception as e:
        result["test_period"] = f"ERROR: {e}"

    time.sleep(0.5)

    # ── Test 2: start/end style (what most scripts use) ───────────────────────
    try:
        raw = yf.download(sym, start=start_dt, end=end_dt,
                          auto_adjust=True, progress=False)
        if not raw.empty and len(raw) >= 1:
            result["test_dates"] = "OK"
            if result["rows"] == 0:
                result["rows"] = len(raw)
        else:
            result["test_dates"] = "EMPTY"
    except Exception as e:
        result["test_dates"] = f"ERROR: {e}"

    time.sleep(0.5)

    # ── Test 3: Ticker.history() ──────────────────────────────────────────────
    try:
        t   = yf.Ticker(sym)
        h   = t.history(period="5d", auto_adjust=True)
        if not h.empty:
            result["test_ticker"] = "OK"
        else:
            result["test_ticker"] = "EMPTY"
    except Exception as e:
        result["test_ticker"] = f"ERROR: {e}"

    return result


def print_result(r: dict):
    sym    = r["symbol"]
    p      = r["test_period"]
    d      = r["test_dates"]
    t      = r["test_ticker"]
    price  = r["latest_price"]
    dt     = r["latest_date"]
    rows   = r["rows"]

    # Overall verdict
    if p == "OK" or d == "OK" or t == "OK":
        verdict = "WORKING"
        mark    = "✅"
    else:
        verdict = "FAILING"
        mark    = "❌"

    print(f"\n  {mark}  {sym}")
    print(f"     period= style  : {p}")
    print(f"     start/end style: {d}")
    print(f"     Ticker.history : {t}")
    if price:
        print(f"     Latest price   : {price}  ({dt})  [{rows} rows]")

    if verdict == "FAILING":
        print(f"     → DIAGNOSIS below")
        # Give specific fix advice
        if all("EMPTY" in str(x) for x in [p, d, t]):
            print(f"     Possible causes:")
            print(f"       1. Symbol may be delisted or renamed on Yahoo Finance")
            print(f"       2. Try searching: https://finance.yahoo.com/quote/{sym}/")
            print(f"       3. Check if symbol needs different prefix (e.g. ^NSEBANK vs BANKNIFTY.NS)")
        elif any("ERROR" in str(x) for x in [p, d, t]):
            print(f"       Rate limit or network issue — try again in 1–2 minutes")
    elif p != "OK" and d == "OK":
        print(f"     NOTE: period= fails but start/end works — use start/end in your scripts")
    elif p == "OK" and d != "OK":
        print(f"     NOTE: period= works but start/end fails — use period= in your scripts")
        print(f"     RECOMMENDED FIX: change yf.download({sym}, start=..., end=...) to")
        print(f"                      yf.download({sym}, period='280d') in your script")


# ── Known working alternatives for common failing India indices ───────────────
KNOWN_ALTERNATIVES = {
    "^CNXFIN":      ("^CNXFIN",    "Nifty Financial Services 25/50"),
    "^CNXPSE":      ("^CNXPSE",    "Nifty PSE"),
    "^CNXCONSUMP":  ("^CNXCONSUMP","Nifty Consumption"),
    "^CNXINFRA":    ("^CNXINFRA",  "Nifty Infrastructure"),
    "^NSEMDCP100":  ("^NSEMDCP100","Nifty Midcap 100"),
    "^CNXSC":       ("^CNXSC",     "Nifty Smallcap 100"),
    "^CNXMEDIA":    ("^CNXMEDIA",  "Nifty Media"),
}


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    syms = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TEST_SYMBOLS

    print("=" * 60)
    print("  Yahoo Finance Symbol Diagnostic")
    print(f"  Testing {len(syms)} symbols …")
    print(f"  Today: {date.today()}")
    print("=" * 60)

    working = []
    failing = []
    partial = []   # works with period= but not start/end or vice versa

    for sym in syms:
        r = test_symbol(sym)
        print_result(r)

        p_ok = r["test_period"] == "OK"
        d_ok = r["test_dates"]  == "OK"
        t_ok = r["test_ticker"] == "OK"

        if p_ok and d_ok:
            working.append(sym)
        elif not p_ok and not d_ok and not t_ok:
            failing.append(sym)
        else:
            partial.append(sym)

        time.sleep(1.0)  # be polite to Yahoo

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  ✅ Fully working  : {len(working)}")
    if working:
        for s in working: print(f"       {s}")

    print(f"  ⚠  Partial only   : {len(partial)}")
    if partial:
        for s in partial: print(f"       {s}  ← use period= style only")

    print(f"  ❌ Fully failing  : {len(failing)}")
    if failing:
        print(f"\n  For each failing symbol, check Yahoo Finance manually:")
        for s in failing:
            url = f"https://finance.yahoo.com/quote/{s}/"
            print(f"       {s:20s}  →  {url}")
        print(f"\n  If the chart loads on the website but still fails here,")
        print(f"  the symbol likely requires period= instead of start/end.")
        print(f"  Run this to confirm:  python symbol_checker.py {failing[0]}")

    print("=" * 60)
