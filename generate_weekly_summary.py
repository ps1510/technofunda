"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  generate_weekly_summary.py  —  Weekly "What Changed" HTML report          ║
║                                                                            ║
║  Parses already-generated country HTML files, compares signal counts       ║
║  with the previous week's snapshot, and writes weekly_summary.html.        ║
║                                                                            ║
║  Usage:                                                                    ║
║    python generate_weekly_summary.py                                       ║
║    python generate_weekly_summary.py --out path/to/weekly_summary.html    ║
║    python generate_weekly_summary.py --force   # overwrite this week's snap║
║    python generate_weekly_summary.py --no-save # dry run, no snapshot saved║
║                                                                            ║
║  Run each Sunday after all country scripts have completed.                 ║
║  Snapshots stored in  weekly_snapshots/snapshot_YYYY-WNN.json             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import argparse, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure UTF-8 output on Windows (emoji in print statements)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).parent

# ── Import from build_index (avoids duplicating COUNTRIES + parse_country_html) ─
sys.path.insert(0, str(SCRIPT_DIR))
try:
    from build_index import COUNTRIES, parse_country_html
except ImportError:
    print("ERROR: build_index.py not found. Run this from the same directory.")
    sys.exit(1)

SNAPSHOT_DIR = SCRIPT_DIR / "weekly_snapshots"

# ─────────────────────────────────────────────────────────────────────────────
#  SNAPSHOT: save / load
# ─────────────────────────────────────────────────────────────────────────────

def current_week_key():
    now = datetime.now(timezone.utc)
    return f"{now.year}-W{now.isocalendar()[1]:02d}"

def _snap_path(week_key: str) -> Path:
    return SNAPSHOT_DIR / f"snapshot_{week_key}.json"

def save_snapshot(data: dict, week_key: str) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    p = _snap_path(week_key)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p

def load_previous_snapshot(current_key: str):
    """Return the most recent snapshot older than current_key, or None."""
    if not SNAPSHOT_DIR.exists():
        return None
    snapshots = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"), reverse=True)
    current_p = _snap_path(current_key)
    for p in snapshots:
        if p.name == current_p.name:
            continue
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    return None

# ─────────────────────────────────────────────────────────────────────────────
#  HTML PARSING: extract hc-sectors pills (top/worst sectors per market)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_sector_pills(html: str) -> dict:
    """Return {top: [...], worst: [...]} from health-card hc-sectors divs."""
    top, worst = [], []
    # hc-sectors divs contain span.hc-label + span.sec-pill elements
    for block in re.findall(r'<div class="hc-sectors">(.*?)</div>', html, re.DOTALL):
        label_m = re.search(r'class="hc-label">(.*?)</span>', block)
        label   = label_m.group(1) if label_m else ""
        pills   = re.findall(r'class="sec-pill[^"]*">([^<]+)</span>', block)
        if "Top" in label or "\U0001f7e2" in label:   # 🟢
            top = pills
        elif "Worst" in label or "\U0001f534" in label:  # 🔴
            worst = pills
    return {"top": top[:3], "worst": worst[:3]}

# ─────────────────────────────────────────────────────────────────────────────
#  DATA COLLECTION
# ─────────────────────────────────────────────────────────────────────────────

def collect_market_data(base_dir: Path) -> dict:
    """Parse all available country HTML files and return a markets dict."""
    markets = {}
    for country in COUNTRIES:
        html_path = base_dir / country["html_file"]
        if not html_path.exists():
            continue

        data = parse_country_html(str(html_path), country)
        if data["status"] != "live":
            continue

        # Sector pills (re-read; parse_country_html already opened the file once)
        try:
            html_text = html_path.read_text(encoding="utf-8", errors="ignore")
            sectors = _extract_sector_pills(html_text)
        except Exception:
            sectors = {"top": [], "worst": []}

        sig     = data["signals"]
        total   = data["universe"] or 1
        buy_cnt = sig["prime"] + sig["conf"] + sig["rs"]
        buy_pct = round(100 * buy_cnt / max(total, 1))

        markets[country["name"]] = {
            "flag":          country["flag"],
            "id":            country["id"],
            "index_name":    country["index_name"],
            "mood":          data["mood"],
            "prime":         sig["prime"],
            "conf":          sig["conf"],
            "rs":            sig["rs"],
            "watch":         sig["watch"],
            "avoid":         sig["avoid"],
            "total":         total,
            "buy_cnt":       buy_cnt,
            "buy_pct":       buy_pct,
            "updated":       data["updated"],
            "top_sectors":   sectors["top"],
            "worst_sectors": sectors["worst"],
        }

    return markets

