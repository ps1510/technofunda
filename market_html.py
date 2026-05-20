"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  HTML REPORT GENERATOR  v6.0  —  market_html.py                           ║
║                                                                            ║
║  v6.0 redesign:                                                            ║
║   • Signal_Label badges — 10 distinct labels, each color-coded by tier     ║
║   • Market Health card section — regime + breadth + quick stats            ║
║   • "Opportunities" tab replaces "Top Picks" (decision-first naming)       ║
║   • Sector bars redesigned — signal icon + RS bar + RSI indicator          ║
║   • Stock cards show Signal_Label prominently above all metrics            ║
║   • Trade cards compacted and colour-keyed to Signal_Label                 ║
║   • New "Guide" tab — clean signal reference with colour-coded rows        ║
║   • Dark/light theme via CSS variables + prefers-color-scheme              ║
║   • Tab state preserved in localStorage                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
import os
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
#  SIGNAL LABEL → CSS CLASS
# ─────────────────────────────────────────────────────────────────────────────

_SL_CLASS = {
    "🌟 Triple Confirmed": "sl-triple",
    "🌟 RS30 + Long":      "sl-triple",
    "🌟 RS30 + Swing":     "sl-prime",
    "🌟 RS30 Leader":      "sl-prime",
    "🌟 Long Momentum":    "sl-prime",
    "🌟 Prime Setup":      "sl-prime",
    "✅ Long Momentum":    "sl-confirmed",
    "✅ Strong RS":        "sl-confirmed",
    "📈 Swing Entry":      "sl-rsbuy",
    "📈 RS Leader":        "sl-rsbuy",
    "👁 Setup Building":   "sl-watch",
    "👁 RS30 Watch":       "sl-watch",
    "👁 LST Watch":        "sl-watch",
    "👁 MST Watch":        "sl-watch",
    "👁 Watch":            "sl-watch",
    "⬜ Neutral":          "sl-neutral",
    "🔴 RS Breakdown":     "sl-avoid",
}

_AT_CLASS = {
    "PRIME BUY":     "sl-prime",
    "CONFIRMED BUY": "sl-confirmed",
    "RS BUY":        "sl-rsbuy",
    "WATCH":         "sl-watch",
    "NEUTRAL":       "sl-neutral",
    "AVOID":         "sl-avoid",
}


def _signal_class(val: str) -> str:
    v = str(val or "")
    return _SL_CLASS.get(v) or _AT_CLASS.get(v) or ""


def _cell_class(col: str, val) -> str:
    col = str(col).lower().strip()

    if col == "signal_label":  return _signal_class(val)
    if col == "action_tier":   return _signal_class(val)

    if col in ("signal", "enhanced", "sec_signal"):
        return {"Strong Buy":"sig-strongbuy","Buy":"sig-buy","Sell":"sig-sell","Neutral":"sig-neutral"}.get(str(val),"")

    if col == "action":
        return {"BUY":"sig-buy","SELL":"sig-sell","WAIT":"sig-neutral"}.get(str(val),"")

    if col in ("mst_signal","lst_signal","rs30_signal"):
        return {"Buy":"sig-buy","Watch":"sig-neutral","Neutral":""}.get(str(val),"")

    if col == "supertrend":
        return {"Buy":"pos","Sell":"neg"}.get(str(val),"")

    if col == "trend":
        v = str(val)
        if "Bullish" in v or "BULLISH" in v: return "pos-strong"
        if "Bearish" in v or "BEARISH" in v: return "neg-strong"
        return ""

    if col == "sec_gated":
        return "pos-strong" if str(val) == "✓" else "dim"

    if col == "sl_grade":
        return {"A":"pos-strong","B":"pos","C":"pos-dim","D":"neg-dim","F":"neg"}.get(str(val),"")

    if col in ("sl_buy%","sl%","sl_sell%"):
        try:
            f = float(val)
            if f <= 3:  return "pos-strong"
            if f <= 5:  return "pos"
            if f <= 8:  return "pos-dim"
            if f <= 12: return "neg-dim"
            return "neg"
        except: pass

    pct_cols = {
        "chg_1d%","chg_5d%","rs_22d%","rs_55d%","rs_120d%","rs_252d%",
        "rs_22d_idx%","rs_55d_idx%","rs_120d_idx%","rs_252d_idx%",
        "rs_22d_sec%","rs_55d_sec%","1m%","3m%","6m%","12m%","ytd%",
        "sales_yoy%","pat_yoy%","sales_qoq%","pat_qoq%","roe%","margin%",
        "w_rs21%","w_rs30%","m_rs12%","sec_rs22d%","sec_rs55d%",
    }
    if col in pct_cols or col.endswith("%"):
        try:
            f = float(val)
            if f > 5:  return "pos-strong"
            if f > 0:  return "pos"
            if f < -5: return "neg-strong"
            if f < 0:  return "neg"
        except: pass
    return ""


def _fmt(val) -> str:
    if val is None: return ""
    if isinstance(val, float):
        if np.isnan(val): return ""
        if val == int(val) and abs(val) < 1e9: return str(int(val))
        return f"{val:.2f}"
    s = str(val)
    return "" if s in ("nan","None","") else s


# ─────────────────────────────────────────────────────────────────────────────
#  TABLE BUILDER  (searchable + sortable)
# ─────────────────────────────────────────────────────────────────────────────

_SKIP_COLS = {"tv_symbol","_o","primary_rs_period"}
_LEFT_COLS = {"symbol","company","name","sector","industry","country","region","commodity",
              "group","chart_pattern","setup_desc","strategy","notes","signal_type","trend",
              "signal_label","etf"}


def _build_table(df: pd.DataFrame, table_id: str, searchable=True, max_rows=2000) -> str:
    if df is None or df.empty:
        return '<p class="empty">No data available.</p>'
    df = df.head(max_rows).copy()
    cols = [c for c in df.columns if c.lower().strip() not in _SKIP_COLS]

    ths = "".join(
        f'<th style="text-align:{"left" if c.lower() in _LEFT_COLS else "center"}" '
        f'onclick="sortTable(this)">{c}</th>'
        for c in cols
    )

    rows_html = ""
    for _, row in df.iterrows():
        tds = ""
        for c in cols:
            val = row[c]; display = _fmt(val); cls = _cell_class(c, val)
            align = "left" if c.lower() in _LEFT_COLS else "center"
            ca = f' class="{cls}"' if cls else ""
            tds += f'<td{ca} style="text-align:{align}">{display}</td>'
        rows_html += f"<tr>{tds}</tr>"

    search = f'''<div class="tbl-search">
      <input type="text" placeholder="🔍 Filter…" oninput="filterTable(this,'{table_id}')">
    </div>''' if searchable else ""

    return f"""{search}
    <div class="tbl-wrap">
      <table id="{table_id}" class="data-tbl">
        <thead><tr>{ths}</tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    <p class="row-count" id="{table_id}-count">{len(df)} rows</p>"""


