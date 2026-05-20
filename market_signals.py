"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  MARKET SIGNALS ENGINE  v6.0 — market_signals.py                          ║
║  SELF-CONTAINED (no imports from market_engine — avoids circular import)   ║
║                                                                            ║
║  v6.0 changes:                                                             ║
║   • build_dashboard_df uses Signal_Label counts (human-readable)           ║
║   • Dashboard reorganized: Health → Opportunities → Sectors → Guide        ║
║   • TV watchlists keyed to Signal_Label groups                             ║
║   • compute_signal_label() duplicated here to avoid circular import        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple, Dict

# ── Pine Script parameters (from RS All-TF v3) ────────────────────────────────
MST_RS_ENTRY  = 55
MST_RS_HTF    = 21
MST_RSI_LEN   = 14
MST_RSI_THRESH= 50
MST_ST_PERIOD = 10
MST_ST_FACTOR = 3.0
MST_SWING_LB  = 20
MST_TP1_MULT  = 2.5
MST_TP2_MULT  = 3.5
MST_MAX_SL    = 7.0

LST_RS_ENTRY  = 21
LST_RS_HTF    = 12
LST_RSI_LEN   = 12
LST_RSI_THRESH= 50
LST_ST_PERIOD = 10
LST_ST_FACTOR = 3.0
LST_SWING_LB  = 20
LST_TP1_MULT  = 3.0
LST_TP2_MULT  = 4.0
LST_MAX_SL    = 12.0

RS30_RS_PERIOD    = 30
RS30_EMA_S        = 10
RS30_EMA_L        = 30
RS30_NEAR_HIGH_PCT= 10.0
RS30_SWING_LB     = 20
RS30_MIN_SALES_QOQ= 15.0
RS30_MIN_PAT_QOQ  = 15.0


# ─────────────────────────────────────────────────────────────────────────────
#  INLINED UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _norm(s: pd.Series) -> pd.Series:
    try:
        if isinstance(s, pd.DataFrame): s = s.squeeze()
        idx = s.index
        if hasattr(idx, 'tz') and idx.tz is not None:
            try: idx = idx.tz_localize(None)
            except: idx = idx.tz_convert(None)
        idx = idx.normalize()
        s2  = pd.Series(s.values, index=idx, dtype=float)
        return s2[~s2.index.duplicated(keep='last')].sort_index()
    except: return s


def _rs(stock: pd.Series, bench: pd.Series, period: int) -> float:
    try:
        s = _norm(stock.dropna()); b = _norm(bench.dropna())
        common = s.index.intersection(b.index)
        if len(common) < period + 1: return np.nan
        s, b = s.loc[common], b.loc[common]
        sc, sp = float(s.iloc[-1]), float(s.iloc[-(period+1)])
        bc, bp = float(b.iloc[-1]), float(b.iloc[-(period+1)])
        if sp == 0 or bp == 0 or bc == 0: return np.nan
        return (sc/sp) / (bc/bp) - 1
    except: return np.nan


def _rsi(series: pd.Series, period: int = 14) -> float:
    try:
        d = series.diff().dropna()
        g = d.clip(lower=0).rolling(period, min_periods=period).mean().iloc[-1]
        l = (-d.clip(upper=0)).rolling(period, min_periods=period).mean().iloc[-1]
        if l == 0 or np.isnan(l): return 100.0 if g > 0 else 50.0
        return round(100 - (100 / (1 + g / l)), 1)
    except: return np.nan


def _pct_n(series: pd.Series, n: int) -> float:
    try:
        if len(series) < n + 1: return np.nan
        cur = float(series.iloc[-1]); past = float(series.iloc[-(n+1)])
        return (cur/past - 1)*100 if past != 0 else np.nan
    except: return np.nan


# ─────────────────────────────────────────────────────────────────────────────
#  RESAMPLING
# ─────────────────────────────────────────────────────────────────────────────

def to_weekly(s: pd.Series) -> pd.Series:
    try:
        s2 = _norm(s.dropna())
        return s2.resample('W-FRI').last().dropna()
    except: return pd.Series(dtype=float)


def to_monthly(s: pd.Series) -> pd.Series:
    try:
        s2 = _norm(s.dropna())
        try: return s2.resample('ME').last().dropna()
        except: return s2.resample('M').last().dropna()
    except: return pd.Series(dtype=float)


# ─────────────────────────────────────────────────────────────────────────────
#  ATR
# ─────────────────────────────────────────────────────────────────────────────

