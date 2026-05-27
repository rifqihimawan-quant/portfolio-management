"""
Portfolio Manager — Multi-Book Crypto Portfolio
Assets: USDT, BTC, ETH
Features: multi-book, real-time prices, IDR toggle, risk metrics, charts
"""

import io, json, re, time, requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AR = True
except ImportError:
    HAS_AR = False

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Manager",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# THEME
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html,body,.stApp{font-family:'Inter',sans-serif!important;background:#0f1117;color:#e2e8f0;}
.main .block-container{padding-top:0!important;padding-bottom:2rem;max-width:1600px;}

[data-testid="stSidebar"]{background:#141820;border-right:1px solid #1e2535;}
[data-testid="stSidebar"] *{color:#e2e8f0!important;}
[data-testid="stSidebar"] .stMarkdown p{color:#64748b!important;font-size:10px;letter-spacing:.1em;text-transform:uppercase;font-weight:600;}
[data-testid="stSidebar"] input,[data-testid="stSidebar"] textarea{background:#1e2535!important;border-color:#2d3748!important;color:#e2e8f0!important;font-family:'JetBrains Mono',monospace!important;font-size:12px!important;}
[data-testid="stSidebar"] [data-baseweb="select"]>div{background:#1e2535!important;border-color:#2d3748!important;}
[data-testid="stSidebar"] [data-baseweb="select"] span{color:#e2e8f0!important;}

.top-bar{background:linear-gradient(90deg,#0f1117 0%,#141820 100%);border-bottom:1px solid #1e2535;padding:12px 28px;display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;}
.top-bar-title{font-size:18px;font-weight:700;color:#f1f5f9;letter-spacing:-.02em;}
.top-bar-sub{font-size:10px;color:#475569;letter-spacing:.08em;text-transform:uppercase;margin-top:2px;}
.live-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#22c55e;margin-right:6px;animation:pulse 2s ease-in-out infinite;}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1);}50%{opacity:.5;transform:scale(1.4);}}

.section-head{font-size:10px;font-weight:700;color:#475569;letter-spacing:.12em;text-transform:uppercase;border-bottom:1px solid #1e2535;padding-bottom:6px;margin-bottom:14px;margin-top:4px;}

[data-testid="stMetric"]{background:#141820;border:1px solid #1e2535;border-radius:12px;padding:14px 18px;}
[data-testid="stMetric"] label{color:#475569!important;font-size:10px!important;letter-spacing:.09em;text-transform:uppercase;font-weight:600;}
[data-testid="stMetricValue"]{color:#f1f5f9!important;font-size:1.5rem!important;font-weight:700!important;font-family:'JetBrains Mono',monospace!important;}
[data-testid="stMetricDelta"] svg{display:none;}
[data-testid="stMetricDelta"]{font-family:'JetBrains Mono',monospace!important;font-size:12px!important;}

.price-card{background:#141820;border:1px solid #1e2535;border-radius:10px;padding:12px 16px;text-align:center;}
.price-label{font-size:9px;color:#475569;letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px;}
.price-val{font-size:18px;font-weight:700;font-family:'JetBrains Mono',monospace;color:#f1f5f9;}
.price-chg{font-size:11px;font-weight:600;margin-top:3px;}
.up{color:#22c55e;}.down{color:#ef4444;}.neutral{color:#94a3b8;}

.risk-badge{display:inline-flex;align-items:center;gap:8px;padding:8px 20px;border-radius:8px;font-weight:700;font-size:14px;letter-spacing:.04em;}
.risk-on{background:rgba(34,197,94,.12);color:#22c55e;border:1px solid rgba(34,197,94,.3);}
.risk-off{background:rgba(239,68,68,.12);color:#ef4444;border:1px solid rgba(239,68,68,.3);}
.risk-neutral{background:rgba(234,179,8,.12);color:#eab308;border:1px solid rgba(234,179,8,.3);}

.book-card{background:#141820;border:1px solid #1e2535;border-radius:12px;padding:14px 18px;margin-bottom:10px;}
.book-name{font-size:13px;font-weight:700;color:#f1f5f9;margin-bottom:8px;}
.book-row{display:flex;justify-content:space-between;font-size:11px;padding:4px 0;border-bottom:1px solid #1e2535;}
.book-row:last-child{border:none;}
.book-asset{color:#64748b;}
.book-amount{color:#e2e8f0;font-family:'JetBrains Mono',monospace;}
.book-value{color:#63b3ff;font-family:'JetBrains Mono',monospace;font-weight:600;}

.stButton>button{background:#1e2535!important;color:#e2e8f0!important;border:1px solid #2d3748!important;border-radius:8px!important;font-size:12px!important;font-weight:500!important;transition:all .15s!important;}
.stButton>button:hover{background:#2d3748!important;border-color:#3d4f6e!important;}
.btn-primary>button{background:linear-gradient(135deg,#3b82f6,#2563eb)!important;color:#fff!important;border:none!important;font-weight:600!important;}
.btn-danger>button{background:rgba(239,68,68,.12)!important;color:#ef4444!important;border:1px solid rgba(239,68,68,.3)!important;}

.idr-toggle-on{background:rgba(99,179,255,.12)!important;color:#63b3ff!important;border:1px solid rgba(99,179,255,.3)!important;font-weight:700!important;}

[data-testid="stInfo"]{background:rgba(59,130,246,.08)!important;border:1px solid rgba(59,130,246,.2)!important;border-radius:8px!important;color:#93c5fd!important;}
[data-testid="stSuccess"]{background:rgba(34,197,94,.08)!important;border:1px solid rgba(34,197,94,.2)!important;border-radius:8px!important;color:#86efac!important;}
[data-testid="stWarning"]{background:rgba(234,179,8,.08)!important;border:1px solid rgba(234,179,8,.2)!important;border-radius:8px!important;color:#fde68a!important;}
[data-testid="stError"]{background:rgba(239,68,68,.08)!important;border:1px solid rgba(239,68,68,.2)!important;border-radius:8px!important;}

.stTabs [data-baseweb="tab-list"]{background:#141820!important;border-radius:10px!important;border:1px solid #1e2535!important;padding:4px!important;}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:#64748b!important;border-radius:7px!important;font-size:12px!important;font-weight:500!important;}
.stTabs [aria-selected="true"]{background:#1e2535!important;color:#f1f5f9!important;}

hr{border:none;border-top:1px solid #1e2535;margin:1rem 0;}
.stDataFrame{border:1px solid #1e2535!important;border-radius:8px!important;}

.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:16px;}
.metric-box{background:#141820;border:1px solid #1e2535;border-radius:10px;padding:12px 14px;}
.metric-box .label{font-size:9px;color:#475569;letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px;}
.metric-box .val{font-size:17px;font-weight:700;font-family:'JetBrains Mono',monospace;color:#f1f5f9;}
.metric-box .sub{font-size:10px;color:#475569;margin-top:2px;}

.footer{font-size:10px;color:#334155;text-align:center;margin-top:24px;padding-top:14px;border-top:1px solid #1e2535;}
</style>
""", unsafe_allow_html=True)

CHART_STYLE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(20,24,32,0.8)",
    font=dict(family="Inter, sans-serif", color="#64748b", size=11),
    margin=dict(l=52, r=20, t=36, b=40),
    xaxis=dict(gridcolor="#1e2535", linecolor="#1e2535",
               tickfont=dict(size=10, color="#475569"), showgrid=True),
    yaxis=dict(gridcolor="#1e2535", linecolor="#1e2535",
               tickfont=dict(size=10, color="#475569"), showgrid=True),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#94a3b8")),
    hoverlabel=dict(bgcolor="#1e2535", bordercolor="#2d3748",
                    font=dict(family="JetBrains Mono", size=12, color="#e2e8f0")),
)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INITIALISATION
# ─────────────────────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "books":        {},          # {book_name: {asset: amount}}
        "history":      [],          # [{ts, total_usd, book_values}]
        "show_idr":     False,
        "idr_rate":     17520.0,     # fallback Kurs Tengah BCA
        "prices":       {"BTC": 0.0, "ETH": 0.0, "USDT": 1.0},
        "price_change": {"BTC": 0.0, "ETH": 0.0, "USDT": 0.0},
        "last_price_fetch": 0,
        "last_idr_fetch":   0,
        "price_error":  None,
        "idr_error":    None,
        "editing_book": None,        # name of book currently being edited
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ─────────────────────────────────────────────────────────────────────────────
# PRICE FETCHING  — CoinGecko free (no key required)
# ─────────────────────────────────────────────────────────────────────────────
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum,tether"
    "&vs_currencies=usd"
    "&include_24hr_change=true"
)

@st.cache_data(ttl=60, show_spinner=False)
def fetch_prices() -> dict:
    """
    Fetch BTC, ETH, USDT prices from CoinGecko free API.
    Falls back to Binance public ticker if CoinGecko fails.
    Returns {"BTC": price, "ETH": price, "USDT": price,
             "BTC_chg": %, "ETH_chg": %, "ts": datetime_str}
    """
    # ── Primary: CoinGecko ────────────────────────────────────────────────
    try:
        r = requests.get(COINGECKO_URL,
                         headers={"User-Agent": "PortfolioManager/1.0"},
                         timeout=8)
        r.raise_for_status()
        d = r.json()
        return {
            "BTC":      d["bitcoin"]["usd"],
            "ETH":      d["ethereum"]["usd"],
            "USDT":     d["tether"]["usd"],
            "BTC_chg":  d["bitcoin"].get("usd_24h_change", 0),
            "ETH_chg":  d["ethereum"].get("usd_24h_change", 0),
            "USDT_chg": 0.0,
            "source":   "CoinGecko",
            "ts":       datetime.utcnow().strftime("%H:%M:%S UTC"),
            "error":    None,
        }
    except Exception as cg_err:
        pass

    # ── Fallback: Binance public ticker ───────────────────────────────────
    try:
        def binance_price(symbol):
            r = requests.get(
                f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}",
                timeout=8)
            d = r.json()
            return float(d["lastPrice"]), float(d["priceChangePercent"])

        btc, btc_c = binance_price("BTCUSDT")
        eth, eth_c = binance_price("ETHUSDT")
        return {
            "BTC": btc, "ETH": eth, "USDT": 1.0,
            "BTC_chg": btc_c, "ETH_chg": eth_c, "USDT_chg": 0.0,
            "source": "Binance",
            "ts": datetime.utcnow().strftime("%H:%M:%S UTC"),
            "error": None,
        }
    except Exception as bn_err:
        return {
            "BTC": st.session_state["prices"].get("BTC", 95000),
            "ETH": st.session_state["prices"].get("ETH", 3500),
            "USDT": 1.0,
            "BTC_chg": 0.0, "ETH_chg": 0.0, "USDT_chg": 0.0,
            "source": "cached",
            "ts": "—",
            "error": f"CoinGecko: {str(cg_err)[:60]} | Binance: {str(bn_err)[:60]}",
        }

# ─────────────────────────────────────────────────────────────────────────────
# BCA IDR RATE FETCHING  — Kurs Tengah = (Beli + Jual) / 2
# ─────────────────────────────────────────────────────────────────────────────
BCA_KURS_URL = "https://www.bca.co.id/id/informasi/kurs"

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_idr_rate() -> dict:
    """
    Scrape BCA e-Rate table and compute Kurs Tengah for USD.
    Kurs Tengah = (Harga Beli + Harga Jual) / 2
    Returns {"rate": float, "buy": float, "sell": float,
             "updated": str, "error": str_or_None}
    """
    FALLBACK = {"rate": 17520.0, "buy": 17445.0, "sell": 17595.0,
                "updated": "16 May 2026 (fallback)", "error": None}
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "id-ID,id;q=0.9",
            "Referer": "https://www.bca.co.id/",
        }
        r = requests.get(BCA_KURS_URL, headers=headers, timeout=15)
        r.raise_for_status()

        tables = pd.read_html(io.StringIO(r.text))
        for t in tables:
            # Flatten multiindex if present
            if isinstance(t.columns, pd.MultiIndex):
                t.columns = [" ".join(str(c) for c in col).strip() for col in t.columns]
            cols = [str(c).upper() for c in t.columns]
            # Must have USD and BUY/SELL indicators
            if not any("USD" in str(row) for row in t.iloc[:, 0].astype(str)):
                continue

            # Find USD row
            for _, row in t.iterrows():
                if "USD" in str(row.iloc[0]).upper():
                    vals = []
                    for v in row.values:
                        s = str(v).replace(".", "").replace(",", ".").strip()
                        try:
                            fv = float(s)
                            if 10000 < fv < 25000:
                                vals.append(fv)
                        except Exception:
                            pass
                    if len(vals) >= 2:
                        buy, sell = vals[0], vals[1]
                        return {
                            "rate":    (buy + sell) / 2,
                            "buy":     buy,
                            "sell":    sell,
                            "updated": datetime.now().strftime("%d %b %Y %H:%M"),
                            "error":   None,
                        }
        return {**FALLBACK, "error": "USD row not found — using fallback"}
    except Exception as ex:
        return {**FALLBACK, "error": str(ex)[:80]}

# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO CALCULATIONS
# ─────────────────────────────────────────────────────────────────────────────
def calc_book_value(book: dict, prices: dict) -> float:
    return sum(amt * prices.get(asset, 0)
               for asset, amt in book.items())

def calc_total_usd(books: dict, prices: dict) -> float:
    return sum(calc_book_value(b, prices) for b in books.values())

def calc_metrics(history: list) -> dict:
    """
    Compute portfolio risk metrics from history.
    Returns dict of metrics + risk signal.
    """
    if len(history) < 2:
        return {}

    values = [h["total_usd"] for h in history]
    ts     = [h["ts"] for h in history]
    vals   = np.array(values, dtype=float)

    # Returns (period = each snapshot interval)
    rets = np.diff(vals) / vals[:-1]
    rets = rets[np.isfinite(rets)]

    if len(rets) == 0:
        return {}

    n          = len(vals)
    total_ret  = (vals[-1] - vals[0]) / vals[0] if vals[0] > 0 else 0
    peak       = np.maximum.accumulate(vals)
    drawdowns  = (vals - peak) / peak
    max_dd     = float(drawdowns.min())
    current_dd = float(drawdowns[-1])

    mu_ret  = float(np.mean(rets))
    std_ret = float(np.std(rets, ddof=1)) if len(rets) > 1 else 0

    # Sharpe (annualise assuming ~288 5-min snapshots/day)
    sharpe = (mu_ret / std_ret * np.sqrt(288)) if std_ret > 0 else 0

    # Sortino (downside deviation)
    neg_rets   = rets[rets < 0]
    down_std   = float(np.std(neg_rets, ddof=1)) if len(neg_rets) > 1 else 0
    sortino    = (mu_ret / down_std * np.sqrt(288)) if down_std > 0 else 0

    # Max profit (max from start)
    max_profit = float(np.max(vals) - vals[0]) / vals[0] if vals[0] > 0 else 0

    # Calmar = annualised return / |max drawdown|
    calmar = (total_ret / abs(max_dd)) if abs(max_dd) > 1e-6 else 0

    # Volatility (annualised)
    vol_ann = std_ret * np.sqrt(288) * 100

    # ── Risk signal ────────────────────────────────────────────────────────
    score = 0
    score += 1 if sharpe > 1.5   else (-1 if sharpe < 0.3 else 0)
    score += 1 if max_dd > -0.10 else (-1 if max_dd < -0.25 else 0)
    score += 1 if current_dd > -0.05 else (-1 if current_dd < -0.15 else 0)
    score += 1 if vol_ann < 30   else (-1 if vol_ann > 60 else 0)
    score += 1 if total_ret > 0  else -1

    if   score >= 3: signal = ("RISK-ON",   "risk-on",  "🟢")
    elif score <= -2: signal = ("RISK-OFF",  "risk-off", "🔴")
    else:             signal = ("NEUTRAL",   "risk-neutral", "🟡")

    return {
        "total_ret":    total_ret * 100,
        "max_profit":   max_profit * 100,
        "max_drawdown": max_dd * 100,
        "current_dd":   current_dd * 100,
        "sharpe":       sharpe,
        "sortino":      sortino,
        "calmar":       calmar,
        "volatility":   vol_ann,
        "signal":       signal,
        "score":        score,
        "n_snapshots":  n,
    }

# ─────────────────────────────────────────────────────────────────────────────
# CHART BUILDERS
# ─────────────────────────────────────────────────────────────────────────────
def chart_portfolio_over_time(history: list, show_idr: bool, idr_rate: float):
    if len(history) < 2:
        return None
    df = pd.DataFrame(history)
    df["ts"] = pd.to_datetime(df["ts"])
    multiplier = idr_rate if show_idr else 1
    unit = "IDR" if show_idr else "USD"
    ytitle = f"Portfolio Value ({unit})"

    fig = go.Figure()

    # Total line
    vals = df["total_usd"] * multiplier
    fig.add_trace(go.Scatter(
        x=df["ts"], y=vals, mode="lines",
        name=f"Total ({unit})",
        line=dict(color="#63b3ff", width=2.5),
        fill="tozeroy", fillcolor="rgba(99,179,255,0.06)",
        hovertemplate=f"%{{x|%H:%M:%S}}<br>%{{y:,.2f}} {unit}<extra>Total</extra>",
    ))

    # Per-book lines
    colors = ["#a78bfa","#34d399","#fb923c","#f472b6","#facc15","#38bdf8"]
    if "book_values" in df.columns:
        # Explode book_values dict column
        try:
            books_df = df["book_values"].apply(pd.Series)
            for idx, book in enumerate(books_df.columns):
                fig.add_trace(go.Scatter(
                    x=df["ts"], y=books_df[book] * multiplier,
                    mode="lines", name=book,
                    line=dict(color=colors[idx % len(colors)], width=1.5, dash="dot"),
                    hovertemplate=f"%{{x|%H:%M:%S}}<br>%{{y:,.2f}} {unit}<extra>{book}</extra>",
                ))
        except Exception:
            pass

    fig.update_layout(**CHART_STYLE,
        title=dict(text="Portfolio Value Over Time", font=dict(size=13, color="#94a3b8"), x=0),
        yaxis_title=ytitle,
        height=320,
        yaxis_tickformat=",.0f",
    )
    return fig


def chart_drawdown(history: list):
    if len(history) < 3:
        return None
    vals  = np.array([h["total_usd"] for h in history], dtype=float)
    ts    = pd.to_datetime([h["ts"] for h in history])
    peak  = np.maximum.accumulate(vals)
    dd    = (vals - peak) / peak * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts, y=dd, mode="lines",
        name="Drawdown %",
        line=dict(color="#ef4444", width=1.5),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.08)",
        hovertemplate="%{x|%H:%M:%S}<br>%{y:.2f}%<extra>Drawdown</extra>",
    ))
    fig.add_hline(y=0, line_color="#2d3748", line_width=1)
    fig.update_layout(**CHART_STYLE,
        title=dict(text="Portfolio Drawdown (%)", font=dict(size=13, color="#94a3b8"), x=0),
        yaxis_title="Drawdown (%)",
        height=200,
    )
    return fig


def chart_allocation(books: dict, prices: dict):
    if not books:
        return None
    labels, vals = [], []
    for book, positions in books.items():
        for asset, amt in positions.items():
            usd = amt * prices.get(asset, 0)
            if usd > 0:
                labels.append(f"{book} · {asset}")
                vals.append(usd)
    if not vals:
        return None

    colors = ["#63b3ff","#a78bfa","#34d399","#fb923c","#f472b6",
              "#facc15","#38bdf8","#84cc16","#f87171","#c084fc"]
    fig = go.Figure(go.Pie(
        labels=labels, values=vals,
        hole=0.52,
        marker=dict(colors=colors[:len(vals)], line=dict(color="#0f1117", width=2)),
        textfont=dict(size=11, color="#e2e8f0"),
        hovertemplate="%{label}<br>$%{value:,.2f}<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=36, b=20),
        height=280,
        title=dict(text="Allocation by Book & Asset",
                   font=dict(size=13, color="#94a3b8"), x=0),
        legend=dict(font=dict(size=10, color="#94a3b8"),
                    bgcolor="rgba(0,0,0,0)"),
        showlegend=True,
    )
    return fig


def chart_asset_breakdown(books: dict, prices: dict):
    if not books:
        return None
    assets = {"BTC": 0.0, "ETH": 0.0, "USDT": 0.0}
    for pos in books.values():
        for a, amt in pos.items():
            if a in assets:
                assets[a] += amt * prices.get(a, 0)

    fig = go.Figure(go.Bar(
        x=list(assets.keys()),
        y=list(assets.values()),
        marker_color=["#f7931a","#627eea","#26a17b"],
        text=[f"${v:,.0f}" for v in assets.values()],
        textposition="outside",
        textfont=dict(size=11, color="#94a3b8"),
        hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(**CHART_STYLE,
        title=dict(text="Value by Asset", font=dict(size=13, color="#94a3b8"), x=0),
        yaxis_title="USD Value",
        height=240,
        showlegend=False,
        yaxis_tickformat="$,.0f",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
def build_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="padding:16px 0 12px;border-bottom:1px solid #1e2535;margin-bottom:14px;">
          <div style="font-size:16px;font-weight:700;color:#f1f5f9;letter-spacing:-.02em;">📈 Portfolio Manager</div>
          <div style="font-size:9px;color:#475569;letter-spacing:.1em;text-transform:uppercase;margin-top:3px;">Multi-Book · Real-Time</div>
        </div>
        """, unsafe_allow_html=True)

        def sh(t): st.markdown(
            f'<p style="color:#475569;font-size:10px;letter-spacing:.1em;'
            f'text-transform:uppercase;font-weight:600;border-bottom:1px solid #1e2535;'
            f'padding-bottom:5px;margin-bottom:10px;margin-top:12px;">{t}</p>',
            unsafe_allow_html=True)

        # ── Refresh controls ─────────────────────────────────────────────
        sh("Data Controls")
        refresh = st.button("🔄  Refresh Now", use_container_width=True)
        st.caption("Auto-refresh every 60s when autorefresh is installed")

        # ── IDR Toggle ──────────────────────────────────────────────────
        sh("Currency")
        idr_on = st.toggle("Show values in IDR (Rupiah)", value=st.session_state["show_idr"])
        st.session_state["show_idr"] = idr_on
        idr_data = st.session_state.get("_idr_data", {"rate": st.session_state["idr_rate"],
                                                        "updated": "—", "error": None})
        if idr_on:
            st.markdown(
                f'<div style="font-size:10px;color:#475569;margin-top:-8px;">'
                f'USD/IDR Kurs Tengah (BCA e-Rate): '
                f'<b style="color:#63b3ff;">Rp {idr_data["rate"]:,.0f}</b><br>'
                f'Updated: {idr_data["updated"]}</div>',
                unsafe_allow_html=True
            )
            if idr_data.get("error"):
                st.caption(f"⚠ {idr_data['error']}")

        # ── Trading Books — clickable list with inline edit ──────────────
        sh("Trading Books")

        books = st.session_state["books"]
        prices = st.session_state.get("prices", {"BTC":0,"ETH":0,"USDT":1})
        editing = st.session_state.get("editing_book")

        if not books:
            st.markdown(
                '<div style="font-size:11px;color:#475569;padding:8px 0;">'
                'No books yet — add one below.</div>',
                unsafe_allow_html=True)

        for bname, pos in list(books.items()):
            bval = sum(amt * prices.get(a, 0) for a, amt in pos.items())
            is_editing = (editing == bname)

            # ── Book header row with Edit / Delete buttons ───────────────
            left, mid, right = st.columns([5, 1, 1])
            with left:
                summary = " · ".join(
                    f'{a} {v:,.4g}' for a, v in pos.items() if v > 0
                ) or "empty"
                st.markdown(
                    f'<div style="padding:4px 0;">'
                    f'<div style="font-size:12px;font-weight:600;color:#f1f5f9;">{bname}</div>'
                    f'<div style="font-size:10px;color:#475569;">{summary}</div>'
                    f'<div style="font-size:10px;color:#3b82f6;">${bval:,.2f}</div>'
                    f'</div>', unsafe_allow_html=True)

            with mid:
                if st.button("✏️", key=f"edit_{bname}",
                             help=f"Edit {bname}", use_container_width=True):
                    if editing == bname:
                        st.session_state["editing_book"] = None  # toggle off
                    else:
                        # Pre-fill editor state
                        st.session_state["editing_book"] = bname
                        st.session_state[f"edit_usdt_{bname}"] = pos.get("USDT", 0.0)
                        st.session_state[f"edit_btc_{bname}"]  = pos.get("BTC",  0.0)
                        st.session_state[f"edit_eth_{bname}"]  = pos.get("ETH",  0.0)
                    st.rerun()

            with right:
                if st.button("🗑", key=f"del_{bname}",
                             help=f"Delete {bname}", use_container_width=True):
                    del st.session_state["books"][bname]
                    if st.session_state.get("editing_book") == bname:
                        st.session_state["editing_book"] = None
                    st.rerun()

            # ── Inline editor — expands under the book when ✏️ clicked ──
            if is_editing:
                with st.container():
                    st.markdown(
                        f'<div style="background:#1e2535;border:1px solid #3b82f6;'
                        f'border-radius:8px;padding:12px;margin:4px 0 10px 0;">'
                        f'<div style="font-size:10px;color:#3b82f6;font-weight:600;'
                        f'margin-bottom:8px;letter-spacing:.05em;">EDITING: {bname}</div></div>',
                        unsafe_allow_html=True)

                    ec1, ec2 = st.columns(2)
                    with ec1:
                        new_usdt = st.number_input(
                            "USDT", min_value=0.0,
                            value=float(st.session_state.get(f"edit_usdt_{bname}", pos.get("USDT",0))),
                            step=100.0, format="%.2f",
                            key=f"einp_usdt_{bname}")
                        new_btc = st.number_input(
                            "BTC", min_value=0.0,
                            value=float(st.session_state.get(f"edit_btc_{bname}", pos.get("BTC",0))),
                            step=0.001, format="%.4f",
                            key=f"einp_btc_{bname}")
                    with ec2:
                        new_eth = st.number_input(
                            "ETH", min_value=0.0,
                            value=float(st.session_state.get(f"edit_eth_{bname}", pos.get("ETH",0))),
                            step=0.01, format="%.4f",
                            key=f"einp_eth_{bname}")

                    sa, sc = st.columns(2)
                    with sa:
                        if st.button("💾 Save", key=f"save_{bname}",
                                     use_container_width=True):
                            st.session_state["books"][bname] = {
                                "USDT": new_usdt,
                                "BTC":  new_btc,
                                "ETH":  new_eth,
                            }
                            st.session_state["editing_book"] = None
                            st.rerun()
                    with sc:
                        if st.button("✕ Cancel", key=f"cancel_{bname}",
                                     use_container_width=True):
                            st.session_state["editing_book"] = None
                            st.rerun()

            st.markdown(
                '<div style="border-bottom:1px solid #1e2535;margin:2px 0 6px;"></div>',
                unsafe_allow_html=True)

        # ── Add New Book ────────────────────────────────────────────────
        sh("Add New Book")
        book_name = st.text_input("Book name", placeholder="e.g. Prop Book 1",
                                   key="inp_book_name")
        c1, c2 = st.columns(2)
        with c1:
            usdt_amt = st.number_input("USDT", min_value=0.0, value=0.0,
                                        step=100.0, format="%.2f", key="inp_usdt")
            btc_amt  = st.number_input("BTC",  min_value=0.0, value=0.0,
                                        step=0.001, format="%.4f", key="inp_btc")
        with c2:
            eth_amt  = st.number_input("ETH",  min_value=0.0, value=0.0,
                                        step=0.01, format="%.4f", key="inp_eth")

        if st.button("➕ Add Book", use_container_width=True, key="btn_add_book"):
            name = book_name.strip()
            if name:
                if name in st.session_state["books"]:
                    st.warning(f"'{name}' already exists — use ✏️ to edit it.")
                else:
                    st.session_state["books"][name] = {
                        "USDT": usdt_amt,
                        "BTC":  btc_amt,
                        "ETH":  eth_amt,
                    }
                    st.success(f"✓ Added: {name}")
                    st.rerun()
            else:
                st.error("Enter a book name first.")

        sh("History")
        hist_len = st.slider("Keep last N snapshots", 10, 500, 100, 10)
        if st.button("🗑 Clear History", use_container_width=True):
            st.session_state["history"] = []

        return refresh, hist_len


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    # ── Auto-refresh ───────────────────────────────────────────────────────
    if HAS_AR:
        st_autorefresh(interval=60_000, key="portfolio_ar")

    refresh, hist_len = build_sidebar()

    # ── Fetch prices ───────────────────────────────────────────────────────
    if refresh:
        st.cache_data.clear()

    price_data = fetch_prices()
    prices = {
        "BTC":  price_data["BTC"],
        "ETH":  price_data["ETH"],
        "USDT": price_data["USDT"],
    }
    st.session_state["prices"] = prices

    # ── Fetch IDR rate ─────────────────────────────────────────────────────
    idr_data = fetch_idr_rate()
    st.session_state["_idr_data"] = idr_data
    idr_rate = idr_data["rate"]
    st.session_state["idr_rate"] = idr_rate
    show_idr = st.session_state["show_idr"]

    # ── Record history snapshot ────────────────────────────────────────────
    books = st.session_state["books"]
    if books:
        total_usd = calc_total_usd(books, prices)
        book_vals = {b: calc_book_value(pos, prices) for b, pos in books.items()}
        snap = {
            "ts":           datetime.utcnow().isoformat(),
            "total_usd":    total_usd,
            "book_values":  book_vals,
        }
        hist = st.session_state["history"]
        hist.append(snap)
        if len(hist) > hist_len:
            hist = hist[-hist_len:]
        st.session_state["history"] = hist
    else:
        total_usd = 0.0
        book_vals = {}

    metrics = calc_metrics(st.session_state["history"])

    # ═══════════════════════════════════════════════════════════════════════
    # TOP BAR
    # ═══════════════════════════════════════════════════════════════════════
    currency_label = "IDR" if show_idr else "USD"
    multiplier     = idr_rate if show_idr else 1.0
    fmt_val        = lambda v: f"Rp {v*multiplier:,.0f}" if show_idr else f"${v:,.2f}"

    st.markdown(f"""
    <div class="top-bar">
      <div>
        <div class="top-bar-title">📈 Portfolio Manager</div>
        <div class="top-bar-sub">
          {len(books)} trading book{"s" if len(books)!=1 else ""} ·
          Prices: {price_data.get("source","—")} ·
          <span class="live-dot"></span>{price_data.get("ts","—")}
        </div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:22px;font-weight:800;color:#f1f5f9;font-family:'JetBrains Mono',monospace;">
          {fmt_val(total_usd)}
        </div>
        <div style="font-size:10px;color:#475569;margin-top:2px;">Total Portfolio · {currency_label}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if price_data.get("error"):
        st.error(f"⚠ Price feed error: {price_data['error']}")
    if idr_data.get("error"):
        st.warning(f"⚠ IDR rate: {idr_data['error']} — using Rp {idr_rate:,.0f}")

    if not books:
        st.info("👈 Add your first trading book in the sidebar to get started.", icon="ℹ️")
        st.markdown("""
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:20px;">
          <div style="background:#141820;border:1px solid #1e2535;border-radius:12px;padding:20px;text-align:center;">
            <div style="font-size:24px;margin-bottom:8px;">📚</div>
            <div style="font-size:13px;font-weight:600;color:#f1f5f9;margin-bottom:4px;">Multiple Books</div>
            <div style="font-size:11px;color:#475569;">Track Prop Book, Hedge Book, Personal — separately and combined</div>
          </div>
          <div style="background:#141820;border:1px solid #1e2535;border-radius:12px;padding:20px;text-align:center;">
            <div style="font-size:24px;margin-bottom:8px;">⚡</div>
            <div style="font-size:13px;font-weight:600;color:#f1f5f9;margin-bottom:4px;">Real-Time Prices</div>
            <div style="font-size:11px;color:#475569;">BTC, ETH, USDT from CoinGecko or Binance — auto-refreshed</div>
          </div>
          <div style="background:#141820;border:1px solid #1e2535;border-radius:12px;padding:20px;text-align:center;">
            <div style="font-size:24px;margin-bottom:8px;">🇮🇩</div>
            <div style="font-size:13px;font-weight:600;color:#f1f5f9;margin-bottom:4px;">IDR Toggle</div>
            <div style="font-size:11px;color:#475569;">Switch to Rupiah using live BCA Kurs Tengah e-Rate</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ═══════════════════════════════════════════════════════════════════════
    # LIVE PRICE STRIP
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-head">Live Prices</p>', unsafe_allow_html=True)
    p1, p2, p3, p4, p5 = st.columns(5)

    def price_card(col, label, price, chg, icon=""):
        cls = "up" if chg >= 0 else "down"
        sign = "▲" if chg >= 0 else "▼"
        col.markdown(f"""
        <div class="price-card">
          <div class="price-label">{icon} {label}</div>
          <div class="price-val">${price:,.2f}</div>
          <div class="price-chg {cls}">{sign} {abs(chg):.2f}% 24h</div>
        </div>
        """, unsafe_allow_html=True)

    price_card(p1, "Bitcoin",  prices["BTC"],  price_data.get("BTC_chg", 0),  "₿")
    price_card(p2, "Ethereum", prices["ETH"],  price_data.get("ETH_chg", 0),  "Ξ")
    price_card(p3, "USDT",     prices["USDT"], 0.0,                           "💵")

    # IDR equivalents
    p4.markdown(f"""
    <div class="price-card">
      <div class="price-label">🇮🇩 BTC/IDR</div>
      <div class="price-val" style="font-size:14px;">Rp {prices["BTC"]*idr_rate:,.0f}</div>
      <div class="price-chg neutral">Kurs Tengah BCA</div>
    </div>
    """, unsafe_allow_html=True)

    p5.markdown(f"""
    <div class="price-card">
      <div class="price-label">🇮🇩 ETH/IDR</div>
      <div class="price-val" style="font-size:14px;">Rp {prices["ETH"]*idr_rate:,.0f}</div>
      <div class="price-chg neutral">USD/IDR: {idr_rate:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # PORTFOLIO KPI CARDS
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-head">Portfolio Overview</p>', unsafe_allow_html=True)
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    with k1:
        st.metric("Total Value",
                  f"Rp {total_usd*multiplier:,.0f}" if show_idr else f"${total_usd:,.2f}")
    with k2:
        btc_total = sum(b.get("BTC", 0) for b in books.values())
        st.metric("Total BTC", f"{btc_total:.4f}",
                  delta=f"≈ ${btc_total*prices['BTC']:,.0f}")
    with k3:
        eth_total = sum(b.get("ETH", 0) for b in books.values())
        st.metric("Total ETH", f"{eth_total:.4f}",
                  delta=f"≈ ${eth_total*prices['ETH']:,.0f}")
    with k4:
        usdt_total = sum(b.get("USDT", 0) for b in books.values())
        st.metric("Total USDT", f"{usdt_total:,.2f}",
                  delta=f"≈ ${usdt_total:,.0f}")
    with k5:
        st.metric("Trading Books", len(books),
                  delta=f"{sum(1 for b in books.values() if any(v>0 for v in b.values()))} active")
    with k6:
        n_snaps = len(st.session_state["history"])
        st.metric("History Snapshots", n_snaps,
                  delta=f"~{n_snaps} min tracked")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # TRADING BOOKS BREAKDOWN
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-head">Trading Books</p>', unsafe_allow_html=True)
    book_cols = st.columns(min(len(books), 4))
    for idx, (bname, pos) in enumerate(books.items()):
        bval = calc_book_value(pos, prices)
        pct  = bval / total_usd * 100 if total_usd > 0 else 0
        with book_cols[idx % 4]:
            rows_html = ""
            for asset, amt in pos.items():
                if amt > 0:
                    usd_val = amt * prices.get(asset, 0)
                    rows_html += (
                        f'<div class="book-row">'
                        f'<span class="book-asset">{asset}</span>'
                        f'<span class="book-amount">{amt:,.4g}</span>'
                        f'<span class="book-value">${usd_val:,.2f}</span>'
                        f'</div>'
                    )
            disp_val = (f"Rp {bval*multiplier:,.0f}" if show_idr
                        else f"${bval:,.2f}")
            st.markdown(f"""
            <div class="book-card">
              <div class="book-name">{bname}
                <span style="font-size:11px;color:#475569;font-weight:400;"> · {pct:.1f}%</span>
              </div>
              {rows_html}
              <div style="margin-top:8px;padding-top:8px;border-top:1px solid #1e2535;
                          display:flex;justify-content:space-between;">
                <span style="font-size:10px;color:#475569;">Total</span>
                <span style="font-size:14px;font-weight:700;color:#63b3ff;
                             font-family:'JetBrains Mono',monospace;">{disp_val}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # RISK METRICS
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-head">Risk & Performance Metrics</p>',
                unsafe_allow_html=True)

    if not metrics:
        st.info("Accumulating data — metrics appear after 2+ snapshots (~2 minutes).", icon="⏳")
    else:
        signal_label, signal_cls, signal_emoji = metrics["signal"]
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;">
          <div class="risk-badge {signal_cls}">
            {signal_emoji} {signal_label}
          </div>
          <div style="font-size:12px;color:#475569;">
            Risk score: {metrics["score"]:+d} / 5 &nbsp;·&nbsp;
            Based on Sharpe, drawdown, current DD, volatility, return direction
          </div>
        </div>
        """, unsafe_allow_html=True)

        m1,m2,m3,m4 = st.columns(4)
        m5,m6,m7,m8 = st.columns(4)

        def mcard(col, label, val, sub="", color="#f1f5f9"):
            col.markdown(f"""
            <div class="metric-box">
              <div class="label">{label}</div>
              <div class="val" style="color:{color};">{val}</div>
              <div class="sub">{sub}</div>
            </div>
            """, unsafe_allow_html=True)

        dd_col  = "#ef4444" if metrics["max_drawdown"] < -20 else (
                   "#eab308" if metrics["max_drawdown"] < -10 else "#22c55e")
        ret_col = "#22c55e" if metrics["total_ret"] >= 0 else "#ef4444"
        sh_col  = "#22c55e" if metrics["sharpe"] > 1 else (
                   "#eab308" if metrics["sharpe"] > 0 else "#ef4444")
        vol_col = "#ef4444" if metrics["volatility"] > 60 else (
                   "#eab308" if metrics["volatility"] > 30 else "#22c55e")

        mcard(m1, "Total Return",   f"{metrics['total_ret']:+.2f}%",    "Since first snapshot", ret_col)
        mcard(m2, "Max Profit",     f"{metrics['max_profit']:+.2f}%",   "Peak from start",      "#22c55e")
        mcard(m3, "Max Drawdown",   f"{metrics['max_drawdown']:.2f}%",  "Peak-to-trough",       dd_col)
        mcard(m4, "Current DD",     f"{metrics['current_dd']:.2f}%",    "From last peak",
              "#ef4444" if metrics["current_dd"] < -5 else "#94a3b8")

        mcard(m5, "Sharpe Ratio",   f"{metrics['sharpe']:.3f}",
              "> 1.5 = strong · < 0 = weak", sh_col)
        mcard(m6, "Sortino Ratio",  f"{metrics['sortino']:.3f}",
              "Downside-adjusted Sharpe", "#94a3b8")
        mcard(m7, "Calmar Ratio",   f"{metrics['calmar']:.3f}",
              "Return / |Max DD|", "#94a3b8")
        mcard(m8, "Volatility",     f"{metrics['volatility']:.1f}%",
              "Annualised (288×/day)", vol_col)

        # ── Risk signal explanation ────────────────────────────────────
        explain = {
            "RISK-ON": (
                "Portfolio metrics are strong across multiple dimensions. "
                "Sharpe ratio indicates good risk-adjusted returns, drawdown is "
                "contained, and the overall trend is positive. "
                "Suitable for maintaining or increasing exposure."
            ),
            "RISK-OFF": (
                "One or more critical risk metrics are deteriorating — elevated drawdown, "
                "negative Sharpe, or high volatility. "
                "Consider reducing exposure, tightening stops, or moving to USDT."
            ),
            "NEUTRAL": (
                "Mixed signals — some metrics are positive, others neutral or slightly negative. "
                "No strong directional edge in either risk-on or risk-off direction. "
                "Maintain current allocation but monitor closely."
            ),
        }
        with st.expander("📖 What does this signal mean?", expanded=False):
            st.markdown(
                f'<div style="font-size:13px;color:#94a3b8;line-height:1.7;">'
                f'{explain[signal_label]}</div>',
                unsafe_allow_html=True
            )

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # CHARTS
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-head">Charts</p>', unsafe_allow_html=True)
    tab_time, tab_dd, tab_alloc, tab_assets = st.tabs([
        "📈 Portfolio Over Time",
        "📉 Drawdown",
        "🥧 Allocation",
        "📊 By Asset",
    ])

    with tab_time:
        fig = chart_portfolio_over_time(
            st.session_state["history"], show_idr, idr_rate)
        if fig:
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.info("Chart appears after 2+ data snapshots.", icon="📈")

    with tab_dd:
        fig = chart_drawdown(st.session_state["history"])
        if fig:
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.info("Chart appears after 3+ data snapshots.", icon="📉")

    with tab_alloc:
        fig = chart_allocation(books, prices)
        if fig:
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.info("Add holdings to see allocation chart.", icon="🥧")

    with tab_assets:
        fig = chart_asset_breakdown(books, prices)
        if fig:
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.info("Add holdings to see breakdown.", icon="📊")

    # ═══════════════════════════════════════════════════════════════════════
    # HISTORY TABLE
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("📋  Snapshot History", expanded=False):
        if st.session_state["history"]:
            hist_df = pd.DataFrame([
                {
                    "Time (UTC)": h["ts"],
                    "Total USD": round(h["total_usd"], 2),
                    **{f"{k} (USD)": round(v, 2)
                       for k, v in h.get("book_values", {}).items()},
                }
                for h in st.session_state["history"]
            ])
            hist_df = hist_df.iloc[::-1].reset_index(drop=True)
            hist_df.index += 1
            st.dataframe(hist_df, use_container_width=True, height=300)
        else:
            st.info("No history yet.", icon="ℹ️")

    st.markdown("""
    <div class="footer">
      Portfolio Manager · Prices: CoinGecko / Binance (free, no API key required) ·
      IDR Rate: BCA e-Rate Kurs Tengah · Not financial advice ·
      Data refreshes every 60 seconds
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
