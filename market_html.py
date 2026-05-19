"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  HTML REPORT GENERATOR  v1.0  —  market_html.py                           ║
║  Generates a single self-contained mobile-first HTML report from all       ║
║  DataFrames produced by market_engine.py.                                  ║
║                                                                            ║
║  Features:                                                                 ║
║   • Mobile-first responsive design (works on phone, tablet, desktop)       ║
║   • Tab navigation — all 10 sections in one file                           ║
║   • Live search/filter on every table                                      ║
║   • Sortable columns (tap header to sort)                                  ║
║   • Color-coded cells matching Excel output                                 ║
║   • Action_Tier badges with color hierarchy                                ║
║   • TradingView symbol copy buttons                                        ║
║   • GitHub Pages compatible — pure HTML/CSS/JS, zero dependencies          ║
║   • Dark-mode aware via prefers-color-scheme                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
import json
import os
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
#  COLOR HELPERS  (match market_excel.py palette)
# ─────────────────────────────────────────────────────────────────────────────

def _cell_class(col: str, val) -> str:
    """Return CSS class name for a cell based on column + value."""
    col = str(col).lower().strip()

    if col == "action_tier":
        v = str(val)
        return {
            "PRIME BUY":     "tier-prime",
            "CONFIRMED BUY": "tier-confirmed",
            "RS BUY":        "tier-rsbuy",
            "WATCH":         "tier-watch",
            "AVOID":         "tier-avoid",
            "NEUTRAL":       "tier-neutral",
        }.get(v, "")

    if col in ("signal", "enhanced", "sec_signal"):
        v = str(val)
        return {
            "Strong Buy": "sig-strongbuy",
            "Buy":        "sig-buy",
            "Sell":       "sig-sell",
            "Neutral":    "sig-neutral",
        }.get(v, "")

    if col == "action":
        return {"BUY": "sig-buy", "SELL": "sig-sell", "WAIT": "sig-neutral"}.get(str(val), "")

    if col in ("mst_signal", "lst_signal", "rs30_signal"):
        return {"Buy": "sig-buy", "Watch": "sig-neutral", "Neutral": ""}.get(str(val), "")

    if col == "supertrend":
        return {"Buy": "sig-buy", "Sell": "sig-sell"}.get(str(val), "")

    if col == "trend":
        v = str(val)
        if "Bullish" in v or "BULLISH" in v: return "pos-strong"
        if "Bearish" in v or "BEARISH" in v: return "neg-strong"
        return ""

    if col == "sec_gated":
        return "pos-strong" if str(val) == "✓" else "dim"

    if col == "sl_grade":
        return {"A": "pos-strong", "B": "pos", "C": "pos-dim", "D": "neg-dim", "F": "neg"}.get(str(val), "")

    if col in ("direction",):
        return {"BULLISH": "pos-strong", "BEARISH": "neg-strong"}.get(str(val), "")

    # Percentage columns — positive green, negative red
    pct_cols = {
        "chg_1d%", "chg_5d%", "rs_22d%", "rs_55d%", "rs_120d%", "rs_252d%",
        "rs_22d_idx%", "rs_55d_idx%", "rs_120d_idx%", "rs_252d_idx%",
        "rs_22d_sec%", "rs_55d_sec%", "1m%", "3m%", "6m%", "12m%", "ytd%",
        "rs_1m%", "rs_3m%", "rs_6m%", "avg_chg_1d%", "avg_chg_5d%",
        "sales_yoy%", "pat_yoy%", "sales_qoq%", "pat_qoq%",
        "rs22%", "rs55%", "w_rs21%", "w_rs30%", "m_rs12%",
        "sec_rs22d%", "sec_rs55d%",
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
    """Format a value for HTML display."""
    if val is None: return ""
    if isinstance(val, float):
        if np.isnan(val): return ""
        if val == int(val) and abs(val) < 1e9: return str(int(val))
        return f"{val:.2f}"
    s = str(val)
    if s in ("nan", "None", ""): return ""
    return s


# ─────────────────────────────────────────────────────────────────────────────
#  TABLE BUILDER
# ─────────────────────────────────────────────────────────────────────────────

# Columns to skip in HTML (internal / redundant)
_SKIP_COLS = {"tv_symbol", "_o", "primary_rs_period"}

# Columns that should be left-aligned
_LEFT_COLS = {"symbol", "company", "name", "sector", "industry", "country",
              "region", "commodity", "group", "chart_pattern", "setup_desc",
              "strategy", "notes", "signal_type", "trend", "etf"}


def _build_table(df: pd.DataFrame, table_id: str,
                 searchable: bool = True, max_rows: int = 2000) -> str:
    if df is None or df.empty:
        return '<p class="empty">No data available.</p>'

    df = df.head(max_rows).copy()

    # Filter out internal columns
    cols = [c for c in df.columns if c.lower().strip() not in _SKIP_COLS]

    # Build header
    ths = ""
    for c in cols:
        align = "left" if c.lower() in _LEFT_COLS else "center"
        ths += f'<th style="text-align:{align}" onclick="sortTable(this)">{c}</th>'

    # Build rows
    rows_html = ""
    for _, row in df.iterrows():
        tds = ""
        for c in cols:
            val = row[c]
            display = _fmt(val)
            cls = _cell_class(c, val)
            align = "left" if c.lower() in _LEFT_COLS else "center"
            cls_attr = f' class="{cls}"' if cls else ""
            tds += f'<td{cls_attr} style="text-align:{align}">{display}</td>'
        rows_html += f"<tr>{tds}</tr>"

    search_bar = ""
    if searchable:
        search_bar = f'''
        <div class="tbl-search">
          <input type="text" placeholder="🔍 Search / filter…"
                 oninput="filterTable(this, '{table_id}')">
        </div>'''

    return f"""
    {search_bar}
    <div class="tbl-wrap">
      <table id="{table_id}" class="data-tbl">
        <thead><tr>{ths}</tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    <p class="row-count" id="{table_id}-count">{len(df)} rows</p>
    """


# ─────────────────────────────────────────────────────────────────────────────
#  DASHBOARD BUILDER (special two-column layout)
# ─────────────────────────────────────────────────────────────────────────────

def _build_dashboard(df: pd.DataFrame) -> str:
    if df is None or df.empty: return ""
    html = ""
    for _, row in df.iterrows():
        k = _fmt(row.get("Key", ""))
        v = _fmt(row.get("Value", ""))
        if not k and not v:
            html += '<div class="dash-spacer"></div>'
            continue
        if k.startswith("══") or k.startswith("──"):
            html += f'<div class="dash-section">{k}</div>'
            continue
        # Color value cells for action tier counts
        vcls = ""
        if any(t in k for t in ["PRIME BUY", "CONFIRMED BUY", "RS BUY"]):
            vcls = " tier-prime" if "PRIME" in k else (" tier-confirmed" if "CONFIRMED" in k else " tier-rsbuy")
        elif "AVOID" in k:    vcls = " tier-avoid"
        elif "WATCH" in k:    vcls = " tier-watch"
        elif "NEUTRAL" in k:  vcls = " tier-neutral"

        # TV watchlist rows — make copyable
        is_tv = any(x in k for x in ["PRIME BUY", "CONFIRMED", "RS BUY", "WATCH", "LST", "RS30"])
        if is_tv and v and len(v) > 10:
            v_html = f'<span class="tv-list">{v}</span><button class="copy-btn" onclick="copyText(this, \'{v.replace(chr(39), "")}\')">Copy</button>'
        else:
            v_html = v

        html += f'<div class="dash-row"><div class="dash-key">{k}</div><div class="dash-val{vcls}">{v_html}</div></div>'
    return html


# ─────────────────────────────────────────────────────────────────────────────
#  MARKET SUMMARY CARDS (from snapshot)
# ─────────────────────────────────────────────────────────────────────────────

def _build_summary_cards(snapshot_df: pd.DataFrame) -> str:
    if snapshot_df is None or snapshot_df.empty: return ""
    cards = ""
    for _, row in snapshot_df.iterrows():
        name  = _fmt(row.get("Name", ""))
        price = _fmt(row.get("Price", ""))
        chg1  = row.get("Chg_1D%", "")
        trend = _fmt(row.get("Trend", ""))
        if not name or "──" in name: continue
        try:
            chg_f = float(chg1)
            chg_cls = "pos" if chg_f > 0 else ("neg" if chg_f < 0 else "")
            chg_str = f"{chg_f:+.2f}%"
        except:
            chg_cls = ""; chg_str = _fmt(chg1)
        trend_cls = "pos-strong" if "Bullish" in trend else ("neg-strong" if "Bearish" in trend else "dim")
        cards += f"""<div class="snap-card">
          <div class="snap-name">{name}</div>
          <div class="snap-price">{price}</div>
          <div class="snap-chg {chg_cls}">{chg_str}</div>
          <div class="snap-trend {trend_cls}">{trend}</div>
        </div>"""
    return f'<div class="snap-grid">{cards}</div>'


# ─────────────────────────────────────────────────────────────────────────────
#  SECTOR BARS (visual RS bar chart)
# ─────────────────────────────────────────────────────────────────────────────

def _build_sector_bars(sector_df: pd.DataFrame) -> str:
    if sector_df is None or sector_df.empty: return ""
    html = '<div class="sector-bars">'
    for _, row in sector_df.iterrows():
        sec = _fmt(row.get("Sector", ""))
        sig = _fmt(row.get("Signal", ""))
        rs22 = row.get("RS_22d%", 0)
        rs55 = row.get("RS_55d%", 0)
        rank = _fmt(row.get("Rank", ""))
        try:
            rs22f = float(rs22); rs55f = float(rs55)
        except:
            rs22f = 0; rs55f = 0
        bar_w = min(abs(rs22f) * 3, 100)
        bar_cls = "bar-pos" if rs22f >= 0 else "bar-neg"
        sig_cls = {"Buy": "sig-buy", "Sell": "sig-sell"}.get(sig, "sig-neutral")
        html += f"""<div class="sec-row">
          <div class="sec-rank">#{rank}</div>
          <div class="sec-name">{sec}</div>
          <div class="sec-bar-wrap"><div class="sec-bar {bar_cls}" style="width:{bar_w:.0f}%"></div></div>
          <div class="sec-rs22 {'' if rs22f >= 0 else 'neg'}">{rs22f:+.1f}%</div>
          <div class="sec-rs55 {'' if rs55f >= 0 else 'neg'}">{rs55f:+.1f}%</div>
          <div class="{sig_cls} sec-sig">{sig}</div>
        </div>"""
    html += "</div>"
    return html


# ─────────────────────────────────────────────────────────────────────────────
#  TOP PICKS CARD VIEW (mobile-friendly cards for top buy stocks)
# ─────────────────────────────────────────────────────────────────────────────

def _build_top_picks_cards(df: pd.DataFrame) -> str:
    if df is None or df.empty: return ""
    # Check if it's a message-only df
    if "Message" in df.columns:
        return f'<p class="empty">{df["Message"].iloc[0]}</p>'

    KEY_COLS = ["Symbol", "Company", "Sector", "Price", "Action_Tier",
                "RS_22d_Idx%", "RSI_14", "SL_Buy%", "SL_Grade",
                "Total_Score", "Sales_YoY%", "PAT_YoY%"]
    available = [c for c in KEY_COLS if c in df.columns]

    prev_sec = None
    html = ""
    for _, row in df.iterrows():
        sec = _fmt(row.get("Sector", ""))
        sym = _fmt(row.get("Symbol", ""))
        if not sym: continue  # skip divider rows

        # Sector header
        if sec != prev_sec:
            sec_sig  = _fmt(row.get("Sec_Signal", ""))
            sec_rs   = row.get("Sec_RS22d%", row.get("Sec_RS55d%", ""))
            try: sec_rs_str = f"{float(sec_rs):+.1f}%"
            except: sec_rs_str = _fmt(sec_rs)
            sig_cls = {"Buy": "sig-buy", "Sell": "sig-sell"}.get(sec_sig, "sig-neutral")
            html += f'<div class="picks-sec-hdr"><span>{sec}</span><span class="{sig_cls}">{sec_sig} {sec_rs_str}</span></div>'
            prev_sec = sec

        # Stock card
        tier    = _fmt(row.get("Action_Tier", ""))
        company = _fmt(row.get("Company", ""))
        price   = _fmt(row.get("Price", ""))
        rs22    = row.get("RS_22d_Idx%", "")
        rsi     = _fmt(row.get("RSI_14", ""))
        sl_pct  = _fmt(row.get("SL_Buy%", ""))
        sl_gr   = _fmt(row.get("SL_Grade", ""))
        score   = _fmt(row.get("Total_Score", ""))
        sal_yoy = _fmt(row.get("Sales_YoY%", ""))
        pat_yoy = _fmt(row.get("PAT_YoY%", ""))
        fin_sc  = _fmt(row.get("Fin_Score", ""))
        chart_p = _fmt(row.get("Chart_Pattern", ""))

        try: rs22_str = f"{float(rs22):+.1f}%"
        except: rs22_str = _fmt(rs22)
        rs_cls = "pos-strong" if rs22_str.startswith("+") else "neg-strong"

        tier_cls = {
            "PRIME BUY": "tier-prime", "CONFIRMED BUY": "tier-confirmed",
            "RS BUY": "tier-rsbuy", "WATCH": "tier-watch",
            "AVOID": "tier-avoid", "NEUTRAL": "tier-neutral",
        }.get(tier, "")

        sl_gr_cls = {"A":"pos-strong","B":"pos","C":"pos-dim","D":"neg-dim","F":"neg"}.get(sl_gr,"")

        tv_sym = f"{sym}"
        html += f"""<div class="stock-card">
          <div class="sc-head">
            <div class="sc-sym">{sym}</div>
            <span class="sc-tier badge {tier_cls}">{tier}</span>
          </div>
          <div class="sc-company">{company}</div>
          <div class="sc-metrics">
            <div class="sc-m"><span class="sc-ml">Price</span><span class="sc-mv">₹{price}</span></div>
            <div class="sc-m"><span class="sc-ml">RS 22d</span><span class="sc-mv {rs_cls}">{rs22_str}</span></div>
            <div class="sc-m"><span class="sc-ml">RSI</span><span class="sc-mv">{rsi}</span></div>
            <div class="sc-m"><span class="sc-ml">SL%</span><span class="sc-mv">{sl_pct}% <span class="{sl_gr_cls}">({sl_gr})</span></span></div>
            <div class="sc-m"><span class="sc-ml">Score</span><span class="sc-mv">{score}</span></div>
            <div class="sc-m"><span class="sc-ml">Sales YoY</span><span class="sc-mv {'pos' if sal_yoy and sal_yoy not in ('','nan') else ''}">{sal_yoy}%</span></div>
            <div class="sc-m"><span class="sc-ml">PAT YoY</span><span class="sc-mv {'pos' if pat_yoy and pat_yoy not in ('','nan') else ''}">{pat_yoy}%</span></div>
            <div class="sc-m"><span class="sc-ml">Fin Score</span><span class="sc-mv">{fin_sc}</span></div>
          </div>
          {f'<div class="sc-pattern">{chart_p}</div>' if chart_p else ''}
          <button class="copy-btn sm" onclick="copyText(this,'{tv_sym},')">📋 Copy TV</button>
        </div>"""
    return f'<div class="stock-cards">{html}</div>'


# ─────────────────────────────────────────────────────────────────────────────
#  TRADE SETUPS — compact card view filtered to BUY only
# ─────────────────────────────────────────────────────────────────────────────

def _build_trade_cards(df: pd.DataFrame) -> str:
    if df is None or df.empty: return ""
    buy_df = df[df.get("Action", df.get("action", pd.Series())) == "BUY"] if "Action" in df.columns else df
    if buy_df.empty:
        buy_df = df[df["Action_Tier"].isin(["PRIME BUY","CONFIRMED BUY","RS BUY"])] if "Action_Tier" in df.columns else df

    html = ""
    for _, row in buy_df.head(50).iterrows():
        sym     = _fmt(row.get("Symbol",""))
        company = _fmt(row.get("Company",""))
        tier    = _fmt(row.get("Action_Tier",""))
        sig_t   = _fmt(row.get("Signal_Type",""))
        price   = _fmt(row.get("Price",""))
        sl_pct  = _fmt(row.get("SL%",""))
        sl_pr   = _fmt(row.get("SL_Price",""))
        sl_gr   = _fmt(row.get("SL_Grade",""))
        tp1     = _fmt(row.get("TP1%",""))
        tp2     = _fmt(row.get("TP2%",""))
        rr      = _fmt(row.get("RR_T1",""))
        notes   = _fmt(row.get("Notes",""))
        desc    = _fmt(row.get("Setup_Desc",""))
        mst     = _fmt(row.get("MST_Signal",""))
        lst     = _fmt(row.get("LST_Signal",""))
        rs30    = _fmt(row.get("RS30_Signal",""))

        tier_cls = {
            "PRIME BUY":"tier-prime","CONFIRMED BUY":"tier-confirmed",
            "RS BUY":"tier-rsbuy","WATCH":"tier-watch",
        }.get(tier,"")
        sl_gr_cls = {"A":"pos-strong","B":"pos","C":"pos-dim","D":"neg-dim","F":"neg"}.get(sl_gr,"")

        sigs_html = ""
        for label, val, cls in [("MST",mst,"sig-buy" if mst=="Buy" else ""),
                                  ("LST",lst,"sig-buy" if lst=="Buy" else ""),
                                  ("RS30",rs30,"sig-buy" if rs30=="Buy" else "")]:
            if val and val not in ("","Neutral","nan"):
                sigs_html += f'<span class="mini-badge {cls}">{label}:{val}</span>'

        html += f"""<div class="trade-card">
          <div class="tc-head">
            <div class="tc-sym">{sym} <span class="tc-co">{company}</span></div>
            <span class="badge {tier_cls}">{tier}</span>
          </div>
          <div class="tc-desc">{desc}</div>
          <div class="tc-metrics">
            <div class="tc-m"><span class="tc-l">Price</span><span>{price}</span></div>
            <div class="tc-m"><span class="tc-l">SL</span><span class="{sl_gr_cls}">{sl_pct}% @ {sl_pr} <b>[{sl_gr}]</b></span></div>
            <div class="tc-m"><span class="tc-l">TP1/TP2</span><span class="pos">{tp1}% / {tp2}%</span></div>
            <div class="tc-m"><span class="tc-l">R:R</span><span class="{'pos-strong' if rr and float(rr or 0)>=2 else ''}">{rr}×</span></div>
          </div>
          <div class="tc-sigs">{sigs_html}</div>
          {f'<div class="tc-notes">{notes}</div>' if notes else ''}
        </div>"""
    return f'<div class="trade-cards">{html}</div>'


# ─────────────────────────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
:root {
  --bg:       #0f1117;
  --bg2:      #1a1d27;
  --bg3:      #22263a;
  --border:   #2e3250;
  --text:     #e8eaf0;
  --text2:    #9ba3c0;
  --text3:    #5f6680;
  --accent:   #4f8ef7;
  --green:    #2ecc71;
  --green2:   #1a7a44;
  --green3:   #c8e6c9;
  --red:      #e74c3c;
  --red2:     #7f1c1c;
  --red3:     #ffcdd2;
  --amber:    #f39c12;
  --amber2:   #7a4f0a;
  --prime:    #1a6b2e;
  --confirmed:#2e7d32;
  --rsbuy:    #558b2f;
  --shadow:   0 2px 12px rgba(0,0,0,0.4);
  --radius:   10px;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #f4f6fb; --bg2: #ffffff; --bg3: #eef1f8;
    --border: #d0d6e8; --text: #1a1d2e; --text2: #4a5070;
    --text3: #8890a8; --shadow: 0 2px 12px rgba(0,0,0,0.08);
  }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--text);
  font-size: 14px; line-height: 1.5;
}

