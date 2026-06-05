"""
ENHANCED fetch_close_batch with detailed logging
Replace the fetch_close_batch function in market_engine.py with this version
to diagnose why UK stocks are failing to load.
"""

import time
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

def fetch_close_batch_verbose(symbols, days=420, end_date=None):
    """
    Fetch closing prices for a batch of symbols with detailed error logging.
    Returns a DataFrame with symbols as columns, dates as index.
    """
    result = {}
    failed = []
    insufficient = []
    
    end_dt   = (pd.Timestamp(end_date) + timedelta(days=1)) if end_date \
                else (datetime.today() + timedelta(days=1))
    start_dt = end_dt - timedelta(days=days + 5)
    
    print(f"\n  📊 Fetching {len(symbols)} symbols from {start_dt.date()} to {end_dt.date()}")
    print(f"  ────────────────────────────────────────────────────────")
    
    for idx, sym in enumerate(symbols):
        try:
            if (idx + 1) % 50 == 0:
                print(f"    Progress: {idx+1}/{len(symbols)} ({len(result)} loaded)")
            
            raw = yf.download(
                sym,
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                auto_adjust=True, 
                progress=False
            )
            
            if raw.empty:
                failed.append((sym, "Empty response from Yahoo Finance"))
                continue
            
            cl = raw["Close"]
            if isinstance(cl, pd.DataFrame):
                cl = cl.squeeze()
            
            s = _normalize(cl.dropna())
            
            if len(s) < 22:
                insufficient.append((sym, f"Only {len(s)} days (need 22+)"))
                continue
            
            result[sym] = s
            
        except yf.utils.TickerMissingError:
            failed.append((sym, "Ticker not found on Yahoo Finance (verify symbol)"))
        except Exception as e:
            failed.append((sym, str(e)[:60]))
        
        time.sleep(0.05)  # Rate limit: 50ms between requests
    
    # Print detailed summary
    print(f"\n  ✅ Successfully loaded: {len(result)}/{len(symbols)}")
    
    if insufficient:
        print(f"\n  ⚠️  Insufficient data ({len(insufficient)}):")
        for sym, reason in insufficient[:10]:
            print(f"      • {sym}: {reason}")
        if len(insufficient) > 10:
            print(f"      ... and {len(insufficient)-10} more")
    
    if failed:
        print(f"\n  ❌ Failed to fetch ({len(failed)}):")
        for sym, reason in failed[:10]:
            print(f"      • {sym}: {reason}")
        if len(failed) > 10:
            print(f"      ... and {len(failed)-10} more")
        
        # Print first 5 failed symbols for manual testing
        print(f"\n  🔍 Test these symbols manually:")
        for sym in [f for f, _ in failed[:5]]:
            print(f"      yfinance.download('{sym}')")
    
    print(f"  ────────────────────────────────────────────────────────\n")
    
    return pd.DataFrame(result) if result else pd.DataFrame()


# Helper function from market_engine.py (include if needed)
def _normalize(s):
    try:
        if isinstance(s, pd.DataFrame): 
            s = s.squeeze()
        idx = s.index
        if hasattr(idx, "tz") and idx.tz is not None:
            try: 
                idx = idx.tz_localize(None)
            except: 
                idx = idx.tz_convert(None)
        idx = idx.normalize()
        s2 = pd.Series(s.values, index=idx, dtype=float)
        return s2[~s2.index.duplicated(keep="last")].sort_index()
    except: 
        return s