# ─────────────────────────────────────────────────────────────────────────────
#  DELTA COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────

def compute_deltas(current: dict, prev_snapshot: dict) -> dict:
    """Return {market_name: delta_dict | None} comparing current vs prev."""
    prev_markets = prev_snapshot.get("markets", {})
    deltas = {}
    for name, cur in current.items():
        prev = prev_markets.get(name)
        if not prev:
            deltas[name] = None
            continue
        deltas[name] = {
            "d_prime":   cur["prime"]   - prev.get("prime",   cur["prime"]),
            "d_conf":    cur["conf"]    - prev.get("conf",    cur["conf"]),
            "d_rs":      cur["rs"]      - prev.get("rs",      cur["rs"]),
            "d_buy_pct": cur["buy_pct"] - prev.get("buy_pct", cur["buy_pct"]),
            "mood_prev": prev.get("mood", cur["mood"]),
        }
    return deltas

# ─────────────────────────────────────────────────────────────────────────────
#  HTML HELPERS
# ─────────────────────────────────────────────────────────────────────────────

_MOOD = {
    "bull":   ("Risk-On",  "mood-on"),
    "mixed":  ("Mixed",    "mood-mix"),
    "bear":   ("Risk-Off", "mood-off"),
    "coming": ("—",        "dim"),
}
_MOOD_ARROW = {
    ("bull", "mixed"): "↘",
    ("bull", "bear"):  "↘↘",
    ("mixed", "bear"): "↘",
    ("mixed", "bull"): "↗",
    ("bear", "mixed"): "↗",
    ("bear", "bull"):  "↗↗",
}

def _delta_html(val, suffix=""):
    if val is None:
        return '<span class="d-zero">—</span>'
    if val == 0:
        return '<span class="d-zero">±0</span>'
    cls  = "d-pos" if val > 0 else "d-neg"
    sign = "+" if val > 0 else ""
    return f'<span class="{cls}">{sign}{val}{suffix}</span>'

