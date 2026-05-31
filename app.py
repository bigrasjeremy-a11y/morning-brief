import streamlit as st
import requests
import json
import os
import time
from datetime import datetime
import feedparser

st.set_page_config(page_title="Morning Brief — Jacob", page_icon="📊", layout="centered", initial_sidebar_state="collapsed")

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
AV_API_KEY   = st.secrets.get("AV_API_KEY",   os.environ.get("AV_API_KEY",   ""))
TODAY        = datetime.now().strftime("%A, %B %d, %Y")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');
html,body,[class*="css"],.stApp{font-family:'DM Sans',system-ui,sans-serif!important;background-color:#080c12!important;color:#e2e8f0!important}
.stApp{background-color:#080c12!important}
.block-container{max-width:960px!important;padding:0 24px 48px 24px!important;margin:0 auto!important}
#MainMenu,footer,header,.stDeployButton{visibility:hidden!important;display:none!important}

/* TABS — full width, evenly spaced */
.stTabs{width:100%!important}
.stTabs [data-baseweb="tab-list"]{
  background:rgba(255,255,255,0.04)!important;
  border-radius:9px!important;padding:4px!important;
  display:flex!important;width:100%!important;gap:4px!important;
}
.stTabs [data-baseweb="tab"]{
  background:transparent!important;color:#475569!important;border-radius:6px!important;
  font-family:'DM Sans',sans-serif!important;font-weight:600!important;font-size:12px!important;
  border:none!important;flex:1!important;text-align:center!important;padding:8px 0!important;
}
.stTabs [aria-selected="true"]{background:rgba(255,255,255,0.1)!important;color:#f1f5f9!important;}
.stTabs [data-baseweb="tab-panel"]{padding-top:18px!important;}

/* Buttons */
.stButton>button{
  background:linear-gradient(135deg,#1e40af,#4f46e5)!important;color:#e0e7ff!important;
  border:none!important;border-radius:10px!important;padding:13px 38px!important;
  font-family:'DM Sans',sans-serif!important;font-weight:700!important;font-size:13px!important;
  letter-spacing:.03em!important;box-shadow:0 4px 22px rgba(79,70,229,.25)!important;
  transition:all .2s!important;
}
.stButton>button:hover{box-shadow:0 6px 28px rgba(79,70,229,.38)!important;transform:translateY(-1px)!important;}

.stSpinner>div{border-top-color:#4f46e5!important;}
::-webkit-scrollbar{width:4px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:#1e293b;border-radius:2px}
hr{border-color:rgba(255,255,255,.06)!important;margin:16px 0!important}
.streamlit-expanderHeader{background:rgba(255,255,255,.02)!important;border:1px solid rgba(255,255,255,.08)!important;border-radius:10px!important;color:#94a3b8!important;font-family:'DM Sans',sans-serif!important;}
.streamlit-expanderContent{background:rgba(255,255,255,.015)!important;border:1px solid rgba(255,255,255,.06)!important;border-top:none!important;border-radius:0 0 10px 10px!important;}
</style>
""", unsafe_allow_html=True)

# ── GROQ ──────────────────────────────────────────────────────────────────────
def call_groq(system, user, max_tokens=2000):
    if not GROQ_API_KEY:
        st.error("GROQ_API_KEY missing — go to Manage App → Secrets.")
        st.stop()
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    for model in ["llama-3.3-70b-versatile","llama3-70b-8192","llama3-8b-8192"]:
        body = {"model":model,"max_tokens":min(max_tokens,4096),"temperature":0.3,
                "messages":[{"role":"system","content":system},{"role":"user","content":user[:6000]}]}
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",headers=headers,json=body,timeout=60)
            if r.status_code==200: return r.json()["choices"][0]["message"]["content"].strip()
            if r.status_code==429:
                time.sleep(5)
                r2 = requests.post("https://api.groq.com/openai/v1/chat/completions",headers=headers,json=body,timeout=60)
                if r2.status_code==200: return r2.json()["choices"][0]["message"]["content"].strip()
                st.error("Rate limit — wait 30s and try again."); st.stop()
            if r.status_code==401: st.error("Groq key invalid — check it starts with 'gsk_'."); st.stop()
            if r.status_code in (400,413): continue
            st.error(f"Groq {r.status_code}: {r.text[:200]}"); st.stop()
        except requests.exceptions.Timeout: st.error("Groq timed out — try again."); st.stop()
        except Exception as e: st.error(f"Error: {e}"); st.stop()
    st.error("All Groq models failed."); st.stop()

def parse_json(raw):
    raw = raw.replace("```json","").replace("```","").strip()
    try: return json.loads(raw)
    except:
        s,e = raw.find("{"),raw.rfind("}")
        if s!=-1 and e>s:
            try: return json.loads(raw[s:e+1])
            except: pass
    return {}

# ── ALPHA VANTAGE ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_prices(av_key):
    p = {}
    if not av_key: return p
    for name,sym in [("NQ","QQQ"),("ES","SPY"),("US30","DIA"),("VIX","^VIX")]:
        try:
            r = requests.get("https://www.alphavantage.co/query",params={"function":"GLOBAL_QUOTE","symbol":sym,"apikey":av_key},timeout=8)
            d = r.json().get("Global Quote",{})
            if d.get("05. price"):
                p[name]={"price":float(d["05. price"]),"change_pct":float(d.get("10. change percent","0%").replace("%",""))}
        except: pass
    try:
        r = requests.get("https://www.alphavantage.co/query",params={"function":"CURRENCY_EXCHANGE_RATE","from_currency":"XAU","to_currency":"USD","apikey":av_key},timeout=8)
        rate = r.json().get("Realtime Currency Exchange Rate",{})
        if rate.get("5. Exchange Rate"): p["XAU/USD"]={"price":float(rate["5. Exchange Rate"]),"change_pct":None}
    except: pass
    return p

@st.cache_data(ttl=600)
def fetch_headlines():
    out=[]
    for url in ["https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US","https://www.cnbc.com/id/100003114/device/rss/rss.html","https://feeds.reuters.com/reuters/businessNews"]:
        try:
            feed=feedparser.parse(url)
            for e in feed.entries[:4]: out.append({"title":e.get("title","")[:100],"link":e.get("link",""),"source":feed.feed.get("title","")})
        except: pass
    return out[:12]

# ── PROMPTS ───────────────────────────────────────────────────────────────────
BRIEF_SYS = f"""You are a senior macro trader. Today is {TODAY}. Write like Bloomberg Intelligence — precise, opinionated.

FRAMEWORK:
1. GEOPOLITICS FIRST: Iran/Hormuz, ceasefire, trade war — dominant driver right now
2. TRANSMISSION: Oil UP→inflation→yields UP→DXY UP→gold pressure+indices DOWN
3. GOLD: resolve real yield/DXY channel vs geopolitical fear channel — name which wins
4. CONVICTION: 65-72%=aligned | 55-64%=mixed | 45-54%=conflicting

For each instrument include:
- bias_summary: 1 sentence plain English summary of why the bias is what it is (shown on main card)
- edge_factor: 1-10 score representing overall edge/conviction for a trade today
- edge_label: "Strong Edge" / "Moderate Edge" / "Low Edge" / "Wait"
- event_risk: "High" / "Medium" / "Low" — binary event risk today
- flow_direction: "Institutional Buying" / "Institutional Selling" / "Neutral Flows" / "Mixed Flows"
- session_relevance: "High" / "Medium" / "Low" — how relevant is this instrument to today's session

Return ONLY raw JSON no markdown:
{{"risk_regime":"Risk-On/Risk-Off/Mixed","risk_rationale":"<18 words>",
"macro_tone":"Hawkish/Dovish/Neutral/Risk-On/Risk-Off/Stagflation",
"session_context":{{"phase":"Pre-Market/London/NY Open/NY Afternoon/Overlap","london_bias":"Bullish/Bearish/Neutral","ny_bias":"Bullish/Bearish/Neutral","key_session_note":"<12 words>"}},
"currency_strength":{{"usd":"Strong/Weak/Neutral","gold_flow":"Into Gold/Out of Gold/Neutral","risk_appetite":"High/Low/Neutral"}},
"institutional_sentiment":{{"overall":"Bullish/Cautiously Bullish/Neutral/Cautiously Bearish/Bearish","summary":"<2 sentences>","positioning":"<1 sentence>","capital_flow":"<1 sentence on where institutional money is flowing today>"}},"session_theme":"<20 words>","macro_drivers":[{{"label":"<n>","detail":"<12 words>"}},{{"label":"<n>","detail":"<12 words>"}},{{"label":"<n>","detail":"<12 words>"}}],
"indicators":{{"vix":{{"value":"<str>","direction":"up/down","note":"<5 words>"}},"dxy":{{"value":"<str>","direction":"up/down","note":"<5 words>"}},"yield10y":{{"value":"<str>","direction":"up/down","note":"<5 words>"}}}},"instruments":{{"XAU/USD":{{"bias":"Bullish/Bullish — low conviction/Neutral/Bearish — low conviction/Bearish","confidence":55,"price":"","change":"","action":"Buy/Sell/Hold","action_reason":"<10 words>","bias_summary":"<1 sentence plain English>","edge_factor":7,"edge_label":"Moderate Edge","event_risk":"Medium","flow_direction":"Neutral Flows","session_relevance":"High","bullets":["<14 words>","<14 words>","<14 words>"]}},"NQ":{{"bias":"Neutral","confidence":50,"price":"","change":"","action":"Hold","action_reason":"","bias_summary":"","edge_factor":5,"edge_label":"Low Edge","event_risk":"Low","flow_direction":"Neutral Flows","session_relevance":"Medium","bullets":["","",""]}},"ES":{{"bias":"Neutral","confidence":50,"price":"","change":"","action":"Hold","action_reason":"","bias_summary":"","edge_factor":5,"edge_label":"Low Edge","event_risk":"Low","flow_direction":"Neutral Flows","session_relevance":"Medium","bullets":["","",""]}},"US30":{{"bias":"Neutral","confidence":50,"price":"","change":"","action":"Hold","action_reason":"","bias_summary":"","edge_factor":5,"edge_label":"Low Edge","event_risk":"Low","flow_direction":"Neutral Flows","session_relevance":"Medium","bullets":["","",""]}}}},"top_risk":"<12 words>"}}"""

OUTLOOK_SYS = f"""You are a senior macro strategist. Today is {TODAY}. Use live data. Reference specific prices and events.
Return ONLY raw JSON no markdown:
{{"headline":"<18 words>","chain":"<3 sentences with specific prices/events>","gold_resolution":"<1 sentence which channel wins>","indices_view":"<1 sentence most/least exposed>","flip_risk":"<1 sentence>","correlated_assets":[{{"asset":"WTI Crude","direction":"up/down/neutral","reason":"<8 words>"}},{{"asset":"10Y Yield","direction":"up/down/neutral","reason":"<8 words>"}},{{"asset":"DXY","direction":"up/down/neutral","reason":"<8 words>"}},{{"asset":"Brent","direction":"up/down/neutral","reason":"<8 words>"}}]}}"""

DEEP_SYS = f"""You are a senior macro strategist. Today is {TODAY}. Write like a JPMorgan morning note — full paragraphs, authoritative, specific prices and levels.
Return ONLY raw JSON no markdown:
{{"fundamental_overview":"<3 sentences — dominant transmission chain with specific prices>","macro_correlations":"<3 sentences — DXY/gold, yields/NQ, oil/indices relationships today>","key_drivers":"<3 sentences — structural driver vs binary event risk, specific catalysts>","risk_scenario":"<3 sentences — what price level or event invalidates the bias>","trade_context":"<2 sentences — how to position, key levels to watch>","session_notes":"<2 sentences — London vs NY session dynamics for this instrument today>"}}"""

INST_SYS = f"""You are a Goldman Sachs institutional strategist. Today is {TODAY}. Full paragraphs, specific evidence.
Return ONLY raw JSON no markdown:
{{"overview":"<3 sentences on overall institutional posture>","xauusd":"<3 sentences — COT data, ETF flows, bank targets>","xauusd_action":"Buy/Hold/Sell","nq":"<3 sentences — tech fund flows, options positioning>","nq_action":"Buy/Hold/Sell","es":"<3 sentences — net futures, ETF flows, key levels>","es_action":"Buy/Hold/Sell","us30":"<3 sentences — rotation signals, sector flows>","us30_action":"Buy/Hold/Sell","key_signal":"<2 sentences — most important signal and what to do>"}}"""

NEWS_SYS = f"""Financial news aggregator. Today is {TODAY}.
Return ONLY raw JSON no markdown:
{{"news":[{{"time":"<HH:MM ET>","headline":"<10 words>","summary":"<1 sentence>","url":"<url>","source":"<source>","impact":"high/medium/low","category":"Geopolitical/Macro/Earnings/Fed/Energy/Equity/FX"}}],"calendar":[{{"day":"<Mon-Fri>","time":"<HH:MM ET>","event":"<name>","affects":"<assets>","consensus":"<value>"}}]}}"""

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
BIAS_C  = {"Bullish":"#22c55e","Bullish — low conviction":"#86efac","Neutral":"#94a3b8","Bearish — low conviction":"#fbbf24","Bearish":"#ef4444"}
BIAS_BG = {"Bullish":"rgba(34,197,94,0.13)","Bullish — low conviction":"rgba(34,197,94,0.07)","Neutral":"rgba(148,163,184,0.08)","Bearish — low conviction":"rgba(251,191,36,0.08)","Bearish":"rgba(239,68,68,0.11)"}
# Card border: green for bullish variants, red for bearish, grey for neutral
CARD_BORDER = {"Bullish":"rgba(34,197,94,0.55)","Bullish — low conviction":"rgba(34,197,94,0.3)","Neutral":"rgba(255,255,255,0.08)","Bearish — low conviction":"rgba(251,191,36,0.4)","Bearish":"rgba(239,68,68,0.55)"}
META    = {"XAU/USD":("Gold","#f59e0b"),"NQ":("Nasdaq 100","#3b82f6"),"ES":("S&P 500","#8b5cf6"),"US30":("Dow Jones","#10b981")}
SENT_C  = {"Bullish":"#4ade80","Cautiously Bullish":"#86efac","Neutral":"#94a3b8","Cautiously Bearish":"#fbbf24","Bearish":"#f87171"}
RS      = {"Risk-On":("#4ade80","rgba(34,197,94,.12)","rgba(34,197,94,.4)","▲"),"Risk-Off":("#f87171","rgba(239,68,68,.11)","rgba(239,68,68,.38)","▼"),"Mixed":("#fbbf24","rgba(251,191,36,.09)","rgba(251,191,36,.3)","◆")}
CAT_C   = {"Geopolitical":"#f87171","Macro":"#a78bfa","Earnings":"#34d399","Fed":"#60a5fa","Energy":"#f59e0b","Equity":"#8b5cf6","FX":"#10b981"}
INST_C  = {"XAU/USD":"#f59e0b","NQ":"#3b82f6","ES":"#8b5cf6","US30":"#10b981"}
conf_c  = lambda c: "#22c55e" if c>=65 else "#f59e0b" if c>=55 else "#94a3b8"

FLOW_STYLE = {
    "Institutional Buying": ("#4ade80","rgba(34,197,94,.1)","↑"),
    "Institutional Selling":("#f87171","rgba(239,68,68,.1)","↓"),
    "Neutral Flows":        ("#94a3b8","rgba(148,163,184,.08)","→"),
    "Mixed Flows":          ("#fbbf24","rgba(251,191,36,.08)","⇄"),
}
EDGE_STYLE = {
    "Strong Edge":  ("#4ade80","rgba(34,197,94,.12)"),
    "Moderate Edge":("#f59e0b","rgba(245,158,11,.1)"),
    "Low Edge":     ("#94a3b8","rgba(148,163,184,.08)"),
    "Wait":         ("#f87171","rgba(239,68,68,.1)"),
}
RISK_STYLE = {
    "High":  ("#f87171","rgba(239,68,68,.1)"),
    "Medium":("#fbbf24","rgba(251,191,36,.08)"),
    "Low":   ("#94a3b8","rgba(148,163,184,.07)"),
}

def action_html(action, reason):
    s = {"Buy":("rgba(34,197,94,.1)","rgba(34,197,94,.3)","#4ade80","↑"),
         "Sell":("rgba(239,68,68,.1)","rgba(239,68,68,.3)","#f87171","↓"),
         "Hold":("rgba(148,163,184,.08)","rgba(148,163,184,.2)","#94a3b8","→")}.get(action,("rgba(148,163,184,.08)","rgba(148,163,184,.2)","#94a3b8","→"))
    return f'<div style="background:{s[0]};border:1px solid {s[1]};border-radius:7px;padding:8px 11px;display:flex;align-items:center;gap:8px;margin-top:8px;"><span style="font-size:16px;color:{s[2]};font-weight:800;">{s[3]}</span><div><div style="font-size:10px;color:{s[2]};font-weight:700;letter-spacing:.1em;text-transform:uppercase;">You should {action}</div><div style="font-size:11px;color:{s[2]};opacity:.75;margin-top:1px;">{reason}</div></div><div style="margin-left:auto;font-size:9px;color:#334155;font-style:italic;">based on analysis</div></div>'

def inst_pill(action):
    s = {"Buy":("#4ade80","rgba(34,197,94,.12)","rgba(34,197,94,.35)"),"Sell":("#f87171","rgba(239,68,68,.12)","rgba(239,68,68,.35)"),"Hold":("#94a3b8","rgba(148,163,184,.1)","rgba(148,163,184,.25)")}.get(action,("#94a3b8","rgba(148,163,184,.1)","rgba(148,163,184,.25)"))
    return f'<span style="font-size:10px;font-weight:700;padding:2px 8px;background:{s[1]};border:1px solid {s[2]};color:{s[0]};border-radius:20px;letter-spacing:.08em;text-transform:uppercase;">{action}</span>'

# ── RENDER: SESSION CONTEXT BAR ───────────────────────────────────────────────
def render_session_bar(brief):
    sc   = brief.get("session_context",{})
    ct   = brief.get("currency_strength",{})
    tone = brief.get("macro_tone","Neutral")
    tone_c = {"Hawkish":"#f87171","Dovish":"#4ade80","Risk-On":"#4ade80","Risk-Off":"#f87171","Stagflation":"#fbbf24","Neutral":"#94a3b8"}.get(tone,"#94a3b8")

    phase   = sc.get("phase","NY Open")
    l_bias  = sc.get("london_bias","Neutral")
    ny_bias = sc.get("ny_bias","Neutral")
    note    = sc.get("key_session_note","")
    usd     = ct.get("usd","Neutral")
    gflow   = ct.get("gold_flow","Neutral")
    risk_ap = ct.get("risk_appetite","Neutral")
    usd_c   = "#f87171" if usd=="Strong" else "#4ade80" if usd=="Weak" else "#94a3b8"
    gflow_c = "#f87171" if "Out" in gflow else "#4ade80" if "Into" in gflow else "#94a3b8"
    risk_c  = "#4ade80" if risk_ap=="High" else "#f87171" if risk_ap=="Low" else "#94a3b8"

    st.markdown(f"""
    <div style="background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.06);border-radius:9px;
        padding:10px 16px;margin-bottom:12px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
        <div style="display:flex;align-items:center;gap:6px;">
            <div style="width:6px;height:6px;border-radius:50%;background:#4ade80;box-shadow:0 0 6px #4ade80;animation:pulse 2s infinite;"></div>
            <span style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.08em;">{phase}</span>
        </div>
        <div style="width:1px;height:14px;background:rgba(255,255,255,.08);"></div>
        <div style="display:flex;align-items:center;gap:5px;">
            <span style="font-size:10px;color:#475569;">Macro Tone</span>
            <span style="font-size:10px;font-weight:700;color:{tone_c};">{tone}</span>
        </div>
        <div style="width:1px;height:14px;background:rgba(255,255,255,.08);"></div>
        <div style="display:flex;align-items:center;gap:5px;">
            <span style="font-size:10px;color:#475569;">London</span>
            <span style="font-size:10px;font-weight:700;color:{"#4ade80" if l_bias=="Bullish" else "#f87171" if l_bias=="Bearish" else "#94a3b8"};">{l_bias}</span>
        </div>
        <div style="display:flex;align-items:center;gap:5px;">
            <span style="font-size:10px;color:#475569;">NY</span>
            <span style="font-size:10px;font-weight:700;color:{"#4ade80" if ny_bias=="Bullish" else "#f87171" if ny_bias=="Bearish" else "#94a3b8"};">{ny_bias}</span>
        </div>
        <div style="width:1px;height:14px;background:rgba(255,255,255,.08);"></div>
        <div style="display:flex;align-items:center;gap:5px;">
            <span style="font-size:10px;color:#475569;">USD</span>
            <span style="font-size:10px;font-weight:700;color:{usd_c};">{usd}</span>
        </div>
        <div style="display:flex;align-items:center;gap:5px;">
            <span style="font-size:10px;color:#475569;">Gold Flow</span>
            <span style="font-size:10px;font-weight:700;color:{gflow_c};">{gflow}</span>
        </div>
        <div style="display:flex;align-items:center;gap:5px;">
            <span style="font-size:10px;color:#475569;">Risk Appetite</span>
            <span style="font-size:10px;font-weight:700;color:{risk_c};">{risk_ap}</span>
        </div>
        {f'<div style="margin-left:auto;font-size:10px;color:#475569;font-style:italic;">{note}</div>' if note else ''}
    </div>
    <style>@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}</style>
    """, unsafe_allow_html=True)

# ── RENDER: OUTLOOK STRIP ─────────────────────────────────────────────────────
def render_outlook(o):
    if not o: return
    DIR = {"up":("#4ade80","↑"),"down":("#f87171","↓"),"neutral":("#94a3b8","→")}
    corr = ""
    for a in (o.get("correlated_assets") or []):
        dc,di = DIR.get(a.get("direction","neutral"),("#94a3b8","→"))
        corr += f'<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:7px;padding:7px 11px;display:flex;align-items:center;gap:7px;flex:1;min-width:120px;"><span style="font-size:18px;color:{dc};font-weight:700;">{di}</span><div><div style="font-size:10px;font-weight:700;color:#cbd5e1;">{a.get("asset","")}</div><div style="font-size:10px;color:#475569;">{a.get("reason","")}</div></div></div>'
    st.markdown(f"""
    <div style="background:rgba(15,23,42,.9);border:1px solid rgba(255,255,255,.09);border-radius:12px;padding:16px 20px;margin-bottom:14px;position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,#6366f1,#3b82f6,#10b981,transparent);"></div>
        <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">
            <div style="flex-shrink:0;width:28px;height:28px;border-radius:7px;background:rgba(99,102,241,.15);border:1px solid rgba(99,102,241,.3);display:flex;align-items:center;justify-content:center;font-size:13px;">🔗</div>
            <div><div style="font-size:10px;font-weight:700;color:#6366f1;letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px;">Market Transmission Chain</div>
            <div style="font-size:14px;font-weight:700;color:#f1f5f9;line-height:1.4;">{o.get("headline","")}</div></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;">
            <div style="background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.05);border-radius:8px;padding:10px 12px;">
                <div style="font-size:9px;font-weight:700;color:#475569;letter-spacing:.1em;text-transform:uppercase;margin-bottom:5px;">Transmission Chain</div>
                <div style="font-size:12px;color:#94a3b8;line-height:1.65;">{o.get("chain","")}</div>
            </div>
            <div style="display:flex;flex-direction:column;gap:8px;">
                <div style="background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.15);border-radius:8px;padding:9px 12px;flex:1;">
                    <div style="font-size:9px;font-weight:700;color:#f59e0b;letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px;">Gold Net Resolution</div>
                    <div style="font-size:12px;color:#94a3b8;line-height:1.55;">{o.get("gold_resolution","")}</div>
                </div>
                <div style="background:rgba(99,102,241,.06);border:1px solid rgba(99,102,241,.15);border-radius:8px;padding:9px 12px;flex:1;">
                    <div style="font-size:9px;font-weight:700;color:#818cf8;letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px;">Indices View</div>
                    <div style="font-size:12px;color:#94a3b8;line-height:1.55;">{o.get("indices_view","")}</div>
                </div>
            </div>
        </div>
        <div style="display:flex;gap:7px;margin-bottom:10px;flex-wrap:wrap;">{corr}</div>
        <div style="display:flex;align-items:center;gap:8px;background:rgba(239,68,68,.05);border:1px solid rgba(239,68,68,.14);border-radius:7px;padding:8px 12px;">
            <span style="font-size:12px;">⚡</span>
            <div><span style="font-size:9px;font-weight:700;color:#f87171;letter-spacing:.1em;text-transform:uppercase;margin-right:7px;">Flip Risk</span>
            <span style="font-size:12px;color:#fca5a5;">{o.get("flip_risk","")}</span></div>
        </div>
    </div>""", unsafe_allow_html=True)

# ── RENDER: ASSET CARD ────────────────────────────────────────────────────────
def render_card(inst, data, prices, expanded_inst):
    name,color = META.get(inst,(inst,"#94a3b8"))
    bias   = data.get("bias","Neutral")
    bc     = BIAS_C.get(bias,"#94a3b8")
    bbg    = BIAS_BG.get(bias,"rgba(148,163,184,.08)")
    cbord  = CARD_BORDER.get(bias,"rgba(255,255,255,.08)")
    c      = data.get("confidence",50)
    live   = prices.get(inst,{})
    p_str  = f"${live['price']:,.2f}" if live.get("price") else data.get("price","—")
    chg    = live.get("change_pct")
    c_str  = f"{chg:+.2f}%" if chg is not None else data.get("change","—")
    c_col  = "#4ade80" if (chg or 0)>=0 else "#f87171"

    # Edge factor
    ef     = data.get("edge_factor",5)
    el     = data.get("edge_label","Low Edge")
    el_c,el_bg = EDGE_STYLE.get(el,("#94a3b8","rgba(148,163,184,.08)"))

    # Event risk
    er   = data.get("event_risk","Low")
    er_c,er_bg = RISK_STYLE.get(er,("#94a3b8","rgba(148,163,184,.07)"))

    # Flow direction
    fd   = data.get("flow_direction","Neutral Flows")
    fd_c,fd_bg,fd_i = FLOW_STYLE.get(fd,("#94a3b8","rgba(148,163,184,.08)","→"))

    buls = "".join(f'<div style="font-size:11px;color:#94a3b8;line-height:1.65;padding:2px 0 2px 12px;position:relative;"><span style="position:absolute;left:0;color:#334155;font-size:10px;">›</span>{b}</div>' for b in data.get("bullets",[]) if b)
    cbar = f'<div style="display:flex;align-items:center;gap:5px;"><div style="width:50px;height:3px;background:rgba(255,255,255,.07);border-radius:2px;overflow:hidden;"><div style="height:100%;width:{c}%;background:{conf_c(c)};border-radius:2px;"></div></div><span style="font-size:11px;color:{conf_c(c)};font-weight:700;font-family:\'DM Mono\',monospace;">{c}%</span></div>'

    is_expanded = (expanded_inst == inst)
    expand_hint = "▲ Close" if is_expanded else "▼ Deep Dive"

    st.markdown(f"""
    <div style="background:rgba(255,255,255,.025);border:1px solid {cbord};border-top:2px solid {color};
        border-radius:12px;padding:16px 18px;margin-bottom:4px;position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,{color},transparent);"></div>
        <!-- Header -->
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
            <div>
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;">
                    <div style="width:7px;height:7px;border-radius:50%;background:{color};box-shadow:0 0 5px {color};"></div>
                    <span style="font-size:13px;font-weight:700;color:#f1f5f9;letter-spacing:.04em;">{inst}</span>
                </div>
                <div style="font-size:10px;color:#475569;">{name}</div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:16px;font-weight:800;color:#f8fafc;font-family:'DM Mono',monospace;">{p_str}</div>
                <div style="font-size:11px;font-weight:600;color:{c_col};">{c_str}</div>
            </div>
        </div>
        <!-- Bias + confidence -->
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
            <span style="font-size:10px;font-weight:700;padding:3px 8px;background:{bbg};border:1px solid {bc}44;color:{bc};border-radius:20px;letter-spacing:.07em;text-transform:uppercase;">{bias}</span>
            {cbar}
        </div>
        <!-- Bias summary -->
        {f'<div style="font-size:11px;color:#64748b;line-height:1.55;margin-bottom:10px;padding:7px 10px;background:rgba(255,255,255,.02);border-radius:6px;border-left:2px solid {color}50;">{data.get("bias_summary","")}</div>' if data.get("bias_summary") else ""}
        <!-- Edge + Event Risk + Flow row -->
        <div style="display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap;">
            <div style="display:flex;align-items:center;gap:5px;background:{el_bg};border-radius:6px;padding:4px 8px;">
                <span style="font-size:9px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.07em;">Edge</span>
                <span style="font-size:11px;font-weight:700;color:{el_c};">{ef}/10</span>
                <span style="font-size:9px;color:{el_c};font-weight:600;">{el}</span>
            </div>
            <div style="display:flex;align-items:center;gap:5px;background:{er_bg};border-radius:6px;padding:4px 8px;">
                <span style="font-size:9px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.07em;">Event Risk</span>
                <span style="font-size:9px;font-weight:700;color:{er_c};">{er}</span>
            </div>
            <div style="display:flex;align-items:center;gap:5px;background:{fd_bg};border-radius:6px;padding:4px 8px;">
                <span style="font-size:12px;color:{fd_c};">{fd_i}</span>
                <span style="font-size:9px;font-weight:600;color:{fd_c};">{fd}</span>
            </div>
        </div>
        <!-- Bullets -->
        <div style="border-top:1px solid rgba(255,255,255,.05);padding-top:8px;margin-bottom:8px;">{buls}</div>
        <!-- Action signal -->
        {action_html(data.get("action","Hold"),data.get("action_reason",""))}
        <!-- Deep dive hint -->
        <div style="margin-top:8px;font-size:10px;color:#334155;text-align:right;letter-spacing:.06em;text-transform:uppercase;">{expand_hint}</div>
    </div>""", unsafe_allow_html=True)

# ── RENDER: DEEP DIVE (inline below card) ─────────────────────────────────────
def render_deep_div_inline(inst, data, deep):
    name,color = META.get(inst,(inst,"#94a3b8"))
    sections = [
        ("Fundamental Overview",  "fundamental_overview"),
        ("Macro Correlations",    "macro_correlations"),
        ("Key Drivers (24–48h)",  "key_drivers"),
        ("Risk Scenario",         "risk_scenario"),
        ("Trade Context",         "trade_context"),
        ("Session Notes",         "session_notes"),
    ]
    if not deep:
        st.markdown(f"""
        <div style="background:rgba(255,255,255,.015);border:1px solid rgba(255,255,255,.07);
            border-radius:0 0 12px 12px;padding:20px;margin-bottom:12px;text-align:center;">
            <div style="font-size:12px;color:#475569;">Generating deep dive analysis...</div>
        </div>""", unsafe_allow_html=True)
        return

    bias   = data.get("bias","Neutral")
    bc     = BIAS_C.get(bias,"#94a3b8")
    bbg    = BIAS_BG.get(bias,"rgba(148,163,184,.08)")
    c      = data.get("confidence",50)

    sections_html = ""
    for label,key in sections:
        txt = deep.get(key,"")
        if txt:
            sections_html += f"""
            <div style="margin-bottom:20px;">
                <div style="font-size:10px;font-weight:700;color:{color};letter-spacing:.1em;text-transform:uppercase;
                    margin-bottom:8px;display:flex;align-items:center;gap:7px;">
                    <div style="width:18px;height:1px;background:{color};opacity:.5;"></div>{label}
                </div>
                <p style="font-size:13px;color:#94a3b8;line-height:1.8;margin:0;">{txt}</p>
            </div>"""

    st.markdown(f"""
    <div style="background:#0d1117;border:1px solid rgba(255,255,255,.1);border-top:2px solid {color};
        border-radius:0 0 12px 12px;padding:24px 22px;margin-bottom:14px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:18px;flex-wrap:wrap;">
            <div style="width:9px;height:9px;border-radius:50%;background:{color};box-shadow:0 0 7px {color};"></div>
            <span style="font-size:15px;font-weight:800;color:#f8fafc;">{inst}</span>
            <span style="font-size:12px;color:#475569;">— {name}</span>
            <span style="font-size:10px;font-weight:700;padding:3px 8px;background:{bbg};border:1px solid {bc}44;
                color:{bc};border-radius:20px;letter-spacing:.07em;text-transform:uppercase;">{bias}</span>
            <span style="font-size:12px;color:{conf_c(c)};font-weight:700;">{c}% confidence</span>
        </div>
        {sections_html}
        <div style="font-size:10px;color:#1e293b;text-align:center;padding-top:10px;
            border-top:1px solid rgba(255,255,255,.05);letter-spacing:.08em;text-transform:uppercase;">
            Not financial advice</div>
    </div>""", unsafe_allow_html=True)

# ── RENDER: REGIME + INSTITUTIONS ────────────────────────────────────────────
def render_regime(brief):
    regime = brief.get("risk_regime","Mixed")
    rc,rbg,rb,ri = RS.get(regime,RS["Mixed"])
    sent = brief.get("institutional_sentiment",{})
    so   = sent.get("overall","Neutral")
    sc   = SENT_C.get(so,"#94a3b8")
    cf   = sent.get("capital_flow","")
    st.markdown(f"""
    <div style="background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.07);border-radius:9px;padding:11px 14px;margin-bottom:11px;">
        <div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:7px;">
            <span style="font-size:10px;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:.08em;">Regime</span>
            <span style="font-size:10px;font-weight:700;padding:2px 8px;background:{rbg};border:1px solid {rb};color:{rc};border-radius:20px;">{ri} {regime}</span>
            <span style="color:#334155;font-size:10px;">·</span>
            <span style="font-size:10px;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:.08em;">Institutions</span>
            <span style="font-size:10px;font-weight:700;padding:2px 8px;background:{sc}18;border:1px solid {sc}44;color:{sc};border-radius:20px;text-transform:uppercase;">{so}</span>
            <span style="font-size:11px;color:#475569;font-style:italic;">{brief.get("risk_rationale","")}</span>
        </div>
        <div style="font-size:12px;color:#64748b;line-height:1.6;">{sent.get("summary","")} <span style="color:#475569;">{sent.get("positioning","")}</span></div>
        {f'<div style="font-size:11px;color:#4f46e5;margin-top:5px;padding-top:5px;border-top:1px solid rgba(255,255,255,.04);">💰 {cf}</div>' if cf else ''}
    </div>""", unsafe_allow_html=True)

def render_indicators(indicators, prices):
    cols = st.columns(3)
    for col,(key,label) in zip(cols,[("vix","VIX"),("dxy","DXY"),("yield10y","10Y Yield")]):
        ind = indicators.get(key,{})
        val = (f"{prices['VIX']['price']:.2f}" if key=="vix" and prices.get("VIX",{}).get("price") else None) or ind.get("value","—")
        d   = ind.get("direction","up")
        ac  = "#4ade80" if d=="up" else "#f87171"
        with col:
            st.markdown(f"""
            <div style="background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:9px;
                padding:12px 14px;display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                <div>
                    <div style="font-size:10px;color:#475569;letter-spacing:.08em;margin-bottom:3px;">{label}</div>
                    <div style="font-size:15px;font-weight:800;color:#f1f5f9;font-family:'DM Mono',monospace;">{val}</div>
                    <div style="font-size:10px;color:#475569;margin-top:2px;">{ind.get("note","")}</div>
                </div>
                <span style="font-size:26px;color:{ac};font-weight:700;">{"↑" if d=="up" else "↓"}</span>
            </div>""", unsafe_allow_html=True)

def render_inst(data):
    if not data: st.info("Click 'Load Institutional Deep Dive' to generate."); return
    st.markdown(f'<div style="font-size:13px;color:#94a3b8;line-height:1.8;margin-bottom:20px;">{data.get("overview","")}</div>', unsafe_allow_html=True)
    for key,label in [("xauusd","XAU/USD"),("nq","NQ"),("es","ES"),("us30","US30")]:
        color = INST_C.get(label,"#94a3b8")
        txt   = data.get(key,"")
        if txt:
            st.markdown(f"""
            <div style="margin-bottom:22px;padding-left:14px;border-left:2px solid {color}30;">
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;flex-wrap:wrap;">
                    <div style="width:7px;height:7px;border-radius:50%;background:{color};box-shadow:0 0 5px {color};"></div>
                    <span style="font-size:12px;font-weight:700;color:#f1f5f9;">{label}</span>
                    <span style="font-size:11px;color:#475569;">— {META.get(label,("",""))[0]}</span>
                    {inst_pill(data.get(f"{key.replace('/','').replace(' ','').lower()}_action", data.get(f"{key}_action","Hold")))}
                </div>
                <p style="font-size:13px;color:#94a3b8;line-height:1.8;margin:0;">{txt}</p>
            </div>""", unsafe_allow_html=True)
    if data.get("key_signal"):
        st.markdown(f"""
        <div style="background:rgba(167,139,250,.07);border:1px solid rgba(167,139,250,.2);border-radius:8px;padding:12px 14px;margin-top:4px;">
            <div style="font-size:10px;font-weight:700;color:#a78bfa;text-transform:uppercase;letter-spacing:.1em;margin-bottom:5px;">Key Signal</div>
            <p style="font-size:13px;color:#c4b5fd;line-height:1.7;margin:0;">{data["key_signal"]}</p>
        </div>""", unsafe_allow_html=True)
    st.markdown('<div style="font-size:10px;color:#1e293b;text-align:center;margin-top:18px;letter-spacing:.08em;text-transform:uppercase;">Not financial advice</div>', unsafe_allow_html=True)

def render_news(headlines, news_data):
    c1,c2 = st.columns([2,1])
    with c1:
        st.markdown('<div style="font-size:11px;font-weight:700;color:#475569;letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px;">Latest Headlines</div>', unsafe_allow_html=True)
        items = news_data.get("news") or [{"headline":h["title"],"summary":"","url":h["link"],"source":h["source"],"time":"","impact":"medium","category":"Macro"} for h in headlines]
        for item in items[:8]:
            imp=item.get("impact","medium"); cat=item.get("category","Macro")
            bdr="#ef4444" if imp=="high" else "#f59e0b" if imp=="medium" else "#334155"
            cc=CAT_C.get(cat,"#94a3b8")
            ib="rgba(239,68,68,.12)" if imp=="high" else "rgba(251,191,36,.1)" if imp=="medium" else "rgba(148,163,184,.08)"
            ic="#f87171" if imp=="high" else "#fbbf24" if imp=="medium" else "#64748b"
            url=item.get("url","")
            lnk=f'<a href="{url}" target="_blank" style="font-size:10px;color:#4f46e5;text-decoration:none;">Read full article ↗</a>' if url else ""
            st.markdown(f"""
            <div style="background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.06);border-radius:9px;padding:11px 13px;margin-bottom:7px;border-left:2px solid {bdr};">
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;flex-wrap:wrap;">
                    <span style="font-size:10px;color:#334155;font-family:'DM Mono',monospace;">{item.get("time","")}</span>
                    <span style="font-size:9px;padding:2px 5px;background:{cc}20;color:{cc};border-radius:4px;font-weight:700;">{cat}</span>
                    <span style="font-size:9px;padding:2px 5px;background:{ib};color:{ic};border-radius:4px;font-weight:700;text-transform:uppercase;">{imp}</span>
                    <span style="font-size:9px;color:#334155;">{item.get("source","")}</span>
                </div>
                <div style="font-size:12px;font-weight:600;color:#e2e8f0;line-height:1.5;margin-bottom:3px;">{item.get("headline","")}</div>
                <div style="font-size:11px;color:#64748b;line-height:1.5;margin-bottom:{4 if url else 0}px;">{item.get("summary","")}</div>
                {lnk}
            </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown('<div style="font-size:11px;font-weight:700;color:#475569;letter-spacing:.1em;text-transform:uppercase;margin-bottom:3px;">Economic Calendar</div><div style="font-size:10px;color:#334155;margin-bottom:10px;">High-impact only</div>', unsafe_allow_html=True)
        for ev in (news_data.get("calendar") or []):
            st.markdown(f"""
            <div style="background:rgba(255,255,255,.02);border:1px solid rgba(239,68,68,.15);border-left:2px solid #ef4444;border-radius:7px;padding:9px 11px;margin-bottom:5px;">
                <div style="font-size:9px;color:#ef4444;font-weight:700;margin-bottom:3px;">{ev.get("day","")} · {ev.get("time","")}</div>
                <div style="font-size:11px;font-weight:600;color:#cbd5e1;margin-bottom:3px;">{ev.get("event","")}</div>
                <div style="font-size:10px;color:#475569;">Affects: <span style="color:#64748b;">{ev.get("affects","")}</span></div>
                {f'<div style="font-size:10px;color:#475569;margin-top:2px;">Est: <span style="color:#64748b;font-family:monospace;">{ev["consensus"]}</span></div>' if ev.get("consensus") else ""}
            </div>""", unsafe_allow_html=True)

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    now = datetime.now().strftime("%a %b %d, %Y · %I:%M %p")
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 0 14px;
        margin-bottom:20px;border-bottom:1px solid rgba(255,255,255,.05);">
        <div style="display:flex;align-items:center;gap:10px;">
            <div style="width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,#1e40af,#6d28d9);
                display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;color:white;">J</div>
            <div>
                <div style="font-size:14px;font-weight:700;color:#f1f5f9;">Morning Brief</div>
                <div style="font-size:10px;color:#334155;letter-spacing:.06em;">{now}</div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    if not GROQ_API_KEY:
        st.error("⚠ GROQ_API_KEY not found — go to Manage App → Secrets.")
        st.stop()

    for k in ["brief","outlook","inst","news_data","deep_dives","prices","headlines","ready","expanded_inst"]:
        if k not in st.session_state:
            st.session_state[k] = None

    t1,t2,t3 = st.tabs(["📊   Brief", "📰   News", "🏦   Institutions"])

    # ── BRIEF ─────────────────────────────────────────────────────────────────
    with t1:
        if not st.session_state.ready:
            st.markdown("""
            <div style="text-align:center;padding:52px 0 36px;">
                <div style="width:54px;height:54px;border-radius:16px;margin:0 auto 20px;
                    background:linear-gradient(135deg,#1e3a5f,#1e40af);border:1px solid rgba(59,130,246,.3);
                    display:flex;align-items:center;justify-content:center;font-size:22px;
                    box-shadow:0 0 28px rgba(59,130,246,.15);">⚡</div>
                <div style="font-size:19px;font-weight:700;color:#f1f5f9;margin-bottom:8px;">Ready for your brief</div>
                <div style="font-size:13px;color:#475569;line-height:1.6;max-width:360px;margin:0 auto 28px;">
                    Live prices via Alpha Vantage · AI analysis via Groq · Geopolitical transmission chain framework
                </div>
            </div>""", unsafe_allow_html=True)

        _,bc,_ = st.columns([1,1.2,1])
        with bc:
            gen = st.button("⚡   Generate Morning Brief", use_container_width=True)

        if gen:
            prog = st.empty()
            try:
                prog.markdown('<div style="text-align:center;font-size:11px;color:#64748b;letter-spacing:.1em;text-transform:uppercase;padding:8px 0;">Fetching live prices...</div>', unsafe_allow_html=True)
                st.session_state.prices    = fetch_prices(AV_API_KEY)
                st.session_state.headlines = fetch_headlines()
                prices = st.session_state.prices
                p_ctx  = "\n".join([f"{k}: ${v['price']:,.2f} ({v.get('change_pct',0):+.2f}%)" if v.get("price") else f"{k}: N/A" for k,v in prices.items()])
                n_ctx  = "\n".join([f"- {h['title']} ({h['source']})" for h in (st.session_state.headlines or [])])
                mdata  = f"TODAY: {TODAY}\nLIVE PRICES:\n{p_ctx}\n\nRECENT HEADLINES:\n{n_ctx}"

                prog.markdown('<div style="text-align:center;font-size:11px;color:#64748b;letter-spacing:.1em;text-transform:uppercase;padding:8px 0;">Generating analysis (1/3)...</div>', unsafe_allow_html=True)
                st.session_state.brief = parse_json(call_groq(BRIEF_SYS, f"Market data:\n{mdata}\n\nGenerate the brief JSON.", 2200))

                prog.markdown('<div style="text-align:center;font-size:11px;color:#64748b;letter-spacing:.1em;text-transform:uppercase;padding:8px 0;">Generating outlook (2/3)...</div>', unsafe_allow_html=True)
                st.session_state.outlook = parse_json(call_groq(OUTLOOK_SYS, f"Market data:\n{mdata}\n\nWrite the outlook JSON.", 1200))

                prog.markdown('<div style="text-align:center;font-size:11px;color:#64748b;letter-spacing:.1em;text-transform:uppercase;padding:8px 0;">Generating news (3/3)...</div>', unsafe_allow_html=True)
                st.session_state.news_data = parse_json(call_groq(NEWS_SYS, f"Headlines:\n{n_ctx}\n\nConvert to JSON with high-impact calendar events this week for XAU/USD, NQ, ES, US30.", 1500))

                st.session_state.deep_dives  = {}
                st.session_state.inst        = None
                st.session_state.expanded_inst = None
                st.session_state.ready       = True
                prog.empty()
                st.rerun()
            except Exception as e:
                prog.empty()
                st.error(f"Error: {str(e)}")

        if st.session_state.ready and st.session_state.brief:
            brief   = st.session_state.brief
            outlook = st.session_state.outlook or {}
            prices  = st.session_state.prices  or {}
            insts   = brief.get("instruments",{})

            # Session context bar
            render_session_bar(brief)

            # Outlook strip
            render_outlook(outlook)

            # Session theme
            st.markdown(f"""
            <div style="background:rgba(79,70,229,.07);border:1px solid rgba(79,70,229,.18);border-radius:9px;padding:11px 16px;margin-bottom:9px;">
                <span style="font-size:10px;color:#6366f1;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-right:9px;">Session Theme</span>
                <span style="font-size:13px;color:#a5b4fc;">{brief.get("session_theme","")}</span>
            </div>""", unsafe_allow_html=True)

            # Macro drivers
            drivers = brief.get("macro_drivers",[])
            if drivers:
                d1,d2,d3 = st.columns(3)
                for col,d in zip([d1,d2,d3],drivers[:3]):
                    with col:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.06);border-radius:7px;padding:9px 12px;margin-bottom:12px;">
                            <div style="font-size:10px;font-weight:700;color:#6366f1;letter-spacing:.08em;text-transform:uppercase;margin-bottom:3px;">{d.get("label","")}</div>
                            <div style="font-size:11px;color:#94a3b8;line-height:1.5;">{d.get("detail","")}</div>
                        </div>""", unsafe_allow_html=True)

            # Asset cards 2×2 — click to deep dive
            st.markdown('<div style="font-size:11px;font-weight:700;color:#475569;letter-spacing:.1em;text-transform:uppercase;margin-bottom:8px;">Assets — click any card to open deep dive</div>', unsafe_allow_html=True)
            row1 = ["XAU/USD","NQ"]
            row2 = ["ES","US30"]

            for row in [row1, row2]:
                c1,c2 = st.columns(2)
                for col,inst in zip([c1,c2],row):
                    d = insts.get(inst,{})
                    if not d: continue
                    with col:
                        render_card(inst, d, prices, st.session_state.expanded_inst)
                        if st.button(f"{'▲ Close' if st.session_state.expanded_inst==inst else '▼ Deep Dive'}", key=f"dd_{inst}"):
                            if st.session_state.expanded_inst == inst:
                                st.session_state.expanded_inst = None
                            else:
                                st.session_state.expanded_inst = inst
                                # Generate deep dive if not cached
                                if inst not in (st.session_state.deep_dives or {}):
                                    with st.spinner(f"Generating {inst} deep dive..."):
                                        p_ctx  = "\n".join([f"{k}: ${v['price']:,.2f}" if v.get("price") else f"{k}: N/A" for k,v in prices.items()])
                                        n_ctx  = "\n".join([f"- {h['title']}" for h in (st.session_state.headlines or [])])
                                        raw = call_groq(DEEP_SYS,
                                            f"Instrument: {inst} ({META.get(inst,('',''))[0]})\nBias: {d.get('bias','Neutral')}\nData:\nTODAY: {TODAY}\nPRICES:\n{p_ctx}\nHEADLINES:\n{n_ctx}\n\nWrite the deep-dive JSON.",
                                            1800)
                                        if st.session_state.deep_dives is None:
                                            st.session_state.deep_dives = {}
                                        st.session_state.deep_dives[inst] = parse_json(raw)
                            st.rerun()

                # Show deep dive inline after the row if one of these instruments is expanded
                for inst in row:
                    if st.session_state.expanded_inst == inst:
                        d = insts.get(inst,{})
                        deep = (st.session_state.deep_dives or {}).get(inst)
                        render_deep_div_inline(inst, d, deep)

            # Regime
            render_regime(brief)

            # Indicators
            render_indicators(brief.get("indicators",{}), prices)

            # Top risk
            if brief.get("top_risk"):
                st.markdown(f"""
                <div style="background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.18);border-radius:9px;
                    padding:9px 14px;font-size:12px;color:#fca5a5;display:flex;align-items:center;gap:9px;margin-bottom:16px;">
                    <span>🎯</span><span><strong style="color:#f87171;">Top risk — </strong>{brief["top_risk"]}</span>
                </div>""", unsafe_allow_html=True)

            st.markdown("---")
            _,rc,_ = st.columns([1,1,1])
            with rc:
                if st.button("↺   Refresh Brief", use_container_width=True):
                    for k in ["brief","outlook","inst","news_data","deep_dives","prices","headlines","ready","expanded_inst"]:
                        st.session_state[k] = None
                    st.rerun()
            st.markdown('<div style="text-align:center;font-size:10px;color:#1e293b;letter-spacing:.06em;margin-top:4px;">NOT FINANCIAL ADVICE · GROQ + ALPHA VANTAGE</div>', unsafe_allow_html=True)

    # ── NEWS ──────────────────────────────────────────────────────────────────
    with t2:
        if not st.session_state.ready:
            st.info("Generate a brief first to load news.")
        else:
            render_news(st.session_state.headlines or [], st.session_state.news_data or {})

    # ── INSTITUTIONS ──────────────────────────────────────────────────────────
    with t3:
        if not st.session_state.ready:
            st.info("Generate a brief first.")
        else:
            st.markdown('<div style="font-size:17px;font-weight:800;color:#f8fafc;margin-bottom:3px;">Institutional Positioning</div><div style="font-size:12px;color:#475569;margin-bottom:16px;">How smart money is positioned across your assets</div>', unsafe_allow_html=True)
            if not st.session_state.inst:
                _,ib,_ = st.columns([1,1.5,1])
                with ib:
                    if st.button("🏦   Load Institutional Deep Dive", use_container_width=True):
                        with st.spinner("Generating institutional analysis..."):
                            brief  = st.session_state.brief or {}
                            prices = st.session_state.prices or {}
                            p_ctx  = "\n".join([f"{k}: ${v['price']:,.2f}" if v.get("price") else f"{k}: N/A" for k,v in prices.items()])
                            n_ctx  = "\n".join([f"- {h['title']}" for h in (st.session_state.headlines or [])])
                            st.session_state.inst = parse_json(call_groq(INST_SYS,
                                f"Sentiment: {json.dumps(brief.get('institutional_sentiment',{}))}\nPrices:\n{p_ctx}\nHeadlines:\n{n_ctx}\n\nWrite the institutional JSON.", 2000))
                            st.rerun()
            else:
                render_inst(st.session_state.inst)

main()
