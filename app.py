"""
Portfolio Manager v3
─────────────────────────────────────────────────────────
Layout: CoinGecko-inspired, light theme
Persistence: JSON file on disk (survives browser refresh)
Data: CoinGecko → Binance fallback | BCA Kurs Tengah for IDR
"""

import io, json, os, re, time, requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
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
# PERSISTENT STORAGE  — JSON file, survives browser refresh / F5
# ─────────────────────────────────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_data.json")

def load_persistent() -> tuple:
    """
    Read books + history from disk.
    Returns (books_dict, history_list) — both empty on any error.
    History entries older than 7 days are pruned on load.
    """
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            books = data.get("books", {})
            raw_hist = data.get("history", [])
            # Prune snapshots older than 7 days to keep file size sane
            cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
            history = [h for h in raw_hist if h.get("ts", "") >= cutoff]
            return books, history
    except Exception:
        pass
    return {}, []

def save_persistent(books: dict, history: list = None):
    """
    Write books (and optionally history) to disk immediately.
    If history is None, preserves whatever history is already on disk.
    """
    try:
        # Read existing data so we don't wipe history when saving only books
        existing = {}
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    existing = json.load(f)
            except Exception:
                pass
        payload = {
            "books":    books,
            "history":  history if history is not None else existing.get("history", []),
            "saved_at": datetime.utcnow().isoformat(),
        }
        with open(DATA_FILE, "w") as f:
            json.dump(payload, f)
    except Exception as e:
        st.warning(f"⚠ Could not save to disk: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# LIGHT THEME
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

html,body,.stApp{font-family:'Inter',sans-serif!important;background:#f7f8fc;color:#1a1f36;}
.main .block-container{padding-top:0!important;padding-bottom:2rem;max-width:1560px;}

/* Sidebar */
[data-testid="stSidebar"]{background:#ffffff;border-right:1px solid #e3e8f0;box-shadow:2px 0 8px rgba(0,0,0,.04);}
[data-testid="stSidebar"] *{color:#1a1f36!important;}
[data-testid="stSidebar"] .stMarkdown p{color:#8898aa!important;font-size:10px;letter-spacing:.1em;text-transform:uppercase;font-weight:600;}
[data-testid="stSidebar"] input,[data-testid="stSidebar"] textarea{background:#f7f8fc!important;border:1px solid #dde3ed!important;color:#1a1f36!important;border-radius:7px!important;font-size:12px!important;}
[data-testid="stSidebar"] [data-baseweb="select"]>div{background:#f7f8fc!important;border-color:#dde3ed!important;}

/* Top stat bar */
.stat-bar{background:#ffffff;border-bottom:1px solid #e3e8f0;padding:14px 28px;display:flex;align-items:stretch;gap:0;}
.stat-item{padding:0 28px;border-right:1px solid #edf0f7;flex:1;}
.stat-item:first-child{padding-left:0;}
.stat-item:last-child{border-right:none;}
.stat-label{font-size:11px;font-weight:600;color:#8898aa;letter-spacing:.06em;text-transform:uppercase;margin-bottom:3px;}
.stat-val{font-size:22px;font-weight:800;color:#1a1f36;font-family:'JetBrains Mono',monospace;letter-spacing:-.02em;line-height:1;}
.stat-sub{font-size:12px;font-weight:500;margin-top:3px;}
.up{color:#0ecb81;}.down{color:#f6465d;}.muted{color:#8898aa;}

/* Section labels */
.sec-head{font-size:11px;font-weight:700;color:#8898aa;letter-spacing:.1em;text-transform:uppercase;border-bottom:1px solid #e3e8f0;padding-bottom:7px;margin:18px 0 12px;}

/* Price ticker cards */
.ticker-wrap{display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap;}
.ticker-card{background:#ffffff;border:1px solid #e3e8f0;border-radius:10px;padding:11px 16px;min-width:150px;flex:1;box-shadow:0 1px 4px rgba(26,31,54,.05);}
.ticker-symbol{font-size:11px;font-weight:700;color:#8898aa;letter-spacing:.06em;text-transform:uppercase;margin-bottom:3px;}
.ticker-price{font-size:17px;font-weight:700;color:#1a1f36;font-family:'JetBrains Mono',monospace;}
.ticker-chg{font-size:11px;font-weight:600;margin-top:2px;}

/* Book table */
.book-table{width:100%;border-collapse:collapse;font-size:13px;}
.book-table thead th{background:#f7f8fc;color:#8898aa;font-weight:600;font-size:11px;letter-spacing:.06em;text-transform:uppercase;padding:9px 14px;text-align:left;border-bottom:2px solid #e3e8f0;}
.book-table thead th.right{text-align:right;}
.book-table tbody td{padding:12px 14px;border-bottom:1px solid #edf0f7;vertical-align:middle;}
.book-table tbody td.right{text-align:right;font-family:'JetBrains Mono',monospace;}
.book-table tbody tr:hover td{background:#f7f8fc;}
.book-tag{display:inline-block;background:#eff2ff;color:#3b5af5;border-radius:5px;padding:2px 9px;font-size:11px;font-weight:700;}
.asset-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;}

/* Metric boxes */
.metric-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:12px 0;}
.mbox{background:#ffffff;border:1px solid #e3e8f0;border-radius:10px;padding:14px 16px;box-shadow:0 1px 4px rgba(26,31,54,.04);}
.mbox-label{font-size:10px;font-weight:600;color:#8898aa;letter-spacing:.08em;text-transform:uppercase;margin-bottom:5px;}
.mbox-val{font-size:20px;font-weight:700;font-family:'JetBrains Mono',monospace;color:#1a1f36;line-height:1;}
.mbox-sub{font-size:10px;color:#8898aa;margin-top:3px;}

/* Risk badge */
.risk-badge{display:inline-flex;align-items:center;gap:8px;padding:7px 18px;border-radius:8px;font-weight:700;font-size:13px;}
.risk-on{background:#e8fcf4;color:#0ecb81;border:1px solid #b7efda;}
.risk-off{background:#fff1f2;color:#f6465d;border:1px solid #fdc9cd;}
.risk-neutral{background:#fffbeb;color:#d97706;border:1px solid #fde68a;}

/* Buttons */
.stButton>button{background:#ffffff!important;color:#1a1f36!important;border:1px solid #dde3ed!important;border-radius:8px!important;font-size:12px!important;font-weight:500!important;transition:all .15s!important;box-shadow:0 1px 3px rgba(26,31,54,.06)!important;}
.stButton>button:hover{background:#f0f3ff!important;border-color:#3b5af5!important;color:#3b5af5!important;}

[data-testid="stMetric"]{background:#ffffff;border:1px solid #e3e8f0;border-radius:10px;padding:14px 18px;box-shadow:0 1px 4px rgba(26,31,54,.04);}
[data-testid="stMetric"] label{color:#8898aa!important;font-size:10px!important;letter-spacing:.08em;text-transform:uppercase;font-weight:600;}
[data-testid="stMetricValue"]{color:#1a1f36!important;font-size:1.4rem!important;font-weight:700!important;font-family:'JetBrains Mono',monospace!important;}
[data-testid="stMetricDelta"] svg{display:none;}
[data-testid="stMetricDelta"]{font-size:12px!important;font-weight:600!important;}

[data-testid="stInfo"]{background:#eff5ff!important;border:1px solid #c7d9ff!important;border-radius:8px!important;color:#3b5af5!important;}
[data-testid="stSuccess"]{background:#e8fcf4!important;border:1px solid #b7efda!important;border-radius:8px!important;color:#059669!important;}
[data-testid="stWarning"]{background:#fffbeb!important;border:1px solid #fde68a!important;border-radius:8px!important;}

.stTabs [data-baseweb="tab-list"]{background:#f7f8fc!important;border-radius:10px!important;border:1px solid #e3e8f0!important;padding:3px!important;}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:#8898aa!important;border-radius:7px!important;font-size:12px!important;font-weight:500!important;}
.stTabs [aria-selected="true"]{background:#ffffff!important;color:#1a1f36!important;box-shadow:0 1px 3px rgba(26,31,54,.08)!important;}

hr{border:none;border-top:1px solid #e3e8f0;margin:.8rem 0;}
.footer{font-size:10px;color:#c4cdd8;text-align:center;margin-top:24px;padding-top:14px;border-top:1px solid #e3e8f0;}
</style>
""", unsafe_allow_html=True)

CHART_STYLE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#ffffff",
    font=dict(family="Inter,sans-serif", color="#8898aa", size=11),
    margin=dict(l=52, r=20, t=36, b=40),
    xaxis=dict(gridcolor="#f0f2f8", linecolor="#e3e8f0",
               tickfont=dict(size=10, color="#aab0c0"), showgrid=True),
    yaxis=dict(gridcolor="#f0f2f8", linecolor="#e3e8f0",
               tickfont=dict(size=10, color="#aab0c0"), showgrid=True),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#8898aa")),
    hoverlabel=dict(bgcolor="#1a1f36", bordercolor="#3b5af5",
                    font=dict(family="JetBrains Mono", size=12, color="#fff")),
)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
def init_state():
    if "books_loaded" not in st.session_state:
        # Load books AND history from disk on first run (browser refresh safe)
        books, history = load_persistent()
        st.session_state["books"]       = books
        st.session_state["history"]     = history
        st.session_state["books_loaded"]= True
    defaults = {
        "history":      [],
        "show_idr":     False,
        "idr_rate":     17520.0,
        "prices":       {"BTC": 95000.0, "ETH": 3500.0, "USDT": 1.0},
        "editing_book": None,
        "_idr_data":    {"rate": 17520.0, "updated": "—", "error": None},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ─────────────────────────────────────────────────────────────────────────────
# PRICE FETCHING
# ─────────────────────────────────────────────────────────────────────────────
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum,tether&vs_currencies=usd&include_24hr_change=true"
)

@st.cache_data(ttl=60, show_spinner=False)
def fetch_prices() -> dict:
    _cg_err_msg = "not tried"
    try:
        r = requests.get(COINGECKO_URL,
                         headers={"User-Agent": "PortfolioManager/3.0"},
                         timeout=8)
        r.raise_for_status()
        d = r.json()
        return {
            "BTC": d["bitcoin"]["usd"], "ETH": d["ethereum"]["usd"],
            "USDT": d["tether"]["usd"],
            "BTC_chg":  d["bitcoin"].get("usd_24h_change", 0),
            "ETH_chg":  d["ethereum"].get("usd_24h_change", 0),
            "USDT_chg": 0.0,
            "source": "CoinGecko",
            "ts": datetime.utcnow().strftime("%H:%M UTC"),
            "error": None,
        }
    except Exception as cg_err:
        _cg_err_msg = str(cg_err)[:60]

    try:
        def bp(sym):
            r2 = requests.get(
                f"https://api.binance.com/api/v3/ticker/24hr?symbol={sym}",
                timeout=8)
            d2 = r2.json()
            return float(d2["lastPrice"]), float(d2["priceChangePercent"])
        btc, bc = bp("BTCUSDT")
        eth, ec = bp("ETHUSDT")
        return {"BTC": btc, "ETH": eth, "USDT": 1.0,
                "BTC_chg": bc, "ETH_chg": ec, "USDT_chg": 0.0,
                "source": "Binance", "ts": datetime.utcnow().strftime("%H:%M UTC"),
                "error": None}
    except Exception as bn_err:
        _bn_err_msg = str(bn_err)[:60]
        cached = st.session_state.get("prices", {"BTC": 95000, "ETH": 3500})
        return {"BTC": cached.get("BTC", 95000), "ETH": cached.get("ETH", 3500),
                "USDT": 1.0, "BTC_chg": 0.0, "ETH_chg": 0.0, "USDT_chg": 0.0,
                "source": "cached", "ts": "—",
                "error": f"CoinGecko: {_cg_err_msg} | Binance: {_bn_err_msg}"}

# ─────────────────────────────────────────────────────────────────────────────
# IDR RATE
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_idr_rate() -> dict:
    FALLBACK = {"rate": 17520.0, "buy": 17445.0, "sell": 17595.0,
                "updated": "16 May 2026 (fallback)", "error": None}
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "id-ID,id;q=0.9"}
        r = requests.get("https://www.bca.co.id/id/informasi/kurs",
                         headers=headers, timeout=15)
        r.raise_for_status()
        tables = pd.read_html(io.StringIO(r.text))
        for t in tables:
            if isinstance(t.columns, pd.MultiIndex):
                t.columns = [" ".join(str(c) for c in col).strip() for col in t.columns]
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
                        return {"rate": (buy+sell)/2, "buy": buy, "sell": sell,
                                "updated": datetime.now().strftime("%d %b %Y %H:%M"),
                                "error": None}
        return {**FALLBACK, "error": "USD row not found"}
    except Exception as ex:
        return {**FALLBACK, "error": str(ex)[:80]}

# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO MATH
# ─────────────────────────────────────────────────────────────────────────────
def book_value(pos: dict, prices: dict) -> float:
    return sum(amt * prices.get(a, 0) for a, amt in pos.items())

def total_usd(books: dict, prices: dict) -> float:
    return sum(book_value(p, prices) for p in books.values())

def calc_metrics(history: list) -> dict:
    if len(history) < 2:
        return {}
    vals = np.array([h["total_usd"] for h in history], dtype=float)
    rets = np.diff(vals) / np.where(vals[:-1] != 0, vals[:-1], 1)
    rets = rets[np.isfinite(rets)]
    if not len(rets):
        return {}
    peak      = np.maximum.accumulate(vals)
    dd        = (vals - peak) / np.where(peak != 0, peak, 1)
    max_dd    = float(dd.min())
    cur_dd    = float(dd[-1])
    tot_ret   = (vals[-1] - vals[0]) / vals[0] if vals[0] else 0
    max_prof  = (np.max(vals) - vals[0]) / vals[0] if vals[0] else 0
    mu, std   = float(np.mean(rets)), float(np.std(rets, ddof=1)) if len(rets)>1 else 0
    sharpe    = mu / std * np.sqrt(288) if std else 0
    neg       = rets[rets < 0]
    dstd      = float(np.std(neg, ddof=1)) if len(neg)>1 else 0
    sortino   = mu / dstd * np.sqrt(288) if dstd else 0
    calmar    = tot_ret / abs(max_dd) if abs(max_dd) > 1e-6 else 0
    vol_ann   = std * np.sqrt(288) * 100

    score = 0
    score += 1 if sharpe > 1.5   else (-1 if sharpe < 0.3 else 0)
    score += 1 if max_dd > -0.10 else (-1 if max_dd < -0.25 else 0)
    score += 1 if cur_dd > -0.05 else (-1 if cur_dd < -0.15 else 0)
    score += 1 if vol_ann < 30   else (-1 if vol_ann > 60 else 0)
    score += 1 if tot_ret > 0    else -1

    if   score >= 3:  sig = ("RISK-ON",  "risk-on",  "🟢")
    elif score <= -2: sig = ("RISK-OFF", "risk-off", "🔴")
    else:             sig = ("NEUTRAL",  "risk-neutral", "🟡")

    return dict(total_ret=tot_ret*100, max_profit=max_prof*100,
                max_drawdown=max_dd*100, current_dd=cur_dd*100,
                sharpe=sharpe, sortino=sortino, calmar=calmar,
                volatility=vol_ann, signal=sig, score=score)

# ─────────────────────────────────────────────────────────────────────────────
# CHARTS
# ─────────────────────────────────────────────────────────────────────────────
def chart_portfolio(history, show_idr, idr_rate, books):
    if len(history) < 2:
        return None
    df  = pd.DataFrame(history)
    df["ts"] = pd.to_datetime(df["ts"])
    mul  = idr_rate if show_idr else 1
    unit = "IDR" if show_idr else "USD"

    fig = go.Figure()
    # Total fill area
    fig.add_trace(go.Scatter(
        x=df["ts"], y=df["total_usd"] * mul,
        mode="lines", name=f"Total ({unit})",
        line=dict(color="#3b5af5", width=2.5),
        fill="tozeroy", fillcolor="rgba(59,90,245,0.06)",
        hovertemplate=f"%{{x|%H:%M:%S}}<br>%{{y:,.2f}} {unit}<extra>Total</extra>",
    ))
    # Per-book lines
    colors = ["#0ecb81","#f0a500","#f6465d","#a78bfa","#06b6d4","#84cc16"]
    if "book_values" in df.columns:
        try:
            bdf = df["book_values"].apply(pd.Series)
            for i, bk in enumerate(bdf.columns):
                fig.add_trace(go.Scatter(
                    x=df["ts"], y=bdf[bk]*mul,
                    mode="lines", name=bk,
                    line=dict(color=colors[i % len(colors)], width=1.5, dash="dot"),
                    hovertemplate=f"%{{x|%H:%M:%S}}<br>%{{y:,.2f}} {unit}<extra>{bk}</extra>",
                ))
        except Exception:
            pass

    fig.update_layout(**CHART_STYLE,
        title=dict(text="Portfolio Value — All Books Combined",
                   font=dict(size=14, color="#1a1f36", weight=700), x=0),
        yaxis_title=f"Value ({unit})", height=300, yaxis_tickformat=",.0f",
    )
    return fig


def chart_drawdown(history):
    if len(history) < 3:
        return None
    vals = np.array([h["total_usd"] for h in history], dtype=float)
    ts   = pd.to_datetime([h["ts"] for h in history])
    peak = np.maximum.accumulate(vals)
    dd   = (vals - peak) / np.where(peak != 0, peak, 1) * 100
    fig  = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts, y=dd, mode="lines", name="Drawdown",
        line=dict(color="#f6465d", width=1.5),
        fill="tozeroy", fillcolor="rgba(246,70,93,0.07)",
        hovertemplate="%{x|%H:%M:%S}<br>%{y:.2f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="#e3e8f0", line_width=1)
    fig.update_layout(**CHART_STYLE,
        title=dict(text="Drawdown (%)", font=dict(size=13, color="#1a1f36"), x=0),
        height=190, yaxis_title="Drawdown (%)",
    )
    return fig


def chart_allocation(books, prices):
    labels, vals, colors = [], [], []
    palette = ["#3b5af5","#0ecb81","#f0a500","#f6465d","#a78bfa","#06b6d4"]
    ci = 0
    for bname, pos in books.items():
        for asset, amt in pos.items():
            usd = amt * prices.get(asset, 0)
            if usd > 0:
                labels.append(f"{bname} · {asset}")
                vals.append(usd)
                colors.append(palette[ci % len(palette)])
                ci += 1
    if not vals:
        return None
    fig = go.Figure(go.Pie(
        labels=labels, values=vals, hole=0.55,
        marker=dict(colors=colors, line=dict(color="#ffffff", width=2.5)),
        textfont=dict(size=11),
        hovertemplate="%{label}<br>$%{value:,.2f}<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=30, b=10), height=270,
        title=dict(text="Allocation", font=dict(size=13, color="#1a1f36"), x=0),
        legend=dict(font=dict(size=10, color="#8898aa"), bgcolor="rgba(0,0,0,0)"),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
def build_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="padding:16px 0 12px;border-bottom:1px solid #e3e8f0;margin-bottom:14px;">
          <div style="font-size:16px;font-weight:800;color:#1a1f36;letter-spacing:-.03em;">📈 Portfolio Manager</div>
          <div style="font-size:9px;color:#8898aa;letter-spacing:.1em;text-transform:uppercase;margin-top:3px;">Multi-Book · Real-Time · Persistent</div>
        </div>
        """, unsafe_allow_html=True)

        def sh(t): st.markdown(
            f'<p style="color:#8898aa;font-size:10px;letter-spacing:.1em;text-transform:uppercase;'
            f'font-weight:600;border-bottom:1px solid #e3e8f0;padding-bottom:5px;margin-bottom:10px;'
            f'margin-top:12px;">{t}</p>', unsafe_allow_html=True)

        # Data controls
        sh("Data Controls")
        refresh = st.button("🔄  Refresh Prices", use_container_width=True)
        st.caption("Books are auto-saved to disk — safe to refresh anytime")

        # IDR toggle
        sh("Currency")
        idr_on  = st.toggle("Show in IDR (Rupiah)", value=st.session_state["show_idr"])
        st.session_state["show_idr"] = idr_on
        idr_d   = st.session_state.get("_idr_data", {"rate": 17520.0, "updated": "—", "error": None})
        if idr_on:
            st.markdown(
                f'<div style="font-size:10px;color:#8898aa;margin-top:-6px;">'
                f'Kurs Tengah BCA e-Rate: <b style="color:#3b5af5;">Rp {idr_d["rate"]:,.0f}</b><br>'
                f'Updated: {idr_d["updated"]}</div>', unsafe_allow_html=True)
            if idr_d.get("error"):
                st.caption(f"⚠ {idr_d['error']}")

        # ── Book list with inline edit ─────────────────────────────────
        sh("Trading Books")
        books   = st.session_state["books"]
        prices  = st.session_state.get("prices", {"BTC": 95000, "ETH": 3500, "USDT": 1})
        editing = st.session_state.get("editing_book")

        if not books:
            st.markdown('<div style="font-size:11px;color:#aab0c0;padding:6px 0;">No books yet.</div>',
                        unsafe_allow_html=True)

        for bname, pos in list(books.items()):
            bval = book_value(pos, prices)
            is_ed = (editing == bname)

            col_info, col_edit, col_del = st.columns([5, 1, 1])
            with col_info:
                summary = " · ".join(f"{a} {v:,.4g}" for a, v in pos.items() if v > 0) or "empty"
                st.markdown(
                    f'<div style="padding:3px 0;">'
                    f'<div style="font-size:12px;font-weight:700;color:#1a1f36;">{bname}</div>'
                    f'<div style="font-size:10px;color:#8898aa;">{summary}</div>'
                    f'<div style="font-size:11px;color:#3b5af5;font-weight:600;">${bval:,.2f}</div>'
                    f'</div>', unsafe_allow_html=True)
            with col_edit:
                if st.button("✏️", key=f"ed_{bname}", help="Edit", use_container_width=True):
                    st.session_state["editing_book"] = None if is_ed else bname
                    if not is_ed:
                        st.session_state[f"ev_usdt_{bname}"] = pos.get("USDT", 0.0)
                        st.session_state[f"ev_btc_{bname}"]  = pos.get("BTC",  0.0)
                        st.session_state[f"ev_eth_{bname}"]  = pos.get("ETH",  0.0)
                    st.rerun()
            with col_del:
                if st.button("🗑", key=f"rm_{bname}", help="Delete", use_container_width=True):
                    del st.session_state["books"][bname]
                    save_persistent(st.session_state["books"])
                    if editing == bname:
                        st.session_state["editing_book"] = None
                    st.rerun()

            if is_ed:
                st.markdown(
                    f'<div style="background:#f0f3ff;border:1px solid #3b5af5;border-radius:8px;'
                    f'padding:10px 12px;margin:4px 0 8px;">'
                    f'<div style="font-size:10px;color:#3b5af5;font-weight:700;margin-bottom:8px;">'
                    f'EDITING: {bname}</div></div>', unsafe_allow_html=True)
                ec1, ec2 = st.columns(2)
                with ec1:
                    nu = st.number_input("USDT", min_value=0.0,
                        value=float(st.session_state.get(f"ev_usdt_{bname}", pos.get("USDT",0))),
                        step=100.0, format="%.2f", key=f"ei_usdt_{bname}")
                    nb = st.number_input("BTC", min_value=0.0,
                        value=float(st.session_state.get(f"ev_btc_{bname}", pos.get("BTC",0))),
                        step=0.001, format="%.4f", key=f"ei_btc_{bname}")
                with ec2:
                    ne = st.number_input("ETH", min_value=0.0,
                        value=float(st.session_state.get(f"ev_eth_{bname}", pos.get("ETH",0))),
                        step=0.01, format="%.4f", key=f"ei_eth_{bname}")
                s1, s2 = st.columns(2)
                with s1:
                    if st.button("💾 Save", key=f"sv_{bname}", use_container_width=True):
                        st.session_state["books"][bname] = {
                            "USDT": nu, "BTC": nb, "ETH": ne}
                        save_persistent(st.session_state["books"])   # ← persist to disk
                        st.session_state["editing_book"] = None
                        st.rerun()
                with s2:
                    if st.button("✕", key=f"cx_{bname}", use_container_width=True):
                        st.session_state["editing_book"] = None
                        st.rerun()

            st.markdown('<div style="border-bottom:1px solid #edf0f7;margin:3px 0 7px;"></div>',
                        unsafe_allow_html=True)

        # ── Add New Book — single button, expands inline, resets on save ───
        # Track whether the add-form is open and a version key for resetting
        if "add_form_open" not in st.session_state:
            st.session_state["add_form_open"] = False
        if "add_form_ver" not in st.session_state:
            st.session_state["add_form_ver"] = 0

        st.markdown(
            '<div style="border-top:1px solid #e3e8f0;margin:10px 0 8px;"></div>',
            unsafe_allow_html=True)

        # Single toggle button
        btn_label = "✕ Cancel" if st.session_state["add_form_open"] else "＋ Add New Book"
        if st.button(btn_label, use_container_width=True, key="btn_toggle_add"):
            st.session_state["add_form_open"] = not st.session_state["add_form_open"]
            st.rerun()

        if st.session_state["add_form_open"]:
            ver = st.session_state["add_form_ver"]   # bump this to reset all fields

            st.markdown(
                '<div style="background:#f7f8fc;border:1px solid #dde3ed;border-radius:8px;'
                'padding:12px;margin-top:6px;">',
                unsafe_allow_html=True)

            new_name = st.text_input(
                "Book name",
                placeholder="e.g. Prop Desk",
                key=f"inp_bname_{ver}",
            )

            # Text inputs for amounts — shows empty with grayed placeholder
            # Parse to float ourselves so we control the UX completely
            def parse_amount(raw: str, default: float = 0.0) -> float:
                try:
                    v = float(raw.replace(",", ".").strip())
                    return max(0.0, v)
                except (ValueError, AttributeError):
                    return default

            c1, c2 = st.columns(2)
            with c1:
                raw_usdt = st.text_input(
                    "USDT", placeholder="0.00000000",
                    key=f"inp_usdt_{ver}")
                raw_btc  = st.text_input(
                    "BTC",  placeholder="0.00000000",
                    key=f"inp_btc_{ver}")
            with c2:
                raw_eth  = st.text_input(
                    "ETH",  placeholder="0.00000000",
                    key=f"inp_eth_{ver}")

            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("💾 Save Book", use_container_width=True, key=f"btn_save_new_{ver}"):
                nm = new_name.strip()
                if not nm:
                    st.error("Enter a book name.")
                elif nm in st.session_state["books"]:
                    st.warning("Already exists — use ✏️ to edit.")
                else:
                    st.session_state["books"][nm] = {
                        "USDT": parse_amount(raw_usdt),
                        "BTC":  parse_amount(raw_btc),
                        "ETH":  parse_amount(raw_eth),
                    }
                    save_persistent(st.session_state["books"])
                    # Reset: close form and bump version so all keys are fresh
                    st.session_state["add_form_open"] = False
                    st.session_state["add_form_ver"]  = ver + 1
                    st.rerun()

        sh("History")
        hist_len = st.slider("Keep last N snapshots", 10, 500, 100, 10)
        if st.button("🗑 Clear History", use_container_width=True):
            st.session_state["history"] = []
            save_persistent(st.session_state["books"], [])   # wipe history on disk too

        return refresh, hist_len


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    if HAS_AR:
        st_autorefresh(interval=60_000, key="portfolio_ar")

    refresh, hist_len = build_sidebar()
    if refresh:
        st.cache_data.clear()

    # Fetch live data
    price_data = fetch_prices()
    prices = {"BTC": price_data["BTC"], "ETH": price_data["ETH"], "USDT": price_data["USDT"]}
    st.session_state["prices"] = prices
    idr_data = fetch_idr_rate()
    st.session_state["_idr_data"] = idr_data
    idr_rate = idr_data["rate"]
    st.session_state["idr_rate"] = idr_rate
    show_idr  = st.session_state["show_idr"]
    multiplier = idr_rate if show_idr else 1.0
    unit = "IDR" if show_idr else "USD"
    books = st.session_state["books"]

    def fv(v):
        return f"Rp {v*multiplier:,.0f}" if show_idr else f"${v:,.2f}"

    # Record snapshot
    if books:
        tot = total_usd(books, prices)
        bvals = {b: book_value(p, prices) for b, p in books.items()}
        hist = st.session_state["history"]
        hist.append({"ts": datetime.utcnow().isoformat(), "total_usd": tot, "book_values": bvals})
        if len(hist) > hist_len:
            hist = hist[-hist_len:]
        st.session_state["history"] = hist
        # Persist history to disk every 5 snapshots to avoid excessive writes
        if len(hist) % 5 == 0 or len(hist) <= 2:
            save_persistent(st.session_state["books"], hist)
    else:
        tot  = 0.0
        bvals = {}

    metrics = calc_metrics(st.session_state["history"])

    if price_data.get("error"):
        st.error(f"⚠ Price feed: {price_data['error']}")
    if idr_data.get("error"):
        st.warning(f"⚠ IDR rate: {idr_data['error']}")

    if not books:
        st.markdown("""
        <div style="padding:60px 0;text-align:center;">
          <div style="font-size:40px;margin-bottom:12px;">📈</div>
          <div style="font-size:18px;font-weight:700;color:#1a1f36;margin-bottom:6px;">Add your first trading book</div>
          <div style="font-size:13px;color:#8898aa;">Use the sidebar to add a book with USDT, BTC, or ETH holdings.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ═══════════════════════════════════════════════════════════════════════
    # 1. STAT BAR (CoinGecko-style top strip)
    # ═══════════════════════════════════════════════════════════════════════
    hist_data = st.session_state["history"]
    prev_tot  = hist_data[-2]["total_usd"] if len(hist_data) >= 2 else tot
    chg_24h   = ((tot - prev_tot) / prev_tot * 100) if prev_tot else 0
    chg_cls   = "up" if chg_24h >= 0 else "down"
    chg_sign  = "▲" if chg_24h >= 0 else "▼"

    btc_dom   = (books_val_by_asset(books, prices, "BTC") / tot * 100) if tot else 0
    eth_dom   = (books_val_by_asset(books, prices, "ETH") / tot * 100) if tot else 0
    usdt_dom  = (books_val_by_asset(books, prices, "USDT") / tot * 100) if tot else 0

    sig_label, sig_cls, sig_emoji = metrics.get("signal", ("—", "risk-neutral", "🟡"))

    st.markdown(f"""
    <div class="stat-bar">
      <div class="stat-item">
        <div class="stat-label">Total Portfolio Value</div>
        <div class="stat-val">{fv(tot)}</div>
        <div class="stat-sub {chg_cls}">{chg_sign} {abs(chg_24h):.2f}% since last snapshot</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">BTC Dominance</div>
        <div class="stat-val">{btc_dom:.1f}%</div>
        <div class="stat-sub muted">of portfolio</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">ETH Dominance</div>
        <div class="stat-val">{eth_dom:.1f}%</div>
        <div class="stat-sub muted">of portfolio</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">USDT Dominance</div>
        <div class="stat-val">{usdt_dom:.1f}%</div>
        <div class="stat-sub muted">of portfolio</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">Risk Signal</div>
        <div class="stat-val">{sig_emoji} {sig_label}</div>
        <div class="stat-sub muted">Score: {metrics.get("score", "—")}/5</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">Price Source</div>
        <div class="stat-val" style="font-size:14px;">{price_data.get("source","—")}</div>
        <div class="stat-sub muted">{price_data.get("ts","—")}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 2. LIVE PRICE TICKER
    # ═══════════════════════════════════════════════════════════════════════
    btc_c = price_data.get("BTC_chg", 0)
    eth_c = price_data.get("ETH_chg", 0)

    def ticker_html(sym, price, chg, extra_label="", extra_val=""):
        cls  = "up" if chg >= 0 else "down"
        sign = "▲" if chg >= 0 else "▼"
        return (f'<div class="ticker-card">'
                f'<div class="ticker-symbol">{sym}</div>'
                f'<div class="ticker-price">${price:,.2f}</div>'
                f'<div class="ticker-chg {cls}">{sign} {abs(chg):.2f}% 24h</div>'
                + (f'<div style="font-size:10px;color:#aab0c0;margin-top:2px;">{extra_label}: {extra_val}</div>'
                   if extra_label else '')
                + '</div>')

    st.markdown(
        '<div class="ticker-wrap">'
        + ticker_html("₿ Bitcoin",  prices["BTC"],  btc_c,
                      "IDR", f"Rp {prices['BTC']*idr_rate:,.0f}")
        + ticker_html("Ξ Ethereum", prices["ETH"],  eth_c,
                      "IDR", f"Rp {prices['ETH']*idr_rate:,.0f}")
        + ticker_html("💵 USDT",    prices["USDT"], 0.0,
                      "Kurs Tengah", f"Rp {idr_rate:,.0f}")
        + f'<div class="ticker-card" style="background:#f0f3ff;border-color:#c7d9ff;">'
          f'<div class="ticker-symbol" style="color:#3b5af5;">Portfolio Total</div>'
          f'<div class="ticker-price" style="color:#3b5af5;">{fv(tot)}</div>'
          f'<div class="ticker-chg {"up" if chg_24h>=0 else "down"}">'
          f'{"▲" if chg_24h>=0 else "▼"} {abs(chg_24h):.2f}%</div>'
          f'</div>'
        + '</div>',
        unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 3. CHARTS (prominent, at the top)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="sec-head">Portfolio Charts</p>', unsafe_allow_html=True)
    chart_cols = st.columns([3, 1])
    with chart_cols[0]:
        fig = chart_portfolio(hist_data, show_idr, idr_rate, books)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Chart appears after 2+ price snapshots (~2 min).", icon="📈")
        fig_dd = chart_drawdown(hist_data)
        if fig_dd:
            st.plotly_chart(fig_dd, use_container_width=True, config={"displayModeBar": False})
    with chart_cols[1]:
        fig_alloc = chart_allocation(books, prices)
        if fig_alloc:
            st.plotly_chart(fig_alloc, use_container_width=True, config={"displayModeBar": False})

    # ═══════════════════════════════════════════════════════════════════════
    # 4. TRADING BOOKS TABLE  (CoinGecko coin-list style)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="sec-head">Trading Books</p>', unsafe_allow_html=True)

    asset_colors = {"BTC": "#f7931a", "ETH": "#627eea", "USDT": "#26a17b"}
    rows_html = ""
    for rank, (bname, pos) in enumerate(books.items(), 1):
        bval    = book_value(pos, prices)
        pct_tot = bval / tot * 100 if tot else 0
        pct_cls = "up" if bval > 0 else "muted"

        # Asset breakdown mini-badges
        asset_badges = "".join(
            f'<span class="asset-dot" style="background:{asset_colors.get(a,"#aaa")};"></span>'
            f'<span style="font-size:11px;color:#1a1f36;margin-right:8px;">'
            f'{a} {v:,.4g}</span>'
            for a, v in pos.items() if v > 0
        )

        # Bars for allocation
        bar_w = min(100, pct_tot)
        rows_html += f"""
        <tr>
          <td style="color:#aab0c0;font-size:12px;width:32px;">{rank}</td>
          <td>
            <span class="book-tag">{bname[:12]}</span>
          </td>
          <td>{asset_badges or '<span style="color:#aab0c0;font-size:11px;">empty</span>'}</td>
          <td class="right" style="font-weight:700;">{fv(bval)}</td>
          <td class="right {pct_cls}">{pct_tot:.1f}%</td>
          <td style="min-width:120px;">
            <div style="background:#edf0f7;border-radius:4px;height:6px;width:100%;">
              <div style="background:#3b5af5;border-radius:4px;height:6px;width:{bar_w:.0f}%;"></div>
            </div>
          </td>
        </tr>"""

    st.markdown(f"""
    <table class="book-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Book</th>
          <th>Holdings</th>
          <th class="right">Value ({unit})</th>
          <th class="right">% of Portfolio</th>
          <th>Allocation Bar</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 5. PORTFOLIO METRICS
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="sec-head" style="margin-top:22px;">Portfolio Metrics</p>',
                unsafe_allow_html=True)

    if not metrics:
        st.info("Accumulating data — metrics appear after 2+ snapshots (~2 min).", icon="⏳")
    else:
        # Risk signal pill
        sl, sc, se = metrics["signal"]
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px;">'
            f'<div class="risk-badge {sc}">{se} {sl}</div>'
            f'<div style="font-size:12px;color:#8898aa;">Score {metrics["score"]:+d}/5 · '
            f'Based on Sharpe, drawdown, current DD, volatility, return</div>'
            f'</div>', unsafe_allow_html=True)

        def mc(label, val, sub, color="#1a1f36"):
            return (f'<div class="mbox">'
                    f'<div class="mbox-label">{label}</div>'
                    f'<div class="mbox-val" style="color:{color};">{val}</div>'
                    f'<div class="mbox-sub">{sub}</div>'
                    f'</div>')

        dd_c  = "#f6465d" if metrics["max_drawdown"]<-20 else ("#d97706" if metrics["max_drawdown"]<-10 else "#0ecb81")
        sh_c  = "#0ecb81" if metrics["sharpe"]>1 else ("#d97706" if metrics["sharpe"]>0 else "#f6465d")
        rt_c  = "#0ecb81" if metrics["total_ret"]>=0 else "#f6465d"
        vl_c  = "#f6465d" if metrics["volatility"]>60 else ("#d97706" if metrics["volatility"]>30 else "#0ecb81")

        st.markdown(
            '<div class="metric-row">'
            + mc("Total Return",   f'{metrics["total_ret"]:+.2f}%',  "Since first snapshot", rt_c)
            + mc("Max Profit",     f'{metrics["max_profit"]:+.2f}%', "Peak from start", "#0ecb81")
            + mc("Max Drawdown",   f'{metrics["max_drawdown"]:.2f}%',"Peak-to-trough", dd_c)
            + mc("Current DD",     f'{metrics["current_dd"]:.2f}%',  "From last peak",
                 "#f6465d" if metrics["current_dd"]<-5 else "#8898aa")
            + mc("Sharpe Ratio",   f'{metrics["sharpe"]:.3f}',       ">1.5 strong · <0 weak", sh_c)
            + mc("Sortino Ratio",  f'{metrics["sortino"]:.3f}',      "Downside-adj Sharpe", "#8898aa")
            + mc("Calmar Ratio",   f'{metrics["calmar"]:.3f}',       "Return / |Max DD|", "#8898aa")
            + mc("Volatility",     f'{metrics["volatility"]:.1f}%',  "Annualised", vl_c)
            + '</div>', unsafe_allow_html=True)

    with st.expander("📋 Snapshot history", expanded=False):
        if hist_data:
            hdf = pd.DataFrame([{
                "Time": h["ts"],
                "Total USD": round(h["total_usd"], 2),
                **{f"{k} USD": round(v, 2) for k, v in h.get("book_values", {}).items()}
            } for h in reversed(hist_data)])
            hdf.index = range(1, len(hdf)+1)
            st.dataframe(hdf, use_container_width=True, height=280)

    st.markdown("""
    <div class="footer">
      Portfolio Manager v3 · Prices: CoinGecko / Binance (free) ·
      IDR: BCA e-Rate Kurs Tengah · Books saved to disk — survives refresh ·
      Not financial advice
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY (needs to be defined before main() calls it)
# ─────────────────────────────────────────────────────────────────────────────
def books_val_by_asset(books: dict, prices: dict, asset: str) -> float:
    return sum(pos.get(asset, 0) * prices.get(asset, 0) for pos in books.values())


if __name__ == "__main__":
    main()