# ─────────────────────────────────────────────────────────────────────────────
#  HTML GENERATION
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """
:root{
  --bg:#0f1117;--bg2:#151820;--bg3:#1c1f2e;
  --border:rgba(255,255,255,0.07);
  --text:#e2e4ec;--text2:#8b90a8;--text3:#7b82a0;
  --accent:#5b8def;--green:#22c55e;--red:#ef4444;--amber:#f59e0b;
  --radius:10px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  background:var(--bg);color:var(--text);font-size:15px;line-height:1.5}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}

/* Header */
.app-header{background:var(--bg2);border-bottom:1px solid var(--border);
  padding:11px 20px;display:flex;align-items:center;justify-content:space-between;
  position:sticky;top:0;z-index:10}
.brand{font-weight:700;color:var(--accent);font-size:16px}
.hdr-meta{font-size:12px;color:var(--text3)}

/* Layout */
.container{max-width:1400px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;font-weight:700;margin-bottom:4px}
h2{font-size:15px;font-weight:600;color:var(--text2);margin:32px 0 12px;
  border-bottom:1px solid var(--border);padding-bottom:6px;text-transform:uppercase;
  letter-spacing:.05em}
.week-meta{font-size:13px;color:var(--text3);margin-bottom:24px}

/* Banner */
.no-prev-banner{background:#1c1810;border:1px solid #92400e;border-radius:var(--radius);
  padding:10px 16px;font-size:13px;color:#fbbf24;margin-bottom:20px}

/* Pulse cards */
.pulse-grid{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:8px}
.pulse-card{background:var(--bg2);border:1px solid var(--border);
  border-radius:var(--radius);padding:14px 18px;min-width:130px;flex:1}
.pulse-lbl{font-size:11px;color:var(--text3);text-transform:uppercase;
  letter-spacing:.05em;margin-bottom:4px}
.pulse-val{font-size:26px;font-weight:700}
.pulse-val.prime-col{color:#4ade80}
.pulse-val.conf-col{color:#86efac}
.pulse-val.rs-col{color:#5b8def}
.pulse-d{font-size:12px;color:var(--text3);margin-top:2px}

/* Movers section */
.movers-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.movers-col h3{font-size:13px;font-weight:600;margin-bottom:10px;padding-bottom:4px;
  border-bottom:1px solid var(--border)}
.movers-col.good h3{color:#4ade80}
.movers-col.bad  h3{color:#f87171}
.mover-cards{display:flex;flex-direction:column;gap:8px}
.mover-card{border-radius:8px;padding:10px 14px;border:1px solid}
.mover-card.good{background:#0d2b1a;border-color:#166534}
.mover-card.bad {background:#2b0d0d;border-color:#991b1b}
.mc-name{font-size:14px;font-weight:600;margin-bottom:2px}
.mc-delta{font-size:20px;font-weight:700}
.mover-card.good .mc-delta{color:#4ade80}
.mover-card.bad  .mc-delta{color:#f87171}
.mc-detail{font-size:11px;color:var(--text3);margin-top:2px}
.no-movers{font-size:13px;color:var(--text3);padding:8px 0}

/* Table */
.tbl-wrap{overflow-x:auto;border-radius:var(--radius);border:1px solid var(--border)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:var(--bg3);padding:8px 10px;text-align:left;font-size:11px;
  font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.04em;
  border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:8px 10px;border-bottom:1px solid var(--border);vertical-align:middle;
  white-space:nowrap}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,.025)}
td.n{text-align:right;font-variant-numeric:tabular-nums}
td.dim{color:var(--text3)}
td.seccol{max-width:170px;overflow:hidden;text-overflow:ellipsis;color:var(--text3);
  font-size:12px;white-space:nowrap}

/* Mood */
.mood-on {color:#22c55e;font-weight:600}
.mood-mix{color:#f59e0b;font-weight:600}
.mood-off{color:#ef4444;font-weight:600}
.mood-arr{font-size:11px;margin-left:3px;opacity:.7}

/* Deltas */
.d-pos{color:#22c55e;font-weight:600}
.d-neg{color:#ef4444;font-weight:600}
.d-zero{color:var(--text3)}
.buy-pct{font-weight:600}

/* Footer */
.footer{text-align:center;padding:32px 16px;font-size:12px;color:var(--text3);
  border-top:1px solid var(--border);margin-top:40px}

@media(max-width:720px){
  .movers-grid{grid-template-columns:1fr}
  .pulse-card{min-width:100px}
  th,td{padding:6px 8px}
}
"""

