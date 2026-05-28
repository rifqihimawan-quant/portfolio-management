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
    """
    Compute full suite of portfolio metrics across 3 categories:
      Performance: cumulative return, CAGR, max profit, best/worst snapshot
      Risk:        Sharpe, Sortino, Calmar, Omega, VaR 95, CVaR 95,
                   max drawdown, current drawdown, volatility, Ulcer Index
      Benchmark:   vs BTC-hold, vs crypto hedge fund avg (Sharpe 1.6, vol 46%)
    """
    if len(history) < 2:
        return {}
    vals = np.array([h["total_usd"] for h in history], dtype=float)
    rets = np.diff(vals) / np.where(vals[:-1] != 0, vals[:-1], 1)
    rets = rets[np.isfinite(rets)]
    if not len(rets):
        return {}

    ANN = 288   # ~5-min snapshots per day

    # ── Returns ──────────────────────────────────────────────────────────
    tot_ret  = (vals[-1] - vals[0]) / vals[0] if vals[0] else 0
    max_prof = (np.max(vals) - vals[0]) / vals[0] if vals[0] else 0
    n_days   = len(vals) / ANN
    cagr     = ((vals[-1] / vals[0]) ** (365 / max(n_days, 0.01)) - 1) if vals[0] else 0
    best_snap  = float(np.max(rets)) * 100
    worst_snap = float(np.min(rets)) * 100

    # ── Volatility & risk-adjusted ────────────────────────────────────────
    mu  = float(np.mean(rets))
    std = float(np.std(rets, ddof=1)) if len(rets) > 1 else 0
    vol_ann = std * np.sqrt(ANN) * 100
    sharpe  = mu / std * np.sqrt(ANN) if std else 0

    neg   = rets[rets < 0]
    dstd  = float(np.std(neg, ddof=1)) if len(neg) > 1 else 0
    sortino = mu / dstd * np.sqrt(ANN) if dstd else 0

    # Omega ratio (threshold = 0)
    gains  = np.sum(rets[rets > 0])
    losses = np.abs(np.sum(rets[rets < 0]))
    omega  = gains / losses if losses > 1e-10 else float("inf")

    # ── Drawdown ─────────────────────────────────────────────────────────
    peak    = np.maximum.accumulate(vals)
    dd      = (vals - peak) / np.where(peak != 0, peak, 1)
    max_dd  = float(dd.min())
    cur_dd  = float(dd[-1])
    calmar  = tot_ret / abs(max_dd) if abs(max_dd) > 1e-6 else 0

    # Ulcer Index = RMS of drawdown series
    ulcer = float(np.sqrt(np.mean(dd ** 2))) * 100

    # Longest drawdown (consecutive snapshots below peak)
    in_dd, longest, cur_len = False, 0, 0
    for d in dd:
        if d < -0.001:
            cur_len += 1; in_dd = True
        else:
            if in_dd: longest = max(longest, cur_len)
            cur_len = 0; in_dd = False
    longest = max(longest, cur_len)
    longest_dd_hrs = round(longest / 12, 1)   # approx hours (12 × 5-min = 1hr)

    # ── VaR / CVaR at 95% ────────────────────────────────────────────────
    var95  = float(np.percentile(rets, 5)) * 100   # 5th percentile
    cvar95 = float(np.mean(rets[rets <= np.percentile(rets, 5)])) * 100 if len(rets) >= 20 else var95

    # Recovery factor = total_ret / |max_dd|
    recovery = abs(tot_ret / max_dd) if abs(max_dd) > 1e-6 else 0

    # ── Risk signal ───────────────────────────────────────────────────────
    score = 0
    score += 1 if sharpe > 1.5   else (-1 if sharpe < 0.3 else 0)
    score += 1 if max_dd > -0.10 else (-1 if max_dd < -0.25 else 0)
    score += 1 if cur_dd > -0.05 else (-1 if cur_dd < -0.15 else 0)
    score += 1 if vol_ann < 30   else (-1 if vol_ann > 60 else 0)
    score += 1 if tot_ret > 0    else -1
    score += 1 if omega > 1.5    else (-1 if omega < 0.8 else 0)

    if   score >= 3:  sig = ("RISK-ON",  "risk-on",  "🟢")
    elif score <= -2: sig = ("RISK-OFF", "risk-off", "🔴")
    else:             sig = ("NEUTRAL",  "risk-neutral", "🟡")

    return dict(
        # Performance
        total_ret=tot_ret*100, max_profit=max_prof*100,
        cagr=cagr*100, best_snap=best_snap, worst_snap=worst_snap,
        # Risk — volatility
        sharpe=sharpe, sortino=sortino, omega=omega, calmar=calmar,
        recovery=recovery, volatility=vol_ann,
        # Risk — drawdown
        max_drawdown=max_dd*100, current_dd=cur_dd*100,
        ulcer=ulcer, longest_dd_hrs=longest_dd_hrs,
        # Risk — loss
        var95=var95, cvar95=cvar95,
        # Meta
        signal=sig, score=score,
    )

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

    # Y-axis range derived from Total line only (not per-book sub-lines)
    total_vals = df["total_usd"] * mul
    y_min = max(0, total_vals.min() * 0.97)
    y_max = total_vals.max() * 1.03

    # Merge yaxis override into a local copy so there's no duplicate keyword
    portfolio_layout = {
        **CHART_STYLE,
        "yaxis": dict(
            range=[y_min, y_max],
            gridcolor="#f0f2f8", linecolor="#e3e8f0",
            tickfont=dict(size=10, color="#aab0c0"),
            tickformat=",.0f",
        ),
    }
    fig.update_layout(**portfolio_layout,
        title=dict(text="Portfolio Value — All Books Combined",
                   font=dict(size=14, color="#1a1f36", weight=700), x=0),
        yaxis_title=f"Value ({unit})", height=300,
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
        margin=dict(l=10, r=10, t=36, b=10), height=320,
        title=dict(text="Allocation by Book & Asset",
                   font=dict(size=13, color="#1a1f36"), x=0),
        legend=dict(font=dict(size=11, color="#8898aa"), bgcolor="rgba(0,0,0,0)",
                    orientation="h", yanchor="bottom", y=-0.22, x=0.5, xanchor="center"),
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
    # 3. CHARTS — stacked: portfolio value | drawdown | allocation pie
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="sec-head">Portfolio Charts</p>', unsafe_allow_html=True)

    # Row 1: Portfolio value (full width)
    fig = chart_portfolio(hist_data, show_idr, idr_rate, books)
    if fig:
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Chart appears after 2+ price snapshots (~2 min).", icon="📈")

    # Row 2: Drawdown (full width)
    fig_dd = chart_drawdown(hist_data)
    if fig_dd:
        st.plotly_chart(fig_dd, use_container_width=True, config={"displayModeBar": False})

    # Row 3: Allocation pie (full width, below)
    fig_alloc = chart_allocation(books, prices)
    if fig_alloc:
        st.plotly_chart(fig_alloc, use_container_width=True, config={"displayModeBar": False})

    # ═══════════════════════════════════════════════════════════════════════
    # 4. TRADING BOOKS TABLE  (CoinGecko coin-list style)
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="sec-head">Trading Books</p>', unsafe_allow_html=True)

    # Asset colours & bar chart constants
    asset_colors = {"BTC": "#f7931a", "ETH": "#627eea", "USDT": "#26a17b"}
    BAR_W, BAR_H = 180, 22    # total bar width (px) and height

    rows_html = ""
    for rank, (bname, pos) in enumerate(books.items(), 1):
        bval    = book_value(pos, prices)
        pct_tot = bval / tot * 100 if tot else 0
        pct_cls = "up" if bval > 0 else "muted"

        # ── Inline stacked bar chart for Holdings column ──────────────────
        # Each asset segment width is proportional to its USD share of THIS book
        if bval > 0:
            segments = [
                (a, amt, amt * prices.get(a, 0))
                for a, amt in pos.items()
                if amt > 0 and prices.get(a, 0) > 0
            ]
            bar_segs = ""
            label_parts = []
            for a, amt, usd in segments:
                seg_w = usd / bval * BAR_W
                col   = asset_colors.get(a, "#aaa")
                title = f"{a}: {amt:,.6g} (${usd:,.2f})"
                bar_segs += (
                    f'<div title="{title}" style="display:inline-block;'
                    f'width:{seg_w:.1f}px;height:{BAR_H}px;background:{col};'
                    f'vertical-align:middle;cursor:default;"></div>'
                )
                label_parts.append(
                    f'<span style="display:inline-flex;align-items:center;gap:3px;'
                    f'margin-right:10px;font-size:10px;color:#4a5568;">'
                    f'<span style="width:8px;height:8px;border-radius:2px;'
                    f'background:{col};display:inline-block;flex-shrink:0;"></span>'
                    f'{a} <b>{amt:,.4g}</b></span>'
                )
            holding_cell = (
                f'<div style="border-radius:5px;overflow:hidden;height:{BAR_H}px;'
                f'width:{BAR_W}px;background:#edf0f7;display:flex;">'
                f'{bar_segs}</div>'
                f'<div style="display:flex;flex-wrap:wrap;gap:0;margin-top:5px;">'
                f'{"".join(label_parts)}</div>'
            )
        else:
            holding_cell = '<span style="color:#aab0c0;font-size:11px;">empty</span>'

        rows_html += f"""
        <tr>
          <td style="color:#aab0c0;font-size:12px;width:32px;">{rank}</td>
          <td><span class="book-tag">{bname[:16]}</span></td>
          <td style="min-width:220px;">{holding_cell}</td>
          <td class="right" style="font-weight:700;">{fv(bval)}</td>
          <td class="right {pct_cls}">{pct_tot:.1f}%</td>
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
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 5. PORTFOLIO METRICS — 3 categories with benchmarks
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown('<p class="sec-head" style="margin-top:22px;">Portfolio Metrics</p>',
                unsafe_allow_html=True)

    if not metrics:
        st.info("Accumulating data — metrics appear after 2+ snapshots (~2 min).", icon="⏳")
    else:
        # ── Risk signal banner ────────────────────────────────────────────
        sl, sc, se = metrics["signal"]
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:18px;'
            f'background:#f7f8fc;border:1px solid #e3e8f0;border-radius:10px;padding:12px 18px;">'
            f'<div class="risk-badge {sc}">{se} {sl}</div>'
            f'<div style="font-size:12px;color:#8898aa;">'
            f'Score {metrics["score"]:+d}/6 · Sharpe · Drawdown · Volatility · Return · Omega'
            f'</div></div>', unsafe_allow_html=True)

        # ── Helper: metric table row ──────────────────────────────────────
        def mrow(label, your_val, ideal, benchmark, bm_source, note, val_color):
            return f"""
            <tr>
              <td style="padding:10px 14px;font-size:12px;font-weight:600;color:#1a1f36;
                         border-bottom:1px solid #edf0f7;min-width:160px;">{label}</td>
              <td style="padding:10px 14px;font-size:15px;font-weight:800;color:{val_color};
                         border-bottom:1px solid #edf0f7;font-family:'JetBrains Mono',monospace;
                         text-align:right;">{your_val}</td>
              <td style="padding:10px 14px;font-size:12px;color:#0ecb81;font-weight:600;
                         border-bottom:1px solid #edf0f7;text-align:center;">{ideal}</td>
              <td style="padding:10px 14px;font-size:12px;color:#3b5af5;font-weight:500;
                         border-bottom:1px solid #edf0f7;text-align:center;">{benchmark}</td>
              <td style="padding:10px 14px;font-size:11px;color:#8898aa;
                         border-bottom:1px solid #edf0f7;">{bm_source}</td>
              <td style="padding:10px 14px;font-size:11px;color:#aab0c0;
                         border-bottom:1px solid #edf0f7;">{note}</td>
            </tr>"""

        def mtable(rows_html):
            return f"""
            <table style="width:100%;border-collapse:collapse;background:#fff;
                          border:1px solid #e3e8f0;border-radius:10px;overflow:hidden;">
              <thead>
                <tr style="background:#f7f8fc;">
                  <th style="padding:9px 14px;font-size:10px;font-weight:700;color:#8898aa;
                             letter-spacing:.08em;text-transform:uppercase;text-align:left;
                             border-bottom:2px solid #e3e8f0;">Metric</th>
                  <th style="padding:9px 14px;font-size:10px;font-weight:700;color:#8898aa;
                             letter-spacing:.08em;text-transform:uppercase;text-align:right;
                             border-bottom:2px solid #e3e8f0;">Your Value</th>
                  <th style="padding:9px 14px;font-size:10px;font-weight:700;color:#0ecb81;
                             letter-spacing:.08em;text-transform:uppercase;text-align:center;
                             border-bottom:2px solid #e3e8f0;">Ideal Target</th>
                  <th style="padding:9px 14px;font-size:10px;font-weight:700;color:#3b5af5;
                             letter-spacing:.08em;text-transform:uppercase;text-align:center;
                             border-bottom:2px solid #e3e8f0;">Benchmark</th>
                  <th style="padding:9px 14px;font-size:10px;font-weight:700;color:#8898aa;
                             letter-spacing:.08em;text-transform:uppercase;
                             border-bottom:2px solid #e3e8f0;">Source</th>
                  <th style="padding:9px 14px;font-size:10px;font-weight:700;color:#8898aa;
                             letter-spacing:.08em;text-transform:uppercase;
                             border-bottom:2px solid #e3e8f0;">Interpretation</th>
                </tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>"""

        def col(v, good, bad):
            if isinstance(v, str): return "#1a1f36"
            return "#0ecb81" if v >= good else ("#f6465d" if v <= bad else "#d97706")

        m = metrics

        # ════════════════════════════════════════════════════════════════
        # CATEGORY 1 — PERFORMANCE METRICS
        # ════════════════════════════════════════════════════════════════
        st.markdown('''
        <div style="display:flex;align-items:center;gap:10px;margin:10px 0 8px;">
          <div style="font-size:13px;font-weight:800;color:#1a1f36;">📈 Performance Metrics</div>
          <div style="font-size:11px;color:#8898aa;">Returns focus — how much you made vs risk taken</div>
        </div>''', unsafe_allow_html=True)

        perf_rows = (
            mrow("Cumulative Return",
                 f'{m["total_ret"]:+.2f}%',
                 "> +15%/yr",
                 "~36% (2025 avg)",
                 "Crypto Fund Research 2025",
                 "Total gain since first snapshot",
                 col(m["total_ret"], 15, 0))
            + mrow("CAGR (annualised)",
                 f'{m["cagr"]:+.1f}%',
                 "> +20%/yr",
                 "~36%/yr",
                 "Crypto HF avg 2025",
                 "Compound annual growth rate",
                 col(m["cagr"], 20, 0))
            + mrow("Max Profit (peak)",
                 f'{m["max_profit"]:+.2f}%',
                 "> +10%",
                 "—",
                 "—",
                 "Best gain from portfolio start",
                 col(m["max_profit"], 10, 0))
            + mrow("Best Snapshot",
                 f'{m["best_snap"]:+.3f}%',
                 "> 0%",
                 "—",
                 "—",
                 "Largest single-interval gain",
                 "#0ecb81" if m["best_snap"] > 0 else "#8898aa")
            + mrow("Worst Snapshot",
                 f'{m["worst_snap"]:+.3f}%',
                 "> −0.5%",
                 "—",
                 "—",
                 "Largest single-interval loss",
                 "#f6465d" if m["worst_snap"] < -1 else "#d97706" if m["worst_snap"] < -0.5 else "#0ecb81")
        )
        st.markdown(mtable(perf_rows), unsafe_allow_html=True)

        # ════════════════════════════════════════════════════════════════
        # CATEGORY 2 — RISK METRICS
        # ════════════════════════════════════════════════════════════════
        st.markdown('''
        <div style="display:flex;align-items:center;gap:10px;margin:18px 0 8px;">
          <div style="font-size:13px;font-weight:800;color:#1a1f36;">🛡 Risk Metrics</div>
          <div style="font-size:11px;color:#8898aa;">Volatility · drawdown · loss probability</div>
        </div>''', unsafe_allow_html=True)

        risk_rows = (
            mrow("Sharpe Ratio",
                 f'{m["sharpe"]:.3f}',
                 "> 1.5",
                 "1.6 (crypto HF avg)",
                 "Crypto Fund Research 2025",
                 "Return per unit of total risk",
                 col(m["sharpe"], 1.5, 0.3))
            + mrow("Sortino Ratio",
                 f'{m["sortino"]:.3f}',
                 "> 2.0",
                 "2.03 (quant strategies)",
                 "Crypto Fund Research 2025",
                 "Return per unit of downside risk only",
                 col(m["sortino"], 2.0, 0.5))
            + mrow("Omega Ratio",
                 f'{m["omega"]:.3f}' if m["omega"] != float("inf") else "∞",
                 "> 1.5",
                 "> 1.0 (profitable)",
                 "Industry standard",
                 "Gains-to-losses ratio (threshold = 0)",
                 col(m["omega"], 1.5, 0.8) if m["omega"] != float("inf") else "#0ecb81")
            + mrow("Calmar Ratio",
                 f'{m["calmar"]:.3f}',
                 "> 1.0",
                 "1.0–3.0 (top hedge funds)",
                 "FasterCapital / industry",
                 "Annualised return / |Max Drawdown|",
                 col(m["calmar"], 1.0, 0.3))
            + mrow("Recovery Factor",
                 f'{m["recovery"]:.3f}',
                 "> 1.0",
                 "> 1.0",
                 "Industry standard",
                 "How well returns offset drawdowns",
                 col(m["recovery"], 1.0, 0.3))
            + mrow("Annualised Volatility",
                 f'{m["volatility"]:.1f}%',
                 "< 50%",
                 "~46% (crypto HF avg)",
                 "Crypto Fund Research 2025",
                 "Standard deviation of returns × √288",
                 col(-m["volatility"], -50, -80))
            + mrow("Max Drawdown",
                 f'{m["max_drawdown"]:.2f}%',
                 "> −20%",
                 "−25% to −40% typical",
                 "Bridgewater / crypto HFs",
                 "Worst peak-to-trough decline",
                 col(m["max_drawdown"], -10, -25))
            + mrow("Current Drawdown",
                 f'{m["current_dd"]:.2f}%',
                 "> −5%",
                 "—",
                 "—",
                 "Distance below most recent peak",
                 col(m["current_dd"], -5, -15))
            + mrow("Ulcer Index",
                 f'{m["ulcer"]:.2f}%',
                 "< 5%",
                 "< 10%",
                 "Industry standard",
                 "RMS of drawdown — penalises deep/long DDs",
                 col(-m["ulcer"], -5, -15))
            + mrow("Longest Drawdown",
                 f'{m["longest_dd_hrs"]:.1f}h',
                 "< 24h",
                 "—",
                 "—",
                 "Longest consecutive time below peak",
                 col(-m["longest_dd_hrs"], -24, -168))
            + mrow("VaR 95% (per snapshot)",
                 f'{m["var95"]:.3f}%',
                 "> −0.5%",
                 "—",
                 "—",
                 "Worst expected loss 95% of the time",
                 col(m["var95"], -0.5, -1.5))
            + mrow("CVaR 95% (Exp. Shortfall)",
                 f'{m["cvar95"]:.3f}%',
                 "> −1.0%",
                 "—",
                 "—",
                 "Average loss in the worst 5% of snapshots",
                 col(m["cvar95"], -1.0, -2.5))
        )
        st.markdown(mtable(risk_rows), unsafe_allow_html=True)

        # ════════════════════════════════════════════════════════════════
        # CATEGORY 3 — BENCHMARK COMPARISON
        # ════════════════════════════════════════════════════════════════
        st.markdown('''
        <div style="display:flex;align-items:center;gap:10px;margin:18px 0 8px;">
          <div style="font-size:13px;font-weight:800;color:#1a1f36;">🏆 Benchmark Comparison</div>
          <div style="font-size:11px;color:#8898aa;">How you compare to known benchmarks</div>
        </div>''', unsafe_allow_html=True)

        # Benchmark reference table (static — from research)
        bench_html = """
        <table style="width:100%;border-collapse:collapse;background:#fff;
                      border:1px solid #e3e8f0;border-radius:10px;overflow:hidden;margin-bottom:14px;">
          <thead>
            <tr style="background:#f7f8fc;">
              <th style="padding:9px 14px;font-size:10px;font-weight:700;color:#8898aa;letter-spacing:.08em;text-transform:uppercase;text-align:left;border-bottom:2px solid #e3e8f0;">Fund / Benchmark</th>
              <th style="padding:9px 14px;font-size:10px;font-weight:700;color:#8898aa;letter-spacing:.08em;text-transform:uppercase;text-align:center;border-bottom:2px solid #e3e8f0;">Sharpe</th>
              <th style="padding:9px 14px;font-size:10px;font-weight:700;color:#8898aa;letter-spacing:.08em;text-transform:uppercase;text-align:center;border-bottom:2px solid #e3e8f0;">Sortino</th>
              <th style="padding:9px 14px;font-size:10px;font-weight:700;color:#8898aa;letter-spacing:.08em;text-transform:uppercase;text-align:center;border-bottom:2px solid #e3e8f0;">Calmar</th>
              <th style="padding:9px 14px;font-size:10px;font-weight:700;color:#8898aa;letter-spacing:.08em;text-transform:uppercase;text-align:center;border-bottom:2px solid #e3e8f0;">Vol</th>
              <th style="padding:9px 14px;font-size:10px;font-weight:700;color:#8898aa;letter-spacing:.08em;text-transform:uppercase;border-bottom:2px solid #e3e8f0;">Notes</th>
            </tr>
          </thead>
          <tbody>
            <tr style="background:#eff6ff;">
              <td style="padding:9px 14px;font-size:12px;font-weight:800;color:#3b5af5;border-bottom:1px solid #edf0f7;">Your Portfolio</td>
              <td style="padding:9px 14px;font-size:13px;font-weight:700;color:#3b5af5;font-family:'JetBrains Mono',monospace;text-align:center;border-bottom:1px solid #edf0f7;">""" + f"{m['sharpe']:.2f}" + """</td>
              <td style="padding:9px 14px;font-size:13px;font-weight:700;color:#3b5af5;font-family:'JetBrains Mono',monospace;text-align:center;border-bottom:1px solid #edf0f7;">""" + f"{m['sortino']:.2f}" + """</td>
              <td style="padding:9px 14px;font-size:13px;font-weight:700;color:#3b5af5;font-family:'JetBrains Mono',monospace;text-align:center;border-bottom:1px solid #edf0f7;">""" + f"{m['calmar']:.2f}" + """</td>
              <td style="padding:9px 14px;font-size:13px;font-weight:700;color:#3b5af5;font-family:'JetBrains Mono',monospace;text-align:center;border-bottom:1px solid #edf0f7;">""" + f"{m['volatility']:.0f}%" + """</td>
              <td style="padding:9px 14px;font-size:11px;color:#8898aa;border-bottom:1px solid #edf0f7;">Live</td>
            </tr>
            <tr>
              <td style="padding:9px 14px;font-size:12px;font-weight:600;color:#1a1f36;border-bottom:1px solid #edf0f7;">Crypto HF Average (2025)</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">1.60</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">2.03</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">—</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">46%</td>
              <td style="padding:9px 14px;font-size:11px;color:#8898aa;border-bottom:1px solid #edf0f7;">Crypto Fund Research 2025</td>
            </tr>
            <tr>
              <td style="padding:9px 14px;font-size:12px;font-weight:600;color:#1a1f36;border-bottom:1px solid #edf0f7;">Top Quant Crypto Strategies</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">1.58</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">2.03</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">—</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">—</td>
              <td style="padding:9px 14px;font-size:11px;color:#8898aa;border-bottom:1px solid #edf0f7;">Quant backtests, Crypto Fund Research</td>
            </tr>
            <tr>
              <td style="padding:9px 14px;font-size:12px;font-weight:600;color:#1a1f36;border-bottom:1px solid #edf0f7;">Renaissance Medallion (est.)</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">> 2.0</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">—</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">—</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">—</td>
              <td style="padding:9px 14px;font-size:11px;color:#8898aa;border-bottom:1px solid #edf0f7;">Arca Labs / Nobel-level research</td>
            </tr>
            <tr>
              <td style="padding:9px 14px;font-size:12px;font-weight:600;color:#1a1f36;border-bottom:1px solid #edf0f7;">S&P 500 (historical)</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">0.40</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">—</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">—</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;border-bottom:1px solid #edf0f7;">16%</td>
              <td style="padding:9px 14px;font-size:11px;color:#8898aa;border-bottom:1px solid #edf0f7;">Arca Labs (1926–2024 record)</td>
            </tr>
            <tr>
              <td style="padding:9px 14px;font-size:12px;font-weight:600;color:#1a1f36;">60/40 Portfolio (historical)</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;">0.50</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;">—</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;">—</td>
              <td style="padding:9px 14px;font-size:12px;text-align:center;color:#1a1f36;">~12%</td>
              <td style="padding:9px 14px;font-size:11px;color:#8898aa;">Arca Labs</td>
            </tr>
          </tbody>
        </table>"""
        st.markdown(bench_html, unsafe_allow_html=True)

        st.markdown(
            '<div style="font-size:10px;color:#aab0c0;margin-top:4px;">'
            'Benchmark data from: Crypto Fund Research 2025, The Arca Labs (2026), '
            'FasterCapital. Past performance does not guarantee future results. '
            'Not financial advice.</div>', unsafe_allow_html=True)

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
