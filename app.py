import streamlit as st
import requests
import json
import os
from datetime import datetime
import feedparser

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Morning Brief",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── LOAD API KEYS ─────────────────────────────────────────────────────────────
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
AV_API_KEY   = st.secrets.get("AV_API_KEY",   os.environ.get("AV_API_KEY",   ""))

TODAY = datetime.now().strftime("%A, %B %d, %Y")

# ── STYLES ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', system-ui, sans-serif !important;
    background-color: #080c12 !important;
    color: #e2e8f0 !important;
}
.stApp { background-color: #080c12 !important; }
.block-container { padding: 1.5rem 2rem !important; max-width: 980px !important; }

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* Cards */
.brief-card {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 12px;
    transition: all 0.18s;
}
.brief-card:hover {
    background: rgba(255,255,255,0.042);
    transform: translateY(-1px);
}

/* Bias pills */
.bias-bullish      { background:rgba(34,197,94,0.13);  border:1px solid rgba(34,197,94,0.4);   color:#4ade80; }
.bias-bullish-low  { background:rgba(34,197,94,0.07);  border:1px solid rgba(34,197,94,0.22);  color:#86efac; }
.bias-neutral      { background:rgba(148,163,184,0.08);border:1px solid rgba(148,163,184,0.2); color:#94a3b8; }
.bias-bearish-low  { background:rgba(251,191,36,0.08); border:1px solid rgba(251,191,36,0.28); color:#fbbf24; }
.bias-bearish      { background:rgba(239,68,68,0.11);  border:1px solid rgba(239,68,68,0.35);  color:#f87171; }

.pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #1e40af, #4f46e5) !important;
    color: #e0e7ff !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 12px 32px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    letter-spacing: 0.03em !important;
    box-shadow: 0 4px 22px rgba(79,70,229,0.25) !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 28px rgba(79,70,229,0.35) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.04) !important;
    border-radius: 8px !important;
    padding: 3px !important;
    gap: 2px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #475569 !important;
    border-radius: 6px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(255,255,255,0.1) !important;
    color: #f1f5f9 !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 16px !important; }

/* Expander */
.streamlit-expanderHeader {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 8px !important;
    color: #94a3b8 !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* Metrics */
.metric-box {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 9px;
    padding: 12px 14px;
    text-align: center;
}

hr { border-color: rgba(255,255,255,0.06) !important; }
</style>
""", unsafe_allow_html=True)


# ── ALPHA VANTAGE FETCHER ─────────────────────────────────────────────────────
@st.cache_data(ttl=300)  # cache 5 mins
def fetch_market_prices(av_key: str) -> dict:
    """Fetch live prices from Alpha Vantage."""
    prices = {}
    symbols = {
        "XAU/USD": ("FOREX_INTRADAY", {"from_symbol": "XAU", "to_symbol": "USD", "interval": "5min"}),
        "DXY":     ("FOREX_INTRADAY", {"from_symbol": "USD", "to_symbol": "EUR", "interval": "5min"}),  # proxy
        "EUR/USD": ("FOREX_INTRADAY", {"from_symbol": "EUR", "to_symbol": "USD", "interval": "5min"}),
        "WTI":     ("TIME_SERIES_INTRADAY", {"symbol": "USO", "interval": "5min"}),  # WTI ETF proxy
    }

    for name, (func, params) in symbols.items():
        try:
            url = "https://www.alphavantage.co/query"
            p = {"function": func, "apikey": av_key, **params}
            r = requests.get(url, params=p, timeout=8)
            data = r.json()

            if func == "FOREX_INTRADAY":
                ts_key = "Time Series FX (5min)"
                if ts_key in data:
                    latest = list(data[ts_key].values())[0]
                    prices[name] = {
                        "price": float(latest["4. close"]),
                        "open":  float(latest["1. open"]),
                    }
                    prices[name]["change_pct"] = round(
                        (prices[name]["price"] - prices[name]["open"]) / prices[name]["open"] * 100, 2
                    )
            elif func == "TIME_SERIES_INTRADAY":
                ts_key = "Time Series (5min)"
                if ts_key in data:
                    latest = list(data[ts_key].values())[0]
                    prices[name] = {
                        "price": float(latest["4. close"]),
                        "open":  float(latest["1. open"]),
                    }
                    prices[name]["change_pct"] = round(
                        (prices[name]["price"] - prices[name]["open"]) / prices[name]["open"] * 100, 2
                    )
        except Exception:
            prices[name] = {"price": None, "change_pct": None}

    # Fetch VIX via global quote
    try:
        r = requests.get("https://www.alphavantage.co/query", params={
            "function": "GLOBAL_QUOTE", "symbol": "^VIX", "apikey": av_key
        }, timeout=8)
        d = r.json().get("Global Quote", {})
        if d:
            prices["VIX"] = {"price": float(d.get("05. price", 0)), "change_pct": float(d.get("10. change percent", "0%").replace("%",""))}
    except Exception:
        prices["VIX"] = {"price": None, "change_pct": None}

    # Fetch indices via global quote
    for name, symbol in [("NQ", "QQQ"), ("ES", "SPY"), ("US30", "DIA")]:
        try:
            r = requests.get("https://www.alphavantage.co/query", params={
                "function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": av_key
            }, timeout=8)
            d = r.json().get("Global Quote", {})
            if d:
                prices[name] = {
                    "price": float(d.get("05. price", 0)),
                    "change_pct": float(d.get("10. change percent", "0%").replace("%",""))
                }
        except Exception:
            prices[name] = {"price": None, "change_pct": None}

    return prices


@st.cache_data(ttl=600)  # cache 10 mins
def fetch_news_rss() -> list:
    """Pull headlines from free financial RSS feeds."""
    feeds = [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.investing.com/rss/news_25.rss",
    ]
    headlines = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:4]:
                headlines.append({
                    "title": entry.get("title", "")[:100],
                    "link":  entry.get("link", ""),
                    "source": feed.feed.get("title", "News"),
                    "published": entry.get("published", "")
                })
        except Exception:
            continue
    return headlines[:12]


# ── GROQ AI ───────────────────────────────────────────────────────────────────
def call_groq(system: str, user: str, max_tokens: int = 2000) -> str:
    """Call Groq API with Llama 3.3 70B."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "llama-3.3-70b-versatile",
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user}
        ]
    }
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                      headers=headers, json=body, timeout=45)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def parse_json_safe(raw: str) -> dict:
    """Extract and parse JSON from raw text."""
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except Exception:
        # Try to extract first { ... } block
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end+1])
            except Exception:
                pass
    return {}


