"""
market_rrg.py  —  Relative Rotation Graph integration module
─────────────────────────────────────────────────────────────
Called from all country market scripts.
Takes already-fetched sector price Series + benchmark Series,
builds ratio time-series (no extra download), returns an HTML
snippet ready to drop into the main page as the RRG tab.

Public API
----------
  build_rrg_data(sector_prices, index_prices)  -> dict
  build_rrg_section(rrg_data, sector_list, sector_colors,
                    market_name, benchmark_name,
                    market_code=None)  -> str
"""
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Display names for each market code
_MARKET_META = {
    "IN":  ("India",        "Nifty 50"),
    "US":  ("US",           "S&P 500 (SPY)"),
    "UK":  ("UK",           "FTSE 100"),
    "CA":  ("Canada",       "S&P/TSX"),
    "AU":  ("Australia",    "ASX 200"),
    "DE":  ("Germany",      "DAX"),
    "JP":  ("Japan",        "Nikkei 225"),
    "SG":  ("Singapore",    "STI"),
    "HK":  ("Hong Kong",    "Hang Seng"),
    "FR":  ("France",       "CAC 40"),
    "IT":  ("Italy",        "FTSE MIB"),
    "BR":  ("Brazil",       "Bovespa"),
    "ZA":  ("South Africa", "JSE All Share"),
    "MX":  ("Mexico",       "IPC (BMV)"),
    "AE":  ("UAE",          "DFM"),
    "UAE": ("UAE",          "DFM"),
    "CH":  ("Switzerland",  "SMI"),
    "CN":  ("China",        "CSI 300"),
    "ES":  ("Spain",        "IBEX 35"),
    "ID":  ("Indonesia",    "IDX Composite"),
    "KR":  ("South Korea",  "KOSPI"),
    "MY":  ("Malaysia",     "KLCI"),
    "NL":  ("Netherlands",  "AEX"),
    "PL":  ("Poland",       "WIG20"),
    "SA":  ("Saudi Arabia", "Tadawul"),
    "SE":  ("Sweden",       "OMX Stockholm"),
    "TH":  ("Thailand",     "SET"),
    "TR":  ("Turkey",       "BIST 100"),
    "TW":  ("Taiwan",       "TAIEX"),
}

# One colour per sector (same palette as rrg_test.py)
_PALETTE = [
    "#E91E63","#2196F3","#4CAF50","#FF9800","#9C27B0",
    "#00BCD4","#F44336","#8BC34A","#FF5722","#607D8B",
    "#795548","#009688","#3F51B5","#FFC107","#673AB7",
    "#CDDC39","#03A9F4","#FF4081","#00E676","#FF6D00",
]


# ─────────────────────────────────────────────────────────────────────────────
#  DATA BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_rrg_data(sector_prices: dict, index_prices: pd.Series) -> dict:
    """
    Build raw sector/benchmark ratio time-series for the RRG chart.

    Parameters
    ----------
    sector_prices : {sector_name: pd.Series(daily close prices)}
        Already fetched by fetch_india_sector_prices() or fetch_us_sector_prices().
        Values are raw (unadjusted) price series — _normalize() preserves prices.
    index_prices  : pd.Series  (daily benchmark close prices, e.g. ^NSEI or SPY)

    Returns
    -------
    {
      'weekly': { name: {'ratio': [float, ...], 'dates': [str, ...]} },
      'daily':  { name: {'ratio': [float, ...], 'dates': [str, ...]} },
    }
    """
    bench = index_prices.dropna()

    result = {"weekly": {}, "daily": {}}

    for name, sec_series in sector_prices.items():
        sec = sec_series.dropna()

        # Align on common trading dates
        common = sec.index.intersection(bench.index)
        if len(common) < 60:
            continue

        s = sec.loc[common]
        b = bench.loc[common]

        # Daily ratio
        ratio_d = (s / b).dropna()
        if len(ratio_d) < 40:
            continue
        result["daily"][name] = {
            "ratio": [round(float(v), 6) for v in ratio_d.values],
            "dates": [d.strftime("%Y-%m-%d") for d in ratio_d.index],
        }

        # Weekly ratio (Friday close)
        try:
            sw = s.resample("W-FRI").last().ffill()
            bw = b.resample("W-FRI").last().ffill()
            wc = sw.index.intersection(bw.index)
            ratio_w = (sw.loc[wc] / bw.loc[wc]).dropna()
            if len(ratio_w) >= 20:
                result["weekly"][name] = {
                    "ratio": [round(float(v), 6) for v in ratio_w.values],
                    "dates": [d.strftime("%Y-%m-%d") for d in ratio_w.index],
                }
        except Exception:
            pass

    return result