def calc_atr(close_s, high_s, low_s, period=10):
    prev_c = close_s.shift(1)
    tr = pd.concat([
        high_s - low_s,
        (high_s - prev_c).abs(),
        (low_s  - prev_c).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False, min_periods=max(2, period//2)).mean()


# ─────────────────────────────────────────────────────────────────────────────
#  SUPERTREND
# ─────────────────────────────────────────────────────────────────────────────

def calc_supertrend(close_s, high_s, low_s, period=10, multiplier=3.0):
    n = len(close_s)
    if n < period + 2:
        return (pd.Series(np.nan, index=close_s.index),
                pd.Series(0,      index=close_s.index))
    atr  = calc_atr(close_s, high_s, low_s, period)
    hl2  = (high_s + low_s) / 2.0
    ub   = (hl2 + multiplier * atr).values
    lb   = (hl2 - multiplier * atr).values
    c    = close_s.values
    atr_v= atr.values
    f_ub = ub.copy(); f_lb = lb.copy()
    direction = np.ones(n, dtype=int)
    st        = np.zeros(n)
    for i in range(1, n):
        if np.isnan(atr_v[i]):
            direction[i] = direction[i-1]; st[i] = st[i-1]; continue
        f_ub[i] = ub[i] if (ub[i] < f_ub[i-1] or c[i-1] > f_ub[i-1]) else f_ub[i-1]
        f_lb[i] = lb[i] if (lb[i] > f_lb[i-1] or c[i-1] < f_lb[i-1]) else f_lb[i-1]
        if   direction[i-1] == -1 and c[i] > f_ub[i]: direction[i] =  1
        elif direction[i-1] ==  1 and c[i] < f_lb[i]: direction[i] = -1
        else:                                           direction[i] = direction[i-1]
        st[i] = f_lb[i] if direction[i] == 1 else f_ub[i]
    return (pd.Series(st, index=close_s.index),
            pd.Series(direction, index=close_s.index))


def calc_supertrend_from_df(ohlcv_df, period=10, multiplier=3.0, freq='D'):
    _empty = pd.Series(dtype=float), pd.Series(dtype=int)
    if ohlcv_df is None or not isinstance(ohlcv_df, pd.DataFrame) or ohlcv_df.empty:
        return _empty
    try:
        h = ohlcv_df["High"]; l = ohlcv_df["Low"]; c = ohlcv_df["Close"]
        if freq == 'W':
            c = c.resample('W-FRI').last().dropna()
            h = h.resample('W-FRI').max().dropna()
            l = l.resample('W-FRI').min().dropna()
            idx = c.index.intersection(h.index).intersection(l.index)
            c, h, l = c.loc[idx], h.loc[idx], l.loc[idx]
        elif freq == 'M':
            try:
                c = c.resample('ME').last().dropna()
                h = h.resample('ME').max().dropna()
                l = l.resample('ME').min().dropna()
            except:
                c = c.resample('M').last().dropna()
                h = h.resample('M').max().dropna()
                l = l.resample('M').min().dropna()
            idx = c.index.intersection(h.index).intersection(l.index)
            c, h, l = c.loc[idx], h.loc[idx], l.loc[idx]
        return calc_supertrend(c, h, l, period, multiplier)
    except:
        return pd.Series(dtype=float), pd.Series(dtype=float)


# ─────────────────────────────────────────────────────────────────────────────
#  SWING HIGH / LOW → STOP LOSS
# ─────────────────────────────────────────────────────────────────────────────

def calc_swing_sl(close_s, high_s=None, low_s=None, lookback=20):
    out = dict(swing_low=np.nan, swing_high=np.nan,
               sl_buy_pct=np.nan, sl_sell_pct=np.nan,
               sl_buy_grade="F", sl_sell_grade="F",
               swing_high_break=False)
    try:
        c = _norm(close_s.dropna())
        if len(c) < lookback + 1: return out
        cur = float(c.iloc[-1])
        if cur <= 0: return out
        if low_s is not None and len(low_s) >= lookback:
            ls = _norm(low_s.dropna())
            sw_lo = float(ls.iloc[-lookback:].min())
        else:
            sw_lo = float(c.iloc[-lookback:].min())
        if high_s is not None and len(high_s) >= lookback + 1:
            hs = _norm(high_s.dropna())
            sw_hi      = float(hs.iloc[-lookback:].max())
            sw_hi_prev = float(hs.iloc[-lookback-1:-1].max())
        else:
            sw_hi      = float(c.iloc[-lookback:].max())
            sw_hi_prev = float(c.iloc[-lookback-1:-1].max())
        sl_buy  = (cur - sw_lo) / cur * 100 if sw_lo > 0 else np.nan
        sl_sell = (sw_hi - cur) / cur * 100 if sw_hi > cur else 0.0
        out.update(dict(
            swing_low        = round(sw_lo, 2),
            swing_high       = round(sw_hi, 2),
            sl_buy_pct       = round(sl_buy,  2) if sl_buy  == sl_buy  else np.nan,
            sl_sell_pct      = round(sl_sell, 2) if sl_sell == sl_sell else np.nan,
            sl_buy_grade     = sl_grade(sl_buy),
            sl_sell_grade    = sl_grade(sl_sell),
            swing_high_break = (cur > sw_hi_prev),
        ))
    except: pass
    return out


def sl_grade(pct) -> str:
    if not isinstance(pct, (int, float)) or np.isnan(pct) or pct < 0: return "F"
    if   pct <= 3:  return "A"
    elif pct <= 5:  return "B"
    elif pct <= 8:  return "C"
    elif pct <= 12: return "D"
    else:           return "F"


def sl_bonus(sl_pct, rr_t1=np.nan) -> float:
    g = sl_grade(sl_pct)
    base = {"A":4,"B":3,"C":2,"D":1,"F":0}.get(g, 0)
    rr_pts = 0
    try:
        rr = float(rr_t1)
        if not np.isnan(rr):
            if   rr >= 3.0: rr_pts = 2
            elif rr >= 2.0: rr_pts = 1
    except: pass
    return float(base + rr_pts)


# ─────────────────────────────────────────────────────────────────────────────
#  SIGNAL LABEL — duplicated here to avoid circular import with market_engine
# ─────────────────────────────────────────────────────────────────────────────

def compute_signal_label(action_tier, mst_sig="Neutral", lst_sig="Neutral",
                          rs30_sig="Neutral", sig="Neutral", fin_score=0):
    """
    Single unified human-readable signal label for display.
    See market_engine_patch.py for full documentation.
    """
    at  = str(action_tier  or "NEUTRAL")
    mst = str(mst_sig      or "Neutral")
    lst = str(lst_sig      or "Neutral")
    r30 = str(rs30_sig     or "Neutral")

    if at == "PRIME BUY":
        if r30 == "Buy" and lst == "Buy" and mst == "Buy": return "🌟 Triple Confirmed"
        if r30 == "Buy" and lst == "Buy":                  return "🌟 RS30 + Long"
        if r30 == "Buy" and mst == "Buy":                  return "🌟 RS30 + Swing"
        if r30 == "Buy":                                   return "🌟 RS30 Leader"
        if lst == "Buy" and fin_score >= 5:                return "🌟 Long Momentum"
        return "🌟 Prime Setup"

    if at == "CONFIRMED BUY":
        return "✅ Long Momentum" if lst == "Buy" else "✅ Strong RS"

    if at == "RS BUY":
        return "📈 Swing Entry" if mst == "Buy" else "📈 RS Leader"

    if at == "WATCH":
        watches = [x for x, v in [("RS30", r30), ("LST", lst), ("MST", mst)] if v == "Watch"]
        if len(watches) > 1:  return "👁 Setup Building"
        if watches:           return f"👁 {watches[0]} Watch"
        return "👁 Watch"

    if at == "AVOID": return "🔴 RS Breakdown"
    return "⬜ Neutral"


# ─────────────────────────────────────────────────────────────────────────────
#  MST SIGNAL
# ─────────────────────────────────────────────────────────────────────────────

def calc_mst_signal(daily_close, bench_close, st_daily, swing_data,
                    rs_55d, rsi_14d, ema200_d, w_rs21, w_rsi):
    try:
        htf_ok = (
            not (isinstance(w_rs21, float) and np.isnan(w_rs21)) and w_rs21 > 0 and
            not (isinstance(w_rsi,  float) and np.isnan(w_rsi))  and w_rsi  > MST_RSI_THRESH
        )
        if not htf_ok: return "Neutral"
        rs_ok  = not (isinstance(rs_55d,  float) and np.isnan(rs_55d))  and rs_55d  > 0
        rsi_ok = not (isinstance(rsi_14d, float) and np.isnan(rsi_14d)) and rsi_14d > MST_RSI_THRESH
        st_ok  = (st_daily in ("Buy", "N/A"))
        cur    = float(daily_close.iloc[-1])
        ema_ok = not (isinstance(ema200_d, float) and np.isnan(ema200_d)) and cur > ema200_d
        entry_ok = rs_ok and rsi_ok and st_ok and ema_ok
        breakout = bool(swing_data.get("swing_high_break", False))
        if entry_ok and breakout: return "Buy"
        elif entry_ok:            return "Watch"
        else:                     return "Neutral"
    except: return "Neutral"


# ─────────────────────────────────────────────────────────────────────────────
#  LST SIGNAL
# ─────────────────────────────────────────────────────────────────────────────

def calc_lst_signal(daily_close, bench_close, st_daily_w, swing_data,
                    m_rs12=np.nan, m_rsi=np.nan, fin=None) -> str:
    try:
        htf_ok = (
            not (isinstance(m_rs12, float) and np.isnan(m_rs12)) and m_rs12 > 0 and
            not (isinstance(m_rsi,  float) and np.isnan(m_rsi))  and m_rsi  > LST_RSI_THRESH
        )
        if fin and htf_ok:
            sy = fin.get("SalesYoY", np.nan); py = fin.get("PATYoY", np.nan)
            if not np.isnan(sy) and sy <= 0: htf_ok = False
            if not np.isnan(py) and py <= 0: htf_ok = False
        if not htf_ok: return "Neutral"
        c  = _norm(daily_close.dropna()); b = _norm(bench_close.dropna())
        cw = to_weekly(c);               bw = to_weekly(b)
        rs_w21  = _rs(cw, bw, LST_RS_ENTRY)
        rsi_w12 = _rsi(cw, LST_RSI_LEN)
        ema200_w = float(cw.ewm(span=200, adjust=False, min_periods=20).mean().iloc[-1])
        ema_ok   = float(cw.iloc[-1]) > ema200_w
        st_ok    = (st_daily_w in ("Buy", "N/A"))
        entry_ok = (
            not (isinstance(rs_w21,  float) and np.isnan(rs_w21))  and rs_w21  > 0 and
            not (isinstance(rsi_w12, float) and np.isnan(rsi_w12)) and rsi_w12 > LST_RSI_THRESH and
            st_ok and ema_ok
        )
        lb   = LST_SWING_LB
        sw_h = float(cw.iloc[-lb-1:-1].max()) if len(cw) >= lb+1 else float(cw.iloc[:-1].max())
        breakout = float(cw.iloc[-1]) > sw_h
        if entry_ok and breakout: return "Buy"
        elif entry_ok:            return "Watch"
        else:                     return "Neutral"
    except: return "Neutral"


# ─────────────────────────────────────────────────────────────────────────────
#  RS30 SIGNAL
# ─────────────────────────────────────────────────────────────────────────────

def calc_rs30_signal(daily_close, bench_close, swing_data, fin,
                     w_rs30, w_ema10, w_ema30, market="INDIA"):
    try:
        if isinstance(w_rs30, float) and np.isnan(w_rs30): return "Neutral"
        if w_rs30 <= 0: return "Neutral"
        ema_valid = (
            not (isinstance(w_ema10, float) and np.isnan(w_ema10)) and
            not (isinstance(w_ema30, float) and np.isnan(w_ema30))
        )
        if not ema_valid or w_ema10 <= w_ema30: return "Neutral"
        c   = _norm(daily_close.dropna())
        cur = float(c.iloc[-1])
        n52 = min(252, len(c))
        h52 = float(c.iloc[-n52:].max())
        dist      = (h52 - cur) / h52 * 100 if h52 > 0 else 100.0
        near_high = dist <= RS30_NEAR_HIGH_PCT
        funda_ok = True
        if fin:
            sq = fin.get("SalesQoQ", np.nan)
            pq = fin.get("PATQoQ",   np.nan)
            mc = fin.get("MktCap",   np.nan)
            sales_ok = np.isnan(sq) or sq >= RS30_MIN_SALES_QOQ
            pat_ok   = np.isnan(pq) or pq >= RS30_MIN_PAT_QOQ
            mc_thresh = 10.0 if market == "INDIA" else 1.0
            mcap_ok  = np.isnan(mc) or mc >= mc_thresh
            funda_ok = sales_ok and pat_ok and mcap_ok
        breakout = bool(swing_data.get("swing_high_break", False))
        if near_high and funda_ok: return "Buy" if breakout else "Watch"
        elif near_high:            return "Watch"
        else:                      return "Neutral"
    except: return "Neutral"


# ─────────────────────────────────────────────────────────────────────────────
#  UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def calc_rs_tf(stock_d, bench_d, period, freq="D"):
    try:
        c = _norm(stock_d.dropna()); b = _norm(bench_d.dropna())
        if freq == "W": c = to_weekly(c); b = to_weekly(b)
        elif freq == "M": c = to_monthly(c); b = to_monthly(b)
        return _rs(c, b, period)
    except: return np.nan


def calc_rsi_tf(series_d, period=14, freq="D"):
    try:
        s = _norm(series_d.dropna())
        if freq == "W": s = to_weekly(s)
        elif freq == "M": s = to_monthly(s)
        return _rsi(s, period)
    except: return np.nan


def calc_ema_tf(series_d, period, freq="D"):
    try:
        s = _norm(series_d.dropna())
        if freq == "W": s = to_weekly(s)
        elif freq == "M": s = to_monthly(s)
        return float(s.ewm(span=period, adjust=False, min_periods=max(2,period//3)).mean().iloc[-1])
    except: return np.nan


def calc_pct_from_52w_high(series_d) -> float:
    try:
        s = _norm(series_d.dropna())
        n = min(252, len(s))
        return (float(s.iloc[-1]) / float(s.iloc[-n:].max()) - 1) * 100
    except: return np.nan


# ─────────────────────────────────────────────────────────────────────────────
#  DASHBOARD BUILDER  v6.0 — clean, decision-oriented layout
# ─────────────────────────────────────────────────────────────────────────────

def build_dashboard_df(stock_df: pd.DataFrame,
                        sector_str_df: pd.DataFrame,
                        market: str,
                        run_time: str, primary_rs=55) -> pd.DataFrame:
    """
    Build 📋 Dashboard as a two-column DataFrame.
    v6.0: Organized into 5 sections:
      1. Market Health     — regime, breadth, signal counts by new Signal_Label
      2. Opportunities     — counts by Signal_Label tier + TV watchlists
      3. Sector Ranking    — sorted by primary RS period
      4. Signal Guide      — how to read each signal label
      5. Full Methodology  — MST/LST/RS30/Supertrend details
    """
    def _cnt(col, val):
        if col not in stock_df.columns or stock_df.empty: return 0
        return int((stock_df[col] == val).sum())

    def _cnt_contains(col, substr):
        if col not in stock_df.columns or stock_df.empty: return 0
        return int(stock_df[col].astype(str).str.contains(substr, na=False).sum())

    is_nse = (market == "INDIA")
    pfx    = "NSE:" if is_nse else ""
    bench  = "NSE:NIFTY" if is_nse else "SPY"
    p1, p2 = 22, 55

    # ── Signal_Label counts ───────────────────────────────────────────────────
    sl_col = "Signal_Label"
    has_sl = sl_col in stock_df.columns and not stock_df.empty

    def _sl(label):
        return _cnt(sl_col, label) if has_sl else 0

    triple   = _sl("🌟 Triple Confirmed")
    rs30_l   = _sl("🌟 RS30 + Long")
    rs30_s   = _sl("🌟 RS30 + Swing")
    rs30_ldr = _sl("🌟 RS30 Leader")
    long_mom_prime = _sl("🌟 Long Momentum")
    prime_oth= _sl("🌟 Prime Setup")
    long_mom = _sl("✅ Long Momentum")
    strong_rs= _sl("✅ Strong RS")
    swing    = _sl("📈 Swing Entry")
    rs_ldr   = _sl("📈 RS Leader")
    bld      = _sl("👁 Setup Building")
    w_rs30   = _sl("👁 RS30 Watch")
    w_lst    = _sl("👁 LST Watch")
    w_mst    = _sl("👁 MST Watch")
    w_oth    = _sl("👁 Watch")
    neutral  = _sl("⬜ Neutral")
    avoid    = _sl("🔴 RS Breakdown")

    total_prime = triple + rs30_l + rs30_s + rs30_ldr + long_mom_prime + prime_oth
    total_conf  = long_mom + strong_rs
    total_rsbuy = swing + rs_ldr
    total_watch = bld + w_rs30 + w_lst + w_mst + w_oth
    total_buy   = total_prime + total_conf + total_rsbuy
    total_avoid = avoid

    # ── Action_Tier fallback counts (if Signal_Label not present) ─────────────
    prime_b = _cnt("Action_Tier", "PRIME BUY")
    conf_b  = _cnt("Action_Tier", "CONFIRMED BUY")
    rs_b    = _cnt("Action_Tier", "RS BUY")
    watch_b = _cnt("Action_Tier", "WATCH")
    avoid_b = _cnt("Action_Tier", "AVOID")

    # ── SL quality on buy stocks ──────────────────────────────────────────────
    sl_a = sl_b_g = sl_c = 0
    if "SL_Grade" in stock_df.columns and not stock_df.empty:
        buy_df = stock_df[stock_df.get("Signal_Label", stock_df.get("Signal", pd.Series())).astype(str).str.contains("🌟|✅|📈", na=False)]
        if buy_df.empty:
            buy_df = stock_df[stock_df["Signal"].isin(["Buy","Strong Buy"])]
        sl_a   = int((buy_df["SL_Grade"] == "A").sum())
        sl_b_g = int((buy_df["SL_Grade"] == "B").sum())
        sl_c   = int((buy_df["SL_Grade"] == "C").sum())

    # ── TV Watchlists ─────────────────────────────────────────────────────────
    def _tv_sl(prefix_emoji):
        if not has_sl: return ""
        syms = stock_df[stock_df[sl_col].astype(str).str.startswith(prefix_emoji)]["Symbol"].tolist()
        return "".join(f"{pfx}{s}," for s in syms[:50])

    def _tv_at(at_val):
        if "Action_Tier" not in stock_df.columns: return ""
        syms = stock_df[stock_df["Action_Tier"] == at_val]["Symbol"].tolist()
        return "".join(f"{pfx}{s}," for s in syms[:50])

    tv_prime    = _tv_sl("🌟") or _tv_at("PRIME BUY")
    tv_conf     = _tv_sl("✅") or _tv_at("CONFIRMED BUY")
    tv_rsbuy    = _tv_sl("📈") or _tv_at("RS BUY")
    tv_all_buy  = (tv_prime + tv_conf + tv_rsbuy)[:2000]

    rows = [
        # ══════════════════════════════════════════════════════════════════════
        [f"══ FundaTechno Market Analysis  v6.0  [{market}] ══", ""],
        ["Generated",   run_time],
        ["Benchmark",   bench],
        ["Universe",    f"{len(stock_df)} stocks"],
        ["", ""],

        # ── SECTION 1: MARKET HEALTH ─────────────────────────────────────────
        ["── MARKET HEALTH ──", ""],
        ["Total stocks analysed",  len(stock_df)],
        ["🌟 PRIME BUY (highest conviction)", total_prime if has_sl else prime_b],
        ["✅ CONFIRMED BUY",                  total_conf  if has_sl else conf_b],
        ["📈 RS BUY",                         total_rsbuy if has_sl else rs_b],
        ["👁 WATCH (pre-breakout setups)",    total_watch if has_sl else watch_b],
        ["🔴 AVOID (RS breakdown)",           total_avoid if has_sl else avoid_b],
        ["⬜ Neutral",  neutral if has_sl else (len(stock_df) - prime_b - conf_b - rs_b - watch_b - avoid_b)],
        ["", ""],
        ["── SL QUALITY ON BUY STOCKS ──", ""],
        ["Grade A  ≤3%  (Ideal tight stop)",   sl_a],
        ["Grade B  3-5% (Good)",               sl_b_g],
        ["Grade C  5-8% (Acceptable)",         sl_c],
        ["", ""],

        # ── SECTION 2: SIGNAL BREAKDOWN (detailed) ───────────────────────────
        ["── SIGNAL BREAKDOWN ──", ""],
        ["🌟 Triple Confirmed  (RS30+LST+MST)",  triple],
        ["🌟 RS30 + Long  (RS30+LST)",            rs30_l],
        ["🌟 RS30 + Swing  (RS30+MST)",           rs30_s],
        ["🌟 RS30 Leader  (weekly momentum+funda)",rs30_ldr],
        ["🌟 Long Momentum  (LST+strong funda)",   long_mom_prime],
        ["🌟 Prime Setup  (other Prime)",          prime_oth],
        ["✅ Long Momentum  (LST Buy)",            long_mom],
        ["✅ Strong RS  (all 5 peer filters)",     strong_rs],
        ["📈 Swing Entry  (MST Buy)",              swing],
        ["📈 RS Leader  (RS Buy, index+sector)",   rs_ldr],
        ["👁 Setup Building  (multiple watches)",  bld],
        ["👁 RS30 Watch",                          w_rs30],
        ["👁 LST Watch",                           w_lst],
        ["👁 MST Watch",                           w_mst],
        ["🔴 RS Breakdown  (Sell signal)",         avoid],
        ["", ""],

        # ── SECTION 3: TV WATCHLISTS ──────────────────────────────────────────
        ["── 📺 TRADINGVIEW WATCHLISTS ──", ""],
        ["HOW TO USE", "Copy value → TradingView → Watchlist → Import from clipboard"],
        ["🌟 PRIME BUY (all variants)",  tv_prime],
        ["✅ CONFIRMED BUY",             tv_conf],
        ["📈 RS BUY",                    tv_rsbuy],
        ["ALL BUY (Prime+Conf+RS)",      tv_all_buy],
        ["", ""],

        # ── SECTION 4: SECTOR RANKING ─────────────────────────────────────────
        ["── SECTOR RANKING (RS sorted) ──", ""],
    ]

    if not sector_str_df.empty:
        rs_col = {22:"RS_22d%", 55:"RS_55d%", 120:"RS_120d%"}.get(primary_rs, "RS_55d%")
        for _, r in sector_str_df.iterrows():
            rs_v = r.get(rs_col, r.get("RS_55d%", 0)) or 0
            rs22 = r.get("RS_22d%", 0) or 0
            sig  = r.get("Signal", "")
            icon = "✅" if sig == "Buy" else ("🔴" if sig == "Sell" else "⬜")
            rows.append([
                f"  {icon} #{int(r['Rank'])} {r['Sector']}",
                f"Signal:{sig} | RS_{primary_rs}d:{rs_v:+.1f}% | RS22d:{rs22:+.1f}% | RSI:{r.get('RSI_14','—')}",
            ])

    rows += [
        ["", ""],

        # ── SECTION 5: SIGNAL GUIDE ───────────────────────────────────────────
        ["── SIGNAL GUIDE — WHAT EACH LABEL MEANS ──", ""],

        ["🌟 Triple Confirmed",
         "Highest conviction. RS30 + LST + MST all show Buy. "
         "Weekly RS(30)>0, monthly RS(12)>0, daily RS(55)>0. All timeframes aligned. "
         "Entry on price > 20-day swing high. Target 30%+. SL = swing low."],

        ["🌟 RS30 + Long / RS30 + Swing",
         "Two strategies confirmed. RS30 (weekly momentum + fundamentals) confirmed "
         "alongside either Long Swing (monthly trend) or Medium Swing (daily entry)."],

        ["🌟 RS30 Leader",
         "Weekly RS(30)>0 AND EMA(10)>EMA(30) AND price within 10% of 52W high "
         "AND Sales QoQ≥15% AND PAT QoQ≥15%. Breakout confirmed."],

        ["🌟 Long Momentum",
         "Monthly pre-conditions (RS12>0, RSI12>50, Revenue+, PAT+) met. "
         "Weekly entry conditions confirmed. Strong fundamentals (fin_score≥5)."],

        ["✅ Long Momentum",
         "LST Buy signal. Monthly trend bullish. Weekly entry + Supertrend + EMA200 confirmed. "
         "60-120 day swing. Target 30%+. 3× R:R minimum."],

        ["✅ Strong RS",
         "All 5 peer filters pass: RS Buy + beats sector avg + beats industry avg "
         "+ sector RS>0 + industry RS>0. No TF confirmation yet."],

        ["📈 Swing Entry",
         "MST Buy signal. Weekly pre-conditions (RS21>0, RSI>50) AND daily entry "
         "(RS55>0, RSI>50, Supertrend Buy, Close>EMA200, 20-day breakout). "
         "20-60 day swing. Target 20-25%. 2.5× R:R."],

        ["📈 RS Leader",
         "RS Buy: RS_22d>0 AND RS_55d>0 vs index AND vs sector. "
         "Stock beating benchmark and sector on both timeframes."],

        ["👁 Watch (RS30/LST/MST)",
         "Pre-conditions met but no breakout yet. Stock is setting up. "
         "Wait for close above 20-day swing high before entry."],

        ["🔴 RS Breakdown",
         "All RS values negative. Stock lagging index and sector. "
         "Avoid new positions. Consider exit if in-position."],

        ["", ""],

        # ── SECTION 6: FULL METHODOLOGY ───────────────────────────────────────
        ["── METHODOLOGY ──", ""],

        ["RS Formula",       f"(Stock/Stock_Nd) / (Benchmark/Benchmark_Nd) - 1"],
        ["Total_Score",      "RS_Score×0.6 + Fin_Score×2 + SL_Bonus"],
        ["RS_Score",         "RS_22d×35% + RS_55d×30% + RS_120d×20% + RS_252d×15%"],
        ["Fin_Score",        "Sales_YoY≥15% +2 | PAT_YoY≥15% +2 | ROE≥15% +2 | Margin≥10% +1 | D/E<1 +1"],
        ["SL_Bonus",         "Grade A +4 | B +3 | C +2 | D +1 | F +0 | R:R≥3× +2 | ≥2× +1"],

        ["", ""],
        ["MST: Medium Swing (20-60 days)",  ""],
        ["  HTF Weekly pre-cond",    "RS(21)>0 AND RSI(14)>50"],
        ["  Entry Daily cond",       "RS(55)>0 + RSI(14)>50 + Supertrend=Buy + Close>EMA(200) + 20d breakout"],
        ["  Stop",                   "20-day swing low"],
        ["  Target",                 f"{MST_TP1_MULT}×SL (TP1) and {MST_TP2_MULT}×SL (TP2)"],
        ["  Exit",                   "RS(55)<0 OR Supertrend=Sell OR RSI>90"],

        ["", ""],
        ["LST: Long Swing (60-120+ days)", ""],
        ["  HTF Monthly pre-cond",   "RS(12)>0 AND RSI(12)>50 AND Revenue+ AND PAT+"],
        ["  Entry Weekly cond",      "RS(21)>0 + RSI(12)>50 + Supertrend=Buy + EMA(200) + 20w breakout"],
        ["  Stop",                   "20-day swing low (wider, structure-based)"],
        ["  Target",                 f"{LST_TP1_MULT}×SL (TP1) and {LST_TP2_MULT}×SL (TP2)"],

        ["", ""],
        ["RS30: Weekly Momentum (FundaTechno)", ""],
        ["  Technical",              "Weekly RS(30)>0 + EMA(10)>EMA(30) + Within 10% of 52W High"],
        ["  Fundamental",            "Sales QoQ≥15% + PAT QoQ≥15% + MCap≥1000Cr"],
        ["  Entry",                  "Breakout above 20-day swing high"],

        ["", ""],
        ["Supertrend",               "ATR period=10, Multiplier=3.0 (Pine Script ta.supertrend)"],
        ["  Buy",                    "Price crosses above lower band (+1 direction)"],
        ["  Sell (gate)",            "Price crosses below upper band — blocks any Buy tier → WATCH"],

        ["", ""],
        ["Generated by FundaTechno Market Analysis v6.0", run_time],
    ]

    return pd.DataFrame(rows, columns=["Key", "Value"])


# ─────────────────────────────────────────────────────────────────────────────
#  CLASSIFY_TRADE  (unchanged from v5.2 — kept for backward compatibility)
# ─────────────────────────────────────────────────────────────────────────────

def classify_trade(sig: str, enh: str, mst: str, lst: str, rs30: str,
                   active_sl: float = np.nan, fin_sc: int = 0,
                   rs_sc: float = 0.0) -> dict:
    sl = active_sl if (active_sl == active_sl and not np.isnan(float(active_sl))) else np.nan

    def _tp(mult):
        if sl == sl and sl > 0: return round(sl * mult, 2)
        return np.nan

    def _rr(tp_pct):
        if tp_pct == tp_pct and sl == sl and sl > 0: return round(tp_pct / sl, 2)
        return np.nan

    def _build(action, stype, strategy, tp1m, tp2m):
        tp1 = _tp(tp1m); tp2 = _tp(tp2m)
        return dict(action=action, signal_type=stype, strategy=strategy,
                    tp1_pct=tp1, tp2_pct=tp2, rr_t1=_rr(tp1), rr_t2=_rr(tp2))

    if rs30 == "Buy" and lst == "Buy" and mst == "Buy":
        return _build("BUY","RS30 Buy","🌟 RS30+LST+MST triple confirmed",LST_TP1_MULT,LST_TP2_MULT)
    if rs30 == "Buy" and lst == "Buy":
        return _build("BUY","RS30 Buy","🔥 RS30+LST double confirmed",LST_TP1_MULT,LST_TP2_MULT)
    if rs30 == "Buy" and mst == "Buy":
        return _build("BUY","RS30 Buy","🔥 RS30+MST confirmed",MST_TP1_MULT,MST_TP2_MULT)
    if lst == "Buy" and mst == "Buy":
        return _build("BUY","LST Buy","📈 LST+MST multi-TF",LST_TP1_MULT,LST_TP2_MULT)
    if rs30 == "Buy":
        return _build("BUY","RS30 Buy","📊 RS30 weekly momentum",MST_TP1_MULT,MST_TP2_MULT)
    if lst == "Buy":
        return _build("BUY","LST Buy","📈 LST monthly trend",LST_TP1_MULT,LST_TP2_MULT)
    if mst == "Buy":
        return _build("BUY","MST Buy","🎯 MST daily entry",MST_TP1_MULT,MST_TP2_MULT)
    if enh == "Strong Buy":
        return _build("BUY","Strong Buy","⭐ Strong RS peer filters",2.5,3.5)
    if sig == "Buy":
        return _build("BUY","RS Buy","✅ RS Buy index+sector",2.5,3.5)
    if sig == "Sell":
        return _build("SELL","Sell/Exit","🔴 RS breakdown",2.5,3.5)
    ws = "+".join(s for s,v in [("MST",mst),("LST",lst),("RS30",rs30)] if v=="Watch")
    if ws:
        return _build("WAIT","Watch",f"⏳ {ws} Watch — awaiting breakout",np.nan,np.nan)
    return _build("WAIT","No Signal","⬜ No setup — monitor",np.nan,np.nan)