# ── PROMPT SYSTEMS ────────────────────────────────────────────────────────────
BRIEF_SYSTEM = f"""You are a senior macro trader with 20 years of institutional experience. Today is {TODAY}.
Write like a Bloomberg Intelligence analyst — precise, opinionated, no hedging.

ANALYTICAL FRAMEWORK — apply before assigning any bias:

1. GEOPOLITICS FIRST — check and weight first:
   - Iran/Hormuz: closed = oil UP → inflation → yields UP → real rates UP → gold BEARISH (yield channel) unless fear overrides
   - Ceasefire holding = bullish indices, bearish gold fear premium
   - Trade war escalation = stagflation risk → indices DOWN, gold UP
   - De-escalation = risk-on → indices UP, gold DOWN

2. TRANSMISSION CHAINS:
   - Oil UP → inflation → yields UP → real rates UP → gold pressure + indices DOWN + DXY UP
   - DXY UP → gold headwind
   - Yields UP → NQ most sensitive, US30 least
   - Strong data → indices UP but watch yield spike capping NQ

3. GOLD DUAL-FORCE RESOLUTION — always resolve:
   - Real yield/DXY channel vs geopolitical fear channel vs commodity rotation
   - Name which force DOMINATES today

4. CONVICTION: 65-72% = all channels aligned | 55-64% = two aligned, one opposing | 45-54% = conflicting/event risk

Bullet 1 = dominant transmission chain. Bullet 2 = evidence. Bullet 3 = key flip risk.

Return ONLY raw JSON (no markdown):
{{"risk_regime":"Risk-On"|"Risk-Off"|"Mixed","risk_rationale":"<18 words max>","institutional_sentiment":{{"overall":"Bullish"|"Cautiously Bullish"|"Neutral"|"Cautiously Bearish"|"Bearish","summary":"<2 sentences on COT/flows>","positioning":"<1 sentence>"}},"session_theme":"<22 words max>","macro_drivers":[{{"label":"<n>","detail":"<15 words>"}},{{"label":"<n>","detail":"<15 words>"}},{{"label":"<n>","detail":"<15 words>"}}],"indicators":{{"vix":{{"value":"<str>","direction":"up"|"down","note":"<5 words>"}},"dxy":{{"value":"<str>","direction":"up"|"down","note":"<5 words>"}},"yield10y":{{"value":"<str>","direction":"up"|"down","note":"<5 words>"}}}},"instruments":{{"XAU/USD":{{"bias":"Bullish"|"Bullish — low conviction"|"Neutral"|"Bearish — low conviction"|"Bearish","confidence":0,"price":"","change":"","action":"Buy"|"Sell"|"Hold","action_reason":"<12 words>","bullets":["<16 words>","<16 words>","<16 words>"]}},"NQ":{{"bias":"","confidence":0,"price":"","change":"","action":"Buy"|"Sell"|"Hold","action_reason":"","bullets":["","",""]}},"ES":{{"bias":"","confidence":0,"price":"","change":"","action":"Buy"|"Sell"|"Hold","action_reason":"","bullets":["","",""]}},"US30":{{"bias":"","confidence":0,"price":"","change":"","action":"Buy"|"Sell"|"Hold","action_reason":"","bullets":["","",""]}}}},"top_risk":"<15 words>"}}"""