/* ── HEADER ──────────────────────────────────────────────────────────────── */
.app-header {
  background: var(--bg2); border-bottom: 1px solid var(--border);
  padding: 12px 16px; position: sticky; top: 0; z-index: 100;
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px;
}
.app-title { font-size: 16px; font-weight: 600; color: var(--accent); }
.app-meta  { font-size: 11px; color: var(--text3); }
.regime-badge {
  padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600;
}
.regime-BULL    { background:#1a6b2e; color:#fff; }
.regime-CAUTION { background:#7a4f0a; color:#fff; }
.regime-BEAR    { background:#7f1c1c; color:#fff; }

/* ── TABS ────────────────────────────────────────────────────────────────── */
.tab-bar {
  display: flex; overflow-x: auto; background: var(--bg2);
  border-bottom: 1px solid var(--border);
  scrollbar-width: none; position: sticky; top: 57px; z-index: 99;
}
.tab-bar::-webkit-scrollbar { display: none; }
.tab-btn {
  padding: 10px 14px; font-size: 13px; white-space: nowrap;
  border: none; background: none; color: var(--text2); cursor: pointer;
  border-bottom: 2px solid transparent; transition: all .15s;
  flex-shrink: 0;
}
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
.tab-btn:hover  { color: var(--text); }

/* ── CONTENT ─────────────────────────────────────────────────────────────── */
.tab-content { display: none; padding: 14px 12px; max-width: 1400px; margin: 0 auto; }
.tab-content.active { display: block; }
.section-title {
  font-size: 15px; font-weight: 600; color: var(--text);
  margin: 16px 0 8px; display: flex; align-items: center; gap: 6px;
}
.section-title:first-child { margin-top: 0; }

/* ── SNAPSHOT CARDS ──────────────────────────────────────────────────────── */
.snap-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 8px; margin-bottom: 16px;
}
.snap-card {
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 10px 12px;
}
.snap-name  { font-size: 11px; color: var(--text3); margin-bottom: 3px; }
.snap-price { font-size: 16px; font-weight: 600; }
.snap-chg   { font-size: 13px; font-weight: 500; margin-top: 2px; }
.snap-trend { font-size: 11px; margin-top: 3px; }

/* ── SECTOR BARS ─────────────────────────────────────────────────────────── */
.sector-bars { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
.sec-row {
  display: grid;
  grid-template-columns: 22px 120px 1fr 52px 52px 60px;
  align-items: center; gap: 6px;
  background: var(--bg2); border-radius: 6px; padding: 6px 10px;
  border: 1px solid var(--border);
}
.sec-rank  { color: var(--text3); font-size: 12px; }
.sec-name  { font-size: 13px; font-weight: 500; }
.sec-bar-wrap { height: 6px; background: var(--bg3); border-radius: 3px; overflow: hidden; }
.sec-bar   { height: 100%; border-radius: 3px; min-width: 2px; }
.bar-pos   { background: var(--green); }
.bar-neg   { background: var(--red); }
.sec-rs22, .sec-rs55 { font-size: 12px; text-align: right; }
.sec-sig   { font-size: 12px; text-align: center; padding: 2px 6px; border-radius: 4px; }

/* ── STOCK CARDS ─────────────────────────────────────────────────────────── */
.stock-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 10px; margin-bottom: 16px;
}
.stock-card, .trade-card {
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 12px 14px;
}
.sc-head, .tc-head {
  display: flex; justify-content: space-between;
  align-items: center; margin-bottom: 4px;
}
.sc-sym  { font-size: 18px; font-weight: 700; }
.sc-company, .tc-co { font-size: 12px; color: var(--text3); margin-bottom: 8px; }
.tc-sym  { font-size: 16px; font-weight: 700; }
.sc-tier { font-size: 11px; }
.sc-metrics, .tc-metrics {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 4px 8px; margin-bottom: 8px;
}
.sc-m, .tc-m {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 12px; padding: 3px 0;
  border-bottom: 1px solid var(--border);
}
.sc-ml, .tc-l { color: var(--text3); }
.sc-mv  { font-weight: 500; }
.sc-pattern { font-size: 12px; color: var(--accent); margin-bottom: 6px; }
.tc-desc { font-size: 11px; color: var(--text2); margin-bottom: 8px; line-height: 1.4; }
.tc-sigs { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 6px; }
.tc-notes { font-size: 11px; color: var(--text3); font-style: italic; }
.mini-badge {
  padding: 2px 6px; border-radius: 10px; font-size: 11px;
  background: var(--bg3); color: var(--text2);
}
.picks-sec-hdr {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 13px; font-weight: 600; padding: 8px 4px;
  color: var(--text2); border-bottom: 1px solid var(--border);
  margin-bottom: 8px; grid-column: 1 / -1;
}

/* ── TABLES ──────────────────────────────────────────────────────────────── */
.tbl-search { margin-bottom: 8px; }
.tbl-search input {
  width: 100%; padding: 8px 12px; border-radius: 8px;
  border: 1px solid var(--border); background: var(--bg2);
  color: var(--text); font-size: 14px; outline: none;
}
.tbl-search input:focus { border-color: var(--accent); }
.tbl-wrap {
  overflow-x: auto; border-radius: var(--radius);
  border: 1px solid var(--border); margin-bottom: 6px;
}
table.data-tbl {
  border-collapse: collapse; width: 100%;
  font-size: 12px; min-width: 400px;
}
.data-tbl thead th {
  background: #0d1730; color: #90caf9;
  padding: 8px 10px; font-weight: 600; font-size: 11px;
  white-space: nowrap; cursor: pointer; user-select: none;
  border-bottom: 1px solid var(--border); position: sticky; top: 0;
}
.data-tbl thead th:hover { background: #1a2a4a; }
.data-tbl thead th::after { content: " ↕"; opacity: 0.4; }
.data-tbl thead th.asc::after  { content: " ↑"; opacity: 1; }
.data-tbl thead th.desc::after { content: " ↓"; opacity: 1; }
.data-tbl tbody tr:nth-child(even) { background: var(--bg3); }
.data-tbl tbody tr:hover { background: rgba(79,142,247,0.08); }
.data-tbl td {
  padding: 6px 10px; border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.row-count { font-size: 11px; color: var(--text3); margin-bottom: 12px; }

/* ── DASHBOARD ───────────────────────────────────────────────────────────── */
.dash-section {
  background: #0d47a1; color: #90caf9;
  padding: 8px 12px; border-radius: 6px;
  font-weight: 600; font-size: 13px; margin: 10px 0 4px;
}
.dash-row {
  display: grid; grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid var(--border); padding: 6px 4px;
  gap: 8px; align-items: start;
}
@media (max-width: 500px) {
  .dash-row { grid-template-columns: 1fr; }
}
.dash-key { font-size: 12px; font-weight: 500; color: var(--text2); }
.dash-val { font-size: 12px; color: var(--text); word-break: break-all; }
.dash-spacer { height: 8px; }
.tv-list { font-size: 11px; color: var(--text3); word-break: break-all; }

/* ── BADGES & SIGNALS ────────────────────────────────────────────────────── */
.badge {
  display: inline-block; padding: 3px 9px; border-radius: 12px;
  font-size: 11px; font-weight: 600; white-space: nowrap;
}
.tier-prime     { background:#1a6b2e; color:#fff; }
.tier-confirmed { background:#c8e6c9; color:#1b5e20; }
.tier-rsbuy     { background:#dcedc8; color:#33691e; }
.tier-watch     { background:#fff9c4; color:#5d4037; }
.tier-avoid     { background:#b71c1c; color:#fff; }
.tier-neutral   { background:#424242; color:#ccc; }
.sig-strongbuy  { background:#006b3c; color:#fff; }
.sig-buy        { background:#c8e6c9; color:#1b5e20; }
.sig-sell       { background:#b71c1c; color:#fff; }
.sig-neutral    { background:#fff9c4; color:#5d4037; }
.pos-strong { color: var(--green); font-weight: 600; }
.pos        { color: #81c784; }
.pos-dim    { color: #a5d6a7; }
.neg-strong { color: var(--red); font-weight: 600; }
.neg        { color: #e57373; }
.neg-dim    { color: #ef9a9a; }
.dim        { color: var(--text3); }

/* ── BUTTONS ─────────────────────────────────────────────────────────────── */
.copy-btn {
  margin-top: 8px; padding: 5px 12px; border-radius: 6px;
  border: 1px solid var(--accent); background: transparent;
  color: var(--accent); font-size: 12px; cursor: pointer;
  transition: all .15s;
}
.copy-btn:hover { background: var(--accent); color: #fff; }
.copy-btn.sm { padding: 3px 8px; font-size: 11px; margin-top: 6px; }
.copy-btn.copied { background: var(--green2); border-color: var(--green); color: #fff; }

/* ── TOGGLE TABS (Cards / Table) ─────────────────────────────────────────── */
.view-toggle {
  display: flex; gap: 6px; margin-bottom: 10px;
}
.vt-btn {
  padding: 5px 14px; border-radius: 6px; font-size: 12px;
  border: 1px solid var(--border); background: transparent;
  color: var(--text2); cursor: pointer;
}
.vt-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }

/* ── EMPTY ───────────────────────────────────────────────────────────────── */
.empty { color: var(--text3); font-size: 13px; padding: 20px 0; text-align: center; }

/* ── RESPONSIVE ──────────────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .sec-row { grid-template-columns: 22px 1fr 60px 44px; }
  .sec-bar-wrap, .sec-rs55 { display: none; }
  .stock-cards { grid-template-columns: 1fr; }
  .snap-grid   { grid-template-columns: repeat(2, 1fr); }
  .sc-metrics  { grid-template-columns: 1fr; }
}
"""

# ─────────────────────────────────────────────────────────────────────────────
#  JAVASCRIPT
# ─────────────────────────────────────────────────────────────────────────────

JS = """
// ── TAB SWITCHING ──────────────────────────────────────────────────────────
function showTab(id) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  document.querySelector(`[data-tab="${id}"]`).classList.add('active');
  localStorage.setItem('activeTab', id);
}
document.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem('activeTab') || 'snapshot';
  showTab(saved);
});

// ── TABLE FILTER ───────────────────────────────────────────────────────────
function filterTable(input, tableId) {
  const q = input.value.toLowerCase();
  const tbody = document.getElementById(tableId).tBodies[0];
  let vis = 0;
  for (const row of tbody.rows) {
    const match = row.textContent.toLowerCase().includes(q);
    row.style.display = match ? '' : 'none';
    if (match) vis++;
  }
  const cnt = document.getElementById(tableId + '-count');
  if (cnt) cnt.textContent = vis + ' rows';
}

// ── TABLE SORT ─────────────────────────────────────────────────────────────
function sortTable(th) {
  const table = th.closest('table');
  const tbody = table.tBodies[0];
  const col   = th.cellIndex;
  const asc   = !th.classList.contains('asc');
  table.querySelectorAll('th').forEach(h => h.classList.remove('asc','desc'));
  th.classList.add(asc ? 'asc' : 'desc');
  const rows = Array.from(tbody.rows);
  rows.sort((a, b) => {
    let av = a.cells[col]?.textContent.trim() || '';
    let bv = b.cells[col]?.textContent.trim() || '';
    const af = parseFloat(av.replace(/[+%,]/g,''));
    const bf = parseFloat(bv.replace(/[+%,]/g,''));
    if (!isNaN(af) && !isNaN(bf)) return asc ? af - bf : bf - af;
    return asc ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  rows.forEach(r => tbody.appendChild(r));
}

// ── COPY TO CLIPBOARD ──────────────────────────────────────────────────────
function copyText(btn, text) {
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = '✅ Copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = btn.dataset.orig || '📋 Copy TV'; btn.classList.remove('copied'); }, 2000);
  }).catch(() => {
    // Fallback
    const el = document.createElement('textarea');
    el.value = text; document.body.appendChild(el);
    el.select(); document.execCommand('copy'); document.body.removeChild(el);
    btn.textContent = '✅ Copied!';
    setTimeout(() => { btn.textContent = '📋 Copy TV'; }, 2000);
  });
}

// ── VIEW TOGGLE (Cards / Table) ────────────────────────────────────────────
function toggleView(sectionId, mode) {
  document.querySelectorAll(`#${sectionId} .vt-btn`).forEach(b => b.classList.remove('active'));
  document.querySelector(`#${sectionId} [data-mode="${mode}"]`).classList.add('active');
  const cardView  = document.getElementById(sectionId + '-cards');
  const tableView = document.getElementById(sectionId + '-table');
  if (cardView)  cardView.style.display  = mode === 'cards' ? '' : 'none';
  if (tableView) tableView.style.display = mode === 'table' ? '' : 'none';
}
"""


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN BUILD FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def build_html_report(
    market: str,
    snapshot_df: pd.DataFrame,
    sector_str_df: pd.DataFrame,
    sector_rot_df: pd.DataFrame,
    industry_rot_df: pd.DataFrame,
    breadth_df: pd.DataFrame,
    sector_perf_df: pd.DataFrame,
    stock_str_df: pd.DataFrame,
    top_buy_df: pd.DataFrame,
    top_sell_df: pd.DataFrame,
    chart_pat_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    dashboard_df: pd.DataFrame,
    sleeve_df: pd.DataFrame,
    country_etf_df: pd.DataFrame,
    commodity_df: pd.DataFrame,
    output_path: str,
    run_time: str = "",
    primary_rs: int = 55,
) -> str:
    """
    Build and write the complete self-contained HTML report.
    Returns the output_path.
    """

    run_time = run_time or datetime.now().strftime("%d %b %Y  %H:%M")

    # ── Detect regime from dashboard ─────────────────────────────────────────
    regime = "BULL"
    if dashboard_df is not None and not dashboard_df.empty:
        for _, r in dashboard_df.iterrows():
            k = str(r.get("Key", ""))
            if "MARKET REGIME" in k.upper():
                if "BEAR" in k.upper():   regime = "BEAR"
                elif "CAUTION" in k.upper(): regime = "CAUTION"
                else:                       regime = "BULL"
                break
            v = str(r.get("Value", ""))
            if "BULL" in v and "REGIME" in k.upper(): regime = "BULL"

    # ── Signal counts for header ──────────────────────────────────────────────
    prime_n = conf_n = rsbuy_n = avoid_n = 0
    if stock_str_df is not None and not stock_str_df.empty and "Action_Tier" in stock_str_df.columns:
        prime_n = int((stock_str_df["Action_Tier"] == "PRIME BUY").sum())
        conf_n  = int((stock_str_df["Action_Tier"] == "CONFIRMED BUY").sum())
        rsbuy_n = int((stock_str_df["Action_Tier"] == "RS BUY").sum())
        avoid_n = int((stock_str_df["Action_Tier"] == "AVOID").sum())

    # ── Build individual sections ─────────────────────────────────────────────

    # Top Picks — cards default on mobile, table toggle available
    buy_cards  = _build_top_picks_cards(top_buy_df)
    buy_table  = _build_table(top_buy_df,  "tbl-top-buy",  searchable=True)
    sell_table = _build_table(top_sell_df, "tbl-top-sell", searchable=True)

    # Stock Strength — trim to main cols for HTML
    MAIN_COLS = [
        "Symbol","Company","Sector","Price","Chg_1D%",
        "Action_Tier","Sec_Gated",
        "RS_22d_Idx%","RS_55d_Idx%","RSI_14","Trend","SMA_Score",
        "Total_Score","Fin_Score","SL_Buy%","SL_Grade","SL_Buy_Price",
        "Sales_YoY%","PAT_YoY%","ROE%","D/E","Mkt_Cap_B","Chart_Pattern",
    ]
    if stock_str_df is not None and not stock_str_df.empty:
        stock_main = stock_str_df[[c for c in MAIN_COLS if c in stock_str_df.columns]]
    else:
        stock_main = stock_str_df

    # Sleeve — only data rows (skip divider rows)
    sleeve_clean = None
    if sleeve_df is not None and not sleeve_df.empty:
        SLEEVE_COLS = ["Rank","Symbol","Company","Sector","Price","Sleeve_RS",
                       "RS_22d_Idx%","RS_55d_Idx%","Signal","SL_Buy%","SL_Grade",
                       "Equal_Wt%","ATR_Wt%","Sales_YoY%","PAT_YoY%"]
        try:
            clean = sleeve_df[sleeve_df["Rank"].apply(
                lambda x: str(x).strip() not in ("","━━━") and not str(x).startswith("━")
            )].copy()
            sleeve_clean = clean[[c for c in SLEEVE_COLS if c in clean.columns]]
        except: sleeve_clean = None

    # ── Tab definitions ───────────────────────────────────────────────────────
    tabs = [
        ("snapshot",   "📸 Market"),
        ("sectors",    "🏭 Sectors"),
        ("top-buy",    "🏆 Buy Picks"),
        ("top-sell",   "🔴 Sell Picks"),
        ("stocks",     "📊 Stocks"),
        ("trade",      "🎯 Trades"),
        ("breadth",    "📊 Breadth"),
        ("global",     "🌍 Global"),
        ("sleeves",    "📋 Sleeves"),
        ("dashboard",  "📋 Guide"),
    ]

    tab_btns = "".join(
        f'<button class="tab-btn" data-tab="{tid}" onclick="showTab(\'{tid}\')">{label}</button>'
        for tid, label in tabs
    )

    def _section(tid, title, content):
        return f'<div class="tab-content" id="tab-{tid}"><h2 class="section-title">{title}</h2>{content}</div>'

    def _view_toggle(sid, default="cards"):
        other = "table" if default == "cards" else "cards"
        return f"""<div class="view-toggle" id="{sid}">
          <button class="vt-btn {'active' if default=='cards' else ''}" data-mode="cards" onclick="toggleView('{sid}','cards')">Cards</button>
          <button class="vt-btn {'active' if default=='table' else ''}" data-mode="table" onclick="toggleView('{sid}','table')">Table</button>
        </div>"""

    # Build each tab content
    snap_content = _build_summary_cards(snapshot_df) + _build_table(snapshot_df, "tbl-snap", searchable=False)

    sec_content = (
        _build_sector_bars(sector_str_df) +
        '<h2 class="section-title">Sector Performance</h2>' +
        _build_table(sector_perf_df, "tbl-secperf", searchable=False) +
        '<h2 class="section-title">Sector Rotation</h2>' +
        _build_table(sector_rot_df, "tbl-secrot", searchable=True) +
        '<h2 class="section-title">Industry Rotation</h2>' +
        _build_table(industry_rot_df, "tbl-indrot", searchable=True)
    )

    buy_content = (
        _view_toggle("vt-buy", "cards") +
        f'<div id="vt-buy-cards">{buy_cards}</div>' +
        f'<div id="vt-buy-table" style="display:none">{buy_table}</div>'
    )

    sell_content = _build_table(top_sell_df, "tbl-top-sell2", searchable=True)

    stock_content = _build_table(stock_main, "tbl-stocks", searchable=True, max_rows=500)

    trade_cards = _build_trade_cards(trade_df)
    trade_tbl   = _build_table(
        trade_df[trade_df["Action"] == "BUY"] if trade_df is not None and "Action" in trade_df.columns else trade_df,
        "tbl-trade", searchable=True, max_rows=100
    )
    trade_content = (
        _view_toggle("vt-trade", "cards") +
        f'<div id="vt-trade-cards">{trade_cards}</div>' +
        f'<div id="vt-trade-table" style="display:none">{trade_tbl}</div>'
    )

    breadth_content = (
        _build_table(breadth_df, "tbl-breadth", searchable=True) +
        '<h2 class="section-title">Chart Patterns</h2>' +
        _build_table(chart_pat_df, "tbl-patterns", searchable=True)
    )

    global_content = (
        '<h2 class="section-title">🌍 Country ETFs (RS vs SPY)</h2>' +
        _build_table(country_etf_df, "tbl-etfs", searchable=True) +
        '<h2 class="section-title">🏅 Commodities (RS vs GLD)</h2>' +
        _build_table(commodity_df, "tbl-commod", searchable=True)
    )

    sleeve_html = _build_table(sleeve_clean, "tbl-sleeves", searchable=True) if sleeve_clean is not None else \
                  '<p class="empty">Sleeve data unavailable</p>'

    dash_content = _build_dashboard(dashboard_df)

    sections_html = (
        _section("snapshot", "📸 Market Snapshot", snap_content) +
        _section("sectors",  "🏭 Sector Strength & Rotation", sec_content) +
        _section("top-buy",  "🏆 Top Buy Picks", buy_content) +
        _section("top-sell", "🔴 Top Sell Picks", sell_content) +
        _section("stocks",   "📊 Stock Strength", stock_content) +
        _section("trade",    "🎯 Trade Setups (BUY only)", trade_content) +
        _section("breadth",  "📊 Market Breadth & Chart Patterns", breadth_content) +
        _section("global",   "🌍 Global — ETFs & Commodities", global_content) +
        _section("sleeves",  "📋 RS Sleeve Lists", sleeve_html) +
        _section("dashboard","📋 Signal Guide & Methodology", dash_content)
    )

    # ── Counts bar ────────────────────────────────────────────────────────────
    counts_bar = f"""<div style="display:flex;gap:8px;padding:8px 12px;background:var(--bg2);
      border-bottom:1px solid var(--border);overflow-x:auto;scrollbar-width:none">
      <span class="badge tier-prime">🌟 PRIME {prime_n}</span>
      <span class="badge tier-confirmed">✅ CONF {conf_n}</span>
      <span class="badge tier-rsbuy">📊 RS {rsbuy_n}</span>
      <span class="badge tier-avoid">🔴 AVOID {avoid_n}</span>
    </div>"""

    # ── Full HTML ─────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="theme-color" content="#0f1117">
  <title>FundaTechno Market Analysis [{market}] — {run_time}</title>
  <style>{CSS}</style>
</head>
<body>

<header class="app-header">
  <div>
    <div class="app-title">FundaTechno [{market}]</div>
    <div class="app-meta">{run_time} · RS{primary_rs}d</div>
  </div>
  <span class="regime-badge regime-{regime}">{regime}</span>
</header>

{counts_bar}

<nav class="tab-bar">{tab_btns}</nav>

<main>
  {sections_html}
</main>

<script>{JS}</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(output_path) // 1024
    print(f"  💾 HTML saved: {output_path}  ({size_kb} KB)")
    return output_path