# ─────────────────────────────────────────────────────────────────────────────
#  MARKET HEALTH CARD  (shown at top of Market tab)
# ─────────────────────────────────────────────────────────────────────────────

def _build_health_card(stock_df, sector_str_df, market):
    if stock_df is None or stock_df.empty: return ""

    sl_col = "Signal_Label" if "Signal_Label" in stock_df.columns else None
    at_col = "Action_Tier"  if "Action_Tier"  in stock_df.columns else None

    def _cnt_sl(emoji):
        if sl_col: return int(stock_df[sl_col].astype(str).str.startswith(emoji).sum())
        return 0

    def _cnt_at(val):
        if at_col: return int((stock_df[at_col] == val).sum())
        return 0

    prime = _cnt_sl("🌟") or _cnt_at("PRIME BUY")
    conf  = _cnt_sl("✅") or _cnt_at("CONFIRMED BUY")
    rsbuy = _cnt_sl("📈") or _cnt_at("RS BUY")
    watch = _cnt_sl("👁") or _cnt_at("WATCH")
    avoid = _cnt_sl("🔴") or _cnt_at("AVOID")
    total = len(stock_df)

    buy_pct   = round((prime + conf + rsbuy) / max(total, 1) * 100)
    avoid_pct = round(avoid / max(total, 1) * 100)

    # Market mood
    if buy_pct >= 50:    mood, mood_cls = "Risk-On 🟢", "mood-on"
    elif buy_pct >= 25:  mood, mood_cls = "Mixed ⚪", "mood-mix"
    else:                mood, mood_cls = "Risk-Off 🔴", "mood-off"

    # Top sectors
    top_secs = ""
    if sector_str_df is not None and not sector_str_df.empty:
        for _, r in sector_str_df.head(3).iterrows():
            sig = r.get("Signal","")
            cls = "pos-strong" if sig == "Buy" else ("neg" if sig == "Sell" else "dim")
            rs  = r.get("RS_22d%", r.get("RS_55d%", 0)) or 0
            top_secs += f'<span class="sec-pill {cls}">{r["Sector"]} {rs:+.1f}%</span>'

    return f"""<div class="health-card">
  <div class="hc-grid">
    <div class="hc-block">
      <div class="hc-label">Market Mood</div>
      <div class="hc-value {mood_cls}">{mood}</div>
    </div>
    <div class="hc-block">
      <div class="hc-label">Stocks Analysed</div>
      <div class="hc-value">{total}</div>
    </div>
    <div class="hc-block">
      <div class="hc-label">Buy Setups</div>
      <div class="hc-value pos-strong">{prime+conf+rsbuy} <span class="hc-sub">({buy_pct}%)</span></div>
    </div>
    <div class="hc-block">
      <div class="hc-label">🌟 Prime</div>
      <div class="hc-value sl-triple-inline">{prime}</div>
    </div>
    <div class="hc-block">
      <div class="hc-label">✅ Confirmed</div>
      <div class="hc-value sl-confirmed-inline">{conf}</div>
    </div>
    <div class="hc-block">
      <div class="hc-label">📈 RS Buy</div>
      <div class="hc-value sl-rsbuy-inline">{rsbuy}</div>
    </div>
    <div class="hc-block">
      <div class="hc-label">👁 Watch</div>
      <div class="hc-value sl-watch-inline">{watch}</div>
    </div>
    <div class="hc-block">
      <div class="hc-label">🔴 Avoid</div>
      <div class="hc-value sl-avoid-inline">{avoid}</div>
    </div>
  </div>
  <div class="hc-sectors">
    <span class="hc-label">Top Sectors: </span>{top_secs}
  </div>
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
#  SNAPSHOT CARDS
# ─────────────────────────────────────────────────────────────────────────────

def _build_snap_cards(snapshot_df):
    if snapshot_df is None or snapshot_df.empty: return ""
    cards = ""
    for _, row in snapshot_df.iterrows():
        name = _fmt(row.get("Name","")); price = _fmt(row.get("Price",""))
        chg1 = row.get("Chg_1D%",""); trend = _fmt(row.get("Trend",""))
        if not name or "──" in name: continue
        try:
            cf = float(chg1); cls = "pos" if cf > 0 else ("neg" if cf < 0 else ""); cs = f"{cf:+.2f}%"
        except: cls = ""; cs = _fmt(chg1)
        tc = "pos-strong" if "Bullish" in trend else ("neg-strong" if "Bearish" in trend else "dim")
        cards += f"""<div class="snap-card">
  <div class="snap-name">{name}</div>
  <div class="snap-price">{price}</div>
  <div class="snap-chg {cls}">{cs}</div>
  <div class="snap-trend {tc}">{trend}</div>
</div>"""
    return f'<div class="snap-grid">{cards}</div>'


# ─────────────────────────────────────────────────────────────────────────────
#  SECTOR BARS  (visual RS bar with signal icon)
# ─────────────────────────────────────────────────────────────────────────────

def _build_sector_bars(sector_df):
    if sector_df is None or sector_df.empty: return ""
    html = '<div class="sector-bars">'
    for _, row in sector_df.iterrows():
        sec  = _fmt(row.get("Sector",""))
        sig  = _fmt(row.get("Signal",""))
        rs22 = row.get("RS_22d%", 0); rs55 = row.get("RS_55d%", 0)
        rank = _fmt(row.get("Rank",""))
        rsi  = _fmt(row.get("RSI_14",""))
        try:  r22 = float(rs22); r55 = float(rs55)
        except: r22 = 0; r55 = 0
        bar_w   = min(abs(r22) * 3, 100)
        bar_cls = "bar-pos" if r22 >= 0 else "bar-neg"
        icon = "✅" if sig == "Buy" else ("🔴" if sig == "Sell" else "⬜")
        sc   = "sig-buy" if sig == "Buy" else ("sig-sell" if sig == "Sell" else "sig-neutral")
        rsi_cls = "pos" if rsi and float(rsi) > 50 else "neg" if rsi and float(rsi) < 50 else ""
        html += f"""<div class="sec-row">
  <div class="sec-rank">#{rank}</div>
  <div class="sec-name">{icon} {sec}</div>
  <div class="sec-bar-wrap"><div class="sec-bar {bar_cls}" style="width:{bar_w:.0f}%"></div></div>
  <div class="sec-rs {'' if r22>=0 else 'neg'}">{r22:+.1f}%</div>
  <div class="sec-rs55 {'' if r55>=0 else 'neg'}">{r55:+.1f}%</div>
  <div class="sec-rsi {rsi_cls}">RSI {rsi}</div>
  <div class="{sc} sec-sig-badge">{sig}</div>