OUTLOOK_SYSTEM = f"""You are a senior macro strategist. Today is {TODAY}.
Use the live data provided. Reference specific levels and events. No generic statements.

Priority order:
1. Geopolitics (Iran/Hormuz, ceasefire, trade war) — dominant driver right now
2. Transmission chain: dominant force → oil → yields → DXY → gold → indices
3. Gold net resolution: which channel wins today (yield/DXY vs fear vs rotation)
4. Indices: which is most/least exposed
5. Flip risk: single event or level that reverses everything

Return ONLY raw JSON (no markdown):
{{"headline":"<18 words — dominant force today>","chain":"<3 sentences tracing full chain with specific prices/events>","gold_resolution":"<1 sentence — which channel wins and why>","indices_view":"<1 sentence — most/least exposed>","flip_risk":"<1 sentence>","correlated_assets":[{{"asset":"WTI Crude","direction":"up"|"down"|"neutral","reason":"<10 words>"}},{{"asset":"10Y Yield","direction":"up"|"down"|"neutral","reason":"<10 words>"}},{{"asset":"DXY","direction":"up"|"down"|"neutral","reason":"<10 words>"}},{{"asset":"Brent","direction":"up"|"down"|"neutral","reason":"<10 words>"}}]}}"""

INST_SYSTEM = f"""You are a senior institutional strategist. Today is {TODAY}. Write like a Goldman Sachs positioning note.

Return ONLY raw JSON (no markdown):
{{"overview":"<2 sentences on overall institutional posture>","xauusd":"<2 sentences on gold institutional positioning — cite COT, ETF flows, bank targets>","xauusd_action":"Buy"|"Hold"|"Sell","nq":"<2 sentences on Nasdaq institutional positioning>","nq_action":"Buy"|"Hold"|"Sell","es":"<2 sentences on S&P institutional positioning>","es_action":"Buy"|"Hold"|"Sell","us30":"<2 sentences on Dow institutional positioning>","us30_action":"Buy"|"Hold"|"Sell","key_signal":"<1 sentence — most important signal today>"}}"""


# ── RENDERING HELPERS ─────────────────────────────────────────────────────────
def bias_color(bias: str) -> str:
    return {
        "Bullish":                  "#4ade80",
        "Bullish — low conviction": "#86efac",
        "Neutral":                  "#94a3b8",
        "Bearish — low conviction": "#fbbf24",
        "Bearish":                  "#f87171",
    }.get(bias, "#94a3b8")

def bias_bg(bias: str) -> str:
    return {
        "Bullish":                  "rgba(34,197,94,0.13)",
        "Bullish — low conviction": "rgba(34,197,94,0.07)",
        "Neutral":                  "rgba(148,163,184,0.08)",
        "Bearish — low conviction": "rgba(251,191,36,0.08)",
        "Bearish":                  "rgba(239,68,68,0.11)",
    }.get(bias, "rgba(148,163,184,0.08)")

def conf_color(c: int) -> str:
    return "#22c55e" if c >= 65 else "#f59e0b" if c >= 55 else "#94a3b8"

def action_html(action: str, reason: str) -> str:
    styles = {
        "Buy":  ("rgba(34,197,94,0.1)",    "rgba(34,197,94,0.3)",   "#4ade80", "↑"),
        "Sell": ("rgba(239,68,68,0.1)",    "rgba(239,68,68,0.3)",   "#f87171", "↓"),
        "Hold": ("rgba(148,163,184,0.08)", "rgba(148,163,184,0.2)", "#94a3b8", "→"),
    }.get(action, ("rgba(148,163,184,0.08)", "rgba(148,163,184,0.2)", "#94a3b8", "→"))
    bg, border, color, icon = styles
    return f"""
    <div style="background:{bg};border:1px solid {border};border-radius:7px;padding:8px 11px;
                display:flex;align-items:center;gap:8px;margin-top:8px;">
        <span style="font-size:16px;color:{color};font-weight:800;">{icon}</span>
        <div>
            <div style="font-size:10px;color:{color};font-weight:700;letter-spacing:.1em;text-transform:uppercase;">
                You should {action}</div>
            <div style="font-size:11px;color:{color};opacity:.75;margin-top:1px;">{reason}</div>
        </div>
        <div style="margin-left:auto;font-size:9px;color:#334155;font-style:italic;">based on analysis</div>
    </div>"""

def inst_action_html(action: str) -> str:
    s = {"Buy":  ("#4ade80","rgba(34,197,94,0.12)","rgba(34,197,94,0.35)"),
         "Sell": ("#f87171","rgba(239,68,68,0.12)","rgba(239,68,68,0.35)"),
         "Hold": ("#94a3b8","rgba(148,163,184,0.1)","rgba(148,163,184,0.25)")
         }.get(action, ("#94a3b8","rgba(148,163,184,0.1)","rgba(148,163,184,0.25)"))
    return f'<span style="font-size:10px;font-weight:700;padding:2px 8px;background:{s[1]};border:1px solid {s[2]};color:{s[0]};border-radius:20px;letter-spacing:.08em;text-transform:uppercase;">{action}</span>'

INST_COLORS = {"XAU/USD": "#f59e0b", "NQ": "#3b82f6", "ES": "#8b5cf6", "US30": "#10b981"}
CAT_COLORS  = {"Geopolitical":"#f87171","Macro":"#a78bfa","Earnings":"#34d399",
               "Fed":"#60a5fa","Energy":"#f59e0b","Equity":"#8b5cf6","FX":"#10b981"}