def render_summary(current_markets: dict, prev_snapshot, week_key: str, output_path: Path):
    """Build and write weekly_summary.html."""
    now      = datetime.now(timezone.utc)
    gen_time = now.strftime("%d %b %Y %H:%M UTC")
    prev_week = prev_snapshot.get("week", "—") if prev_snapshot else None
    prev_date = prev_snapshot.get("date", "—") if prev_snapshot else None

    deltas = compute_deltas(current_markets, prev_snapshot) if prev_snapshot else {}

    # ── Aggregates ─────────────────────────────────────────────────────────────
    live        = list(current_markets.values())
    agg_prime   = sum(m["prime"]   for m in live)
    agg_conf    = sum(m["conf"]    for m in live)
    agg_rs      = sum(m["rs"]      for m in live)
    agg_buy_cnt = sum(m["buy_cnt"] for m in live)
    agg_total   = sum(m["total"]   for m in live)
    agg_buy_pct = round(100 * agg_buy_cnt / max(agg_total, 1))

    with_delta  = [d for d in deltas.values() if d is not None]
    agg_d_prime = sum(d["d_prime"]   for d in with_delta) if with_delta else None
    agg_d_conf  = sum(d["d_conf"]    for d in with_delta) if with_delta else None
    agg_d_buy   = round(sum(d["d_buy_pct"] for d in with_delta) / len(with_delta)) if with_delta else None

    # ── Sort markets by buy_pct desc ───────────────────────────────────────────
    sorted_mkts = sorted(current_markets.items(), key=lambda x: x[1]["buy_pct"], reverse=True)

    # ── Table rows ─────────────────────────────────────────────────────────────
    rows_html = ""
    for name, m in sorted_mkts:
        d         = deltas.get(name)
        ml, mc    = _MOOD.get(m["mood"], ("—", ""))
        mood_prev = d["mood_prev"] if d else m["mood"]
        arr       = _MOOD_ARROW.get((mood_prev, m["mood"]), "")
        arr_html  = f'<span class="mood-arr">{arr}</span>' if arr else ""

        top_s = ", ".join(m.get("top_sectors", [])[:2]) or "—"

        rows_html += (
            f"<tr>"
            f"<td>{m['flag']} {name}</td>"
            f"<td class='{mc}'>{ml}{arr_html}</td>"
            f"<td class='n'>{m['prime']}</td>"
            f"<td class='n'>{_delta_html(d['d_prime']   if d else None)}</td>"
            f"<td class='n'>{m['conf']}</td>"
            f"<td class='n'>{_delta_html(d['d_conf']    if d else None)}</td>"
            f"<td class='n'>{m['rs']}</td>"
            f"<td class='n buy-pct'>{m['buy_pct']}%</td>"
            f"<td class='n'>{_delta_html(d['d_buy_pct'] if d else None, '%')}</td>"
            f"<td class='n dim'>{m['total']:,}</td>"
            f"<td class='seccol' title='{top_s}'>{top_s}</td>"
            f"</tr>\n"
        )

    # ── Mover cards ────────────────────────────────────────────────────────────
    def _mover_card(name, d, good):
        m    = current_markets.get(name, {})
        icon = "📈" if good else "📉"
        cls  = "good" if good else "bad"
        return (
            f'<div class="mover-card {cls}">'
            f'<div class="mc-name">{m.get("flag","")} {name}</div>'
            f'<div class="mc-delta">{icon} {d["d_buy_pct"]:+}% buy setups</div>'
            f'<div class="mc-detail">'
            f'🌟 Prime {d["d_prime"]:+} &nbsp;·&nbsp; '
            f'✅ Confirmed {d["d_conf"]:+} &nbsp;·&nbsp; '
            f'📈 RS {d["d_rs"]:+}'
            f'</div></div>'
        )

    mover_pairs = [(n, d) for n, d in deltas.items() if d is not None]
    improvers   = sorted(mover_pairs, key=lambda x: x[1]["d_buy_pct"], reverse=True)
    decliners   = sorted(mover_pairs, key=lambda x: x[1]["d_buy_pct"])

    imp_html = "".join(_mover_card(n, d, True)  for n, d in improvers[:3]  if d["d_buy_pct"] > 0)
    dec_html = "".join(_mover_card(n, d, False) for n, d in decliners[:3]  if d["d_buy_pct"] < 0)
    if not imp_html: imp_html = '<p class="no-movers">No significant improvements this week.</p>'
    if not dec_html: dec_html = '<p class="no-movers">No significant deteriorations this week.</p>'

    # ── Banner when no previous data ───────────────────────────────────────────
    no_prev_banner = (
        '<div class="no-prev-banner">⚠️ No previous week snapshot found. '
        'Delta columns (Δ) will populate after the second weekly run.</div>'
        if not prev_snapshot else ""
    )

    # ── Comparison subtitle ────────────────────────────────────────────────────
    cmp_txt = (
        f"Compared to {prev_week} ({prev_date})"
        if prev_snapshot else
        "First run — no prior week to compare"
    )

    # ── Movers section (only when we have deltas) ─────────────────────────────
    movers_section = ""
    if prev_snapshot:
        movers_section = f"""
  <h2>Signal Movers This Week</h2>
  <div class="movers-grid">
    <div class="movers-col good">
      <h3>📈 Most Improved Markets</h3>
      <div class="mover-cards">{imp_html}</div>
    </div>
    <div class="movers-col bad">
      <h3>📉 Most Deteriorated Markets</h3>
      <div class="mover-cards">{dec_html}</div>
    </div>
  </div>"""

    # ── Full HTML ─────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>TechnoFunda — Weekly Summary {week_key}</title>
  <style>{_CSS}</style>
</head>
<body>

<div class="app-header">
  <span class="brand">TechnoFunda</span>
  <span class="hdr-meta"><a href="index.html">← Home</a> &nbsp;·&nbsp; Weekly Summary {week_key}</span>
</div>