</div>"""
    html += "</div>"
    return html


# ─────────────────────────────────────────────────────────────────────────────
#  OPPORTUNITIES CARDS  (Signal_Label prominently at top of each card)
# ─────────────────────────────────────────────────────────────────────────────

def _build_opportunity_cards(df):
    if df is None or df.empty: return ""
    if "Message" in df.columns:
        return f'<p class="empty">{df["Message"].iloc[0]}</p>'

    prev_sec = ""; html = ""
    for _, row in df.iterrows():
        sec = _fmt(row.get("Sector",""))
        sym = _fmt(row.get("Symbol",""))
        if not sym: continue

        if sec != prev_sec:
            sec_sig  = _fmt(row.get("Sec_Signal",""))
            sec_rs   = row.get("Sec_RS22d%", row.get("Sec_RS55d%",""))
            try: rs_s = f"{float(sec_rs):+.1f}%"
            except: rs_s = _fmt(sec_rs)
            sc = "sig-buy" if sec_sig == "Buy" else ("sig-sell" if sec_sig == "Sell" else "sig-neutral")
            html += f'<div class="opp-sec-hdr"><span>{sec}</span><span class="{sc}">{sec_sig} {rs_s}</span></div>'
            prev_sec = sec

        sl    = _fmt(row.get("Signal_Label", row.get("Action_Tier","")))
        sl_c  = _signal_class(sl)
        company = _fmt(row.get("Company",""))
        price   = _fmt(row.get("Price",""))
        rs22    = row.get("RS_22d_Idx%","")
        rsi     = _fmt(row.get("RSI_14",""))
        sl_pct  = _fmt(row.get("SL_Buy%",""))
        sl_gr   = _fmt(row.get("SL_Grade",""))
        score   = _fmt(row.get("Total_Score",""))
        sal_yoy = _fmt(row.get("Sales_YoY%",""))
        pat_yoy = _fmt(row.get("PAT_YoY%",""))
        chart_p = _fmt(row.get("Chart_Pattern",""))
        try: rs_s = f"{float(rs22):+.1f}%"
        except: rs_s = _fmt(rs22)
        rs_cls = "pos-strong" if rs_s.startswith("+") else "neg-strong"
        sl_g_cls = {"A":"pos-strong","B":"pos","C":"pos-dim","D":"neg-dim","F":"neg"}.get(sl_gr,"")
        currency = "₹" if "NS" in sym or len(sym) < 5 else "$"

        html += f"""<div class="opp-card">
  <div class="opp-head">
    <span class="opp-sym">{sym}</span>
    <span class="sl-badge {sl_c}">{sl}</span>
  </div>
  <div class="opp-company">{company}</div>
  <div class="opp-metrics">
    <div class="m-row"><span class="ml">Price</span><span>{currency}{price}</span></div>
    <div class="m-row"><span class="ml">RS 22d</span><span class="{rs_cls}">{rs_s}</span></div>
    <div class="m-row"><span class="ml">RSI</span><span>{rsi}</span></div>
    <div class="m-row"><span class="ml">SL%</span><span>{sl_pct}% <span class="{sl_g_cls}">[{sl_gr}]</span></span></div>
    <div class="m-row"><span class="ml">Score</span><span class="pos">{score}</span></div>
    <div class="m-row"><span class="ml">Sales YoY</span><span>{sal_yoy}%</span></div>
    <div class="m-row"><span class="ml">PAT YoY</span><span>{pat_yoy}%</span></div>
  </div>
  {f'<div class="opp-pattern">{chart_p}</div>' if chart_p else ''}
  <button class="copy-btn sm" data-orig="📋" onclick="copyText(this,'{sym},')">📋 Copy TV</button>
</div>"""

    return f'<div class="opp-cards">{html}</div>'


# ─────────────────────────────────────────────────────────────────────────────
#  SIGNAL GUIDE  (human-readable, colour-keyed reference)
# ─────────────────────────────────────────────────────────────────────────────

_GUIDE_ROWS = [
    ("🌟 Triple Confirmed",
     "sl-triple",
     "RS30 + LST + MST all fire Buy simultaneously. Highest conviction setup. "
     "All timeframes (weekly, monthly, daily) confirm. Target 30%+. R:R ≥3×.",
     "RS30 weekly momentum + fundamentals confirmed. LST monthly trend confirmed. "
     "MST daily entry confirmed. Price > 20-day swing high."),

    ("🌟 RS30 + Long / RS30 + Swing",
     "sl-triple",
     "Two strategies confirmed: RS30 (weekly momentum) + either LST (monthly trend) "
     "or MST (daily swing). Very high conviction.",
     "Weekly RS(30)>0, EMA10>30, near 52W high, funda OK. Plus monthly or daily confirmation."),

    ("🌟 RS30 Leader",
     "sl-prime",
     "RS30 strategy confirmed alone: Weekly RS(30)>0 + EMA(10)>EMA(30) + "
     "price within 10% of 52W high + Sales QoQ≥15% + PAT QoQ≥15%. "
     "Breakout above 20-day swing high.",
     "FundaTechno weekly momentum strategy. Strong fundamentals + technical breakout required."),

    ("🌟 Long Momentum",
     "sl-prime",
     "LST Buy with strong fundamentals (fin_score ≥ 5). "
     "Monthly trend bullish (RS12>0, RSI>50, Revenue+, PAT+). "
     "Weekly entry confirmed. 60-120 day swing. Target 30%+.",
     "Monthly pre-conditions + weekly entry + Supertrend + EMA200. "
     "Best held for 2-3 months minimum."),

    ("✅ Long Momentum",
     "sl-confirmed",
     "LST Buy without prime-level fin_score. "
     "Strong sector + monthly trend + weekly entry all confirmed. "
     "60-120 day swing.",
     "Monthly RS(12)>0, RSI(12)>50, Revenue+, PAT+. "
     "Weekly RS(21)>0 + RSI(12)>50 + Supertrend=Buy + EMA200."),

    ("✅ Strong RS",
     "sl-confirmed",
     "All 5 peer filters pass: RS Buy + stock beats sector avg + beats industry avg "
     "+ sector RS>0 + industry RS>0. Strong relative performance vs all peers. "
     "No TF confirmation yet.",
     "RS_22d_Idx>0 + RS_55d_Idx>0 + RS_22d_Sec>0 + RS_55d_Sec>0 + "
     "beats sector ret + beats industry ret."),

    ("📈 Swing Entry",
     "sl-rsbuy",
     "MST Buy: Weekly pre-conditions + daily entry fully confirmed + 20-day breakout. "
     "20-60 day swing. Target 20-25%. 2.5× R:R minimum.",
     "Weekly: RS(21)>0, RSI(14)>50. Daily: RS(55)>0, RSI(14)>50, "
     "Supertrend=Buy, Close>EMA(200), Close > 20-day swing high."),

    ("📈 RS Leader",
     "sl-rsbuy",
     "RS Buy: RS_22d>0 AND RS_55d>0 vs both index AND sector. "
     "Stock outperforming market + sector on both 1M and 3M. "
     "Waiting for TF confirmation (MST/LST).",
     "Four RS checks all positive: 22d-index, 55d-index, 22d-sector, 55d-sector."),

    ("👁 Watch (any variant)",
     "sl-watch",
     "Pre-conditions met but no confirmed breakout yet. "
     "Stock is consolidating near resistance. "
     "Wait for close above 20-day swing high before entry.",
     "RS30 Watch: technical OK, awaiting breakout. "
     "LST Watch: monthly OK, weekly entry pending. "
     "MST Watch: weekly OK, daily entry/breakout pending."),

    ("⬜ Neutral",
     "sl-neutral",
     "Mixed RS signals or insufficient data. "
     "Stock neither leading nor lagging meaningfully. "
     "No action required.",
     "RS values inconsistent — some positive, some negative across periods."),

    ("🔴 RS Breakdown",
     "sl-avoid",
     "RS Sell: All RS values negative vs index AND sector. "
     "Stock clearly underperforming. Avoid new positions. "
     "Consider exit if holding.",
     "RS_22d_Idx<0 AND RS_55d_Idx<0 AND RS_22d_Sec<0 AND RS_55d_Sec<0. "
     "Sustained underperformance."),
]


def _build_guide() -> str:
    rows = ""
    for label, cls, summary, detail in _GUIDE_ROWS:
        rows += f"""<div class="guide-row">
  <div class="guide-label-col">
    <span class="sl-badge {cls}">{label}</span>
  </div>
  <div class="guide-content">
    <div class="guide-summary">{summary}</div>
    <div class="guide-detail">{detail}</div>
  </div>