# ── RENDER OUTLOOK STRIP ──────────────────────────────────────────────────────
def render_outlook(o: dict):
    if not o:
        return
    dir_map = {"up": ("#4ade80","↑"), "down": ("#f87171","↓"), "neutral": ("#94a3b8","→")}

    corr_html = ""
    for a in (o.get("correlated_assets") or []):
        c, i = dir_map.get(a.get("direction","neutral"), ("#94a3b8","→"))
        corr_html += f"""
        <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                    border-radius:7px;padding:7px 11px;display:flex;align-items:center;gap:7px;flex:1;min-width:130px;">
            <span style="font-size:18px;color:{c};font-weight:700;">{i}</span>
            <div>
                <div style="font-size:10px;font-weight:700;color:#cbd5e1;">{a.get("asset","")}</div>
                <div style="font-size:10px;color:#475569;">{a.get("reason","")}</div>
            </div>
        </div>"""

    st.markdown(f"""
    <div style="background:rgba(15,23,42,0.9);border:1px solid rgba(255,255,255,0.09);border-radius:12px;
                padding:16px 20px;margin-bottom:14px;position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;
                    background:linear-gradient(90deg,#6366f1,#3b82f6,#10b981,transparent);"></div>
        <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">
            <div style="flex-shrink:0;width:28px;height:28px;border-radius:7px;
                        background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.3);
                        display:flex;align-items:center;justify-content:center;font-size:13px;">🔗</div>
            <div>
                <div style="font-size:10px;font-weight:700;color:#6366f1;letter-spacing:.1em;
                            text-transform:uppercase;margin-bottom:4px;">Market Transmission Chain</div>
                <div style="font-size:14px;font-weight:700;color:#f1f5f9;line-height:1.4;">{o.get("headline","")}</div>
            </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;">
            <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);
                        border-radius:8px;padding:10px 12px;">
                <div style="font-size:9px;font-weight:700;color:#475569;letter-spacing:.1em;
                            text-transform:uppercase;margin-bottom:5px;">Transmission Chain</div>
                <div style="font-size:12px;color:#94a3b8;line-height:1.65;">{o.get("chain","")}</div>
            </div>
            <div style="display:flex;flex-direction:column;gap:8px;">
                <div style="background:rgba(245,158,11,0.06);border:1px solid rgba(245,158,11,0.15);
                            border-radius:8px;padding:9px 12px;flex:1;">
                    <div style="font-size:9px;font-weight:700;color:#f59e0b;letter-spacing:.1em;
                                text-transform:uppercase;margin-bottom:4px;">Gold Net Resolution</div>
                    <div style="font-size:12px;color:#94a3b8;line-height:1.55;">{o.get("gold_resolution","")}</div>
                </div>
                <div style="background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.15);
                            border-radius:8px;padding:9px 12px;flex:1;">
                    <div style="font-size:9px;font-weight:700;color:#818cf8;letter-spacing:.1em;
                                text-transform:uppercase;margin-bottom:4px;">Indices View</div>
                    <div style="font-size:12px;color:#94a3b8;line-height:1.55;">{o.get("indices_view","")}</div>
                </div>
            </div>
        </div>
        <div style="display:flex;gap:7px;margin-bottom:10px;flex-wrap:wrap;">{corr_html}</div>
        <div style="display:flex;align-items:center;gap:8px;background:rgba(239,68,68,0.05);
                    border:1px solid rgba(239,68,68,0.14);border-radius:7px;padding:8px 12px;">
            <span style="font-size:12px;flex-shrink:0;">⚡</span>
            <div>
                <span style="font-size:9px;font-weight:700;color:#f87171;letter-spacing:.1em;
                             text-transform:uppercase;margin-right:7px;">Flip Risk</span>
                <span style="font-size:12px;color:#fca5a5;">{o.get("flip_risk","")}</span>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)


# ── RENDER ASSET CARD ─────────────────────────────────────────────────────────
def render_asset_card(inst: str, data: dict, prices: dict):
    colors = {"XAU/USD":"#f59e0b","NQ":"#3b82f6","ES":"#8b5cf6","US30":"#10b981"}
    names  = {"XAU/USD":"Gold","NQ":"Nasdaq 100","ES":"S&P 500","US30":"Dow Jones"}
    color  = colors.get(inst, "#94a3b8")
    name   = names.get(inst, inst)
    bias   = data.get("bias","Neutral")
    bc     = bias_color(bias)
    bbg    = bias_bg(bias)
    conf   = data.get("confidence", 50)
    cc     = conf_color(conf)

    # Use live price if available, else from AI
    live = prices.get(inst, {})
    price_display  = f"${live['price']:,.2f}" if live.get("price") else data.get("price","—")
    change_display = f"{live['change_pct']:+.2f}%" if live.get("change_pct") is not None else data.get("change","—")
    change_color   = "#4ade80" if (live.get("change_pct") or 0) >= 0 else "#f87171"

    bullets_html = "".join(
        f'<div style="font-size:11px;color:#94a3b8;line-height:1.6;padding:2px 0 2px 12px;position:relative;">'
        f'<span style="position:absolute;left:0;color:#334155;font-size:10px;">›</span>{b}</div>'
        for b in data.get("bullets", [])
    )

    conf_bar = f"""
    <div style="display:flex;align-items:center;gap:5px;">
        <div style="width:50px;height:3px;background:rgba(255,255,255,0.07);border-radius:2px;overflow:hidden;">
            <div style="height:100%;width:{conf}%;background:{cc};border-radius:2px;"></div>
        </div>
        <span style="font-size:11px;color:{cc};font-weight:700;font-family:'DM Mono',monospace;">{conf}%</span>
    </div>"""

    st.markdown(f"""
    <div class="brief-card" style="border-top:2px solid {color};">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
            <div>
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;">
                    <div style="width:7px;height:7px;border-radius:50%;background:{color};
                                box-shadow:0 0 5px {color};"></div>
                    <span style="font-size:13px;font-weight:700;color:#f1f5f9;letter-spacing:.04em;">{inst}</span>
                </div>
                <div style="font-size:10px;color:#475569;">{name}</div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:16px;font-weight:800;color:#f8fafc;font-family:'DM Mono',monospace;">{price_display}</div>
                <div style="font-size:11px;font-weight:600;color:{change_color};">{change_display}</div>
            </div>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
            <span style="font-size:10px;font-weight:700;padding:3px 8px;background:{bbg};
                         border:1px solid {bc}44;color:{bc};border-radius:20px;
                         letter-spacing:.07em;text-transform:uppercase;">{bias}</span>
            {conf_bar}
        </div>
        <div style="border-top:1px solid rgba(255,255,255,0.05);padding-top:8px;margin-bottom:8px;">
            {bullets_html}
        </div>
        {action_html(data.get("action","Hold"), data.get("action_reason",""))}
    </div>""", unsafe_allow_html=True)


# ── RENDER REGIME STRIP ───────────────────────────────────────────────────────
def render_regime(brief: dict):
    regime = brief.get("risk_regime","Mixed")
    rs = {
        "Risk-On":  ("#4ade80","rgba(34,197,94,0.12)","rgba(34,197,94,0.4)","▲"),
        "Risk-Off": ("#f87171","rgba(239,68,68,0.11)","rgba(239,68,68,0.38)","▼"),
        "Mixed":    ("#fbbf24","rgba(251,191,36,0.09)","rgba(251,191,36,0.3)","◆"),
    }.get(regime, ("#94a3b8","rgba(148,163,184,0.08)","rgba(148,163,184,0.2)","◆"))
    rc, rbg, rb, ri = rs

    sent  = brief.get("institutional_sentiment",{})
    so    = sent.get("overall","Neutral")
    sc    = {"Bullish":"#4ade80","Cautiously Bullish":"#86efac","Neutral":"#94a3b8",
             "Cautiously Bearish":"#fbbf24","Bearish":"#f87171"}.get(so,"#94a3b8")

    st.markdown(f"""
    <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);
                border-radius:9px;padding:11px 14px;margin-bottom:11px;">
        <div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:7px;">
            <span style="font-size:10px;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:.08em;">Regime</span>
            <span style="font-size:10px;font-weight:700;padding:2px 8px;background:{rbg};
                         border:1px solid {rb};color:{rc};border-radius:20px;letter-spacing:.07em;">{ri} {regime}</span>
            <span style="font-size:10px;color:#334155;">·</span>
            <span style="font-size:10px;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:.08em;">Institutions</span>
            <span style="font-size:10px;font-weight:700;padding:2px 8px;background:{sc}18;
                         border:1px solid {sc}44;color:{sc};border-radius:20px;letter-spacing:.07em;text-transform:uppercase;">{so}</span>
            <span style="font-size:11px;color:#475569;font-style:italic;">{brief.get("risk_rationale","")}</span>
        </div>
        <div style="font-size:12px;color:#64748b;line-height:1.6;">
            {sent.get("summary","")} <span style="color:#475569;">{sent.get("positioning","")}</span>
        </div>
    </div>""", unsafe_allow_html=True)


# ── RENDER INDICATORS ─────────────────────────────────────────────────────────
def render_indicators(indicators: dict, prices: dict):
    cols = st.columns(3)
    labels = [("vix","VIX"), ("dxy","DXY"), ("yield10y","10Y Yield")]
    for col, (key, label) in zip(cols, labels):
        ind = indicators.get(key, {})
        # Use live price for VIX
        live_val = None
        if key == "vix" and prices.get("VIX",{}).get("price"):
            live_val = f"{prices['VIX']['price']:.2f}"

        val   = live_val or ind.get("value","—")
        direc = ind.get("direction","up")
        note  = ind.get("note","")
        arrow = "↑" if direc == "up" else "↓"
        ac    = "#4ade80" if direc == "up" else "#f87171"

        with col:
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.07);
                        border-radius:9px;padding:12px 14px;display:flex;align-items:center;
                        justify-content:space-between;margin-bottom:12px;">
                <div>
                    <div style="font-size:10px;color:#475569;letter-spacing:.08em;margin-bottom:3px;">{label}</div>
                    <div style="font-size:15px;font-weight:800;color:#f1f5f9;font-family:'DM Mono',monospace;">{val}</div>
                    <div style="font-size:10px;color:#475569;margin-top:2px;">{note}</div>
                </div>
                <span style="font-size:26px;color:{ac};font-weight:700;">{arrow}</span>
            </div>""", unsafe_allow_html=True)


