"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  market_engine_patch.py  — v6.0 additions                                  ║
║                                                                             ║
║  HOW TO APPLY:                                                              ║
║  1. Add compute_signal_label() immediately after ACTION_TIER_ORDER dict     ║
║     (around line 248 in market_engine.py)                                  ║
║  2. In build_stock_strength(), add  signal_label = ...  after line 1233    ║
║     (after the action_tier = compute_action_tier(...) call)                 ║
║  3. In the row{} dict, add  "Signal_Label": signal_label  after             ║
║     "Action_Tier": action_tier  (around line 1262)                         ║
║  4. After the Action_Tier recompute block (~line 1320-1327), add            ║
║     Signal_Label recompute (shown below)                                    ║
║  5. In build_top_picks_buy/sell rows.append dicts, add                      ║
║     "Signal_Label": r.get("Signal_Label","") after Symbol                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ─────────────────────────────────────────────────────────────────────────────
#  STEP 1 — ADD THIS FUNCTION after ACTION_TIER_ORDER dict (~line 248)
# ─────────────────────────────────────────────────────────────────────────────

def compute_signal_label(action_tier, mst_sig="Neutral", lst_sig="Neutral",
                          rs30_sig="Neutral", sig="Neutral", fin_score=0):
    """
    Single unified human-readable signal label.
    Replaces the 6-column Action_Tier + MST/LST/RS30 confusion with one
    plain-English label that tells a trader exactly what type of setup it is.

    Values (ordered from highest to lowest conviction):
      🌟 Triple Confirmed  — RS30 + LST + MST all firing Buy
      🌟 RS30 + Long       — RS30 Buy + LST Buy
      🌟 RS30 + Swing      — RS30 Buy + MST Buy
      🌟 RS30 Leader       — RS30 Buy alone (weekly momentum + fundamentals)
      🌟 Long Momentum     — LST Buy with strong fundamentals (fin_score ≥ 5)
      ✅ Long Momentum     — LST Buy (strong sector + monthly trend)
      ✅ Strong RS         — Strong Buy peer filter (LST not yet confirmed)
      📈 Swing Entry       — MST Buy (daily entry with weekly pre-conditions)
      📈 RS Leader         — RS Buy (index+sector RS positive, no TF confirmation)
      👁 RS30 Watch        — RS30 pre-conditions met, waiting for breakout
      👁 LST Watch         — LST pre-conditions met, waiting for weekly breakout
      👁 MST Watch         — MST pre-conditions met, waiting for daily breakout
      👁 Setup Building    — Multiple watches, consolidating
      ⬜ Neutral           — No signal
      🔴 RS Breakdown      — RS Sell (all RS values negative)
    """
    at  = str(action_tier  or "NEUTRAL")
    mst = str(mst_sig      or "Neutral")
    lst = str(lst_sig      or "Neutral")
    r30 = str(rs30_sig     or "Neutral")

    if at == "PRIME BUY":
        if r30 == "Buy" and lst == "Buy" and mst == "Buy":
            return "🌟 Triple Confirmed"
        if r30 == "Buy" and lst == "Buy":
            return "🌟 RS30 + Long"
        if r30 == "Buy" and mst == "Buy":
            return "🌟 RS30 + Swing"
        if r30 == "Buy":
            return "🌟 RS30 Leader"
        if lst == "Buy" and fin_score >= 5:
            return "🌟 Long Momentum"
        return "🌟 Prime Setup"

    if at == "CONFIRMED BUY":
        if lst == "Buy":
            return "✅ Long Momentum"
        return "✅ Strong RS"

    if at == "RS BUY":
        if mst == "Buy":
            return "📈 Swing Entry"
        return "📈 RS Leader"

    if at == "WATCH":
        watches = []
        if r30 == "Watch": watches.append("RS30")
        if lst == "Watch": watches.append("LST")
        if mst == "Watch": watches.append("MST")
        if len(watches) > 1:
            return "👁 Setup Building"
        if watches:
            return f"👁 {watches[0]} Watch"
        return "👁 Watch"

    if at == "AVOID":
        return "🔴 RS Breakdown"

    return "⬜ Neutral"


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 2 — In build_stock_strength(), after action_tier = compute_action_tier(...)
#  add this single line:
# ─────────────────────────────────────────────────────────────────────────────
#
#     signal_label = compute_signal_label(
#         action_tier, mst_sig, lst_sig, rs30_sig, sig, _fin_est
#     )
#


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 3 — In the row{} dict, add "Signal_Label" right after "Action_Tier"
#  (approximately line 1262 in the current file):
# ─────────────────────────────────────────────────────────────────────────────
#
#         "Action_Tier":   action_tier,
#         "Signal_Label":  signal_label,     # ← ADD THIS LINE
#         "Sec_Gated":     sec_gated,
#


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 4 — After the Action_Tier recompute block (after line ~1327),
#  add a Signal_Label recompute so it stays consistent with the final Fin_Score:
# ─────────────────────────────────────────────────────────────────────────────
#
#     if "Action_Tier" in df.columns and "Signal_Label" in df.columns:
#         df["Signal_Label"] = df.apply(lambda r: compute_signal_label(
#             r["Action_Tier"],
#             r.get("MST_Signal", "Neutral"),
#             r.get("LST_Signal", "Neutral"),
#             r.get("RS30_Signal", "Neutral"),
#             r.get("Signal", "Neutral"),
#             int(r.get("Fin_Score", 0)),
#         ), axis=1)
#


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 5 — In build_top_picks_buy(), add "Signal_Label" to the rows.append dict
#  (after "Symbol":r.get("Symbol","")  line, around line 1371):
# ─────────────────────────────────────────────────────────────────────────────
#
#             "Signal_Label": r.get("Signal_Label",""),   # ← ADD THIS
#             "Symbol":r.get("Symbol",""),
#
# Repeat the same for build_top_picks_sell().
#