</div>"""

    meta = """<div class="guide-meta">
  <h3>Scoring Formula</h3>
  <div class="guide-table">
    <div class="gt-row"><span class="gt-k">Total_Score</span><span>RS_Score×0.6 + Fin_Score×2 + SL_Bonus</span></div>
    <div class="gt-row"><span class="gt-k">RS_Score</span><span>RS_22d×35% + RS_55d×30% + RS_120d×20% + RS_252d×15%</span></div>
    <div class="gt-row"><span class="gt-k">Fin_Score</span><span>Sales_YoY≥15% +2  |  PAT_YoY≥15% +2  |  ROE≥15% +2  |  Margin≥10% +1  |  D/E&lt;1 +1</span></div>
    <div class="gt-row"><span class="gt-k">SL_Bonus</span><span>Grade A +4  |  B +3  |  C +2  |  D +1  |  R:R≥3× +2  |  ≥2× +1</span></div>
    <div class="gt-row"><span class="gt-k">Supertrend Gate</span><span>Supertrend=Sell → any Buy tier → WATCH (blocks entry)</span></div>
  </div>
  <h3>Stop Loss Grades</h3>
  <div class="guide-table">
    <div class="gt-row"><span class="sl-badge sl-confirmed">A ≤3%</span><span>Ideal — very tight stop, high reward:risk</span></div>
    <div class="gt-row"><span class="sl-badge sl-confirmed">B ≤5%</span><span>Good — acceptable for MST (20-60 day)</span></div>
    <div class="gt-row"><span class="sl-badge sl-watch">C ≤8%</span><span>Acceptable for LST (60-120 day)</span></div>
    <div class="gt-row"><span class="sl-badge sl-watch">D ≤12%</span><span>Wide — only for high-conviction LST</span></div>
    <div class="gt-row"><span class="sl-badge sl-avoid">F &gt;12%</span><span>Too wide — skip or wait for tighter entry</span></div>
  </div>