# ── NEWS TAB ──────────────────────────────────────────────────────────────────
def render_news(headlines: list, news_brief: dict):
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown('<div style="font-size:11px;font-weight:700;color:#475569;letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px;">Latest Headlines</div>', unsafe_allow_html=True)

        # AI-generated headlines if available
        ai_news = news_brief.get("news", [])
        items = ai_news if ai_news else [{"headline": h["title"], "summary": "", "url": h["link"],
                                           "source": h["source"], "time": "", "impact": "medium",
                                           "category": "Macro"} for h in headlines]
        for item in items[:8]:
            impact = item.get("impact","medium")
            cat    = item.get("category","Macro")
            border = "#ef4444" if impact=="high" else "#f59e0b" if impact=="medium" else "#334155"
            cat_c  = CAT_COLORS.get(cat,"#94a3b8")
            imp_bg = "rgba(239,68,68,0.12)" if impact=="high" else "rgba(251,191,36,0.1)" if impact=="medium" else "rgba(148,163,184,0.08)"
            imp_c  = "#f87171" if impact=="high" else "#fbbf24" if impact=="medium" else "#64748b"
            url    = item.get("url","")
            link   = f'<a href="{url}" target="_blank" style="font-size:10px;color:#4f46e5;text-decoration:none;">Read full article ↗</a>' if url else ""

            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
                        border-radius:9px;padding:11px 13px;margin-bottom:7px;border-left:2px solid {border};">
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;flex-wrap:wrap;">
                    <span style="font-size:10px;color:#334155;font-family:'DM Mono',monospace;">{item.get("time","")}</span>
                    <span style="font-size:9px;padding:2px 5px;background:{cat_c}20;color:{cat_c};border-radius:4px;font-weight:700;">{cat}</span>
                    <span style="font-size:9px;padding:2px 5px;background:{imp_bg};color:{imp_c};border-radius:4px;font-weight:700;text-transform:uppercase;">{impact}</span>
                    <span style="font-size:9px;color:#334155;">{item.get("source","")}</span>
                </div>
                <div style="font-size:12px;font-weight:600;color:#e2e8f0;line-height:1.5;margin-bottom:3px;">{item.get("headline","")}</div>
                <div style="font-size:11px;color:#64748b;line-height:1.5;margin-bottom:{4 if url else 0}px;">{item.get("summary","")}</div>
                {link}
            </div>""", unsafe_allow_html=True)

    with col2:
        st.markdown('<div style="font-size:11px;font-weight:700;color:#475569;letter-spacing:.1em;text-transform:uppercase;margin-bottom:3px;">Economic Calendar</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;color:#334155;margin-bottom:10px;">High-impact events only</div>', unsafe_allow_html=True)

        for ev in (news_brief.get("calendar") or []):
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(239,68,68,0.15);
                        border-left:2px solid #ef4444;border-radius:7px;padding:9px 11px;margin-bottom:5px;">
                <div style="font-size:9px;color:#ef4444;font-weight:700;margin-bottom:3px;">{ev.get("day","")} · {ev.get("time","")}</div>
                <div style="font-size:11px;font-weight:600;color:#cbd5e1;margin-bottom:3px;">{ev.get("event","")}</div>
                <div style="font-size:10px;color:#475569;">Affects: <span style="color:#64748b;">{ev.get("affects","")}</span></div>
                {f'<div style="font-size:10px;color:#475569;">Est: <span style="color:#64748b;font-family:DM Mono,monospace;">{ev["consensus"]}</span></div>' if ev.get("consensus") else ""}
            </div>""", unsafe_allow_html=True)


