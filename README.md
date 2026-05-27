# Morning Brief — Trading Dashboard

A live institutional-grade trading dashboard powered by:
- **Groq API** (free) — AI analysis via Llama 3.3 70B
- **Alpha Vantage** (free) — Live market prices
- **Streamlit** (free) — Web hosting

## Features
- Market Transmission Chain analysis (geopolitics → oil → yields → DXY → gold → indices)
- 4 asset cards: XAU/USD, NQ, ES, US30 with Buy/Sell/Hold signals
- Institutional positioning deep dive
- Live news feed + economic calendar
- Risk regime, VIX/DXY/10Y indicators

---

## Setup (one time, ~10 minutes)

### Step 1 — Get your free API keys

**Groq (AI engine):**
1. Go to [console.groq.com](https://console.groq.com)
2. Sign up free → API Keys → Create Key
3. Copy your key (starts with `gsk_`)

**Alpha Vantage (live prices):**
1. Go to [alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key)
2. Enter your email → get free key instantly
3. Copy your key

---

### Step 2 — Put the code on GitHub

1. Go to [github.com](https://github.com) → sign up free if needed
2. Click **New repository**
3. Name it `morning-brief` → set to **Public** → click Create
4. Upload all files from this folder (drag and drop in the GitHub UI)
5. **Do NOT upload** `.streamlit/secrets.toml` (it has your keys)

---

### Step 3 — Deploy to Streamlit

1. Go to [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub
2. Click **New app**
3. Select your `morning-brief` repo → branch: `main` → file: `app.py`
4. Click **Advanced settings** → paste your secrets:

```toml
GROQ_API_KEY = "gsk_your_key_here"
AV_API_KEY   = "your_alphavantage_key_here"
```

5. Click **Deploy** — takes ~2 minutes
6. You get a permanent URL like `https://your-name-morning-brief.streamlit.app`

---

### Step 4 — Use it every morning

Open your Streamlit URL → click **Generate Morning Brief** → done.

Bookmark it on your phone or desktop. The URL never changes.

---

## Cost

| Service | Cost |
|---|---|
| Groq API | Free (generous daily limits) |
| Alpha Vantage | Free (25 requests/day on free tier) |
| GitHub | Free |
| Streamlit Cloud | Free |
| **Total** | **$0** |

---

## Notes

- Alpha Vantage free tier: 25 API calls/day. The app uses ~8 calls per brief generation, so ~3 briefs/day max on the free tier. Upgrade to premium ($50/month) for unlimited.
- Prices are cached for 5 minutes to avoid hitting rate limits.
- If prices show N/A, Alpha Vantage rate limit was hit — wait a few minutes and try again.