# ─────────────────────────────────────────────────────────────────────────────
#  UPDATED STOCK_MAIN_COLS (replace in market_excel.py build_workbook method)
#  This is the clean, simplified column list for the main Stock Strength sheet.
#  All raw intermediate columns go to "🔬 Signal Detail" sheet.
# ─────────────────────────────────────────────────────────────────────────────

STOCK_MAIN_COLS_V6 = [
    # Identity
    "Symbol", "Company", "Sector", "Industry",
    # Price + momentum
    "Price", "Chg_1D%", "Chg_5D%",
    # PRIMARY DECISION COLUMN (new unified label)
    "Signal_Label",
    # Sector gate quality flag
    "Sec_Gated",
    # Core RS metrics
    "RS_22d_Idx%", "RS_55d_Idx%",
    # Technical health
    "RSI_14", "Trend", "SMA_Score",
    # Risk management
    "SL_Buy%", "SL_Grade", "SL_Buy_Price",
    # Score for ranking
    "Total_Score", "Fin_Score",
    # Fundamentals (key 4 only)
    "Sales_YoY%", "PAT_YoY%", "ROE%", "D/E",
    # Size + pattern
    "Mkt_Cap_B", "Chart_Pattern",
]

# Columns to include in Opportunities / Top Picks sheet (minimal, decision-focused)
OPPORTUNITIES_COLS_V6 = [
    "Rank", "Sec_Rank", "Sector", "Sec_Signal",
    "Signal_Label",
    "Symbol", "Company", "Price", "Chg_1D%",
    "RS_22d_Idx%", "RSI_14",
    "SL_Buy%", "SL_Grade", "SL_Buy_Price",
    "Total_Score", "Fin_Score",
    "Sales_YoY%", "PAT_YoY%", "ROE%",
    "Chart_Pattern",
]

# Signal_Label sort order for display (best signals first)
SIGNAL_LABEL_ORDER = {
    "🌟 Triple Confirmed": 0,
    "🌟 RS30 + Long":      1,
    "🌟 RS30 + Swing":     2,
    "🌟 RS30 Leader":      3,
    "🌟 Long Momentum":    4,
    "🌟 Prime Setup":      5,
    "✅ Long Momentum":    6,
    "✅ Strong RS":        7,
    "📈 Swing Entry":      8,
    "📈 RS Leader":        9,
    "👁 Setup Building":   10,
    "👁 RS30 Watch":       11,
    "👁 LST Watch":        12,
    "👁 MST Watch":        13,
    "👁 Watch":            14,
    "⬜ Neutral":          15,
    "🔴 RS Breakdown":     16,
}