# ── INST DEEP DIVE ────────────────────────────────────────────────────────────
def render_inst_deep(data: dict):
    if not data:
        st.info("Generate a brief first to load institutional positioning.")
        return
    st.markdown(f'<div style="font-size:13px;color:#94a3b8;line-height:1.8;margin-bottom:16px;">{data.get("overview","")}</div>', unsafe_allow_html=True)

    for key, label in [("xauusd","XAU/USD"), ("nq","NQ"), ("es","ES"), ("us30","US30")]:
        color = INST_COLORS.get(label,"#94a3b8")
        action = data.get(f"{key}_action","Hold")
        text   = data.get(key,"")
        st.markdown(f"""
        <div style="margin-bottom:18px;padding-left:13px;border-left:2px solid {color}30;">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:5px;flex-wrap:wrap;">
                <div style="width:7px;height:7px;border-radius:50%;background:{color};box-shadow:0 0 5px {color};"></div>
                <span style="font-size:12px;font-weight:700;color:#f1f5f9;">{label}</span>
                {inst_action_html(action)}
            </div>
            <p style="font-size:13px;color:#94a3b8;line-height:1.75;margin:0;">{text}</p>
        </div>""", unsafe_allow_html=True)

    if data.get("key_signal"):
        st.markdown(f"""
        <div style="background:rgba(167,139,250,0.07);border:1px solid rgba(167,139,250,0.2);
                    border-radius:8px;padding:10px 13px;margin-top:4px;">
            <div style="font-size:10px;font-weight:700;color:#a78bfa;text-transform:uppercase;
                        letter-spacing:.1em;margin-bottom:4px;">Key Signal</div>
            <p style="font-size:13px;color:#c4b5fd;line-height:1.65;margin:0;">{data["key_signal"]}</p>
        </div>""", unsafe_allow_html=True)