</div>"""

    return f'<div class="guide">{rows}{meta}</div>'


# ─────────────────────────────────────────────────────────────────────────────
#  DASHBOARD SECTION
# ─────────────────────────────────────────────────────────────────────────────

def _build_dashboard(df: pd.DataFrame) -> str:
    if df is None or df.empty: return ""
    html = ""
    for _, row in df.iterrows():
        k = _fmt(row.get("Key","")); v = _fmt(row.get("Value",""))
        if not k and not v:
            html += '<div class="dash-spacer"></div>'; continue
        if k.startswith("══") or k.startswith("──"):
            html += f'<div class="dash-section">{k}</div>'; continue
        is_tv = "TV" in k or "TRADINGVIEW" in k.upper() or k in ("ALL BUY (Prime+Conf+RS)",)
        if is_tv and v and len(v) > 10:
            v_html = f'<span class="tv-list">{v[:200]}{"…" if len(v)>200 else ""}</span>' \
                     f'<button class="copy-btn sm" data-orig="📋" onclick="copyText(this,\'{v[:500].replace(chr(39),"")}\')">Copy</button>'
        else:
            v_html = v
        vcls = ""
        if k.startswith("🌟"):   vcls = " sl-triple-inline"
        elif k.startswith("✅"): vcls = " sl-confirmed-inline"
        elif k.startswith("📈"): vcls = " sl-rsbuy-inline"
        elif k.startswith("👁"): vcls = " sl-watch-inline"
        elif k.startswith("🔴"): vcls = " sl-avoid-inline"
        html += f'<div class="dash-row"><div class="dash-key">{k}</div><div class="dash-val{vcls}">{v_html}</div></div>'
    return html


# ─────────────────────────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
:root {
  --bg:      #0f1117; --bg2: #151820; --bg3: #1c1f2e;
  --border:  rgba(255,255,255,0.07);
  --text:    #e2e4ec; --text2: #8b90a8; --text3: #4d5268;
  --accent:  #5b8def;
  --green:   #22c55e; --green2: #16a34a;
  --red:     #ef4444; --amber:  #f59e0b;
  --radius:  10px; --shadow: 0 2px 14px rgba(0,0,0,0.4);
  /* Signal tier palette */
  --sl-triple-bg: #0d2b1a; --sl-triple-fg: #4ade80;
  --sl-prime-bg:  #0f3024; --sl-prime-fg:  #86efac;
  --sl-conf-bg:   #c8e6c9; --sl-conf-fg:   #1b5e20;
  --sl-rsbuy-bg:  #e8f5e9; --sl-rsbuy-fg:  #1b5e20;
  --sl-watch-bg:  #2d1b0d; --sl-watch-fg:  #fde68a;
  --sl-neutral-bg:#374151; --sl-neutral-fg:#9ca3af;
  --sl-avoid-bg:  #2d0d0d; --sl-avoid-fg:  #fca5a5;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg:#f8fafc; --bg2:#ffffff; --bg3:#f1f5f9;
    --border:rgba(0,0,0,0.07); --text:#1e293b; --text2:#64748b; --text3:#94a3b8;
    --shadow:0 2px 14px rgba(0,0,0,0.08);
    --sl-triple-bg:#dcfce7; --sl-triple-fg:#14532d;
    --sl-prime-bg: #d1fae5; --sl-prime-fg: #166534;
    --sl-watch-bg: #fefce8; --sl-watch-fg: #92400e;
    --sl-avoid-bg: #fef2f2; --sl-avoid-fg: #991b1b;
    --sl-neutral-bg:#f3f4f6; --sl-neutral-fg:#6b7280;
  }
}
*{box-sizing:border-box;margin:0;padding:0;}
html{scroll-behavior:smooth;}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
     background:var(--bg);color:var(--text);font-size:14px;line-height:1.5;}

/* ── HEADER ── */
.app-header{background:var(--bg2);border-bottom:1px solid var(--border);
  padding:10px 16px;position:sticky;top:0;z-index:100;
  display:flex;align-items:center;justify-content:space-between;gap:10px;}
.app-title{font-size:15px;font-weight:700;color:var(--accent);}
.app-meta{font-size:11px;color:var(--text3);}
.regime-BULL{background:#166534;color:#fff;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:600;}
.regime-CAUTION{background:#92400e;color:#fff;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:600;}
.regime-BEAR{background:#7f1d1d;color:#fff;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:600;}

/* ── SIGNAL LABEL BADGES ── */
.sl-badge{display:inline-block;padding:3px 9px;border-radius:10px;
  font-size:11px;font-weight:600;white-space:nowrap;}
.sl-triple  {background:var(--sl-triple-bg);color:var(--sl-triple-fg);}
.sl-prime   {background:var(--sl-prime-bg); color:var(--sl-prime-fg);}
.sl-confirmed{background:var(--sl-conf-bg); color:var(--sl-conf-fg);}
.sl-rsbuy   {background:var(--sl-rsbuy-bg); color:var(--sl-rsbuy-fg);}
.sl-watch   {background:var(--sl-watch-bg); color:var(--sl-watch-fg);}
.sl-neutral {background:var(--sl-neutral-bg);color:var(--sl-neutral-fg);}
.sl-avoid   {background:var(--sl-avoid-bg); color:var(--sl-avoid-fg);}
/* inline value coloring (no badge border-radius) */
.sl-triple-inline{color:var(--sl-triple-fg);font-weight:700;}
.sl-confirmed-inline{color:var(--green2);font-weight:600;}
.sl-rsbuy-inline{color:#33691e;font-weight:600;}
.sl-watch-inline{color:var(--amber);}
.sl-avoid-inline{color:var(--red);}

/* ── QUICK STATS BAR ── */
.stats-bar{display:flex;gap:8px;padding:8px 12px;background:var(--bg2);
  border-bottom:1px solid var(--border);overflow-x:auto;scrollbar-width:none;}
.stats-bar::-webkit-scrollbar{display:none;}

/* ── TABS ── */
.tab-bar{display:flex;overflow-x:auto;background:var(--bg2);
  border-bottom:1px solid var(--border);position:sticky;top:49px;z-index:99;
  scrollbar-width:none;}
.tab-bar::-webkit-scrollbar{display:none;}
.tab-btn{padding:10px 14px;font-size:13px;white-space:nowrap;border:none;
  background:none;color:var(--text2);cursor:pointer;
  border-bottom:2px solid transparent;transition:all .15s;flex-shrink:0;}
.tab-btn.active{color:var(--accent);border-bottom-color:var(--accent);font-weight:600;}
.tab-btn:hover{color:var(--text);}

/* ── CONTENT ── */
.tab-content{display:none;padding:14px 12px;max-width:1400px;margin:0 auto;}
.tab-content.active{display:block;}
.sec-title{font-size:14px;font-weight:600;color:var(--text);
  margin:18px 0 8px;border-left:3px solid var(--accent);padding-left:10px;}
.sec-title:first-child{margin-top:0;}

/* ── MARKET HEALTH CARD ── */
.health-card{background:var(--bg2);border:1px solid var(--border);
  border-radius:var(--radius);padding:16px;margin-bottom:16px;}
.hc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:12px;margin-bottom:12px;}
.hc-block{text-align:center;}
.hc-label{font-size:11px;color:var(--text3);margin-bottom:4px;}
.hc-value{font-size:18px;font-weight:700;}
.hc-sub{font-size:12px;font-weight:400;color:var(--text2);}
.hc-sectors{display:flex;flex-wrap:wrap;gap:6px;align-items:center;}
.sec-pill{padding:3px 8px;border-radius:8px;font-size:12px;font-weight:500;
  background:var(--bg3);color:var(--text2);}
.sec-pill.pos-strong{background:#0d3320;color:#4ade80;}
.sec-pill.neg{background:#2d0d0d;color:#fca5a5;}
.mood-on{color:#22c55e;} .mood-mix{color:var(--amber);} .mood-off{color:var(--red);}

/* ── SNAPSHOT CARDS ── */
.snap-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;margin-bottom:16px;}
.snap-card{background:var(--bg2);border:1px solid var(--border);
  border-radius:var(--radius);padding:10px 12px;}
.snap-name{font-size:11px;color:var(--text3);margin-bottom:3px;}
.snap-price{font-size:15px;font-weight:700;}
.snap-chg{font-size:13px;font-weight:500;margin-top:2px;}
.snap-trend{font-size:11px;margin-top:3px;}

/* ── SECTOR BARS ── */
.sector-bars{display:flex;flex-direction:column;gap:5px;margin-bottom:16px;}
.sec-row{display:grid;grid-template-columns:24px 1fr 80px 52px 52px 52px 56px;
  align-items:center;gap:6px;background:var(--bg2);border-radius:6px;
  padding:6px 10px;border:1px solid var(--border);}
.sec-rank{color:var(--text3);font-size:11px;}
.sec-name{font-size:13px;font-weight:500;}
.sec-bar-wrap{height:5px;background:var(--bg3);border-radius:3px;overflow:hidden;}
.sec-bar{height:100%;border-radius:3px;min-width:2px;}
.bar-pos{background:var(--green);} .bar-neg{background:var(--red);}
.sec-rs,.sec-rs55,.sec-rsi{font-size:12px;text-align:right;}
.sec-sig-badge{font-size:11px;font-weight:600;text-align:center;
  padding:2px 5px;border-radius:4px;}
.sig-buy{background:#c8e6c9;color:#1b5e20;}
.sig-sell{background:#ffcdd2;color:#b71c1c;}
.sig-neutral{background:#fff9c4;color:#5d4037;}
.sig-strongbuy{background:#006b3c;color:#fff;}

/* ── OPPORTUNITY CARDS ── */
.opp-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
  gap:10px;margin-bottom:16px;}
.opp-card{background:var(--bg2);border:1px solid var(--border);
  border-radius:var(--radius);padding:12px 14px;transition:border-color .2s;}
.opp-card:hover{border-color:var(--accent);}
.opp-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;}
.opp-sym{font-size:17px;font-weight:700;}
.opp-company{font-size:12px;color:var(--text3);margin-bottom:8px;}
.opp-metrics{display:grid;grid-template-columns:1fr 1fr;gap:3px 8px;margin-bottom:8px;}
.m-row{display:flex;justify-content:space-between;font-size:12px;
  padding:3px 0;border-bottom:1px solid var(--border);}
.ml{color:var(--text2);}
.opp-pattern{font-size:11px;color:var(--accent);margin-bottom:6px;}
.opp-sec-hdr{display:flex;justify-content:space-between;align-items:center;
  font-size:13px;font-weight:600;padding:8px 4px;color:var(--text2);
  border-bottom:1px solid var(--border);margin-bottom:8px;grid-column:1/-1;}

/* ── TABLES ── */
.tbl-search{margin-bottom:8px;}
.tbl-search input{width:100%;padding:8px 12px;border-radius:8px;
  border:1px solid var(--border);background:var(--bg2);color:var(--text);
  font-size:14px;outline:none;}
.tbl-search input:focus{border-color:var(--accent);}
.tbl-wrap{overflow-x:auto;border-radius:var(--radius);border:1px solid var(--border);margin-bottom:6px;}
table.data-tbl{border-collapse:collapse;width:100%;font-size:12px;min-width:400px;}
.data-tbl thead th{background:#0d1730;color:#90caf9;padding:8px 10px;
  font-weight:600;font-size:11px;white-space:nowrap;cursor:pointer;
  user-select:none;border-bottom:1px solid var(--border);position:sticky;top:0;}
.data-tbl thead th:hover{background:#1a2a4a;}
.data-tbl thead th::after{content:" ↕";opacity:.4;}
.data-tbl thead th.asc::after{content:" ↑";opacity:1;}
.data-tbl thead th.desc::after{content:" ↓";opacity:1;}
.data-tbl tbody tr:nth-child(even){background:var(--bg3);}
.data-tbl tbody tr:hover{background:rgba(91,141,239,0.08);}
.data-tbl td{padding:6px 10px;border-bottom:1px solid var(--border);white-space:nowrap;}
.row-count{font-size:11px;color:var(--text3);margin-bottom:12px;}

/* ── SIGNAL COLORS IN TABLE ── */
.sl-triple td,.data-tbl td.sl-triple{background:var(--sl-triple-bg)!important;color:var(--sl-triple-fg)!important;font-weight:700;}
.data-tbl td.sl-prime{background:var(--sl-prime-bg)!important;color:var(--sl-prime-fg)!important;font-weight:700;}
.data-tbl td.sl-confirmed{background:var(--sl-conf-bg)!important;color:var(--sl-conf-fg)!important;font-weight:600;}
.data-tbl td.sl-rsbuy{background:var(--sl-rsbuy-bg)!important;color:var(--sl-rsbuy-fg)!important;}
.data-tbl td.sl-watch{background:var(--sl-watch-bg)!important;color:var(--sl-watch-fg)!important;}
.data-tbl td.sl-avoid{background:var(--sl-avoid-bg)!important;color:var(--sl-avoid-fg)!important;font-weight:600;}
.data-tbl td.sl-neutral{color:var(--text3);}
.pos-strong{color:var(--green);font-weight:600;}
.pos{color:#81c784;}
.pos-dim{color:#a5d6a7;}
.neg-strong{color:var(--red);font-weight:600;}
.neg{color:#e57373;}
.neg-dim{color:#ef9a9a;}
.dim{color:var(--text3);}

/* ── DASHBOARD ── */
.dash-section{background:#0d47a1;color:#90caf9;padding:8px 12px;
  border-radius:6px;font-weight:600;font-size:13px;margin:10px 0 4px;}
.dash-row{display:grid;grid-template-columns:1fr 1fr;
  border-bottom:1px solid var(--border);padding:6px 4px;gap:8px;}
.dash-key{font-size:12px;font-weight:500;color:var(--text2);}
.dash-val{font-size:12px;color:var(--text);word-break:break-all;}
.dash-spacer{height:8px;}
.tv-list{font-size:11px;color:var(--text3);word-break:break-all;}

/* ── GUIDE ── */
.guide{display:flex;flex-direction:column;gap:10px;margin-bottom:16px;}
.guide-row{display:grid;grid-template-columns:200px 1fr;gap:12px;
  background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:12px;}
.guide-label-col{display:flex;align-items:flex-start;padding-top:2px;}
.guide-content{}
.guide-summary{font-size:13px;margin-bottom:4px;line-height:1.5;}
.guide-detail{font-size:11px;color:var(--text2);line-height:1.5;}
.guide-meta{margin-top:20px;display:flex;flex-direction:column;gap:16px;}
.guide-meta h3{font-size:13px;font-weight:600;color:var(--text2);margin-bottom:6px;}
.guide-table{display:flex;flex-direction:column;gap:4px;}
.gt-row{display:flex;gap:12px;font-size:12px;padding:5px 8px;
  border-radius:4px;background:var(--bg2);}
.gt-k{font-weight:600;color:var(--accent);min-width:140px;}

/* ── VIEW TOGGLE ── */
.view-toggle{display:flex;gap:6px;margin-bottom:10px;}
.vt-btn{padding:5px 14px;border-radius:6px;font-size:12px;
  border:1px solid var(--border);background:transparent;color:var(--text2);cursor:pointer;}
.vt-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);}

/* ── BUTTONS ── */
.copy-btn{margin-top:8px;padding:5px 12px;border-radius:6px;
  border:1px solid var(--accent);background:transparent;color:var(--accent);
  font-size:12px;cursor:pointer;transition:all .15s;}
.copy-btn:hover{background:var(--accent);color:#fff;}
.copy-btn.sm{padding:3px 8px;font-size:11px;margin-top:6px;}
.copy-btn.copied{background:var(--green2);border-color:var(--green);color:#fff;}
.empty{color:var(--text3);font-size:13px;padding:20px 0;text-align:center;}

/* ── RESPONSIVE ── */
@media(max-width:640px){
  .sec-row{grid-template-columns:20px 1fr 44px 44px;}.sec-bar-wrap,.sec-rs55,.sec-rsi{display:none;}
  .opp-cards{grid-template-columns:1fr;}
  .snap-grid{grid-template-columns:repeat(2,1fr);}
  .guide-row{grid-template-columns:1fr;}.guide-label-col{margin-bottom:6px;}
  .dash-row{grid-template-columns:1fr;}
  .hc-grid{grid-template-columns:repeat(4,1fr);}
}
"""