def make_sector_colors(sector_list: list) -> dict:
    """Assign a stable colour to each sector name."""
    return {
        name: _PALETTE[i % len(_PALETTE)]
        for i, name in enumerate(sector_list)
    }


# ─────────────────────────────────────────────────────────────────────────────
#  HTML GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def build_rrg_section(
    rrg_data: dict,
    sector_list: list,
    sector_colors: dict,
    market_name: str = "",
    benchmark_name: str = "",
    market_code: str = None,
) -> str:
    """
    Return an HTML string to embed as the RRG tab content in the main page.

    The snippet:
    - Is fully self-contained (CSS scoped to .rrg-wrap, JS prefixed rrgXxx)
    - Loads Plotly.js lazily from CDN (only when the tab is first opened)
    - Exposes a global  rrgInit()  function that the tab button calls
    """
    import json

    if market_code and market_code in _MARKET_META:
        _mn, _bn = _MARKET_META[market_code]
        market_name    = market_name    or _mn
        benchmark_name = benchmark_name or _bn
    market_name    = market_name    or (market_code or "Market")
    benchmark_name = benchmark_name or "Benchmark"

    data_js     = json.dumps(rrg_data)
    colors_js   = json.dumps(sector_colors)
    sectors_js  = json.dumps(sector_list)
    title_js    = json.dumps(f"{market_name} Sector Rotation — Relative Rotation Graph")
    bench_js    = json.dumps(benchmark_name)

    return f"""
<!-- ═══ RRG TAB CONTENT ═══════════════════════════════════════════════════ -->
<style>
/* All rules scoped to .rrg-wrap so they never bleed into the main page */
.rrg-wrap {{
  display:flex; flex-direction:column;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:13px;
}}
.rrg-body {{ display:flex; height:calc(100vh - 240px); min-height:400px; gap:0; }}

/* Sidebar */
.rrg-sb {{
  width:175px; min-width:175px; background:var(--bg2,#f5f5f5);
  border-right:1px solid var(--border,#e0e0e0);
  display:flex; flex-direction:column;
  border-radius:6px 0 0 6px; overflow:hidden;
}}
.rrg-sb-hd {{
  padding:10px 10px 7px; border-bottom:1px solid var(--border,#e0e0e0);
  font-size:11px; font-weight:700; text-transform:uppercase;
  letter-spacing:0.5px; color:var(--text2,#666);
}}
.rrg-sb-btns {{ display:flex; gap:5px; margin-top:6px; }}
.rrg-sbtn {{
  flex:1; padding:3px 0; border:1px solid var(--border,#ccc);
  background:var(--bg1,#fff); color:var(--text1,#333);
  border-radius:3px; cursor:pointer; font-size:10px; font-weight:700;
}}
.rrg-sbtn:hover {{ background:var(--accent-soft,#e8edff); }}
.rrg-sbtn.rrg-danger {{ color:#c0392b; border-color:#e0b0b0; }}
.rrg-sl {{ flex:1; overflow-y:auto; padding:4px 0; }}
.rrg-sl::-webkit-scrollbar {{ width:3px; }}
.rrg-sl::-webkit-scrollbar-thumb {{ background:#ccc; border-radius:2px; }}
.rrg-item {{
  display:flex; align-items:center; gap:6px; padding:5px 9px;
  cursor:pointer; border-radius:3px; margin:1px 4px;
  transition:background 0.1s; user-select:none;
}}
.rrg-item:hover {{ background:var(--accent-soft,#eef0f8); }}
.rrg-item.rrg-off {{ opacity:0.3; }}
.rrg-dot {{ width:8px; height:8px; border-radius:50%; flex-shrink:0; }}
.rrg-lbl {{ flex:1; font-size:11px; }}
.rrg-chk {{ width:12px; height:12px; cursor:pointer; }}

/* Main area */
.rrg-main {{ flex:1; display:flex; flex-direction:column; min-width:0; }}

/* Controls */
.rrg-ctrl {{
  background:var(--bg1,#fff); border-bottom:1.5px solid var(--border,#e4e8ef);
  padding:7px 12px; display:flex; align-items:center; gap:14px;
  flex-wrap:wrap; flex-shrink:0;
}}
.rrg-cg {{ display:flex; align-items:center; gap:6px; }}
.rrg-cl {{
  font-size:10px; color:var(--text2,#777); font-weight:700;
  text-transform:uppercase; letter-spacing:0.3px; white-space:nowrap;
}}
.rrg-fbtn {{
  padding:4px 11px; border:2px solid var(--border,#ccc);
  background:var(--bg2,#f5f5f5); border-radius:4px; cursor:pointer;
  font-size:11px; font-weight:700; color:var(--text2,#555);
  transition:all 0.15s;
}}
.rrg-fbtn.rrg-on {{ background:#4361ee; border-color:#4361ee; color:#fff; }}
.rrg-fbtn:hover:not(.rrg-on) {{ border-color:#999; }}
.rrg-sw {{ display:flex; align-items:center; gap:5px; }}
.rrg-sw input[type=range] {{
  width:100px; height:3px; cursor:pointer; accent-color:#4361ee;
}}
.rrg-sv {{ min-width:26px; text-align:right; font-weight:700;
           color:#4361ee; font-size:12px; }}
.rrg-su {{ font-size:10px; color:#aaa; }}
.rrg-sel {{
  padding:4px 6px; border:1.5px solid var(--border,#ccc); border-radius:4px;
  background:var(--bg1,#fff); font-size:11px; cursor:pointer;
  color:var(--text1,#444); font-weight:600;
}}
.rrg-sel:focus {{ outline:none; border-color:#4361ee; }}
.rrg-hint {{
  margin-left:auto; font-size:10px; color:#bbb; font-style:italic;
  white-space:nowrap;
}}

/* Chart placeholder */
.rrg-chart-wrap {{ flex:1; min-height:0; position:relative; }}
.rrg-chart {{ width:100%; height:100%; }}
.rrg-loading {{
  position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
  font-size:14px; color:#999; font-style:italic;
}}

/* Quadrant table */
.rrg-qt {{
  background:var(--bg1,#fff); border-top:1.5px solid var(--border,#e4e8ef);
  padding:7px 12px 9px; flex-shrink:0;
}}
.rrg-qt-ttl {{
  font-size:10px; font-weight:700; color:#999; text-transform:uppercase;
  letter-spacing:0.5px; margin-bottom:6px;
}}
.rrg-qt-legend {{
  font-size:10px; color:#bbb; text-align:center; margin-bottom:5px; letter-spacing:0.3px;
}}
.rrg-qt-grid {{
  display:grid; grid-template-columns:repeat(2,1fr); gap:8px;
}}
.rrg-qc {{
  border-radius:5px; padding:4px 8px; min-height:28px;
}}
.rrg-qc.rrg-leading  {{ background:rgba(0,200,100,0.07); border:1.5px solid rgba(0,180,80,0.25); }}
.rrg-qc.rrg-improving{{ background:rgba(70,70,245,0.06); border:1.5px solid rgba(70,70,220,0.22); }}
.rrg-qc.rrg-weakening{{ background:rgba(255,195,0,0.07); border:1.5px solid rgba(200,155,0,0.25); }}
.rrg-qc.rrg-lagging  {{ background:rgba(255,60,60,0.06); border:1.5px solid rgba(220,50,50,0.2); }}
.rrg-qh {{ font-size:10px; font-weight:800; text-transform:uppercase;
           letter-spacing:0.5px; margin-bottom:4px; }}
.rrg-qc.rrg-leading  .rrg-qh {{ color:#00aa55; }}
.rrg-qc.rrg-improving .rrg-qh {{ color:#4040cc; }}
.rrg-qc.rrg-weakening .rrg-qh {{ color:#bb8800; }}
.rrg-qc.rrg-lagging  .rrg-qh {{ color:#cc3030; }}
.rrg-qs {{
  display:flex; align-items:center; gap:4px; margin:2px 0;
  font-size:11px; font-weight:600; color:var(--text1,#333);
}}
.rrg-qdot {{ width:7px; height:7px; border-radius:50%; flex-shrink:0; }}
.rrg-qe {{ font-size:10px; color:#bbb; font-style:italic; }}
</style>

<div class="rrg-wrap">
  <!-- body: sidebar + main -->
  <div class="rrg-body">

    <!-- SIDEBAR -->
    <div class="rrg-sb">
      <div class="rrg-sb-hd">
        Sectors
        <div class="rrg-sb-btns">
          <button class="rrg-sbtn" onclick="rrgSelAll()">All</button>
          <button class="rrg-sbtn rrg-danger" onclick="rrgSelNone()">None</button>
        </div>
      </div>
      <div class="rrg-sl" id="rrg-sl"></div>
    </div>

    <!-- MAIN -->
    <div class="rrg-main">

      <!-- Controls -->
      <div class="rrg-ctrl">
        <div class="rrg-cg">
          <span class="rrg-cl">Frequency</span>
          <button class="rrg-fbtn rrg-on" id="rrg-bW" onclick="rrgSetFreq('weekly')">Weekly</button>
          <button class="rrg-fbtn"        id="rrg-bD" onclick="rrgSetFreq('daily')">Daily</button>
        </div>
        <div class="rrg-cg">
          <span class="rrg-cl">Tail</span>
          <div class="rrg-sw">
            <input type="range" id="rrg-tail" min="5" max="52" value="20"
                   oninput="rrgSlide('tail',this.value)">
            <span class="rrg-sv" id="rrg-v-tail">20</span>
            <span class="rrg-su" id="rrg-u-tail">wks</span>
          </div>
        </div>
        <div class="rrg-cg">
          <span class="rrg-cl">RS Period</span>
          <select class="rrg-sel" id="rrg-rs" onchange="rrgDraw()">
            <option value="13">13 wks</option>
            <option value="26">26 wks</option>
            <option value="52" selected>52 wks</option>
          </select>
        </div>
        <div class="rrg-cg">
          <span class="rrg-cl">Momentum</span>
          <select class="rrg-sel" id="rrg-mom" onchange="rrgDraw()">
            <option value="3">3 — Fast</option>
            <option value="5" selected>5 — Std</option>
            <option value="10">10 — Slow</option>
          </select>
        </div>
        <div class="rrg-cg">
          <span class="rrg-cl">Smooth</span>
          <div class="rrg-sw">
            <input type="range" id="rrg-smooth" min="1" max="9" value="5"
                   oninput="rrgSlide('smooth',this.value)">
            <span class="rrg-sv" id="rrg-v-smooth">5</span>
            <span class="rrg-su">EMA</span>
          </div>
        </div>
        <span class="rrg-hint">Scroll=zoom &bull; Drag=pan &bull; Dbl-click=reset</span>
      </div>

      <!-- Chart -->
      <div class="rrg-chart-wrap">
        <div class="rrg-chart" id="rrg-chart">
          <div class="rrg-loading" id="rrg-loading">Loading chart&hellip;</div>
        </div>
      </div>

    </div><!-- /rrg-main -->
  </div><!-- /rrg-body -->

  <!-- Quadrant table lives outside rrg-body so it's never clipped by the chart flex layout -->
  <div class="rrg-qt">
    <div class="rrg-qt-ttl">Current Quadrant Positions</div>
    <div class="rrg-qt-legend">&#8592; RS-Ratio below 100 (underperforming) &nbsp;&bull;&nbsp; RS-Ratio above 100 (outperforming) &#8594;</div>
    <div class="rrg-qt-grid">
      <!-- Row 1: RS-Momentum > 100 (rising) -->
      <div class="rrg-qc rrg-improving">
        <div class="rrg-qh">&#9651; Improving</div>
        <div id="rrg-qt-improving"></div>
      </div>
      <div class="rrg-qc rrg-leading">
        <div class="rrg-qh">&#9650; Leading</div>
        <div id="rrg-qt-leading"></div>
      </div>
      <!-- Row 2: RS-Momentum < 100 (falling) -->
      <div class="rrg-qc rrg-lagging">
        <div class="rrg-qh">&#9661; Lagging</div>
        <div id="rrg-qt-lagging"></div>
      </div>
      <div class="rrg-qc rrg-weakening">
        <div class="rrg-qh">&#9660; Weakening</div>
        <div id="rrg-qt-weakening"></div>
      </div>
    </div>
  </div>

</div><!-- /rrg-wrap -->

<script>
(function() {{
// ── Data injected by Python ──────────────────────────────────────
const _RRG   = {data_js};
const _CLRS  = {colors_js};
const _SECTS = {sectors_js};

// ── State ────────────────────────────────────────────────────────
let _freq   = 'weekly';
let _active = new Set(_SECTS);
let _inited = false;
let _ready  = false;   // Plotly loaded?

// ── EMA smoothing ────────────────────────────────────────────────
function _ema(arr, span) {{
  if (span <= 1) return arr;
  const alpha = 2 / (span + 1);
  const out = new Float64Array(arr.length).fill(NaN);
  let prev = NaN;
  for (let i = 0; i < arr.length; i++) {{
    if (isNaN(arr[i])) continue;
    if (isNaN(prev)) {{ out[i] = arr[i]; prev = arr[i]; continue; }}
    out[i] = alpha * arr[i] + (1 - alpha) * prev;
    prev = out[i];
  }}
  return out;
}}

// ── Rolling z-score ───────────────────────────────────────────────
function _rs(arr, n) {{
  const minP = Math.max(5, Math.ceil(n / 3));
  const m = new Float64Array(arr.length).fill(NaN);
  const s = new Float64Array(arr.length).fill(NaN);
  for (let i = 0; i < arr.length; i++) {{
    const lo = Math.max(0, i - n + 1);
    let sum = 0, cnt = 0;
    for (let j = lo; j <= i; j++) {{ if (!isNaN(arr[j])) {{ sum += arr[j]; cnt++; }} }}
    if (cnt < minP) continue;
    const mean = sum / cnt;
    let vr = 0;
    for (let j = lo; j <= i; j++) {{ if (!isNaN(arr[j])) vr += (arr[j]-mean)**2; }}
    m[i] = mean; s[i] = Math.sqrt(vr / cnt);
  }}
  return {{ m, s }};
}}

function _calcRRG(ratio, rsPeriod, momPeriod, smooth) {{
  const sm = _ema(ratio, smooth || 5);
  const {{ m: rm, s: rs }} = _rs(sm, rsPeriod);
  const rsR = sm.map((v,i) => isNaN(rm[i])||rs[i]<1e-9 ? NaN : (v-rm[i])/rs[i]*10+100);
  const delta = rsR.map((v,i) =>
    i>=momPeriod && !isNaN(v) && !isNaN(rsR[i-momPeriod]) ? v-rsR[i-momPeriod] : NaN);
  const {{ m: dm, s: ds }} = _rs(delta, rsPeriod);
  const rsM = delta.map((v,i) =>
    isNaN(v)||isNaN(dm[i])||ds[i]<1e-9 ? NaN : (v-dm[i])/ds[i]*10+100);
  return {{ rsR, rsM }};
}}

function _quad(x, y) {{
  if (x>=100&&y>=100) return 'leading';
  if (x>=100&&y< 100) return 'weakening';
  if (x< 100&&y>=100) return 'improving';
  return 'lagging';
}}

// ── Sidebar ───────────────────────────────────────────────────────
function _buildSb() {{
  const el = document.getElementById('rrg-sl');
  if (!el) return;
  el.innerHTML = _SECTS.map(n => {{
    const on = _active.has(n);
    return `<div class="rrg-item${{on?'':' rrg-off'}}" data-s="${{n}}" onclick="rrgToggle('${{n}}')">
      <div class="rrg-dot" style="background:${{_CLRS[n]}}"></div>
      <span class="rrg-lbl">${{n}}</span>
      <input class="rrg-chk" type="checkbox" ${{on?'checked':''}} id="rrg-chk-${{n}}"
             onclick="event.stopPropagation()" onchange="rrgToggle('${{n}}')">
    </div>`;
  }}).join('');
}}

// Exposed globally for onclick handlers
window.rrgToggle = function(n) {{
  if (_active.has(n)) _active.delete(n); else _active.add(n);
  const item = document.querySelector(`.rrg-item[data-s="${{n}}"]`);
  if (item) {{
    item.classList.toggle('rrg-off', !_active.has(n));
    const chk = item.querySelector('.rrg-chk');
    if (chk) chk.checked = _active.has(n);
  }}
  if (_ready) rrgDraw();
}};
window.rrgSelAll  = function() {{ _SECTS.forEach(n=>_active.add(n));   _buildSb(); if(_ready)rrgDraw(); }};
window.rrgSelNone = function() {{ _active.clear();                      _buildSb(); if(_ready)rrgDraw(); }};

window.rrgSetFreq = function(f) {{
  _freq = f;
  document.getElementById('rrg-bW').classList.toggle('rrg-on', f==='weekly');
  document.getElementById('rrg-bD').classList.toggle('rrg-on', f==='daily');
  const sl = document.getElementById('rrg-tail');
  const ut = document.getElementById('rrg-u-tail');
  const rs = document.getElementById('rrg-rs');
  const mm = document.getElementById('rrg-mom');
  if (f==='weekly') {{
    sl.max=52; sl.min=5; if(+sl.value>52) sl.value=20; ut.textContent='wks';
    rs.innerHTML='<option value="13">13 wks</option><option value="26">26 wks</option><option value="52" selected>52 wks</option>';
    mm.innerHTML='<option value="3">3 — Fast</option><option value="5" selected>5 — Std</option><option value="10">10 — Slow</option>';
  }} else {{
    sl.max=130; sl.min=5; if(+sl.value<15) sl.value=30; ut.textContent='days';
    rs.innerHTML='<option value="30">30 days</option><option value="65" selected>65 days</option><option value="130">130 days</option>';
    mm.innerHTML='<option value="5">5 — Fast</option><option value="10" selected>10 — Std</option><option value="21">21 — Slow</option>';
  }}
  document.getElementById('rrg-v-tail').textContent = sl.value;
  if (_ready) rrgDraw();
}};

window.rrgSlide = function(id, val) {{
  document.getElementById('rrg-v-' + id).textContent = val;
  if (_ready) rrgDraw();
}};

// ── Chart shapes & annotations ────────────────────────────────────
const _QSHAPES = [
  {{type:'rect',layer:'below',x0:100,x1:300,y0:100,y1:300,fillcolor:'rgba(0,195,95,0.07)',line:{{width:0}}}},
  {{type:'rect',layer:'below',x0:100,x1:300,y0:-100,y1:100,fillcolor:'rgba(245,185,0,0.07)',line:{{width:0}}}},
  {{type:'rect',layer:'below',x0:-100,x1:100,y0:-100,y1:100,fillcolor:'rgba(245,55,55,0.07)',line:{{width:0}}}},
  {{type:'rect',layer:'below',x0:-100,x1:100,y0:100,y1:300,fillcolor:'rgba(70,70,245,0.07)',line:{{width:0}}}},
  {{type:'line',x0:100,x1:100,y0:-100,y1:300,line:{{color:'rgba(0,0,0,0.18)',width:1,dash:'dash'}}}},
  {{type:'line',x0:-100,x1:300,y0:100,y1:100,line:{{color:'rgba(0,0,0,0.18)',width:1,dash:'dash'}}}},
];
const _QANNO = [
  {{x:0.02,y:0.98,xref:'paper',yref:'paper',text:'<b>Improving</b>',showarrow:false,font:{{size:12,color:'rgba(60,60,200,0.45)'}},xanchor:'left',yanchor:'top'}},
  {{x:0.98,y:0.98,xref:'paper',yref:'paper',text:'<b>Leading</b>',showarrow:false,font:{{size:12,color:'rgba(0,170,75,0.55)'}},xanchor:'right',yanchor:'top'}},
  {{x:0.98,y:0.02,xref:'paper',yref:'paper',text:'<b>Weakening</b>',showarrow:false,font:{{size:12,color:'rgba(190,140,0,0.65)'}},xanchor:'right',yanchor:'bottom'}},
  {{x:0.02,y:0.02,xref:'paper',yref:'paper',text:'<b>Lagging</b>',showarrow:false,font:{{size:12,color:'rgba(210,50,50,0.55)'}},xanchor:'left',yanchor:'bottom'}},
];

// ── Draw ──────────────────────────────────────────────────────────
window.rrgDraw = function() {{
  if (!_ready || !window.Plotly) return;
  const tail      = +document.getElementById('rrg-tail').value;
  const rsPeriod  = +document.getElementById('rrg-rs').value;
  const momPeriod = +document.getElementById('rrg-mom').value;
  const smooth    = +document.getElementById('rrg-smooth').value;
  const src       = _RRG[_freq] || {{}};

  const traces=[], arrows=[..._QANNO];
  const tbl={{leading:[],improving:[],weakening:[],lagging:[]}};
  const allX=[], allY=[];

  for (const sec of _SECTS) {{
    if (!_active.has(sec)) continue;
    const raw = src[sec]; if (!raw) continue;
    const {{ rsR, rsM }} = _calcRRG(raw.ratio, rsPeriod, momPeriod, smooth);
    const n=raw.dates.length, start=Math.max(0,n-tail), pts=[];
    for (let i=start;i<n;i++) {{
      if (!isNaN(rsR[i])&&!isNaN(rsM[i])) pts.push({{x:rsR[i],y:rsM[i],d:raw.dates[i]}});
    }}
    if (pts.length<2) continue;
    const color=_CLRS[sec], last=pts[pts.length-1], prev=pts[pts.length-2];
    const q=_quad(last.x,last.y);
    tbl[q].push(sec);
    pts.forEach(p=>{{allX.push(p.x);allY.push(p.y);}});

    // Tail — spline for smooth curves
    traces.push({{
      x:pts.slice(0,-1).map(p=>p.x), y:pts.slice(0,-1).map(p=>p.y),
      mode:'lines+markers',
      line:{{color,width:1.8,shape:'spline',smoothing:1.2}},
      marker:{{size:4,color,opacity:0.5}},
      hoverinfo:'skip', showlegend:false, name:sec,
    }});
    // Head dot
    traces.push({{
      x:[last.x],y:[last.y],
      mode:'markers+text',
      marker:{{size:13,color,line:{{color:'white',width:1.5}}}},
      text:[sec], textposition:'top center', textfont:{{size:10,color}},
      name:sec,
      hovertemplate:`<b>${{sec}}</b><br>${{last.d}}<br>RS-Ratio: %{{x:.2f}}<br>RS-Mom: %{{y:.2f}}<br>${{q.charAt(0).toUpperCase()+q.slice(1)}}<extra></extra>`,
    }});
    arrows.push({{x:last.x,y:last.y,ax:prev.x,ay:prev.y,xref:'x',yref:'y',axref:'x',ayref:'y',
      showarrow:true,arrowhead:3,arrowsize:1.5,arrowwidth:2,arrowcolor:color}});
  }}

  const pad=2;
  const xMin=allX.length?Math.min(...allX)-pad:90, xMax=allX.length?Math.max(...allX)+pad:110;
  const yMin=allY.length?Math.min(...allY)-pad:90, yMax=allY.length?Math.max(...allY)+pad:110;

  const layout={{
    shapes:_QSHAPES, annotations:arrows,
    xaxis:{{title:{{text:'RS-Ratio  (Relative Strength vs Benchmark)',font:{{size:11}}}},range:[xMin,xMax],zeroline:false,gridcolor:'rgba(0,0,0,0.06)'}},
    yaxis:{{title:{{text:'RS-Momentum  (Rate of Change of RS-Ratio)',font:{{size:11}}}},range:[yMin,yMax],zeroline:false,gridcolor:'rgba(0,0,0,0.06)'}},
    plot_bgcolor:'white', paper_bgcolor:'white',
    hovermode:'closest', showlegend:false,
    margin:{{l:60,r:14,t:12,b:48}},
  }};

  if (!_inited) {{
    Plotly.newPlot('rrg-chart', traces, layout, {{
      displayModeBar:true,
      modeBarButtonsToRemove:['select2d','lasso2d','autoScale2d','toggleSpikelines','hoverCompareCartesian','hoverClosestCartesian'],
      displaylogo:false, responsive:true,
    }});
    _inited=true;
    document.getElementById('rrg-loading').style.display='none';
  }} else {{
    Plotly.react('rrg-chart', traces, layout);
  }}

  // Update quadrant table
  ['leading','improving','weakening','lagging'].forEach(q=>{{
    const el=document.getElementById('rrg-qt-'+q); if(!el) return;
    const secs=tbl[q]||[];
    el.innerHTML=secs.length
      ? secs.map(s=>`<div class="rrg-qs"><div class="rrg-qdot" style="background:${{_CLRS[s]}}"></div><span>${{s}}</span></div>`).join('')
      : '<div class="rrg-qe">—</div>';
  }});
}};

// ── Public init (called when tab is opened) ───────────────────────
window.rrgInit = function() {{
  if (_ready) {{ rrgDraw(); return; }}
  if (window.Plotly) {{ _ready=true; _buildSb(); rrgDraw(); return; }}
  // Lazy-load Plotly only on first open
  const s=document.createElement('script');
  s.src='https://cdn.plot.ly/plotly-2.27.0.min.js';
  s.onload=function(){{ _ready=true; _buildSb(); rrgDraw(); }};
  document.head.appendChild(s);
}};

// Build sidebar immediately (no Plotly needed)
_buildSb();

}})();
</script>
<!-- ═══ END RRG TAB ════════════════════════════════════════════════════════ -->
"""