# ── MAIN APP ──────────────────────────────────────────────────────────────────
def main():
    # Header
    now = datetime.now().strftime("%a %b %d, %Y · %I:%M %p")
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;
                padding-bottom:14px;margin-bottom:20px;border-bottom:1px solid rgba(255,255,255,0.05);">
        <div style="display:flex;align-items:center;gap:10px;">
            <div style="width:30px;height:30px;border-radius:9px;
                        background:linear-gradient(135deg,#1e40af,#6d28d9);
                        display:flex;align-items:center;justify-content:center;
                        font-size:14px;font-weight:800;color:white;">J</div>
            <div>
                <div style="font-size:14px;font-weight:700;color:#f1f5f9;">Morning Brief</div>
                <div style="font-size:10px;color:#334155;letter-spacing:.06em;">{now}</div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    # API key check
    if not GROQ_API_KEY:
        st.error("⚠ GROQ_API_KEY not set. Add it to `.streamlit/secrets.toml` or your Streamlit Cloud secrets.")
        st.code('GROQ_API_KEY = "gsk_..."\nAV_API_KEY = "your_key"', language="toml")
        st.stop()

    # Session state
    for k in ["brief","outlook","inst_deep","news_brief","prices","headlines","generated"]:
        if k not in st.session_state:
            st.session_state[k] = None
    if "generated" not in st.session_state:
        st.session_state.generated = False

    # Generate button
    tab_brief, tab_news, tab_inst = st.tabs(["📊 Brief", "📰 News", "🏦 Institutions"])

    with tab_brief:
        if not st.session_state.generated:
            st.markdown("""
            <div style="text-align:center;padding:48px 0 32px;">
                <div style="width:54px;height:54px;border-radius:16px;margin:0 auto 20px;
                            background:linear-gradient(135deg,#1e3a5f,#1e40af);
                            border:1px solid rgba(59,130,246,0.3);
                            display:flex;align-items:center;justify-content:center;
                            font-size:22px;box-shadow:0 0 28px rgba(59,130,246,0.15);">⚡</div>
                <div style="font-size:19px;font-weight:700;color:#f1f5f9;margin-bottom:8px;">Ready for your brief</div>
                <div style="font-size:13px;color:#475569;line-height:1.6;max-width:340px;margin:0 auto 28px;">
                    Pulls live prices via Alpha Vantage, fetches news headlines, then generates
                    a full institutional-grade analysis via Groq AI.
                </div>
            </div>""", unsafe_allow_html=True)

        col_btn, col_spacer = st.columns([1,3])
        with col_btn:
            if st.button("⚡ Generate Morning Brief", use_container_width=True):
                with st.spinner(""):
                    progress = st.empty()

                    progress.markdown('<div style="font-size:11px;color:#64748b;letter-spacing:.1em;text-transform:uppercase;">Fetching live prices...</div>', unsafe_allow_html=True)
                    if AV_API_KEY:
                        st.session_state.prices = fetch_market_prices(AV_API_KEY)
                    else:
                        st.session_state.prices = {}

                    progress.markdown('<div style="font-size:11px;color:#64748b;letter-spacing:.1em;text-transform:uppercase;">Fetching news headlines...</div>', unsafe_allow_html=True)
                    st.session_state.headlines = fetch_news_rss()

                    # Build market context for AI
                    prices = st.session_state.prices
                    price_ctx = "\n".join([
                        f"{k}: ${v['price']:.2f} ({v['change_pct']:+.2f}%)" if v.get("price") else f"{k}: N/A"
                        for k,v in prices.items()
                    ])
                    news_ctx = "\n".join([f"- {h['title']} ({h['source']})" for h in (st.session_state.headlines or [])])
                    market_data = f"LIVE PRICES:\n{price_ctx}\n\nRECENT HEADLINES:\n{news_ctx}"

                    progress.markdown('<div style="font-size:11px;color:#64748b;letter-spacing:.1em;text-transform:uppercase;">Generating brief (1/3)...</div>', unsafe_allow_html=True)
                    raw_brief = call_groq(BRIEF_SYSTEM, f"Market data:\n\n{market_data}\n\nGenerate the JSON brief now.", 2400)
                    st.session_state.brief = parse_json_safe(raw_brief)

                    progress.markdown('<div style="font-size:11px;color:#64748b;letter-spacing:.1em;text-transform:uppercase;">Generating outlook (2/3)...</div>', unsafe_allow_html=True)
                    raw_outlook = call_groq(OUTLOOK_SYSTEM, f"Market data:\n\n{market_data}\n\nWrite the outlook JSON.", 1600)
                    st.session_state.outlook = parse_json_safe(raw_outlook)

                    progress.markdown('<div style="font-size:11px;color:#64748b;letter-spacing:.1em;text-transform:uppercase;">Generating news brief (3/3)...</div>', unsafe_allow_html=True)
                    NEWS_SYS = f"""You are a financial news aggregator. Today is {TODAY}.
Return ONLY raw JSON:
{{"news":[{{"time":"<HH:MM ET>","headline":"<12 words>","summary":"<1 sentence>","url":"<url>","source":"<source>","impact":"high"|"medium"|"low","category":"Geopolitical"|"Macro"|"Earnings"|"Fed"|"Energy"|"Equity"|"FX"}}],"calendar":[{{"day":"<Mon-Fri>","time":"<HH:MM ET>","event":"<name>","affects":"<assets>","consensus":"<value>"}}]}}"""
                    raw_news = call_groq(NEWS_SYS, f"Headlines:\n{news_ctx}\n\nConvert to JSON. Include high-impact calendar events for XAU/USD, NQ, ES, US30 this week.", 2000)
                    st.session_state.news_brief = parse_json_safe(raw_news)

                    progress.empty()
                    st.session_state.generated = True
                    st.rerun()

        if st.session_state.generated and st.session_state.brief:
            brief   = st.session_state.brief
            outlook = st.session_state.outlook or {}
            prices  = st.session_state.prices or {}

            # Transmission chain outlook
            render_outlook(outlook)

            # Session theme
            st.markdown(f"""
            <div style="background:rgba(79,70,229,0.07);border:1px solid rgba(79,70,229,0.18);
                        border-radius:9px;padding:11px 16px;margin-bottom:9px;">
                <span style="font-size:10px;color:#6366f1;font-weight:700;letter-spacing:.1em;
                             text-transform:uppercase;margin-right:9px;">Session Theme</span>
                <span style="font-size:13px;color:#a5b4fc;">{brief.get("session_theme","")}</span>
            </div>""", unsafe_allow_html=True)

            # Macro drivers
            drivers = brief.get("macro_drivers", [])
            if drivers:
                cols = st.columns(3)
                for i, d in enumerate(drivers[:3]):
                    with cols[i]:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
                                    border-radius:7px;padding:9px 12px;margin-bottom:12px;">
                            <div style="font-size:10px;font-weight:700;color:#6366f1;letter-spacing:.08em;
                                        text-transform:uppercase;margin-bottom:3px;">{d.get("label","")}</div>
                            <div style="font-size:11px;color:#94a3b8;line-height:1.5;">{d.get("detail","")}</div>
                        </div>""", unsafe_allow_html=True)

            # Asset cards (2x2 grid)
            instruments = brief.get("instruments", {})
            col1, col2 = st.columns(2)
            for i, inst in enumerate(["XAU/USD","NQ","ES","US30"]):
                data = instruments.get(inst, {})
                if not data:
                    continue
                with (col1 if i % 2 == 0 else col2):
                    render_asset_card(inst, data, prices)

            # Regime + institutions
            render_regime(brief)

            # Indicators
            render_indicators(brief.get("indicators",{}), prices)

            # Top risk
            if brief.get("top_risk"):
                st.markdown(f"""
                <div style="background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.18);
                            border-radius:9px;padding:9px 14px;font-size:12px;color:#fca5a5;
                            display:flex;align-items:center;gap:9px;margin-bottom:16px;">
                    <span>🎯</span>
                    <span><strong style="color:#f87171;">Top risk — </strong>{brief["top_risk"]}</span>
                </div>""", unsafe_allow_html=True)

            col_r, _ = st.columns([1,4])
            with col_r:
                if st.button("↺ Refresh brief"):
                    st.session_state.generated = False
                    st.rerun()

            st.markdown('<div style="text-align:center;font-size:10px;color:#1e293b;letter-spacing:.06em;margin-top:8px;">NOT FINANCIAL ADVICE · POWERED BY GROQ + ALPHA VANTAGE</div>', unsafe_allow_html=True)

    with tab_news:
        if not st.session_state.generated:
            st.info("Generate a brief first to load news.")
        else:
            render_news(st.session_state.headlines or [], st.session_state.news_brief or {})

    with tab_inst:
        if not st.session_state.generated:
            st.info("Generate a brief first to load institutional positioning.")
        else:
            st.markdown("""
            <div style="margin-bottom:16px;">
                <div style="font-size:17px;font-weight:800;color:#f8fafc;margin-bottom:3px;">Institutional Positioning</div>
                <div style="font-size:12px;color:#475569;">How smart money is positioned across your assets</div>
            </div>""", unsafe_allow_html=True)

            if not st.session_state.inst_deep:
                if st.button("Load Positioning Deep Dive →"):
                    with st.spinner("Generating institutional analysis..."):
                        brief = st.session_state.brief or {}
                        prices = st.session_state.prices or {}
                        price_ctx = "\n".join([f"{k}: ${v['price']:.2f}" if v.get("price") else f"{k}: N/A" for k,v in prices.items()])
                        raw = call_groq(INST_SYSTEM,
                            f"Institutional sentiment: {json.dumps(brief.get('institutional_sentiment',{}))}\n\nPrices:\n{price_ctx}\n\nWrite the institutional deep-dive JSON.", 1800)
                        st.session_state.inst_deep = parse_json_safe(raw)
                        st.rerun()
            else:
                render_inst_deep(st.session_state.inst_deep)

            st.markdown('<div style="font-size:10px;color:#1e293b;text-align:center;margin-top:16px;letter-spacing:.08em;text-transform:uppercase;">Not financial advice</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