# ─────────────────────────────────────────────────────────────────────────────
#  JAVASCRIPT
# ─────────────────────────────────────────────────────────────────────────────

JS = """
function showTab(id){
  document.querySelectorAll('.tab-content').forEach(e=>e.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(e=>e.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  document.querySelector('[data-tab="'+id+'"]').classList.add('active');
  localStorage.setItem('activeTab',id);
}
document.addEventListener('DOMContentLoaded',()=>{
  const saved = localStorage.getItem('activeTab')||'market';
  showTab(saved);
});
function filterTable(input,tableId){
  const q=input.value.toLowerCase();
  const tbody=document.getElementById(tableId).tBodies[0];
  let vis=0;
  for(const row of tbody.rows){
    const match=row.textContent.toLowerCase().includes(q);
    row.style.display=match?'':'none';
    if(match)vis++;
  }
  const cnt=document.getElementById(tableId+'-count');
  if(cnt)cnt.textContent=vis+' rows';
}
function sortTable(th){
  const table=th.closest('table');
  const tbody=table.tBodies[0];
  const col=th.cellIndex;
  const asc=!th.classList.contains('asc');
  table.querySelectorAll('th').forEach(h=>h.classList.remove('asc','desc'));
  th.classList.add(asc?'asc':'desc');
  const rows=Array.from(tbody.rows);
  rows.sort((a,b)=>{
    let av=a.cells[col]?.textContent.trim()||'';
    let bv=b.cells[col]?.textContent.trim()||'';
    const af=parseFloat(av.replace(/[+%,]/g,''));
    const bf=parseFloat(bv.replace(/[+%,]/g,''));
    if(!isNaN(af)&&!isNaN(bf))return asc?af-bf:bf-af;
    return asc?av.localeCompare(bv):bv.localeCompare(av);
  });
  rows.forEach(r=>tbody.appendChild(r));
}
function copyText(btn,text){
  const orig=btn.dataset.orig||btn.textContent;
  navigator.clipboard.writeText(text).then(()=>{
    btn.textContent='✅ Copied!';btn.classList.add('copied');
    setTimeout(()=>{btn.textContent=orig;btn.classList.remove('copied');},2000);
  }).catch(()=>{
    const el=document.createElement('textarea');
    el.value=text;document.body.appendChild(el);
    el.select();document.execCommand('copy');document.body.removeChild(el);
    btn.textContent='✅ Copied!';
    setTimeout(()=>{btn.textContent=orig;},2000);
  });
}
function toggleView(sid,mode){
  document.querySelectorAll('#'+sid+' .vt-btn').forEach(b=>b.classList.remove('active'));
  document.querySelector('#'+sid+' [data-mode="'+mode+'"]').classList.add('active');
  const cv=document.getElementById(sid+'-cards');
  const tv=document.getElementById(sid+'-table');
  if(cv)cv.style.display=mode==='cards'?'':'none';
  if(tv)tv.style.display=mode==='table'?'':'none';
}
"""


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN BUILD FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def build_html_report(
    market: str,
    snapshot_df:    pd.DataFrame,
    sector_str_df:  pd.DataFrame,
    sector_rot_df:  pd.DataFrame,
    industry_rot_df:pd.DataFrame,
    breadth_df:     pd.DataFrame,
    sector_perf_df: pd.DataFrame,
    stock_str_df:   pd.DataFrame,
    top_buy_df:     pd.DataFrame,
    top_sell_df:    pd.DataFrame,
    chart_pat_df:   pd.DataFrame,
    trade_df:       pd.DataFrame,
    dashboard_df:   pd.DataFrame,
    sleeve_df:      pd.DataFrame,
    country_etf_df: pd.DataFrame,
    commodity_df:   pd.DataFrame,
    output_path:    str,
    run_time:       str = "",
    primary_rs:     int = 55,
) -> str:

    run_time = run_time or datetime.now().strftime("%d %b %Y  %H:%M")

    # Regime detection from dashboard
    regime = "BULL"
    if dashboard_df is not None and not dashboard_df.empty:
        for _, r in dashboard_df.iterrows():
            k = str(r.get("Key",""))
            if "MARKET REGIME" in k.upper():
                if "BEAR" in k.upper():    regime = "BEAR"
                elif "CAUTION" in k.upper(): regime = "CAUTION"
                break

    # Signal counts for stats bar
    sl_col = "Signal_Label" if (stock_str_df is not None and not stock_str_df.empty
                                  and "Signal_Label" in stock_str_df.columns) else None
    at_col = "Action_Tier"  if (stock_str_df is not None and not stock_str_df.empty
                                  and "Action_Tier"  in stock_str_df.columns) else None
    def _cnt(emoji, at_val):
        if sl_col: return int(stock_str_df[sl_col].astype(str).str.startswith(emoji).sum())
        if at_col: return int((stock_str_df[at_col] == at_val).sum())
        return 0
    prime = _cnt("🌟","PRIME BUY")
    conf  = _cnt("✅","CONFIRMED BUY")
    rsbuy = _cnt("📈","RS BUY")
    avoid = _cnt("🔴","AVOID")

    # Simplified stock view for HTML (Signal_Label prominently first)
    MAIN_COLS = ["Symbol","Company","Sector","Price","Chg_1D%",
                 "Signal_Label","Sec_Gated",
                 "RS_22d_Idx%","RS_55d_Idx%","RSI_14","Trend","SMA_Score",
                 "Total_Score","Fin_Score","SL_Buy%","SL_Grade","SL_Buy_Price",
                 "Sales_YoY%","PAT_YoY%","ROE%","D/E","Mkt_Cap_B","Chart_Pattern"]
    if stock_str_df is not None and not stock_str_df.empty:
        stock_main = stock_str_df[[c for c in MAIN_COLS if c in stock_str_df.columns]]
    else:
        stock_main = stock_str_df

    # Sleeve clean (data rows only)
    sleeve_clean = None
    if sleeve_df is not None and not sleeve_df.empty:
        try:
            SLEEVE_COLS = ["Rank","Symbol","Company","Sector","Price","Sleeve_RS","Signal_Label",
                           "RS_22d_Idx%","RS_55d_Idx%","Signal","SL_Buy%","SL_Grade","Equal_Wt%","ATR_Wt%",
                           "Sales_YoY%","PAT_YoY%"]
            clean = sleeve_df[sleeve_df["Rank"].apply(
                lambda x: str(x).strip().isdigit()
            )].copy()
            sleeve_clean = clean[[c for c in SLEEVE_COLS if c in clean.columns]]
        except: sleeve_clean = None

    # ── Build tab content ─────────────────────────────────────────────────────
    tabs = [
        ("market",       "📸 Market"),
        ("sectors",      "🏭 Sectors"),
        ("opportunities","🎯 Opportunities"),
        ("stocks",       "📊 Stocks"),
        ("global",       "🌍 Global"),
        ("sleeves",      "📋 Sleeves"),
        ("guide",        "📚 Guide"),
        ("dashboard",    "📋 Dashboard"),
    ]
    tab_btns = "".join(
        f'<button class="tab-btn" data-tab="{tid}" onclick="showTab(\'{tid}\')">{lbl}</button>'
        for tid, lbl in tabs
    )

    def _sec(tid, title, content):
        return f'<div class="tab-content" id="tab-{tid}"><h2 class="sec-title">{title}</h2>{content}</div>'

    def _toggle(sid, default="cards"):
        other = "table" if default == "cards" else "cards"
        return (f'<div class="view-toggle" id="{sid}">'
                f'<button class="vt-btn {"active" if default=="cards" else ""}" '
                f'data-mode="cards" onclick="toggleView(\'{sid}\',\'cards\')">Cards</button>'
                f'<button class="vt-btn {"active" if default=="table" else ""}" '
                f'data-mode="table" onclick="toggleView(\'{sid}\',\'table\')">Table</button>'
                f'</div>')

    # Market tab
    market_content = (
        _build_health_card(stock_str_df, sector_str_df, market) +
        '<h2 class="sec-title">Market Snapshot</h2>' +
        _build_snap_cards(snapshot_df) +
        '<h2 class="sec-title">Market Breadth</h2>' +
        _build_table(breadth_df, "tbl-breadth", searchable=False)
    )

    # Sectors tab
    sector_content = (
        '<h2 class="sec-title">Sector Strength</h2>' +
        _build_sector_bars(sector_str_df) +
        '<h2 class="sec-title">Sector Performance</h2>' +
        _build_table(sector_perf_df, "tbl-secperf", searchable=False) +
        '<h2 class="sec-title">Sector Rotation</h2>' +
        _build_table(sector_rot_df, "tbl-secrot") +
        '<h2 class="sec-title">Industry Rotation</h2>' +
        _build_table(industry_rot_df, "tbl-indrot")
    )

    # Opportunities tab (cards + table toggle)
    opp_cards = _build_opportunity_cards(top_buy_df)
    opp_table = _build_table(top_buy_df, "tbl-opp-table")
    sell_table = _build_table(top_sell_df, "tbl-sell")
    opp_content = (
        _toggle("vt-opp","cards") +
        f'<div id="vt-opp-cards">{opp_cards}</div>' +
        f'<div id="vt-opp-table" style="display:none">{opp_table}</div>' +
        '<h2 class="sec-title">🔴 Sell Alerts</h2>' + sell_table
    )

    # Stocks tab
    stock_content = _build_table(stock_main, "tbl-stocks", max_rows=500)

    # Global tab
    global_content = (
        '<h2 class="sec-title">🌍 Country ETFs (RS vs SPY)</h2>' +
        _build_table(country_etf_df, "tbl-etfs") +
        '<h2 class="sec-title">🏅 Commodities (RS vs GLD)</h2>' +
        _build_table(commodity_df, "tbl-commod") +
        '<h2 class="sec-title">📐 Chart Patterns</h2>' +
        _build_table(chart_pat_df, "tbl-patterns")
    )

    # Sleeves tab
    sleeves_content = _build_table(sleeve_clean, "tbl-sleeves") if sleeve_clean is not None \
                      else '<p class="empty">Sleeve data unavailable</p>'

    # Guide tab
    guide_content = _build_guide()

    # Dashboard tab
    dash_content = _build_dashboard(dashboard_df)

    sections_html = (
        _sec("market",        "📸 Market Overview",          market_content) +
        _sec("sectors",       "🏭 Sector Analysis",          sector_content) +
        _sec("opportunities", "🎯 Opportunities",            opp_content) +
        _sec("stocks",        "📊 All Stocks",               stock_content) +
        _sec("global",        "🌍 Global Markets",           global_content) +
        _sec("sleeves",       "📋 RS Momentum Portfolios",   sleeves_content) +
        _sec("guide",         "📚 Signal Guide & Reference", guide_content) +
        _sec("dashboard",     "📋 Run Summary & Methodology",dash_content)
    )

    # Stats bar
    stats_bar = (
        f'<div class="stats-bar">'
        f'<span class="sl-badge sl-triple">🌟 Prime {prime}</span>'
        f'<span class="sl-badge sl-confirmed">✅ Conf {conf}</span>'
        f'<span class="sl-badge sl-rsbuy">📈 RS {rsbuy}</span>'
        f'<span class="sl-badge sl-avoid">🔴 Avoid {avoid}</span>'
        f'</div>'
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="theme-color" content="#0f1117">
  <title>FundaTechno [{market}] — {run_time}</title>
  <style>{CSS}</style>
</head>
<body>
<header class="app-header">
  <div>
    <div class="app-title">FundaTechno [{market}]</div>
    <div class="app-meta">{run_time} · RS{primary_rs}d primary</div>
  </div>
  <span class="regime-{regime}">{regime}</span>
</header>
{stats_bar}
<nav class="tab-bar">{tab_btns}</nav>
<main>{sections_html}</main>
<script>{JS}</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(output_path) // 1024
    print(f"  💾 HTML saved: {output_path}  ({size_kb} KB)")
    return output_path