<div class="container">

  <h1>Weekly Market Summary — {week_key}</h1>
  <p class="week-meta">
    Generated {gen_time} &nbsp;·&nbsp; {cmp_txt}
    &nbsp;·&nbsp; {len(current_markets)} markets analysed
  </p>

  {no_prev_banner}

  <h2>Global Pulse</h2>
  <div class="pulse-grid">
    <div class="pulse-card">
      <div class="pulse-lbl">🌟 Prime</div>
      <div class="pulse-val prime-col">{agg_prime:,}</div>
      <div class="pulse-d">{_delta_html(agg_d_prime)} vs last week</div>
    </div>
    <div class="pulse-card">
      <div class="pulse-lbl">✅ Confirmed</div>
      <div class="pulse-val conf-col">{agg_conf:,}</div>
      <div class="pulse-d">{_delta_html(agg_d_conf)} vs last week</div>
    </div>
    <div class="pulse-card">
      <div class="pulse-lbl">📈 RS Buy</div>
      <div class="pulse-val rs-col">{agg_rs:,}</div>
      <div class="pulse-d">across all markets</div>
    </div>
    <div class="pulse-card">
      <div class="pulse-lbl">Buy Setup %</div>
      <div class="pulse-val">{agg_buy_pct}%</div>
      <div class="pulse-d">{_delta_html(agg_d_buy, "% avg")} vs last week</div>
    </div>
    <div class="pulse-card">
      <div class="pulse-lbl">Universe</div>
      <div class="pulse-val">{agg_total:,}</div>
      <div class="pulse-d">stocks in {len(current_markets)} markets</div>
    </div>
  </div>

  {movers_section}

  <h2>Market Overview</h2>
  <div class="tbl-wrap">
    <table>
      <thead><tr>
        <th>Market</th>
        <th>Mood</th>
        <th title="Prime Buy setups">🌟 Prime</th>
        <th title="Change vs last week">Δ</th>
        <th title="Confirmed Buy setups">✅ Conf</th>
        <th title="Change vs last week">Δ</th>
        <th title="RS Buy setups">📈 RS</th>
        <th title="Buy setups as % of universe">Buy&nbsp;%</th>
        <th title="Change in Buy % vs last week">Δ%</th>
        <th>Universe</th>
        <th>Top Sectors</th>
      </tr></thead>
      <tbody>
{rows_html}      </tbody>
    </table>
  </div>

  <div class="footer">
    TechnoFunda · Weekly Summary {week_key} · Generated {gen_time}<br>
    Not financial advice. Data is delayed / end-of-day.<br>
    <a href="index.html">← Back to Home</a>
  </div>

</div>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"  ✅  Written → {output_path}")
    return html


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Generate weekly market summary HTML")
    ap.add_argument("--out",     default="weekly_summary.html",
                    help="Output path (default: weekly_summary.html in this directory)")
    ap.add_argument("--force",   action="store_true",
                    help="Overwrite the snapshot for the current week if it exists")
    ap.add_argument("--no-save", action="store_true",
                    help="Do not save a snapshot (dry run / testing)")
    args = ap.parse_args()

    week_key = current_week_key()
    print(f"\n📅  Weekly Summary Generator — {week_key}")
    print(f"    Directory : {SCRIPT_DIR}")

    # 1. Parse HTML files
    print("\n🔍  Parsing country HTML files...")
    current = collect_market_data(SCRIPT_DIR)
    if not current:
        print("❌  No country HTML files found. Run country analysis scripts first.")
        sys.exit(1)
    print(f"    {len(current)} live markets found: {', '.join(current)}")

    # 2. Load previous snapshot
    prev = load_previous_snapshot(week_key)
    if prev:
        print(f"    Previous : {prev.get('week','?')} ({prev.get('date','?')}) — "
              f"{len(prev.get('markets', {}))} markets")
    else:
        print("    No previous snapshot — delta columns will show '—'")

    # 3. Save current snapshot
    if not args.no_save:
        snap_p = _snap_path(week_key)
        if snap_p.exists() and not args.force:
            print(f"    Snapshot already exists for {week_key}. Use --force to overwrite.")
        else:
            saved = save_snapshot({
                "week":    week_key,
                "date":    datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "markets": current,
            }, week_key)
            print(f"    Snapshot saved → {saved}")

    # 4. Render HTML
    out_path = SCRIPT_DIR / args.out
    print(f"\n📝  Generating {out_path.name} ...")
    render_summary(current, prev, week_key, out_path)

    print(f"\n✅  Done.")


if __name__ == "__main__":
    main()
